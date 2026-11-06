import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .platforms import PLATFORM_NAMES


class GetJobsBridge:
    def __init__(self, settings_file: Path):
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        self.settings = settings
        self.url = settings["bridge_url"]
        if urlsplit(self.url).hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("投递服务必须位于本机")
        self.headers = {"X-Jobsearch-Token": settings["bridge_token"]}

    def require_login(self, platform: str):
        endpoint = "status" if platform == "boss" else f"platforms/{platform}/status"
        status = self.call("GET", endpoint)
        if not status["logged_in"]:
            name = PLATFORM_NAMES[platform]
            raise ValueError(f"请先登录{name}：点击“打开登录浏览器”，完成登录后点击“检查登录状态”，再搜索岗位。")
        return status

    def call(self, method: str, endpoint: str, data: dict | None = None):
        with httpx.Client(trust_env=False, timeout=httpx.Timeout(600, connect=5)) as client:
            response = client.request(method, f"{self.url}/api/jobsearch/{endpoint}",
                                      headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
