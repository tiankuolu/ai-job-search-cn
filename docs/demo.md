# 工作台操作演示

[![风格章节动画与真实工作台执行结果](media/workbench-overview.gif)](media/workbench-overview.mp4)

[下载三十五秒完整演示](https://raw.githubusercontent.com/tiankuolu/ai-job-search-cn/main/docs/media/workbench-overview.mp4) · [二十二秒执行录屏](https://raw.githubusercontent.com/tiankuolu/ai-job-search-cn/main/docs/media/workbench-demo.mp4) · [静态截图](media/workbench-preview.png)

制作与录制日期：2026-11-06。完整演示三十五秒，1920×1080、30 fps，H.264，无声，含中文字幕。章节动画与真实执行画面交替展示，模型等待片段已经剪除。

真实执行部分共约二十二秒，依次展示字段提取、岗位保存、模型分析和材料选项。每个章节前有动画引导，执行时保留对应说明。

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

## 视觉与制作

章节动画采用 [XiaoyeCodes/code-animation-prompts](https://github.com/XiaoyeCodes/code-animation-prompts) 中的 **H1 Biennale Yellow** 风格：羊皮纸底色、太阳黄色、靛蓝衬线文字与刻度环。参考版本为 `2e6396abb45c2d183e91bc5a6583597411860217`。

原始素材整理与 H1 中文提示词改写来自俯仰观照，技能封装与工具由 XiaoyeCodes 提供。素材约定为免费使用、免费分享，请勿将素材合集包装为收费课程、付费技能或其他收费内容出售；详情见原仓库的 [来源与许可](https://github.com/XiaoyeCodes/code-animation-prompts/blob/main/LICENSE.md)。

动画通过确定性时间接口渲染，与真实录屏合成。成片完整解码一千零五十帧，检查分辨率、时长、帧率和有效画面，并逐秒检查个人识别信息。
