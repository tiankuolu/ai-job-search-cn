"""新动作的单元验证：投递状态表、面试故事库/练习/评分、公司调研编排（假模型+注入式搜索）。"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from jobsearch_agents.actions import status as status_mod  # noqa: E402
from jobsearch_agents.actions.interview import (  # noqa: E402
    grade_practice,
    make_practice_sheet,
    run_storybank,
)
from jobsearch_agents.actions.research import run_research  # noqa: E402
from jobsearch_agents.actions.common import ActionContext  # noqa: E402
from jobsearch_agents.runtime import Agent, Trace  # noqa: E402
from .fakes import ScriptedLLMClient, make_text_response  # noqa: E402


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "evaluated"
        self.dir.mkdir(parents=True)
        (self.dir / "acme-dev-application.md").write_text(
            "# Application Pack: 开发工程师 @ Acme\n\n## BOSS Greeting\n你好",
            encoding="utf-8",
        )
        self.status_path = self.dir / "delivery-status.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_rows(self):
        rows = status_mod.init_from_evaluated(self.dir, self.status_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company"], "Acme")
        self.assertEqual(rows[0]["stage"], "未投递")

    def test_init_idempotent(self):
        status_mod.init_from_evaluated(self.dir, self.status_path)
        rows = status_mod.init_from_evaluated(self.dir, self.status_path)
        self.assertEqual(len(rows), 1)

    def test_set_stage(self):
        status_mod.init_from_evaluated(self.dir, self.status_path)
        row = status_mod.set_stage("acme-dev", "已投递", self.status_path, note="BOSS 已发",
                                   applied=True)
        self.assertEqual(row["stage"], "已投递")
        self.assertNotEqual(row["applied_date"], "")

    def test_set_stage_rejects_invalid(self):
        status_mod.init_from_evaluated(self.dir, self.status_path)
        with self.assertRaises(ValueError):
            status_mod.set_stage("acme-dev", "不存在阶段", self.status_path)

    def test_render_table(self):
        status_mod.init_from_evaluated(self.dir, self.status_path)
        status_mod.set_stage("acme-dev", "约面", self.status_path)
        table = status_mod.render_table(status_mod._load(self.status_path))
        self.assertIn("约面", table)
        self.assertIn("Acme", table)


class TestInterview(unittest.TestCase):
    def _profile(self, tmp: Path) -> Path:
        profile = tmp / "profile"
        profile.mkdir(exist_ok=True)
        for name in ("candidate.md", "preferences.md", "evidence.md"):
            (profile / name).write_text(f"# {name}\n虚构资料", encoding="utf-8")
        return profile

    def test_storybank(self):
        import tempfile

        from jobsearch_agents.actions.interview import STORYBANK, INTERVIEW_DIR, PRACTICE_DIR

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            profile = self._profile(tmp_path)
            original_dir = INTERVIEW_DIR
            import jobsearch_agents.actions.interview as iv
            iv.INTERVIEW_DIR = tmp_path
            iv.STORYBANK = tmp_path / "storybank.md"
            iv.PRACTICE_DIR = tmp_path / "practice"
            iv.PRACTICE_LOG = tmp_path / "log.md"
            original_runs = iv.RUNS_DIR
            iv.RUNS_DIR = tmp_path / "runs"
            ctx_repo = tmp_path
            try:
                client = ScriptedLLMClient([make_text_response("故事库内容\n<STORYBANK_OK>")])
                result = run_storybank(client)
                self.assertTrue(iv.STORYBANK.exists())
                self.assertIn("故事库内容", iv.STORYBANK.read_text(encoding="utf-8"))

                # 已存在时拒绝覆盖
                with self.assertRaises(FileExistsError):
                    run_storybank(client)

                # practice：无岗位出通用卷
                client2 = ScriptedLLMClient([make_text_response("练习卷内容")])
                result = make_practice_sheet(client2, None)
                self.assertTrue((tmp_path / result["output_file"]).exists())

                # grade
                sheet = Path(result["output_file"])
                answers = tmp_path / "answers.md"
                answers.write_text("我的答案", encoding="utf-8")
                client3 = ScriptedLLMClient(
                    [make_text_response("总分：7.5\n<GRADE_OK>\n评语")]
                )
                result = grade_practice(client3, sheet, answers)
                self.assertEqual(result["score"], 7.5)
                self.assertTrue(iv.PRACTICE_LOG.exists())
            finally:
                iv.INTERVIEW_DIR = original_dir
                iv.STORYBANK = original_dir / "storybank.md" if False else iv.STORYBANK
                iv.RUNS_DIR = original_runs

    def test_storybank_requires_profile(self):
        import tempfile

        import jobsearch_agents.actions.interview as iv

        with tempfile.TemporaryDirectory() as tmp:
            original = iv.PROFILE_DIR
            iv.PROFILE_DIR = Path(tmp) / "none"
            try:
                with self.assertRaises(FileNotFoundError):
                    run_storybank(ScriptedLLMClient([make_text_response("x")]))
            finally:
                iv.PROFILE_DIR = original


class TestResearch(unittest.TestCase):
    def _job(self, tmp: Path, company="望石智慧") -> Path:
        (tmp / "markets" / "china" / "jobs" / "inbox").mkdir(parents=True, exist_ok=True)
        jd = tmp / "markets" / "china" / "jobs" / "inbox" / "job.md"
        jd.write_text(f"# 岗位\n**Company:** {company}\n", encoding="utf-8")
        return jd

    def test_missing_company_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            jd = self._job(Path(tmp), company="未知（待补充）")
            ctx = ActionContext(repo_root=Path(tmp), profile_dir=Path(tmp))
            with self.assertRaises(ValueError):
                run_research(None, ctx, jd)

    def test_research_flow_with_injected_search(self):
        import tempfile

        import jobsearch_agents.actions.research as research_mod

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jd = self._job(tmp_path)
            (tmp_path / "runs").mkdir()
            ctx = ActionContext(repo_root=tmp_path, profile_dir=tmp_path / "profile")
            profile = tmp_path / "profile"
            profile.mkdir(exist_ok=True)
            for name in ("candidate.md", "preferences.md", "evidence.md"):
                (profile / name).write_text("x", encoding="utf-8")
            original_evaluated = research_mod.EVALUATED_DIR
            original_runs = research_mod.RUNS_DIR
            (tmp_path / "evaluated").mkdir(exist_ok=True)
            research_mod.EVALUATED_DIR = tmp_path / "evaluated"
            research_mod.RUNS_DIR = tmp_path / "runs"
            original_search = research_mod.search_company
            original_fetch = research_mod.fetch_page
            research_mod.search_company = lambda company, max_results=4: [
                {"query": "q", "title": "官网", "url": "https://example.com/a", "snippet": "s"},
            ]
            research_mod.fetch_page = lambda url: "这是公司官网正文，内容足够长。" * 20
            try:
                client = ScriptedLLMClient([make_text_response("简报内容")])
                result = run_research(client, ctx, jd)
                self.assertEqual(result["company"], "望石智慧")
                self.assertEqual(result["sources"], ["https://example.com/a"])
                self.assertTrue((tmp_path / result["output_file"]).exists())
            finally:
                research_mod.EVALUATED_DIR = original_evaluated
                research_mod.RUNS_DIR = original_runs
                research_mod.search_company = original_search
                research_mod.fetch_page = original_fetch


if __name__ == "__main__":
    unittest.main()
