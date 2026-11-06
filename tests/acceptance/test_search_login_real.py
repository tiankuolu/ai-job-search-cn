import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


def test_real_logged_out_search_returns_login_message_without_creating_task(tmp_path: Path):
    service = DeliveryService(default_context(), tmp_path / "delivery")
    shutil.copy2(RUNS_DIR / "delivery/settings.json", service.root / "settings.json")
    status = service.bridge().call("GET", "status")
    if status["logged_in"]:
        service.executor.shutdown(wait=True)
        pytest.skip("真实 BOSS 账号已登录，未登录检查需要退出后的实际状态")
    app = FastAPI()
    app.include_router(router(service))
    with TestClient(app) as client:
        response = client.post("/api/delivery/search", json={"keywords": ["Agent"], "limit": 1, "prepare": False})
        assert response.status_code == 409
        assert "BOSS" in response.json()["detail"]
        assert "登录" in response.json()["detail"]
        assert service.list("tasks") == []
    service.executor.shutdown(wait=True)
