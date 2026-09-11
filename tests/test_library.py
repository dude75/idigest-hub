import json

from tests.conftest import (
    add_worker,
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    me,
    open_db,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
)


def _insert_transcript_and_summary(org_id: str, user_id: str, audio_id: str | None = None):
    from app.crypto import encrypt_str
    from app.models import Summary, Transcript, new_id
    from app.timeutil import utcnow

    db = open_db()
    try:
        now = utcnow()
        transcript_id = new_id()
        summary_id = new_id()
        db.add(
            Transcript(
                id=transcript_id,
                org_id=org_id,
                owner_user_id=user_id,
                source_audio_id=audio_id,
                utterances_encrypted=encrypt_str(
                    json.dumps([{"speaker": "A", "start": 0, "end": 1, "text": "hi"}])
                ),
                created_at=now,
            )
        )
        db.flush()
        db.add(
            Summary(
                id=summary_id,
                org_id=org_id,
                owner_user_id=user_id,
                source_transcript_id=transcript_id,
                skill_ids_json=[],
                body_encrypted=encrypt_str("kept summary"),
                created_at=now,
            )
        )
        db.commit()
        return transcript_id, summary_id
    finally:
        db.close()


def test_org_admin_sees_member_hidden_audio_unhide_restores(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    member = client.post(
        "/api/v1/org/users",
        json={"email": "hide@example.com", "password": "hidepass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    logout(client)
    login_ready(client, "hide@example.com", "hidepass1")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    assert client.post(f"/api/v1/audios/{audio_id}/hide").status_code == 200

    member_list = client.get("/api/v1/audios")
    assert member_list.status_code == 200
    assert all(item["id"] != audio_id for item in member_list.json()["items"])
    still_there = client.get(f"/api/v1/audios/{audio_id}")
    assert still_there.status_code == 200, still_there.text

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    admin_list = client.get("/api/v1/audios")
    assert admin_list.status_code == 200
    ids = [item["id"] for item in admin_list.json()["items"]]
    assert audio_id in ids

    logout(client)
    login_ready(client, "hide@example.com", "hidepass1")
    assert client.post(f"/api/v1/audios/{audio_id}/unhide").status_code == 200
    restored = client.get("/api/v1/audios")
    assert restored.status_code == 200
    assert any(item["id"] == audio_id for item in restored.json()["items"])


def test_include_hidden_shows_own_hidden_audio(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    assert client.post(f"/api/v1/audios/{audio_id}/hide").status_code == 200

    hidden = client.get("/api/v1/audios")
    assert hidden.status_code == 200
    assert all(item["id"] != audio_id for item in hidden.json()["items"])
    assert hidden.json()["hidden_count"] == 1

    shown = client.get("/api/v1/audios?include_hidden=true")
    assert shown.status_code == 200
    match = next(item for item in shown.json()["items"] if item["id"] == audio_id)
    assert match["hidden"] is True
    assert shown.json()["hidden_count"] == 1


def test_org_admin_own_hidden_audio_respects_include_hidden(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    assert client.post(f"/api/v1/audios/{audio_id}/hide").status_code == 200

    hidden = client.get("/api/v1/audios")
    assert hidden.status_code == 200
    assert all(item["id"] != audio_id for item in hidden.json()["items"])
    assert hidden.json()["hidden_count"] == 1

    shown = client.get("/api/v1/audios?include_hidden=true")
    assert shown.status_code == 200
    assert any(item["id"] == audio_id for item in shown.json()["items"])
    assert shown.json()["hidden_count"] == 1


def test_include_hidden_shows_own_hidden_summary(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id)
    assert client.post(f"/api/v1/summaries/{summary_id}/hide").status_code == 200

    hidden = client.get("/api/v1/summaries")
    assert hidden.status_code == 200
    assert all(item["id"] != summary_id for item in hidden.json()["items"])
    assert hidden.json()["hidden_count"] == 1

    shown = client.get("/api/v1/summaries?include_hidden=true")
    assert shown.status_code == 200
    match = next(item for item in shown.json()["items"] if item["id"] == summary_id)
    assert match["hidden"] is True
    assert shown.json()["hidden_count"] == 1


def test_org_admin_can_hide_member_summary(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    member = client.post(
        "/api/v1/org/users",
        json={"email": "sum@example.com", "password": "sumpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    logout(client)
    login_ready(client, "sum@example.com", "sumpass1")
    member_user_id = me(client)["user"]["id"]
    _transcript_id, summary_id = _insert_transcript_and_summary(org_id, member_user_id)
    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    assert client.post(f"/api/v1/summaries/{summary_id}/hide").status_code == 200

    hidden = client.get("/api/v1/summaries")
    assert hidden.status_code == 200
    assert all(item["id"] != summary_id for item in hidden.json()["items"])
    assert hidden.json()["hidden_count"] == 1


def test_list_transcripts_includes_source_filename(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    transcript_id, _summary_id = _insert_transcript_and_summary(org_id, user_id, audio_id)

    listed = client.get("/api/v1/transcripts")
    assert listed.status_code == 200, listed.text
    match = next(item for item in listed.json()["items"] if item["id"] == transcript_id)
    assert match["source_audio_id"] == audio_id
    assert match["source_filename"] == "clip.wav"

    detail = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["source_filename"] == "clip.wav"


def test_delete_transcript_does_not_cascade_summaries(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])

    deleted = client.delete(f"/api/v1/transcripts/{transcript_id}")
    assert deleted.status_code == 200, deleted.text
    missing = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert missing.status_code == 404
    summary = client.get(f"/api/v1/summaries/{summary_id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["body"] == "kept summary"
    assert summary.json()["edited"] is False
    assert summary.json()["source_transcript_id"] in {None, transcript_id}

    patched = client.patch(f"/api/v1/summaries/{summary_id}", json={"body": "## Edited\n\nnew body"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["body"] == "## Edited\n\nnew body"
    assert patched.json()["edited"] is True
    listed = client.get("/api/v1/summaries")
    assert listed.status_code == 200
    match = next(item for item in listed.json()["items"] if item["id"] == summary_id)
    assert match["edited"] is True


def test_delete_artifacts_after_task_produced_refs(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    summarize_worker = add_worker(
        client, type="summarize", name="llm", base_url="http://summarize.test"
    )
    seed_node_health(summarize_worker["id"], ready_http=200)
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert skill.status_code == 200, skill.text
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "wipe@example.com", "wipepass1", tariff_id).status_code == 200

    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    fake_workers.transcribe_mode = "success"
    transcribed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio_id})
    assert transcribed.status_code == 202, transcribed.text
    assert transcribed.json()["status"] == "success"
    transcript_id = transcribed.json()["transcript_id"]
    assert transcript_id

    fake_workers.summarize_mode = "success"
    summarized = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": transcript_id, "skill_ids": [skill.json()["id"]]},
    )
    assert summarized.status_code == 202, summarized.text
    assert summarized.json()["status"] == "success"
    summary_id = summarized.json()["summary_id"]
    assert summary_id

    wiped_audio = client.delete(f"/api/v1/audios/{audio_id}")
    assert wiped_audio.status_code == 200, wiped_audio.text

    deleted_transcript = client.delete(f"/api/v1/transcripts/{transcript_id}")
    assert deleted_transcript.status_code == 200, deleted_transcript.text
    assert client.get(f"/api/v1/transcripts/{transcript_id}").status_code == 404

    deleted_summary = client.delete(f"/api/v1/summaries/{summary_id}")
    assert deleted_summary.status_code == 200, deleted_summary.text
    assert client.get(f"/api/v1/summaries/{summary_id}").status_code == 404


def test_shares_incoming_and_recipient_decline(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    owner = client.post(
        "/api/v1/org/users",
        json={"email": "owner@example.com", "password": "ownerpass", "role": "org_member"},
    )
    peer = client.post(
        "/api/v1/org/users",
        json={"email": "peer@example.com", "password": "peerpass1", "role": "org_member"},
    )
    assert owner.status_code == 200 and peer.status_code == 200
    peer_id = peer.json()["id"]

    logout(client)
    login_ready(client, "owner@example.com", "ownerpass")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    shared = client.post(
        "/api/v1/shares",
        json={"object_type": "audio", "object_id": audio_id, "to_user_ids": [peer_id]},
    )
    assert shared.status_code == 200, shared.text
    owner_view = client.get(f"/api/v1/audios/{audio_id}")
    assert owner_view.status_code == 200
    assert peer_id in owner_view.json()["shared_with"]
    shares = owner_view.json()["shares"]
    assert len(shares) == 1
    assert shares[0]["to_user_id"] == peer_id
    assert shares[0]["email"] == "peer@example.com"
    share_id = shares[0]["id"]

    listed = client.get(f"/api/v1/shares?object_type=audio&object_id={audio_id}")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    revoked = client.delete(f"/api/v1/shares/{share_id}")
    assert revoked.status_code == 200, revoked.text
    after_revoke = client.get(f"/api/v1/audios/{audio_id}")
    assert after_revoke.status_code == 200
    assert peer_id not in (after_revoke.json().get("shared_with") or [])

    shared = client.post(
        "/api/v1/shares",
        json={"object_type": "audio", "object_id": audio_id, "to_user_ids": [peer_id]},
    )
    assert shared.status_code == 200, shared.text

    logout(client)
    login_ready(client, "peer@example.com", "peerpass1")
    incoming = client.get("/api/v1/audios")
    assert incoming.status_code == 200
    match = next(item for item in incoming.json()["items"] if item["id"] == audio_id)
    assert match["share_kind"] == "incoming"
    share_id = match["share_id"]
    declined = client.delete(f"/api/v1/shares/{share_id}")
    assert declined.status_code == 200, declined.text
    after = client.get("/api/v1/audios")
    assert all(item["id"] != audio_id for item in after.json()["items"])

    logout(client)
    login_ready(client, "owner@example.com", "ownerpass")
    updated = client.get(f"/api/v1/audios/{audio_id}")
    assert updated.status_code == 200
    assert peer_id not in (updated.json().get("shared_with") or [])


def test_transfer_offboarding_retargets_incoming_shares_and_frees_email(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    owner = client.post(
        "/api/v1/org/users",
        json={"email": "from@example.com", "password": "frompass1", "role": "org_member"},
    )
    leaving = client.post(
        "/api/v1/org/users",
        json={"email": "gone@example.com", "password": "gonepass1", "role": "org_member"},
    )
    target = client.post(
        "/api/v1/org/users",
        json={"email": "keep@example.com", "password": "keeppass1", "role": "org_member"},
    )
    assert owner.status_code == 200 and leaving.status_code == 200 and target.status_code == 200
    leaving_id = leaving.json()["id"]
    target_id = target.json()["id"]

    logout(client)
    login_ready(client, "from@example.com", "frompass1")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    assert (
        client.post(
            "/api/v1/shares",
            json={"object_type": "audio", "object_id": audio_id, "to_user_ids": [leaving_id]},
        ).status_code
        == 200
    )

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    offboard = client.post(
        f"/api/v1/org/users/{leaving_id}/offboard",
        json={"action": "transfer", "target_user_id": target_id},
    )
    assert offboard.status_code == 200, offboard.text

    logout(client)
    login_ready(client, "keep@example.com", "keeppass1")
    incoming = client.get("/api/v1/audios")
    assert incoming.status_code == 200
    match = next(item for item in incoming.json()["items"] if item["id"] == audio_id)
    assert match["share_kind"] == "incoming"

    reused = signup(client, "gone@example.com", "newpass12", tariff_id)
    assert reused.status_code == 200, reused.text
    assert me(client)["user"]["email"] == "gone@example.com"


def test_export_audio_transcript_summary(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio_id)

    audio_file = client.get(f"/api/v1/audios/{audio_id}/file?download=true")
    assert audio_file.status_code == 200, audio_file.text
    assert audio_file.content
    assert "attachment" in audio_file.headers.get("content-disposition", "")

    txt = client.get(f"/api/v1/transcripts/{transcript_id}/export?format=txt")
    assert txt.status_code == 200, txt.text
    assert txt.text == "A: hi"
    assert txt.headers["content-type"].startswith("text/plain")

    exported = client.get(f"/api/v1/transcripts/{transcript_id}/export?format=json")
    assert exported.status_code == 200, exported.text
    assert exported.json()[0]["text"] == "hi"

    summary = client.get(f"/api/v1/summaries/{summary_id}/export?format=md")
    assert summary.status_code == 200, summary.text
    assert summary.text == "kept summary"
    assert "markdown" in summary.headers["content-type"]

    from app.crypto import encrypt_str
    from app.models import Summary

    fenced_body = "```markdown\n# Title\n\nBody text\n```"
    db = open_db()
    try:
        row = db.get(Summary, summary_id)
        row.body_encrypted = encrypt_str(fenced_body)
        db.commit()
    finally:
        db.close()

    exported = client.get(f"/api/v1/summaries/{summary_id}/export?format=md")
    assert exported.status_code == 200, exported.text
    assert exported.text == "# Title\n\nBody text"
    assert "```" not in exported.text


def test_summary_display_title_uses_transcript_name(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])

    listed = client.get("/api/v1/summaries")
    assert listed.status_code == 200, listed.text
    match = next(item for item in listed.json()["items"] if item["id"] == summary_id)
    assert match["source_transcript_title"] == "clip"
    assert match["display_title"] == f"clip-{summary_id[:8]}"


def test_rename_transcript_and_summary(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])

    renamed_tr = client.patch(f"/api/v1/transcripts/{transcript_id}", json={"title": "Meeting notes"})
    assert renamed_tr.status_code == 200, renamed_tr.text
    assert renamed_tr.json()["title"] == "Meeting notes"
    assert renamed_tr.json()["display_title"] == "Meeting notes"

    listed = client.get("/api/v1/transcripts")
    match = next(item for item in listed.json()["items"] if item["id"] == transcript_id)
    assert match["display_title"] == "Meeting notes"

    renamed_sum = client.patch(f"/api/v1/summaries/{summary_id}", json={"title": "Weekly recap"})
    assert renamed_sum.status_code == 200, renamed_sum.text
    assert renamed_sum.json()["title"] == "Weekly recap"
    assert renamed_sum.json()["display_title"] == "Weekly recap"

    both = client.patch(
        f"/api/v1/summaries/{summary_id}",
        json={"title": "Final recap", "body": "updated body"},
    )
    assert both.status_code == 200, both.text
    assert both.json()["title"] == "Final recap"
    assert both.json()["body"] == "updated body"
    assert both.json()["edited"] is True


def test_backup_zip_and_tgz(client):
    import io
    import json
    import tarfile
    import zipfile

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])
    skill = client.post("/api/v1/skills/self", json={"name": "My skill", "body": "# Notes\nKeep"})
    assert skill.status_code == 200, skill.text

    zip_resp = client.get(
        "/api/v1/me/backup?transcripts=true&summaries=true&skills=true&format=zip"
    )
    assert zip_resp.status_code == 200, zip_resp.text
    assert zip_resp.headers["content-type"] == "application/zip"
    assert "attachment" in zip_resp.headers.get("content-disposition", "")

    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert f"transcripts/{transcript_id}.json" in names
        transcript_payload = json.loads(zf.read(f"transcripts/{transcript_id}.json"))
        assert transcript_payload["utterances"][0]["text"] == "hi"
        summary_md = [name for name in names if name.startswith("summaries/") and name.endswith(".md")]
        assert len(summary_md) == 1
        assert zf.read(summary_md[0]).decode() == "kept summary"
        skill_md = [name for name in names if name.startswith("skills/") and name.endswith(".md")]
        assert len(skill_md) == 1
        assert zf.read(skill_md[0]).decode() == "# Notes\nKeep"
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["includes"] == ["transcripts", "summaries", "skills"]

    tgz_resp = client.get("/api/v1/me/backup?summaries=true&format=tgz")
    assert tgz_resp.status_code == 200, tgz_resp.text
    assert tgz_resp.headers["content-type"] == "application/gzip"
    with tarfile.open(fileobj=io.BytesIO(tgz_resp.content), mode="r:gz") as tf:
        names = tf.getnames()
        assert "manifest.json" in names
        assert any(name.startswith("summaries/") and name.endswith(".md") for name in names)
        assert not any(name.startswith("transcripts/") for name in names)

    empty = client.get("/api/v1/me/backup")
    assert empty.status_code == 400
    assert err_code(empty) == "validation_error"


def test_export_skill(client):
    setup_admin(client)
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "# Prompt\nDo it"})
    assert skill.status_code == 200, skill.text
    skill_id = skill.json()["id"]

    exported = client.get(f"/api/v1/skills/{skill_id}/export")
    assert exported.status_code == 200, exported.text
    assert exported.text == "# Prompt\nDo it"
    assert exported.headers["content-disposition"].endswith('Minutes.md"')


def test_last_org_admin_cannot_offboard(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "solo@example.com", "solopass1", tariff_id).status_code == 200
    user_id = me(client)["user"]["id"]
    response = client.post(f"/api/v1/org/users/{user_id}/offboard", json={"action": "wipe"})
    assert response.status_code == 409
    assert err_code(response) == "last_org_admin"
