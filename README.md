# 中国实习求职 Agent

项目使用 Python 驱动模型工具调用、并行岗位分析、申请材料生成与审查、岗位排序、公司调研和面试练习。Codex、ZCode 也可通过项目技能执行相同求职任务。

## 工作区

代码与个人材料分别保存。默认工作区为仓库同级的 `jobsearch-workspace/`，材料目录为其中的 `求职材料/`。
通过 `JOBSEARCH_WORKSPACE_ROOT` 和 `JOBSEARCH_MATERIALS_ROOT` 可以指定已有工作区与材料目录。
首次配置与资料格式见 [SETUP.md](SETUP.md)；个人资料、登录状态和运行记录保留在本地。

材料目录中的文件位置：

- `个人资料/`：`candidate.md`、`preferences.md`、`evidence.md`，以及 `项目事实档案/index.json` 和对应项目 Markdown。
- 各公司岗位目录：`岗位JD.md`、简历源文件与成品、`打招呼语.md`。
- `岗位记录/inbox/`：抓取与手动保存的岗位原文。
- `岗位记录/evaluated/`：评估、公司调研、申请包、排序与 `delivery-status.csv`。
- `面试准备/`：故事库、练习卷、评分记录。

程序同时读取公司岗位目录中的 JD 和 inbox，内容完全相同的文件优先使用公司岗位目录。公司岗位目录以目录名称作为岗位标识，inbox 使用文件名。
模型调用轨迹保存在项目 `runs/`；开发验证中间文件保存在 `.artifacts/`。

## 运行

工作台首次生成、按要求修改和重新生成材料时，可以分别勾选“中英文简历”“项目职责和项目描述”“自我描述”。材料页支持依据当前保存的简历单独生成这三类内容。英文版本提供可编辑 HTML、A4 单页 PDF 和预览图；项目介绍逐字段复制和下载 Markdown，自我描述支持复制和下载。项目名称与顺序取自当前简历，JD 用于确定表达重点；生成内容经过原文依据检查与模型核查。修改简历后，需要重新生成对应材料才能下载或复制。

在本项目目录安装 `requirements-dev.txt`，配置 `JOBSEARCH_LLM_BASE_URL`、`JOBSEARCH_LLM_MODEL`、`JOBSEARCH_LLM_API_KEY`。
使用 OpenAI 兼容模型接口，密钥通过环境变量传入。

```powershell
py -3.11 -m pip install -r requirements-dev.txt
py -3.11 -m jobsearch_agents --help
py -3.11 -m jobsearch_agents analyze
py -3.11 -m jobsearch_agents rank
py -3.11 -m jobsearch_agents apply '求职材料/公司-岗位/岗位JD.md'
py -3.11 -m jobsearch_agents status
```

相对输入路径以工作区为基准，也可以提供完整路径。
`JOBSEARCH_WORKSPACE_ROOT` 可指定工作区，`JOBSEARCH_MATERIALS_ROOT` 可指定材料目录。
程序的 `apply` 生成 Markdown 申请包。简历提升采用 ASu 的岗位定位、项目改写与证据关联方法，制作采用 ASu 单栏高密度模板，交付可编辑 HTML、A4 单页 PDF 和预览图。
申请包包含 `Resume Project Experience` 正文与内部 `Resume Evidence` 记录。生成时读取个人信息、偏好和全部项目事实档案，按 JD 选择相关事实与篇幅。写作与审查 Agent 自动加载 `markets/china/resume-writing.md`、`resume-enhancement.md`，以及 ASu great-resume、make-resume 原始技能和证据、页面检查规范；运行记录保存技能文件位置与摘要。助手工作流使用相同规范。原始事实、个人贡献、指标条件与候选措辞分别核查。正式简历要求 A4 一页，页面占用 95%—100%，最小字号 9pt，内容及导出检查通过后交付。

```powershell
py -3.11 -m pip install -r requirements-web.txt
py -3.11 -m tools.make_resume --job '求职材料/公司-岗位/岗位JD.md' --output '求职材料/公司-岗位/ASu简历'
```

使用本机 Edge（默认）或 `--browser-channel chrome` 导出 PDF，检查单页、正文、链接、文字边界、字号和页面占用。已有申请包自动读取，也可通过 `--application` 指定；改写结果与模型记录单独保存，输出目录必须不存在。

Codex、ZCode 使用 `.agents/skills/china-job-search/SKILL.md`，按 `markets/china/workflows/` 执行。操作见 `docs/first-application.md`。

## React 交互工作台

