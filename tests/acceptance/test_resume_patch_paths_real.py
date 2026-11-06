import json
from pathlib import Path

import pytest

from jobsearch_agents.actions.common import REPO_ROOT, RUNS_DIR, ActionContext
from jobsearch_agents.delivery.generation import DraftPatch, ResumeDraft, WriterDraft, apply_draft_patch, draft_patch_schema, initial_draft
from jobsearch_agents.resume_sources import ResumePreferences


pytestmark = pytest.mark.integration


def test_actual_seven_skill_patch_has_no_count_ceiling():
    trace = json.loads((RUNS_DIR / "apply-20261101-185728-37bdf4.json").read_text(encoding="utf-8"))
    version = next(event["data"]["input_sha256"] for event in reversed(trace["events"]) if event["type"] == "resume.draft")
    draft = ResumeDraft.model_validate_json((RUNS_DIR / "delivery/generation-cache" / version / "draft.json").read_text(encoding="utf-8"))
    call = next(call for call in reversed(trace["calls"]) if call["agent"] == "writer")
    updated = apply_draft_patch(draft, DraftPatch.model_validate_json(call["response"]["content"]))
    assert len(updated.plan.skills) == 7
    for model in (WriterDraft, ResumeDraft):
        schema = model.model_json_schema()
        plan = schema["properties"]["plan"]["$ref"].rsplit("/", 1)[1]
        assert "maxItems" not in schema["$defs"][plan]["properties"]["skills"]


def test_actual_invalid_patch_is_outside_the_advertised_paths():
    directory = REPO_ROOT / ".artifacts/resume-speed-comparison-20261031/samples-low/acaea5439b835d4eb614afa7-1-optimized"
    trace = json.loads(next(directory.glob("comparison-*.json")).read_text(encoding="utf-8"))
    draft = ResumeDraft.model_validate_json((directory / trace["run_id"] / "generation/draft.json").read_text(encoding="utf-8"))
    schema = draft_patch_schema(draft)
    allowed = schema["$defs"]["ReplaceField"]["properties"]["path"]["enum"]
    assert "/claims/9/fact_ids" in allowed
    assert "/plan/claims/9/fact_ids" not in allowed
    with pytest.raises(ValueError):
        patch = DraftPatch.model_validate_json(trace["calls"][2]["response"]["content"])
        apply_draft_patch(draft, patch)


def test_actual_successful_patch_reconstructs_the_exported_resume():
    experiment = REPO_ROOT / ".artifacts/resume-speed-comparison-20261031"
    directory = experiment / "samples/acaea5439b835d4eb614afa7-2-optimized"
    trace = json.loads(next(directory.glob("comparison-*.json")).read_text(encoding="utf-8"))
    profile = ActionContext(Path(r"D:\work"), experiment / "profile").read_resume_profile()
    preferences = ResumePreferences.model_validate_json(profile["resume_preferences"])
    original = initial_draft(trace["calls"][0]["response"]["content"], preferences, profile, "Harness算法实习生")
    patch = DraftPatch.model_validate_json(trace["calls"][2]["response"]["content"])
    allowed = draft_patch_schema(original)["$defs"]["ReplaceField"]["properties"]["path"]["enum"]
    assert all(item.path in allowed for item in patch.changes)
    updated = apply_draft_patch(original, patch)
    exported = json.loads((directory / "package/resume.json").read_text(encoding="utf-8"))
    assert updated.plan.model_dump() == exported
