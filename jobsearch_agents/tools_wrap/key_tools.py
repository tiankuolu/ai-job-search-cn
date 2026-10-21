# 岗位标识与评分工具：job_key 包 tools/job_key.py；评分合成按 analyze 工作流的六维度权重实现。
# tools/rank_state.py 的权重是四维度旧口径，与 markets/china/workflows/analyze-job.md 的
# 六维度权重不一致，这里以工作流口径为准，不包装旧实现。

import importlib.util
import sys
from pathlib import Path

from ..runtime.tools import Tool, ToolRegistry, infer_schema

DIMENSIONS = {
    "technical": 0.25,
    "experience": 0.25,
    "domain": 0.15,
    "communication": 0.10,
    "compensation_location": 0.10,
    "growth": 0.15,
}

BANDS = (
    (80, "Strong Fit"),
    (65, "Good Fit"),
    (50, "Moderate Fit"),
    (35, "Weak Fit"),
    (0, "Poor Fit"),
)


def overall_score(scores: dict) -> int:
    """六维度按工作流权重合成总分，输入不全或越界就地崩溃。"""
    total = 0.0
    for dim, weight in DIMENSIONS.items():
        value = scores.get(dim)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"维度 {dim} 缺失或不是数字")
        if not 0 <= value <= 100:
            raise ValueError(f"维度 {dim} 必须在 0 到 100 之间")
        total += float(value) * weight
    return int(total + 0.5)


def band(score: int) -> str:
    if not 0 <= score <= 100:
        raise ValueError(f"总分必须在 0 到 100 之间，收到 {score}")
    for floor, name in BANDS:
        if score >= floor:
            return name
    raise ValueError(f"无法判定的总分：{score}")


def _load_job_key(repo_root: Path):
    spec = importlib.util.spec_from_file_location(
        "job_key_tool", repo_root / "tools" / "job_key.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {repo_root / 'tools' / 'job_key.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["job_key_tool"] = module
    spec.loader.exec_module(module)
    return module


def register_key_tools(registry: ToolRegistry, repo_root: Path) -> None:
    job_key = _load_job_key(repo_root)

    registry.register(
        Tool(
            name="make_job_key",
            description="为公司名与岗位名称生成规范的去重标识 key（内容寻址）。",
            parameters=infer_schema(job_key.make_key),
            func=job_key.make_key,
        )
    )
    registry.register(
        Tool(
            name="overall_score",
            description=(
                "把六个维度的分数字典（technical/experience/domain/"
                "communication/compensation_location/growth，各 0-100）"
                "按工作流权重合成为总分。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    dim: {"type": "integer", "description": f"{dim} 维度得分 0-100"}
                    for dim in DIMENSIONS
                },
                "required": list(DIMENSIONS),
            },
            func=overall_score,
        )
    )
    registry.register(
        Tool(
            name="score_band",
            description="把 0-100 的总分映射为判定档位：Strong/Good/Moderate/Weak/Poor Fit。",
            parameters=infer_schema(band),
            func=band,
        )
    )
