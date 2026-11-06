import json

import pytest

from jobsearch_agents.actions.analyze import _job_files
from jobsearch_agents.actions.apply import _input_bundle, parse_verdict, run_apply
from jobsearch_agents.actions.common import RUNS_DIR, default_context
from jobsearch_agents.config import LLMConfig
from jobsearch_agents.prompts import load_prompt
from jobsearch_agents.runtime import Agent, OpenAICompatClient
from jobsearch_agents.runtime.trace import Trace


pytestmark = pytest.mark.integration


@pytest.mark.parametrize("job_index", [0, 1])
def test_real_application_contains_reviewed_star_resume(workspace, job_index):
    client = OpenAICompatClient(LLMConfig().require())
    job = _job_files(workspace)[job_index]
    trace = Trace(RUNS_DIR, "star-application")
    try:
        result = run_apply(client, workspace, job, trace=trace)
    finally:
        trace.save()
    result["trace_obj"].assert_complete()
    assert result["passed_review"], result["rounds"]
    draft = result["final_draft"]
    projects = draft.split("## Resume Project Experience\n", 1)[1].split("\n## ", 1)[0]
    assert projects.strip()
    assert "轨道动力学" not in draft
    assert "10 份真实 JD" not in projects
    assert "10份真实JD" not in projects
    artifact = workspace.evaluated_dir / "star-validation.json"
    artifact.write_text(
        json.dumps({"job": str(job), "rounds": result["rounds"], "trace": result["trace"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_real_reviewer_requires_star_resume_in_existing_application():
    original = default_context()
    matches = [
        (job, original.evaluated_dir / f"{original.job_key(job)}-application.md")
        for job in _job_files(original)
    ]
    job, application = next(
        (job, path) for job, path in matches
        if path.is_file() and "## Resume Project Experience" not in path.read_text(encoding="utf-8")
    )
    client = OpenAICompatClient(LLMConfig().require())
    trace = Trace(RUNS_DIR, "star-review")
    reviewer = Agent("reviewer", load_prompt("reviewer"), client, trace=trace)
    review = reviewer.run(
        f"# 待审查的申请材料\n{application.read_text(encoding='utf-8')}\n\n"
        f"# 事实依据\n{_input_bundle(original, job)}"
    )
    trace.save()
    trace.assert_complete()
    verdict = parse_verdict(review)
    assert not verdict["pass"], review
    assert any(str(item).startswith("5") for item in verdict["violations"]), review
