# 动作编排入口：analyze 并行扇出 / apply 生成-审查循环 / rank 汇总排序（GOAL.md §2.3）。

from .analyze import run_analyze
from .apply import run_apply
from .rank import run_rank
from .interview import run_interview
from .setup import run_setup

__all__ = ["run_analyze", "run_apply", "run_rank", "run_interview", "run_setup"]
