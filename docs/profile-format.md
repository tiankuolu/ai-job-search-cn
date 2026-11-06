# 个人资料与项目档案

个人资料保存在配置的材料目录，包含 candidate.md、preferences.md 和 evidence.md。
使用 markets/china/profile 中的空白模板，字段名称保持不变。
教育背景表格保留“时间”“学校”“学位 / 专业”“GPA”四个表头，可以增加其他列。
GPA 未提供时保留空白，学校、时间和学位采用真实记录。

preferences.md 可以使用 YAML frontmatter 配置 resume.required_skills、resume.skill_categories、resume.fixed_awards 和 resume.jd_required_experiences。
这些字段分别控制必需技能、技能类别、荣誉顺序和按 JD 启用的经历。

简历生成读取“个人资料/项目事实档案/index.json”。该文件包含 version（固定为 1）、verified_on（实际核查日期）及 projects。
projects 每项包含唯一的 id（大写英文字母）与 file（同目录 Markdown 文件名称）。
每个项目档案使用以项目 id 加连字符开头的一级或二级标题记录稳定事实编号。
事实内容写清本人行动、实现、验证条件与结果，并记录实际来源。
项目档案为空、编号缺失或引用路径无效时，程序会终止并指出对应问题。

工作区根目录的 AGENTS.md 可以从 markets/china/workspace-rules.md 复制，再按实际要求填写。
个人事实与访问凭据保留在本地，公共仓库仅保存空白模板。
