import json
import hashlib
from pathlib import Path

import pytest

from jobsearch_agents.actions.apply import _input_bundle
from jobsearch_agents.prompts import load_prompt
from jobsearch_agents.resume_sources import ASU_FILES, ResumePreferences, asu_guidance, conditional_experience_issues
from jobsearch_agents.actions.common import default_context
from jobsearch_agents.delivery.resume import ResumePlan, resume_preference_issues


pytestmark = pytest.mark.integration


def test_real_archives_are_used_without_baseline_or_legacy_evidence(workspace):
    assert not (workspace.data_root / "简历基版.tex").exists()
    (workspace.profile_dir / "evidence.md").unlink()
    profile = workspace.read_resume_profile()
    assert "## 项目经历" not in profile["candidate"]
    assert "## 专业技能" not in profile["candidate"]
    assert "## 教育背景" in profile["candidate"]
    for identifier in ("PAPER-05", "TRIP-05", "JOB-04", "DIFY-02", "TAU-05"):
        assert identifier in profile["project_facts"]
    sources = json.loads(profile["project_sources"])
    manifest = json.loads(profile["project_index"])
    assert {source["id"] for source in sources} == {item["id"] for item in manifest["projects"]}
    assert len(sources) == len(manifest["projects"])
    for source in sources:
        assert source["sha256"] == hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()
    job = next(workspace.data_root.glob("*/岗位JD.md"))
    bundle = _input_bundle(workspace, job)
    assert profile["project_facts"] in bundle
    assert profile["preferences"] in bundle


def test_confirmed_resume_preferences_match_real_materials(workspace):
    profile = workspace.read_resume_profile()
    preferences = ResumePreferences.model_validate_json(profile["resume_preferences"])
    assert len(preferences.fixed_awards) == 5
    assert "熟悉 Git 和 Linux 操作" in preferences.required_skills
    original = Path(__file__).resolve().parents[2] / ".artifacts/facts-resume-94f374ff/output/resume.json"
    plan = ResumePlan.model_validate_json(original.read_text(encoding="utf-8"))
    assert resume_preference_issues(plan, preferences)
    updated = plan.model_copy(update={"awards": preferences.fixed_awards,
                                      "skills": [
                                          "编程语言：Python、TypeScript",
                                          "前端开发：React、TypeScript、SSE",
                                          "后端开发：FastAPI、Pydantic、REST API",
                                          "服务与部署：MySQL、SQLite、Celery、Redis、Docker Compose；熟悉 Git 和 Linux 操作",
                                      ]})
    assert not resume_preference_issues(updated, preferences)
    incomplete = updated.model_copy(update={"awards": preferences.fixed_awards[:-1]})
    assert len(resume_preference_issues(incomplete, preferences)) == 1
    unclassified = updated.model_copy(update={"skills": [skill.partition("：")[2] for skill in updated.skills]})
    assert any("分类" in issue for issue in resume_preference_issues(unclassified, preferences))


def test_missing_real_archive_stops_material_generation(workspace):
    (workspace.profile_dir / "项目事实档案" / "论文研读智能体.md").unlink()
    with pytest.raises(FileNotFoundError):
        workspace.read_resume_profile()


def test_conditional_experience_checks_actual_jobs(workspace):
    original = default_context()
    preferences = ResumePreferences.model_validate_json(workspace.read_resume_profile()["resume_preferences"])
    archive = (workspace.profile_dir / "项目事实档案/Dify个人助手.md").read_text(encoding="utf-8")
    jobs = [path.read_text(encoding="utf-8") for path in original.data_root.rglob("岗位JD.md")]
    matching = next(job for job in jobs if "dify" in job.casefold())
    other = next(job for job in jobs if "dify" not in job.casefold())
    assert not conditional_experience_issues(archive, matching, preferences)
    assert conditional_experience_issues(archive, other, preferences)


def test_original_asu_guidance_is_loaded_for_writing_and_review():
    root = Path(__file__).resolve().parents[2]
    guidance, sources = asu_guidance(root)
    assert len(sources) == 4
    for file, source in zip(ASU_FILES, sources, strict=True):
        original = (root / "third_party" / "asu-skills" / file).read_text(encoding="utf-8")
        assert original in guidance
        assert len(source["sha256"]) == 64
    for name in ("writer", "reviewer"):
        prompt = load_prompt(name)
        assert guidance in prompt
        assert "95%—100%" in prompt
        assert "最小字号 9pt" in prompt


def test_archive_paths_cannot_escape_directory(workspace):
    path = workspace.profile_dir / "项目事实档案" / "index.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["projects"][0]["file"] = "../candidate.md"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="路径无效"):
        workspace.read_resume_profile()
