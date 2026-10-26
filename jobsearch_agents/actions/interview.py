# 面试相关动作：run_interview（岗位面试准备材料，生成-审查式单轮）+ 面试的跨时间迭代
# （storybank 故事库 / practice 练习卷 / grade 评分记录）。产物保存到简历目录。

import re
from datetime import date
from pathlib import Path

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import PROFILE_DIR, MATERIALS_ROOT, EVALUATED_DIR, RUNS_DIR, default_context

INTERVIEW_DIR = MATERIALS_ROOT / "面试准备"
STORYBANK = INTERVIEW_DIR / "storybank.md"
PRACTICE_DIR = INTERVIEW_DIR / "practice"
PRACTICE_LOG = INTERVIEW_DIR / "practice-log.md"


def run_interview(
    client: LLMClient,
    ctx,
    job_file: Path,
    max_review_rounds: int = 2,
    trace: Trace | None = None,
) -> dict:
    """面试准备：写手换成 interview prompt，审查沿用 reviewer 的结构检查。"""
    if not job_file.is_file():
        raise FileNotFoundError(f"岗位文件不存在：{job_file}")

    trace = trace or Trace(RUNS_DIR, "interview")
    jd_text = job_file.read_text(encoding="utf-8")
    profile = ctx.read_profile()
    eval_path = ctx.evaluation_path(job_file)
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
        task_id=ctx.job_key(job_file),
    )
    draft = interviewer.run(
        f"# 岗位描述\n{jd_text}\n\n# 评估报告\n{evaluation}\n\n"
        f"# 候选人资料\n{profile['candidate']}\n\n# 事实证据\n{profile['evidence']}"
    )

    out_dir = ctx.evaluated_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ctx.job_key(job_file)}-interview-prep.md"
    out_path.write_text(draft, encoding="utf-8")

    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "prep": draft,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }

STORYBANK_PROMPT = (
    "你是面试教练。给你候选人的完整档案与证据库，产出 STAR 故事库：把候选人的每个项目、"
    "每段经历预写成可背诵的面试故事。规则：\n"
    "1. 每个故事按「情境 S / 任务 T / 动作 A（含取舍）/ 结果 R（量化数字）」四段。\n"
    "2. 缺口问题单独一节：每个硬性缺口给出被问到时的坦诚话术与学习计划表述。\n"
    "3. 只使用档案与证据库里的事实，禁止编造。\n"
    "4. 语言口语化，是「说出口的话」，书面腔直接扣分。\n"
    "5. 输出前写一行 <STORYBANK_OK> 作为完成标记。\n"
)


def run_storybank(client: LLMClient) -> dict:
    """从档案生成面试故事库。已存在则就地崩溃（先备份或删除）。"""
    if STORYBANK.exists():
        raise FileExistsError(f"故事库已存在：{STORYBANK}。确认覆盖请先手动删除。")
    profile = ""
    for name in ("candidate.md", "preferences.md", "evidence.md"):
        path = PROFILE_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"档案缺失：{path}")
        profile += f"\n## {name}\n{path.read_text(encoding='utf-8')}"

    trace = Trace(RUNS_DIR, "storybank")
    agent = Agent(name="storybank", system_prompt=STORYBANK_PROMPT, client=client, trace=trace)
    content = agent.run(f"# 候选人档案{profile}")
    if "<STORYBANK_OK>" not in content:
        raise ValueError("故事库生成未完成（缺少完成标记），请重试")
    content = content.replace("<STORYBANK_OK>", "").strip()

    INTERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    STORYBANK.write_text(content, encoding="utf-8")
    trace.save()
    return {"output_file": str(STORYBANK), "trace": str(trace.save())}


PRACTICE_PROMPT = (
    "你是面试官。给你一个岗位的评估与面试准备材料、候选人的故事库，出一套练习卷：\n"
    "1. 8-10 个问题：覆盖岗位核心技能追问、项目深挖、行为题、缺口质疑题。\n"
    "2. 每个问题附「强回答必须命中的要点」（rubric，3-5 条），面试官评分就看这些要点。\n"
    "3. 每个问题标注难度（基础/进阶/刁钻）。\n"
    "4. 只基于给定材料出题，禁止编造候选人经历。\n"
)


