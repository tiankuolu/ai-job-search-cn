import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from jobsearch_agents.actions.common import REPO_ROOT, default_context
from jobsearch_agents.delivery.generation import WriterDraft, confirmed_fields, education_label, source_facts
from jobsearch_agents.delivery.resume import ResumePlan, fit_resume_layout, render_resume


pytestmark = pytest.mark.integration


def test_identity_and_education_are_built_from_actual_personal_records():
    profile = default_context().read_resume_profile()
    fields = confirmed_fields(profile)
    assert fields["name"] in profile["candidate"]
    assert fields["email"] in profile["candidate"]
    for item in fields["education"]:
        assert item["school"] in profile["candidate"]
        assert item["gpa"] in profile["candidate"]
        assert item["dates"] in profile["candidate"]
    assert fields["availability"]


@pytest.mark.parametrize(("source", "expected"), [
    ("航空航天工程/本科", "航空航天工程本科"),
    ("本科 / 航空航天工程", "航空航天工程本科"),
    (" 硕士在读 / 电子信息 ", "电子信息硕士在读"),
    ("电子信息／硕士在读", "电子信息硕士在读"),
    ("本科", "本科"),
    ("硕士在读", "硕士在读"),
    ("本科 / ", "本科"),
    ("", ""),
])
def test_education_labels_accept_optional_major_and_flexible_separators(source, expected):
    assert education_label(source) == expected


def test_current_education_exports_with_actual_resume(tmp_path: Path):
    source = REPO_ROOT / ".artifacts/resume-latency-20261031/live-replay/latency-baseline-20261031-171011-efac02/layout/round-1/font-9.5/resume.json"
    plan = ResumePlan.model_validate_json(source.read_text(encoding="utf-8"))
    current = ResumePlan.model_validate({**plan.model_dump(), **confirmed_fields(default_context().read_resume_profile())})
    result = render_resume(current, tmp_path / "current-education", {"browser_channel": "msedge"})
    assert result["checks"]["pages"] == 1
    assert result["checks"]["all_text"]


def test_stage_context_keeps_original_conditions_and_project_ownership():
    facts = source_facts(default_context().read_resume_profile())
    assert "rerank+contextual+hype" in facts["PAPER-02"]
    assert "246" in facts["PAPER-02"] and "0.663" in facts["PAPER-02"]
    assert "MIT" in facts["JOB-01"]
    assert "## TRIP-01" not in facts["PAPER-05"]


def test_actual_invalid_model_output_stops_before_file_delivery():
    directory = REPO_ROOT / ".artifacts/resume-speed-comparison-20261031/samples/acaea5439b835d4eb614afa7-1-optimized"
    trace_file = next(directory.glob("comparison-*.json"))
    recorded = json.loads(trace_file.read_text(encoding="utf-8"))
    actual_output = recorded["calls"][0]["response"]["content"]
    with pytest.raises(ValidationError):
        WriterDraft.model_validate_json(actual_output)
    assert not (directory / "package/简历.pdf").exists()


def test_actual_resume_uses_allowed_font_without_content_regeneration(tmp_path: Path):
    source = REPO_ROOT / ".artifacts/resume-latency-20261031/live-replay/latency-baseline-20261031-171011-efac02/layout/round-1/font-9.5/resume.json"
    plan = ResumePlan.model_validate_json(source.read_text(encoding="utf-8"))
    before = plan.model_dump_json()
    started = time.perf_counter()
    layout = fit_resume_layout(plan, tmp_path / "layout", "msedge")
    seconds = time.perf_counter() - started
    assert 95 <= layout["fill_percent"] <= 100, layout
    assert layout["min_font_pt"] >= 9 and not layout["horizontal_overflow"]
    assert 9 <= layout["body_font_pt"] < 9.5
    assert plan.model_dump_json() == before
    measured = json.loads((tmp_path / "layout/measurements.json").read_text(encoding="utf-8"))
    assert {9, 9.25} <= {item["body_font_pt"] for item in measured}
    assert len(list((tmp_path / "layout").rglob("简历.html"))) == 1
    (tmp_path / "verification.json").write_text(json.dumps({"layout": layout, "seconds": seconds}, ensure_ascii=False), encoding="utf-8")


def test_original_content_exports_as_one_a4_at_allowed_font(tmp_path: Path):
    source = REPO_ROOT / ".artifacts/resume-latency-20261031/live-replay/latency-baseline-20261031-171011-efac02/layout/round-1/font-9.5/resume.json"
    plan = ResumePlan.model_validate_json(source.read_text(encoding="utf-8"))
    result = render_resume(plan, tmp_path / "package", {"browser_channel": "msedge"}, body_font_pt=9.25)
    checks = result["checks"]
    assert checks["pages"] == 1 and checks["a4"] and checks["all_text"] and checks["links"] and checks["bounds"]
    assert checks["layout"]["fill_percent"] == 98.7
    assert checks["layout"]["min_font_pt"] >= 9
