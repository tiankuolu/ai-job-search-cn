import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from jobsearch_agents.actions.common import REPO_ROOT, RUNS_DIR, default_context
from jobsearch_agents.delivery.editing import export_edited_resume, resume_document, sheet_content
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService
from jobsearch_agents.delivery.resume import normalize


pytestmark = pytest.mark.integration


@pytest.fixture
def editor_workspace(tmp_path: Path):
    sources = sorted((REPO_ROOT / ".artifacts").glob("resume-density-*/checks.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    source = next(path.parent for path in sources if json.loads(path.read_text(encoding="utf-8"))["layout"]["fill_percent"] >= 95)
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages ORDER BY rowid DESC")]
    package = next(item for item in packages if item["status"] == "ready" and item.get("platform") == "boss" and item.get("url"))
    service = DeliveryService(default_context(), tmp_path / "delivery")
    shutil.copy2(RUNS_DIR / "delivery/settings.json", service.root / "settings.json")
    directory = service.root / "packages" / package["id"]
    shutil.copytree(source, directory)
    package = dict(package)
    for kind, filename in {"html": "简历.html", "pdf": "简历.pdf", "image": "简历.png"}.items():
        package[kind] = str(directory / filename)
    package["checks"] = json.loads((directory / "checks.json").read_text(encoding="utf-8"))
    for kind in ("pdf", "image"):
        package[f"{kind}_sha256"] = hashlib.sha256(Path(package[kind]).read_bytes()).hexdigest()
    service.save("packages", package["id"], package)
    app = FastAPI()
    app.include_router(router(service))
    yield service, package, app
    service.executor.shutdown(wait=True)


def test_html_edit_persists_and_exports_actual_pdf(editor_workspace):
    service, package, app = editor_workspace
    endpoint = f"/api/delivery/packages/{package['id']}"
    original_pdf = Path(package["pdf"]).read_bytes()
    _, sheet = resume_document(Path(package["html"]).read_text(encoding="utf-8"))
    heading = next(item for item in sheet.xpath('.//h2') if item.text_content() == "竞赛与语言")
    heading.text = "语言与竞赛"
    with TestClient(app) as client:
        state = client.get(endpoint + "/resume").json()
        revision = state["revision"]
        assert "resumeEditorConfig" in state["document"]
        response = client.patch(endpoint + "/resume", json={"content": sheet_content(sheet), "base_revision": revision})
        assert response.status_code == 200
        assert response.json()["revision"] == revision + 1
        assert "语言与竞赛" in client.get(endpoint + "/resume").json()["document"]
        assert client.get(endpoint + "/pdf").status_code == 409
        assert client.get(endpoint + "/image").status_code == 409
        with pytest.raises(ValueError, match="重新导出"):
            service.deliver({}, [package["id"]])
        assert client.patch(endpoint + "/resume", json={"content": sheet_content(sheet), "base_revision": revision}).status_code == 409
        response = client.post("/api/delivery/export", json={"package_ids": [package["id"]], "expected_revision": revision + 1})
        assert response.status_code == 202
        service.executor.shutdown(wait=True)
        task = service.get("tasks", response.json()["id"])
        assert task["status"] == "completed", task["error"]
        current = service.get("packages", package["id"])
        assert current["resume_dirty"] is False
        assert current["exported_revision"] == current["editor_revision"] == revision + 1
        assert current["checks"]["pages"] == 1
        assert 95 <= current["checks"]["layout"]["fill_percent"] <= 100
        assert current["pdf_sha256"] == hashlib.sha256(Path(current["pdf"]).read_bytes()).hexdigest()
        assert current["html_sha256"] == hashlib.sha256(Path(current["html"]).read_bytes()).hexdigest()
        text = PdfReader(current["pdf"]).pages[0].extract_text()
        assert "语言与竞赛" in text and "竞赛与语言" not in text
        assert client.get(endpoint + "/pdf").status_code == 200
        png = client.get(endpoint + "/image")
        assert png.status_code == 200
        assert png.headers["content-type"] == "image/png"
        assert png.content == Path(current["image"]).read_bytes()
        assert Path(package["pdf"]).read_bytes() == original_pdf
        Path(current["html"]).write_text(Path(current["html"]).read_text(encoding="utf-8") + " ", encoding="utf-8")
        with pytest.raises(ValueError, match="文件已改变"):
            service.deliver({}, [package["id"]])


def test_human_edited_education_and_spacing_export_directly(editor_workspace, tmp_path: Path):
    service, package, app = editor_workspace
    endpoint = f"/api/delivery/packages/{package['id']}/resume"
    _, sheet = resume_document(Path(package["html"]).read_text(encoding="utf-8"))
    gpa = next(item for item in sheet.xpath('.//span') if item.text and item.text.startswith("GPA："))
    updated_gpa = gpa.text + "（编辑）"
    gpa.text = updated_gpa
    for element in sheet.xpath('.//article[contains(@class, "project")]/ul/li[position() > 1]'):
        element.getparent().remove(element)
    with TestClient(app) as client:
        revision = client.get(endpoint).json()["revision"]
        assert client.patch(endpoint, json={"content": "<p> </p>", "base_revision": revision}).status_code == 409
        assert client.patch(endpoint, json={"content": sheet_content(sheet), "base_revision": revision}).status_code == 200
    current = service.get("packages", package["id"])
    assets = export_edited_resume(Path(current["html"]), tmp_path / "export", service.bridge().settings["tools"])
    assert assets["checks"]["human_edited"] is True
    assert assets["checks"]["layout"]["fill_percent"] < 95
    text = "".join(page.extract_text() for page in PdfReader(assets["pdf"]).pages)
    assert normalize(updated_gpa) in normalize(text)


def test_actual_structured_resume_converts_to_editable_html(tmp_path: Path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages")]
    packages += [json.loads(path.read_text(encoding="utf-8"))
                 for path in (RUNS_DIR / "delivery/packages").glob("*/html-conversion/*/previous-package.json")]
    package = next(item for item in packages if item["status"] == "ready" and not item.get("html"))
    original = RUNS_DIR / "delivery/packages" / package["id"]
    service = DeliveryService(default_context(), tmp_path / "delivery")
    directory = service.root / "packages" / package["id"]
    shutil.copytree(original, directory)
    package = dict(package)
    package["pdf"] = str(directory / "简历.pdf")
    package["image"] = str(directory / "简历.png")
    service.save("packages", package["id"], package)
    original_pdf = Path(package["pdf"]).read_bytes()
    app = FastAPI()
    app.include_router(router(service))
    endpoint = f"/api/delivery/packages/{package['id']}/resume"
    with TestClient(app) as client:
        assert client.get(endpoint).json()["requires_conversion"]
        response = client.post(endpoint + "/convert")
        assert response.status_code == 200
        assert response.json()["dirty"] is True
        assert response.json()["revision"] == 1
        assert "main" in response.json()["document"]
        assert client.post(endpoint + "/convert").json()["revision"] == 1
        assert Path(package["pdf"]).read_bytes() == original_pdf
    service.executor.shutdown()
