# 牛客网 JD 抓取：公开 API（robots.txt 允许，仅 /search 禁止），低频量访问。
# 职责边界：本模块只做「粗筛 + 去重 + 落盘」，岗位与候选人的匹配判断交给
# analyze 流水线（要求覆盖 + 六维评分 + 分支判定）。
# 粗筛规则：实习 commitment + 标题命中目标方向关键词（默认词表来自
# 简历目录中个人资料的目标岗位：Agent 应用开发 / Python 后端 / Agent 评测）。

import re
import time
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .common import INBOX_DIR

NOWCODER_GW = "https://gw-c.nowcoder.com/api/sparta"
DELAY_SECONDS = 0.3
DETAIL_URL = "https://www.nowcoder.com/jobs/detail/{global_job_id}"

# 三条目标方向的标题关键词。裸「算法」「AI」太宽（会捞进 CV/量化/自动驾驶），不放进来；
# 需要更宽的扫描用 --keywords 覆盖。
DEFAULT_KEYWORDS = [
    # 强方向词（精确命中）
    "agent", "大模型", "llm", "aigc", "rag", "生成式",
    "评测", "eval", "ai应用", "ai 产品", "ai产品", "nlp应用", "python",
    # 宽收词（提高召回，噪音由 analyze 分支 3 与人工删除兜底）
    "ai", "算法", "机器学习", "深度学习", "nlp", "智能",
    "后端", "全栈", "服务端", "数据",
]

# 描述级强信号：前端/后端/全栈类岗位标题不带方向词，但描述里写明做大模型/Agent 业务的，
# 同样保留（匹配判断交给 analyze，抓取层宁可多收）。
STRONG_DESC_RE = re.compile(r"大模型|LLM|Agent|智能体|AIGC|RAG", re.IGNORECASE)

# 届别口径：候选人是 28 届。「只招/仅限/只接受/限 27 届」的岗位跳过；
# 「27 届可投」「27/28 届均可」这类非排他表述保留。
EXCLUSIVE_27_RE = re.compile(r"(?:只招|仅限|只接受|限)\s*(?:20)?27届")


def graduation_year_excludes(text: str | None) -> bool:
    """28 届候选人视角：岗位是否明确排除 28 届。"""
    text = text or ""
    if "28届" in text or "2028届" in text:
        return False  # 明确欢迎 28 届
    if EXCLUSIVE_27_RE.search(text):
        return True
    return False


def build_client() -> httpx.Client:
    # trust_env=False：绕开系统代理对牛客的间歇性劫持
    return httpx.Client(trust_env=False, timeout=15, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})


def iter_companies(client: httpx.Client, max_companies: int | None = None):
    """枚举全部在招公司，返回 [{name, companyId, cityList}]。"""
    companies = []
    page = 1
    while True:
        r = client.get(f"{NOWCODER_GW}/one-delivery-company/list",
                       params={"pageSize": 100, "pageNo": page})
        if r.status_code != 200:
            raise RuntimeError(f"公司列表请求失败：{r.status_code} {r.text[:200]}")
        data = r.json()["data"]
        companies.extend(data["records"])
        if page >= data["totalPage"]:
            break
        page += 1
        time.sleep(DELAY_SECONDS)
        if max_companies and len(companies) >= max_companies:
            break
    if max_companies:
        companies = companies[:max_companies]
    return [{"name": c["name"], "companyId": c["companyId"],
             "cityList": c.get("cityList") or []} for c in companies]


def fetch_company_jobs(client: httpx.Client, company_id: int) -> list[dict]:
    r = client.get(f"{NOWCODER_GW}/one-delivery-job/job-list",
                   params={"companyId": company_id, "pageSize": 100, "pageNo": 1})
    if r.status_code != 200:
        return []
    payload = r.json()
    if not payload.get("success"):
        return []
    return payload.get("data", {}).get("records", [])


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text("\n")
    text = text.replace("\u00a0", " ")
    return re.sub(r"\n{2,}", "\n", text).strip()


def title_matches(title: str, keywords: list[str]) -> str | None:
    """返回命中的关键词；无命中返回 None。大小写不敏感。"""
    lowered = title.lower()
    for kw in keywords:
        if kw.lower() in lowered:
            return kw
    return None


def is_internship(job: dict) -> bool:
    return "实习" in (job.get("commitment") or "") or "实习" in (job.get("title") or "")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", name).strip()


