import hashlib
import json
from datetime import date
from pathlib import Path

import frontmatter
from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Z]+$")
    file: str = Field(min_length=1)


class ConditionalExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class ResumePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_skills: list[str] = Field(default_factory=list)
    skill_categories: list[str] = Field(default_factory=list)
    fixed_awards: list[str] = Field(default_factory=list)
    jd_required_experiences: list[ConditionalExperience] = Field(default_factory=list)


def conditional_experience_issues(content: str, job: str, preferences: ResumePreferences) -> list[str]:
    issues = []
    normalized = "".join(content.split()).casefold()
    for rule in preferences.jd_required_experiences:
        if rule.keyword.casefold() not in job.casefold():
            if any("".join(term.split()).casefold() in normalized for term in [rule.keyword, *rule.aliases]):
                issues.append(f"JD 未提到 {rule.keyword}，简历需要删除该经历及相关技能")
    return issues


class ProjectIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=1)
    verified_on: date
    projects: list[ProjectSource] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self):
        if len({item.id for item in self.projects}) != len(self.projects):
            raise ValueError("项目事实档案包含重复项目编号")
        if len({item.file for item in self.projects}) != len(self.projects):
            raise ValueError("项目事实档案包含重复文件")
        return self


def personal_information(source: str) -> str:
    lines = source.splitlines(keepends=True)
    tokens = MarkdownIt().parse(source)
    headings = [(token.map[0], tokens[index + 1].content)
                for index, token in enumerate(tokens)
                if token.type == "heading_open" and token.tag == "h2"]
    excluded = set()
    for index, (start, title) in enumerate(headings):
        if title in {"项目经历", "专业技能"}:
            end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
            excluded.update(range(start, end))
    return "".join(line for index, line in enumerate(lines) if index not in excluded)


def read_resume_profile(profile_dir: Path) -> dict[str, str]:
    preferences = (profile_dir / "preferences.md").read_text(encoding="utf-8")
    resume_preferences = ResumePreferences.model_validate(frontmatter.loads(preferences).get("resume", {}))
    directory = (profile_dir / "项目事实档案").resolve(strict=True)
    manifest = ProjectIndex.model_validate_json((directory / "index.json").read_text(encoding="utf-8"))
    facts = []
    sources = []
    for project in manifest.projects:
        path = (directory / project.file).resolve(strict=True)
        if path.parent != directory or path.suffix.lower() != ".md":
            raise ValueError(f"项目事实档案路径无效：{project.file}")
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"项目事实档案为空：{path}")
        facts.append(f"# 项目编号 {project.id}\n来源：{path}\n\n{content}")
        sources.append({"id": project.id, "path": str(path),
                        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    return {
        "candidate": personal_information((profile_dir / "candidate.md").read_text(encoding="utf-8")),
        "preferences": preferences,
        "resume_preferences": resume_preferences.model_dump_json(),
        "project_facts": "\n\n".join(facts),
        "project_index": manifest.model_dump_json(),
        "project_sources": json.dumps(sources, ensure_ascii=False),
    }


ASU_FILES = (
    "skills/great-resume/SKILL.md",
    "skills/great-resume/references/claim-evidence-ledger.md",
    "skills/make-resume/SKILL.md",
    "skills/make-resume/references/page-balance-qa.md",
)

RESUME_POLICY = """
本项目执行约定：以当前任务指定的输出格式与最新工作区规则为准。
个人身份、教育、联系方式与荣誉来自个人信息，意向与到岗安排来自已确认偏好。
项目事实来自项目事实档案，按稳定编号记录内部 Resume Evidence，审查每项主张、来源、
个人贡献及指标条件。已有申请包和评估报告中的项目描述也需要与事实档案核对。
按 JD 形成一个岗位定位，选择相关项目、顺序和篇幅；只使用已确认事实。
根据档案推导技能时，需要具体实现支撑。内部证据编号与源文件路径仅保存在内部记录中。
专业技能采用“分类：具体技能”的形式，按 resume.skill_categories 保留类别，按 JD 补充相关类别。
项目正文按 JD 的职责与技术要求重新组织，直接写关键设计、本人行动与可验证成果。
采用积极、有力的经历表达，充分展开已有能力；实验规模与配置融入成果句，来源与归属记录保存在内部证据。
项目档案提供事实依据；写作时选取相关事实形成当前岗位的项目要点。
用户已确认的通用技能直接使用；竞赛与语言使用 preferences.md 中固定内容和顺序。
遵循 resume.jd_required_experiences，只有 JD 明确提到指定关键词时，简历才可以出现对应经历及相关技能。
完成 great-resume 的经历改写和证据审查，再由 make-resume 制作可编辑 HTML 与 PDF。
使用完整自然的中文词语，项目名称和正文省略个人项目、独立开发、独立完成等角色标签。
采用现有 ASu 单栏模板，保持纯文字身份区域和真实链接，照片字段省略。
必须写满 A4 一页，正文占可用高度 95%—100%，目标 97%—99%，最小字号 9pt。
页面占用采用本项目此项要求。占用不足时展开相关事实、设计与验证条件并重新审查。
正式交付必须经过真实浏览器导出，检查单页、文字、链接、字号、页面占用和内容边界。
"""


def asu_guidance(repo_root: Path) -> tuple[str, list[dict[str, str]]]:
    directory = repo_root / "third_party" / "asu-skills"
    guidance = []
    sources = []
    for name in ASU_FILES:
        path = directory / name
        content = path.read_text(encoding="utf-8")
        guidance.append(f"# ASu 技能原文：{name}\n\n{content}")
        sources.append({"path": str(path), "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    return "\n\n".join(guidance) + "\n\n" + RESUME_POLICY, sources
