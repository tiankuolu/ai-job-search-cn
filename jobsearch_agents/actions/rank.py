# rank 动作：读取当前岗位的评估报告，单个 agent 做全局排序。

from datetime import date
from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, RUNS_DIR
from .analyze import _job_files


def run_rank(client: LLMClient, ctx: ActionContext, trace: Trace | None = None) -> dict:
    """汇总 evaluated 下全部评估报告，产出排序报告文件。"""
    if not ctx.evaluated_dir.is_dir():
        raise FileNotFoundError(f"目录不存在：{ctx.evaluated_dir}")
    evaluations = sorted(
        ctx.evaluation_path(job) for job in _job_files(ctx)
        if ctx.evaluation_path(job).is_file()
    )
    if not evaluations:
        raise FileNotFoundError(f"{ctx.evaluated_dir} 下没有任何评估报告，请先运行 analyze")

    profile = ctx.read_profile()
    eval_texts = "\n\n---\n\n".join(
        f"# 评估报告：{p.name}\n{p.read_text(encoding='utf-8')}" for p in evaluations
    )

    trace = trace or Trace(RUNS_DIR, "rank")
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

    out_path = ctx.evaluated_dir / f"ranking-{date.today().isoformat()}.md"
    out_path.write_text(report, encoding="utf-8")

    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "job_count": len(evaluations),
        "report": report,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
