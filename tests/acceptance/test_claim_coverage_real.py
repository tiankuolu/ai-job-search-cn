import pytest

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.generation import ResumeDraft, source_facts, validate_draft


pytestmark = pytest.mark.integration


def actual_draft():
    path = RUNS_DIR / "delivery/generation-cache/56745616911d89a2fe8ed46b0c849eb2579cf6d0ef3f0e14b0b245407b3cb282/draft.json"
    return ResumeDraft.model_validate_json(path.read_text(encoding="utf-8"))


def check_draft(draft):
    profile = default_context().read_resume_profile()
    return validate_draft(draft, profile, "AI Agent 研发实习生", source_facts(profile))


def test_actual_complete_draft_allows_intention_evidence():
    draft = actual_draft()
    assert any(claim.path == "/plan/intention" for claim in draft.claims)
    check_draft(draft)


def test_actual_complete_draft_allows_positioning_evidence():
    path = RUNS_DIR / "delivery/generation-cache/fc9796465a9b83fe6deb0bef69c55f5422239d93f22916ed4936757fbfef572d/draft.json"
    draft = ResumeDraft.model_validate_json(path.read_text(encoding="utf-8"))
    assert any(claim.path == "/positioning" for claim in draft.claims)
    check_draft(draft)


def test_actual_draft_still_requires_every_content_claim():
    draft = actual_draft()
    draft.claims = [claim for claim in draft.claims if claim.path != "/plan/greeting"]
    with pytest.raises(ValueError, match="事实"):
        check_draft(draft)


def test_actual_draft_rejects_duplicate_claim_paths():
    draft = actual_draft()
    draft.claims.append(draft.claims[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="事实"):
        check_draft(draft)


def test_actual_draft_rejects_unrelated_claim_paths():
    draft = actual_draft()
    claim = draft.claims[0].model_copy(deep=True)
    claim.path = "/plan/undefined"
    draft.claims.append(claim)
    with pytest.raises(ValueError, match="事实"):
        check_draft(draft)
