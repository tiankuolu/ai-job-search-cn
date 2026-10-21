# 命令行入口：python -m jobsearch_agents <action> [args]（GOAL.md §2.3）。

import argparse
import json
import sys
from pathlib import Path

from .actions import run_analyze, run_apply, run_interview, run_rank, run_setup
from .actions.common import REPO_ROOT, default_context
from .runtime import OpenAICompatClient
from .config import LLMConfig


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

    args = parser.parse_args(argv)
    ctx = default_context(args.profile_dir)

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
