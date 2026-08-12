import pytest

from rivet.api.app import create_app

VALID_PAYLOAD = {
    # Sized to stay feasible once circulation takes its share of the
    # buildable area (Phase 3) -- mirrors tests/conftest.py's sample_request.
    "plot": {
        "width_m": 15,
        "length_m": 13,
        "entrance": "north",
        "abutting_road_width_m": 9,
        "proposed_height_m": 6,
    },
    "rooms": [
        {"room_type": "living_room", "count": 1},
        {"room_type": "master_bedroom", "count": 1, "attached_bathroom": True},
        {"room_type": "bedroom", "count": 2, "attached_bathroom": True},
        {"room_type": "kitchen", "count": 1},
        {"room_type": "dining_room", "count": 1},
        {"room_type": "bathroom", "count": 1},
    ],
    "num_candidates": 2,
    "seed": 5,
}


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=str(tmp_path))
    app.testing = True
    return app.test_client()


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_room_types_includes_known_types(client):
    res = client.get("/api/v1/room-types")
    assert res.status_code == 200
    assert "bedroom" in res.get_json()


def test_rules_returns_rulebook(client):
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    data = res.get_json()
    assert "bedroom" in data
    assert data["bedroom"]["min_area_sqm"] > 0


def test_generate_happy_path(client):
    res = client.post("/api/v1/generate", json=VALID_PAYLOAD)
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["candidates"]) == 2
    for candidate in data["candidates"]:
        assert candidate["dxf_url"].startswith("/download/")
        assert candidate["svg"].startswith("<svg")
        assert candidate["score"] >= 0


def test_generate_then_download_dxf(client):
    res = client.post("/api/v1/generate", json=VALID_PAYLOAD)
    dxf_url = res.get_json()["candidates"][0]["dxf_url"]

    download = client.get(dxf_url)
    assert download.status_code == 200
    assert download.data.startswith(b"  0") or b"SECTION" in download.data[:50]


def test_generate_rejects_invalid_room_type(client):
    payload = {"plot": {"width_m": 10, "length_m": 10}, "rooms": [{"room_type": "not_a_room"}]}
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_generate_rejects_missing_body(client):
    res = client.post("/api/v1/generate")
    assert res.status_code == 400


def test_generate_rejects_empty_rooms(client):
    payload = {"plot": {"width_m": 10, "length_m": 10}, "rooms": []}
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 400


def test_download_rejects_path_traversal(client):
    res = client.get("/download/..%2F..%2Fetc%2Fpasswd")
    assert res.status_code == 404


def test_download_unknown_token_is_404(client):
    res = client.get("/download/" + "a" * 32 + ".dxf")
    assert res.status_code == 404


def test_generate_accepts_ruleset_and_setback_inputs(client):
    payload = {
        "plot": {
            "width_m": 15,
            "length_m": 13,
            "entrance": "north",
            "num_floors": 2,
            "abutting_road_width_m": 9,
            "proposed_height_m": 6,
        },
        "rooms": VALID_PAYLOAD["rooms"],
        "num_candidates": 1,
        "seed": 42,
        "ruleset": "tncdbr_2019",
    }
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 200


def test_generate_rejects_invalid_ruleset(client):
    payload = {**VALID_PAYLOAD, "ruleset": "not_a_real_ruleset"}
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 400
    assert "ruleset" in res.get_json()["error"]


def test_generate_reports_infeasible_request_as_422_not_a_crash(client):
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
    res = client.post("/api/v1/generate", json=tiny_payload)
    assert res.status_code == 422
    data = res.get_json()
    assert "infeasible" in data
    assert data["infeasible"]["violations"]
    for v in data["infeasible"]["violations"]:
        assert v["source"]  # every hard violation reported to API clients is cited


def test_rules_endpoint_accepts_ruleset_query_param(client):
    tncdbr = client.get("/api/v1/rules?ruleset=tncdbr_2019").get_json()
    generic = client.get("/api/v1/rules?ruleset=generic").get_json()
    assert tncdbr["bedroom"]["citation"].startswith("TNCDBR 2019")
    assert generic["bedroom"]["citation"] == "uncited placeholder"


def test_rules_endpoint_rejects_invalid_ruleset(client):
    res = client.get("/api/v1/rules?ruleset=nonsense")
    assert res.status_code == 400
