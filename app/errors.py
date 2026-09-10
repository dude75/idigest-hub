"""Коды ошибок хаба (ТЗ §16) и HTTP-исключение."""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException


class ErrorCode(str, Enum):
    unauthorized = "unauthorized"
    forbidden = "forbidden"
    insufficient_balance = "insufficient_balance"
    not_found = "not_found"
    payload_too_large = "payload_too_large"
    canceled = "canceled"
    dispatch_timeout = "dispatch_timeout"
    source_deleted = "source_deleted"
    account_wiped = "account_wiped"
    must_change_password = "must_change_password"
    last_org_admin = "last_org_admin"
    tariff_in_use = "tariff_in_use"
    last_tariff = "last_tariff"
    task_running = "task_running"
    invalid_file = "invalid_file"
    validation_error = "validation_error"
    setup_already_done = "setup_already_done"
    signup_disabled = "signup_disabled"
    recovery_disabled = "recovery_disabled"
    email_taken = "email_taken"
    invalid_credentials = "invalid_credentials"
    tariff_not_available = "tariff_not_available"
    api_disabled = "api_disabled"
    text_too_long = "text_too_long"
    invalid_file_type = "invalid_file"
    bootstrap_invalid = "bootstrap_invalid"
    conflict = "conflict"
    pipeline_error = "pipeline_error"
    engine_unavailable = "engine_unavailable"
    invalid_file_worker = "invalid_file"
    worker_error = "pipeline_error"
    rate_limited = "rate_limited"
    sso_disabled = "sso_disabled"
    sso_misconfigured = "sso_misconfigured"
    sso_state_invalid = "sso_state_invalid"
    sso_email_missing = "sso_email_missing"
    sso_user_wrong_org = "sso_user_wrong_org"
    sso_login_required = "sso_login_required"
    account_disabled = "account_disabled"


HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.unauthorized: 401,
    ErrorCode.forbidden: 403,
    ErrorCode.insufficient_balance: 429,
    ErrorCode.not_found: 404,
    ErrorCode.payload_too_large: 413,
    ErrorCode.must_change_password: 403,
    ErrorCode.last_org_admin: 409,
    ErrorCode.tariff_in_use: 409,
    ErrorCode.last_tariff: 409,
    ErrorCode.task_running: 409,
    ErrorCode.invalid_file: 400,
    ErrorCode.validation_error: 400,
    ErrorCode.setup_already_done: 409,
    ErrorCode.signup_disabled: 403,
    ErrorCode.recovery_disabled: 403,
    ErrorCode.email_taken: 409,
    ErrorCode.invalid_credentials: 401,
    ErrorCode.tariff_not_available: 400,
    ErrorCode.api_disabled: 403,
    ErrorCode.text_too_long: 413,
    ErrorCode.bootstrap_invalid: 401,
    ErrorCode.conflict: 409,
    ErrorCode.rate_limited: 429,
    ErrorCode.sso_disabled: 403,
    ErrorCode.sso_misconfigured: 400,
    ErrorCode.sso_state_invalid: 400,
    ErrorCode.sso_email_missing: 400,
    ErrorCode.sso_user_wrong_org: 403,
    ErrorCode.sso_login_required: 403,
    ErrorCode.account_disabled: 403,
}


def error_payload(code: ErrorCode, message: str | None = None) -> dict[str, Any]:
    detail: dict[str, Any] = {"code": code.value}
    if message:
        detail["message"] = message
    return {"status": "error", "error": detail}


class ApiError(HTTPException):
    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code or HTTP_STATUS.get(code, 400),
            detail=error_payload(code, message),
            headers=headers,
        )
        self.code = code