def make_practice_sheet(client: LLMClient, job_file: Path | None) -> dict:
    """生成练习卷。job_file 为 None 时出通用卷（基于故事库）。"""
    PRACTICE_DIR.mkdir(parents=True, exist_ok=True)
    storybank = (
        STORYBANK.read_text(encoding="utf-8")
        if STORYBANK.exists()
        else None
    )
    if storybank is None:
        raise FileNotFoundError(
            f"故事库不存在：{STORYBANK}。先运行 py -m jobsearch_agents storybank 生成。"
        )
    context = f"# 候选人故事库\n{storybank}"
    label = "通用"
    if job_file is not None:
        if not job_file.is_file():
            raise FileNotFoundError(f"岗位文件不存在：{job_file}")
        eval_path = (
            default_context().evaluation_path(job_file)
        )
        app_path = (
            EVALUATED_DIR / f"{default_context().job_key(job_file)}-application.md"
        )
        label = job_file.stem
        if app_path.is_file():
            context += f"\n\n# 目标岗位申请材料\n{app_path.read_text(encoding='utf-8')}"
        if eval_path.is_file():
            context += f"\n\n# 目标岗位评估\n{eval_path.read_text(encoding='utf-8')}"

    trace = Trace(RUNS_DIR, "practice")
    agent = Agent(name="interviewer", system_prompt=PRACTICE_PROMPT, client=client, trace=trace)
    sheet = agent.run(context)
    sheet_path = PRACTICE_DIR / f"练习卷-{label}-{date.today().isoformat()}.md"
    sheet_path.write_text(sheet, encoding="utf-8")
    trace.save()
    return {"output_file": str(sheet_path), "trace": str(trace.save())}


GRADE_PROMPT = (
    "你是面试评分官。给你练习卷（每题带评分要点 rubric）与候选人的答案，逐题评分并给总评：\n"
    "1. 每题按 rubric 命中率给 0-10 分，列出命中的要点与遗漏的要点。\n"
    "2. 总分 = 各题平均分（保留一位小数）。总评给出：最弱的两个点 + 下次练习建议。\n"
    "3. 答案里的事实性错误（编造、数字与故事库不符）单独列出，出现即总评上限 5 分。\n"
    "4. 输出开头一行 <GRADE_OK>\n"
)


def grade_practice(client: LLMClient, sheet_path: Path, answers_path: Path) -> dict:
    """给练习卷答案打分，追加练习记录。"""
    if not sheet_path.is_file():
        raise FileNotFoundError(f"练习卷不存在：{sheet_path}")
    if not answers_path.is_file():
        raise FileNotFoundError(f"答案文件不存在：{answers_path}")
    storybank = STORYBANK.read_text(encoding="utf-8") if STORYBANK.exists() else "（无故事库）"

    trace = Trace(RUNS_DIR, "grade")
    agent = Agent(name="grader", system_prompt=GRADE_PROMPT, client=client, trace=trace)
    result = agent.run(
        f"# 练习卷\n{sheet_path.read_text(encoding='utf-8')}\n\n"
        f"# 候选人答案\n{answers_path.read_text(encoding='utf-8')}\n\n"
        f"# 事实基准（故事库）\n{storybank}"
    )
    if "<GRADE_OK>" not in result:
        raise ValueError("评分输出未完成（缺少完成标记）")
    result = result.replace("<GRADE_OK>", "").strip()

    score_match = re.search(r"总分[：:]\s*([0-9.]+)", result)
    score = float(score_match.group(1)) if score_match else -1.0

    PRACTICE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PRACTICE_LOG.open("a", encoding="utf-8") as f:
        f.write(
            f"\n## {date.today().isoformat()} — {sheet_path.stem} — 总分 {score}\n\n{result}\n"
        )
    trace.save()
    return {"score": score, "output_file": str(PRACTICE_LOG), "grade": result}
