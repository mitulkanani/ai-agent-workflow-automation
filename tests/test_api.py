from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_run_and_get_run() -> None:
    response = client.post("/runs", json={
        "goal": "Summarize an incident and create a ticket",
        "context": {"incident": "Checkout endpoint returned 503."},
    })
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    assert response.json()["status"] == "waiting_for_approval"
    detail = client.get(f"/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["plan"][1]["status"] == "waiting_for_approval"


def test_decision_endpoint_approves_pending_step() -> None:
    created = client.post("/runs", json={"goal": "Create a follow-up ticket", "context": {"incident": "API error"}}).json()
    response = client.post(f"/runs/{created['run_id']}/decision", json={"decision": "approve", "comment": "Test approval"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_decision_on_rejected_run_returns_conflict() -> None:
    created = client.post("/runs", json={"goal": "Create a follow-up ticket", "context": {"incident": "API error"}}).json()
    client.post(f"/runs/{created['run_id']}/decision", json={"decision": "reject"})
    response = client.post(f"/runs/{created['run_id']}/decision", json={"decision": "approve"})
    assert response.status_code == 409


def test_invalid_request_is_rejected() -> None:
    response = client.post("/runs", json={"goal": "x", "unexpected": True})
    assert response.status_code == 422


def test_unknown_run_returns_404() -> None:
    response = client.get("/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
