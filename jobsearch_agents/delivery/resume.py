import json
import shutil
import subprocess
import unicodedata
import uuid
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Annotated

import pdfplumber
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from PIL import Image
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pypdf import PdfReader

from ..actions.apply import parse_verdict
from ..actions.common import ActionContext, REPO_ROOT, RUNS_DIR
from ..prompts import load_prompt
from ..resume_sources import ResumePreferences, asu_guidance, conditional_experience_issues
from ..runtime import Agent, OpenAICompatClient
from ..runtime.trace import Trace
from .rendering import merge_resume_content
from .filenames import browser_file_uri, filesystem_path


MIN_FILL_PERCENT = 95
MAX_FILL_PERCENT = 100


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")
    school: str = Field(min_length=1)
    dates: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    gpa: str


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    role: str
    link: str = ""
    bullets: list[Annotated[str, Field(min_length=1)]] = Field(min_length=2, max_length=4,
                              description="按JD组织的技术贡献要点，每条用简短标题与具体工程动作展开实现机制、设计取舍及可验证成果")


class ResumePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    intention: str
    phone: str
    email: str
    github: str
    availability: str
    education: list[Education] = Field(min_length=1)
    projects: list[Project] = Field(min_length=2, max_length=3)
    awards: list[str] = Field(min_length=1, max_length=12)
    skills: list[str] = Field(min_length=2,
                              description="每项使用分类名称、中文冒号与具体技能，类别遵循个人偏好并按JD补充")
    greeting: str = Field(min_length=1, max_length=140,
                          description="发送给招聘者的完整版打招呼语，最多140个字符")

    @field_validator("education")
    @classmethod
    def check_education(cls, values: list[Education]) -> list[Education]:
        if len({(item.school, item.dates) for item in values}) != len(values):
            raise ValueError("教育背景包含重复的学校与时间")
        return values

def normalize(value: str) -> str:
    # PDF 字体可能将居中点映射为数学居中点，按等价字形核对正文。
    return "".join(unicodedata.normalize("NFKC", value).replace("∙", "·").split())


def resume_preference_issues(plan: ResumePlan, preferences: ResumePreferences, job: str = "") -> list[str]:
    issues = conditional_experience_issues(plan.model_dump_json(), job, preferences)
    if preferences.fixed_awards and plan.awards != preferences.fixed_awards:
        issues.append("竞赛与语言必须逐字采用固定条目及顺序：" + json.dumps(preferences.fixed_awards, ensure_ascii=False))
    skills = normalize(" ".join(plan.skills)).casefold()
    for required in preferences.required_skills:
        if normalize(required).casefold() not in skills:
            issues.append(f"专业技能必须包含已确认表述：{required}")
    categories = {skill.partition("：")[0].strip() for skill in plan.skills if "：" in skill}
    for category in preferences.skill_categories:
        if category not in categories:
            issues.append(f"专业技能需要单独列出分类：{category}")
    if preferences.skill_categories and any("：" not in skill for skill in plan.skills):
        issues.append("专业技能每项需要采用分类名称、中文冒号与具体技能的格式")
    return issues


