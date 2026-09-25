"""Styled HTML pages for the OAuth 2.1 authorization UI (matches web auth layout)."""

from __future__ import annotations

import html
import json
from typing import Iterable
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.constants import SUPPORTED_LOCALES
from app.errors import ErrorCode
from app.deps import locale_from_request
from app.i18n import t
from app.models import User
from app.services.oauth_scopes import ordered_scopes, scope_label_key
from app.version import read_version

_GITHUB_REPO_URL = "https://github.com/dude75/idigest-hub"

_OAUTH_BLOCKED_KEYS: dict[str, str] = {
    "api_disabled": "api_disabled",
    "oauth_org_membership_required": "oauth_org_membership_required",
    "must_change_password": "must_change_password",
    "mfa_enrollment_required": "mfa_enrollment_required",
    "user_agreement_required": "user_agreement_required",
    "account_disabled": "account_disabled",
    "forbidden": "forbidden",
}

_OAUTH_BLOCKED_SIMPLE: frozenset[str] = frozenset({"api_disabled", "oauth_org_membership_required"})

_OAUTH_CSS = """
:root {
  color-scheme: light;
  --bg: #f4f5f7;
  --card: #fff;
  --ink: #1a1d23;
  --muted: #5c6570;
  --line: #d8dee6;
  --accent: #2563eb;
  --accent-ink: #fff;
  --danger: #b42318;
  --warn-bg: #fff7ed;
  --warn-ink: #9a3412;
  --radius: 8px;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.45;
  color: var(--ink);
  background: var(--bg);
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
button, input { font: inherit; }
h1 { font-size: 1.25rem; margin: 0 0 0.75rem; }
.auth-layout { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg); }
.topbar {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.55rem 1rem; border-bottom: 1px solid var(--line);
  background: var(--card);
  position: sticky; top: 0; z-index: 5;
}
.auth-topbar { z-index: 10; }
.brand {
  display: inline-flex; align-items: center; gap: 0.4rem;
  font-weight: 650; color: var(--ink); text-decoration: none;
}
.brand:hover { color: var(--ink); text-decoration: none; }
.badge {
  display: inline-block; font-size: 0.72rem; padding: 0.05rem 0.4rem;
  border-radius: 999px; background: #e8eef8; color: #1e3a5f;
}
.badge.out { background: #ecfdf3; color: #067647; }
.right { margin-left: auto; }
.row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.lang { display: flex; gap: 0.15rem; }
.lang a {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0.2rem 0.4rem; font-size: 0.75rem;
  border: 1px solid var(--line); border-radius: 6px;
  background: #fff; color: var(--ink); text-decoration: none;
}
.lang a:hover { background: #eef2f7; text-decoration: none; }
.lang a.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.github-link {
  display: inline-flex; align-items: center; gap: 0.45rem;
  color: var(--muted); text-decoration: none; border-radius: 6px;
}
.github-link:hover { color: var(--ink); text-decoration: none; }
.github-link-icon { padding: 0.3rem 0.45rem; }
.github-link-icon:hover { background: #eef2f7; }
.github-icon { width: 1.05rem; height: 1.05rem; flex-shrink: 0; }
.auth-page { flex: 1; display: grid; place-items: center; padding: 1.5rem; }
.card {
  width: min(420px, 100%);
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 1.25rem;
}
.stack { display: grid; gap: 0.65rem; }
.muted { color: var(--muted); margin: 0; }
.err { color: var(--danger); font-size: 0.9rem; margin: 0; }
.lead { margin: 0 0 0.5rem; }
.scope-list { margin: 0.35rem 0 0; padding-left: 1.15rem; color: var(--ink); }
.scope-list li { margin: 0.25rem 0; }
.notice, .alert-warn {
  background: var(--warn-bg); color: var(--warn-ink);
  border: 1px solid #fed7aa; border-radius: 6px; padding: 0.65rem 0.75rem;
  font-size: 0.9rem;
}
.alert {
  border-radius: 6px; padding: 0.75rem 0.85rem; font-size: 0.9rem; border: 1px solid;
}
.alert-error {
  background: #fef3f2; color: #912018; border-color: #fecdca;
}
.alert-body { margin: 0; }
.actions {
  display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;
  margin-top: 0.85rem;
}
label { display: grid; gap: 0.2rem; font-size: 0.85rem; color: var(--muted); }
input {
  width: 100%; border: 1px solid var(--line); border-radius: 6px;
  padding: 0.45rem 0.55rem; background: #fff; color: var(--ink);
}
button, .btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--line); background: #fff; border-radius: 6px;
  padding: 0.35rem 0.7rem; cursor: pointer; color: var(--ink);
}
a.btn { text-decoration: none; color: var(--ink); }
a.btn:hover { background: #eef2f7; text-decoration: none; }
.card.stack button, .card.stack > a.btn, .card.stack form > a.btn { width: 100%; }
button.primary, a.btn.primary {
  background: var(--accent); border-color: var(--accent); color: var(--accent-ink);
}
button.primary:hover, a.btn.primary:hover { filter: brightness(1.05); background: var(--accent); }
a.text-link { font-size: 0.9rem; }
.auth-segment {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem;
  padding: 0.2rem; border: 1px solid var(--line); border-radius: 8px; background: #f6f7f9;
}
.auth-segment a.seg-link {
  display: inline-flex; align-items: center; justify-content: center;
  width: 100%; border: none; background: transparent; color: var(--muted);
  font-weight: 500; padding: 0.45rem 0.6rem; border-radius: 6px; text-decoration: none;
}
.auth-segment a.seg-link:hover { text-decoration: none; color: var(--ink); }
.auth-segment a.seg-link.active {
  background: #fff; color: var(--ink); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.auth-panel-stack { display: grid; }
.auth-panel-stack > .auth-panel { grid-area: 1 / 1; min-width: 0; }
.auth-panel-stack > .auth-panel-hidden { visibility: hidden; pointer-events: none; }
"""


