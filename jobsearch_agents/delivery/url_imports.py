import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright
from pydantic import HttpUrl, TypeAdapter

from .imports import JobFields, structure_job


class URLJobImporter:
    def __init__(self, root: Path, bridge):
        self.root = root
        self.bridge = bridge
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jd-browser")
        self.playwright = None
        self.context = None
        self.page = None

    def validate_url(self, url: str) -> str:
        parsed = TypeAdapter(HttpUrl).validate_python(url)
        if parsed.username or parsed.password:
            raise ValueError("请使用不包含账号密码的招聘页面链接")
        return str(parsed)

    def platform(self, url: str) -> str | None:
        host = urlsplit(url).hostname or ""
        for domain, platform in (("zhipin.com", "boss"), ("liepin.com", "liepin"),
                                 ("nowcoder.com", "nowcoder"), ("shixiseng.com", "shixiseng")):
            if host == domain or host.endswith("." + domain):
                return platform
        return None

    def browser_page(self):
        if self.context is not None and not self.context.browser.is_connected():
            self.context = None
            self.page = None
            self.playwright.stop()
            self.playwright = None
        if self.context is None:
            profile = self.root / "url-browser"
            profile.mkdir(parents=True, exist_ok=True)
            self.playwright = sync_playwright().start()
            self.context = self.playwright.chromium.launch_persistent_context(
                str(profile), channel="msedge", headless=False,
                viewport={"width": 1280, "height": 900}, locale="zh-CN")
        if self.page is None or self.page.is_closed():
            self.page = self.context.new_page()
        return self.page

    def open(self, url: str) -> dict:
        url = self.validate_url(url)
        if self.platform(url) == "boss":
            self.bridge().call("POST", "login", {})
            return {"status": "opened", "message": "请在 BOSS 浏览器完成登录，再点击解析链接。"}
        return self.executor.submit(self.open_browser, url).result()

    def open_browser(self, url: str) -> dict:
        page = self.browser_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.bring_to_front()
        return {"status": "opened", "message": "请在打开的浏览器完成登录，再点击解析链接。"}

    def read_browser(self, url: str) -> dict:
        page = self.browser_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.locator("body").wait_for()
        if re.search(r"/(login|signin|passport)(/|\?|$)", page.url, re.IGNORECASE):
            page.bring_to_front()
            return {"status": "login_required", "message": "请在浏览器完成登录，再重新解析链接。"}
        page.wait_for_function("document.body.innerText.trim().length > 200 || document.querySelector('input[type=password]')", timeout=30_000)
        if page.locator('input[type="password"]:visible').count():
            return {"status": "login_required", "message": "请先在浏览器完成登录，再重新解析链接。"}
        return {"status": "read", "description": page.locator("body").inner_text(),
                "source_html": page.content(), "page_url": page.url, "page_title": page.title()}

    def read(self, url: str) -> dict:
        url = self.validate_url(url)
        parsed = urlsplit(url)
        platform = self.platform(url)
        if parsed.hostname == "job.xiaohongshu.com":
            match = re.fullmatch(r"/campus/(?:intern/)?position/(\d+)/?", parsed.path)
            if not match:
                raise ValueError("请提供小红书具体岗位的详情链接")
            with httpx.Client(timeout=30, trust_env=False) as client:
                response = client.get("https://job.xiaohongshu.com/websiterecruit/position/queryPositionDetail",
                                      params={"positionId": match.group(1)})
                response.raise_for_status()
                payload = response.json()
            if not payload["success"] or not payload.get("data"):
                raise ValueError("小红书官网未返回该岗位，请核对链接")
            job = payload["data"]
            if not job.get("duty") or not job.get("qualification"):
                raise ValueError("官网岗位缺少职责或任职要求，请核对完整页面")
            fields = JobFields(company="小红书", title=job["positionName"], city=job["workplace"],
                               url=url, platform=None, responsibilities=job["duty"],
                               requirements=job["qualification"], bonus="",
                               details=f"招聘项目：{job['jobProjectName']}\n官方状态：{job['recruitStatus']}").model_dump(mode="json")
            document = {"description": f"{job['positionName']} @ 小红书\n工作地点：{job['workplace']}\n\n工作职责\n{job['duty']}\n\n任职资格\n{job['qualification']}",
                        "source_json": payload}
        else:
            if platform == "boss":
                bridge = self.bridge()
                status = bridge.call("GET", "status")
                if not status["logged_in"]:
                    return {"status": "login_required", "message": "请先登录 BOSS直聘，再解析完整岗位。", "platform": "boss"}
                detail = bridge.call("POST", "detail", {"url": url})
                document = {"description": detail["text"], "source_json": detail}
            else:
                document = self.executor.submit(self.read_browser, url).result()
                if document["status"] == "login_required":
                    return document
        identifier = uuid.uuid4().hex
        directory = self.root / "imports" / identifier
        directory.mkdir(parents=True)
        if document.get("source_html"):
            (directory / "source.html").write_text(document["source_html"], encoding="utf-8")
        if document.get("source_json"):
            (directory / "source.json").write_text(json.dumps(document["source_json"], ensure_ascii=False, indent=2), encoding="utf-8")
        (directory / "source.md").write_text(document["description"], encoding="utf-8")
        (directory / "source-url.json").write_text(json.dumps({"url": url}, ensure_ascii=False), encoding="utf-8")
        if parsed.hostname != "job.xiaohongshu.com":
            fields = structure_job(f"岗位链接：{url}\n\n{document['description']}", self.root)
            fields.update(url=url, platform=platform)
            if not fields["title"].strip() or not any(fields[key].strip() for key in ("responsibilities", "requirements")):
                raise ValueError("页面未提供可识别的岗位名称、职责或任职要求，请核对目标网页")
        record = {"status": "ready", "import_id": identifier, "filename": urlsplit(url).hostname + "-岗位",
                  "source_url": url, "description": document["description"], "pages": 1,
                  "method": "招聘网页读取", "fields": fields,
                  "missing_sections": [key for key in ("responsibilities", "requirements") if not fields[key].strip()]}
        (directory / "extracted.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def close(self):
        self.executor.submit(self.close_browser).result()
        self.executor.shutdown(wait=True)

    def close_browser(self):
        if self.context is not None:
            self.context.close()
        if self.playwright is not None:
            self.playwright.stop()
