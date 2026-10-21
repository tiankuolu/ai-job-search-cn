# interview 动作：复用 apply 的生成-审查循环结构，换 interview prompt（GOAL.md §2.3）。

from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, EVALUATED_DIR, RUNS_DIR


def run_interview(
    client: LLMClient,
    ctx: ActionContext,
    job_file: Path,
    max_review_rounds: int = 2,
) -> dict:
    """面试准备：写手换成 interview prompt，审查沿用 reviewer 的结构检查。"""
    if not job_file.is_file():
        raise FileNotFoundError(f"岗位文件不存在：{job_file}")

    trace = Trace(RUNS_DIR, "interview")
    jd_text = job_file.read_text(encoding="utf-8")
    profile = ctx.read_profile()
    eval_path = EVALUATED_DIR / f"{job_file.stem}-evaluation.md"
    evaluation = (
        eval_path.read_text(encoding="utf-8")
        if eval_path.is_file()
        else "（没有已保存的评估报告）"
    )

    interviewer = Agent(
        name="interviewer",
        system_prompt=load_prompt("interview"),
        client=client,
        trace=trace,
    )
    draft = interviewer.run(
        f"# 岗位描述\n{jd_text}\n\n# 评估报告\n{evaluation}\n\n"
        f"# 候选人资料\n{profile['candidate']}\n\n# 事实证据\n{profile['evidence']}"
    )

    out_dir = ctx.repo_root / "markets" / "china" / "jobs" / "evaluated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_file.stem}-interview-prep.md"
    out_path.write_text(draft, encoding="utf-8")

    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "prep": draft,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
