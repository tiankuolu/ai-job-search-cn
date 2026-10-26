"""Agent 循环控制流验证：工具调用、回填、终止、错误处理（验收 A1 的一部分）。"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.runtime import Agent, Tool, ToolRegistry  # noqa: E402
from .fakes import (  # noqa: E402
    ScriptedLLMClient,
    make_text_response,
    make_tool_call_response,
)


def _echo_tool() -> Tool:
    return Tool(
        name="echo",
        description="原样返回 message",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        func=lambda message: f"echo: {message}",
    )


class TestAgentLoop(unittest.TestCase):
    def test_direct_text_reply(self):
        client = ScriptedLLMClient([make_text_response("直接回答")])
        agent = Agent(name="t", system_prompt="s", client=client)
        self.assertEqual(agent.run("你好"), "直接回答")
        self.assertEqual(len(client.calls), 1)

    def test_tool_call_then_text(self):
        client = ScriptedLLMClient(
            [
                make_tool_call_response("c1", "echo", {"message": "ping"}),
                make_text_response("完成"),
            ]
        )
        registry = ToolRegistry()
        registry.register(_echo_tool())
        agent = Agent(name="t", system_prompt="s", client=client, tools=registry)
        result = agent.run("请调用 echo")
        self.assertEqual(result, "完成")
        # 第二轮请求里应包含工具结果回填
        second_messages = client.calls[1]["messages"]
        tool_messages = [m for m in second_messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("echo: ping", tool_messages[0]["content"])

    def test_model_receives_tool_schema(self):
        client = ScriptedLLMClient([make_tool_call_response("c1", "echo", {"message": "x"}),
                                    make_text_response("done")])
        registry = ToolRegistry()
        registry.register(_echo_tool())
        agent = Agent(name="t", system_prompt="s", client=client, tools=registry)
        agent.run("go")
        tools_payload = client.calls[0]["tools"]
        self.assertEqual(tools_payload[0]["function"]["name"], "echo")

    def test_max_turns_raises(self):
        responses = [
            make_tool_call_response(f"c{i}", "echo", {"message": str(i)}) for i in range(15)
        ]
        client = ScriptedLLMClient(responses)
        registry = ToolRegistry()
        registry.register(_echo_tool())
        agent = Agent(name="t", system_prompt="s", client=client, tools=registry, max_turns=5)
        with self.assertRaises(RuntimeError) as ctx:
            agent.run("loop")
        self.assertIn("最大轮数", str(ctx.exception))

    def test_null_tool_calls_treated_as_text(self):
        # 某些端点对空工具列表会回 content 空串 + tool_calls 空数组的组合
        response = make_text_response("final")
        response["choices"][0]["message"]["tool_calls"] = None
        client = ScriptedLLMClient([response])
        agent = Agent(name="t", system_prompt="s", client=client)
        self.assertEqual(agent.run("q"), "final")


if __name__ == "__main__":
    unittest.main()
