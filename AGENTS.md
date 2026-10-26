# 中国实习求职 Agent

## 共同要求

读取工作区根目录 `../../../AGENTS.md`。求职目标、真实性、机会判断和材料表达遵循其中约定。
本目录包含 Python 程序、求职技能、工作流、模板、工具与测试，作为同一个项目维护。

## 路径

- 工作区默认取本项目向上三级目录，当前为 `D:\找实习`。
- 简历材料默认在工作区下的 `卢天阔_AI-Agent简历/`。
- 个人资料：简历材料下 `个人资料/candidate.md`、`preferences.md`、`evidence.md`。
- 岗位：已有公司岗位目录的 `岗位JD.md`，以及 `岗位记录/inbox/*.md`。
- 评估、公司调研、申请包和状态：`岗位记录/evaluated/`。
- 故事库、练习卷与评分：`面试准备/`。
- 基版与定制简历：简历材料根目录和各公司岗位目录，沿用现有命名。
- 模型调用轨迹：本项目 `runs/`；开发验证中间文件：本项目 `.artifacts/`。两者受到 Git 忽略保护。

`JOBSEARCH_WORKSPACE_ROOT` 可指定工作区，`JOBSEARCH_MATERIALS_ROOT` 可指定材料目录。
Python 相对输入路径以工作区为基准；文档中的规则、模板和工具路径以本项目为基准。
变更数据目录时同步修改 `jobsearch_agents/actions/common.py`、技能、工作流和使用说明。

## 执行入口

Python 入口为 `py -3.11 -m jobsearch_agents --help`，支持岗位搜索、分析、申请材料、排序、状态、调研和面试练习。
模型配置来自 `JOBSEARCH_LLM_BASE_URL`、`JOBSEARCH_LLM_MODEL`、`JOBSEARCH_LLM_API_KEY`，禁止输出密钥。
Codex、ZCode 使用 `.agents/skills/china-job-search/SKILL.md` 和 `markets/china/workflows/index.md`。
工作流和 Python 提示词共同遵循根目录求职要求；修改规则时分别检查两处实际行为。

## 维护与验证

修改前读取当前文件，保留用户已经完成的删除与调整。遵循当前会话中的代码与操作约束。
个人资料迁移需要核验内容，初始化不得覆盖已有档案。模板保存在 `markets/china/profile/`。
分析以完整岗位原文为输入，已有公司岗位目录以目录名称区分岗位，避免 `岗位JD.md` 相互覆盖。
评估文件使用岗位标识命名，申请、调研与面试材料按同一标识查找；排序只读取评估报告。
测试使用真实工具和真实文件；需要模型的验证使用真实接口，模型配置缺失时如实报告。
验证中间文件写入 `.artifacts/`。真实个人信息与开发验证文件不得提交至项目仓库。
保留 LICENSE 及开源来源说明。删除继承文件时同时检查文档、测试和工具中的引用。
