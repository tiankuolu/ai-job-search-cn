# 求职动作入口

先读取 `markets/china/workflows/runtime.md`，确定材料目录与当前输入。

- `setup`：`setup-profile.md`，初始化或更新个人资料。
- `scrape [方向或城市]`：`scrape-jobs.md`，搜索并保存公开岗位。
- `analyze <岗位文件>`：`analyze-job.md`，分析匹配与相关项目证据。
- `apply <岗位文件>`：`apply-job.md`，生成申请包与用户要求的简历文件。
- `rank`：`rank-jobs.md`，排序已有岗位。
- `interview <岗位文件或评估>`：`interview-prep.md`，准备项目讲解与追问。

路径缺失时先搜索已有材料。读取用户指定的完整 JD，所需个人资料来自材料目录。
Python 的附加动作与参数见 `py -3.11 -m jobsearch_agents --help`。
