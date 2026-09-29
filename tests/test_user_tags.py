from tests.conftest import login_ready, logout, setup_admin, signup, upload_audio, default_tariff_id


def test_user_tags_private_and_filter(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "tagger@example.com", "taggerpass1", tariff_id).status_code == 200

    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]

    put = client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": ["Weekly", "Client"]},
    )
    assert put.status_code == 200, put.text
    tags = put.json()["tags"]
    assert len(tags) == 2
    names = {t["name"] for t in tags}
    assert names == {"Weekly", "Client"}

    detail = client.get(f"/api/v1/audios/{audio_id}")
    assert detail.status_code == 200
    assert len(detail.json()["user_tags"]) == 2

    listed = client.get("/api/v1/audios")
    assert listed.status_code == 200
    match = next(item for item in listed.json()["items"] if item["id"] == audio_id)
    assert len(match["user_tags"]) == 2

    tag_id = next(t["id"] for t in tags if t["name"] == "Weekly")
    filtered = client.get(f"/api/v1/audios?tag={tag_id}")
    assert filtered.status_code == 200
    ids = [item["id"] for item in filtered.json()["items"]]
    assert ids == [audio_id]

    by_name = client.get("/api/v1/audios?tag=client")
    assert by_name.status_code == 200
    assert [item["id"] for item in by_name.json()["items"]] == [audio_id]

    catalog = client.get("/api/v1/tags")
    assert catalog.status_code == 200
    assert len(catalog.json()["items"]) == 2
    weekly = next(item for item in catalog.json()["items"] if item["name"] == "Weekly")
    assert weekly["usage_count"] == 1

    logout(client)
    assert signup(client, "other@example.com", "otherpass1", tariff_id).status_code == 200
    other_view = client.get(f"/api/v1/audios/{audio_id}")
    assert other_view.status_code == 404

    login_ready(client, "tagger@example.com", "taggerpass1")
    rename = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Weekly sync"})
    assert rename.status_code == 200
    assert rename.json()["name"] == "Weekly sync"

    delete_tag = client.delete(f"/api/v1/tags/{tag_id}")
    assert delete_tag.status_code == 200
    after = client.get(f"/api/v1/audios/{audio_id}")
    assert len(after.json()["user_tags"]) == 1
    assert after.json()["user_tags"][0]["name"] == "Client"


def test_user_tag_limits(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "limits@example.com", "limitspass1", tariff_id).status_code == 200

    audio_id = upload_audio(client).json()["id"]
    too_many = [f"tag-{i}" for i in range(33)]
    over = client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": too_many},
    )
    assert over.status_code == 400, over.text
    assert over.json()["error"]["code"] == "user_tag_limit_per_object"

    long_name = "x" * 65
    bad_name = client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": [long_name]},
    )
    assert bad_name.status_code == 400, bad_name.text
    assert bad_name.json()["error"]["code"] == "user_tag_name_invalid"

    ok = client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": ["Alpha", "Beta"]},
    )
    assert ok.status_code == 200, ok.text
    tag_id = ok.json()["tags"][0]["id"]
    taken = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Beta"})
    assert taken.status_code == 400, taken.text
    assert taken.json()["error"]["code"] == "user_tag_name_taken"
