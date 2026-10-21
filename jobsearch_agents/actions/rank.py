# rank 动作：读取全部评估报告，单个 agent 做全局排序（GOAL.md §2.3）。

from datetime import date
from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, EVALUATED_DIR, RUNS_DIR


def run_rank(client: LLMClient, ctx: ActionContext) -> dict:
    """汇总 evaluated 下全部评估报告，产出排序报告文件。"""
    if not EVALUATED_DIR.is_dir():
        raise FileNotFoundError(f"目录不存在：{EVALUATED_DIR}")
    evaluations = sorted(
        p for p in EVALUATED_DIR.glob("*.md")
        if p.is_file() and not p.name.startswith("ranking-")
        and "application" not in p.name
    )
    if not evaluations:
        raise FileNotFoundError(f"{EVALUATED_DIR} 下没有任何评估报告，请先运行 analyze")

    profile = ctx.read_profile()
    eval_texts = "\n\n---\n\n".join(
        f"# 评估报告：{p.name}\n{p.read_text(encoding='utf-8')}" for p in evaluations
    )

    trace = Trace(RUNS_DIR, "rank")
    ranker = Agent(
        name="ranker",
        system_prompt=load_prompt("ranker"),
        client=client,
        trace=trace,
    )
    report = ranker.run(
        f"# 候选人偏好\n{profile['preferences']}\n\n"
        f"# 全部评估报告\n{eval_texts}"
    )

    out_path = EVALUATED_DIR / f"ranking-{date.today().isoformat()}.md"
    out_path.write_text(report, encoding="utf-8")

    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "job_count": len(evaluations),
        "report": report,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