_OAUTH_JSON_PATHS = frozenset({"/oauth/token", "/oauth/register"})


def oauth_wants_html(request: Request) -> bool:
    path = (request.url.path or "").rstrip("/") or "/"
    if path in _OAUTH_JSON_PATHS:
        return False
    return path.startswith("/oauth/")


def oauth_locale(request: Request, user: User | None = None) -> str:
    lang = request.query_params.get("lang")
    if lang in SUPPORTED_LOCALES:
        return lang
    return locale_from_request(request, user)


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _scope_labels(locale: str, scopes: Iterable[str]) -> list[str]:
    return [t(locale, scope_label_key(scope)) for scope in ordered_scopes(scopes)]


def _lang_switcher(request: Request, locale: str) -> str:
    links: list[str] = []
    for lng in SUPPORTED_LOCALES:
        active = " active" if lng == locale else ""
        href = _esc(str(request.url.include_query_params(lang=lng)))
        links.append(f'<a class="lang-link{active}" href="{href}">{_esc(t(locale, f"lang_{lng}"))}</a>')
    return f'<div class="lang" role="group" aria-label="language">{"".join(links)}</div>'


def _topbar(request: Request, locale: str) -> str:
    version = read_version()
    version_badge = f'<span class="badge out">{_esc(version)}</span>' if version else ""
    github_label = _esc(t(locale, "oauth_github"))
    return f"""<header class="auth-topbar topbar">
      <a class="brand" href="/">{_esc(t(locale, "oauth_app_name"))}{version_badge}</a>
      <div class="right row">
        <a class="btn" href="/">{_esc(t(locale, "oauth_back_home"))}</a>
        <a class="github-link github-link-icon" href="{_esc(_GITHUB_REPO_URL)}" target="_blank" rel="noopener noreferrer" aria-label="{github_label}">
          <svg class="github-icon" aria-hidden="true" viewBox="0 0 19 19">
            <use href="/icons.svg#github-icon"/>
          </svg>
        </a>
        {_lang_switcher(request, locale)}
      </div>
    </header>"""


def _page(
    request: Request,
    locale: str,
    *,
    title: str,
    body: str,
    status_code: int = 200,
) -> HTMLResponse:
    doc = f"""<!DOCTYPE html>
<html lang="{_esc(locale)}">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_esc(title)} — {_esc(t(locale, "oauth_app_name"))}</title>
  <style>{_OAUTH_CSS}</style>
</head>
<body>
  <div class="auth-layout">
    {_topbar(request, locale)}
    <main class="auth-page">
      <div class="card stack oauth-page">
        {body}
      </div>
    </main>
  </div>
</body>
</html>"""
    return HTMLResponse(doc, status_code=status_code)


def _oauth_actions(locale: str, *, show_app_link: bool, app_href: str) -> str:
    home = f'<a class="btn" href="/">{_esc(t(locale, "oauth_back_home"))}</a>'
    if show_app_link:
        app = f'<a class="btn primary" href="{_esc(app_href)}">{_esc(t(locale, "oauth_open_app"))}</a>'
        return f'<div class="actions">{app}{home}</div>'
    return f'<div class="actions">{home}</div>'


