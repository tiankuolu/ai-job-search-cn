# 把 tools/ 下现有确定性脚本包装成 agent 工具（GOAL.md §2.3）。

from pathlib import Path

from ..runtime.tools import ToolRegistry
from .file_tools import register_file_tools
from .key_tools import register_key_tools

ROOT = Path(__file__).resolve().parent.parent.parent


def build_default_tools() -> ToolRegistry:
    registry = ToolRegistry()
    register_key_tools(registry, ROOT)
    register_file_tools(registry, ROOT)
    return registry
