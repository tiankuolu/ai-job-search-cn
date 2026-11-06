# 运行环境

在本项目目录使用 Python 3.11，安装 `requirements-dev.txt`。
模型接口通过 `JOBSEARCH_LLM_BASE_URL`、`JOBSEARCH_LLM_MODEL`、`JOBSEARCH_LLM_API_KEY` 配置。禁止输出密钥。

默认工作区为仓库同级的 `jobsearch-workspace/`；个人材料位于工作区下的 `求职材料/`。
通过 `JOBSEARCH_WORKSPACE_ROOT`、`JOBSEARCH_MATERIALS_ROOT` 可以分别指定位置。
个人资料位于材料目录的 `个人资料/`，三个文件需要真实填写。

首次运行时创建工作区，复制规则与空白资料模板：

```powershell
$env:JOBSEARCH_WORKSPACE_ROOT = Join-Path (Split-Path $PWD -Parent) 'jobsearch-workspace'
$env:JOBSEARCH_MATERIALS_ROOT = Join-Path $env:JOBSEARCH_WORKSPACE_ROOT '求职材料'
New-Item -ItemType Directory -Path (Join-Path $env:JOBSEARCH_MATERIALS_ROOT '个人资料')
Copy-Item markets/china/workspace-rules.md (Join-Path $env:JOBSEARCH_WORKSPACE_ROOT 'AGENTS.md')
Copy-Item markets/china/profile/*.md (Join-Path $env:JOBSEARCH_MATERIALS_ROOT '个人资料')
```

已有资料时直接指定目录，保留当前文件。学校、GPA、身份与联系方式从资料读取。
教育背景采用模板中的表头；基本信息中的“手机”和“GitHub / 作品集 / 其他链接”需填写实际内容。
实习安排采用 preferences.md 中的“每周可到岗天数”“可持续实习月数”“可到岗时间”。
简历生成还需要 `个人资料/项目事实档案/index.json` 及其引用的项目档案，格式见 [项目档案要求](docs/profile-format.md)。

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
