import json

import pytest
from pydantic import ValidationError

from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.delivery.generation import initial_draft, source_facts, writer_draft_model
from jobsearch_agents.resume_sources import ResumePreferences


pytestmark = pytest.mark.integration


def recorded_writer(filename):
    trace = json.loads((RUNS_DIR / filename).read_text(encoding="utf-8"))
    return next(call["response"]["content"] for call in trace["calls"]
                if call["agent"] == "writer" and call.get("response") and "plan" in json.loads(call["response"]["content"]))


def test_actual_didi_project_ids_are_rejected_at_writer_ingestion():
    profile = default_context().read_resume_profile()
    preferences = ResumePreferences.model_validate_json(profile["resume_preferences"])
    response = recorded_writer("apply-20261101-221043-88bde8.json")
    identifiers = {identifier for claim in json.loads(response)["claims"] for identifier in claim["fact_ids"]}
    assert {"PAPER", "TRIP", "ECOM"}.issubset(identifiers)
    with pytest.raises(ValidationError, match="fact_ids"):
        initial_draft(response, preferences, profile)


def test_actual_didi_specific_fact_ids_remain_valid():
    profile = default_context().read_resume_profile()
    preferences = ResumePreferences.model_validate_json(profile["resume_preferences"])
    response = recorded_writer("apply-20261101-221045-79d3a0.json")
    draft = initial_draft(response, preferences, profile)
    assert draft.claims


def test_writer_schema_exposes_exact_current_fact_ids():
    facts = source_facts(default_context().read_resume_profile())
    schema = writer_draft_model(facts).model_json_schema()
    identifiers = schema["$defs"]["FactClaim"]["properties"]["fact_ids"]["items"]["enum"]
    assert set(identifiers) == set(facts) | {"PERSONAL"}
    assert not {"PAPER", "TRIP", "ECOM"} & set(identifiers)
