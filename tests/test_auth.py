from tests.conftest import (
    ADMIN_EMAIL,
    default_tariff_id,
    err_code,
    login,
    login_ready,
    logout,
    me,
    setup_admin,
    signup,
)


def test_bootstrap_only_once(client):
    setup_admin(client)
    again = client.post(
        "/api/v1/setup",
        json={"email": "other@example.com", "password": "otherpass", "bootstrap_token": "boot"},
    )
    assert again.status_code == 409
    assert err_code(again) == "setup_already_done"


def test_signup_creates_org_named_local_part(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    response = signup(client, "alice@example.com", "alicepass", tariff_id)
    assert response.status_code == 200, response.text
    payload = me(client)
    assert payload["user"]["role"] == "org_admin"
    assert payload["user"]["email"] == "alice@example.com"
    assert payload["org"]["name"] == "alice"
    assert payload["org"]["balance"] == "0.00"


def test_signup_disabled_when_allow_new_orgs_false(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    patched = client.patch("/api/v1/instance/settings", json={"allow_new_orgs": False})
    assert patched.status_code == 200, patched.text
    response = signup(client, "bob@example.com", "bobpass1", tariff_id)
    assert response.status_code == 403
    assert err_code(response) == "signup_disabled"


def test_signup_disabled_without_signup_tariffs(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    archived = client.post(f"/api/v1/tariffs/{tariff_id}/archive")
    assert archived.status_code == 200, archived.text
    listed = client.get("/api/v1/auth/signup-tariffs")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    response = signup(client, "carol@example.com", "carolpass", tariff_id)
    assert response.status_code == 403
    assert err_code(response) == "signup_disabled"


def test_last_org_admin_cannot_delete_demote_or_disable(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    lead = me(client)
    lead_id = lead["user"]["id"]

    demote = client.patch(f"/api/v1/org/users/{lead_id}", json={"role": "org_member"})
    assert demote.status_code == 409
    assert err_code(demote) == "last_org_admin"

    disable = client.post(f"/api/v1/org/users/{lead_id}/disable")
    assert disable.status_code == 409
    assert err_code(disable) == "last_org_admin"

    offboard = client.post(f"/api/v1/org/users/{lead_id}/offboard", json={"action": "wipe"})
    assert offboard.status_code == 409
    assert err_code(offboard) == "last_org_admin"

    created = client.post(
        "/api/v1/org/users",
        json={"email": "second@example.com", "password": "secondpass", "role": "org_admin"},
    )
    assert created.status_code == 200, created.text
    second_id = created.json()["id"]

    disabled = client.post(f"/api/v1/org/users/{second_id}/disable")
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["disabled"] is True

    still_last = client.post(f"/api/v1/org/users/{lead_id}/disable")
    assert still_last.status_code == 409
    assert err_code(still_last) == "last_org_admin"


def test_disable_kills_cookie_and_tokens_enable_does_not_resurrect(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    admin_token = client.post("/api/v1/auth/tokens", json={"name": "admin"}).json()["token"]
    member = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    member_id = member.json()["id"]

    logout(client)
    login_ready(client, "member@example.com", "memberpass")
    token_resp = client.post("/api/v1/auth/tokens", json={"name": "cli"})
    assert token_resp.status_code == 200, token_resp.text
    member_token = token_resp.json()["token"]
    assert client.get("/api/v1/me").status_code == 200

    disable = client.post(
        f"/api/v1/org/users/{member_id}/disable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert disable.status_code == 200, disable.text

    cookie_me = client.get("/api/v1/me")
    assert cookie_me.status_code == 401
    assert err_code(cookie_me) == "unauthorized"

    token_me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {member_token}"})
    assert token_me.status_code == 401
    assert err_code(token_me) == "unauthorized"

    enable = client.post(
        f"/api/v1/org/users/{member_id}/enable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert enable.status_code == 200, enable.text

    still_cookie = client.get("/api/v1/me")
    assert still_cookie.status_code == 401
    assert err_code(still_cookie) == "unauthorized"

    still_token = client.get("/api/v1/me", headers={"Authorization": f"Bearer {member_token}"})
    assert still_token.status_code == 401
    assert err_code(still_token) == "unauthorized"

    login(client, "member@example.com", "memberpass")
    assert client.get("/api/v1/me").status_code == 200
    fresh = client.post("/api/v1/auth/tokens", json={"name": "after"})
    assert fresh.status_code == 200, fresh.text
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {fresh.json()['token']}"}).status_code == 200


def test_must_change_password_blocks_api_until_changed(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    created = client.post(
        "/api/v1/org/users",
        json={"email": "forced@example.com", "password": "forcedpass", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["must_change_password"] is True

    logout(client)
    login(client, "forced@example.com", "forcedpass")
    allowed = client.get("/api/v1/me")
    assert allowed.status_code == 200
    assert allowed.json()["must_change_password"] is True

    blocked = client.get("/api/v1/audios")
    assert blocked.status_code == 403
    assert err_code(blocked) == "must_change_password"

    changed = client.post("/api/v1/auth/password/change", json={"new_password": "newpass12"})
    assert changed.status_code == 200, changed.text
    after = client.get("/api/v1/audios")
    assert after.status_code == 200, after.text
    assert me(client)["must_change_password"] is False


def test_password_reset_routes_recovery_disabled_without_smtp(client):
    setup_admin(client)
    request = client.post("/api/v1/auth/password/reset/request", json={"email": ADMIN_EMAIL})
    assert request.status_code == 403
    assert err_code(request) == "recovery_disabled"

    confirm = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": "nope", "new_password": "newpass12"},
    )
    assert confirm.status_code in {403, 404}
    if confirm.status_code == 403:
        assert err_code(confirm) == "recovery_disabled"
