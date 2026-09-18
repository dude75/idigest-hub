from sqlalchemy import func, select

from app.models import (
    Audio,
    Membership,
    Organization,
    Session as AuthSession,
    Summary,
    SummaryPublicLink,
    Task,
    Transcript,
    UsageEvent,
    User,
)
from tests.conftest import (
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    me,
    open_db,
    setup_admin,
    signup,
    upload_audio,
)
from tests.test_library import _insert_transcript_and_summary


def test_delete_org_requires_instance_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "solo@example.com", "solopass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    org_name = me(client)["org"]["name"]

    denied = client.post(f"/api/v1/orgs/{org_id}/delete", json={"confirm_name": org_name})
    assert denied.status_code == 403
    assert err_code(denied) == "forbidden"


def test_delete_org_requires_name_confirmation(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "solo@example.com", "solopass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]

    logout(client)
    login_ready(client, "admin@example.com", "adminpass1")

    denied = client.post(f"/api/v1/orgs/{org_id}/delete", json={"confirm_name": "wrong-name"})
    assert denied.status_code == 400
    assert err_code(denied) == "validation_error"


def test_delete_org_cascades_content_users_and_billing(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.example"})
    assert signup(client, "owner@example.com", "ownerpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    org_name = me(client)["org"]["name"]

    member = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text

    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])

    link = client.post(
        f"/api/v1/summaries/{summary_id}/public-link",
        json={"expires_in_days": 7, "pin": None},
    )
    assert link.status_code == 200, link.text

    org_skill = client.post("/api/v1/org/skills", json={"name": "Org skill", "body": "Do it"})
    assert org_skill.status_code == 200, org_skill.text

    transcribe = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert transcribe.status_code == 202, transcribe.text

    logout(client)
    login_ready(client, "admin@example.com", "adminpass1")

    deleted = client.post(f"/api/v1/orgs/{org_id}/delete", json={"confirm_name": org_name})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "ok"

    missing = client.post(f"/api/v1/orgs/{org_id}/delete", json={"confirm_name": org_name})
    assert missing.status_code == 404

    orgs = client.get("/api/v1/orgs")
    assert orgs.status_code == 200
    assert all(item["id"] != org_id for item in orgs.json()["items"])

    db = open_db()
    try:
        assert db.get(Organization, org_id) is None
        assert db.scalar(select(func.count()).select_from(Membership).where(Membership.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(User).where(User.email == "owner@example.com")) == 0
        assert db.scalar(select(func.count()).select_from(User).where(User.email == "peer@example.com")) == 0
        assert db.scalar(select(func.count()).select_from(Audio).where(Audio.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(Transcript).where(Transcript.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(Summary).where(Summary.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(SummaryPublicLink).where(SummaryPublicLink.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(Task).where(Task.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(UsageEvent).where(UsageEvent.org_id == org_id)) == 0
        assert db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id)) == 0
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "ownerpass1"})
    assert login.status_code == 401


def test_delete_org_leaves_other_orgs_intact(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "keep@example.com", "keeppass1", tariff_id).status_code == 200
    keep_org_id = me(client)["org"]["id"]
    keep_org_name = me(client)["org"]["name"]

    logout(client)
    assert signup(client, "gone@example.com", "gonepass1", tariff_id).status_code == 200
    gone_org_id = me(client)["org"]["id"]
    gone_org_name = me(client)["org"]["name"]

    logout(client)
    login_ready(client, "admin@example.com", "adminpass1")

    deleted = client.post(f"/api/v1/orgs/{gone_org_id}/delete", json={"confirm_name": gone_org_name})
    assert deleted.status_code == 200, deleted.text

    orgs = client.get("/api/v1/orgs")
    assert orgs.status_code == 200
    ids = {item["id"] for item in orgs.json()["items"]}
    assert keep_org_id in ids
    assert gone_org_id not in ids

    logout(client)
    login_ready(client, "keep@example.com", "keeppass1")
    assert me(client)["org"]["id"] == keep_org_id
    assert me(client)["org"]["name"] == keep_org_name
