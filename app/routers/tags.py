"""Личные теги на объектах библиотеки."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ApiError, ErrorCode
from app.models import Audio, Summary, Transcript
from app.services.access import can_read_object
from app.services.user_tags import (
    delete_user_tag,
    list_user_tags,
    rename_user_tag,
    set_object_tags,
)

router = APIRouter()


class TagRenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ObjectTagsBody(BaseModel):
    object_type: str
    object_id: str
    tags: list[str] = Field(default_factory=list)


def _readable_library_object(db: Session, ctx: AuthContext, object_type: str, object_id: str):
    model = {"audio": Audio, "transcript": Transcript, "summary": Summary}.get(object_type)
    if model is None:
        ctx.raise_error(ErrorCode.validation_error)
    row = db.get(model, object_id)
    if row is None or not can_read_object(
        ctx, db, object_type, row.owner_user_id, row.org_id, row.id
    ):
        ctx.raise_error(ErrorCode.not_found)
    return row


@router.get("/tags")
def get_tags(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    ctx.require_org()
    return {"items": list_user_tags(db, ctx.user.id)}


@router.patch("/tags/{tag_id}")
def patch_tag(
    tag_id: str,
    body: TagRenameBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    ctx.require_org()
    try:
        return rename_user_tag(db, ctx.user.id, tag_id, body.name)
    except ApiError as exc:
        ctx.raise_error(exc.code, status_code=exc.status_code)


@router.delete("/tags/{tag_id}")
def remove_tag(
    tag_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    ctx.require_org()
    try:
        delete_user_tag(db, ctx.user.id, tag_id)
    except ApiError as exc:
        ctx.raise_error(exc.code, status_code=exc.status_code)
    return {"status": "ok"}


@router.put("/object-tags")
def put_object_tags(
    body: ObjectTagsBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    ctx.require_org()
    _readable_library_object(db, ctx, body.object_type, body.object_id)
    try:
        tags = set_object_tags(
            db,
            user_id=ctx.user.id,
            object_type=body.object_type,
            object_id=body.object_id,
            tag_names=body.tags,
        )
    except ApiError as exc:
        ctx.raise_error(exc.code, status_code=exc.status_code)
    return {"tags": tags}
