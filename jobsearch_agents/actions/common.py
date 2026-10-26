# 动作共享的上下文组装与路径约定。

from dataclasses import dataclass
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = Path(os.environ.get("JOBSEARCH_WORKSPACE_ROOT", REPO_ROOT.parents[2])).resolve()
MATERIALS_ROOT = Path(os.environ.get("JOBSEARCH_MATERIALS_ROOT", WORKSPACE_ROOT / "卢天阔_AI-Agent简历")).resolve()
INBOX_DIR = MATERIALS_ROOT / "岗位记录" / "inbox"
EVALUATED_DIR = MATERIALS_ROOT / "岗位记录" / "evaluated"
PROFILE_DIR = MATERIALS_ROOT / "个人资料"
RUNS_DIR = REPO_ROOT / "runs"


@dataclass
class ActionContext:
    """一次动作的工作区、材料目录与候选人资料。"""

    repo_root: Path
    profile_dir: Path
    materials_root: Path | None = None

    @property
    def data_root(self) -> Path:
        return self.materials_root if self.materials_root is not None else self.repo_root

    @property
    def inbox_dir(self) -> Path:
        return self.data_root / "岗位记录" / "inbox"

    @property
    def evaluated_dir(self) -> Path:
        return self.data_root / "岗位记录" / "evaluated"

    def job_key(self, job_file: Path) -> str:
        return job_file.parent.name if job_file.name == "岗位JD.md" else job_file.stem

    def evaluation_path(self, job_file: Path) -> Path:
        return self.evaluated_dir / f"{self.job_key(job_file)}.md"

    def read_profile(self) -> dict[str, str]:
        """读取候选人资料三件套，缺文件就地崩溃。"""
        parts = {}
        for name in ("candidate.md", "preferences.md", "evidence.md"):
            path = self.profile_dir / name
            if not path.is_file():
                raise FileNotFoundError(
                    f"候选人资料缺失：{path}。请先完成资料初始化或指定个人资料目录。"
                )
            parts[name[:-3]] = path.read_text(encoding="utf-8")
        return parts


def default_context(profile_dir: Path | None = None) -> ActionContext:
    """从工作区读取资料，个人材料集中保存在简历目录。"""
    profile = profile_dir or PROFILE_DIR
    if not profile.is_absolute():
        profile = WORKSPACE_ROOT / profile
    return ActionContext(
        repo_root=WORKSPACE_ROOT,
        profile_dir=profile.resolve(),
        materials_root=MATERIALS_ROOT,
    )
