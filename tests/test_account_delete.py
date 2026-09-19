from sqlalchemy import func, select

from app.models import Audio, Membership, Organization, User
from tests.conftest import (
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    me,
    setup_admin,
    signup,
    upload_audio,
)


def test_member_can_delete_own_account(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "solo@example.com", "solopass1", tariff_id).status_code == 200
    user_id = me(client)["user"]["id"]
    org_id = me(client)["org"]["id"]

    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text

    preview = client.get("/api/v1/me/account-delete")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["requires_successor"] is False
    assert body["will_delete_org"] is True

    deleted = client.post(
        "/api/v1/me/account-delete",
        json={"password": "solopass1"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["org_deleted"] is True

    assert client.get("/api/v1/me").status_code == 401

    from tests.conftest import open_db

    with open_db() as db:
        assert db.get(User, user_id) is None
        assert db.get(Organization, org_id) is None


def test_last_org_admin_must_pick_successor(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    lead_id = me(client)["user"]["id"]

    member = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    peer_id = member.json()["id"]

    preview = client.get("/api/v1/me/account-delete")
    assert preview.status_code == 200
    assert preview.json()["requires_successor"] is True
    assert preview.json()["will_delete_org"] is False

    missing = client.post("/api/v1/me/account-delete", json={"password": "leadpass1"})
    assert missing.status_code == 400
    assert err_code(missing) == "org_admin_successor_required"

    deleted = client.post(
        "/api/v1/me/account-delete",
        json={"password": "leadpass1", "successor_user_id": peer_id},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["org_deleted"] is False

    logout(client)
    login_ready(client, "peer@example.com", "peerpass1")
    peer = me(client)
    assert peer["user"]["role"] == "org_admin"

    from tests.conftest import open_db

    with open_db() as db:
        assert db.get(User, lead_id) is None
        assert db.scalar(select(Membership).where(Membership.user_id == peer_id)).role == "org_admin"


def test_instance_admin_can_assign_org_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "owner@example.com", "ownerpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]

    member = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    peer_id = member.json()["id"]

    logout(client)
    login_ready(client, "admin@example.com", "adminpass1")

    promoted = client.patch(
        f"/api/v1/orgs/{org_id}/users/{peer_id}",
        json={"role": "org_admin"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "org_admin"


def test_instance_admin_cannot_self_delete_via_profile(client):
    setup_admin(client)
    denied = client.get("/api/v1/me/account-delete")
    assert denied.status_code == 403


def test_org_member_delete_keeps_org(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]

    member = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    peer_id = member.json()["id"]

    logout(client)
    login_ready(client, "peer@example.com", "peerpass1")

    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text

    deleted = client.post(
        "/api/v1/me/account-delete",
        json={"password": "peerpass1"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["org_deleted"] is False

    from tests.conftest import open_db

    with open_db() as db:
        assert db.get(User, peer_id) is None
        assert db.get(Organization, org_id) is not None
        assert db.scalar(select(func.count()).select_from(Audio).where(Audio.org_id == org_id)) == 0
