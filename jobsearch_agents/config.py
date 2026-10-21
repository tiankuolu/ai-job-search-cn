# 运行时配置：全部来自环境变量，端点切换零改码（GOAL.md §2.2）。

import os


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(
            f"缺少环境变量 {name}。请设置 JOBSEARCH_LLM_BASE_URL、"
            "JOBSEARCH_LLM_MODEL、JOBSEARCH_LLM_API_KEY 后重试。"
        )
    return value


class LLMConfig:
    """一次运行的模型端点配置。"""

    def __init__(self) -> None:
        self.base_url: str | None = os.environ.get("JOBSEARCH_LLM_BASE_URL")
        self.model: str | None = os.environ.get("JOBSEARCH_LLM_MODEL")
        self.api_key: str | None = os.environ.get("JOBSEARCH_LLM_API_KEY")

    def require(self) -> "LLMConfig":
        """集成路径使用：三个变量缺一就就地崩溃。"""
        _require("JOBSEARCH_LLM_BASE_URL")
        _require("JOBSEARCH_LLM_MODEL")
        _require("JOBSEARCH_LLM_API_KEY")
        return self


# 评审层达标阈值（GOAL.md A7）
JUDGE_THRESHOLD = float(os.environ.get("JOBSEARCH_JUDGE_THRESHOLD", "0.8"))
# 自改循环预算（GOAL.md §4 护栏 3）
LOOP_MAX_ROUNDS = int(os.environ.get("JOBSEARCH_LOOP_MAX_ROUNDS", "10"))
LOOP_TOKEN_BUDGET = int(os.environ.get("JOBSEARCH_LOOP_TOKEN_BUDGET", "5000000"))