def oauth_message_page(
    request: Request,
    *,
    title_key: str,
    message: str,
    status_code: int,
    user: User | None = None,
    hint: str | None = None,
    show_app_link: bool = False,
    app_href: str = "/app",
    alert: str = "alert-error",
) -> HTMLResponse:
    locale = oauth_locale(request, user)
    title = t(locale, title_key)
    hint_block = f'<p class="muted">{_esc(hint)}</p>' if hint else ""
    body = f"""<h1>{_esc(title)}</h1>
<div class="alert {alert}" role="alert">
  <p class="alert-body">{_esc(message)}</p>
</div>
{hint_block}
{_oauth_actions(locale, show_app_link=show_app_link, app_href=app_href)}"""
    return _page(request, locale, title=title, body=body, status_code=status_code)


def oauth_unexpected_error_page(request: Request) -> HTMLResponse:
    locale = oauth_locale(request)
    return oauth_message_page(
        request,
        title_key="oauth_title_error",
        message=t(locale, "oauth_unexpected_error"),
        hint=t(locale, "oauth_error_retry_hint"),
        status_code=500,
    )


def oauth_http_error_page(request: Request, exc) -> HTMLResponse:
    """Map Starlette HTTPException to a styled OAuth HTML page."""
    locale = oauth_locale(request)
    status_code = int(getattr(exc, "status_code", 500) or 500)
    title_key = "oauth_title_error"
    if status_code == 401:
        title_key = "oauth_title_sign_in"
    elif status_code == 403:
        title_key = "oauth_title_blocked"
    detail = getattr(exc, "detail", None)
    message = t(locale, "oauth_unexpected_error")
    if isinstance(detail, dict):
        err = detail.get("error") if isinstance(detail.get("error"), dict) else None
        if isinstance(err, dict):
            message = err.get("message") or t(locale, err.get("code", ErrorCode.validation_error.value))
        elif detail.get("status") != "error":
            message = t(locale, "oauth_invalid_request")
    elif isinstance(detail, str) and detail.strip() and detail.strip().lower() not in {"not found", "internal server error"}:
        message = detail.strip()
    elif status_code == 404:
        message = t(locale, "oauth_invalid_request")
    elif status_code == 400:
        message = t(locale, "oauth_invalid_request")
    elif status_code < 500:
        message = t(locale, "oauth_invalid_request")
    hint = t(locale, "oauth_error_retry_hint") if status_code >= 500 else None
    alert = "alert-warn" if status_code == 403 else "alert-error"
    return oauth_message_page(
        request,
        title_key=title_key,
        message=message,
        hint=hint,
        status_code=status_code,
        show_app_link=status_code == 403,
        alert=alert,
    )


def oauth_blocked_page(request: Request, reason: str, *, user: User | None = None) -> HTMLResponse:
    locale = oauth_locale(request, user)
    detail_key = _OAUTH_BLOCKED_KEYS.get(reason)
    detail = t(locale, detail_key) if detail_key else reason
    if reason in _OAUTH_BLOCKED_SIMPLE:
        body = f"""<h1>{_esc(t(locale, "oauth_title_blocked"))}</h1>
<div class="alert alert-warn" role="status">{_esc(detail)}</div>
{_oauth_actions(locale, show_app_link=True, app_href="/app")}"""
    else:
        body = f"""<h1>{_esc(t(locale, "oauth_title_blocked"))}</h1>
<p class="lead">{_esc(t(locale, "oauth_blocked_intro"))}</p>
<div class="alert alert-warn" role="status">{_esc(detail)}</div>
{_oauth_actions(locale, show_app_link=True, app_href="/app")}"""
    return _page(request, locale, title=t(locale, "oauth_title_blocked"), body=body, status_code=403)


def oauth_consent_page(
    request: Request,
    *,
    client_name: str,
    scopes: Iterable[str],
    hidden_params: str,
) -> HTMLResponse:
    locale = oauth_locale(request)
    scope_items = "".join(f"<li>{_esc(label)}</li>" for label in _scope_labels(locale, scopes))
    body = f"""<h1>{_esc(t(locale, "oauth_title_authorize"))}</h1>
<p class="lead">{_esc(t(locale, "oauth_consent_intro", client_name=client_name))}</p>
<p class="muted">{_esc(t(locale, "oauth_consent_scopes_heading"))}</p>
<ul class="scope-list">{scope_items}</ul>
<form method="post" action="/oauth/authorize" class="stack" target="_top">
  <input type="hidden" name="confirm" value="1"/>
  <input type="hidden" name="oauth_params" value="{_esc(hidden_params)}"/>
  <button type="submit" class="primary">{_esc(t(locale, "oauth_allow"))}</button>
</form>"""
    return _page(request, locale, title=t(locale, "oauth_title_authorize"), body=body)


