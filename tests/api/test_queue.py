import time
from typing import Any

from fastapi.testclient import TestClient

from tests.models.fakes import FailingScriptModel, UseScriptModel


def _queue_audio(client: TestClient, text: str = "Install it with uv.") -> int:
    uploaded = client.post(
        "/api/docs",
        params={"auto_audio": "false"},
        files=[("files", (f"{text}.md", text.encode(), "text/markdown"))],
    ).json()[0]
    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    job_id: int = created.json()["job_id"]
    return job_id


def _wait_for_job(client: TestClient, job_id: int, state: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        items = client.get("/api/queue", params={"state": state}).json()["items"]
        matching: list[dict[str, Any]] = [job for job in items if job["id"] == job_id]
        if matching:
            return matching[0]
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {state}")


def test_queue_lists_jobs_newest_first_with_paging(client: TestClient) -> None:
    client.post("/api/queue/pause")
    job_ids = [_queue_audio(client, text) for text in ["One.", "Two.", "Three."]]

    first_page = client.get("/api/queue", params={"limit": 2}).json()
    second_page = client.get("/api/queue", params={"limit": 2, "offset": 2}).json()

    assert [job["id"] for job in first_page["items"]] == job_ids[:0:-1]
    assert [job["id"] for job in second_page["items"]] == job_ids[:1]
    assert (first_page["total"], first_page["is_paused"]) == (3, True)
    assert first_page["items"][0]["title"] == "Three."
    assert first_page["items"][0]["state"] == "queued"


def test_queue_filters_by_state(client: TestClient) -> None:
    client.post("/api/queue/pause")
    cancelled_id = _queue_audio(client, "One.")
    queued_id = _queue_audio(client, "Two.")
    client.post(f"/api/queue/{cancelled_id}/cancel")

    cancelled = client.get("/api/queue", params={"state": "cancelled"}).json()
    both = client.get("/api/queue", params={"state": ["queued", "cancelled"]}).json()

    assert [job["id"] for job in cancelled["items"]] == [cancelled_id]
    assert {job["id"] for job in both["items"]} == {cancelled_id, queued_id}


def test_unknown_state_filter_is_a_validation_error(client: TestClient) -> None:
    response = client.get("/api/queue", params={"state": "stuck"})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "state.0"


def test_pause_and_resume_report_the_flag(client: TestClient) -> None:
    paused = client.post("/api/queue/pause").json()
    resumed = client.post("/api/queue/resume").json()

    assert (paused, resumed) == ({"is_paused": True}, {"is_paused": False})
    assert client.get("/api/queue").json()["is_paused"] is False


def test_cancel_then_retry_runs_the_job(client: TestClient) -> None:
    client.post("/api/queue/pause")
    job_id = _queue_audio(client)

    cancelled = client.post(f"/api/queue/{job_id}/cancel").json()
    retried = client.post(f"/api/queue/{job_id}/retry").json()
    client.post("/api/queue/resume")

    done = _wait_for_job(client, job_id, "done")
    assert (cancelled["state"], retried["state"]) == ("cancelled", "queued")
    assert done["attempts"] == 2
    assert client.get(f"/api/audio/{done['audio_id']}").json()["status"] == "done"


def test_failed_job_shows_model_error_and_hint(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    use_script_model(FailingScriptModel())
    job_id = _queue_audio(client)

    job = _wait_for_job(client, job_id, "failed")

    assert (job["error"], job["hint"]) == (
        "Provider returned 402.",
        "Add provider credits.",
    )


def test_retrying_a_job_that_has_not_failed_is_a_conflict(
    client: TestClient,
) -> None:
    client.post("/api/queue/pause")
    job_id = _queue_audio(client)

    response = client.post(f"/api/queue/{job_id}/retry")

    assert response.status_code == 409
    body = response.json()
    assert (body["code"], body["detail"]) == (
        "invalid_job_state",
        f"Job {job_id} is queued",
    )
    assert body["hint"]


def test_cancelling_a_finished_job_is_a_conflict(client: TestClient) -> None:
    job_id = _queue_audio(client)
    _wait_for_job(client, job_id, "done")

    response = client.post(f"/api/queue/{job_id}/cancel")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_job_state"


def test_missing_job_returns_not_found(client: TestClient) -> None:
    response = client.post("/api/queue/999/cancel")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job 999 not found", "code": "not_found"}
