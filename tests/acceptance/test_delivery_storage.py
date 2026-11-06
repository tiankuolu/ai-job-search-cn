from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import default_context
from jobsearch_agents.delivery.service import DeliveryService
from jobsearch_agents.web import create_app


def test_delivery_starts_with_real_empty_database(tmp_path: Path):
    service = DeliveryService(default_context(), tmp_path / "delivery")
    assert service.snapshot() == {"configured": False, "jobs": [], "packages": [], "tasks": []}
    with service.connect() as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(KeyError):
        service.get("packages", "not-present")
    service.executor.shutdown()


def test_delivery_api_rejects_invalid_requests(tmp_path: Path):
    with TestClient(create_app(runs_dir=tmp_path / "runs")) as client:
        assert client.get("/api/delivery").json()["jobs"] == []
        assert client.get("/api/delivery/connection").status_code == 503
        assert client.post("/api/delivery/search", json={"keywords": [], "limit": 10}).status_code == 422
        assert client.post("/api/delivery/search", json={"keywords": ["Agent"], "limit": 101}).status_code == 422
        assert client.post("/api/delivery/send", json={"package_ids": ["missing"]}).status_code == 404
        assert client.post("/api/delivery/send", json={"package_ids": ["same", "same"]}).status_code == 422
        assert client.post("/api/delivery/login", json={}).status_code == 503
        assert client.get("/api/delivery/packages/missing/pdf").status_code == 404