def save_job_file(job: dict, company_name: str, company_cities: list[str],
                  keyword: str, inbox: Path) -> Path:
    """按 inbox 规范写一个岗位文件，返回文件路径。"""
    title = job["title"]
    city = job.get("city") or "、".join(company_cities) or "未注明"
    description = html_to_text(job.get("description") or "")
    detail_url = DETAIL_URL.format(global_job_id=job.get("globalJobId") or job["id"])

    # 教育字段 API 常为 null，从描述兜底
    education = job.get("education") or "未注明（见正文）"
    body = (
        f"# {title} @ {company_name}\n\n"
        f"**Source:** 牛客网（NowPick 公开 API）\n"
        f"**Source URL:** {detail_url}\n"
        f"**Fetch Status:** ready\n"
        f"**Saved Date:** {date.today().isoformat()}\n"
        f"**Match Keyword:** {keyword}\n\n"
        f"## Job Facts\n\n"
        f"- Company: {company_name}\n"
        f"- Role: {title}\n"
        f"- Location: {city}\n"
        f"- Work Mode: 未注明（见正文）\n"
        f"- Salary: 未注明（见正文）\n"
        f"- Employment Type: {job.get('commitment') or '实习'}\n"
        f"- Education: {education}\n"
        f"- Department: {job.get('department') or '未注明'}\n"
        f"- Posted At: 未注明\n"
        f"- Application Deadline: 未注明\n\n"
        f"## 职位描述（API 原文）\n\n{description}\n"
    )
    # 文件名用可读的中文（与手动保存的 inbox 文件一致），按「公司+岗位」天然去重
    out = inbox / sanitize_filename(f"牛客-{company_name}-{title}.md")
    out.write_text(body, encoding="utf-8")
    return out


def run_nowcoder_sweep(inbox: Path, repo_root: Path,
                       keywords: list[str] | None = None,
                       max_companies: int | None = None,
                       dry_run: bool = False,
                       delay: float = DELAY_SECONDS) -> dict:
    """全量扫描：公司枚举 → 职位过滤（实习 + 方向关键词）→ 去重 → 落盘。"""
    keywords = keywords or DEFAULT_KEYWORDS
    inbox.mkdir(parents=True, exist_ok=True)
    # job_key 是仓库自带确定性工具，固定从包自身仓库加载（与运行工作区无关）
    existing_files = {p.name for p in inbox.glob("牛客-*.md")}

    client = build_client()
    companies = iter_companies(client, max_companies)
    saved, skipped_dup, skipped_notmatch, skipped_grad_year, errors = [], 0, 0, 0, []

    for company in companies:
        try:
            jobs = fetch_company_jobs(client, company["companyId"])
        except Exception as exc:
            errors.append(f"{company['name']}: {repr(exc)[:80]}")
            time.sleep(delay)
            continue
        for job in jobs:
            if not is_internship(job):
                continue
            description = html_to_text(job.get("description") or "")
            keyword = title_matches(job["title"], keywords)
            if keyword is None and STRONG_DESC_RE.search(description[:600]):
                # 强信号只看描述开头（岗位职责区）；公司简介模板后半段提到大模型不算
                keyword = "描述命中（标题无方向词）"
            if keyword is None:
                skipped_notmatch += 1
                continue
            if graduation_year_excludes(job["title"]) or graduation_year_excludes(description[:1500]):
                skipped_grad_year += 1
                continue
            filename = sanitize_filename(f"牛客-{company['name']}-{job['title']}.md")
            if filename in existing_files:
                skipped_dup += 1
                continue
            if dry_run:
                saved.append({"company": company["name"], "title": job["title"],
                              "keyword": keyword, "dry_run": True})
                existing_files.add(filename)
                continue
            try:
                out = save_job_file(job, company["name"], company["cityList"],
                                    keyword, inbox)
                existing_files.add(filename)
                saved.append({"company": company["name"], "title": job["title"],
                              "keyword": keyword, "file": str(out.name)})
            except Exception as exc:
                errors.append(f"{company['name']}/{job['title']}: {repr(exc)[:80]}")
        time.sleep(delay)

    return {
        "companies_scanned": len(companies),
        "saved": saved,
        "saved_count": len(saved),
        "skipped_duplicate": skipped_dup,
        "skipped_direction_mismatch": skipped_notmatch,
        "skipped_grad_year": skipped_grad_year,
        "errors": errors,
    }
