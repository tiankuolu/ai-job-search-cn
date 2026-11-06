# apply 动作：写手 agent 生成材料，审查 agent 逐条审查，不通过就带着意见重写。
# 应用动作本身在代码层循环（最多 max_review_rounds 轮），生成与审查各自是独立的 agent。

import re
from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, RUNS_DIR
from ..resume_sources import asu_guidance

VERDICT_RE = re.compile(r'VERDICT:\s*(\{.*\})', re.IGNORECASE)
DETAILS_RE = re.compile(r'##\s*审查意见\s*\n(.*)', re.DOTALL)
BULLET_RE = re.compile(r'^\s*[-*]\s+(.+)$')


def parse_review_details(review_text: str) -> list[str]:
    """取出审查意见里的逐条问题，供前端展示和定向修改使用。"""
    section = DETAILS_RE.search(review_text)
    if not section:
        return []
    details = []
    for line in section.group(1).splitlines():
        bullet = BULLET_RE.match(line)
        if bullet:
            details.append(bullet.group(1).strip())
    return details


def parse_verdict(review_text: str) -> dict:
    """解析审查 agent 输出的裁决行，解析失败就地崩溃。"""
    match = VERDICT_RE.search(review_text)
    if not match:
        raise ValueError(f"审查输出里没有 VERDICT 行：{review_text[:200]}")
    import json

    verdict = json.loads(match.group(1))
    if not isinstance(verdict.get("pass"), bool):
        raise ValueError(f"VERDICT 缺少 pass 布尔值：{verdict}")
    return verdict


def _input_bundle(ctx: ActionContext, job_file: Path) -> str:
    profile = ctx.read_resume_profile()
    out_path = ctx.evaluation_path(job_file)
    evaluation = (
        out_path.read_text(encoding="utf-8") if out_path.is_file() else "（没有已保存的评估报告）"
    )
    research_path = ctx.evaluated_dir / f"{ctx.job_key(job_file)}-research.md"
    research = (
        research_path.read_text(encoding="utf-8")
        if research_path.is_file()
        else "（没有公司调研简报；打招呼语中不得编造公司相关信息）"
    )
    return (
        f"# 岗位文件路径\n{job_file.relative_to(ctx.repo_root).as_posix()}\n\n"
        f"# 候选人资料\n## candidate.md\n{profile['candidate']}\n\n"
        f"## preferences.md\n{profile['preferences']}\n\n"
        f"## 项目事实档案\n{profile['project_facts']}\n\n"
        f"## 项目档案核对日期与版本\n{profile['project_index']}\n{profile['project_sources']}\n\n"
        f"# 已有评估报告\n{evaluation}\n\n"
        f"# 简历材料目录\n{ctx.data_root}\n\n"
        f"# 公司调研简报（打招呼语的针对性素材来源，未覆盖的信息禁止编造）\n{research}"
    )


def run_apply(
    client: LLMClient,
    ctx: ActionContext,
    job_file: Path,
    max_review_rounds: int = 3,
    trace: Trace | None = None,
    base_draft: str = "",
    revision: str = "",
    extra_rules: str = "",
    output_path: Path | None = None,
) -> dict:
    """生成-审查循环。返回最终材料、每轮审查裁决与 trace 路径。"""
    if not job_file.is_file():
        raise FileNotFoundError(f"岗位文件不存在：{job_file}")

    trace = trace or Trace(RUNS_DIR, "apply")
    _, skill_sources = asu_guidance(Path(__file__).resolve().parents[2])
    trace.emit("resume.skills", skills=["great-resume", "make-resume"], sources=skill_sources)
    jd_text = job_file.read_text(encoding="utf-8")
    bundle = _input_bundle(ctx, job_file)
    if extra_rules:
        bundle += f"\n\n# 工作区最新确认规则（与旧档案冲突时优先采用）\n{extra_rules}"

    writer = Agent(
        name="writer",
        system_prompt=load_prompt("writer"),
        client=client,
        trace=trace,
        task_id=ctx.job_key(job_file),
    )
    reviewer = Agent(
        name="reviewer",
        system_prompt=load_prompt("reviewer"),
        client=client,
        trace=trace,
        task_id=ctx.job_key(job_file),
    )

    if base_draft:
        draft = writer.run(
            f"# 岗位描述\n{jd_text}\n\n{bundle}\n\n"
            f"# 上一版材料\n{base_draft}\n\n"
            f"# 定向修改要求\n{revision}\n\n"
            "基于上一版材料做定向修改：只改与修改要求相关的段落，保留其余已验证事实、结构和措辞。输出完整材料。"
        )
    else:
        draft = writer.run(f"# 岗位描述\n{jd_text}\n\n{bundle}")
    rounds: list[dict] = []
    final_pass = False
    for round_no in range(1, max_review_rounds + 1):
        trace.emit("review.started", round=round_no, task_id=ctx.job_key(job_file))
        review = reviewer.run(
            f"# 事实依据\n{bundle}\n\n# 岗位描述\n{jd_text}\n\n# 待审查的申请材料\n{draft}"
        )
        verdict = parse_verdict(review)
        details = parse_review_details(review)
        trace.emit(
            "review.finished", round=round_no, task_id=ctx.job_key(job_file),
            **{"pass": verdict["pass"], "violations": verdict.get("violations", [])},
            details=details,
        )
        rounds.append(
            {
                "round": round_no,
                "pass": verdict["pass"],
                "violations": verdict.get("violations", []),
                "details": details,
                "review": review,
            }
        )
        if verdict["pass"]:
            final_pass = True
            break
        if round_no < max_review_rounds:
            draft = writer.run(
                f"# 岗位描述\n{jd_text}\n\n{bundle}\n\n"
                f"# 你的上一稿\n{draft}\n\n"
                f"# 审查意见（逐条修改后重新输出完整材料）\n{review}"
            )

    app_dir = output_path.parent if output_path is not None else ctx.evaluated_dir
    app_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_path if output_path is not None else app_dir / f"{ctx.job_key(job_file)}-application.md"
    out_path.write_text(draft, encoding="utf-8")

    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "passed_review": final_pass,
        "rounds": rounds,
        "final_draft": draft,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
