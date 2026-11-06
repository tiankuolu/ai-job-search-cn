# 申请材料

按 runtime.md 读取完整 JD、个人资料、对应评估和已有公司调研。
中文沟通模板位于项目 `markets/china/templates/`。
涉及基版、岗位定制简历或简历项目正文时，必须完整读取并执行项目 `markets/china/resume-writing.md` 中的 STAR 写作与审查规范。
简历提升与制作同时读取 `markets/china/resume-enhancement.md` 和 `third_party/asu-skills/skills/great-resume/SKILL.md`、`make-resume/SKILL.md`，默认采用 ASu 单栏高密度模板。
申请包写入材料目录 `岗位记录/evaluated/<岗位标识>-application.md`。

申请包使用 Python writer 提示词中的章节：`Supported Positioning`、`BOSS Greeting`、`Recruiter Message`、`Chinese Cover Letter / Email`、`Resume Delivery Note`、`Resume Tailoring Suggestions`、`Resume Project Experience`、`Resume Evidence`、`Interview Focus`、`Gaps To Keep Honest`、`User Confirmation Needed`。
`Resume Project Experience` 提供可以直接用于简历的项目正文。逐个主要项目检查 STAR 要素、个人归属与结果依据，完成审查后再写入简历源文件。
打招呼语的简短版与完整版均采用当前偏好中确认的开头，随后结合岗位核心职责、一项最强相关成果与已确认到岗条件；私信和求职信保持相同事实。
对外正文直接表达相关能力，内部准备与待确认事项保存于申请包的内部章节。
只使用有依据的经历、技能、指标和个人承诺，未经用户表达意愿不得承诺额外试做。

用户要求简历时，读取材料目录的 `个人资料/candidate.md` 中个人信息、`preferences.md` 和 `项目事实档案/index.json` 列出的全部档案，根据完整 JD 按 ASu 方法完成定位、经历改写和内部证据关联。项目主张按稳定编号核对来源与条件；需要更新事实时核查相应源码与实际记录。执行 `py -3.11 -m tools.make_resume --job <岗位JD路径> --output <新目录>` 生成并审查结构化正文，使用 ASu 模板生成可编辑 HTML，再以真实浏览器导出 PDF 和预览图。必须满足 A4 单页、页面占用 95%—100%、最小字号 9pt。
继续使用已有公司岗位目录；新岗位建立 `公司-岗位-实习津贴/`，保存 JD、简历源文件、成品及 `打招呼语.md`。
实际导出并完成 A4 单页、文字、链接、字号、页面占用与渲染图检查，再报告文件完成状态。比较任务保留已有岗位文件，使用单独目录保存新版。确认可直接发送的正文与文件后，按用户授权处理外部发送。