工作台左侧显示公司、岗位和申请状态，右侧按“岗位分析、编写简历、确认材料、提交申请、查看结果”推进申请。页面连接相邻 `get_jobs` 本地服务，读取北京实习岗位，使用现有 Agent 生成与审查材料，编译并检查简历。运行配置与记录位置见 [自动搜索与简历投递](docs/automatic-delivery.md)。

不同岗位支持并发分析、生成和导出，默认同时执行三个任务，额外任务排队。批量岗位按每个岗位分别建立任务，左侧列表分别显示运行状态；同一岗位的重复任务与材料编辑互相保护。搜索、登录、投递和结果核查共用招聘浏览器，按顺序执行。设置 `JOBSEARCH_DELIVERY_CONCURRENCY` 可以调整并发数量，取值为正整数。

在项目目录运行：

```powershell
.\start-web.ps1 -InstallDependencies
```

之后使用 `.\start-web.ps1` 启动，打开 <http://127.0.0.1:8765>。
启动脚本构建 React 界面，使用同一个 Python 服务提供页面和接口。
已经完成构建时可以使用 `.\start-web.ps1 -SkipBuild`。
模型使用前述 `JOBSEARCH_LLM_*` 环境变量；本机已有 `runs/run-integration.env.ps1` 时，启动脚本可读取其中的配置。
配置缺失时仍可浏览已保存岗位和材料，执行按钮会显示为不可用。

- 搜索窗口自动检查所选平台的登录状态，提供“打开登录浏览器”和“检查登录状态”入口；确认登录后搜索岗位。服务在创建搜索任务及开始搜索时再次核对登录状态，未登录时给出明确提示。按公司、岗位名称和申请状态筛选左侧列表。
- 点击“添加 JD”可以填写正文、导入文件或解析招聘链接。链接解析保留完整职责与要求并自动填写字段，核对后保存岗位；BOSS 使用招聘浏览器的登录状态，其他网页使用独立且可保留登录状态的浏览器。需要登录时点击“打开网页登录”，完成后重新解析。小红书官网岗位通过公开详情接口读取。PDF 图片页面和 PNG 使用本地 OCR，原文件与网页原文保存在运行目录。
- 读取完整岗位要求和真实匹配依据，生成对应岗位的定制申请材料。
- 处理过程中用一行动画文字显示实际阶段，包含内容检查、简历导出和投递。
- 页面使用可直接编辑的 HTML 展示简历，支持放大编辑和服务端自动保存，刷新后恢复修改。打招呼语也可修改保存。
- 顶部“重新生成简历”允许留空要求，每次按完整 JD 和最新资料重新编写并保存为独立版本。旧稿与手动修改保留，材料下方可以切换历史版本。“填写修改要求”在当前稿上进行定向修改。
- PDF、HTML、PNG 的导出及下载名称统一使用“公司-岗位名称”，缺少公司名称时使用“-岗位名称”。公司字段可以留空；文件名中的 Windows 非法字符转换为下划线。
- 已保存结构化正文的材料打开时可转换为 HTML，继续进行编辑与导出，原有 PDF 保留。
- 点击“确认材料，继续”时，按照人工保存的 HTML 直接导出 PDF 和图片，不调用审查 Agent，不进行固定字段、页面占用或字号审核，不自动改写正文。导出验证正文与链接，人工稿后续投递不受页面占用要求限制。修改尚未导出时，下载和投递接口会提示重新导出；原有文件保留在历史版本目录。
- 简历必须为 A4 单页，正文占可用高度的 95% 至 100%，最小字号为 9pt；根据真实排版测量结果补充相关事实，重新审查后导出。投递接口检查材料占用是否达标。
- 确认材料、检查登录状态后提交申请，展示实际发送结果；待核实记录提供核实操作。
- 当前岗位和查看步骤保存在浏览器，材料与投递结果保存在服务端。

任务继续使用现有 Python 动作和求职资料，成果写入材料目录。
每次网页任务在 `runs/web/<run_id>/` 保存事件、任务信息和成果副本，模型调用记录保存在 `runs/<run_id>.json`。
服务同一时间接受一个网页任务，岗位分析任务内部支持并行，避免网页任务同时覆盖同一份材料。
服务默认监听本机 `127.0.0.1`；接口验证本机来源和岗位标识。

开发前端时，在项目目录启动 Python 服务，在 `frontend/` 执行 `npm run dev`，Vite 将 `/api` 转发至本机服务。
前端使用 React、TypeScript 和 Lucide 图标，Python 接口使用 FastAPI。

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
简历提升规范和默认制作模板引入自 Hisn00w/ASu-skills，固定提交与 MIT 许可见 [来源说明](third_party/asu-skills/SOURCE.md) 和 [许可全文](third_party/asu-skills/LICENSE)。
