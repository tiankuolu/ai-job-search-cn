import json
import shutil
import subprocess
from pathlib import Path
from html import escape

import bleach
from bleach.css_sanitizer import CSSSanitizer
from lxml import html
from PIL import Image

from .resume import export_resume_pdf, normalize, verify_pdf_content
from .generation import Claim, ResumeDraft, source_facts
from .resume import Project, ResumePlan


SHEET_QUERY = '//main[contains(concat(" ", normalize-space(@class), " "), " sheet ")]'
ALLOWED_TAGS = {"header", "footer", "section", "article", "div", "span", "p", "h1", "h2", "h3", "h4",
                "ul", "ol", "li", "strong", "b", "em", "i", "u", "s", "br", "a", "small", "sub", "sup"}
ALLOWED_CSS = {"font-size", "font-family", "font-weight", "font-style", "color", "background-color",
               "text-decoration", "text-align", "line-height", "letter-spacing", "margin", "margin-top",
               "margin-bottom", "padding", "padding-top", "padding-bottom", "white-space"}


def current_resume_draft(package: dict, profile: dict, source_html: str | None = None) -> ResumeDraft:
    application = Path(package["application"])
    if application.suffix == ".json":
        evidence = json.loads(application.read_text(encoding="utf-8"))
        draft = ResumeDraft.model_validate(evidence["draft"])
    else:
        plan_path = next(parent / "resume.json" for parent in Path(package["pdf"]).parents
                         if (parent / "resume.json").is_file())
        plan = ResumePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        draft = ResumeDraft(plan=plan, positioning=plan.intention,
                            claims=[Claim(path="/plan/greeting", fact_ids=["PERSONAL"])])
    _, sheet = resume_document(source_html if source_html is not None else Path(package["html"]).read_text(encoding="utf-8"))
    intentions = sheet.xpath('./header//div[contains(concat(" ", normalize-space(@class), " "), " meta-row ")][1]/strong')
    if len(intentions) != 1 or "：" not in intentions[0].text_content():
        raise ValueError("编辑稿的求职意向无法唯一识别")
    draft.plan.intention = intentions[0].text_content().partition("：")[2].strip()
    skills = sheet.xpath('.//ul[contains(concat(" ", normalize-space(@class), " "), " skills-list ")]/li')
    articles = sheet.xpath('.//article[contains(concat(" ", normalize-space(@class), " "), " project ")]')
    if not skills or not articles:
        raise ValueError("当前编辑稿缺少可识别的技能或项目区域")
    projects = []
    facts = source_facts(profile)
    sources = json.loads(profile["project_sources"])
    claims = []
    for index, article in enumerate(articles):
        titles = article.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " project-title ")]')
        if len(titles) != 1:
            raise ValueError("当前项目标题无法唯一识别")
        name = titles[0].text_content().strip()
        identifiers = [item["id"] for item in sources if normalize(name) in normalize(Path(item["path"]).stem)]
        if len(identifiers) != 1:
            raise ValueError(f"项目名称无法关联当前事实档案：{name}")
        candidates = [key for key in facts if key.startswith(identifiers[0] + "-")]
        bullets = [element.text_content().strip() for element in article.xpath('./ul/li')]
        links = article.xpath('.//a[@href]')
        projects.append(Project(name=name, role="", link=links[0].get("href") if links else "", bullets=bullets))
        for bullet_no in range(len(bullets)):
            claims.append(Claim(path=f"/plan/projects/{index}/bullets/{bullet_no}", fact_ids=candidates))
    draft.plan.projects = projects
    draft.plan.skills = [item.text_content().strip() for item in skills]
    draft.plan.greeting = package["greeting"]
    original = {item.path: item for item in draft.claims}
    claims += [original.get(f"/plan/skills/{i}", Claim(path=f"/plan/skills/{i}", fact_ids=["PERSONAL", *facts]))
               for i in range(len(skills))]
    claims.append(original.get("/plan/greeting", Claim(path="/plan/greeting", fact_ids=["PERSONAL", *facts])))
    draft.claims = claims
    return ResumeDraft.model_validate(draft.model_dump())


