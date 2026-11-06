# 本地求职 Agent 能力核查

核查日期：2026-10-31。依据为当前工作区源码；本次未修改程序，未调用招聘平台或模型接口。

## 项目事实与证据管理

`ActionContext.read_profile()` 读取 `candidate.md`、`preferences.md`、`evidence.md`，缺少文件会立即终止。证据库模板已经记录成果场景、个人动作、结果和来源。申请材料生成与审查均接收这些原始资料。

源码依据：

- [资料读取](../jobsearch_agents/actions/common.py:54)。
- [证据库模板](../markets/china/profile/evidence.md:10)。
- [申请材料输入](../jobsearch_agents/actions/apply.py:43)。
- [事实审查](../jobsearch_agents/prompts/reviewer.md:10)。

运行轨迹记录模型输入消息、工具调用、事件和运行结果，已经具有自动整理项目证据所需的部分原始数据。[轨迹结构](../jobsearch_agents/runtime/trace.py:15) 与 [轨迹保存](../jobsearch_agents/runtime/trace.py:95) 可以作为证据提取动作的输入。

当前评测模块包含 `EvidenceRef(source, quote)`、关键事实数量和无依据事实数量，用于检查一次流程的材料质量。它具有引用校验所需的结构，但当前公开命令与资料模板中没有按稳定 `claim_id` 管理的项目事实记录，也没有将编程对话自动整理为个人动作、方案决策、交付状态和结果证据的动作。

源码依据：[评测数据模型](../jobsearch_agents/evaluation/models.py:6)、[评测事实检查](../jobsearch_agents/evaluation/judge.md:12)、[命令入口](../jobsearch_agents/cli.py:35)。

可扩展入口：在 `actions/` 增加项目证据整理动作，沿用 `ActionContext`、`Trace` 和评测中的来源引用结构。提取结果需要保存原文来源、适用条件和本人贡献依据；经过核实的项目事实供岗位分析、材料生成和面试复用。

## 岗位匹配

岗位分析已经逐项读取完整 JD，给出六个维度的辅助分数、要求覆盖表、优势、缺口、可申请性、补强动作和未知信息。可申请性使用 `applicable / excluded / unknown`，明确独立于评分，并要求保留符合当前能力的申请动作。

源码依据：

- [岗位分析输入与保存](../jobsearch_agents/actions/analyze.py:79)。
- [要求分类](../jobsearch_agents/prompts/analyzer.md:36)。
- [可申请性与行动](../jobsearch_agents/prompts/analyzer.md:45)。
- [输出结构](../jobsearch_agents/prompts/analyzer.md:80)。

当前要求分类为“已覆盖”“可改造覆盖”“方向性缺口”“弱条件”。“已有经历但表述未充分呈现”以及“经历线索存在但证据不足”尚未成为独立的状态。增加这两个状态能够分别触发材料改写和证据核查，使每项缺口对应明确动作。

自动搜索页面另有较简短的匹配结果 `MatchDecision`，字段为 `eligible`、`reason`、`evidence`。[结构定义](../jobsearch_agents/delivery/service.py:27) 与 [实际调用](../jobsearch_agents/delivery/service.py:129) 说明网页搜索暂时没有直接复用完整的要求覆盖结果。若引入更细的匹配状态，需要同时覆盖完整分析和网页匹配两个入口。

`tools/rank_state.py` 保留四个维度的历史权重及旧抓取状态路径。当前工具注册文件明确说明该文件使用旧口径；它不能作为现有六个维度岗位分析的实现依据。

源码依据：[旧工具配置](../tools/rank_state.py:49)、[当前工具说明](../jobsearch_agents/tools_wrap/key_tools.py:1)。

可扩展入口：调整 `prompts/analyzer.md` 的覆盖分类及输出要求，保持工作流说明一致；为 `DeliveryService` 的匹配结果增加对应的逐项证据结构，并在前端展示具体要求和证据来源。

## 面试准备、练习与评分

现有面试功能包含以下实际动作：

1. `run_interview()` 根据 JD、已有评估、个人资料和证据库生成准备材料。[输入与执行](../jobsearch_agents/actions/interview.py:19)。
2. `run_storybank()` 从个人资料生成 STAR 故事库。[故事库提示词](../jobsearch_agents/actions/interview.py:65)。
3. `make_practice_sheet()` 根据故事库和可用的岗位材料生成 8–10 个问题，每题带 3–5 条评分要点及难度。[练习要求](../jobsearch_agents/actions/interview.py:100)。
4. `grade_practice()` 读取完整练习卷和答案文件，逐题评分、计算平均分并追加练习记录。[评分要求](../jobsearch_agents/actions/interview.py:147) 与 [记录保存](../jobsearch_agents/actions/interview.py:178)。

