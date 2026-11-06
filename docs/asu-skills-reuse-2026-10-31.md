# ASu-skills 可复用内容与接入建议

核查日期：2026-10-31。

上游源码：[Hisn00w/ASu-skills，提交 d27fd2a](https://github.com/Hisn00w/ASu-skills/tree/d27fd2a3864c48472a5c8ed942410098ba9cd35f)。本地核查对象为当前工作目录中的实际文件，包含用户尚未提交的实现。

## 1. 为每条简历表述保存稳定的证据关联

**建议优先采用。** 本项目已经读取 candidate.md、preferences.md、evidence.md，写作和审查提示词也要求回查原始资料。ASu 进一步为每条表述设置稳定 ID，将原始事实、候选措辞、证据位置、确认状态、适用材料和面试细节放进同一条记录。

可复用文件：

- [career-claim-ledger-template.json](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/assets/career-claim-ledger-template.json)：JSON 字段结构。
- [claim-evidence-ledger.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/great-resume/references/claim-evidence-ledger.md)：确认状态与跨任务读写职责。
- [validate_claim_ledger.py](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/scripts/validate_claim_ledger.py)：必填字段、重复 ID、枚举值、日期和占位符检查。
- [evidence-recap/SKILL.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/evidence-recap/SKILL.md)：从开发对话与交付记录整理问题、决策、行动、完成状态、验证条件和面试追问的方法。

接入位置：`actions/common.py` 读取结构化证据；`analyze.py` 将要求关联到证据 ID；`apply.py`、writer 和 reviewer 传递相同 ID；`delivery/resume.py` 为简历条目保存证据引用；网页审查视图支持查看对应来源。个人证据文件保存在材料目录 `个人资料/`，现有 Markdown 可作为阅读视图。现有评测模块已经具有 `EvidenceRef(source, quote)`，可以复用其引用字段，补充跨任务稳定 ID。

采用其字段结构时补充源码版本、运行结果位置和指标条件。用户已经确认的事实直接继承确认状态。用户确认与代码、运行记录分别保存来源类型，避免因证据类型不同重复询问。原始事实与候选措辞分别维护，修改措辞不改变原始事实。

校验器需要适配项目已有的 Pydantic 与错误处理要求。它允许已确认记录具有空 sources，只验证结构与局部状态约束；接入后还需检查最终材料引用的 ID 存在、状态允许使用、适用目标符合当前岗位。

验收：以现有三个项目的真实证据生成两个岗位版本；每条关键项目表述能够定位原始事实和验证材料；两个版本的相同指标及条件一致；未知和已过期记录无法进入正式材料；更新措辞后原始事实保持原样。

## 2. 在 JD 匹配中区分表达、证据和能力的缺口

本项目已有 `Requirements Coverage`、独立 `Eligibility` 和辅助排序分数。现有分类为已覆盖、可改造覆盖、方向性缺口、弱条件。ASu 的五种证据状态能让后续动作更准确：已匹配、表达缺口、证据不足、真实缺口、待确认。

来源：[job-match/SKILL.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/job-match/SKILL.md)。

例如 FastAPI 经验已有代码，但简历遗漏，应调整表达；功能已经实现但缺少运行结果，应补充真实验证；尚未实现核心职责要求的能力，应安排对应开发；JD 没有披露指导形式，应记录待核实事项。每项状态对应不同的实际行动。

接入 `prompts/analyzer.md`、`workflows/analyze-job.md`、结构化评测规则与网页岗位详情。网页自动搜索另有 `delivery/service.py` 的 `MatchDecision`，也需传递逐项证据状态。将要求的重要性、证据状态、可申请性分别记录：必需条件和加分项属于要求属性；表达缺口和证据不足属于证据状态；适用与排除属于岗位判断。保留现有排序和 Eligibility 的职责。

验收：使用固定真实 JD 与现有档案核对分类；已实现但未充分表达的工作能够进入材料改写；缺少运行依据的工作进入验证清单；加分项缺失和一般信息未知继续允许准备申请；已确认硬性冲突准确排除。

## 3. 增加逐题追问、证据状态与薄弱内容复练

本项目已有面试准备材料、STAR 故事库、附 rubric 的练习卷与评分记录。ASu 值得借鉴的部分是持续交互：每道题预先确定必要证据，回答后记录已经支持的内容与缺口，决定继续追问、转换题目或结束。

可复用规范：

- [question-and-scoring-contract.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/interview/references/question-and-scoring-contract.md)：考察意图、必要证据、追问触发与停止条件。
- [interview-contract-and-session.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/interview/references/interview-contract-and-session.md)：轮次、时长、反馈方式和会话记录。
- [review-and-retry.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/interview/references/review-and-retry.md)：围绕薄弱表述生成变体、反事实和故障题。

接入 `actions/interview.py`、面试提示词、CLI 和网页会话入口。按项目表述保存 verified、partial、unverified、contradictory、not_covered，并关联证据 ID、回答原文、题目版本、追问深度和停止原因。未涉及的内容记录为 not_covered。已有 rubric 可以作为每道题必要证据的输入。

验收：真实完成一次岗位面试和一次薄弱内容复练；每轮只提出一个问题；提问标准在回答前保存；后续题目针对实际缺口；会话能够恢复；复练状态变化有新增回答证据；无法处理变体题时保留具体缺口。

上游这部分主要是提示词与会话规范，需要在我们的运行程序内实现持续状态。

## 4. 从源码生成可追问的项目讲解

可借鉴 [project-guide/SKILL.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/project-guide/SKILL.md) 与其课程规范：围绕真实场景组织阅读顺序，记录文件与符号位置、异步注册与消费关系、设计依据、失败处理和验证结果，再生成对应理解题。

对现有论文研读、旅行规划、求职系统三个项目，分别准备目标岗位最相关的执行过程。每项项目亮点都能通过源码位置和真实运行结果展开。代码只支持实现事实，设计动机和历史结果分别使用自己的依据。

接入 `workflows/interview-prep.md` 和面试准备动作，生成材料保存到既有 `面试准备/`。课程和练习按真实源码范围组织，问题数量由需要验证的知识决定。

上游 `scripts/project_guide.py` 负责描述检查与提示词构造，源码读取和讲解依赖宿主 Agent。接入时应沿用我们已有文件工具和模型调用记录。

验收：文件与函数定位有效；同步调用、事件触发与消费者注册均有来源；讲解覆盖实际异常处理；每道理解题关联具体项目过程；更新指定内容时保留用户答案和其他章节。

## 5. 将招聘回复与后续动作纳入现有投递记录

本项目已经实现材料准备、招聘平台发送、回执记录和防止重复发送。ASu 的 [offer/SKILL.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/offer/SKILL.md) 和 [email-monitoring.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/references/email-monitoring.md) 可补充收到回复后的处理：识别笔试、面试、录用与流程结束通知，保留证据来源和下一步动作。

[application-tracker.html](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/assets/application-tracker.html) 具备搜索、筛选、统计、JSON 合并导入与备份、CSV 导出。交互和导出设计可借鉴，数据接入 `delivery/service.py` 的现有持久化与历史页面。采用平台和岗位 ID 关联记录，保存事件发生时间、记录时间、来源、当前阶段及下一步期限。

上游进度表读取失败会返回初始数据，未知状态会转成“已投递”，合并依据为公司与岗位名称。接入时读取错误明确终止、未知状态单独保存，同名岗位通过真实岗位 ID 区分。保留每次状态事件，按实际发生时间形成当前进度，避免较早通知覆盖较新事实。

验收：使用已授权访问的真实招聘通知核对状态；自动回执记录为收到申请；面试通知生成实际时间和下一步；重复通知不重复新增；相同公司同名不同职位分别记录；历史事件和来源可以查询。

## 6. 复用简历编辑交互与页面密度检查

可参考 [assets/frame/editor.js](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/assets/frame/editor.js) 的文字编辑、字体调整、自动保存、HTML 下载和打印，以及 [page-balance-qa.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/make-resume/references/page-balance-qa.md) 的正文占用和溢出检查。

我们的 `delivery/resume.py` 已校验 A4 单页、正文完整、链接和字符边界。可新增正文占用高度、底部空白和最小字号检查，并在工作台提供结构化简历编辑。用户编辑内容写回 `ResumePlan` 和实际简历源文件，重新执行审查、编译及页面检查；浏览器缓存与服务记录保持明确的一致性。

上游 HTML 模板可以作为独立用户副本直接复用。与现有 React 页面整合时，需要适配 DOM、样式、持久化和状态管理。保留用户当前基版与学校、GPA、STAR、项目条目、打招呼语的既有要求。

上游 PDF 导出程序自行实现 CDP 客户端，并使用系统临时目录；字体加载失败也允许继续。若使用 HTML 导出，采用现有浏览器依赖，等待字体成功加载，中间文件保存到受 Git 忽略保护的项目目录。继续使用 PDF 解析库核查实际输出。

验收：真实编辑项目正文并保存，刷新与重新生成后内容一致；执行真实浏览器打印或现有 LaTeX 编译；核查最终单页、文本、链接、字号与底部空白，检查渲染图。

## 7. 增加企业官网申请表填写

上游 [job-apply/SKILL.md](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/skills/job-apply/SKILL.md) 的字段映射与填写后核查规范，可以补充现有四个平台之外的企业官网申请。将网站字段、拟填写内容、资料来源、是否缺失和实际填写结果分别保存，覆盖教育经历、项目经历、日期、级联选择和附件。

接入 `delivery/`，复用已经确认的材料包和现有浏览器连接。填写后重新读取页面显示值，检查截断、日期格式和附件状态。外部填写与提交继续依据用户实际授权范围执行，当前会话已有授权应持续使用。

验收：在用户授权的真实职位页面完成字段识别、填写、重新读取核查和附件检查；缺失字段保持明确状态；保留用户已填写内容；实际提交后按页面结果记录回执。

## 复用实施的依赖与验证

证据关联为岗位匹配、材料审查和面试复练提供共同引用。源码导学补充可讲解内容；招聘回复管理消费现有投递记录；简历编辑消费现有结构化数据。功能接入需同时覆盖 Python 提示词、助手工作流、接口、网页交互和对应真实验证。

上游 [interview-behavior-cases.yaml](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/tests/interview-behavior-cases.yaml)、`evidence-recap-cases.yaml`、`project-guide-course-behavior-cases.yaml` 是人工检查或后续 Agent Eval 输入。文件明确说明没有作为已执行的真实模型行为测试结果。可借用其中的期望行为，接入本项目 `jobsearch_agents/evaluation/`，结合真实材料、真实接口和原始执行记录验证。进度表与浏览器功能需要真实浏览器验证。

本次实际执行：三个相关 JavaScript 文件通过 `node --check`；`build-asu-resume.mjs --check` 通过；`sync-skill-catalog.mjs --check` 通过，核对九个入口。检查使用上游真实文件，未生成虚构求职记录。本次没有安装技能或修改业务程序。

## 来源与许可保存

上游 [LICENSE](https://github.com/Hisn00w/ASu-skills/blob/d27fd2a3864c48472a5c8ed942410098ba9cd35f/LICENSE) 标明 MIT 与 `Copyright (c) 2026 Hisn00w`。复制其代码或文档时，保存原版权及许可全文，记录来源 URL、固定提交和引入文件清单；本项目既有来源许可继续保留。模板中的示例身份、经历和数字在实际材料生成时由已确认资料填充。

本地能力的逐文件依据见 [asu-local-capabilities-2026-10-31.md](asu-local-capabilities-2026-10-31.md)。
