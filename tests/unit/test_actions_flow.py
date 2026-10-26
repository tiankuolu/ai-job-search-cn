"""apply 生成-审查循环与 analyze 子任务派发的控制流验证（验收 A1 的一部分）。

动作的文件路径绑定真实仓库目录，因此这里只测纯逻辑部分：
VERDICT 解析、生成-审查的循环计数、失败重写路径。涉及仓库目录写入的
集成验证放进 tests/acceptance/。
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.actions.apply import parse_verdict  # noqa: E402


class TestVerdictParsing(unittest.TestCase):
    def test_pass_verdict(self):
        text = 'VERDICT: {"pass": true, "violations": []}\n\n## 审查意见\n全部通过'
        verdict = parse_verdict(text)
        self.assertTrue(verdict["pass"])
        self.assertEqual(verdict["violations"], [])

    def test_fail_verdict_with_violations(self):
        text = (
            'VERDICT: {"pass": false, "violations": [2, 3]}\n\n'
            "## 审查意见\n- 第 2 条：编造年限"
        )
        verdict = parse_verdict(text)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["violations"], [2, 3])

    def test_missing_verdict_raises(self):
        with self.assertRaises(ValueError):
            parse_verdict("没有裁决行的审查输出")

    def test_malformed_json_raises(self):
        with self.assertRaises(Exception):
            parse_verdict('VERDICT: {"pass": yes}')

    def test_verdict_case_insensitive(self):
        verdict = parse_verdict('verdict: {"pass": true}')
        self.assertTrue(verdict["pass"])


class TestApplyRoundFlow(unittest.TestCase):
    """用假模型驱动 run_apply 的循环结构（写入临时目录）。"""

    def _run_with_scripts(self, writer_outputs, reviewer_outputs, max_rounds=3, tmp=None):
        import tempfile

        from jobsearch_agents.actions.apply import run_apply
        from jobsearch_agents.actions.common import ActionContext
        from jobsearch_agents.prompts import load_prompt
        from jobsearch_agents.runtime import Agent
        from .fakes import ScriptedLLMClient, make_text_response

        writer = Agent(
            name="writer",
            system_prompt=load_prompt("writer"),
            client=ScriptedLLMClient([make_text_response(t) for t in writer_outputs]),
        )
        reviewer = Agent(
            name="reviewer",
            system_prompt=load_prompt("reviewer"),
            client=ScriptedLLMClient(
                [make_text_response(t) for t in reviewer_outputs]
            ),
        )

        owns_tmp = tmp is None
        tmp_ctx = tempfile.TemporaryDirectory() if owns_tmp else None
        tmp_path = Path(tmp) if tmp else Path(tmp_ctx.__enter__())
        try:
            # 在临时目录里搭出仓库结构与资料
            (tmp_path / "岗位记录" / "inbox").mkdir(parents=True, exist_ok=True)
            (tmp_path / "岗位记录" / "evaluated").mkdir(parents=True, exist_ok=True)
            profile_dir = tmp_path / "profile"
            profile_dir.mkdir(exist_ok=True)
            for name in ("candidate.md", "preferences.md", "evidence.md"):
                (profile_dir / name).write_text(f"# {name}\n虚构资料", encoding="utf-8")
            jd = tmp_path / "岗位记录" / "inbox" / "acme-dev.md"
            jd.write_text("# 岗位 @ 公司\n\n职责与要求", encoding="utf-8")

            ctx = ActionContext(repo_root=tmp_path, profile_dir=profile_dir)

            # 替换 run_apply 内部的 agent 构造：直接调用内部逻辑
            import jobsearch_agents.actions.apply as apply_mod

            original_agent = apply_mod.Agent
            agents = {"writer": writer, "reviewer": reviewer}

            def fake_agent(name, system_prompt, client, **kwargs):
                return agents[name]

            apply_mod.Agent = fake_agent
            original_trace = apply_mod.Trace
            apply_mod.Trace = lambda run_dir, action: original_trace(
                tmp_path / "runs", action
            )
            try:
                return run_apply(
                    writer.client, ctx, jd, max_review_rounds=max_rounds
                )
            finally:
                apply_mod.Agent = original_agent
                apply_mod.Trace = original_trace
        finally:
            if owns_tmp:
                tmp_ctx.__exit__(None, None, None)

    def test_pass_on_first_round(self):
        result = self._run_with_scripts(
            writer_outputs=["第一稿"],
            reviewer_outputs=[
                'VERDICT: {"pass": true, "violations": []}\n## 审查意见\n全部通过'
            ],
        )
        self.assertTrue(result["passed_review"])
        self.assertEqual(len(result["rounds"]), 1)

    def test_rewrite_then_pass(self):
        result = self._run_with_scripts(
            writer_outputs=["第一稿", "第二稿"],
            reviewer_outputs=[
                'VERDICT: {"pass": false, "violations": [3]}',
                'VERDICT: {"pass": true, "violations": []}',
            ],
        )
        self.assertTrue(result["passed_review"])
        self.assertEqual(len(result["rounds"]), 2)
        # 第二轮审查的输入应包含第一稿（重写基于审查意见）
        reviewer_inputs = result["rounds"][-1]
        self.assertEqual(reviewer_inputs["round"], 2)

    def test_never_pass_stops_at_max_rounds(self):
        result = self._run_with_scripts(
            writer_outputs=["一稿", "二稿", "三稿"],
            reviewer_outputs=[
                'VERDICT: {"pass": false, "violations": [1]}',
                'VERDICT: {"pass": false, "violations": [1]}',
                'VERDICT: {"pass": false, "violations": [1]}',
            ],
        )
        self.assertFalse(result["passed_review"])
        self.assertEqual(len(result["rounds"]), 3)

    def test_output_file_written(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_with_scripts(
                writer_outputs=["最终稿"],
                reviewer_outputs=['VERDICT: {"pass": true, "violations": []}'],
                tmp=tmp,
            )
            out = Path(tmp) / result["output_file"]
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_text(encoding="utf-8").strip(), "最终稿")


if __name__ == "__main__":
    unittest.main()