当前 `run_interview()` 的执行路径只有生成和保存，未调用 reviewer，也未使用传入的 `max_review_rounds`。该动作没有构成生成与审查循环。当前面试提示词要求技术问题、行为问题、差距应对及反问清单，未建立逐条事实的能力验证状态。

源码依据：[生成与保存](../jobsearch_agents/actions/interview.py:40)、[准备材料格式](../jobsearch_agents/prompts/interview.md:9)。

当前练习已经提前产生评分要点。进一步借鉴时，应补充评分要求版本、明确得分条件、未能确认的证据、追问终止条件，以及同一能力的变体题练习记录。当前命令入口是整份练习卷与整份答案文件评分，尚无一次提出一个问题、根据回答继续追问的持久会话入口。

源码依据：[面试命令](../jobsearch_agents/cli.py:64) 与 [批量答案评分](../jobsearch_agents/actions/interview.py:156)。

可扩展入口：保留已有故事库和练习卷，围绕稳定 `claim_id` 新增会话状态与逐题回答动作；将薄弱能力、证据不足和变体练习记录关联到对应项目事实。面试工作流已经要求读取代码和运行依据，可以继续作为实际工具访问规范。[工作流要求](../markets/china/workflows/interview-prep.md:3)。

## 简历生成与网页投递

申请材料已有 writer 与 reviewer 的独立生成、审查循环，返回每轮意见和最终通过状态。[申请材料循环](../jobsearch_agents/actions/apply.py:83)。简历生成会进一步使用 Pydantic 验证结构化字段、审查内容，再通过 Jinja2 和 Tectonic 编译 PDF。

PDF 检查已经覆盖 A4 单页、全部预期正文、文字边界、链接和导出图片有效性。[简历生成](../jobsearch_agents/delivery/resume.py:86) 与 [编译检查](../jobsearch_agents/delivery/resume.py:127)。

投递服务支持 BOSS、猎聘、牛客、实习僧四个平台，由相邻 `get_jobs` 服务负责实际浏览器操作。投递前检查材料状态、防止同一岗位重复联系、核验 PDF 与图片哈希；发送操作先保存需要核实的状态，再根据回执确认是否完成。[支持平台](../jobsearch_agents/delivery/platforms.py:4)、[发送流程](../jobsearch_agents/delivery/service.py:214)、[回执判定](../jobsearch_agents/delivery/platforms.py:8)。

当前公开投递请求是对平台服务传递岗位 URL、打招呼语、图片和 PDF 路径。项目中尚未出现面向任意企业官网的页面字段清单、个人资料到字段的映射、下拉选项处理及逐字段填写后核对记录。

可扩展入口：在现有 `delivery/` 中增加企业官网申请动作及字段映射数据模型，沿用材料包、哈希和回执记录。浏览器连接由现有环境选择；字段判断规范可以与具体浏览器工具分离。

## 投递状态与跟进

`delivery-status.csv` 当前保存岗位文件、公司、职位、阶段、投递日期、更新时间和备注。命令支持人工更新阶段，程序实际确认完成发送后会写入“已投递”。

源码依据：[状态字段](../jobsearch_agents/actions/status.py:10)、[人工更新](../jobsearch_agents/actions/status.py:57)、[投递结果写入](../jobsearch_agents/delivery/service.py:248)。

投递数据库另行保存 jobs、packages、tasks，以及材料版本、回执与执行状态。[数据库定义](../jobsearch_agents/delivery/service.py:34)。当前“申请执行状态”已经具备回执依据；招聘进度表尚无独立的下一步动作、截止时间、面试时间和进度事件来源字段。公开命令与动作中尚无招聘邮件、聊天或截图的进度提取入口。

可扩展入口：保留现有实际发送记录，增加招聘事件记录与下一步动作字段。每条事件记录原始来源、发生时间、提取状态和关联岗位；普通回执仅增加投递事件，后续进度由对应来源支持。

## 核查方式

本次读取了动作、提示词、工作流、模板、网页投递服务、命令入口和评测数据模型，并通过全文搜索检查面试会话、复练、事实记录、邮件导入与跟进字段的实现入口。没有执行真实模型任务或平台发送。本文件记录源码中可确认的行为；招聘平台真实发送能力的历史验证范围见 [自动搜索与简历投递](automatic-delivery.md)。
