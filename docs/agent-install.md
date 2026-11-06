# 交给智能体安装

将下面整段提示词复制给你使用的编码智能体。它覆盖环境检查、依赖安装、资料配置、启动和真实验证。

```text
请帮我安装、配置并运行 https://github.com/tiankuolu/ai-job-search-cn 。
我授权你在本机创建项目工作目录、安装所需依赖并启动本地服务。

1. 读取 README.md、AGENTS.md、SETUP.md、docs/profile-format.md、
   docs/automatic-delivery.md 及启动脚本。检查已有目录、软件与配置，
   保留已有个人资料和手动修改。
2. 检查 Git、Windows PowerShell、Python 3.11、Node.js 22、npm、
   Edge 或 Chrome、Playwright 和 Poppler。使用系统包管理器及项目依赖文件
   安装缺少的软件，运行版本命令确认可用。安装 requirements-web.txt，
   执行 npm --prefix frontend ci 和 npm --prefix frontend run build。
3. 在代码目录外创建个人工作区，用 JOBSEARCH_WORKSPACE_ROOT 和
   JOBSEARCH_MATERIALS_ROOT 指定实际位置。从仓库复制缺少的空白资料与规则，
   依据我提供的简历、偏好和项目证据填写资料。姓名、联系方式、教育、到岗安排
   与贡献归属需要有我的真实资料支持。已有文件保持当前内容。
4. 配置项目事实档案/index.json 和引用的 Markdown，使用稳定事实编号，
   记录真实来源、本人动作、验证条件与结果。缺少的个人信息、项目证据和偏好
   集中向我询问，保持未确认内容为空，并按 ResumePlan 与 ResumePreferences
   的当前字段核对简历生成所需资料。
5. 复用我已经配置的 OpenAI 兼容模型服务；缺少时集中询问接口地址、模型名称
   与密钥的安全输入方式。配置 JOBSEARCH_LLM_BASE_URL、JOBSEARCH_LLM_MODEL、
   JOBSEARCH_LLM_API_KEY，检查工具调用和 JSON 输出。密钥只保存在本地受保护
   的配置中，聊天回复与日志不得输出密钥值。
6. 配置 JDK 21、Gradle 和兼容 /api/jobsearch/* 的 get_jobs 服务，
   按 start-integrated.ps1 实际解析的目录检查源码、发行版数据库和构建产物。
   使用 tools/setup_delivery.py 保存 Java、Gradle、浏览器和 pdftoppm 路径。
   缺少适配服务或真实数据库时，列出需要我提供的内容及受影响功能，
   继续完成其他可以真实验证的安装步骤。
7. 启动工作台与已配置的本地服务，实际检查页面、接口、模型响应和公开示例
   JD 导入。运行技能检查、隐私检查、相关测试和前端构建，修复安装与启动错误。
   招聘平台需要登录时，由我完成登录，再读取实际登录状态。
8. 提供本地打开地址、实际安装版本、个人资料目录、已验证功能与待补充配置。
   个人资料、密钥、Cookie、数据库和运行记录保留在本地。
   公开发布、发送招聘消息与提交申请需要我另外明确授权。
```

## 安装时需要你提供

- 模型接口地址、模型名称和安全输入的 API Key。
- 真实简历、求职偏好、项目贡献与验证依据。
- 已有工作区和资料目录的位置，以及需要保留的现有文件。
- 接入完整招聘流程时，提供兼容的 `get_jobs` 服务源码、发行版数据库和工具位置；招聘账号由本人完成登录。

详见 [手动安装与运行](../SETUP.md)、[个人资料格式](profile-format.md) 和 [招聘服务配置](automatic-delivery.md)。
