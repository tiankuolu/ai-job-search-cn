import subprocess
import sys
import unittest
from pathlib import Path

import frontmatter


ROOT = Path(__file__).resolve().parent.parent


class WorkspaceSkillValidation(unittest.TestCase):
    def test_linter_passes_on_current_workspace(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools/lint_skills.py')],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True,
        )
        self.assertIn('lint_skills: OK', result.stdout)

    def test_china_skill_declares_name_and_description(self):
        post = frontmatter.load(ROOT / '.agents/skills/china-job-search/SKILL.md')
        self.assertEqual(post['name'], 'china-job-search')
        self.assertTrue(post['description'].strip())

    def test_both_hosts_have_project_guidance(self):
        text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('Codex', text)
        self.assertIn('ZCode', text)
        self.assertIn('markets/china/workflows/index.md', text)
        self.assertTrue((ROOT / 'docs/zcode.md').is_file())


if __name__ == '__main__':
    unittest.main()
