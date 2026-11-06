import html
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.imports import extract_document
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


@pytest.fixture
def actual_job():
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery' / 'state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        jobs = [json.loads(row[0]) for row in database.execute("SELECT data FROM jobs")]
    return next(job for job in jobs if "Python" in job["description"] and "北京" in job["city"])


def test_manual_entry_and_markdown_import_persist_actual_job(tmp_path: Path, actual_job):
    context = replace(default_context(), materials_root=tmp_path / "materials")
    service = DeliveryService(context, tmp_path / "delivery")
    app = FastAPI()
    app.include_router(router(service))
    original = Path(actual_job["jd_path"]).read_bytes()
    with TestClient(app) as client:
        response = client.post("/api/delivery/imports/extract", files={"file": ("岗位.md", original, "text/markdown")})
        assert response.status_code == 200
        extracted = response.json()
        assert extracted["description"] == Path(actual_job["jd_path"]).read_text(encoding="utf-8-sig").strip()
        assert extracted["fields"]["company"]
        assert extracted["fields"]["title"]
        assert "北京" in extracted["fields"]["city"]
        data = {"company": actual_job["company"], "title": actual_job["title"], "city": actual_job["city"],
                "description": extracted["description"], "import_id": extracted["import_id"], "fields": extracted["fields"]}
        response = client.post("/api/delivery/jobs", json=data)
        assert response.status_code == 201
        job = response.json()
        assert job["match"]["status"] == "pending"
        assert job["platform"] == "manual"
        assert job["fields"] == extracted["fields"]
        assert Path(job["jd_path"]).is_relative_to(context.inbox_dir)
        assert extracted["description"] in Path(job["jd_path"]).read_text(encoding="utf-8")
        assert client.post("/api/delivery/jobs", json=data).json()["id"] == job["id"]
        data.pop("import_id")
        data["description"] = actual_job["description"]
        assert client.post("/api/delivery/jobs", json=data).status_code == 201
        assert client.post("/api/delivery/imports/extract", files={"file": ("岗位.exe", original)}).status_code == 415
        assert client.post("/api/delivery/imports/extract", files={"file": ("岗位.md", b"")}).status_code == 422
        unnamed = client.post("/api/delivery/jobs", json={**data, "company": " "})
        assert unnamed.status_code == 201
        assert unnamed.json()["company"] == ""
    assert len(service.snapshot()["jobs"]) == 3
    service.executor.shutdown()


def test_actual_jd_pdf_png_and_scanned_pdf_extract(tmp_path: Path, actual_job):
    content = f"{actual_job['company']}\n{actual_job['title']}\n{actual_job['city']}\n{actual_job['description']}"
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        spare, scale = page.insert_htmlbox(pymupdf.Rect(30, 30, 565, 812),
                                          f"<div style='white-space:pre-wrap'>{html.escape(content)}</div>",
                                          css="div {font-size:12pt;line-height:1.6}")
        assert spare >= 0 and scale > 0
        pdf = document.tobytes()
        image = page.get_pixmap(dpi=160).tobytes("png")
    (tmp_path / "真实岗位.pdf").write_bytes(pdf)
    (tmp_path / "真实岗位.png").write_bytes(image)
    text_result = extract_document(pdf, ".pdf")
    assert "Python" in text_result["description"]
    assert "北京" in text_result["description"]
    image_result = extract_document(image, ".png")
    assert "Python" in image_result["description"]
    assert "北京" in image_result["description"]
    with pymupdf.open() as scanned:
        page = scanned.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=image)
        scanned_pdf = scanned.tobytes()
    (tmp_path / "真实岗位扫描.pdf").write_bytes(scanned_pdf)
    scanned_result = extract_document(scanned_pdf, ".pdf")
    assert "本地 OCR" in scanned_result["method"]
    assert "Python" in scanned_result["description"]
    assert "北京" in scanned_result["description"]
