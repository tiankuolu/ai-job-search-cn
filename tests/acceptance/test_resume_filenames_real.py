import hashlib
import json
import shutil
import sqlite3
from email.message import Message
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.filenames import filesystem_path, name_resume_assets
from jobsearch_agents.delivery.routes import router
from jobsearch_agents.delivery.service import DeliveryService

pytestmark = pytest.mark.integration


def test_real_pdf_filename_download_and_blank_company(tmp_path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery/state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages")]
    source = next(row for row in packages if row.get("status") == "ready" and row.get("pdf") and Path(row["pdf"]).is_file())
    service = DeliveryService(default_context(), tmp_path / "delivery")
    app = FastAPI()
    app.include_router(router(service))
    with TestClient(app) as client:
        for index, company in enumerate((source["company"], "")):
            identifier = f"filename-{index}"
            directory = service.root / "packages" / identifier
            directory.mkdir(parents=True)
            target = directory / "简历.pdf"
            shutil.copyfile(source["pdf"], target)
            assets = name_resume_assets({"pdf": str(target)}, company, source["title"])
            service.save("packages", identifier, {**source, "id": identifier, "company": company,
                                                "resume_dirty": False, **assets})
            response = client.get(f"/api/delivery/packages/{identifier}/pdf")
            assert response.status_code == 200
            header = Message()
            header["Content-Disposition"] = response.headers["content-disposition"]
            assert header.get_filename() == f"{company}-{source['title']}.pdf"
            assert hashlib.sha256(response.content).hexdigest() == hashlib.sha256(Path(source["pdf"]).read_bytes()).hexdigest()
            assert filesystem_path(Path(assets["pdf"])).is_file()
    service.url_importer.close()
    service.executor.shutdown(wait=True)
