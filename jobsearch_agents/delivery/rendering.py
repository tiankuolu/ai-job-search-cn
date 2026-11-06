from copy import deepcopy

from lxml import html


def one(document, query: str):
    elements = document.xpath(query)
    if len(elements) != 1:
        raise ValueError(f"编辑稿需要包含唯一的目标区域：{query}")
    return elements[0]


def update_list(target, fresh, old_values: list[str], new_values: list[str]):
    old_items = target.xpath("./li")
    new_items = fresh.xpath("./li")
    if len(old_items) != len(old_values) or len(new_items) != len(new_values):
        raise ValueError("编辑稿的列表结构与已读取正文不一致")
    retained = {value: item for value, item in zip(old_values, old_items, strict=True)}
    for item in old_items:
        target.remove(item)
    for value, generated in zip(new_values, new_items, strict=True):
        target.append(deepcopy(retained[value] if value in retained else generated))


def merge_resume_content(current: str, generated: str, previous: dict, revised: dict) -> tuple[str, str]:
    document = html.document_fromstring(current)
    fresh = html.document_fromstring(generated)
    query = '//main[contains(concat(" ", normalize-space(@class), " "), " sheet ")]'
    sheet = one(document, query)
    new_sheet = one(fresh, query)
    sheet.set("contenteditable", "true")
    if previous["intention"] != revised["intention"]:
        label = one(sheet, './header//div[contains(concat(" ", normalize-space(@class), " "), " meta-row ")][1]/strong')
        prefix, separator, _ = label.text_content().partition("：")
        if not separator:
            raise ValueError("编辑稿的求职意向字段缺少明确标签")
        label.text = prefix + "：" + revised["intention"]
        for child in list(label):
            label.remove(child)
    if previous["skills"] != revised["skills"]:
        skill_query = './/ul[contains(concat(" ", normalize-space(@class), " "), " skills-list ")]'
        update_list(one(sheet, skill_query), one(new_sheet, skill_query), previous["skills"], revised["skills"])
    if previous["projects"] != revised["projects"]:
        article_query = './/article[contains(concat(" ", normalize-space(@class), " "), " project ")]'
        articles = sheet.xpath(article_query)
        fresh_articles = new_sheet.xpath(article_query)
        if len(articles) != len(previous["projects"]) or len(fresh_articles) != len(revised["projects"]):
            raise ValueError("编辑稿的项目结构与已读取正文不一致")
        parent = articles[0].getparent()
        if any(article.getparent() is not parent for article in articles):
            raise ValueError("编辑稿项目需要位于同一个经历区域")
        retained = {project["name"]: (project, article)
                    for project, article in zip(previous["projects"], articles, strict=True)}
        for article in articles:
            parent.remove(article)
        for project, generated_article in zip(revised["projects"], fresh_articles, strict=True):
            if project["name"] not in retained:
                parent.append(deepcopy(generated_article))
                continue
            old, source = retained[project["name"]]
            article = deepcopy(source)
            if old["link"] != project["link"]:
                for anchor in article.xpath('.//a[@href]'):
                    anchor.getparent().remove(anchor)
                if project["link"]:
                    anchor = one(generated_article, './/a[@href]')
                    one(article, './div').append(deepcopy(anchor))
            if old["bullets"] != project["bullets"]:
                update_list(one(article, './ul'), one(generated_article, './ul'), old["bullets"], project["bullets"])
            parent.append(article)
    styles = "\n".join(html.tostring(element, encoding="unicode") for element in document.xpath("//head/style"))
    return html.tostring(sheet, encoding="unicode"), styles
