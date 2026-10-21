"""spawn 工具与并行扇出的控制流验证（验收 A1 的一部分）。"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.runtime import (  # noqa: E402
    Agent,
    OpenAICompatClient,  # noqa: F401  仅验证可导入
    ToolRegistry,
    make_spawn_tool,
    SpawnCollector,
)
from .fakes import (  # noqa: E402
    ScriptedLLMClient,
    make_text_response,
    make_tool_call_response,
)


def _spawn_setup(child_response: str):
    """主控调用一次 spawn 后输出总结；子 agent 直接返回固定文本。"""
    child_client = ScriptedLLMClient([make_text_response(child_response)])
    child = Agent(name="child", system_prompt="s", client=child_client)

    collector = SpawnCollector()
    spawn_tool = collector.wrap(make_spawn_tool(lambda task: child))
    orchestrator_tools = ToolRegistry()
    orchestrator_tools.register(spawn_tool)

    orchestrator = Agent(
        name="orchestrator",
        system_prompt="s",
        client=ScriptedLLMClient(
            [
                make_tool_call_response("c1", "spawn", {"task": "做一件事"}),
                make_text_response("全部完成"),
            ]
        ),
        tools=orchestrator_tools,
    )
    return orchestrator, child_client, collector


class TestSpawnTool(unittest.TestCase):
    def test_spawn_returns_child_output(self):
        orchestrator, child_client, collector = _spawn_setup("子任务结果：42")
        result = orchestrator.run("派发一个任务")
        self.assertEqual(result, "全部完成")
        # 子 agent 只被调用一次，且收到的就是 spawn 的 task 参数
        self.assertEqual(len(child_client.calls), 1)
        self.assertEqual(child_client.calls[0]["messages"][1]["content"], "做一件事")
        self.assertEqual(collector.tasks, ["做一件事"])

    def test_child_agent_gets_system_prompt_not_orchestrator_history(self):
        orchestrator, child_client, _ = _spawn_setup("ok")
        orchestrator.run("派发")
        system_msg = child_client.calls[0]["messages"][0]
        self.assertEqual(system_msg["content"], "s")
        # 子 agent 的消息只有 system + 自己的 task，共 2 条
        self.assertEqual(len(child_client.calls[0]["messages"]), 2)

    def test_spawn_strips_code_fence(self):
        child = Agent(
            name="child",
            system_prompt="s",
            client=ScriptedLLMClient(
                [make_text_response("```markdown\n内容\n```")]
            ),
        )
        tool = make_spawn_tool(lambda task: child, strip_fence=True)
        output = tool.invoke({"task": "t"})
        self.assertEqual(output, "内容")


if __name__ == "__main__":
    unittest.main()
