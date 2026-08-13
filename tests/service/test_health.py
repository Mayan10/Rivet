def test_healthz_is_always_ok(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_readyz_reports_database_connectivity(client):
    res = client.get("/readyz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_readyz_returns_503_when_database_unreachable(client, monkeypatch):
    import rivet_service.main as main_module

    monkeypatch.setattr(main_module, "database_is_reachable", lambda: False)
    res = client.get("/readyz")
    assert res.status_code == 503
    assert res.json() == {"status": "not_ready", "database": False}
