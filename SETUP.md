# 运行环境

在本项目目录使用 Python 3.11，安装 `requirements-dev.txt`。
模型接口通过 `JOBSEARCH_LLM_BASE_URL`、`JOBSEARCH_LLM_MODEL`、`JOBSEARCH_LLM_API_KEY` 配置。禁止输出密钥。

默认工作区为项目向上三级目录；个人材料位于工作区下的 `卢天阔_AI-Agent简历/`。
通过 `JOBSEARCH_WORKSPACE_ROOT`、`JOBSEARCH_MATERIALS_ROOT` 可以分别指定位置。
个人资料位于材料目录的 `个人资料/`，三个文件需要真实填写。

Codex、ZCode 从 `AGENTS.md` 和 `.agents/skills/china-job-search/SKILL.md` 进入工作流。
Python 命令入口使用 `py -3.11 -m jobsearch_agents --help`。
日常求职操作见 `docs/first-application.md`，路径约定见 `markets/china/workflows/runtime.md`。

开发检查：

```powershell
py -3.11 tools/lint_skills.py
py -3.11 tools/security_guards.py
py -3.11 -m pytest tests/test_workspace_layout.py -q --basetemp=.artifacts/pytest
```

PDF 编译使用已安装的 TeX 编译器，交付前检查文字、页数和版面。中间文件保存在 `.artifacts/`。