def build_resume(client: OpenAICompatClient, ctx: ActionContext, job: str, application: str,
                 output: Path, tools: dict, trace: Trace,
                 progress: Callable[[str], None] | None = None, revision: str = "") -> dict:
    profile = ctx.read_resume_profile()
    preferences = ResumePreferences.model_validate_json(profile["resume_preferences"])
    _, skill_sources = asu_guidance(REPO_ROOT)
    trace.emit("resume.skills", skills=["great-resume", "make-resume"], sources=skill_sources)
    trace.emit("resume.sources", index=json.loads(profile["project_index"]),
               sources=json.loads(profile["project_sources"]))
    bundle = json.dumps(profile, ensure_ascii=False)
    bundle += "\n工作区最新确认规则（与旧档案冲突时优先采用）：\n" + (ctx.repo_root / "AGENTS.md").read_text(encoding="utf-8")
    instructions = (
        load_prompt("writer") + "\n本次负责将已通过审查的申请包整理为单页简历数据。"
        "只输出符合以下 JSON Schema 的 JSON 对象，不使用代码围栏。"
        "greeting、awards、skills 只允许放在根对象；projects 每项只包含 name、role、link、bullets。"
        "全部字段必须来自候选人资料或已通过审查的申请包。学校名称遵循 preferences.md，"
        "硕士学校与培养单位分别处理，教育字段只填学校。"
        "education.dates 使用个人信息中的起止年份；degree 包含学历及在读状态，专业按当前个人资料和偏好填写，本科省略专业名称。"
        "education.gpa 按当前个人资料填写，原文未提供时保持为空，不推测数值或满分制度。"
        "awards 按 resume_preferences.fixed_awards 原样保留全部条目及顺序。"
        "skills 中必须保留 resume_preferences.required_skills 的完整表述，可合并到相关技能条目中。"
        "skills 按 resume_preferences.skill_categories 分别列出编程语言、前端开发、后端开发、服务与部署等类别；"
        "每项使用分类名称和中文冒号开头，根据JD增加Agent、检索或评测等相关类别。"
        "role 字段仅供内部记录贡献归属，不输出到简历。项目 name 与 bullets 省略个人项目、独立开发、独立完成等角色标签，保留具体问题、行动和结果。"
        "使用 ASu 简历提升方法，按JD核心职责选取事实，写清关键技术设计、个人行动和已验证成果。"
        "项目按岗位相关性排序，每条正文采用简短的技术贡献标题和中文冒号开头。"
        "直接展开实现机制、技术取舍和结果；项目整体覆盖STAR信息，每条围绕独立贡献组织。"
        "条目以开发、设计、实现、构建、优化等具体工程动作展开，根据JD选择有技术深度的机制与成果。"
        "项目正文与技能长度根据相关事实和实际页面高度安排；"
        "最终简历必须写满 A4 一页，正文占可用高度的 95% 至 100%，目标为 97% 至 99%。"
        "根据岗位展开有依据的项目问题、关键设计、实现行动和验证结果。"
        "核心项目采用三至四条充分展开的正文，相关技能写清实际使用方式。"
        "保留完整技术因果与验证条件，优先使用实际能力、效果和故障验证结果。"
        "greeting 使用申请包中已通过审查的完整版打招呼语，"
        "开头遵循当前个人偏好，身份和到岗条件必须有当前资料依据。"
        "github 与项目 link 必须使用完整 HTTPS URL，其他字段全部为纯文本。\n"
        + json.dumps(ResumePlan.model_json_schema(), ensure_ascii=False)
    )
    writer = Agent("writer", instructions, client.with_json_output(), trace=trace)
    reviewer = Agent("reviewer", load_prompt("reviewer") + "\n本次只审查结构化简历 JSON。"
                     "只检查 JSON 中的简历和打招呼语，不要求申请包章节。"
                     "greeting 是唯一的完整版打招呼语，按140个字符上限审查。"
                     "本任务无需简短版打招呼语，80字规则只适用于申请包的简短版字段。"
                     "逐项检查学校名称、个人事实、数字归属和岗位匹配，并按原格式输出 VERDICT。",
                     client, trace=trace)
    base_prompt = f"# 岗位\n{job}\n# 资料\n{bundle}\n# 申请包与证据\n{application}"
    if revision:
        base_prompt += "\n# 用户修改要求\n" + revision
    prompt = base_prompt
    layout_feedback = ""
    plan = None
    for round_no in range(6):
        if progress:
            progress("正在编写定制简历与打招呼语…")
        plan = ResumePlan.model_validate_json(writer.run(prompt))
        if progress:
            progress("正在检查简历内容…")
        review = reviewer.run(f"# 资料\n{bundle}\n# 岗位\n{job}\n# 申请包与证据\n{application}\n# 简历\n{plan.model_dump_json()}")
        verdict = parse_verdict(review)
        preference_issues = resume_preference_issues(plan, preferences, job)
        if preference_issues:
            verdict["pass"] = False
            verdict["violations"] = [*verdict.get("violations", []), "固定偏好"]
            review += "\n固定偏好检查：\n" + "\n".join(preference_issues)
        trace.emit("resume.review", round=round_no + 1, **verdict)
        prompt = base_prompt + f"\n# 上一稿\n{plan.model_dump_json()}\n# 审查意见\n{review}" + layout_feedback
        if not verdict["pass"]:
            continue
        if progress:
            progress("正在检查简历是否写满一页…")
        trial = trace.run_dir / trace.run_id / "layout" / f"round-{round_no + 1}"
        layout = fit_resume_layout(plan, trial, tools.get("browser_channel", "msedge"))
        trace.emit("resume.layout", round=round_no + 1, **layout)
        if (MIN_FILL_PERCENT <= layout["fill_percent"] <= MAX_FILL_PERCENT
                and not layout["horizontal_overflow"] and layout["min_font_pt"] >= 9):
            break
        if progress:
            progress("正在根据实际版面调整简历内容…")
        layout_feedback = (f"\n# 最近通过事实审查稿件的实际排版\n{json.dumps(layout, ensure_ascii=False)}\n"
                   "正文占用必须达到可用高度的95%至100%，目标97%至99%，保持最小字号9pt。"
                   "根据测得的占用比例调整正文长度。占用不足时，充分展开现有证据中的"
                   "关键设计、实现过程、具体问题和验证结果，保持内容与岗位相关；"
                   "超出页面时精简重复措辞。每条事实均需有输入资料支持。")
        prompt = base_prompt + f"\n# 上一稿\n{plan.model_dump_json()}\n# 审查意见\n{review}" + layout_feedback
    else:
        raise ValueError("简历在内容与单页占用检查后仍未达标，请调整相关经历或修改要求")
    return render_resume(plan, output, tools, progress, body_font_pt=layout["body_font_pt"])


