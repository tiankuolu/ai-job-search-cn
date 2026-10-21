"""运行时核心：agent 循环、工具协议、spawn、trace。"""

from .agent import Agent, OpenAICompatClient, LLMClient
from .spawn import make_spawn_tool, SpawnCollector
from .tools import Tool, ToolRegistry, infer_schema
from .trace import Trace, LLMCallRecord

__all__ = [
    "Agent",
    "OpenAICompatClient",
    "LLMClient",
    "Tool",
    "ToolRegistry",
    "infer_schema",
    "make_spawn_tool",
    "SpawnCollector",
    "Trace",
    "LLMCallRecord",
]
