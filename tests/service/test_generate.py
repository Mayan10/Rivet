VALID_PAYLOAD = {
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
    "seed": 42,
}


def test_generate_happy_path(client):
    res = client.post("/api/v1/generate", json=VALID_PAYLOAD)
    assert res.status_code == 200
    data = res.json()
    assert len(data["candidates"]) == 2
    for candidate in data["candidates"]:
        assert candidate["score"] >= 0
        assert candidate["svg"].startswith("<svg")
        assert candidate["dxf_url"] is None  # no storage yet, see Phase 8


def test_generate_rejects_invalid_room_type(client):
    payload = {**VALID_PAYLOAD, "rooms": [{"room_type": "not_a_room"}]}
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "validation_failed"


def test_generate_rejects_empty_rooms(client):
    payload = {**VALID_PAYLOAD, "rooms": []}
    res = client.post("/api/v1/generate", json=payload)
    # 400 even though this is FastAPI's own request-validation path
    # (min_length=1) -- see errors.py, 422 is reserved for infeasible.
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"


def test_generate_reports_infeasible_as_422_with_consistent_envelope(client):
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
    body = res.json()
    assert body["error"]["code"] == "infeasible_program"
    assert body["error"]["details"]["violations"]
    for v in body["error"]["details"]["violations"]:
        assert v["source"]  # every hard violation reported is cited


def test_generate_with_vastu_returns_preferences(client):
    payload = {
        **VALID_PAYLOAD,
        "rooms": [*VALID_PAYLOAD["rooms"], {"room_type": "pooja", "count": 1}],
        "vastu": {"enabled": True, "weight": 1.0, "plot_north": "north"},
        "num_candidates": 5,  # see docs/architecture.md "Determinism" known limit
    }
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 200
    candidate = res.json()["candidates"][0]
    assert candidate["vastu_preferences"]
    assert "vastu" in candidate["score_breakdown"]


def test_generate_rejects_vastu_enabled_without_plot_north(client):
    payload = {**VALID_PAYLOAD, "vastu": {"enabled": True}}
    res = client.post("/api/v1/generate", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"
