"""Browser session storage (database or Valkey)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Protocol

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session as OrmSession

from app.config import Settings, get_settings
from app.models import Session as AuthSession
from app.models import new_id
from app.security import hash_secret, new_session_token
from app.timeutil import as_utc, utcnow

if TYPE_CHECKING:
    import redis

log = logging.getLogger("app.session_store")

SessionBackend = Literal["db", "valkey"]
KEY_PREFIX = "hub:sess:"
USER_INDEX_PREFIX = "hub:sess:user:"
IMPERSONATOR_INDEX_PREFIX = "hub:sess:impersonator_of:"


class SessionStoreError(Exception):
    """Valkey unreachable or command failed."""


@dataclass
class SessionRecord:
    id: str
    user_id: str
    token_hash: str
    impersonate_user_id: str | None
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime


class SessionStore(Protocol):
    def create(self, db: OrmSession, user_id: str, ttl_sec: int) -> str: ...

    def lookup_by_raw_token(self, db: OrmSession, raw_token: str) -> SessionRecord | None: ...

    def touch(self, db: OrmSession, record: SessionRecord, ttl_sec: int) -> None: ...

    def delete_by_raw_token(self, db: OrmSession, raw_token: str) -> None: ...

    def delete_user_sessions(self, db: OrmSession, user_id: str) -> None: ...

    def clear_impersonation_target(self, db: OrmSession, target_user_id: str) -> None: ...

    def set_impersonate(self, db: OrmSession, record: SessionRecord, target_user_id: str | None) -> None: ...

    def count_active(self, db: OrmSession) -> int: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...


_resolved_backend: SessionBackend | None = None
_store: SessionStore | None = None
_redis_client: Any | None = None


def _redis_module():
    import redis

    return redis


def _make_redis_client(url: str) -> redis.Redis:
    return _redis_module().Redis.from_url(url, decode_responses=True)


def _map_redis_error(exc: BaseException) -> SessionStoreError:
    from redis.exceptions import RedisError

    if isinstance(exc, RedisError):
        return SessionStoreError(str(exc))
    raise exc


def resolve_session_backend(settings: Settings) -> SessionBackend:
    mode = settings.SESSION_STORE.strip().lower()
    if mode == "db":
        return "db"
    if mode == "valkey":
        return "valkey"
    if settings.VALKEY_URL.strip():
        return "valkey"
    return "db"


def session_uses_valkey(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    backend = _resolved_backend or resolve_session_backend(resolved)
    return backend == "valkey"


def _record_from_row(row: AuthSession) -> SessionRecord:
    return SessionRecord(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        impersonate_user_id=row.impersonate_user_id,
        expires_at=as_utc(row.expires_at),
        created_at=as_utc(row.created_at),
        last_seen_at=as_utc(row.last_seen_at),
    )


def _row_key(token_hash: str) -> str:
    return f"{KEY_PREFIX}{token_hash}"


def _user_index_key(user_id: str) -> str:
    return f"{USER_INDEX_PREFIX}{user_id}"


def _impersonator_index_key(target_user_id: str) -> str:
    return f"{IMPERSONATOR_INDEX_PREFIX}{target_user_id}"


def _ttl_sec(expires_at: datetime, now: datetime) -> int:
    return max(1, int((expires_at - now).total_seconds()))


def _serialize_record(record: SessionRecord) -> str:
    payload = asdict(record)
    for key in ("expires_at", "created_at", "last_seen_at"):
        payload[key] = as_utc(payload[key]).isoformat()
    return json.dumps(payload, separators=(",", ":"))


def _deserialize_record(raw: str) -> SessionRecord:
    payload = json.loads(raw)
    return SessionRecord(
        id=payload["id"],
        user_id=payload["user_id"],
        token_hash=payload["token_hash"],
        impersonate_user_id=payload.get("impersonate_user_id"),
        expires_at=as_utc(datetime.fromisoformat(payload["expires_at"])),
        created_at=as_utc(datetime.fromisoformat(payload["created_at"])),
        last_seen_at=as_utc(datetime.fromisoformat(payload["last_seen_at"])),
    )


class DbSessionStore:
    def create(self, db: OrmSession, user_id: str, ttl_sec: int) -> str:
        raw = new_session_token()
        now = utcnow()
        db.add(
            AuthSession(
                id=new_id(),
                user_id=user_id,
                token_hash=hash_secret(raw),
                impersonate_user_id=None,
                expires_at=now + timedelta(seconds=ttl_sec),
                created_at=now,
                last_seen_at=now,
            )
        )
        return raw

    def lookup_by_raw_token(self, db: OrmSession, raw_token: str) -> SessionRecord | None:
        row = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_secret(raw_token),
                AuthSession.expires_at > utcnow(),
            )
        )
        if row is None:
            return None
        return _record_from_row(row)

    def touch(self, db: OrmSession, record: SessionRecord, ttl_sec: int) -> None:
        row = db.get(AuthSession, record.id)
        if row is None:
            return
        now = utcnow()
        row.last_seen_at = now
        row.expires_at = now + timedelta(seconds=ttl_sec)
        record.last_seen_at = as_utc(row.last_seen_at)
        record.expires_at = as_utc(row.expires_at)

    def delete_by_raw_token(self, db: OrmSession, raw_token: str) -> None:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_secret(raw_token)))

    def delete_user_sessions(self, db: OrmSession, user_id: str) -> None:
        db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))

    def clear_impersonation_target(self, db: OrmSession, target_user_id: str) -> None:
        db.execute(
            update(AuthSession)
            .where(AuthSession.impersonate_user_id == target_user_id)
            .values(impersonate_user_id=None)
        )

    def set_impersonate(self, db: OrmSession, record: SessionRecord, target_user_id: str | None) -> None:
        row = db.get(AuthSession, record.id)
        if row is None:
            return
        row.impersonate_user_id = target_user_id
        record.impersonate_user_id = target_user_id

    def count_active(self, db: OrmSession) -> int:
        return int(db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.expires_at > utcnow())) or 0)

    def reset(self) -> None:
        return None

    def close(self) -> None:
        return None


class ValkeySessionStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def _save(self, record: SessionRecord, now: datetime) -> None:
        ttl = _ttl_sec(record.expires_at, now)
        try:
            pipe = self._client.pipeline()
            pipe.set(_row_key(record.token_hash), _serialize_record(record), ex=ttl)
            pipe.sadd(_user_index_key(record.user_id), record.token_hash)
            pipe.execute()
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def _remove_indexes(self, record: SessionRecord) -> None:
        try:
            pipe = self._client.pipeline()
            pipe.srem(_user_index_key(record.user_id), record.token_hash)
            if record.impersonate_user_id:
                pipe.srem(_impersonator_index_key(record.impersonate_user_id), record.token_hash)
            pipe.execute()
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def create(self, db: OrmSession, user_id: str, ttl_sec: int) -> str:
        raw = new_session_token()
        now = utcnow()
        record = SessionRecord(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_secret(raw),
            impersonate_user_id=None,
            expires_at=now + timedelta(seconds=ttl_sec),
            created_at=now,
            last_seen_at=now,
        )
        self._save(record, now)
        return raw

    def lookup_by_raw_token(self, db: OrmSession, raw_token: str) -> SessionRecord | None:
        token_hash = hash_secret(raw_token)
        try:
            payload = self._client.get(_row_key(token_hash))
        except Exception as exc:
            raise _map_redis_error(exc) from exc
        if not payload:
            return None
        record = _deserialize_record(payload)
        if record.expires_at <= utcnow():
            self.delete_by_raw_token(db, raw_token)
            return None
        return record

    def touch(self, db: OrmSession, record: SessionRecord, ttl_sec: int) -> None:
        now = utcnow()
        record.last_seen_at = now
        record.expires_at = now + timedelta(seconds=ttl_sec)
        self._save(record, now)

    def delete_by_raw_token(self, db: OrmSession, raw_token: str) -> None:
        token_hash = hash_secret(raw_token)
        try:
            payload = self._client.get(_row_key(token_hash))
        except Exception as exc:
            raise _map_redis_error(exc) from exc
        if payload:
            record = _deserialize_record(payload)
            self._remove_indexes(record)
        try:
            self._client.delete(_row_key(token_hash))
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def delete_user_sessions(self, db: OrmSession, user_id: str) -> None:
        try:
            token_hashes = list(self._client.smembers(_user_index_key(user_id)))
        except Exception as exc:
            raise _map_redis_error(exc) from exc
        for token_hash in token_hashes:
            try:
                payload = self._client.get(_row_key(token_hash))
            except Exception as exc:
                raise _map_redis_error(exc) from exc
            if payload:
                record = _deserialize_record(payload)
                self._remove_indexes(record)
            try:
                self._client.delete(_row_key(token_hash))
            except Exception as exc:
                raise _map_redis_error(exc) from exc
        try:
            self._client.delete(_user_index_key(user_id))
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def clear_impersonation_target(self, db: OrmSession, target_user_id: str) -> None:
        try:
            token_hashes = list(self._client.smembers(_impersonator_index_key(target_user_id)))
        except Exception as exc:
            raise _map_redis_error(exc) from exc
        now = utcnow()
        for token_hash in token_hashes:
            try:
                payload = self._client.get(_row_key(token_hash))
            except Exception as exc:
                raise _map_redis_error(exc) from exc
            if not payload:
                continue
            record = _deserialize_record(payload)
            if record.impersonate_user_id != target_user_id:
                continue
            record.impersonate_user_id = None
            self._save(record, now)
        try:
            self._client.delete(_impersonator_index_key(target_user_id))
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def set_impersonate(self, db: OrmSession, record: SessionRecord, target_user_id: str | None) -> None:
        previous = record.impersonate_user_id
        record.impersonate_user_id = target_user_id
        now = utcnow()
        self._save(record, now)
        try:
            if previous and previous != target_user_id:
                self._client.srem(_impersonator_index_key(previous), record.token_hash)
            if target_user_id:
                self._client.sadd(_impersonator_index_key(target_user_id), record.token_hash)
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def count_active(self, db: OrmSession) -> int:
        try:
            count = 0
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=f"{KEY_PREFIX}*", count=500)
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def reset(self) -> None:
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match="hub:sess:*", count=500)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def close(self) -> None:
        return None


def _build_store(settings: Settings, backend: SessionBackend) -> SessionStore:
    if backend == "db":
        return DbSessionStore()
    global _redis_client
    try:
        _redis_client = _make_redis_client(settings.VALKEY_URL)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SESSION_STORE=valkey (or auto with VALKEY_URL) requires the redis package; "
            "pip install -r requirements.txt"
        ) from exc
    return ValkeySessionStore(_redis_client)


def get_session_store() -> SessionStore:
    global _store, _resolved_backend
    if _store is None:
        settings = get_settings()
        _resolved_backend = resolve_session_backend(settings)
        _store = _build_store(settings, _resolved_backend)
    return _store


def init_session_store(settings: Settings) -> None:
    global _store, _resolved_backend
    close_session_store()
    _resolved_backend = resolve_session_backend(settings)
    _store = _build_store(settings, _resolved_backend)
    if _resolved_backend == "valkey":
        assert _redis_client is not None
        try:
            _redis_client.ping()
        except Exception as exc:
            from redis.exceptions import RedisError

            if isinstance(exc, RedisError):
                raise RuntimeError(f"Valkey ping failed ({settings.VALKEY_URL}): {exc}") from exc
            raise
        log.info("session store: valkey")
    else:
        log.info("session store: db")


def close_session_store() -> None:
    global _store, _redis_client, _resolved_backend
    if _store is not None:
        _store.close()
    _store = None
    _resolved_backend = None
    if _redis_client is not None:
        _redis_client.close()
    _redis_client = None


def reset_session_store() -> None:
    """Tests: clear Valkey session keys and drop cached store."""
    try:
        get_session_store().reset()
    except Exception:
        pass
    close_session_store()
