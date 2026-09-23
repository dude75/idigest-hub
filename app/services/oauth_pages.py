"""Styled HTML pages for the OAuth 2.1 authorization UI (matches web auth layout)."""

from __future__ import annotations

import html
from typing import Iterable

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.deps import locale_from_request
from app.i18n import t
from app.models import User
from app.version import read_version

_OAUTH_BLOCKED_KEYS: dict[str, str] = {
    "api_disabled": "api_disabled",
    "must_change_password": "must_change_password",
    "mfa_enrollment_required": "mfa_enrollment_required",
    "user_agreement_required": "user_agreement_required",
    "account_disabled": "account_disabled",
}

_SCOPE_LABEL_KEYS: dict[str, str] = {
    "transcripts:read": "oauth_scope_transcripts_read",
}

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
}
.brand { font-weight: 650; color: var(--ink); text-decoration: none; }
.badge {
  font-size: 0.72rem; font-weight: 500; color: var(--muted);
  border: 1px solid var(--line); border-radius: 999px; padding: 0.05rem 0.45rem;
}
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
.notice {
  background: var(--warn-bg); color: var(--warn-ink);
  border: 1px solid #fed7aa; border-radius: 6px; padding: 0.65rem 0.75rem;
  font-size: 0.9rem;
}
label { display: grid; gap: 0.2rem; font-size: 0.85rem; color: var(--muted); }
input {
  width: 100%; border: 1px solid var(--line); border-radius: 6px;
  padding: 0.45rem 0.55rem; background: #fff; color: var(--ink);
}
button {
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--line); background: #fff; border-radius: 6px;
  padding: 0.45rem 0.85rem; cursor: pointer; color: var(--ink); width: 100%;
}
button.primary {
  background: var(--accent); border-color: var(--accent); color: var(--accent-ink);
}
button.primary:hover { filter: brightness(1.05); }
a.btn {
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--accent); background: var(--accent); color: var(--accent-ink);
  border-radius: 6px; padding: 0.45rem 0.85rem; text-decoration: none; width: 100%;
}
a.btn:hover { filter: brightness(1.05); text-decoration: none; }
a.text-link { font-size: 0.9rem; }
"""


def oauth_locale(request: Request, user: User | None = None) -> str:
    return locale_from_request(request, user)


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _scope_labels(locale: str, scopes: Iterable[str]) -> list[str]:
    labels: list[str] = []
    for scope in scopes:
        key = _SCOPE_LABEL_KEYS.get(scope)
        labels.append(t(locale, key) if key else scope)
    return labels


def _page(locale: str, *, title: str, body: str, status_code: int = 200) -> HTMLResponse:
    version = read_version()
    version_badge = f'<span class="badge">{_esc(version)}</span>' if version else ""
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
    <header class="topbar">
      <a class="brand" href="/">{_esc(t(locale, "oauth_app_name"))}{version_badge}</a>
    </header>
    <main class="auth-page">
      <div class="card stack oauth-page">
        {body}
      </div>
    </main>
  </div>
</body>
</html>"""
    return HTMLResponse(doc, status_code=status_code)


def oauth_message_page(
    request: Request,
    *,
    title_key: str,
    message: str,
    status_code: int,
    user: User | None = None,
    show_app_link: bool = False,
    app_href: str = "/app",
) -> HTMLResponse:
    locale = oauth_locale(request, user)
    title = t(locale, title_key)
    app_link = ""
    if show_app_link:
        app_link = f'<a class="btn primary" href="{_esc(app_href)}">{_esc(t(locale, "oauth_open_app"))}</a>'
    body = f"""<h1>{_esc(title)}</h1>
<p class="lead">{_esc(message)}</p>
{app_link}"""
    return _page(locale, title=title, body=body, status_code=status_code)


def oauth_blocked_page(request: Request, reason: str, *, user: User | None = None) -> HTMLResponse:
    locale = oauth_locale(request, user)
    detail_key = _OAUTH_BLOCKED_KEYS.get(reason)
    detail = t(locale, detail_key) if detail_key else reason
    if reason == "api_disabled":
        body = f"""<h1>{_esc(t(locale, "oauth_title_blocked"))}</h1>
<div class="notice">{_esc(detail)}</div>
<a class="btn primary" href="/app">{_esc(t(locale, "oauth_open_app"))}</a>"""
    else:
        body = f"""<h1>{_esc(t(locale, "oauth_title_blocked"))}</h1>
<p class="lead">{_esc(t(locale, "oauth_blocked_intro"))}</p>
<div class="notice">{_esc(detail)}</div>
<a class="btn primary" href="/app">{_esc(t(locale, "oauth_open_app"))}</a>"""
    return _page(locale, title=t(locale, "oauth_title_blocked"), body=body, status_code=403)


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
<form method="post" action="/oauth/authorize" class="stack">
  <input type="hidden" name="confirm" value="1"/>
  <input type="hidden" name="oauth_params" value="{_esc(hidden_params)}"/>
  <button type="submit" class="primary">{_esc(t(locale, "oauth_allow"))}</button>
</form>"""
    return _page(locale, title=t(locale, "oauth_title_authorize"), body=body)


def oauth_login_page(
    request: Request,
    *,
    hidden_params: str,
    sso_href: str | None = None,
    error_message: str | None = None,
) -> HTMLResponse:
    locale = oauth_locale(request)
    sso_block = ""
    if sso_href:
        sso_block = f'<p><a class="text-link" href="{_esc(sso_href)}">{_esc(t(locale, "oauth_sso"))}</a></p>'
    err_block = f'<p class="err">{_esc(error_message)}</p>' if error_message else ""
    body = f"""<h1>{_esc(t(locale, "oauth_title_sign_in"))}</h1>
<p class="lead">{_esc(t(locale, "oauth_sign_in_intro"))}</p>
{sso_block}
{err_block}
<form method="post" action="/oauth/login" class="stack">
  <input type="hidden" name="oauth_params" value="{_esc(hidden_params)}"/>
  <label>{_esc(t(locale, "oauth_email"))}
    <input name="email" type="email" autocomplete="username" required/>
  </label>
  <label>{_esc(t(locale, "oauth_password"))}
    <input name="password" type="password" autocomplete="current-password" required/>
  </label>
  <button type="submit" class="primary">{_esc(t(locale, "oauth_sign_in"))}</button>
</form>"""
    return _page(locale, title=t(locale, "oauth_title_sign_in"), body=body)
