import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobsearch_agents.actions.analyze import _job_files
from jobsearch_agents.actions.common import ActionContext, RUNS_DIR, default_context
from jobsearch_agents.web import TERMINAL, RunStore, create_app
from jobsearch_agents.config import LLMConfig
from jobsearch_agents.runtime import Agent, OpenAICompatClient


@pytest.fixture
def real_workspace(tmp_path: Path):
    original = default_context()
    original.read_profile()
    materials = tmp_path / "材料"
    profile = materials / "个人资料"
    shutil.copytree(original.profile_dir, profile)
    sources = sorted(original.data_root.glob("*/岗位JD.md"))[:2]
    assert len(sources) == 2
    for source in sources:
        target = materials / source.parent.name / source.name
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
    return ActionContext(tmp_path, profile, materials)


def test_web_reads_real_jobs_and_saved_history(real_workspace, tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    source = next(path for path in RUNS_DIR.glob("*.json") if isinstance(data := json.loads(path.read_text(encoding="utf-8")), dict) and isinstance(data.get("calls"), list) and data.get("calls"))
    shutil.copy2(source, runs / source.name)
    with TestClient(create_app(real_workspace, runs)) as client:
        jobs = client.get("/api/jobs").json()
        assert len(jobs) == 2
        detail = client.get(f"/api/jobs/{jobs[0]['id']}").json()
        assert detail["content"] == _job_files(real_workspace)[0].read_text(encoding="utf-8-sig")
        history = client.get("/api/runs").json()
        assert history[0]["source"] == "legacy"
        saved = client.get(f"/api/runs/{source.stem}").json()
        assert saved["trace"]["calls"] == json.loads(source.read_text(encoding="utf-8"))["calls"]
        assert client.get("/api/meta").json()["workspace"] == str(real_workspace.data_root)
        assert client.get("/").status_code == 200


def test_web_rejects_invalid_requests_before_execution(real_workspace, tmp_path):
    with TestClient(create_app(real_workspace, tmp_path / "runs")) as client:
        jobs = client.get("/api/jobs").json()
        first = jobs[0]["id"]
        assert client.post("/api/runs", json={"action": "apply", "job_ids": []}).status_code == 422
        assert client.post("/api/runs", json={"action": "analyze", "job_ids": [first, first]}).status_code == 422
        assert client.post("/api/runs", json={"action": "analyze", "job_ids": ["unknown"]}).status_code == 404
        assert client.post("/api/runs", json={"action": "analyze", "job_ids": [first], "max_workers": 0}).status_code == 422
        assert client.post("/api/runs", json={"action": "rank"}, headers={"Origin": "https://example.com"}).status_code == 403
        assert client.get("/api/runs/not_found").status_code == 404
        assert client.get("/api/jobs/not_found").status_code == 404
        assert client.get("/api/meta", headers={"Host": "example.com"}).status_code == 400
        assert client.get("/api/runs").json() == []


@pytest.mark.integration
def test_real_runtime_rejects_missing_tools():
    agent = Agent(name="tool-validation", system_prompt="验证工具调用", client=OpenAICompatClient(LLMConfig()))
    with pytest.raises(KeyError, match="未注册的工具"):
        agent._execute_tool_call({"id": "invalid-tool-request", "function": {"name": "missing_tool", "arguments": "{}"}})
    with pytest.raises(ValueError, match="function.name"):
        agent._execute_tool_call({"id": "invalid-function-request"})


@pytest.mark.integration
def test_real_model_web_workflow_and_event_replay(real_workspace, tmp_path):
    runs = tmp_path / "runs"
    completed = []
    with TestClient(create_app(real_workspace, runs)) as client:
        jobs = client.get("/api/jobs").json()
        for action, selected in (("analyze", [job["id"] for job in jobs]), ("apply", [jobs[0]["id"]]), ("rank", []), ("interview", [jobs[0]["id"]])):
            response = client.post("/api/runs", json={"action": action, "job_ids": selected, "max_workers": 2})
            assert response.status_code == 202, response.text
            run_id = response.json()["run_id"]
            deadline = time.monotonic() + 900
            duplicate = client.post("/api/runs", json={"action": "analyze", "job_ids": [jobs[0]["id"]]})
            assert duplicate.status_code == 409
            while time.monotonic() < deadline:
                detail = client.get(f"/api/runs/{run_id}").json()
                if detail["status"] in TERMINAL:
                    break
                time.sleep(0.5)
            assert detail["status"] in {"completed", "review_required"}, detail.get("error")
            assert detail["artifacts"]
            assert detail["trace"]["calls"]
            assert detail["trace"]["total_tokens"] > 0
            assert all(call["execution_id"] for call in detail["trace"]["calls"])
            events = detail["trace"]["events"]
            assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
            assert events[-1]["type"] in {"run.completed", "run.review_required"}
            assert any(event["type"] == "llm.started" for event in events)
            assert any(event["type"] == "agent.finished" for event in events)
            if action == "analyze":
                assert len({event["data"]["task_id"] for event in events if event["type"] == "agent.started"}) == 2
                assert any(event["type"] == "tool.finished" for event in events)
                first_call = detail["trace"]["calls"][0]
                assert len(first_call["messages"]) == 2
            if action == "apply":
                assert any(event["type"] == "review.finished" for event in events)
                assert detail["result"]["rounds"]
            stream = client.get(f"/api/runs/{run_id}/events?after={len(events) - 2}").text
            assert stream.count("\ndata: ") == 3
            assert "event: end" in stream
            reconnect = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(len(events) - 1)}).text
            assert reconnect.count("\ndata: ") == 2
            completed.append({"run_id": run_id, "action": action, "status": detail["status"], "events": len(events), "calls": len(detail["trace"]["calls"]), "tokens": detail["trace"]["total_tokens"]})
        print(json.dumps(completed, ensure_ascii=False))
    reloaded = RunStore(runs, real_workspace)
    assert len(reloaded.list_runs()) == 4
    for record in completed:
        detail = reloaded.detail(record["run_id"])
        assert len(detail["trace"]["events"]) == record["events"]
        assert detail["artifacts"]
    reloaded.executor.shutdown(wait=True)
