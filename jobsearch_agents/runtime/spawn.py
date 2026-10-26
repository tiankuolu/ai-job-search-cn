# spawn 工具启动子 agent，并等待执行结果。

import re
from typing import Callable

from .tools import Tool, infer_schema
from .trace import Trace
from .agent import Agent


def _strip_fence(text: str) -> str:
    """去掉模型可能包裹的 markdown 代码围栏，保留纯 markdown 正文。"""
    return re.sub(r"^```[a-zA-Z]*\n|```$", "", text.strip(), flags=re.MULTILINE).strip()


def make_spawn_tool(
    agent_factory: Callable[[str], Agent],
    trace: Trace | None = None,
    strip_fence: bool = True,
) -> Tool:
    """构造 spawn 工具。

    agent_factory 接收子任务描述，返回配好 prompt 与工具的子 agent。
    子 agent 的输出直接回填为工具结果，主控不需要任何新机制。
    """

    def spawn(task: str) -> str:
        child = agent_factory(task)
        result = child.run(task)
        return _strip_fence(result) if strip_fence else result

    return Tool(
        name="spawn",
        description=(
            "派发一个自包含的子任务给专职 agent 并阻塞等待其结果。"
            "task 必须包含子 agent 完成任务所需的全部信息，"
            "子 agent 看不到当前对话的任何其他内容。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "自包含的子任务描述"}
            },
            "required": ["task"],
        },
        func=spawn,
    )


class SpawnCollector:
    """记录 spawn 派发过的子任务，测试与 trace 用。"""

    def __init__(self) -> None:
        self.tasks: list[str] = []

    def wrap(self, spawn_tool: Tool) -> Tool:
        original = spawn_tool.func

        def spawn_with_collect(task: str) -> str:
            self.tasks.append(task)
            return original(task)

        return Tool(
            name=spawn_tool.name,
            description=spawn_tool.description,
            parameters=spawn_tool.parameters,
            func=spawn_with_collect,
        )
