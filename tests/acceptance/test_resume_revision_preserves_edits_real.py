import json
from pathlib import Path

import pytest
from lxml import html
from pypdf import PdfReader

from jobsearch_agents.actions.common import REPO_ROOT, default_context
from jobsearch_agents.delivery.editing import current_resume_draft, resume_document
from jobsearch_agents.delivery.resume import ResumePlan, fit_resume_layout, normalize, render_resume


pytestmark = pytest.mark.integration


def test_revision_keeps_user_headings_styles_and_unaffected_projects(tmp_path: Path):
    baseline = REPO_ROOT / ".artifacts/resume-speed-comparison-20261031/samples/acaea5439b835d4eb614afa7-1-baseline"
    measured = json.loads((baseline / "measurement.json").read_text(encoding="utf-8"))
    package = {**measured["assets"], "application": str(baseline / "application.md")}
    document = html.document_fromstring(Path(package["html"]).read_text(encoding="utf-8"))
    heading = next(item for item in document.xpath("//h2") if item.text_content() == "竞赛与语言")
    heading.text = "语言与竞赛"
    document.xpath("//h1")[0].set("style", "color:rgb(20,50,80)")
    edited = html.tostring(document, encoding="unicode")
    current = current_resume_draft(package, default_context().read_resume_profile(), edited)
    previous = current.plan.model_dump()
    actual_source = REPO_ROOT / ".artifacts/resume-latency-20261031/live-replay/latency-baseline-20261031-171011-efac02/layout/round-1/font-9.5/resume.json"
    alternative = ResumePlan.model_validate_json(actual_source.read_text(encoding="utf-8"))
    revised = current.plan.model_copy(deep=True)
    revised.projects[0].bullets[0] = alternative.projects[0].bullets[0]
    source = (edited, previous)
    layout = fit_resume_layout(revised, tmp_path / "layout", "msedge", render_source=source)
    assert 95 <= layout["fill_percent"] <= 100
    result = render_resume(revised, tmp_path / "package", {"browser_channel": "msedge"},
                           body_font_pt=layout["body_font_pt"], render_source=source)
    text = PdfReader(result["pdf"]).pages[0].extract_text()
    assert "语言与竞赛" in text and "竞赛与语言" not in text
    _, exported = resume_document(Path(result["html"]).read_text(encoding="utf-8"))
    assert exported.xpath(".//h1")[0].get("style") == "color:rgb(20,50,80)"
    assert normalize(revised.projects[0].bullets[0]) in normalize(text)
    for project in current.plan.projects[1:]:
        assert all(normalize(bullet) in normalize(text) for bullet in project.bullets)
    (tmp_path / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
