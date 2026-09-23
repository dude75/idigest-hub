"""Library operations for MCP tools (same rules as HTTP API)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.models import Transcript
from app.presenters import transcript_public
from app.routers.library import _audio_filenames, _list_filter, _share_badge, _transcript_derived_info
from app.services.oauth_scopes import SCOPE_TRANSCRIPTS_READ

MCP_TRANSCRIPT_LIST_LIMIT = 100


def list_transcriptions_payload(
    db: Session,
    ctx: AuthContext,
    *,
    include_hidden: bool = False,
) -> dict:
    if ctx.via_oauth_token and SCOPE_TRANSCRIPTS_READ not in ctx.oauth_scopes:
        raise PermissionError("transcripts:read scope required")
    rows = _list_filter(ctx, db, Transcript, "transcript", include_hidden)
    rows = rows[:MCP_TRANSCRIPT_LIST_LIMIT]
    filenames = _audio_filenames(db, {row.source_audio_id for row in rows})
    derived = _transcript_derived_info(db, ctx, [row.id for row in rows])
    return {
        "items": [
            {
                **transcript_public(
                    row,
                    extra=_share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
                    source_filename=filenames.get(row.source_audio_id) if row.source_audio_id else None,
                ),
                **derived.get(row.id, {"has_summary": False}),
            }
            for row in rows
        ],
        "truncated": len(rows) >= MCP_TRANSCRIPT_LIST_LIMIT,
    }
