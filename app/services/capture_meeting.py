"""Meeting URL validation, org host maps, optional Jitsi JWT."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import decrypt_str, encrypt_str
from app.models import InstanceSettings, OrgCaptureJitsiHost, Organization, User, WorkerNode
from app.services.capture_platforms import allowed_connectors, catalog_entry
from app.services.export import safe_filename
from app.services.import_platforms import host_from_url

_MEETING_URL_RE = re.compile(r"^https?://", re.I)
_DEFAULT_JWT_APP_ID = "chat"
DEFAULT_CAPTURE_BOT_DISPLAY_NAME = "Transcription Bot"
_CAPTURE_BOT_NAME_MAX_LEN = 128
_TELEMOST_HOSTS = frozenset({"telemost.yandex.ru", "telemost.yandex.com"})


def normalize_capture_bot_display_name(raw: str | None) -> str | None:
    name = (raw or "").strip()
    if not name:
        return None
    return name[:_CAPTURE_BOT_NAME_MAX_LEN]


def org_capture_bot_display_name(org: Organization) -> str:
    stored = normalize_capture_bot_display_name(org.capture_bot_display_name)
    if stored:
        return stored
    return DEFAULT_CAPTURE_BOT_DISPLAY_NAME


def resolve_capture_bot_display_name(
    *,
    user: User | None,
    org: Organization,
    override: str | None = None,
) -> str:
    """Per-request override, then user profile, then org default."""
    explicit = normalize_capture_bot_display_name(override)
    if explicit:
        return explicit
    if user is not None:
        user_stored = normalize_capture_bot_display_name(user.capture_bot_display_name)
        if user_stored:
            return user_stored
    return org_capture_bot_display_name(org)


def resolve_capture_prefs(
    user: User,
    org: Organization | None,
    settings: InstanceSettings,
) -> dict[str, Any]:
    org_effective = org_capture_bot_display_name(org) if org is not None else DEFAULT_CAPTURE_BOT_DISPLAY_NAME
    user_raw = normalize_capture_bot_display_name(user.capture_bot_display_name)
    org_raw = normalize_capture_bot_display_name(org.capture_bot_display_name if org is not None else None)
    if org is not None:
        effective = resolve_capture_bot_display_name(user=user, org=org)
    elif user_raw:
        effective = user_raw
    else:
        effective = DEFAULT_CAPTURE_BOT_DISPLAY_NAME
    if user_raw:
        source = "user"
    elif org_raw:
        source = "org"
    else:
        source = "default"
    return {
        "capture_enabled": bool(settings.capture_enabled),
        "bot_display_name": effective,
        "source": source,
        "org_bot_display_name": org_effective,
    }


class CaptureMeetingError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CaptureTarget:
    connector: str
    meeting_url: str
    meeting_host: str
    meeting_room: str
    pin: str
    worker: WorkerNode
    jwt: str | None


def normalize_host(host: str) -> str:
    """Hostname only, e.g. meet.example.com (accepts pasted meeting URLs)."""
    value = (host or "").strip()
    if not value:
        return ""
    if "://" in value or value.startswith("//"):
        parsed = urlparse(value if "://" in value else f"https:{value}")
        value = (parsed.hostname or "").strip().lower()
    else:
        value = value.split("/")[0].split("?")[0].strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return value


def is_telemost_meeting_url(meeting_url: str) -> bool:
    try:
        parse_telemost_meeting(meeting_url)
        return True
    except CaptureMeetingError:
        return False


def parse_telemost_meeting(meeting_url: str) -> tuple[str, str]:
    raw = meeting_url.strip()
    if not _MEETING_URL_RE.match(raw):
        raise CaptureMeetingError("invalid_url")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise CaptureMeetingError("invalid_url")
    host = normalize_host(parsed.hostname or "")
    if host not in _TELEMOST_HOSTS:
        raise CaptureMeetingError("invalid_url")
    parts = [part for part in (parsed.path or "").strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] in {"j", "private-join"} and parts[1]:
        return host, parts[1]
    raise CaptureMeetingError("invalid_url")


def detect_capture_connector(meeting_url: str, settings_allowed: list[str]) -> str | None:
    raw = meeting_url.strip()
    if is_telemost_meeting_url(raw):
        return "telemost" if "telemost" in settings_allowed else None
    if "jitsi" not in settings_allowed:
        return None
    from app.services.import_platforms import catalog_platform_for_host, host_from_url

    host = normalize_host(host_from_url(raw))
    if not host or catalog_platform_for_host(host) is not None:
        return None
    try:
        parse_meeting_room(raw)
        return "jitsi"
    except CaptureMeetingError:
        return None


def import_url_routes_to_capture(url: str, settings: InstanceSettings) -> bool:
    """True when POST /tasks/import should create a capture task instead."""
    from app.services.capture_platforms import allowed_connectors

    if not settings.capture_enabled:
        return False
    return detect_capture_connector(url, allowed_connectors(settings)) is not None


def import_url_looks_like_meeting(url: str) -> bool:
    if is_telemost_meeting_url(url.strip()):
        return True
    from app.services.import_platforms import catalog_platform_for_host, host_from_url

    raw = url.strip()
    host = normalize_host(host_from_url(raw))
    if not host or catalog_platform_for_host(host) is not None:
        return False
    try:
        parse_meeting_room(raw)
        return True
    except CaptureMeetingError:
        return False


def find_org_jitsi_host(db: Session, org_id: str, meeting_host: str) -> OrgCaptureJitsiHost | None:
    target = normalize_host(meeting_host)
    if not target:
        return None
    rows = list(
        db.scalars(select(OrgCaptureJitsiHost).where(OrgCaptureJitsiHost.org_id == org_id)).all()
    )
    for row in rows:
        if normalize_host(row.host) == target:
            return row
    return None


def capture_storage_filename(meta: dict[str, Any] | None, suffix: str) -> str:
    """Library filename from conference room name (Jitsi path segment), not worker artifact name."""
    normalized = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
    if normalized not in {".mp3", ".m4a", ".wav"}:
        normalized = ".mp3"
    return f"{capture_storage_stem(meta)}{normalized}"


def capture_storage_stem(meta: dict[str, Any] | None) -> str:
    data = meta if isinstance(meta, dict) else {}
    room = data.get("meeting_room")
    if isinstance(room, str) and room.strip():
        return safe_filename(unquote(room.strip()), fallback="capture")
    url = data.get("meeting_url")
    if isinstance(url, str) and url.strip():
        try:
            _, parsed_room = parse_telemost_meeting(url.strip())
            return safe_filename(unquote(parsed_room), fallback="capture")
        except CaptureMeetingError:
            pass
        try:
            _, parsed_room = parse_meeting_room(url.strip())
            return safe_filename(unquote(parsed_room), fallback="capture")
        except CaptureMeetingError:
            pass
    return "capture"


def parse_meeting_room(url: str) -> tuple[str, str]:
    raw = url.strip()
    if not _MEETING_URL_RE.match(raw):
        raise CaptureMeetingError("invalid_url")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise CaptureMeetingError("invalid_url")
    host = host_from_url(raw)
    if not host:
        raise CaptureMeetingError("invalid_url")
    path = (parsed.path or "").strip("/")
    if not path:
        raise CaptureMeetingError("invalid_url")
    room = path.split("/")[-1]
    if not room:
        raise CaptureMeetingError("invalid_url")
    return host, room


def _sign_jitsi_jwt(
    *,
    secret: str,
    app_id: str,
    room: str,
    display_name: str,
) -> str:
    now = int(time.time())
    payload = {
        "aud": "jitsi",
        "iss": app_id,
        "sub": app_id,
        "room": room,
        "exp": now + 3600,
        "nbf": now - 10,
        "context": {
            "user": {
                "name": display_name,
                "moderator": False,
            }
        },
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def capture_worker_candidates(db: Session, connector_id: str) -> list[WorkerNode]:
    from app.services.capture_platforms import worker_offers_connector

    rows = list(
        db.scalars(
            select(WorkerNode).where(WorkerNode.type == "capture", WorkerNode.enabled.is_(True))
        ).all()
    )
    return [node for node in rows if worker_offers_connector(node, connector_id)]


def pick_capture_worker(db: Session, connector_id: str) -> WorkerNode | None:
    from app.services.dispatcher import pick_node

    return pick_node(db, capture_worker_candidates(db, connector_id))


def resolve_capture_target(
    db: Session,
    *,
    org: Organization,
    meeting_url: str,
    pin: str,
    settings_allowed: list[str],
    display_name: str = DEFAULT_CAPTURE_BOT_DISPLAY_NAME,
) -> CaptureTarget:
    connector = detect_capture_connector(meeting_url, settings_allowed)
    if connector is None:
        raise CaptureMeetingError("capture_disabled")
    if catalog_entry(connector) is None:
        raise CaptureMeetingError("unsupported_connector")

    raw_url = meeting_url.strip()

    if connector == "telemost":
        try:
            host, meeting_id = parse_telemost_meeting(raw_url)
        except CaptureMeetingError:
            raise
        except Exception as exc:
            raise CaptureMeetingError("invalid_url") from exc
        worker = pick_capture_worker(db, "telemost")
        if worker is None:
            raise CaptureMeetingError("capture_no_worker")
        return CaptureTarget(
            connector="telemost",
            meeting_url=raw_url,
            meeting_host=host,
            meeting_room=meeting_id,
            pin="",
            worker=worker,
            jwt=None,
        )

    try:
        host, room = parse_meeting_room(raw_url)
    except CaptureMeetingError:
        raise
    except Exception as exc:
        raise CaptureMeetingError("invalid_url") from exc

    row = find_org_jitsi_host(db, org.id, host)
    if row is None:
        raise CaptureMeetingError("meeting_host_not_configured")

    worker = db.get(WorkerNode, row.worker_id)
    if worker is None or worker.type != "capture" or not worker.enabled:
        raise CaptureMeetingError("meeting_host_not_configured")

    token: str | None = None
    # Public meet.jit.si uses guest XMPP; org JWT breaks icapture-worker join (hub-only symptom).
    if row.jwt_secret_encrypted and normalize_host(host) != "meet.jit.si":
        secret = decrypt_str(row.jwt_secret_encrypted, db)
        app_id = (row.jwt_app_id or _DEFAULT_JWT_APP_ID).strip() or _DEFAULT_JWT_APP_ID
        token = _sign_jitsi_jwt(secret=secret, app_id=app_id, room=room, display_name=display_name)

    return CaptureTarget(
        connector="jitsi",
        meeting_url=raw_url,
        meeting_host=host,
        meeting_room=room,
        pin=pin or "",
        worker=worker,
        jwt=token,
    )


def org_jitsi_hosts_public(db: Session, org_id: str) -> list[dict]:
    rows = list(
        db.scalars(
            select(OrgCaptureJitsiHost)
            .where(OrgCaptureJitsiHost.org_id == org_id)
            .order_by(OrgCaptureJitsiHost.host)
        ).all()
    )
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "id": row.id,
                "host": row.host,
                "worker_id": row.worker_id,
                "jwt_app_id": row.jwt_app_id,
                "jwt_secret_configured": bool((row.jwt_secret_encrypted or "").strip()),
            }
        )
    return out


def org_capture_worker_choices(db: Session) -> list[dict]:
    rows = list(
        db.scalars(
            select(WorkerNode)
            .where(WorkerNode.type == "capture", WorkerNode.enabled.is_(True))
            .order_by(WorkerNode.name, WorkerNode.created_at)
        ).all()
    )
    return [{"id": row.id, "name": row.name or row.base_url} for row in rows]


def normalize_jwt_app_id(raw: object) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip()
        return stripped or None
    return None


def replace_org_jitsi_hosts(
    db: Session,
    *,
    org_id: str,
    items: list[dict],
) -> list[OrgCaptureJitsiHost]:
    from app.models import new_id
    from app.timeutil import utcnow

    existing = list(
        db.scalars(select(OrgCaptureJitsiHost).where(OrgCaptureJitsiHost.org_id == org_id)).all()
    )
    by_id = {row.id: row for row in existing}
    seen_hosts: set[str] = set()
    now = utcnow()
    kept_ids: set[str] = set()

    for item in items:
        raw_host = str(item.get("host") or "")
        host = normalize_host(raw_host)
        worker_id = str(item.get("worker_id") or "").strip()
        if not host:
            raise ValueError(f"invalid host: {raw_host.strip() or '(empty)'}")
        if not worker_id:
            raise ValueError("host and worker_id required")
        if host in seen_hosts:
            raise ValueError(f"duplicate host: {host}")
        seen_hosts.add(host)
        worker = db.get(WorkerNode, worker_id)
        if worker is None or worker.type != "capture":
            raise ValueError(f"invalid capture worker: {worker_id}")

        row_id = str(item.get("id") or "").strip()
        jwt_secret = item.get("jwt_secret")
        clear_secret = item.get("clear_jwt_secret") is True
        jwt_app_id = item.get("jwt_app_id")
        if row_id and row_id in by_id:
            row = by_id[row_id]
            row.host = host
            row.worker_id = worker_id
            row.updated_at = now
            row.jwt_app_id = normalize_jwt_app_id(jwt_app_id)
            if clear_secret:
                row.jwt_secret_encrypted = None
            elif isinstance(jwt_secret, str) and jwt_secret.strip():
                row.jwt_secret_encrypted = encrypt_str(jwt_secret.strip(), db)
        else:
            secret_encrypted = None
            if isinstance(jwt_secret, str) and jwt_secret.strip():
                secret_encrypted = encrypt_str(jwt_secret.strip(), db)
            row = OrgCaptureJitsiHost(
                id=new_id(),
                org_id=org_id,
                host=host,
                worker_id=worker_id,
                jwt_secret_encrypted=secret_encrypted,
                jwt_app_id=normalize_jwt_app_id(jwt_app_id),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        kept_ids.add(row.id)

    for row in existing:
        if row.id not in kept_ids:
            db.delete(row)

    db.flush()
    return list(
        db.scalars(
            select(OrgCaptureJitsiHost)
            .where(OrgCaptureJitsiHost.org_id == org_id)
            .order_by(OrgCaptureJitsiHost.host)
        ).all()
    )
