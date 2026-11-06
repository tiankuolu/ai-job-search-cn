import json

import pytest
from pydantic import ValidationError

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.generation import ContentReview, ResumeDraft, content_review_prompt, content_review_schema, source_facts, validate_content_review, validate_draft


pytestmark = pytest.mark.integration


def recorded_draft():
    trace = json.loads((RUNS_DIR / "apply-20261101-174601-10b41e.json").read_text(encoding="utf-8"))
    version = next(event["data"]["input_sha256"] for event in reversed(trace["events"]) if event["type"] == "resume.draft")
    return ResumeDraft.model_validate_json((RUNS_DIR / "delivery/generation-cache" / version / "draft.json").read_text(encoding="utf-8"))


def test_actual_review_ignores_extra_positioning_and_requires_verdict_fields():
    trace = json.loads((RUNS_DIR / "apply-20261101-183014-35b2c7.json").read_text(encoding="utf-8"))
    response = next(json.loads(call["response"]["content"]) for call in reversed(trace["calls"])
                    if call["agent"] == "reviewer" and "positioning" in json.loads(call["response"]["content"]))
    review = ContentReview.model_validate(response)
    assert "positioning" not in review.model_dump()
    assert review.passed == response["passed"]
    assert review.checked_fact_ids == response["checked_fact_ids"]
    incomplete = dict(response)
    del incomplete["passed"]
    with pytest.raises(ValidationError, match="passed"):
        ContentReview.model_validate(incomplete)


def test_actual_education_review_is_not_a_model_edit():
    trace = json.loads((RUNS_DIR / "apply-20261101-174601-10b41e.json").read_text(encoding="utf-8"))
    review = next(call for call in reversed(trace["calls"]) if call["agent"] == "reviewer")
    with pytest.raises(ValidationError):
        ContentReview.model_validate_json(review["response"]["content"])


def test_review_schema_only_includes_current_editable_content():
    draft = recorded_draft()
    paths = content_review_schema(draft.model_dump())["$defs"]["ReviewIssue"]["properties"]["path"]["enum"]
    assert "/plan/projects/0/bullets/0" in paths
    assert "/plan/greeting" in paths
    assert "/claims/0/fact_ids" in paths
    assert not any(path.startswith(("/plan/education", "/plan/name", "/plan/awards")) for path in paths)
    assert "/plan" not in paths


def test_current_education_is_explicit_in_review_input():
    profile = default_context().read_resume_profile()
    prompt = content_review_prompt(profile, {}, "", recorded_draft().model_dump(), "")
    inputs, _ = json.JSONDecoder().raw_decode(prompt)
    assert inputs["confirmed_personal_information"]["education"][0]["degree"] == "电子信息硕士在读"


def test_personal_fact_is_supplied_with_explicit_required_coverage():
    profile = default_context().read_resume_profile()
    draft = recorded_draft()
    inputs, _ = json.JSONDecoder().raw_decode(content_review_prompt(profile, {}, "", draft.model_dump(), ""))
    assert profile["candidate"] in inputs["facts"]["PERSONAL"]
    assert profile["preferences"] in inputs["facts"]["PERSONAL"]
    required = {identifier for claim in draft.claims for identifier in claim.fact_ids}
    assert set(inputs["required_fact_ids"]) == required
    coverage = content_review_schema(draft.model_dump())["properties"]["checked_fact_ids"]
    assert "PERSONAL" in coverage["items"]["enum"]
    assert coverage["minItems"] == len(required) and coverage["uniqueItems"]


def test_actual_missing_personal_review_reports_the_specific_identifier():
    trace = json.loads((RUNS_DIR / "apply-20261101-175727-89de24.json").read_text(encoding="utf-8"))
    version = next(event["data"]["input_sha256"] for event in reversed(trace["events"]) if event["type"] == "resume.draft")
    draft = ResumeDraft.model_validate_json((RUNS_DIR / "delivery/generation-cache" / version / "draft.json").read_text(encoding="utf-8"))
    recorded = next(call for call in reversed(trace["calls"]) if call["agent"] == "reviewer")
    review = ContentReview.model_validate_json(recorded["response"]["content"])
    with pytest.raises(ValueError, match="独立审查遗漏事实编号：PERSONAL"):
        validate_content_review(review, draft)


def test_program_checks_fixed_fields_before_model_review():
    profile = default_context().read_resume_profile()
    draft = recorded_draft()
    assert not validate_draft(draft, profile, "", source_facts(profile))
    old = draft.model_copy(deep=True)
    old.plan.education[0].degree += "（修改）"
    with pytest.raises(ValueError, match="程序固定字段与当前个人资料不一致：education"):
        validate_draft(old, profile, "", source_facts(profile))
