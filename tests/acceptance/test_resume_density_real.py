import json
import sqlite3
from pathlib import Path

import pytest

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.resume import MIN_FILL_PERCENT, export_resume_pdf
from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


def test_actual_sparse_resume_is_rejected_for_export_and_delivery(tmp_path: Path):
    with sqlite3.connect(f"{(RUNS_DIR / 'delivery' / 'state.sqlite').as_uri()}?mode=ro", uri=True) as database:
        packages = [json.loads(row[0]) for row in database.execute("SELECT data FROM packages ORDER BY rowid DESC")]
    package = next(item for item in packages if item["status"] == "ready"
                   and item.get("checks", {}).get("layout", {}).get("fill_percent", 100) < MIN_FILL_PERCENT)
    pdf = tmp_path / "简历.pdf"
    with pytest.raises(ValueError, match="留白"):
        export_resume_pdf(Path(package["html"]), pdf)
    assert not pdf.exists()
    service = DeliveryService(default_context(), tmp_path / "delivery")
    service.save("packages", package["id"], package)
    with pytest.raises(ValueError, match="单页占用"):
        service.deliver({}, [package["id"]])
    service.executor.shutdown()
