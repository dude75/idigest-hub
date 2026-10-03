"""Library list SQL visibility and batched badges."""

import json

from tests.conftest import login_ready, me, open_db, setup_admin, signup, upload_audio, default_tariff_id, logout


def _insert_transcript(org_id: str, user_id: str, audio_id: str | None) -> str:
    from app.crypto import encrypt_str
    from app.models import Transcript, new_id
    from app.timeutil import utcnow

    db = open_db()
    try:
        now = utcnow()
        transcript_id = new_id()
        db.add(
            Transcript(
                id=transcript_id,
                org_id=org_id,
                owner_user_id=user_id,
                source_audio_id=audio_id,
                utterances_encrypted=encrypt_str(json.dumps([{"speaker": "A", "start": 0, "end": 1, "text": "x"}]), db),
                created_at=now,
            )
        )
        db.commit()
        return transcript_id
    finally:
        db.close()


def test_library_list_hidden_count_without_double_scan(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "owner@example.com", "ownerpass1", tariff_id).status_code == 200
    for _ in range(3):
        assert upload_audio(client).status_code == 200
    listed = client.get("/api/v1/audios")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["items"]) == 3
    assert body["hidden_count"] == 0

    first_id = body["items"][0]["id"]
    assert client.post(f"/api/v1/audios/{first_id}/hide").status_code == 200
    hidden = client.get("/api/v1/audios")
    assert hidden.status_code == 200
    assert len(hidden.json()["items"]) == 2
    assert hidden.json()["hidden_count"] == 1

    shown = client.get("/api/v1/audios?include_hidden=true")
    assert shown.status_code == 200
    assert len(shown.json()["items"]) == 3


def test_member_sees_shared_audio_in_list(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    member = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass12", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    owner_audio = upload_audio(client)
    assert owner_audio.status_code == 200
    audio_id = owner_audio.json()["id"]

    logout(client)
    login_ready(client, "peer@example.com", "peerpass12")
    peer_audio = upload_audio(client)
    assert peer_audio.status_code == 200

    before_share = client.get("/api/v1/audios")
    assert before_share.status_code == 200
    assert audio_id not in {item["id"] for item in before_share.json()["items"]}

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    share = client.post(
        "/api/v1/shares",
        json={"object_type": "audio", "object_id": audio_id, "to_user_ids": [member.json()["id"]]},
    )
    assert share.status_code == 200, share.text

    logout(client)
    login_ready(client, "peer@example.com", "peerpass12")
    after_share = client.get("/api/v1/audios")
    assert after_share.status_code == 200
    ids = {item["id"] for item in after_share.json()["items"]}
    assert audio_id in ids
    shared_row = next(item for item in after_share.json()["items"] if item["id"] == audio_id)
    assert shared_row.get("share_kind") == "incoming"


def test_library_list_pagination_total_and_owner_filter(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    member = client.post(
        "/api/v1/org/users",
        json={"email": "mem@example.com", "password": "mempass123", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    member_id = member.json()["id"]

    logout(client)
    login_ready(client, "mem@example.com", "mempass123")
    assert upload_audio(client).status_code == 200
    assert upload_audio(client).status_code == 200

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    assert upload_audio(client).status_code == 200

    all_rows = client.get("/api/v1/audios")
    assert all_rows.status_code == 200
    assert all_rows.json()["total"] == 3

    page = client.get("/api/v1/audios?limit=2&offset=0")
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3

    by_owner = client.get(f"/api/v1/audios?owner_user_id={member_id}")
    assert by_owner.status_code == 200
    assert by_owner.json()["total"] == 2
    assert all(item["owner_user_id"] == member_id for item in by_owner.json()["items"])


def test_library_list_search_q(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "u@example.com", "userpass12", tariff_id).status_code == 200
    a = upload_audio(client, name="weekly-meeting.mp3")
    assert a.status_code == 200, a.text
    b = upload_audio(client, name="other-note.mp3")
    assert b.status_code == 200, b.text

    match = client.get("/api/v1/audios?q=weekly")
    assert match.status_code == 200
    ids = {item["id"] for item in match.json()["items"]}
    assert a.json()["id"] in ids
    assert b.json()["id"] not in ids
    assert match.json()["total"] == 1

    by_email = client.get("/api/v1/audios?q=u@example")
    assert by_email.status_code == 200
    assert len(by_email.json()["items"]) == 2


def test_transcripts_group_by_source_pagination(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "u@example.com", "userpass12", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio_a = upload_audio(client, name="a.wav")
    audio_b = upload_audio(client, name="b.wav")
    assert audio_a.status_code == 200 and audio_b.status_code == 200
    _insert_transcript(org_id, user_id, audio_a.json()["id"])
    _insert_transcript(org_id, user_id, audio_a.json()["id"])
    _insert_transcript(org_id, user_id, audio_b.json()["id"])

    grouped = client.get("/api/v1/transcripts?group_by=source&limit=10")
    assert grouped.status_code == 200, grouped.text
    body = grouped.json()
    assert body["items"] == []
    assert body["total"] == 2
    assert len(body["groups"]) == 2
    sizes = sorted(len(g["items"]) for g in body["groups"])
    assert sizes == [1, 2]

    page = client.get("/api/v1/transcripts?group_by=source&limit=1&offset=0")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["groups"]) == 1


def test_member_cannot_use_owner_user_id_filter(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    member = client.post(
        "/api/v1/org/users",
        json={"email": "solo@example.com", "password": "solopass12", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    logout(client)
    login_ready(client, "solo@example.com", "solopass12")
    denied = client.get("/api/v1/audios?owner_user_id=any-id")
    assert denied.status_code == 403
