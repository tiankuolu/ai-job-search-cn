# 命令行入口：python -m jobsearch_agents <action> [args]（GOAL.md §2.3）。

import argparse
import json
import sys
from pathlib import Path

from .actions import run_analyze, run_apply, run_interview, run_rank, run_setup
from .actions.interview import grade_practice, make_practice_sheet, run_storybank
from .actions.common import REPO_ROOT, default_context
from .actions.research import run_research
from .actions.nowcoder import run_nowcoder_sweep
from .actions.status import STAGES, STATUS_FILE, init_from_evaluated, render_table, set_stage
from .runtime import OpenAICompatClient
from .config import LLMConfig


def _client() -> OpenAICompatClient:
    return OpenAICompatClient(LLMConfig())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jobsearch_agents",
        description="中国大陆求职多 agent 系统的命令行入口",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=None,
        help="候选人资料目录（默认 documents/china/profile/，测试可指向 fixtures）",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("analyze", help="并行分析 inbox 下全部岗位")
    sub.add_parser("rank", help="汇总排序全部评估报告")

    p_apply = sub.add_parser("apply", help="为一个岗位生成申请材料（生成-审查循环）")
    p_apply.add_argument("job_file", type=Path)

    p_iv = sub.add_parser("interview", help="为一个岗位生成面试准备材料")
    p_iv.add_argument("job_file", type=Path)

    p_setup = sub.add_parser("setup", help="从简历文本初始化资料文件")
    p_setup.add_argument("resume_file", type=Path)

    sub.add_parser("status", help="查看/初始化投递状态表")
    p_set = sub.add_parser("status-set", help="更新某岗位的投递阶段")
    p_set.add_argument("job_file", type=str, help="岗位文件名或其前缀")
    p_set.add_argument("stage", type=str, choices=STAGES)
    p_set.add_argument("--note", type=str, default="")
    p_set.add_argument("--applied", action="store_true", help="同时记录今天为投递日期")

    p_research = sub.add_parser("research", help="公司调研（公开网页低频检索）")
    p_research.add_argument("job_file", type=Path)

    p_scrape = sub.add_parser("scrape", help="抓取牛客网实习 JD（公开 API，低频量）")
    p_scrape.add_argument("--keywords", type=str, default=None, help="逗号分隔标题关键词，默认按档案目标方向")
    p_scrape.add_argument("--max-companies", type=int, default=None, help="限制扫描公司数（测试用）")
    p_scrape.add_argument("--dry-run", action="store_true", help="只报告命中，不写 inbox")

    sub.add_parser("storybank", help="从档案生成面试故事库（已存在则拒绝）")
    p_practice = sub.add_parser("practice", help="生成面试练习卷")
    p_practice.add_argument("--job", type=Path, default=None, help="可选：目标岗位文件")
    p_grade = sub.add_parser("grade", help="给练习卷答案评分并记录")
    p_grade.add_argument("sheet", type=Path)
    p_grade.add_argument("answers", type=Path)

    args = parser.parse_args(argv)
    ctx = default_context(args.profile_dir)

    if args.action == "status":
        rows = init_from_evaluated(EVALUATED_DIR := REPO_ROOT / "markets" / "china" / "jobs" / "evaluated")
        print(render_table(rows))
        print(f"\n状态表：{EVALUATED_DIR / 'delivery-status.csv'}")
        return 0

    if args.action == "status-set":
        row = set_stage(args.job_file, args.stage, note=args.note, applied=args.applied)
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0

    if args.action == "research":
        job_file = Path(args.job_file)
        if not job_file.is_absolute():
            job_file = REPO_ROOT / job_file
        result = run_research(_client(), ctx, job_file)
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "scrape":
        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        result = run_nowcoder_sweep(
            REPO_ROOT / "markets" / "china" / "jobs" / "inbox",
            REPO_ROOT,
            keywords=keywords,
            max_companies=args.max_companies,
            dry_run=args.dry_run,
        )
        print(f"扫描公司 {result['companies_scanned']} 家；"
              f"保存 {result['saved_count']}、方向不符跳过 {result['skipped_direction_mismatch']}、"
              f"重复跳过 {result['skipped_duplicate']}、错误 {len(result['errors'])}")
        for item in result["saved"][:30]:
            marker = "[dry]" if item.get("dry_run") else "写入"
            print(f"  {marker} [{item['company']}] {item['title']}（关键词：{item['keyword']}）")
        if result["errors"]:
            print("错误样例：", result["errors"][:3])
        return 0

    if args.action == "storybank":
        result = run_storybank(_client())
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "practice":
        job = Path(args.job) if args.job else None
        if job is not None and not job.is_absolute():
            job = REPO_ROOT / job
        result = make_practice_sheet(_client(), job)
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "grade":
        sheet = Path(args.sheet)
        answers = Path(args.answers)
        if not sheet.is_absolute():
            sheet = REPO_ROOT / sheet
        if not answers.is_absolute():
            answers = REPO_ROOT / answers
        result = grade_practice(_client(), sheet, answers)
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "setup":
        client = OpenAICompatClient(LLMConfig())
        if not args.resume_file.is_file():
            raise SystemExit(f"简历文件不存在：{args.resume_file}")
        result = run_setup(
            client, ctx, args.resume_file.read_text(encoding="utf-8")
        )
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "analyze":
        client = OpenAICompatClient(LLMConfig())
        result = run_analyze(client, ctx)
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "rank":
        client = OpenAICompatClient(LLMConfig())
        result = run_rank(client, ctx)
        result.pop("trace_obj", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    job_file = Path(args.job_file)
    if not job_file.is_absolute():
        job_file = REPO_ROOT / job_file
    if args.action == "apply":
        client = OpenAICompatClient(LLMConfig())
        result = run_apply(client, ctx, job_file)
    else:
        client = OpenAICompatClient(LLMConfig())
        result = run_interview(client, ctx, job_file)
    result.pop("trace_obj", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
