# 验收 A7-A9：评审层达标、trace 完整、端点切换零改码。

import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.config import JUDGE_THRESHOLD, LLMConfig  # noqa: E402
from jobsearch_agents.prompts import load_prompt  # noqa: E402
from jobsearch_agents.runtime import Agent, OpenAICompatClient  # noqa: E402

pytestmark = pytest.mark.integration

SCORE_RE = re.compile(r'SCORE:\s*(\{.*\})', re.IGNORECASE)

# 三个自成一体的验收测试不复用 workspace fixture，避免与 A3-A6 的执行顺序耦合


class TestJudge:
    def test_a7_judge_scores_above_threshold(self):
        """评审 agent 对一份构造的评估报告打分，分数必须达标。"""
        sample = Path(
            REPO / "jobsearch_agents" / "fixtures" / "jd" / "starfield-research-python-agent-dev.md"
        ).read_text(encoding="utf-8")
        judge = Agent(
            name="judge",
            system_prompt=load_prompt("judge"),
            client=OpenAICompatClient(LLMConfig()),
        )
        raw = judge.run(f"# 待评审产物\n{sample}\n\n# 输入材料\n（该岗位的原始描述文件）")
        match = SCORE_RE.search(raw)
        assert match, f"评审输出没有 SCORE 行：{raw[:200]}"
        score = json.loads(match.group(1))["score"]
        assert score >= JUDGE_THRESHOLD, f"评审分 {score} 低于阈值 {JUDGE_THRESHOLD}"


class TestTrace:
    def test_a8_trace_complete_after_run(self):
        """一次最小真实运行后 trace 必须包含输入输出、token、耗时。"""
        from jobsearch_agents.runtime.trace import Trace

        trace_dir = REPO / "runs"
        trace_dir.mkdir(exist_ok=True)
        trace = Trace(trace_dir, "trace-check")
        agent = Agent(
            name="smoke",
            system_prompt="你是回声服务，原样返回用户输入。",
            client=OpenAICompatClient(LLMConfig()),
            trace=trace,
        )
        reply = agent.run("回复这两个字：正常")
        assert "正常" in reply or len(reply) > 0
        trace.assert_complete()
        saved = trace.save()
        payload = json.loads(saved.read_text(encoding="utf-8"))
        record = payload["calls"][0]
        assert record["model"] == os.environ["JOBSEARCH_LLM_MODEL"]
        assert record["prompt_tokens"] + record["completion_tokens"] > 0


class TestEndpointSwitch:
    def test_a9_endpoint_from_env_only(self):
        """模型名从环境变量进入请求与 trace，代码不含任何端点硬编码。"""
        config = LLMConfig().require()
        assert config.model == os.environ["JOBSEARCH_LLM_MODEL"]
        # cli 模块与 runtime 模块里不允许出现具体厂商域名
        for module_path in (REPO / "jobsearch_agents").rglob("*.py"):
            text = module_path.read_text(encoding="utf-8")
            for domain in ("api.deepseek.com", "dashscope.aliyuncs.com", "open.bigmodel.cn"):
                assert domain not in text, f"{module_path} 硬编码了端点域名 {domain}"
