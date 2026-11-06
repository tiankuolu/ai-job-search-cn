from pathlib import Path

import pytest

from jobsearch_agents.delivery.service import DeliveryService


pytestmark = pytest.mark.integration


def test_analysis_version_changes_with_real_job_preferences_and_rules(workspace, tmp_path: Path):
    job = {"jd_path": str(next(workspace.data_root.glob("*/岗位JD.md")))}
    service = DeliveryService(workspace, tmp_path / "delivery")
    try:
        original = service.analysis_fingerprint(job)
        assert original == service.analysis_fingerprint(job)
        jd = Path(job["jd_path"])
        jd.write_text(jd.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed_job = service.analysis_fingerprint(job)
        assert changed_job != original
        preferences = workspace.profile_dir / "preferences.md"
        preferences.write_text(preferences.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed_preferences = service.analysis_fingerprint(job)
        assert changed_preferences != changed_job
        rules = workspace.repo_root / "AGENTS.md"
        rules.write_text(rules.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert service.analysis_fingerprint(job) != changed_preferences
    finally:
        service.executor.shutdown(wait=True)
