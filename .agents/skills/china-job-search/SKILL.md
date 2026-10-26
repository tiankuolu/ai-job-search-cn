---
name: china-job-search
description: 根据真实档案与项目证据搜索中国实习岗位、分析匹配、生成申请材料、排序岗位及准备面试。
---

# 中国实习求职

先读取项目 `AGENTS.md` 及工作区根目录 `AGENTS.md`。
读取 `markets/china/workflows/runtime.md` 和 `index.md`，再读取当前任务对应的工作流。
规则、模板与工具路径以项目目录为基准，个人材料路径以 runtime.md 为准。

支持 `setup`、`scrape`、`analyze`、`apply`、`rank`、`interview`，以及对应自然语言请求。
完整 JD 可以直接保存后分析；用户提供链接时，先读取完整岗位正文。
个人事实来自材料目录的 `个人资料/`，项目成果需要对应代码或真实运行依据。
保护已有个人文件，岗位分析优先使用现有公司岗位目录。
输出后读取实际文件，完成必要验证并提供完整路径。
