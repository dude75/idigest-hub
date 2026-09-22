"""GET /workers list and summary."""

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, add_worker, login, seed_node_health, setup_admin


def test_list_workers_two_transcribe_nodes(client, fake_workers):
    setup_admin(client)
    w1 = add_worker(client, name="t1", base_url="http://transcribe-a.test")
    w2 = add_worker(client, name="t2", base_url="http://transcribe-b.test")
    seed_node_health(w1["id"])
    seed_node_health(w2["id"])

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.get("/api/v1/workers?probe=false")
    assert response.status_code == 200, response.text
    body = response.json()
    transcribe = [item for item in body["items"] if item["type"] == "transcribe"]
    assert len(transcribe) == 2
    bucket = body["summary"]["by_type"]["transcribe"]
    assert bucket["total"] == 2
    assert bucket["enabled"] == 2
    assert bucket["available"] == 2
