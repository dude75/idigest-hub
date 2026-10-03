"""Library list SQL visibility and batched badges."""

from tests.conftest import login_ready, setup_admin, signup, upload_audio, default_tariff_id, logout


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
