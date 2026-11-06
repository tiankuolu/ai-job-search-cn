import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.editing import resume_document, sheet_content
from jobsearch_agents.delivery.routes import PrepareRequest, router
from jobsearch_agents.delivery.service import DeliveryService
from jobsearch_agents.delivery.website_projects import resume_projects


pytestmark = pytest.mark.integration


@pytest.fixture
def actual_materials(tmp_path: Path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages ORDER BY rowid DESC")]
        jobs = {row[0]: json.loads(row[1]) for row in database.execute("SELECT id,data FROM jobs")}
    package = next(item for item in packages if item["status"] == "ready" and item.get("html")
                   and item.get("generation_input_sha256") and item["job_id"] in jobs)
    service = DeliveryService(default_context(), tmp_path / "delivery")
    shutil.copy2(RUNS_DIR / "delivery/settings.json", service.root / "settings.json")
    job = jobs[package["job_id"]]
    service.save("jobs", job["id"], job)
    copied = dict(package)
    directory = service.root / "packages" / package["id"]
    directory.mkdir(parents=True)
    for kind in ("html", "pdf", "image"):
        copied[kind] = str(shutil.copy2(package[kind], directory / Path(package[kind]).name))
    for key in list(copied):
        if key.startswith("website_projects"):
            del copied[key]
    service.save("packages", copied["id"], copied)
    cache = RUNS_DIR / "delivery/generation-cache" / package["generation_input_sha256"]
    if cache.is_dir():
        shutil.copytree(cache, service.root / "generation-cache" / cache.name)
    app = FastAPI()
    app.include_router(router(service))
    try:
        with TestClient(app) as client:
            yield service, client, copied, job
    finally:
        service.executor.shutdown(wait=True)


def wait_for_task(service, task):
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        record = service.get("tasks", task["id"])
        if record["status"] in {"completed", "failed"}:
            assert record["status"] == "completed", record["error"]
            return record
        time.sleep(0.2)
    pytest.fail("材料生成任务超时")


def test_current_resume_projects_generate_download_and_reject_stale(actual_materials):
    service, client, package, _ = actual_materials
    original = Path(package["html"]).read_bytes()
    revision = package.get("editor_revision", 0)
    response = client.post("/api/delivery/website-projects", json={"package_ids": [package["id"]], "expected_revision": revision + 1})
    assert response.status_code == 409
    response = client.post("/api/delivery/website-projects", json={"package_ids": [package["id"]], "expected_revision": revision})
    assert response.status_code == 202, response.text
    wait_for_task(service, response.json())
    result = service.get("packages", package["id"])
    assert Path(package["html"]).read_bytes() == original
    assert result["website_projects_resume_sha256"] == hashlib.sha256(Path(package["html"]).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    expected = resume_projects(original.decode("utf-8"))
    assert [item["name"] for item in result["website_projects"]] == [item["name"] for item in expected]
    for project in result["website_projects"]:
        assert project["description"] and project["responsibilities"]
    endpoint = f"/api/delivery/packages/{package['id']}/website_projects_file"
    download = client.get(endpoint)
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    for project in result["website_projects"]:
        assert project["description"] in download.text and project["responsibilities"] in download.text
    assert "description_evidence" not in download.text
    _, sheet = resume_document(original.decode("utf-8"))
    bullet = sheet.xpath('.//article[contains(@class,"project")]/ul/li')[0]
    bullet.text = (bullet.text or "") + " "
    changed = client.patch(f"/api/delivery/packages/{package['id']}/resume", json={"content": sheet_content(sheet), "base_revision": revision})
    assert changed.status_code == 200, changed.text
    assert client.get(endpoint).status_code == 409


def test_prepare_option_generates_website_fields(actual_materials):
    service, client, package, job = actual_materials
    assert PrepareRequest(job_ids=[job["id"]]).include_website_projects is False
    response = client.post("/api/delivery/prepare", json={"job_ids": [job["id"]], "include_website_projects": True})
    assert response.status_code == 202, response.text
    task = wait_for_task(service, response.json())
    result = service.get("packages", task["result"]["packages"][0])
    assert result["id"] != package["id"]
    assert result["website_projects_revision"] == 0
    assert result["website_projects"]
    assert result["checks"]["all_text"] and result["checks"]["pages"] == 1
    assert Path(result["website_projects_file"]).is_file()
    assert [item["name"] for item in result["website_projects"]] == [item["name"] for item in resume_projects(Path(result["html"]).read_text(encoding="utf-8"))]


def test_supplements_real_generation_download_and_stale_revision(actual_materials):
    service, client, package, _ = actual_materials
    original = Path(package["html"]).read_bytes()
    revision = package.get("editor_revision", 0)
    for kind in ("self_description", "english_resume"):
        endpoint = f"/api/delivery/supplements/{kind}"
        assert client.post(endpoint, json={"package_ids": [package["id"]], "expected_revision": revision + 1}).status_code == 409
        response = client.post(endpoint, json={"package_ids": [package["id"]], "expected_revision": revision})
        assert response.status_code == 202, response.text
        wait_for_task(service, response.json())
    result = service.get("packages", package["id"])
    assert Path(package["html"]).read_bytes() == original
    assert result["english_checks"]["pages"] == 1 and result["english_checks"]["all_text"]
    assert result["self_description"].strip()
    english = Path(result["english_html"]).read_text(encoding="utf-8")
    assert 'data-action="save"' in english and 'contenteditable="true"' in english
    for kind in ("english_html", "english_pdf", "english_image", "self_description_file"):
        response = client.get(f"/api/delivery/packages/{package['id']}/{kind}")
        assert response.status_code == 200, response.text[:200]
        assert response.content == Path(result[kind]).read_bytes()
    _, sheet = resume_document(original.decode("utf-8"))
    sheet.xpath('.//li')[0].text = (sheet.xpath('.//li')[0].text or "") + " "
    response = client.patch(f"/api/delivery/packages/{package['id']}/resume", json={"content": sheet_content(sheet), "base_revision": revision})
    assert response.status_code == 200, response.text
    for kind in ("english_html", "english_pdf", "english_image", "self_description_file"):
        assert client.get(f"/api/delivery/packages/{package['id']}/{kind}").status_code == 409


def test_prepare_with_all_optional_materials(actual_materials):
    service, client, _, job = actual_materials
    response = client.post("/api/delivery/prepare", json={"job_ids": [job["id"]],
        "include_website_projects": True, "include_english_resume": True, "include_self_description": True})
    assert response.status_code == 202, response.text
    task = wait_for_task(service, response.json())
    result = service.get("packages", task["result"]["packages"][0])
    assert result["website_projects"] and result["self_description"]
    assert result["english_checks"]["all_text"] and result["english_checks"]["pages"] == 1
    assert result["website_projects_revision"] == result["english_resume_revision"] == result["self_description_revision"] == 0
