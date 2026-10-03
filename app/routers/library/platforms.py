"""Library HTTP routes: platforms."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import Depends, Form, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    ALLOWED_AUDIO_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    MAX_UPLOAD_BYTES_CAP,
)
from app.crypto import decrypt_str, encrypt_str
from app.db import get_session
from app.deps import AuthContext, require_auth, require_oauth_scope
from app.services.oauth_scopes import SCOPE_TRANSCRIPTS_READ
from app.errors import ApiError, ErrorCode
from app.models import Audio, HiddenItem, Share, Summary, SummaryPublicLink, Transcript, User, new_id
from app.presenters import (
    audio_public,
    summary_display_title,
    summary_public,
    transcript_display_title,
    transcript_public,
)
from app.services.access import (
    can_read_object,
    ensure_object_share,
    is_hidden,
    is_shared_with,
    outgoing_shares,
    revoke_paired_audio_share,
)
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript
from app.services.dispatcher import utterances_to_text
from app.services.transcript_payload import (
    decode_transcript_payload,
    export_json_payload,
    extract_utterances,
    payload_tone_fields,
)
from app.services.export import attachment_response, safe_filename, unwrap_markdown_fence
from app.rate_limit import enforce_write_limits, get_rate_limits
from app.services.audit import write_audit
from app.services.storage import PayloadTooLarge, get_storage
from app.services.upload_validation import InvalidAudioContent
from app.services.library_list import (
    LIBRARY_LIST_MAX_LIMIT,
    LIBRARY_SEARCH_MAX_LEN,
    batch_share_badges,
    count_hidden_library_rows,
    count_library_rows,
    count_library_source_groups,
    list_library_rows,
    list_library_source_group_page,
)
from app.services.user_tags import batch_object_user_tags, object_user_tags, resolve_user_tag
from app.services.video_extract import VideoExtractError, cleanup_extract_temp, video_upload_to_mp3_temp
from app.schemas.library import CapturePlatformsResponse, ImportPlatformsResponse
from app.services.billing import upload_limit
from app.timeutil import utcnow
from app.services import library_helpers as lh

from app.routers.library._router import router


@router.get("/capture/platforms", response_model=CapturePlatformsResponse)
def capture_platforms(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> CapturePlatformsResponse:
    org, _ = ctx.require_org()
    from app.deps import get_instance_settings
    from app.services.capture_meeting import normalize_host, org_jitsi_hosts_public
    from app.services.capture_platforms import allowed_connectors, public_connectors

    settings = get_instance_settings(db)
    allowed = allowed_connectors(settings)
    jitsi_hosts: list[str] = []
    if settings.capture_enabled and "jitsi" in allowed:
        seen: set[str] = set()
        for item in org_jitsi_hosts_public(db, org.id):
            host = normalize_host(str(item.get("host") or ""))
            if host and host not in seen:
                seen.add(host)
                jitsi_hosts.append(host)
    return CapturePlatformsResponse(
        enabled=settings.capture_enabled,
        connectors=public_connectors(settings, db),
        jitsi_hosts=jitsi_hosts,
    )


@router.get("/import/platforms", response_model=ImportPlatformsResponse)
def import_platforms(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> ImportPlatformsResponse:
    ctx.require_org()
    from app.deps import get_instance_settings
    from app.services.import_platforms import public_platforms

    from app.services.download_proxy_health import download_proxy_status

    settings = get_instance_settings(db)
    return ImportPlatformsResponse(
        enabled=settings.import_enabled,
        platforms=public_platforms(settings),
        **download_proxy_status(settings, db),
    )

