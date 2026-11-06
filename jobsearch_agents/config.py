# 模型配置由环境变量或明确指定的 DeepSeek 配置文件提供。

import os
from pathlib import Path

from dotenv import dotenv_values


class LLMConfig:
    """一次运行的模型端点配置。"""

    def __init__(self) -> None:
        self.base_url: str | None = os.environ.get("JOBSEARCH_LLM_BASE_URL")
        self.model: str | None = os.environ.get("JOBSEARCH_LLM_MODEL")
        self.api_key: str | None = os.environ.get("JOBSEARCH_LLM_API_KEY")
        self.reasoning_effort: str | None = os.environ.get("JOBSEARCH_LLM_REASONING_EFFORT")
        if self.reasoning_effort and self.reasoning_effort not in {"low", "high", "max"}:
            raise ValueError("JOBSEARCH_LLM_REASONING_EFFORT 必须为 low、high 或 max")
        self.resume_reasoning_effort = os.environ.get("JOBSEARCH_RESUME_REASONING_EFFORT", self.reasoning_effort)
        if self.resume_reasoning_effort and self.resume_reasoning_effort not in {"low", "high", "max"}:
            raise ValueError("JOBSEARCH_RESUME_REASONING_EFFORT 必须为 low、high 或 max")
        self.thinking_mode = os.environ.get("JOBSEARCH_LLM_THINKING")
        self.resume_thinking_mode = os.environ.get("JOBSEARCH_RESUME_THINKING", self.thinking_mode)
        for value in (self.thinking_mode, self.resume_thinking_mode):
            if value is not None and value not in {"enabled", "disabled"}:
                raise ValueError("思考模式配置必须为 enabled 或 disabled")
        source_file = os.environ.get("JOBSEARCH_DEEPSEEK_ENV_FILE")
        if source_file:
            path = Path(source_file).resolve(strict=True)
            settings = dotenv_values(path)
            self.base_url = settings["DEEPSEEK_BASE_URL"]
            self.api_key = settings["DEEPSEEK_API_KEY"]

    def require(self) -> "LLMConfig":
        """集成路径使用：三个变量缺一就就地崩溃。"""
        for name, value in {"JOBSEARCH_LLM_BASE_URL": self.base_url, "JOBSEARCH_LLM_MODEL": self.model,
                            "JOBSEARCH_LLM_API_KEY": self.api_key}.items():
            if not value:
                raise RuntimeError(f"模型配置缺少 {name}，请检查环境变量或指定的 DeepSeek 配置文件")
        return self


# 评审层达标阈值。
JUDGE_THRESHOLD = float(os.environ.get("JOBSEARCH_JUDGE_THRESHOLD", "0.8"))
# 自改循环预算。
LOOP_MAX_ROUNDS = int(os.environ.get("JOBSEARCH_LOOP_MAX_ROUNDS", "10"))
LOOP_TOKEN_BUDGET = int(os.environ.get("JOBSEARCH_LOOP_TOKEN_BUDGET", "5000000"))
