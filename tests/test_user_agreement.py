"""User agreement gate for org members."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    default_tariff_id,
    err_code,
    login,
    login_ready,
    logout,
    me,
    setup_admin,
    signup,
)


def _set_agreement(client: TestClient, *, en: str = "Terms EN", ru: str = "Terms RU") -> dict:
    response = client.patch(
        "/api/v1/instance/settings",
        json={"user_agreement_text_en": en, "user_agreement_text_ru": ru},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_user_agreement_blocks_org_member_until_accepted(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "member@example.com", "memberpass1", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    logout(client)

    login(client, "member@example.com", "memberpass1")
    payload = me(client)
    assert payload["user_agreement_required"] is True
    assert payload["user_agreement"]["text"] == "Terms EN"

    blocked = client.get("/api/v1/audios")
    assert blocked.status_code == 403
    assert err_code(blocked) == "user_agreement_required"

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["user_agreement_required"] is False
    assert payload["user_agreement"]["text"] == "Terms EN"
    assert payload["user_agreement"]["version"] == 1

    allowed = client.get("/api/v1/audios")
    assert allowed.status_code == 200, allowed.text


def test_instance_admin_without_org_not_blocked(client: TestClient):
    setup_admin(client)
    _set_agreement(client)
    payload = me(client)
    assert payload["user_agreement_required"] is False


def test_agreement_version_bump_requires_reacceptance(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    settings = _set_agreement(client)
    assert settings["user_agreement_version"] == 1
    logout(client)

    login_ready(client, "owner@example.com", "ownerpass12")
    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    updated = client.patch("/api/v1/instance/settings", json={"user_agreement_text_en": "Terms EN v2"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["user_agreement_version"] == 2
    logout(client)

    login(client, "owner@example.com", "ownerpass12")
    assert me(client)["user_agreement_required"] is True

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False


def test_agreement_locale_ru(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "ru@example.com", "rupass1234", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    logout(client)

    login(client, "ru@example.com", "rupass1234")
    client.patch("/api/v1/me", json={"locale": "ru"})
    payload = me(client)
    assert payload["user_agreement_required"] is True
    assert payload["user_agreement"]["text"] == "Terms RU"


def test_org_users_list_shows_agreement_status(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "listed@example.com", "listedpass1", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    orgs = client.get("/api/v1/orgs")
    assert orgs.status_code == 200, orgs.text
    member = next(
        u
        for org in orgs.json()["items"]
        for u in org.get("members") or []
        if u["email"] == "listed@example.com"
    )
    assert member["user_agreement_status"] == "pending"

    logout(client)
    login(client, "listed@example.com", "listedpass1")
    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    orgs = client.get("/api/v1/orgs")
    member = next(
        u
        for org in orgs.json()["items"]
        for u in org.get("members") or []
        if u["email"] == "listed@example.com"
    )
    assert member["user_agreement_status"] == "accepted"


def test_instance_org_list_marks_disabled_user(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    logout(client)

    login_ready(client, "owner@example.com", "ownerpass12")
    client.post("/api/v1/auth/agreement/accept")
    created = client.post(
        "/api/v1/org/users",
        json={
            "email": "disabled@example.com",
            "password": "disabledpass1",
            "role": "org_member",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["id"]
    owner_org = me(client)["org"]["id"]
    disabled = client.post(f"/api/v1/org/users/{user_id}/disable")
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["disabled"] is True
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    orgs = client.get("/api/v1/orgs")
    org = next(o for o in orgs.json()["items"] if o["id"] == owner_org)
    target = next(u for u in org["members"] if u["email"] == "disabled@example.com")
    assert target["disabled"] is True
    assert target["user_agreement_status"] == "pending"


def test_must_change_password_before_agreement_accept(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    logout(client)

    login_ready(client, "owner@example.com", "ownerpass12")
    client.post("/api/v1/auth/agreement/accept")
    created = client.post(
        "/api/v1/org/users",
        json={
            "email": "reset@example.com",
            "password": "temppass1",
            "role": "org_member",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["must_change_password"] is True
    logout(client)

    login(client, "reset@example.com", "temppass1")
    payload = me(client)
    assert payload["must_change_password"] is True
    assert payload["user_agreement_required"] is True

    blocked_accept = client.post("/api/v1/auth/agreement/accept")
    assert blocked_accept.status_code == 403
    assert err_code(blocked_accept) == "must_change_password"

    changed = client.post("/api/v1/auth/password/change", json={"new_password": "newpass123"})
    assert changed.status_code == 200, changed.text
    payload = me(client)
    assert payload["must_change_password"] is False
    assert payload["user_agreement_required"] is True

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False

    allowed = client.get("/api/v1/audios")
    assert allowed.status_code == 200, allowed.text


def test_normalize_agreement_markdown_fixes_glued_table():
    from app.services.user_agreement import normalize_agreement_markdown

    raw = (
        "- comply with your organization's data policies. | Topic | Rule | "
        "| ---------------- | ---------------------------------------------------- | "
        "| Uploads | You must have rights to content |"
    )
    normalized = normalize_agreement_markdown(raw)
    assert "policies.\n\n| Topic | Rule |" in normalized
    assert "| Uploads | You must have rights to content |" in normalized
    assert "||" not in normalized


def test_agreement_preview_endpoint(client: TestClient):
    setup_admin(client)
    messy = "- item. | Topic | Rule | | --- | --- | | Uploads | ok |"
    resp = client.post("/api/v1/instance/settings/agreement/preview", json={"text": messy})
    assert resp.status_code == 200, resp.text
    assert "item.\n\n| Topic | Rule |" in resp.json()["text"]


def test_save_agreement_normalizes_markdown(client: TestClient):
    setup_admin(client)
    messy = (
        "# User Agreement\n\n"
        "- comply with policies. | Topic | Rule | | --- | --- | | Uploads | rights required |"
    )
    saved = client.patch(
        "/api/v1/instance/settings",
        json={"user_agreement_text_en": messy},
    )
    assert saved.status_code == 200, saved.text
    stored = saved.json()["user_agreement_text_en"]
    assert "policies.\n\n| Topic | Rule |" in stored
    assert "| Uploads | rights required |" in stored


def test_signup_accepts_all_active_legal_documents(client: TestClient):
    setup_admin(client)
    saved = client.patch(
        "/api/v1/instance/settings",
        json={
            "user_agreement_text_en": "Terms EN",
            "personal_data_consent_text_en": "Consent EN",
            "privacy_policy_text_en": "Privacy EN",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["user_agreement_version"] == 1
    assert body["personal_data_consent_version"] == 1
    assert body["privacy_policy_version"] == 1

    tariff_id = default_tariff_id(client)
    blocked = signup(
        client,
        "blocked@example.com",
        "blockedpass1",
        tariff_id,
        accept_legal_documents=False,
    )
    assert blocked.status_code == 400
    assert err_code(blocked) == "validation_error"

    created = signup(client, "legal@example.com", "legalpass12", tariff_id)
    assert created.status_code == 200, created.text
    logout(client)

    login(client, "legal@example.com", "legalpass12")
    payload = me(client)
    assert payload["user_agreement_required"] is False
    assert all(not doc["pending"] for doc in payload["legal_documents"])

    allowed = client.get("/api/v1/audios")
    assert allowed.status_code == 200, allowed.text


def test_privacy_policy_version_bump_requires_reacceptance(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner2@example.com", "ownerpass22", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "user_agreement_text_en": "Terms EN",
            "privacy_policy_text_en": "Privacy EN",
        },
    )
    logout(client)

    login_ready(client, "owner2@example.com", "ownerpass22")
    client.post("/api/v1/auth/agreement/accept")
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    updated = client.patch(
        "/api/v1/instance/settings",
        json={"privacy_policy_text_en": "Privacy EN v2"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["privacy_policy_version"] == 2
    assert updated.json()["user_agreement_version"] == 1
    logout(client)

    login(client, "owner2@example.com", "ownerpass22")
    payload = me(client)
    assert payload["user_agreement_required"] is True
    pending = [doc for doc in payload["legal_documents"] if doc["pending"]]
    assert {doc["key"] for doc in pending} == {"privacy_policy"}

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False


def test_all_active_legal_documents_required_before_accept(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "all-docs@example.com", "alldocspass1", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "user_agreement_text_en": "Terms EN",
            "personal_data_consent_text_en": "Consent EN",
            "privacy_policy_text_en": "Privacy EN",
        },
    )
    logout(client)

    login(client, "all-docs@example.com", "alldocspass1")
    payload = me(client)
    assert payload["user_agreement_required"] is True
    assert {doc["key"] for doc in payload["legal_documents"]} == {
        "user_agreement",
        "personal_data_consent",
        "privacy_policy",
    }
    assert all(doc["pending"] for doc in payload["legal_documents"])

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    after = accepted.json()
    assert after["user_agreement_required"] is False
    assert all(not doc["pending"] for doc in after["legal_documents"])


def test_public_legal_documents_endpoint(client: TestClient):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "user_agreement_text_en": "Terms EN",
            "privacy_policy_text_en": "Privacy EN",
        },
    )
    logout(client)

    listed = client.get("/api/v1/public/legal-documents")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert {item["key"] for item in items} == {"user_agreement", "privacy_policy"}
    assert items[0]["text"]

    one = client.get("/api/v1/public/legal-documents/user_agreement")
    assert one.status_code == 200, one.text
    assert one.json()["text"] == "Terms EN"

    missing = client.get("/api/v1/public/legal-documents/personal_data_consent")
    assert missing.status_code == 404


def test_landing_footer_text_on_public_endpoint(client: TestClient):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "landing_footer_text_en": "**HQ** · Moscow · [email](mailto:ops@example.com)",
            "landing_footer_published": True,
        },
    )
    logout(client)

    listed = client.get("/api/v1/public/legal-documents")
    assert listed.status_code == 200, listed.text
    assert "HQ" in listed.json()["footer_text"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.patch(
        "/api/v1/instance/settings",
        json={"landing_footer_published": False},
    )
    logout(client)

    hidden = client.get("/api/v1/public/legal-documents")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["footer_text"] is None


def test_unpublished_legal_document_hidden_from_landing(client: TestClient):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "user_agreement_text_en": "Terms EN",
            "privacy_policy_text_en": "Privacy EN",
            "privacy_policy_published": False,
        },
    )
    logout(client)

    listed = client.get("/api/v1/public/legal-documents")
    assert listed.status_code == 200, listed.text
    assert {item["key"] for item in listed.json()["items"]} == {"user_agreement"}

    hidden = client.get("/api/v1/public/legal-documents/privacy_policy")
    assert hidden.status_code == 404


def test_bearer_token_blocked_until_agreement_accepted(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "api@example.com", "apipass1234", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _set_agreement(client)
    logout(client)

    login_ready(client, "api@example.com", "apipass1234")
    assert me(client)["user_agreement_required"] is True

    token_resp = client.post("/api/v1/auth/tokens", json={"name": "cli"})
    assert token_resp.status_code == 403
    assert err_code(token_resp) == "user_agreement_required"
