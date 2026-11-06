import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader

from jobsearch_agents.actions.common import MATERIALS_ROOT, RUNS_DIR, default_context
from jobsearch_agents.delivery.resume import ResumePlan, normalize, verify_resume_pdf
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration
RESUME_DIR = MATERIALS_ROOT / "AI全栈开发实习生-北京" / "ASu新版"


def test_actual_package_greeting_edit_is_persisted(tmp_path: Path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery' / 'state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages")]
    ready = next(package for package in packages if package["status"] == "ready")
    sent = next(package for package in packages if package["status"] == "sent")
    service = DeliveryService(default_context(), tmp_path / "delivery")
    copied = dict(ready)
    directory = service.root / "packages" / ready["id"]
    directory.mkdir(parents=True)
    copied["pdf"] = str(shutil.copy2(ready["pdf"], directory / "简历.pdf"))
    service.save("packages", copied["id"], copied)
    service.save("packages", sent["id"], sent)
    app = FastAPI()
    app.include_router(router(service))
    endpoint = f"/api/delivery/packages/{copied['id']}/greeting"
    with TestClient(app) as client:
        assert client.patch(endpoint, json={"greeting": " "}).status_code == 409
        assert client.patch(endpoint, json={"greeting": ""}).status_code == 422
        response = client.patch(endpoint, json={"greeting": ready["greeting"] + " "})
        assert response.status_code == 200
        assert response.json()["greeting"] == ready["greeting"].strip()
        assert (directory / "打招呼语.md").read_text(encoding="utf-8") == ready["greeting"].strip()
        assert client.patch(f"/api/delivery/packages/{sent['id']}/greeting",
                            json={"greeting": sent["greeting"]}).status_code == 409
        assert client.patch("/api/delivery/packages/missing/greeting",
                            json={"greeting": ready["greeting"]}).status_code == 404
    assert service.get("packages", copied["id"])["greeting"] == ready["greeting"].strip()
    assert Path(copied["pdf"]).read_bytes() == Path(ready["pdf"]).read_bytes()
    service.executor.shutdown()


def test_actual_asu_resume_and_printed_document():
    plan = ResumePlan.model_validate_json((RESUME_DIR / "resume.json").read_text(encoding="utf-8"))
    assert verify_resume_pdf(plan, RESUME_DIR / "简历.pdf")["all_text"]
    checks = json.loads((RESUME_DIR / "checks.json").read_text(encoding="utf-8"))
    assert 82 <= checks["layout"]["fill_percent"] <= 100
    text = PdfReader(RESUME_DIR / "简历.pdf").pages[0].extract_text()
    for internal in ("自动保存", "Resume Evidence", "个人项目", "独立开发", "独立完成", "待确认", "待补充"):
        assert internal not in text
    for education in plan.education:
        if education.gpa:
            assert normalize("GPA:" + education.gpa) in normalize(text)


def test_actual_browser_edit_persists_and_prints(tmp_path: Path):
    html = tmp_path / "editable-resume.html"
    shutil.copyfile(RESUME_DIR / "简历.html", html)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 1400}, locale="zh-CN")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(html.as_uri(), wait_until="load")
        page.locator('[data-action="edit"]').click()
        expect(page.locator("main.sheet")).to_have_attribute("contenteditable", "false")
        page.locator('[data-action="edit"]').click()
        intention = "求职意向：AI 全栈开发实习生（北京）"
        page.locator("header strong").fill(intention)
        expect(page.locator("[data-save-status]")).to_have_text("已自动保存")
        page.reload(wait_until="load")
        expect(page.locator("header strong")).to_have_text(intention)
        page.evaluate("document.fonts.ready")
        page.emulate_media(media="print")
        page.pdf(path=str(tmp_path / "edited-resume.pdf"), prefer_css_page_size=True,
                 print_background=True, display_header_footer=False)
        browser.close()
    assert not errors
    reader = PdfReader(tmp_path / "edited-resume.pdf")
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert normalize(intention) in normalize(text)
    assert "自动保存" not in text


def test_actual_resume_download_through_delivery_api(tmp_path: Path):
    service = DeliveryService(default_context(), tmp_path / "delivery")
    directory = service.root / "packages" / "asu-resume"
    directory.mkdir(parents=True)
    html = directory / "简历.html"
    shutil.copyfile(RESUME_DIR / "简历.html", html)
    service.save("packages", "asu-resume", {"id": "asu-resume", "html": str(html)})
    app = FastAPI()
    app.include_router(router(service))
    with TestClient(app) as client:
        response = client.get("/api/delivery/packages/asu-resume/html")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.content == html.read_bytes()
    service.executor.shutdown()
