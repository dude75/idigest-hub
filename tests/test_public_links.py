import json

from tests.conftest import default_tariff_id, err_code, login, login_ready, me, open_db, setup_admin, signup
from tests.test_library import _insert_transcript_and_summary


def _member_client(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.example"})
    signup(client, "owner@example.com", "ownerpass1", tariff_id)
    return client


def _configure_public_url(client, url: str = "https://hub.example") -> None:
    response = client.patch("/api/v1/instance/settings", json={"public_base_url": url})
    assert response.status_code == 200, response.text


def test_public_link_requires_public_base_url(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass1", tariff_id)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    denied = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert denied.status_code == 400
    assert err_code(denied) == "public_base_url_missing"


def test_public_link_create_view_and_revoke(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    created = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": None, "pin": "1234"},
    )
    assert created.status_code == 200, created.text
    url = created.json()["link"]["url"]
    assert url.startswith("https://hub.example/public/summary/")
    token = url.rsplit("/", 1)[-1]

    locked = client.get(f"/api/v1/public/summary/{token}")
    assert locked.status_code == 200
    assert locked.json()["pin_required"] is True
    assert "body" not in locked.json()

    unlocked = client.post(f"/api/v1/public/summary/{token}/unlock", json={"pin": "1234"})
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["body"] == "kept summary"

    again = client.get(f"/api/v1/public/summary/{token}")
    assert again.status_code == 200
    assert again.json()["body"] == "kept summary"

    revoked = client.delete(f"/api/v1/summaries/{summary_id}/public-link")
    assert revoked.status_code == 200

    gone = client.get(f"/api/v1/public/summary/{token}")
    assert gone.status_code == 404


def test_public_link_recreate_after_revoke(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    first = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert first.status_code == 200, first.text
    first_url = first.json()["link"]["url"]

    assert client.delete(f"/api/v1/summaries/{summary_id}/public-link").status_code == 200

    second = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert second.status_code == 200, second.text
    second_url = second.json()["link"]["url"]
    assert second_url
    assert second_url != first_url

    assert client.get(f"/api/v1/public/summary/{first_url.rsplit('/', 1)[-1]}").status_code == 404
    assert client.get(f"/api/v1/public/summary/{second_url.rsplit('/', 1)[-1]}").status_code == 200

    listed = client.get(f"/api/v1/summaries/{summary_id}/public-link")
    assert listed.status_code == 200
    assert listed.json()["link"]["url"] == second_url


def test_org_disable_public_links(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    created = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 1, "pin": None},
    )
    assert created.status_code == 200, created.text
    token = created.json()["link"]["url"].rsplit("/", 1)[-1]

    disabled = client.patch("/api/v1/org/settings", json={"allow_public_links": False})
    assert disabled.status_code == 200

    blocked = client.get(f"/api/v1/public/summary/{token}")
    assert blocked.status_code == 404


def test_org_public_links_list_scoped_by_role(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    admin_id = me(client)["user"]["id"]
    _transcript_id, admin_summary_id = _insert_transcript_and_summary(org_id, admin_id)

    created = client.post(
        f"/api/v1/summaries/{admin_summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert created.status_code == 200, created.text
    admin_link_id = created.json()["link"]["id"]

    client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    peer_id = next(u for u in client.get("/api/v1/org/users").json()["items"] if u["email"] == "peer@example.com")["id"]
    _peer_transcript_id, peer_summary_id = _insert_transcript_and_summary(org_id, peer_id)

    login_ready(client, "peer@example.com", "peerpass1")
    peer_created = client.post(
        f"/api/v1/summaries/{peer_summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert peer_created.status_code == 200, peer_created.text
    peer_link_id = peer_created.json()["link"]["id"]

    peer_list = client.get("/api/v1/org/public-links")
    assert peer_list.status_code == 200, peer_list.text
    peer_items = peer_list.json()["items"]
    assert len(peer_items) == 1
    assert peer_items[0]["id"] == peer_link_id
    assert peer_items[0]["url"].startswith("https://hub.example/public/summary/")
    assert peer_items[0]["summary_id"] == peer_summary_id

    login(client, "owner@example.com", "ownerpass1")
    admin_list = client.get("/api/v1/org/public-links")
    assert admin_list.status_code == 200, admin_list.text
    admin_items = admin_list.json()["items"]
    assert len(admin_items) == 2
    assert {item["id"] for item in admin_items} == {admin_link_id, peer_link_id}


def test_org_public_links_revoke_permissions(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    admin_id = me(client)["user"]["id"]
    _transcript_id, admin_summary_id = _insert_transcript_and_summary(org_id, admin_id)

    created = client.post(
        f"/api/v1/summaries/{admin_summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert created.status_code == 200, created.text
    admin_link_id = created.json()["link"]["id"]

    client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    peer_id = next(u for u in client.get("/api/v1/org/users").json()["items"] if u["email"] == "peer@example.com")["id"]
    _peer_transcript_id, peer_summary_id = _insert_transcript_and_summary(org_id, peer_id)

    login_ready(client, "peer@example.com", "peerpass1")
    peer_created = client.post(
        f"/api/v1/summaries/{peer_summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert peer_created.status_code == 200, peer_created.text
    peer_link_id = peer_created.json()["link"]["id"]

    denied = client.delete(f"/api/v1/org/public-links/{admin_link_id}")
    assert denied.status_code == 403

    allowed = client.delete(f"/api/v1/org/public-links/{peer_link_id}")
    assert allowed.status_code == 200

    login(client, "owner@example.com", "ownerpass1")
    admin_revoke = client.delete(f"/api/v1/org/public-links/{admin_link_id}")
    assert admin_revoke.status_code == 200


def test_delete_summary_invalidates_public_link(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    created = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": None, "pin": None},
    )
    assert created.status_code == 200, created.text
    token = created.json()["link"]["url"].rsplit("/", 1)[-1]

    deleted = client.delete(f"/api/v1/summaries/{summary_id}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/public/summary/{token}")
    assert gone.status_code == 404


def test_org_public_links_list_survives_corrupt_token_encrypted(client):
    _member_client(client)
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)

    created = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert created.status_code == 200, created.text
    link_id = created.json()["link"]["id"]

    with open_db() as db:
        from app.models import SummaryPublicLink

        row = db.get(SummaryPublicLink, link_id)
        assert row is not None
        row.token_encrypted = "v1:00000000-0000-0000-0000-000000000000:bad"
        db.commit()

    listed = client.get("/api/v1/org/public-links")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == link_id
    assert items[0]["url"] is None
