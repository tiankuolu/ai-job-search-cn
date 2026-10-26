from pathlib import Path
import shutil

import pytest

from jobsearch_agents.actions.common import ActionContext, default_context


@pytest.fixture
def workspace(tmp_path: Path) -> ActionContext:
    original = default_context()
    original.read_profile()
    jobs = sorted(original.data_root.glob("*/岗位JD.md"))[:2]
    if len(jobs) != 2:
        raise FileNotFoundError("真实集成验证需要至少两个完整岗位")
    materials = tmp_path / "材料"
    profile = materials / "个人资料"
    shutil.copytree(original.profile_dir, profile)
    for source in jobs:
        target = materials / source.parent.name / source.name
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
    return ActionContext(tmp_path, profile, materials)
