# 集成验收层共享设施：fixtures 数据准备与环境变量守卫。
# 这一层真实调用模型（GOAL.md §2.5），跑之前必须设置三个环境变量。

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FIXTURES = REPO / "jobsearch_agents" / "fixtures"


def llm_env_ready() -> bool:
    return all(
        os.environ.get(name)
        for name in ("JOBSEARCH_LLM_BASE_URL", "JOBSEARCH_LLM_MODEL", "JOBSEARCH_LLM_API_KEY")
    )


def pytest_collection_modifyitems(config, items):
    if llm_env_ready():
        return
    skip = pytest.mark.skip(reason="未设置 JOBSEARCH_LLM_* 环境变量，集成验收跳过")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """复制一份 fixtures 到临时目录并搭出仓库结构，动作跑在临时目录内。"""
    (tmp_path / "markets" / "china" / "jobs" / "inbox").mkdir(parents=True)
    (tmp_path / "markets" / "china" / "jobs" / "evaluated").mkdir(parents=True)
    shutil.copytree(FIXTURES / "jd", tmp_path / "markets" / "china" / "jobs" / "inbox",
                    dirs_exist_ok=True)
    shutil.copytree(FIXTURES / "profile", tmp_path / "profile", dirs_exist_ok=True)
    (tmp_path / "runs").mkdir()
    return tmp_path
