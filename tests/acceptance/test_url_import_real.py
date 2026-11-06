import json
import shutil
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(tmp_path):
    service = DeliveryService(replace(default_context(), materials_root=tmp_path / "materials"), tmp_path / "delivery")
    shutil.copyfile(RUNS_DIR / "delivery/settings.json", service.root / "settings.json")
    app = FastAPI()
    app.include_router(router(service))
    with TestClient(app) as client:
        yield service, client
    service.url_importer.close()
    service.executor.shutdown(wait=True)


def test_official_url_extracts_complete_duties_and_requirements_and_saves(workspace):
    service, client = workspace
    url = "https://job.xiaohongshu.com/campus/intern/position/21906"
    response = client.post("/api/delivery/imports/url", json={"url": url})
    assert response.status_code == 200, response.text
    extracted = response.json()
    fields = extracted["fields"]
    assert extracted["status"] == "ready"
    assert fields["company"] == "小红书"
    assert "28/29" in fields["title"]
    assert "后端服务开发" in fields["responsibilities"]
    assert "FastAPI" in fields["requirements"]
    assert "每周可出勤" in fields["requirements"]
    assert "北京" in fields["city"]
    source = json.loads((service.root / "imports" / extracted["import_id"] / "source.json").read_text(encoding="utf-8"))
    assert fields["responsibilities"] == source["data"]["duty"]
    assert fields["requirements"] == source["data"]["qualification"]
    response = client.post("/api/delivery/jobs", json={**{key: fields[key] for key in ("company", "title", "city", "url", "platform")},
                           "description": extracted["description"], "fields": fields, "import_id": extracted["import_id"]})
    assert response.status_code == 201, response.text
    assert service.get("jobs", response.json()["id"])["fields"] == fields


def test_url_import_rejects_non_web_links_and_embedded_credentials(workspace):
    _, client = workspace
    assert client.post("/api/delivery/imports/url", json={"url": "file:///private"}).status_code == 422
    assert client.post("/api/delivery/imports/url", json={"url": "https://user:password@example.com/job"}).status_code == 422


def test_boss_url_uses_actual_login_state_and_complete_page(workspace):
    service, client = workspace
    status = service.bridge().call("GET", "status")
    response = client.post("/api/delivery/imports/url", json={"url": "https://www.zhipin.com/job_detail/e30bd24b9b21d5620nFz3920GFFV.html"})
    assert response.status_code == 200, response.text
    extracted = response.json()
    if not status["logged_in"]:
        assert extracted["status"] == "login_required"
        assert "fields" not in extracted
    else:
        assert extracted["status"] == "ready"
        assert "中关村" in extracted["fields"]["company"]
        assert extracted["fields"]["responsibilities"]
        assert extracted["fields"]["requirements"]
