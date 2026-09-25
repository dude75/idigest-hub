"""PATCH capture worker connector selection."""

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, add_worker, login, seed_node_health, setup_admin


def test_patch_capture_worker_persists_telemost(client, fake_workers):
    setup_admin(client)
    fake_workers.health = {
        "status": "ok",
        "version": "x",
        "connectors": {
            "jitsi": {"status": "loaded", "label": "Jitsi Meet"},
            "telemost": {"status": "loaded", "label": "Yandex Telemost"},
        },
        "workers": {"max": 4, "active": 0, "available": 4},
    }
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test", capture_connectors=["jitsi"])
    seed_node_health(worker["id"], dict(fake_workers.health))

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    patched = client.patch(
        f"/api/v1/workers/{worker['id']}",
        json={
            "type": "capture",
            "name": "cap",
            "base_url": "http://capture.test",
            "weight": 1,
            "enabled": True,
            "capture_connectors": ["jitsi", "telemost"],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["capture_connectors"] == ["jitsi", "telemost"]

    listed = client.get("/api/v1/workers?probe=false")
    assert listed.status_code == 200
    row = next(item for item in listed.json()["items"] if item["id"] == worker["id"])
    assert row["capture_connectors"] == ["jitsi", "telemost"]
