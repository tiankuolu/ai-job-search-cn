import subprocess
import sys
import unittest
from pathlib import Path

from tools.security_guards import PRIVATE_PATHS, PUBLIC_PATHS, ignored_paths


ROOT = Path(__file__).resolve().parent.parent


class WorkspacePrivacyGuards(unittest.TestCase):
    def test_guard_passes_on_current_workspace(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools/security_guards.py')],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True,
        )
        self.assertIn('security_guards: OK', result.stdout)

    def test_every_personal_output_path_is_protected(self):
        self.assertEqual(ignored_paths(PRIVATE_PATHS), set(PRIVATE_PATHS))

    def test_shared_rules_and_templates_can_be_tracked(self):
        self.assertEqual(ignored_paths(PUBLIC_PATHS), set())
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())


if __name__ == '__main__':
    unittest.main()
