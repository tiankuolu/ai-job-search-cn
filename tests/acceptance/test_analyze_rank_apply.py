# 验收 A3-A6：analyze 产物完整、红旗检出、rank 排序正确、apply 产物完整无编造。
# 全部挂 integration 标记：真实模型调用，未配环境变量时在 conftest 里统一跳过。

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.config import LLMConfig  # noqa: E402
from jobsearch_agents.runtime import OpenAICompatClient  # noqa: E402
from jobsearch_agents.actions.analyze import run_analyze as _analyze  # noqa: E402
from jobsearch_agents.actions.rank import run_rank as _rank  # noqa: E402
from jobsearch_agents.actions.apply import run_apply as _apply  # noqa: E402
from jobsearch_agents.actions.common import ActionContext  # noqa: E402

pytestmark = pytest.mark.integration

REQUIRED_EVALUATION_SECTIONS = [
    "## Job Facts",
    "## Scorecard",
    "## Strengths",
    "## Gaps",
    "## Red Flags",
    "## China-Market Checks",
    "## Recommended Next Action",
    "## Assumptions / Missing Info",
]

REQUIRED_APPLICATION_SECTIONS = [
    "## Supported Positioning",
    "## BOSS Greeting",
    "## Recruiter Message",
    "## Chinese Cover Letter / Email",
    "## Resume Tailoring Suggestions",
    "## Interview Focus",
    "## Gaps To Keep Honest",
    "## User Confirmation Needed",
]


def _evaluations_dir(workspace: Path) -> Path:
    return workspace / "markets" / "china" / "jobs" / "evaluated"


def _run_analyze_in(workspace: Path):
    """在隔离工作区里执行 analyze（动作模块的常量目录指向真实仓库，这里重定向）。"""
    import jobsearch_agents.actions.analyze as analyze_mod

    ctx = ActionContext(repo_root=workspace, profile_dir=workspace / "profile")
    original_inbox = analyze_mod.INBOX_DIR
    original_evaluated = analyze_mod.EVALUATED_DIR
    original_runs = analyze_mod.RUNS_DIR
    analyze_mod.INBOX_DIR = workspace / "markets" / "china" / "jobs" / "inbox"
    analyze_mod.EVALUATED_DIR = _evaluations_dir(workspace)
    analyze_mod.RUNS_DIR = workspace / "runs"
    try:
        return _analyze(OpenAICompatClient(LLMConfig()), ctx, max_workers=4)
    finally:
        analyze_mod.INBOX_DIR = original_inbox
        analyze_mod.EVALUATED_DIR = original_evaluated
        analyze_mod.RUNS_DIR = original_runs


class TestAnalyze:
    def test_a3_analyze_produces_complete_evaluations(self, workspace):
        result = _run_analyze_in(workspace)
        errors = [j for j in result["jobs"] if j["status"] != "done"]
        assert not errors, f"有岗位分析失败：{errors}"
        evaluated = sorted(_evaluations_dir(workspace).glob("*.md"))
        assert len(evaluated) == 10, f"期望 10 份评估，实际 {len(evaluated)}"
        for path in evaluated:
            text = path.read_text(encoding="utf-8")
            missing = [s for s in REQUIRED_EVALUATION_SECTIONS if s not in text]
            assert not missing, f"{path.name} 缺少章节：{missing}"

    def test_a4_red_flag_jobs_flagged(self, workspace):
        _run_analyze_in(workspace)
        checked = 0
        for name in ("dawning-996-startup.md", "goldenhand-outsourcing.md"):
            path = _evaluations_dir(workspace) / name
            text = path.read_text(encoding="utf-8")
            red_flag_section = text.split("## Red Flags", 1)[1].split("##", 1)[0]
            assert "无" not in red_flag_section[:20], f"{name} 未检出红旗"
            checked += 1
        assert checked == 2


class TestRank:
    def test_a5_high_match_group_ranks_above_moderate(self, workspace):
        _run_analyze_in(workspace)
        import jobsearch_agents.actions.rank as rank_mod

        ctx = ActionContext(repo_root=workspace, profile_dir=workspace / "profile")
        original = rank_mod.EVALUATED_DIR, rank_mod.RUNS_DIR
        rank_mod.EVALUATED_DIR = _evaluations_dir(workspace)
        rank_mod.RUNS_DIR = workspace / "runs"
        try:
            result = _rank(OpenAICompatClient(LLMConfig()), ctx)
        finally:
            rank_mod.EVALUATED_DIR, rank_mod.RUNS_DIR = original

        report = result["report"]
        high_names = ["星野", "深桥", "诺瓦"]
        moderate_names = ["晶湖", "量子叶", "睿城云"]
        positions = {name: report.find(name) for name in high_names + moderate_names}
        for name in high_names:
            assert positions[name] != -1, f"排序报告里没找到 {name}"
        # 高匹配组的每个位置都应整体高于中等组（值更小）
        worst_high = max(positions[n] for n in high_names if positions[n] != -1)
        for name in moderate_names:
            if positions[name] != -1:
                assert positions[name] > worst_high, (
                    f"中等匹配 {name} 排到了高匹配组前面"
                )


class TestApply:
    def test_a6_application_complete_and_honest(self, workspace):
        _run_analyze_in(workspace)
        import jobsearch_agents.actions.apply as apply_mod

        ctx = ActionContext(repo_root=workspace, profile_dir=workspace / "profile")
        jd = workspace / "markets" / "china" / "jobs" / "inbox" / "starfield-research-python-agent-dev.md"
        original = apply_mod.EVALUATED_DIR, apply_mod.RUNS_DIR
        apply_mod.EVALUATED_DIR = _evaluations_dir(workspace)
        apply_mod.RUNS_DIR = workspace / "runs"
        try:
            result = _apply(OpenAICompatClient(LLMConfig()), ctx, jd)
        finally:
            apply_mod.EVALUATED_DIR, apply_mod.RUNS_DIR = original

        draft = result["final_draft"]
        missing = [s for s in REQUIRED_APPLICATION_SECTIONS if s not in draft]
        assert not missing, f"申请材料缺少章节：{missing}"
        # 事实红线：证据库里「明确不具备」的内容禁止出现
        for banned in ("Kubernetes", "RabbitMQ", "Kafka", "React"):
            assert banned not in draft, f"申请材料里出现了候选人不具备的 {banned}"
        assert "微服务运维" not in draft
