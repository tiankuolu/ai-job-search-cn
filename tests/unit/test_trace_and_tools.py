"""trace 记录与评分合成工具的单元验证（验收 A1/A8 的一部分）。"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.runtime import Agent, Tool, ToolRegistry, Trace  # noqa: E402
from jobsearch_agents.tools_wrap.key_tools import (  # noqa: E402
    band,
    overall_score,
    register_key_tools,
)
from .fakes import (  # noqa: E402
    ScriptedLLMClient,
    make_text_response,
    make_tool_call_response,
)


class TestTrace(unittest.TestCase):
    def test_trace_records_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp), "analyze")
            client = ScriptedLLMClient([make_text_response("答案")])
            agent = Agent(name="a", system_prompt="s", client=client, trace=trace)
            agent.run("问题")
            self.assertEqual(len(trace.records), 1)
            record = trace.records[0]
            self.assertEqual(record.agent, "a")
            self.assertEqual(record.model, "scripted-fake")
            self.assertGreaterEqual(record.latency_ms, 0)
            self.assertGreater(record.prompt_tokens, 0)
            path = trace.save()
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn("scripted-fake", content)
            trace.assert_complete()

    def test_assert_complete_rejects_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp), "rank")
            with self.assertRaises(AssertionError):
                trace.assert_complete()

    def test_token_totals_accumulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp), "apply")
            client = ScriptedLLMClient(
                [make_text_response("a", token_cost=100), make_text_response("b", token_cost=40)]
            )
            agent = Agent(name="w", system_prompt="s", client=client, trace=trace)
            agent.run("q")
            self.assertEqual(trace.records[0].prompt_tokens, 100)
            self.assertGreater(trace.total_tokens, 120)


class TestScoreTools(unittest.TestCase):
    def test_overall_score_weights(self):
        scores = {
            "technical": 80,
            "experience": 60,
            "domain": 40,
            "communication": 100,
            "compensation_location": 70,
            "growth": 50,
        }
        # 80*.25 + 60*.25 + 40*.15 + 100*.10 + 70*.10 + 50*.15 = 66.0
        self.assertEqual(overall_score(scores), 66)

    def test_band_boundaries(self):
        self.assertEqual(band(80), "Strong Fit")
        self.assertEqual(band(79), "Good Fit")
        self.assertEqual(band(65), "Good Fit")
        self.assertEqual(band(64), "Moderate Fit")
        self.assertEqual(band(50), "Moderate Fit")
        self.assertEqual(band(49), "Weak Fit")
        self.assertEqual(band(35), "Weak Fit")
        self.assertEqual(band(34), "Poor Fit")
        self.assertEqual(band(0), "Poor Fit")

    def test_overall_score_rejects_missing_dimension(self):
        with self.assertRaises(ValueError):
            overall_score({"technical": 50})

    def test_overall_score_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            overall_score(
                {
                    "technical": 101,
                    "experience": 0,
                    "domain": 0,
                    "communication": 0,
                    "compensation_location": 0,
                    "growth": 0,
                }
            )

    def test_job_key_tool_registered(self):
        registry = ToolRegistry()
        register_key_tools(registry, REPO)
        self.assertIn("make_job_key", registry.names())
        self.assertIn("overall_score", registry.names())
        self.assertIn("score_band", registry.names())


class TestToolInvocation(unittest.TestCase):
    def test_tool_invoke_via_agent(self):
        registry = ToolRegistry()
        register_key_tools(registry, REPO)
        client = ScriptedLLMClient(
            [
                make_tool_call_response(
                    "c1",
                    "make_job_key",
                    {"company": "星野科研软件", "title": "Agent 应用开发工程师"},
                ),
                make_text_response("key 已生成"),
            ]
        )
        agent = Agent(
            name="analyzer",
            system_prompt="s",
            client=client,
            tools=registry,
        )
        result = agent.run("生成 key")
        self.assertEqual(result, "key 已生成")
        tool_reply = [
            m for m in client.calls[1]["messages"] if m.get("role") == "tool"
        ][0]
        self.assertIn("output", tool_reply["content"])


if __name__ == "__main__":
    unittest.main()
