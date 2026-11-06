# 手动安装与运行

以下命令在 Windows PowerShell 中执行。完整依赖清单见 [README](README.md#安装前准备)；也可以使用 [智能体安装提示词](docs/agent-install.md) 完成环境检查与配置。

## 安装代码与依赖

需要 Git、Python 3.11、Node.js 22 与 npm。

```powershell
git clone https://github.com/tiankuolu/ai-job-search-cn.git
cd ai-job-search-cn
py -3.11 -m pip install -r requirements-web.txt
npm --prefix frontend ci
npm --prefix frontend run build
```

## 配置个人工作区

默认工作区为仓库同级的 `jobsearch-workspace/`，材料保存在其中的 `求职材料/`。以下命令用于创建全新资料目录；已有资料时直接设置两个环境变量，保留当前文件。

```powershell
$ErrorActionPreference = 'Stop'
$env:JOBSEARCH_WORKSPACE_ROOT = Join-Path (Split-Path $PWD -Parent) 'jobsearch-workspace'
$env:JOBSEARCH_MATERIALS_ROOT = Join-Path $env:JOBSEARCH_WORKSPACE_ROOT '求职材料'
New-Item -ItemType Directory -Path (Join-Path $env:JOBSEARCH_MATERIALS_ROOT '个人资料')
Copy-Item markets/china/workspace-rules.md (Join-Path $env:JOBSEARCH_WORKSPACE_ROOT 'AGENTS.md')
Copy-Item markets/china/profile/*.md (Join-Path $env:JOBSEARCH_MATERIALS_ROOT '个人资料')
```

根据真实信息填写 `candidate.md`、`preferences.md`、`evidence.md`，并准备 `个人资料/项目事实档案/index.json` 及引用的 Markdown。字段和编号要求见 [资料格式](docs/profile-format.md)。

基本信息的“手机”和“GitHub / 作品集 / 其他链接”采用模板字段名称；教育背景保留模板表头，GPA 未提供时留空。实习安排填写“每周可到岗天数”“可持续实习月数”“可到岗时间”。当前简历格式需要两个以上相关项目、两条以上有依据的技能，以及至少一条真实的荣誉、竞赛或语言条目。

## 配置模型

使用支持工具调用和 JSON 输出的 OpenAI 兼容服务。接口地址与模型名称按服务商提供的值填写，密钥输入会隐藏：

```powershell
$env:JOBSEARCH_LLM_BASE_URL = Read-Host 'OpenAI 兼容接口地址'
$env:JOBSEARCH_LLM_MODEL = Read-Host '模型名称'
$env:JOBSEARCH_LLM_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host '模型 API Key' -AsSecureString)).Password
```

这些环境变量在当前 PowerShell 窗口生效。再次启动时，在新窗口设置变量，或使用已经配置并受到 Git 忽略保护的本地启动配置。密钥保留在本地，回复和共享日志中省略密钥值。

## 启动工作台

在同一窗口运行：

```powershell
.\start-web.ps1 -SkipBuild
```

打开 [本地工作台](http://127.0.0.1:8765)。首次安装也可以使用 `.\start-web.ps1 -InstallDependencies` 完成 Python 依赖安装与前端构建；后续使用 `.\start-web.ps1` 重新构建并启动。

## 接入完整招聘流程

搜索、界面材料生成与投递需要配置兼容 `/api/jobsearch/*` 的 `get_jobs` 本地服务、JDK 21、Gradle、浏览器和 Poppler。脚本按本项目目录中的 `../../get_jobs` 解析服务源码目录，还需要服务发行版提供的数据库。

按实际位置填写工具路径：

```powershell
py -3.11 tools/setup_delivery.py --java-home '<Java 21 根目录>' --gradle '<gradle.bat 路径>' --browser-channel msedge --pdftoppm '<pdftoppm.exe 路径>'
.\start-integrated.ps1 -Build
```

配置写入本地 `runs/delivery/settings.json`。招聘平台账号由本人完成登录，再核对真实登录状态。完整接口、保存位置和结果核查见 [自动搜索与简历投递](docs/automatic-delivery.md)。

## 生成与导出简历

在项目目录运行，填写实际完整路径，输出目录需要尚未存在：

```powershell
py -3.11 -m tools.make_resume --job '<岗位JD完整路径>' --output '<尚不存在的输出目录>'
```

该命令读取当前资料与事实档案，生成、审查并制作可编辑 HTML、A4 PDF 与预览图。默认使用 Edge，也可以通过 `--browser-channel chrome` 选择 Chrome。

生成稿要求 A4 单页、正文占用 95% 至 100%、最小字号 9pt，并检查文字、链接和页面边界。人工修改后的简历保持当前正文，直接导出 PDF 与预览图，验证导出文件与当前版本一致。

## 常用入口

- [首次申请操作](docs/first-application.md)
- [Codex](docs/codex.md) / [ZCode](docs/zcode.md) 使用说明
- [项目技能](.agents/skills/china-job-search/SKILL.md) 与 [工作流](markets/china/workflows/index.md)
- [开发检查与程序结构](README.md#开发与实现)
