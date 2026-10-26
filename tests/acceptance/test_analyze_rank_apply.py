import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jobsearch_agents.actions.analyze import _job_files, run_analyze
from jobsearch_agents.actions.apply import run_apply
from jobsearch_agents.actions.interview import run_interview
from jobsearch_agents.actions.rank import run_rank
from jobsearch_agents.actions.status import init_from_evaluated, set_stage
from jobsearch_agents.actions.setup import run_setup
from jobsearch_agents.config import LLMConfig
from jobsearch_agents.runtime import OpenAICompatClient

pytestmark = pytest.mark.integration


def test_real_jobs_complete_pipeline_in_external_materials(workspace):
    client = OpenAICompatClient(LLMConfig().require())
    with pytest.raises(FileExistsError, match="个人资料已存在"):
        run_setup(client, workspace, workspace.read_profile()["candidate"])
    jobs = _job_files(workspace)
    assert len(jobs) == 2
    analysis = run_analyze(client, workspace, max_workers=2)
    assert len(analysis["jobs"]) == 2
    for job in jobs:
        text = workspace.evaluation_path(job).read_text(encoding="utf-8")
        assert f"**Date:** {datetime.now(timezone(timedelta(hours=8))).date().isoformat()}" in text
        for section in ("## Job Facts", "## Scorecard", "## Strengths", "## Gaps", "## Assumptions / Missing Info"):
            assert section in text
    ranking = run_rank(client, workspace)
    assert ranking["job_count"] == 2
    assert (workspace.repo_root / ranking["output_file"]).is_file()
    application = run_apply(client, workspace, jobs[0])
    assert application["passed_review"], application["rounds"]
    application_path = workspace.repo_root / application["output_file"]
    assert application_path.parent == workspace.evaluated_dir
    assert "## BOSS Greeting" in application_path.read_text(encoding="utf-8")
    interview = run_interview(client, workspace, jobs[0])
    assert (workspace.repo_root / interview["output_file"]).parent == workspace.evaluated_dir
    status = workspace.evaluated_dir / "delivery-status.csv"
    rows = init_from_evaluated(workspace.evaluated_dir, status)
    assert len(rows) == 1
    updated = set_stage(rows[0]["job_file"], "已投递", status_path=status, applied=True)
    assert updated["applied_date"]
    assert updated["stage"] == "已投递"
    for result in (analysis, ranking, application, interview):
        result["trace_obj"].assert_complete()
        payload = json.loads(Path(result["trace"]).read_text(encoding="utf-8"))
        assert payload["calls"]
        assert all(call["model"] == client.model for call in payload["calls"])
        assert all(call["prompt_tokens"] + call["completion_tokens"] > 0 for call in payload["calls"])
    assert not (workspace.repo_root / "markets").exists()
