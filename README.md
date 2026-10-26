# 中国实习求职 Agent

项目使用 Python 驱动模型工具调用、并行岗位分析、申请材料生成与审查、岗位排序、公司调研和面试练习。Codex、ZCode 也可通过项目技能执行相同求职任务。

## 工作区

工作区为 `D:\找实习`，共同规则见工作区根目录 `AGENTS.md`。
`项目/` 保存代码与实验依据，`卢天阔_AI-Agent简历/` 集中保存个人求职资料和材料。

材料目录中的文件位置：

- `个人资料/`：`candidate.md`、`preferences.md`、`evidence.md`。
- 各公司岗位目录：`岗位JD.md`、简历源文件与成品、`打招呼语.md`。
- `岗位记录/inbox/`：抓取与手动保存的岗位原文。
- `岗位记录/evaluated/`：评估、公司调研、申请包、排序与 `delivery-status.csv`。
- `面试准备/`：故事库、练习卷、评分记录。

程序同时读取公司岗位目录中的 JD 和 inbox，内容完全相同的文件优先使用公司岗位目录。公司岗位目录以目录名称作为岗位标识，inbox 使用文件名。
模型调用轨迹保存在项目 `runs/`；开发验证中间文件保存在 `.artifacts/`。

## 运行

在本项目目录安装 `requirements-dev.txt`，配置 `JOBSEARCH_LLM_BASE_URL`、`JOBSEARCH_LLM_MODEL`、`JOBSEARCH_LLM_API_KEY`。
使用 OpenAI 兼容模型接口，密钥通过环境变量传入。

```powershell
py -3.11 -m pip install -r requirements-dev.txt
py -3.11 -m jobsearch_agents --help
py -3.11 -m jobsearch_agents analyze
py -3.11 -m jobsearch_agents rank
py -3.11 -m jobsearch_agents apply '卢天阔_AI-Agent简历/月之暗面-Agent评测实习-350-400元天/岗位JD.md'
py -3.11 -m jobsearch_agents status
```

相对输入路径以工作区为基准，也可以提供完整路径。
`JOBSEARCH_WORKSPACE_ROOT` 可指定工作区，`JOBSEARCH_MATERIALS_ROOT` 可指定材料目录。
程序的 `apply` 生成 Markdown 申请包；简历源文件和 PDF 由助手结合现有基版制作，实际编译并检查后交付。

Codex、ZCode 使用 `.agents/skills/china-job-search/SKILL.md`，按 `markets/china/workflows/` 执行。操作见 `docs/first-application.md`。

## React 交互工作台

在项目目录运行：

```powershell
.\start-web.ps1 -InstallDependencies
```

之后使用 `.\start-web.ps1` 启动，打开 <http://127.0.0.1:8765>。
启动脚本构建 React 界面，使用同一个 Python 服务提供页面和接口。
已经完成构建时可以使用 `.\start-web.ps1 -SkipBuild`。
模型使用前述 `JOBSEARCH_LLM_*` 环境变量；本机已有 `runs/run-integration.env.ps1` 时，启动脚本可读取其中的配置。
配置缺失时仍可浏览岗位和历史记录，执行按钮会显示为不可用。

- 从真实材料目录读取岗位，支持搜索、选择和阅读原文及已有材料。
- 运行选中岗位的并行分析、单个岗位的申请材料生成、全部评估的排序和面试准备。
- 交互流程图展示 Agent、模型调用和工具调用；支持拖动、缩放和点击节点查看输入输出。
- SSE 推送真实执行事件，记录岗位归属、材料审查轮次、工具参数与结果、模型 token 和耗时；断开后按事件编号续接。
- 历史运行支持事件回放和成果阅读、下载；旧版 JSON 记录展示已有模型输入输出。
- 材料未通过全部审查时显示“需要审阅”；任务错误显示失败原因；服务重新启动后将未结束任务标记为中断。

任务继续使用现有 Python 动作和求职资料，成果写入材料目录。
每次网页任务在 `runs/web/<run_id>/` 保存事件、任务信息和成果副本，模型调用记录保存在 `runs/<run_id>.json`。
服务同一时间接受一个网页任务，岗位分析任务内部支持并行，避免网页任务同时覆盖同一份材料。
服务默认监听本机 `127.0.0.1`；接口验证本机来源和岗位标识。

开发前端时，在项目目录启动 Python 服务，在 `frontend/` 执行 `npm run dev`，Vite 将 `/api` 转发至本机服务。
前端使用 React、TypeScript、Mermaid 和 Markdown 渲染组件；Mermaid 绘制执行流程，React Flow 提供浏览、缩放和视图控制，Python 接口使用 FastAPI。

文件、接口和真实模型验证命令：

```powershell
py -3.11 -m pytest tests/test_web_real.py -m 'not integration' --basetemp=.artifacts/pytest-web -q
py -3.11 -m pytest tests/test_web_real.py -m integration --basetemp=.artifacts/pytest-web-model -s -q
```

真实模型验证复制现有个人资料及两个完整岗位至独立验证目录，执行分析、材料生成与审查、排序和面试准备，检查事件续接及历史重新读取。

## 项目组成

- `jobsearch_agents/`：运行时、动作编排、模型提示词。
- `markets/china/`：招聘来源、资料模板、中文材料模板、工作流。
- `.agents/skills/china-job-search/`：技能入口。
- `tools/`：岗位标识、状态、薪资和文档验证工具。
- `tests/`：程序与工具验证。
- `cv/`、`cover_letters/`：通用排版参考；当前实习简历使用材料目录的单页基版。

修改路径时同步更新程序、技能、工作流和测试。个人资料初始化保护已有文件，真实岗位与申请状态需要保留。

## 来源与许可

基于 MadsLorentzen/ai-job-search 开发，保留其 MIT License，详见 LICENSE。
