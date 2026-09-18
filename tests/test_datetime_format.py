from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, default_tariff_id, err_code, login, me, setup_admin, signup, upload_audio


def test_me_includes_date_time_prefs(client):
    setup_admin(client)
    payload = me(client)
    prefs = payload["date_time_prefs"]
    assert prefs["format"] == "eu_24h"
    assert prefs["timezone"] == "GMT+0"
    assert prefs["format_source"] == "instance"
    assert prefs["timezone_source"] == "instance"


def test_instance_date_time_settings_and_user_override(client):
    setup_admin(client)
    patched = client.patch(
        "/api/v1/instance/settings",
        json={"date_time_format": "iso", "timezone": "GMT+3"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["date_time_format"] == "iso"
    assert patched.json()["timezone"] == "GMT+3"

    tariff_id = default_tariff_id(client)
    assert signup(client, "dt@example.com", "dtpass1234", tariff_id).status_code == 200
    user_me = me(client)
    assert user_me["date_time_prefs"]["format"] == "iso"
    assert user_me["date_time_prefs"]["timezone"] == "GMT+3"
    assert user_me["user"]["date_time_format"] is None

    override = client.patch(
        "/api/v1/me",
        json={"date_time_format": "us_12h", "timezone": "GMT-5"},
    )
    assert override.status_code == 200, override.text
    body = override.json()
    assert body["user"]["date_time_format"] == "us_12h"
    assert body["user"]["timezone"] == "GMT-5"
    assert body["date_time_prefs"]["format"] == "us_12h"
    assert body["date_time_prefs"]["timezone"] == "GMT-5"
    assert body["date_time_prefs"]["format_source"] == "user"
    assert body["date_time_prefs"]["timezone_source"] == "user"

    reset = client.patch("/api/v1/me", json={"date_time_format": None, "timezone": None})
    assert reset.status_code == 200, reset.text
    reset_body = reset.json()
    assert reset_body["user"]["date_time_format"] is None
    assert reset_body["date_time_prefs"]["format"] == "iso"
    assert reset_body["date_time_prefs"]["format_source"] == "instance"


def test_library_created_at_is_utc_z(client):
    setup_admin(client)
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created_at = audio.json()["created_at"]
    assert created_at.endswith("Z"), created_at


def test_invalid_date_time_format_rejected(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "bad@example.com", "badpass1234", tariff_id).status_code == 200

    bad = client.patch("/api/v1/me", json={"date_time_format": "custom"})
    assert bad.status_code == 400
    assert err_code(bad) == "validation_error"

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    bad_instance = client.patch("/api/v1/instance/settings", json={"timezone": "Europe/Moscow"})
    assert bad_instance.status_code == 400
    assert err_code(bad_instance) == "validation_error"

    bad_offset = client.patch("/api/v1/instance/settings", json={"timezone": "GMT+99"})
    assert bad_offset.status_code == 400
    assert err_code(bad_offset) == "validation_error"
