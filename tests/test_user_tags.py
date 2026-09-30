from tests.conftest import (
    add_worker,
    default_tariff_id,
    login_ready,
    logout,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
    wait_task,
)


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


def test_user_tags_inherit_on_transcribe_and_summarize(client, fake_workers):
    setup_admin(client)
    transcribe_worker = add_worker(client, type="transcribe", name="asr", base_url="http://transcribe.test")
    summarize_worker = add_worker(
        client, type="summarize", name="llm", base_url="http://summarize.test"
    )
    seed_node_health(transcribe_worker["id"])
    seed_node_health(summarize_worker["id"], ready_http=200)
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert skill.status_code == 200, skill.text
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "inherit@example.com", "inheritpass1", tariff_id).status_code == 200

    audio_id = upload_audio(client).json()["id"]
    untagged_audio_id = upload_audio(client).json()["id"]

    tag_put = client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": ["Project", "Q3"]},
    )
    assert tag_put.status_code == 200, tag_put.text

    fake_workers.transcribe_mode = "success"
    fake_workers.summarize_mode = "success"

    transcribed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio_id})
    assert transcribed.status_code == 202, transcribed.text
    transcript_id = wait_task(client, transcribed.json()["task_id"], status="success")["transcript_id"]

    tr = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert tr.status_code == 200, tr.text
    tr_names = {t["name"] for t in tr.json()["user_tags"]}
    assert tr_names == {"Project", "Q3"}

    client.put(
        "/api/v1/object-tags",
        json={"object_type": "audio", "object_id": audio_id, "tags": ["OnlyOnAudio"]},
    )
    tr_after = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert {t["name"] for t in tr_after.json()["user_tags"]} == {"Project", "Q3"}

    summarized = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": transcript_id, "skill_ids": [skill.json()["id"]]},
    )
    assert summarized.status_code == 202, summarized.text
    summary_id = wait_task(client, summarized.json()["task_id"], status="success")["summary_id"]

    sm = client.get(f"/api/v1/summaries/{summary_id}")
    assert sm.status_code == 200, sm.text
    assert {t["name"] for t in sm.json()["user_tags"]} == {"Project", "Q3"}

    bare = client.post("/api/v1/tasks/transcribe", json={"audio_id": untagged_audio_id})
    assert bare.status_code == 202, bare.text
    bare_tr_id = wait_task(client, bare.json()["task_id"], status="success")["transcript_id"]
    bare_tr = client.get(f"/api/v1/transcripts/{bare_tr_id}")
    assert bare_tr.status_code == 200, bare_tr.text
    assert bare_tr.json()["user_tags"] == []
