import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from jobsearch_agents.actions.analyze import _job_files, _subtasks
from jobsearch_agents.actions.apply import _input_bundle
from jobsearch_agents.actions.common import ActionContext, MATERIALS_ROOT, REPO_ROOT, default_context
from jobsearch_agents.runtime import ToolRegistry
from jobsearch_agents.tools_wrap.file_tools import register_file_tools


def test_default_workspace_and_materials_are_separate_from_code():
    ctx = default_context()
    assert ctx.data_root == MATERIALS_ROOT
    assert ctx.profile_dir == MATERIALS_ROOT / "个人资料"
    assert ctx.evaluated_dir == MATERIALS_ROOT / "岗位记录" / "evaluated"
    assert REPO_ROOT not in ctx.data_root.parents


def test_environment_paths_resolve_in_fresh_process(tmp_path):
    env = dict(os.environ)
    env["JOBSEARCH_WORKSPACE_ROOT"] = str(tmp_path)
    env["JOBSEARCH_MATERIALS_ROOT"] = str(tmp_path / "材料")
    result = subprocess.run(
        [sys.executable, "-c", "from jobsearch_agents.actions.common import default_context; import json; c=default_context(); print(json.dumps([str(c.repo_root),str(c.data_root),str(c.profile_dir)]))"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout) == [str(tmp_path), str(tmp_path / "材料"), str(tmp_path / "材料" / "个人资料")]


def test_file_tools_read_and_write_real_project_content(tmp_path):
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    registry = ToolRegistry()
    register_file_tools(registry, tmp_path)
    registry.get("write_file").invoke({"path": "README.md", "content": content})
    assert registry.get("read_file").invoke({"path": "README.md"}) == content
    with pytest.raises(ValueError, match="路径越界"):
        registry.get("read_file").invoke({"path": "../README.md"})


def _real_context():
    ctx = default_context()
    if not ctx.profile_dir.is_dir() or not list(ctx.data_root.glob("*/岗位JD.md")):
        pytest.skip("当前环境没有用户的真实求职资料")
    ctx.read_profile()
    return ctx


def test_existing_jobs_are_discovered_without_identical_duplicates():
    ctx = _real_context()
    files = _job_files(ctx)
    assert files
    assert len({p.read_text(encoding="utf-8-sig").strip() for p in files}) == len(files)
    canonical = list(ctx.data_root.glob("*/岗位JD.md"))
    for path in canonical:
        assert path in files
    assert len({ctx.job_key(p) for p in files}) == len(files)


def test_same_jd_filenames_keep_distinct_evaluation_paths(tmp_path):
    original = _real_context()
    jobs = sorted(original.data_root.glob("*/岗位JD.md"))[:2]
    ctx = ActionContext(tmp_path, original.profile_dir, tmp_path / "材料")
    copies = []
    for source in jobs:
        target = ctx.data_root / source.parent.name / source.name
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        copies.append(target)
    assert len({ctx.evaluation_path(path) for path in copies}) == 2


def test_existing_evaluation_is_included_in_application_input():
    ctx = _real_context()
    jobs = _job_files(ctx)
    checked = 0
    for job in jobs:
        evaluation = ctx.evaluation_path(job)
        if evaluation.is_file():
            bundle = _input_bundle(ctx, job)
            assert evaluation.read_text(encoding="utf-8") in bundle
            checked += 1
    assert checked > 0


def test_analysis_tasks_point_to_materials_outputs():
    ctx = _real_context()
    jobs = _job_files(ctx)[:2]
    tasks = _subtasks(ctx, jobs)
    for job, task in zip(jobs, tasks):
        assert ctx.evaluation_path(job).relative_to(ctx.repo_root).as_posix() in task
        assert job.relative_to(ctx.repo_root).as_posix() in task


def test_cli_status_uses_configured_materials_and_utf8(tmp_path):
    original = _real_context()
    application = next(original.evaluated_dir.glob("*-application.md"))
    evaluated = tmp_path / "材料" / "岗位记录" / "evaluated"
    evaluated.mkdir(parents=True)
    shutil.copy2(application, evaluated / application.name)
    env = dict(os.environ)
    env["JOBSEARCH_WORKSPACE_ROOT"] = str(tmp_path)
    env["JOBSEARCH_MATERIALS_ROOT"] = str(tmp_path / "材料")
    env["PYTHONIOENCODING"] = "cp1252"
    status = subprocess.run(
        [sys.executable, "-m", "jobsearch_agents", "status"],
        cwd=REPO_ROOT, env=env, capture_output=True, check=True,
    )
    assert "状态表" in status.stdout.decode("utf-8")
    updated = subprocess.run(
        [sys.executable, "-m", "jobsearch_agents", "status-set", application.name.removesuffix("-application.md") + ".md", "已投递", "--applied"],
        cwd=REPO_ROOT, env=env, capture_output=True, check=True,
    )
    assert json.loads(updated.stdout.decode("utf-8"))["stage"] == "已投递"
    assert (evaluated / "delivery-status.csv").is_file()
