import json
import sqlite3
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


def test_revision_rejects_version_from_another_actual_job(tmp_path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        jobs = [json.loads(row[0]) for row in database.execute("SELECT data FROM jobs")]
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages")]
    source = next(package for package in packages if package["status"] == "ready")
    target = next(job for job in jobs if job["id"] != source["job_id"] and not job.get("deleted_at"))
    service = DeliveryService(replace(default_context(), materials_root=tmp_path / "materials"), tmp_path / "delivery")
    service.save("jobs", target["id"], target)
    service.save("packages", source["id"], source)
    app = FastAPI()
    app.include_router(router(service))
    with TestClient(app) as client:
        response = client.post("/api/delivery/prepare", json={"job_ids": [target["id"]],
                               "base_package_id": source["id"], "revision": "突出工具调用"})
        assert response.status_code == 409
        assert not service.list("tasks")
        assert service.get("packages", source["id"]) == source
    service.url_importer.close()
    service.executor.shutdown(wait=True)
