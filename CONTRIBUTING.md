# 贡献说明

## 项目范围

项目面向中国大陆求职，执行环境为 Codex 和 ZCode。
两者共用根目录 `AGENTS.md` 与 `markets/china/workflows/`。
Python 程序、模型提示词和 Markdown 工作流共同维护，目录约定见 `AGENTS.md`。

## 修改规范

- 中国求职动作映射维护在 `markets/china/workflows/index.md`。
- 公开招聘来源维护在 `markets/china/sources.json` 和 `search-queries.md`。
- 个人事实保存到材料目录的 `个人资料/`，公共模板保留占位符。
- 使用真实文件和实际工具结果验证修改。
- 修改使用方式时，同步更新 README、配置说明与首次投递说明。
- 保留 MIT License 和开源来源说明。

## 检查

安装 `requirements-dev.txt` 中的依赖，在仓库根目录执行：

```powershell
python tools/lint_skills.py
python tools/security_guards.py
python -m pytest tests/test_workspace_layout.py -q --basetemp=.artifacts/pytest
```

涉及简历或求职信模板时，运行相应编译和 PDF 检查。
报告实际执行的检查范围与结果。