def resume_document(source: str):
    document = html.document_fromstring(source)
    sheets = document.xpath(SHEET_QUERY)
    if len(sheets) != 1:
        raise ValueError("简历 HTML 需要包含一个 A4 正文区域")
    sheet = sheets[0]
    for element in document.xpath("//script | //base | //link | //iframe | //object | //embed"):
        element.drop_tree()
    body = document.find("body")
    for element in list(body):
        if element is not sheet:
            body.remove(element)
    sheet.set("contenteditable", "false")
    return document, sheet


def sheet_content(sheet) -> str:
    return escape(sheet.text or "", quote=False) + "".join(html.tostring(child, encoding="unicode") for child in sheet)


def edited_document(source: str, content: str) -> str:
    document, sheet = resume_document(source)
    cleaned = bleach.clean(content, tags=ALLOWED_TAGS,
                           attributes={"*": ["class", "style"], "a": ["href", "title"]},
                           protocols={"https", "http", "mailto"}, strip=True,
                           css_sanitizer=CSSSanitizer(allowed_css_properties=ALLOWED_CSS))
    fragment = html.fragment_fromstring(cleaned, create_parent="div")
    if not fragment.text_content().strip():
        raise ValueError("简历正文不能为空")
    for child in list(sheet):
        sheet.remove(child)
    sheet.text = fragment.text
    for child in list(fragment):
        sheet.append(child)
    return html.tostring(document, encoding="unicode", doctype="<!doctype html>")


def editor_document(source: str, package_id: str, revision: int, read_only: bool) -> str:
    document, sheet = resume_document(source)
    head = document.find("head")
    policy = html.Element("meta", {"http-equiv": "Content-Security-Policy", "content":
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"})
    head.insert(0, policy)
    style = html.Element("style")
    style.text = ("html, body {background:#fff!important; padding:0!important; margin:0!important;}"
                  "body[data-page-mode] main.sheet {width:210mm;min-height:297mm;margin:0;box-shadow:none;}"
                  "main.sheet[contenteditable=true]:focus {outline:none;}"
                  "main.sheet[contenteditable=true] {cursor:text;}")
    head.append(style)
    script = html.Element("script")
    script.text = "const resumeEditorConfig = " + json.dumps(
        {"packageId": package_id, "revision": revision, "readOnly": read_only}, ensure_ascii=False) + ";\n"
    script.text += Path(__file__).with_name("editor.js").read_text(encoding="utf-8")
    document.find("body").append(script)
    return html.tostring(document, encoding="unicode", doctype="<!doctype html>")


def export_edited_resume(source: Path, output: Path, tools: dict) -> dict:
    document, sheet = resume_document(source.read_text(encoding="utf-8"))
    expected = [text for text in sheet.itertext() if text.strip()]
    links = {element.get("href") for element in sheet.xpath('.//a[@href]') if element.get("href")}
    output.mkdir(parents=True, exist_ok=False)
    target = output / "简历.html"
    target.write_text(html.tostring(document, encoding="unicode", doctype="<!doctype html>"), encoding="utf-8")
    pdf = output / "简历.pdf"
    layout = export_resume_pdf(target, pdf, tools.get("browser_channel", "msedge"), enforce_layout=False)
    checks = verify_pdf_content(pdf, expected, links, enforce_layout=False)
    pdftoppm = tools.get("pdftoppm") or shutil.which("pdftoppm")
    if pdftoppm is None:
        raise FileNotFoundError("简历预览需要 Poppler pdftoppm")
    subprocess.run([pdftoppm, "-png", "-scale-to", "2200", "-singlefile", str(pdf), str(output / "简历")],
                   check=True, capture_output=True)
    image = output / "简历.png"
    with Image.open(image) as preview:
        preview.verify()
    checks.update(layout=layout, template="ASu", editable_html=True, human_edited=True)
    (output / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"html": str(target), "pdf": str(pdf), "image": str(image), "checks": checks}
