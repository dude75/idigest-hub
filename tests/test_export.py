from app.services.export import content_disposition_attachment


def test_content_disposition_ascii():
    header = content_disposition_attachment("Minutes.md")
    assert header == 'attachment; filename="Minutes.md"'


def test_content_disposition_unicode():
    header = content_disposition_attachment("Протокол встречи.md")
    assert header.startswith("attachment; filename*=utf-8''")
    assert "%D0%9F" in header  # encoded "П"


def test_export_summary_with_cyrillic_title(client):
    from app.crypto import encrypt_str
    from app.models import Summary

    from tests.conftest import (
        default_tariff_id,
        login_ready,
        me,
        open_db,
        setup_admin,
        signup,
        upload_audio,
    )
    from tests.test_library import _insert_transcript_and_summary

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    user_id = me(client)["user"]["id"]
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    transcript_id, summary_id = _insert_transcript_and_summary(org_id, user_id, audio.json()["id"])

    renamed = client.patch(f"/api/v1/transcripts/{transcript_id}", json={"title": "Протокол встречи"})
    assert renamed.status_code == 200, renamed.text

    db = open_db()
    try:
        row = db.get(Summary, summary_id)
        row.body_encrypted = encrypt_str("# Итоги\n\nТекст", db)
        db.commit()
    finally:
        db.close()

    exported = client.get(f"/api/v1/summaries/{summary_id}/export?format=md")
    assert exported.status_code == 200, exported.text
    assert exported.text == "# Итоги\n\nТекст"
    disposition = exported.headers.get("content-disposition", "")
    assert "filename*=utf-8''" in disposition
