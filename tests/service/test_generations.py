"""POST /projects/{id}/generations enqueues via real Redis (the route
calls queue.enqueue(...) directly, not something a test can bypass
without mocking) -- so this whole module needs Redis reachable, same
skip-cleanly pattern as Postgres.
"""

from __future__ import annotations

import pytest

from .conftest import redis_is_reachable

if not redis_is_reachable():
    pytest.skip("No Redis reachable at localhost:6379 -- skipping generation tests.", allow_module_level=True)

from rq import SimpleWorker

from rivet_service.jobs.queue import get_queue, get_redis_connection

VALID_REGISTER = {"email": "generations-test@example.com", "password": "hunter22222"}

VALID_GENERATE_PAYLOAD = {
    "plot": {"width_m": 15, "length_m": 13, "entrance": "north", "abutting_road_width_m": 9, "proposed_height_m": 6},
    "rooms": [
        {"room_type": "living_room", "count": 1},
        {"room_type": "master_bedroom", "count": 1, "attached_bathroom": True},
        {"room_type": "bedroom", "count": 2, "attached_bathroom": True},
        {"room_type": "kitchen", "count": 1},
        {"room_type": "dining_room", "count": 1},
        {"room_type": "bathroom", "count": 1},
    ],
    "num_candidates": 2,
    "seed": 42,
}


def _run_worker_once() -> None:
    # SimpleWorker runs the job in-process (no fork()) -- avoids a real
    # Worker's fork-in-a-multithreaded-pytest-process deprecation warning
    # and is faster/more deterministic for tests; production still uses
    # the real forking Worker (jobs/worker.py) for proper job isolation.
    SimpleWorker([get_queue()], connection=get_redis_connection()).work(burst=True)


def _create_project(client) -> str:
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    return client.post("/api/v1/projects", json={"name": "Test Project"}).json()["id"]


def test_create_generation_returns_202_and_queues(client):
    project_id = _create_project(client)
    res = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD)
    assert res.status_code == 202
    assert res.json()["status"] == "queued"
    assert len(get_queue()) == 1


def test_create_generation_rejects_invalid_payload_without_queueing(client):
    project_id = _create_project(client)
    bad_payload = {**VALID_GENERATE_PAYLOAD, "rooms": [{"room_type": "not_a_room"}]}
    res = client.post(f"/api/v1/projects/{project_id}/generations", json=bad_payload)
    assert res.status_code == 400
    assert len(get_queue()) == 0


def test_create_generation_requires_project_ownership(client):
    project_id = _create_project(client)
    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"email": "other-org@example.com", "password": "hunter22222"})
    res = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD)
    assert res.status_code == 404


def test_generation_lifecycle_queued_to_succeeded(client):
    project_id = _create_project(client)
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD).json()[
        "generation_id"
    ]

    res = client.get(f"/api/v1/generations/{gen_id}")
    assert res.json()["status"] == "queued"
    assert res.json()["engine_version"] >= 1
    assert res.json()["rulebook_version"] >= 1

    _run_worker_once()

    res2 = client.get(f"/api/v1/generations/{gen_id}")
    body = res2.json()
    assert body["status"] == "succeeded"
    assert body["started_at"] is not None
    assert body["finished_at"] is not None
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["index"] == 1
    assert "score" in body["candidates"][0]
    assert "score_breakdown" in body["candidates"][0]


def test_generation_of_an_infeasible_request_fails_with_message(client):
    project_id = _create_project(client)
    tiny_payload = {
        "plot": {"width_m": 5, "length_m": 6},
        "rooms": [
            {"room_type": "living_room", "count": 1},
            {"room_type": "bedroom", "count": 2},
            {"room_type": "kitchen", "count": 1},
            {"room_type": "bathroom", "count": 1},
        ],
        "seed": 1,
    }
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=tiny_payload).json()["generation_id"]
    _run_worker_once()

    res = client.get(f"/api/v1/generations/{gen_id}")
    body = res.json()
    assert body["status"] == "failed"
    assert body["error_message"]
    assert body["candidates"] == []


def test_download_returns_a_working_presigned_url(client):
    project_id = _create_project(client)
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD).json()[
        "generation_id"
    ]
    _run_worker_once()

    res = client.get(f"/api/v1/generations/{gen_id}/candidates/1/download?format=dxf")
    assert res.status_code == 200
    download_url = res.json()["download_url"]
    assert res.json()["watermarked"] is False

    token = download_url.rsplit("/", 1)[-1]
    fetch = client.get(f"/api/v1/local-artifacts/{token}")
    assert fetch.status_code == 200
    assert fetch.content.startswith(b"  0") or b"SECTION" in fetch.content[:50]


def test_download_unknown_format_returns_404(client):
    project_id = _create_project(client)
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD).json()[
        "generation_id"
    ]
    _run_worker_once()

    res = client.get(f"/api/v1/generations/{gen_id}/candidates/1/download?format=pdf")
    assert res.status_code == 404


def test_delete_generation_removes_it_and_its_artifacts(client):
    project_id = _create_project(client)
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD).json()[
        "generation_id"
    ]
    _run_worker_once()

    download_url = client.get(f"/api/v1/generations/{gen_id}/candidates/1/download?format=dxf").json()["download_url"]
    token = download_url.rsplit("/", 1)[-1]

    res = client.delete(f"/api/v1/generations/{gen_id}")
    assert res.status_code == 200

    assert client.get(f"/api/v1/generations/{gen_id}").status_code == 404
    # The artifact file itself is gone too, not just the DB row.
    assert client.get(f"/api/v1/local-artifacts/{token}").status_code == 404


def test_generations_require_authentication(client):
    res = client.get("/api/v1/generations/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401
