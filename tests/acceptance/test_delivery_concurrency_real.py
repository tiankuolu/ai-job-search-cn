import json
import shutil
import sqlite3
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


def test_actual_jobs_run_concurrently_and_export_independently(tmp_path: Path):
    original = default_context()
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        jobs = [json.loads(row[0]) for row in database.execute("SELECT data FROM jobs")]
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages ORDER BY rowid DESC")]
    package = next(item for item in packages if item["status"] == "ready" and item.get("html")
                   and item.get("checks", {}).get("layout", {}).get("fill_percent", 0) >= 95)
    selected = [job for job in jobs if job["id"] != package["job_id"] and Path(job["jd_path"]).is_file()][:4]
    assert len(selected) == 4
    materials = tmp_path / "materials"
    shutil.copytree(original.profile_dir, materials / "个人资料")
    context = replace(original, materials_root=materials, profile_dir=materials / "个人资料")
    service = DeliveryService(context, tmp_path / "delivery")
    shutil.copy2(RUNS_DIR / "delivery/settings.json", service.root / "settings.json")
    for job in selected:
        target = context.inbox_dir / f"{job['id']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(job["jd_path"], target)
        service.save("jobs", job["id"], {**job, "jd_path": str(target)})
    directory = service.root / "packages" / package["id"]
    directory.mkdir(parents=True)
    copied = dict(package)
    for kind, suffix in (("html", "html"), ("pdf", "pdf"), ("image", "png")):
        copied[kind] = str(shutil.copy2(package[kind], directory / f"简历.{suffix}"))
    service.save("packages", copied["id"], copied)
    app = FastAPI()
    app.include_router(router(service))
    try:
        with TestClient(app) as client:
            response = client.post("/api/delivery/analyze", json={"job_ids": [job["id"] for job in selected]})
            assert response.status_code == 202, response.text
            task_ids = response.json()["task_ids"]
            assert len(task_ids) == 4
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                tasks = [service.get("tasks", identifier) for identifier in task_ids]
                if sum(task["status"] == "running" for task in tasks) == 3:
                    break
                time.sleep(0.1)
            assert sum(task["status"] == "running" for task in tasks) == 3
            assert sum(task["status"] == "queued" for task in tasks) == 1
            duplicate = client.post("/api/delivery/analyze", json={"job_ids": [selected[0]["id"]]})
            assert duplicate.status_code == 409
            endpoint = f"/api/delivery/packages/{copied['id']}/greeting"
            assert client.patch(endpoint, json={"greeting": copied["greeting"]}).status_code == 200
            exported = client.post("/api/delivery/export", json={"package_ids": [copied["id"]],
                                    "expected_revision": copied.get("editor_revision", 0)})
            assert exported.status_code == 202, exported.text
            assert client.patch(endpoint, json={"greeting": copied["greeting"]}).status_code == 409
            all_ids = [*task_ids, exported.json()["id"]]
            while time.monotonic() < deadline:
                finished = [service.get("tasks", identifier) for identifier in all_ids]
                if all(task["status"] not in {"running", "queued"} for task in finished):
                    break
                time.sleep(0.2)
            assert all(task["status"] == "completed" for task in finished), finished
            analyses = [service.get("tasks", identifier) for identifier in task_ids]
            starts = [datetime.fromisoformat(task["started_at"]) for task in analyses]
            ends = [datetime.fromisoformat(task["ended_at"]) for task in analyses]
            assert max(starts[:3]) < min(ends[:3])
            assert starts[3] >= min(ends[:3])
            current = service.get("packages", copied["id"])
            assert current["checks"]["pages"] == 1
            assert 95 <= current["checks"]["layout"]["fill_percent"] <= 100
            (tmp_path / "parallel-verification.json").write_text(
                json.dumps({"tasks": finished, "checks": current["checks"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        service.executor.shutdown(wait=True)