def _oauth_mode_href(authorize_params: dict[str, str], mode: str) -> str:
    query = dict(authorize_params)
    query["hub_auth_mode"] = mode
    return f"/oauth/authorize?{urlencode(query)}"


def oauth_login_page(
    request: Request,
    *,
    hidden_params: str,
    authorize_params: dict[str, str],
    auth_mode: str = "email",
    prefill_org_id: str = "",
    error_message: str | None = None,
) -> HTMLResponse:
    locale = oauth_locale(request)
    mode = auth_mode if auth_mode in ("email", "sso") else "email"
    email_active = " active" if mode == "email" else ""
    sso_active = " active" if mode == "sso" else ""
    email_panel_class = "stack auth-panel" if mode == "email" else "stack auth-panel auth-panel-hidden"
    sso_panel_class = "stack auth-panel" if mode == "sso" else "stack auth-panel auth-panel-hidden"
    err_block = (
        f'<div class="alert alert-error" role="alert"><p class="alert-body">{_esc(error_message)}</p></div>'
        if error_message
        else ""
    )
    body = f"""<h1>{_esc(t(locale, "oauth_title_sign_in"))}</h1>
<p class="lead">{_esc(t(locale, "oauth_sign_in_intro"))}</p>
<div class="auth-segment" role="group" aria-label="{_esc(t(locale, "oauth_title_sign_in"))}">
  <a class="seg-link{email_active}" href="{_esc(_oauth_mode_href(authorize_params, "email"))}">{_esc(t(locale, "oauth_mode_email"))}</a>
  <a class="seg-link{sso_active}" href="{_esc(_oauth_mode_href(authorize_params, "sso"))}">{_esc(t(locale, "oauth_mode_sso"))}</a>
</div>
{err_block}
<div class="auth-panel-stack">
  <form method="post" action="/oauth/login" class="{email_panel_class}" target="_top" aria-hidden="{str(mode != "email").lower()}">
    <input type="hidden" name="oauth_params" value="{_esc(hidden_params)}"/>
    <label>{_esc(t(locale, "oauth_email"))}
      <input name="email" type="email" autocomplete="username" required/>
    </label>
    <label>{_esc(t(locale, "oauth_password"))}
      <input name="password" type="password" autocomplete="current-password" required/>
    </label>
    <button type="submit" class="primary">{_esc(t(locale, "oauth_sign_in"))}</button>
  </form>
  <form method="post" action="/oauth/sso" class="{sso_panel_class}" target="_top" aria-hidden="{str(mode != "sso").lower()}">
    <input type="hidden" name="oauth_params" value="{_esc(hidden_params)}"/>
    <label>{_esc(t(locale, "oauth_org_id"))}
      <input name="org_id" type="text" required spellcheck="false" autocomplete="off" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value="{_esc(prefill_org_id)}"/>
    </label>
    <p class="muted">{_esc(t(locale, "oauth_org_id_hint"))}</p>
    <button type="submit" class="primary">{_esc(t(locale, "oauth_sso_continue"))}</button>
  </form>
</div>"""
    return _page(request, locale, title=t(locale, "oauth_title_sign_in"), body=body)


def oauth_client_redirect_page(request: Request, redirect_url: str) -> HTMLResponse:
    """Return to the OAuth client (break out of iframe/popup when embedded in Open WebUI)."""
    locale = oauth_locale(request)
    js_url = json.dumps(redirect_url)
    body = f"""<h1>{_esc(t(locale, "oauth_redirect_title"))}</h1>
<p class="muted">{_esc(t(locale, "oauth_redirect_hint"))}</p>
<a class="btn primary" href="{_esc(redirect_url)}">{_esc(t(locale, "oauth_continue"))}</a>
<script>
(function () {{
  var url = {js_url};
  try {{
    if (window.top && window.top !== window.self) {{
      window.top.location.replace(url);
      return;
    }}
  }} catch (e) {{}}
  window.location.replace(url);
}})();
</script>
<noscript><meta http-equiv="refresh" content="0;url={_esc(redirect_url)}"/></noscript>"""
    return _page(request, locale, title=t(locale, "oauth_redirect_title"), body=body)
