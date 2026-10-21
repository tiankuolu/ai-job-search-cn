# 动作共享的上下文组装与路径约定。

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_DIR = REPO_ROOT / "markets" / "china" / "jobs" / "inbox"
EVALUATED_DIR = REPO_ROOT / "markets" / "china" / "jobs" / "evaluated"
PROFILE_DIR = REPO_ROOT / "documents" / "china" / "profile"
RUNS_DIR = REPO_ROOT / "runs"


@dataclass
class ActionContext:
    """一次 action 运行的全部输入。profile_dir 可指向 fixtures 的虚拟资料目录。"""

    repo_root: Path
    profile_dir: Path

    def read_profile(self) -> dict[str, str]:
        """读取候选人资料三件套，缺文件就地崩溃。"""
        parts = {}
        for name in ("candidate.md", "preferences.md", "evidence.md"):
            path = self.profile_dir / name
            if not path.is_file():
                raise FileNotFoundError(
                    f"候选人资料缺失：{path}。请先完成资料初始化或指定 fixtures 目录。"
                )
            parts[name[:-3]] = path.read_text(encoding="utf-8")
        return parts


def default_context(profile_dir: Path | None = None) -> ActionContext:
    """真实运行用 documents/china/profile/；测试传入 fixtures 目录。"""
    return ActionContext(
        repo_root=REPO_ROOT,
        profile_dir=profile_dir or PROFILE_DIR,
    )
