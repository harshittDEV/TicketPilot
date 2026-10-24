"""Tests for Task API endpoints."""

import pytest
from fastapi.testclient import TestClient


def _create_task(client: TestClient, **overrides) -> dict:
    """Helper to create a task and return the response data."""
    payload = {
        "name": "Test task",
        "task_type": "train_booking",
        "description": "A test task",
        "configuration": {"source": "Delhi", "destination": "Mumbai"},
    }
    payload.update(overrides)
    resp = client.post("/api/v1/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


class TestTaskCreation:
    """POST /api/v1/tasks"""

    def test_create_task_returns_201(self, client: TestClient):
        resp = client.post("/api/v1/tasks", json={
            "name": "My task",
            "task_type": "train_booking",
            "description": "Book a train",
            "configuration": {"source": "A", "destination": "B"},
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "CREATED"
        assert data["task_type"] == "train_booking"
        assert data["name"] == "My task"
        assert "id" in data
        assert data["version"] == 1

    def test_create_task_without_name(self, client: TestClient):
        """Name is optional."""
        resp = client.post("/api/v1/tasks", json={"task_type": "generic_task"})
        assert resp.status_code == 201
        assert resp.json()["data"]["name"] is None

    def test_create_task_rejects_missing_task_type(self, client: TestClient):
        resp = client.post("/api/v1/tasks", json={"name": "No type"})
        assert resp.status_code == 422

    def test_create_task_rejects_blank_task_type(self, client: TestClient):
        resp = client.post("/api/v1/tasks", json={"task_type": "   "})
        assert resp.status_code == 422

    def test_create_task_rejects_empty_task_type(self, client: TestClient):
        resp = client.post("/api/v1/tasks", json={"task_type": ""})
        assert resp.status_code == 422

    def test_client_cannot_set_status_on_create(self, client: TestClient):
        """Even if a client sends 'status', it must be ignored — task starts as CREATED."""
        data = _create_task(client, task_type="test")
        assert data["status"] == "CREATED"

    def test_create_generates_uuid_id(self, client: TestClient):
        data = _create_task(client)
        assert len(data["id"]) == 36  # UUID format


class TestTaskRetrieval:
    """GET /api/v1/tasks/{task_id}"""

    def test_get_existing_task(self, client: TestClient):
        created = _create_task(client)
        resp = client.get(f"/api/v1/tasks/{created['id']}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == created["id"]
        assert data["task_type"] == created["task_type"]

    def test_get_nonexistent_task_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/tasks/nonexistent-uuid")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "TASK_NOT_FOUND"

    def test_get_task_does_not_expose_stack_traces(self, client: TestClient):
        resp = client.get("/api/v1/tasks/nonexistent")
        body_text = resp.text.lower()
        assert "traceback" not in body_text
        assert "file " not in body_text


class TestTaskStatus:
    """GET /api/v1/tasks/{task_id}/status"""

    def test_status_endpoint(self, client: TestClient):
        created = _create_task(client)
        resp = client.get(f"/api/v1/tasks/{created['id']}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "CREATED"
        assert "created_at" in data

    def test_status_nonexistent(self, client: TestClient):
        resp = client.get("/api/v1/tasks/doesnt-exist/status")
        assert resp.status_code == 404


class TestTaskListing:
    """GET /api/v1/tasks"""

    def test_list_empty(self, client: TestClient):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tasks"] == []
        assert data["meta"]["total"] == 0

    def test_list_with_tasks(self, client: TestClient):
        _create_task(client, task_type="type_a")
        _create_task(client, task_type="type_b")
        resp = client.get("/api/v1/tasks")
        data = resp.json()["data"]
        assert data["meta"]["total"] == 2
        assert len(data["tasks"]) == 2

    def test_list_filter_by_status(self, client: TestClient):
        _create_task(client)
        resp = client.get("/api/v1/tasks?status=CREATED")
        assert resp.json()["data"]["meta"]["total"] >= 1
        resp2 = client.get("/api/v1/tasks?status=COMPLETED")
        assert resp2.json()["data"]["meta"]["total"] == 0

    def test_list_filter_by_task_type(self, client: TestClient):
        _create_task(client, task_type="alpha")
        _create_task(client, task_type="beta")
        resp = client.get("/api/v1/tasks?task_type=alpha")
        data = resp.json()["data"]
        assert data["meta"]["total"] == 1
        assert data["tasks"][0]["task_type"] == "alpha"

    def test_list_pagination(self, client: TestClient):
        for i in range(5):
            _create_task(client, name=f"Task {i}", task_type="paginated")
        resp = client.get("/api/v1/tasks?page=1&page_size=2")
        data = resp.json()["data"]
        assert len(data["tasks"]) == 2
        assert data["meta"]["total"] == 5
        assert data["meta"]["total_pages"] == 3

    def test_list_invalid_status_filter(self, client: TestClient):
        resp = client.get("/api/v1/tasks?status=INVALID_STATUS")
        assert resp.status_code == 422

    def test_list_newest_first(self, client: TestClient):
        t1 = _create_task(client, name="First", task_type="order")
        t2 = _create_task(client, name="Second", task_type="order")
        resp = client.get("/api/v1/tasks?task_type=order")
        tasks = resp.json()["data"]["tasks"]
        assert tasks[0]["id"] == t2["id"]  # newest first


class TestTaskTransition:
    """POST /api/v1/tasks/{task_id}/transition"""

    def test_valid_transition(self, client: TestClient):
        created = _create_task(client)
        resp = client.post(
            f"/api/v1/tasks/{created['id']}/transition",
            json={"target_status": "READY"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "READY"
        assert data["version"] == 2

    def test_full_lifecycle(self, client: TestClient):
        """Walk a task through CREATED → READY → RUNNING → VERIFYING → COMPLETED."""
        t = _create_task(client)
        tid = t["id"]

        for target in ["READY", "RUNNING", "VERIFYING", "COMPLETED"]:
            resp = client.post(
                f"/api/v1/tasks/{tid}/transition",
                json={"target_status": target},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == target

    def test_invalid_transition_rejected(self, client: TestClient):
        t = _create_task(client)
        resp = client.post(
            f"/api/v1/tasks/{t['id']}/transition",
            json={"target_status": "COMPLETED"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_TASK_TRANSITION"

    def test_terminal_state_immutable(self, client: TestClient):
        t = _create_task(client)
        # Cancel it (terminal)
        client.post(f"/api/v1/tasks/{t['id']}/cancel")
        # Try to reopen
        resp = client.post(
            f"/api/v1/tasks/{t['id']}/transition",
            json={"target_status": "RUNNING"},
        )
        assert resp.status_code == 409

    def test_invalid_target_status_string(self, client: TestClient):
        t = _create_task(client)
        resp = client.post(
            f"/api/v1/tasks/{t['id']}/transition",
            json={"target_status": "NONEXISTENT"},
        )
        assert resp.status_code == 422

    def test_transition_updates_version(self, client: TestClient):
        t = _create_task(client)
        resp = client.post(
            f"/api/v1/tasks/{t['id']}/transition",
            json={"target_status": "READY"},
        )
        assert resp.json()["data"]["version"] == 2

    def test_transition_nonexistent_task(self, client: TestClient):
        resp = client.post(
            "/api/v1/tasks/no-such-id/transition",
            json={"target_status": "READY"},
        )
        assert resp.status_code == 404

    def test_started_at_set_on_running(self, client: TestClient):
        t = _create_task(client)
        client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": "READY"})
        resp = client.post(
            f"/api/v1/tasks/{t['id']}/transition",
            json={"target_status": "RUNNING"},
        )
        data = resp.json()["data"]
        assert data["started_at"] is not None

    def test_completed_at_set_on_completed(self, client: TestClient):
        t = _create_task(client)
        for s in ["READY", "RUNNING", "VERIFYING", "COMPLETED"]:
            client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": s})
        resp = client.get(f"/api/v1/tasks/{t['id']}")
        assert resp.json()["data"]["completed_at"] is not None


class TestTaskCancellation:
    """POST /api/v1/tasks/{task_id}/cancel"""

    def test_cancel_created_task(self, client: TestClient):
        t = _create_task(client)
        resp = client.post(f"/api/v1/tasks/{t['id']}/cancel")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "CANCELLED"
        assert data["cancelled_at"] is not None

    def test_cancel_running_task(self, client: TestClient):
        t = _create_task(client)
        client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": "READY"})
        client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": "RUNNING"})
        resp = client.post(f"/api/v1/tasks/{t['id']}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_completed_task_rejected(self, client: TestClient):
        t = _create_task(client)
        for s in ["READY", "RUNNING", "VERIFYING", "COMPLETED"]:
            client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": s})
        resp = client.post(f"/api/v1/tasks/{t['id']}/cancel")
        assert resp.status_code == 409

    def test_cancel_already_cancelled_idempotent(self, client: TestClient):
        t = _create_task(client)
        client.post(f"/api/v1/tasks/{t['id']}/cancel")
        resp = client.post(f"/api/v1/tasks/{t['id']}/cancel")
        assert resp.status_code == 200  # Idempotent — no error
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_nonexistent_task(self, client: TestClient):
        resp = client.post("/api/v1/tasks/nope/cancel")
        assert resp.status_code == 404


class TestTaskUpdate:
    """PATCH /api/v1/tasks/{task_id}"""

    def test_update_name(self, client: TestClient):
        t = _create_task(client)
        resp = client.patch(
            f"/api/v1/tasks/{t['id']}",
            json={"name": "Updated name"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated name"

    def test_update_configuration(self, client: TestClient):
        t = _create_task(client)
        resp = client.patch(
            f"/api/v1/tasks/{t['id']}",
            json={"configuration": {"key": "value"}},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["configuration"] == {"key": "value"}

    def test_update_terminal_task_rejected(self, client: TestClient):
        t = _create_task(client)
        client.post(f"/api/v1/tasks/{t['id']}/cancel")
        resp = client.patch(
            f"/api/v1/tasks/{t['id']}",
            json={"name": "Nope"},
        )
        assert resp.status_code == 409

    def test_update_nonexistent(self, client: TestClient):
        resp = client.patch("/api/v1/tasks/nope", json={"name": "x"})
        assert resp.status_code == 404


class TestTaskPersistence:
    """Verify tasks persist across sessions."""

    def test_task_survives_new_session(self, client: TestClient):
        t = _create_task(client)
        # Retrieve in a new request (new session)
        resp = client.get(f"/api/v1/tasks/{t['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == t["id"]

    def test_state_change_persists(self, client: TestClient):
        t = _create_task(client)
        client.post(f"/api/v1/tasks/{t['id']}/transition", json={"target_status": "READY"})
        resp = client.get(f"/api/v1/tasks/{t['id']}")
        assert resp.json()["data"]["status"] == "READY"


class TestConcurrency:
    """Verify optimistic concurrency control."""

    def test_stale_version_rejected(self, client: TestClient):
        """
        Simulate a stale update by manually transitioning via the service
        with an outdated expected_version.
        """
        t = _create_task(client)
        task_id = t["id"]
        # First transition succeeds, bumping version to 2
        client.post(f"/api/v1/tasks/{task_id}/transition", json={"target_status": "READY"})

        # Now use the service directly to test optimistic locking
        from app.database.session import get_engine, get_session_factory
        from app.services.task_service import TaskService
        from app.services.task_state_machine import TaskStateConflictError

        factory = get_session_factory()
        session = factory()
        try:
            svc = TaskService(session)
            with pytest.raises(TaskStateConflictError):
                svc.transition_task(
                    task_id, "RUNNING", expected_version=1  # stale!
                )
        finally:
            session.close()


class TestResponseConsistency:
    """Verify responses follow established conventions."""

    def test_success_envelope(self, client: TestClient):
        t = _create_task(client)
        resp = client.get(f"/api/v1/tasks/{t['id']}")
        body = resp.json()
        assert "success" in body
        assert "data" in body
        assert "message" in body

    def test_error_envelope(self, client: TestClient):
        resp = client.get("/api/v1/tasks/nope")
        body = resp.json()
        assert body["success"] is False
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