def write_resume_html(plan: ResumePlan, output: Path, body_font_pt: float = 10.5,
                      render_source: tuple[str, dict] | None = None) -> Path:
    output = filesystem_path(output)
    output.mkdir(parents=True, exist_ok=False)
    template_dir = REPO_ROOT / "jobsearch_agents" / "delivery" / "templates"
    environment = Environment(loader=FileSystemLoader(template_dir), undefined=StrictUndefined,
                              autoescape=True, trim_blocks=True, lstrip_blocks=True)
    template = environment.get_template("resume.html.j2")
    source = template.render(**plan.model_dump(), body_font_pt=body_font_pt, existing_main="", existing_styles="")
    if render_source:
        current, previous = render_source
        main, styles = merge_resume_content(current, source, previous, plan.model_dump())
        source = template.render(**plan.model_dump(), body_font_pt=body_font_pt, existing_main=main, existing_styles=styles)
    source_path = output / "简历.content.html"
    source_path.write_text(source, encoding="utf-8")
    (output / "resume.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (output / "打招呼语.md").write_text(plan.greeting, encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        raise FileNotFoundError("生成 ASu 可编辑简历需要 Node.js")
    builder = REPO_ROOT / "third_party" / "asu-skills" / "scripts" / "build-asu-resume.mjs"
    html = output / "简历.html"
    subprocess.run([node, str(builder), str(source_path), str(html)],
                   check=True, capture_output=True, text=True, encoding="utf-8")
    return html


def fit_resume_layout(plan: ResumePlan, root: Path, browser_channel: str,
                      render_source: tuple[str, dict] | None = None) -> dict:
    layouts = []
    html = write_resume_html(plan, root / "measurement", body_font_pt=10.5, render_source=render_source)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=browser_channel, headless=True)
        try:
            page = browser.new_page(viewport={"width": 718, "height": 1066}, locale="zh-CN")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(browser_file_uri(html), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.emulate_media(media="print")
            style = page.add_style_tag(content="body {font-size:10.5pt;}")
            primary_fonts = (10.5, 10.75, 11, 10.25, 10, 9.75, 9.5, 9.25, 9)
            fonts = (*primary_fonts, *(9 + index / 8 for index in range(17) if 9 + index / 8 not in primary_fonts))
            for font_pt in fonts:
                style.evaluate("(element, font) => element.textContent = `body {font-size:${font}pt;}`", font_pt)
                layout = measure_resume_page(page)
                layout["body_font_pt"] = font_pt
                layouts.append(layout)
            if errors:
                raise ValueError(f"简历编辑脚本执行失败：{errors}")
        finally:
            browser.close()
    (root / "measurements.json").write_text(json.dumps(layouts, ensure_ascii=False, indent=2), encoding="utf-8")
    valid = [item for item in layouts if MIN_FILL_PERCENT <= item["fill_percent"] <= MAX_FILL_PERCENT
             and not item["horizontal_overflow"] and item["min_font_pt"] >= 9]
    return min(valid or layouts, key=lambda item: abs(item["fill_percent"] - 98))


def render_resume(plan: ResumePlan, output: Path, tools: dict,
                  progress: Callable[[str], None] | None = None, body_font_pt: float | None = None,
                  render_source: tuple[str, dict] | None = None) -> dict:
    if progress:
        progress("正在排版与导出简历…")
    if body_font_pt is None:
        trial = RUNS_DIR / "resume-layout" / uuid.uuid4().hex
        selected = fit_resume_layout(plan, trial, tools.get("browser_channel", "msedge"), render_source=render_source)
        body_font_pt = selected["body_font_pt"]
    html = write_resume_html(plan, output, body_font_pt=body_font_pt, render_source=render_source)
    pdf = output / "简历.pdf"
    layout = export_resume_pdf(html, pdf, tools.get("browser_channel", "msedge"))
    layout["body_font_pt"] = body_font_pt
    if progress:
        progress("正在检查导出文件与生成预览…")
    checks = verify_resume_pdf(plan, pdf)
    pdftoppm = tools.get("pdftoppm") or shutil.which("pdftoppm")
    if pdftoppm is None:
        raise FileNotFoundError("简历预览需要 Poppler pdftoppm")
    subprocess.run([pdftoppm, "-png", "-scale-to", "2200", "-singlefile",
                    str(pdf), str(output / "简历")], check=True, capture_output=True)
    with Image.open(output / "简历.png") as image:
        image.verify()
    checks.update(layout=layout, template="ASu", editable_html=True)
    (output / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pdf": str(pdf), "image": str(output / "简历.png"), "html": str(html),
            "source": str(output / "简历.content.html"), "greeting": plan.greeting, "checks": checks}


def export_resume_pdf(html: Path, pdf: Path | None, browser_channel: str = "msedge", *, enforce_layout: bool = True) -> dict:
    errors = []
    with sync_playwright() as playwright, closing(playwright.chromium.launch(channel=browser_channel, headless=True)) as browser:
        page = browser.new_page(viewport={"width": 718, "height": 1066}, locale="zh-CN")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(browser_file_uri(html), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.emulate_media(media="print")
        layout = measure_resume_page(page)
        if errors:
            raise ValueError(f"简历编辑脚本执行失败：{errors}")
        if pdf is None:
            return layout
        if enforce_layout and (layout["horizontal_overflow"] or layout["fill_percent"] > MAX_FILL_PERCENT or layout["min_font_pt"] < 9):
            raise ValueError("简历文字超出页面或字号小于9pt，请调整正文后重新导出")
        if enforce_layout and layout["fill_percent"] < MIN_FILL_PERCENT:
            raise ValueError(f"简历底部留白过大（正文占用{layout['fill_percent']}%），请补充相关内容后重新导出")
        page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True,
                 display_header_footer=False)
    return layout


def measure_resume_page(page) -> dict:
    return page.evaluate("""() => {
            const sheet = document.querySelector('main.sheet');
            const elements = [...sheet.querySelectorAll('*')].filter(element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden'
                    && [...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
            });
            const bounds = sheet.getBoundingClientRect();
            const bottom = Math.max(...elements.map(element => element.getBoundingClientRect().bottom));
            const available = 282 * 96 / 25.4;
            return {
                fill_percent: Math.round((bottom - bounds.top) / available * 1000) / 10,
                available_height_px: available,
                project_blocks: [...sheet.querySelectorAll('article.project')].flatMap((article, index) =>
                    [...article.querySelectorAll('ul li')].map((item, bullet) => ({
                        path: `/plan/projects/${index}/bullets/${bullet}`,
                        height_px: item.getBoundingClientRect().height,
                        characters: item.textContent.trim().length
                    }))),
                min_font_pt: Math.min(...elements.map(element => parseFloat(getComputedStyle(element).fontSize))) * 0.75,
                horizontal_overflow: elements.some(element => {
                    const rect = element.getBoundingClientRect();
                    return rect.left < bounds.left - 1 || rect.right > bounds.right + 1;
                })
            };
        }""")


def verify_resume_pdf(plan: ResumePlan, pdf: Path) -> dict:
    expected = [plan.name, plan.intention, plan.phone, plan.email, plan.availability]
    expected += [item.school for item in plan.education] + [item.degree for item in plan.education]
    expected += [project.name for project in plan.projects]
    expected += [f"GPA：{item.gpa}" for item in plan.education if item.gpa]
    expected += [bullet for project in plan.projects for bullet in project.bullets] + plan.awards + plan.skills
    required_links = {plan.github} | {item.link for item in plan.projects if item.link}
    return verify_pdf_content(pdf, expected, required_links)


def verify_pdf_content(pdf: Path, expected: list[str], required_links: set[str], *, enforce_layout: bool = True) -> dict:
    reader = PdfReader(pdf)
    if enforce_layout and len(reader.pages) != 1:
        raise ValueError(f"简历生成了 {len(reader.pages)} 页，需要调整正文长度")
    page = reader.pages[0]
    if abs(float(page.mediabox.width) - 595.28) > 1 or abs(float(page.mediabox.height) - 841.89) > 1:
        raise ValueError("简历页面必须为 A4")
    text = normalize("".join(item.extract_text() for item in reader.pages))
    if any(normalize(item) not in text for item in expected):
        raise ValueError("PDF 正文存在缺失内容")
    if enforce_layout:
        with pdfplumber.open(pdf) as document:
            for char in document.pages[0].chars:
                if not (0 <= char["x0"] <= char["x1"] <= 595.29 and 0 <= char["top"] <= char["bottom"] <= 841.90):
                    raise ValueError("简历文字超出页面边界")
    links = {str(item.get_object().get("/A", {}).get("/URI", ""))
             for current in reader.pages for item in current.get("/Annots", [])}
    if not required_links <= links:
        raise ValueError("PDF 缺少简历链接")
    return {"pages": len(reader.pages), "a4": True, "all_text": True, "links": True, "bounds": True if enforce_layout else None}
