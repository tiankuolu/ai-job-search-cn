# 工作台操作演示

[![工作台操作演示节选](media/workbench-preview.gif)](media/workbench-demo.mp4)

[下载结果演示 MP4](https://raw.githubusercontent.com/tiankuolu/ai-job-search-cn/main/docs/media/workbench-demo.mp4) · [静态截图](media/workbench-preview.png)

录制日期：2026-11-06。时长约二十二秒，含中文字幕。
视频与上方动画展示实际处理结果，模型等待片段已经剪除。

## 视频内容

- JD 字段提取结果：公司、岗位、地点与任职条件。
- 岗位保存结果：完整职责与原始招聘来源。
- 模型分析结果：已有证据与待补充资料。
- 材料选项：中英文简历、项目职责与描述、自我描述。

本段录屏展示岗位导入与分析。简历生成、编辑、导出与投递的使用方法见 [工作流说明](automatic-delivery.md)。

## 演示资料

岗位来源：[牛客公开招聘页面](https://www.nowcoder.com/jobs/detail/458263)。录制使用其公开职责和要求的节选与转述，文件保存在 [公开岗位节选](examples/public-agent-jd.md)。招聘状态以原始页面为准。

候选人档案采用空白模板；项目资料仅描述公开仓库功能，并明确没有提供候选人身份或个人贡献。模型实际返回资料不足的判断，录制中保留了这一结果。

视频通过 Playwright 录制真实页面操作，封装为 H.264 MP4 并添加中文字幕。没有提交申请或联系招聘者。
