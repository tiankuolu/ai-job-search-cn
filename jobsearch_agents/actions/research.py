# 公司调研动作：岗位评估之后的可选步骤（GOAL 之外的用户新增能力）。
# 搜索层：国内可达来源优先（360 -> 搜狗 -> ddgs 国际引擎）。
# 搜索与抓取是确定性代码，只做公开网页的低频量访问，不碰任何招聘平台。

import re
from pathlib import Path

import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..prompts import load_prompt
from ..runtime import Agent, LLMClient
from ..runtime.trace import Trace
from .common import ActionContext, RUNS_DIR

QUERIES = [
    "{company} 工商 全称",
    "{company} 官网 产品",
    "{company} 实习 面试 经验",
    "{company} 新闻 融资",
]
MAX_SOURCES = 8
FETCH_TIMEOUT = 12.0
MAX_PAGE_CHARS = 6000
SEARCH_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
JS_REDIRECT_RE = re.compile(
    r"""(?:window\.location\.(?:replace\(|href\s*=\s*)["']|URL=['"]|href=["'])(https?://[^"']+)"""
)


def _http_get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=FETCH_TIMEOUT, follow_redirects=True, headers=SEARCH_UA)


def _search_so360(query: str, max_results: int) -> list[dict]:
    response = _http_get(f"https://www.so.com/s?q={query}")
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for li in soup.select("li.res-list"):
        a = li.select_one("h3 a")
        if not a or not a.get("href"):
            continue
        results.append({
            "query": query, "title": a.get_text(strip=True),
            "url": a["href"], "snippet": (li.select_one("p") or a).get_text(strip=True)[:200],
        })
        if len(results) >= max_results:
            break
    return results


def _search_sogou(query: str, max_results: int) -> list[dict]:
    response = _http_get(f"https://www.sogou.com/web?query={query}")
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for a in soup.select("h3 a")[:max_results]:
        href = a.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.sogou.com" + href
        results.append({
            "query": query, "title": a.get_text(strip=True),
            "url": href, "snippet": "",
        })
    return results


def _search_ddgs(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS
    with DDGS(timeout=15) as ddgs:
        return [
            {"query": query, "title": item.get("title", ""),
             "url": item.get("href", ""), "snippet": item.get("body", "")}
            for item in ddgs.text(query, max_results=max_results)
        ]


def _search_backends(query: str, max_results: int) -> list[dict]:
    for backend in (_search_so360, _search_sogou, _search_ddgs):
        try:
            results = backend(query, max_results)
        except Exception:
            continue
        if results:
            return results
    return []


def search_company(company: str, max_results: int = 3) -> list[dict]:
    """对固定四类查询执行搜索（国内可达后端优先），返回去重后的结果列表。"""
    seen: set[str] = set()
    results: list[dict] = []
    for template in QUERIES:
        query = template.format(company=company)
        found = _search_backends(query, max_results)
        if not found:
            results.append({"query": query, "title": "（搜索失败）", "url": "",
                            "snippet": "所有搜索后端都没有返回结果"})
            continue
        for item in found:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(item)
    return results[:MAX_SOURCES]


def fetch_page(url: str) -> str:
    """抓取一个公开网页并抽取正文；处理搜索跳转包装与 JS 跳转，失败返回空串。"""
    try:
        response = _http_get(url)
        if response.status_code != 200:
            return ""
        text = response.text
        if len(trafilatura.extract(text) or "") < 200:
            # 跳转包装页：尝试从 JS/meta 里取真实地址再抓一次
            match = JS_REDIRECT_RE.search(text)
            if match:
                response = _http_get(match.group(1))
                if response.status_code != 200:
                    return ""
                text = response.text
        return trafilatura.extract(text) or ""
    except Exception:
        return ""


def build_research_material(company: str, role: str) -> tuple[str, list[str]]:
    """执行搜索与抓取，返回（喂给调研 agent 的材料文本, 成功来源列表）。"""
    results = search_company(company)
    sources: list[str] = []
    parts: list[str] = []
    for i, item in enumerate(results, 1):
        if not item["url"]:
            parts.append(f"### 来源 {i}（查询失败）\n查询：{item['query']}\n错误：{item['snippet']}")
            continue
        content = fetch_page(item["url"])
        if len(content) < 200:
            parts.append(f"### 来源 {i}（正文抽取失败）\n标题：{item['title']}\nURL：{item['url']}\n摘要：{item['snippet']}")
            continue
        sources.append(item["url"])
        parts.append(
            f"### 来源 {i}：{item['title']}\nURL：{item['url']}\n查询：{item['query']}\n\n{content[:MAX_PAGE_CHARS]}"
        )
    material = "\n\n".join(parts) if parts else "（所有来源都抓取失败）"
    header = f"# 调研对象：{company} · {role}\n\n"
    return header + material, sources


def run_research(client: LLMClient, ctx: ActionContext, job_file: Path) -> dict:
    """对单个岗位执行公司调研，产出调研简报。"""
    if not job_file.is_file():
        raise FileNotFoundError(f"岗位文件不存在：{job_file}")
    jd_text = job_file.read_text(encoding="utf-8")
    company_match = re.search(r"\*\*Company:\*\*\s*(.+)", jd_text)
    if not company_match or "未知" in company_match.group(1):
        raise ValueError(
            f"岗位文件缺少公司名，先补全 {job_file.name} 的 Company 字段再调研"
        )
    company = company_match.group(1).strip()
    role_match = re.search(r"^# (.+)$", jd_text, re.MULTILINE)
    role = role_match.group(1).strip() if role_match else job_file.stem

    material, sources = build_research_material(company, role)
    trace = Trace(RUNS_DIR, "research")
    agent = Agent(
        name="researcher",
        system_prompt=load_prompt("researcher"),
        client=client,
        trace=trace,
    )
    brief = agent.run(material)

    ctx.evaluated_dir.mkdir(parents=True, exist_ok=True)
    out_path = ctx.evaluated_dir / f"{ctx.job_key(job_file)}-research.md"
    out_path.write_text(
        f"# Company Research: {company} · {role}\n\n"
        f"**Sources:** {'; '.join(sources) if sources else '（无成功来源）'}\n\n{brief}",
        encoding="utf-8",
    )
    trace.save()
    return {
        "output_file": str(out_path.relative_to(ctx.repo_root)),
        "company": company,
        "sources": sources,
        "brief": brief,
        "trace": str(trace.save()),
        "trace_obj": trace,
    }
