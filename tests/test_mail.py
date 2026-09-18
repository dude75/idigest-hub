from types import SimpleNamespace

from app.services.mail import SmtpParams, _envelope_from, resolve_smtp_params, resolve_smtp_password


def test_resolve_smtp_params_empty_override_falls_back_to_saved(db):
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="mailer@example.com",
        smtp_from="mailer@example.com",
        smtp_tls=True,
        smtp_password_encrypted=None,
    )
    params = resolve_smtp_params(
        settings,
        db,
        host="",
        user="",
        from_addr="",
    )
    assert params.host == "smtp.example.com"
    assert params.user == "mailer@example.com"
    assert params.from_addr == "mailer@example.com"


def test_resolve_smtp_params_port_465_enables_ssl_mode(db):
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_user="mailer@example.com",
        smtp_from="mailer@example.com",
        smtp_tls=False,
        smtp_password_encrypted=None,
    )
    params = resolve_smtp_params(settings, db)
    assert params.port == 465
    assert params.tls is True


def test_resolve_smtp_password_uses_saved_when_override_empty(db, monkeypatch):
    settings = SimpleNamespace(smtp_password_encrypted="enc")
    monkeypatch.setattr(
        "app.services.mail.try_decrypt_str",
        lambda *_args, **_kwargs: "saved-secret",
    )
    assert resolve_smtp_password(settings, db, password="") == "saved-secret"
    assert resolve_smtp_password(settings, db, password=None) == "saved-secret"
    assert resolve_smtp_password(settings, db, password=" typed ") == "typed"


def test_envelope_from_prefers_smtp_user():
    params = SmtpParams(
        host="smtp.example.com",
        port=587,
        user="mailer@example.com",
        password="secret",
        from_addr="Display <noreply@example.com>",
        tls=True,
    )
    assert _envelope_from(params) == "mailer@example.com"
