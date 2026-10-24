"""牛客抓取动作的单元验证：注入式 http 客户端，不触网。"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.actions import nowcoder as nc  # noqa: E402
from jobsearch_agents.actions.nowcoder import (  # noqa: E402
    graduation_year_excludes,
    html_to_text,
    is_internship,
    run_nowcoder_sweep,
    title_matches,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload


class FakeClient:
    """按 companyId 返回预置职位列表的假客户端。"""

    def __init__(self, company_page, job_lists):
        self._company_page = company_page
        self._job_lists = job_lists

    def get(self, url, params=None):
        if "one-delivery-company" in url:
            return FakeResponse(self._company_page)
        company_id = params["companyId"]
        return FakeResponse({"success": True,
                             "data": {"records": self._job_lists.get(company_id, [])}})


COMPANY_PAGE = {
    "data": {"records": [
        {"name": "Acme", "companyId": 1, "cityList": ["北京"]},
        {"name": "Beta", "companyId": 2, "cityList": ["上海"]},
    ], "totalPage": 1},
}
JOB_LISTS = {
    1: [
        {"id": 10, "globalJobId": 10010, "title": "Agent 应用实习生", "commitment": "实习",
         "city": "北京", "education": None, "department": "AI 部",
         "description": "<p>做 Agent 应用</p>"},
        {"id": 11, "globalJobId": 10011, "title": "Java 后端工程师", "commitment": "全职",
         "city": "北京", "description": "<p>后端</p>"},
        {"id": 12, "globalJobId": 10012, "title": "大模型算法实习生", "commitment": "实习",
         "city": "北京", "description": "<p>大模型</p>"},
        {"id": 13, "globalJobId": 10013, "title": "服务端开发实习生", "commitment": "实习",
         "city": "北京", "description": "<p>负责大模型业务的后端服务开发</p>"},
        {"id": 14, "globalJobId": 10014, "title": "后端开发实习生", "commitment": "实习",
         "city": "北京", "description": "<p>只招27届，负责大模型业务的后端服务开发</p>"},
        {"id": 15, "globalJobId": 10015, "title": "平台开发实习生", "commitment": "实习",
         "city": "北京", "description": "<p>27/28届均可投递，开发内部平台</p>"},
    ],
    2: [
        {"id": 20, "globalJobId": 10020, "title": "大模型算法实习生", "commitment": "实习",
         "city": None, "description": "<p>同名岗位去重验证</p>"},
    ],
}


class TestFilters(unittest.TestCase):
    def test_title_matches_case_insensitive(self):
        self.assertEqual(title_matches("Agent 应用实习", ["agent"]), "agent")
        self.assertEqual(title_matches("大模型研发实习", ["大模型"]), "大模型")
        self.assertIsNone(title_matches("Java 后端实习", ["agent", "大模型"]))

    def test_is_internship(self):
        self.assertTrue(is_internship({"commitment": "实习"}))
        self.assertTrue(is_internship({"commitment": None, "title": "XX实习生"}))
        self.assertFalse(is_internship({"commitment": "全职", "title": "工程师"}))

    def test_graduation_year_rules(self):
        # 只招/仅限 27 届 → 排除
        self.assertTrue(graduation_year_excludes("只招27届，做存储开发"))
        self.assertTrue(graduation_year_excludes("限2027届毕业生"))
        # 27/28 均可 → 保留
        self.assertFalse(graduation_year_excludes("27/28届均可投递"))
        # 27届可投（无排他词）→ 保留
        self.assertFalse(graduation_year_excludes("27届可投"))
        # 未提及 → 保留
        self.assertFalse(graduation_year_excludes("负责大模型业务后端"))

    def test_html_to_text(self):
        text = html_to_text("<p>职责一</p><p>1.要求A&nbsp;2.要求B</p><div>加分项</div>")
        self.assertIn("职责一", text)
        self.assertIn("要求A", text)
        self.assertNotIn("<p>", text)


class TestSweep(unittest.TestCase):
    def run_sweep(self, tmp_path: Path, dry_run: bool) -> dict:
        original_client = nc.build_client
        nc.build_client = lambda: FakeClient(COMPANY_PAGE, JOB_LISTS)
        try:
            return run_nowcoder_sweep(tmp_path / "inbox", tmp_path,
                                      max_companies=2, dry_run=dry_run)
        finally:
            nc.build_client = original_client

    def test_dry_run_reports_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_sweep(Path(tmp), dry_run=True)
            self.assertEqual(result["saved_count"], 4)
            self.assertEqual(result["skipped_direction_mismatch"], 1)
            self.assertEqual(result["skipped_grad_year"], 1)
            self.assertFalse(any((Path(tmp) / "inbox").glob("牛客-*.md")))

    def test_sweep_writes_inbox_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_sweep(Path(tmp), dry_run=False)
            inbox = Path(tmp) / "inbox"
            files = sorted(inbox.glob("牛客-*.md"))
            self.assertEqual(len(files), 4)
            self.assertEqual(result["skipped_direction_mismatch"], 1)
            self.assertEqual(result["skipped_grad_year"], 1)
            content = files[0].read_text(encoding="utf-8")
            self.assertIn("**Source:** 牛客网", content)
            self.assertIn("## Job Facts", content)
            self.assertIn("Employment Type: 实习", content)

    def test_rerun_is_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_sweep(Path(tmp), dry_run=False)
            first = sorted(p.name for p in (Path(tmp) / "inbox").glob("牛客-*.md"))
            result = self.run_sweep(Path(tmp), dry_run=False)
            second = sorted(p.name for p in (Path(tmp) / "inbox").glob("牛客-*.md"))
            self.assertEqual(first, second)
            self.assertEqual(result["skipped_duplicate"], 4)


if __name__ == "__main__":
    unittest.main()
