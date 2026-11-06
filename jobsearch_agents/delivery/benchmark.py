import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import jsonpatch
from pydantic import BaseModel, ConfigDict

from ..actions.common import REPO_ROOT, RUNS_DIR, default_context
from ..resume_sources import ResumePreferences
from .generation import DraftPatch, ResumeDraft, apply_draft_patch, initial_draft


class OfficeTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    capability: str
    need: str
    test: str
    acceptance: str


TASKS = [
    OfficeTask(task_id="office-claim-coverage", capability="fact_provenance",
               need="每条项目正文、技能、打招呼语分别关联事实，接受定位字段的合法事实关联",
               test="test_claim_coverage_real.py", acceptance="重放真实模型草稿；合法草稿通过，遗漏及重复路径被拒绝"),
    OfficeTask(task_id="office-fact-identifiers", capability="fact_provenance",
               need="拒绝模型返回的项目简称，必须引用具体事实编号",
               test="test_writer_fact_ids_real.py", acceptance="真实滴滴岗位模型输出通过正式入口校验"),
    OfficeTask(task_id="office-targeted-revision", capability="document_revision",
               need="修改指定项目时保留人工修改的标题、样式及其他项目",
               test="test_resume_revision_preserves_edits_real.py", acceptance="真实 HTML 经正式排版和 PDF 导出，其他内容保留"),
    OfficeTask(task_id="office-version-ownership", capability="version_management",
               need="选取历史版本重新修改时检查版本所属岗位",
               test="test_resume_versions_real.py", acceptance="真实岗位跨版本请求返回 409，历史版本内容保持一致"),
    OfficeTask(task_id="office-patch-paths", capability="structured_editing",
               need="模型修改路径必须合法，修改结果与实际导出内容一致",
               test="test_resume_patch_paths_real.py", acceptance="真实模型修改记录通过 JSON Patch 正式处理并核对导出正文"),
    OfficeTask(task_id="office-manual-export", capability="document_export",
               need="人工正文保存后直接导出，保持教育写法与当前正文",
               test="test_resume_editor_real.py", acceptance="真实浏览器导出后检查 PDF 文本及当前 HTML"),
    OfficeTask(task_id="office-jd-import", capability="document_understanding",
               need="导入真实岗位正文、PDF、图片和扫描件，允许公司名称为空",
               test="test_jd_import_real.py", acceptance="正式解析、OCR 和导入接口保留岗位信息"),
    OfficeTask(task_id="office-url-import", capability="web_understanding",
               need="从官网完整读取职责和要求，招聘网页需要登录时依据真实登录状态处理",
               test="test_url_import_real.py", acceptance="官网正文逐项核对原始响应；BOSS 读取真实登录状态"),
    OfficeTask(task_id="office-export-filename", capability="document_export",
               need="导出使用公司-岗位名称，公司为空时保留空白公司部分",
               test="test_resume_filenames_real.py", acceptance="正式下载接口返回准确名称和原始 PDF 字节"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edit_analysis(before: dict, after: dict) -> list[dict]:
    changes = jsonpatch.make_patch(before, after).patch
    return [{**change, "category": "fact_links" if change["path"].startswith("/claims")
             else "project_content" if change["path"].startswith("/plan/projects")
             else "skill_content" if change["path"].startswith("/plan/skills") else "other_content"}
            for change in changes]


def prepare_reviews(output: Path) -> dict:
    context = default_context()
    profile = context.read_resume_profile()
    database_path = RUNS_DIR / "delivery/state.sqlite"
    with sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True) as database:
        jobs = {row["id"]: row for (data,) in database.execute("SELECT data FROM jobs")
                for row in [json.loads(data)]}
        packages = [json.loads(data) for (data,) in database.execute("SELECT data FROM packages")]
    reviews = []
    for package in packages:
        application = Path(package["application"]) if package.get("application") else None
        if package.get("status") != "ready" or not application or application.suffix != ".json" or not application.is_file():
            continue
        evidence = json.loads(application.read_text(encoding="utf-8"))
        draft = ResumeDraft.model_validate(evidence["draft"])
        job = jobs[package["job_id"]]
        reviews.append({"task_id": package["id"], "job_id": job["id"],
                        "full_jd": job["description"], "company": job["company"], "title": job["title"],
                        "draft": draft.model_dump(),
                        "source": {"application": str(application), "sha256": sha256(application),
                                   "trace": package.get("trace"), "editor_revision": package.get("editor_revision")},
                        "review": {"duties_covered": None, "requirements_covered": None,
                                   "project_selection_supported": None, "facts_supported": None,
                                   "rationale": "", "annotator": ""}})
    if not reviews:
        raise ValueError("没有可核验的真实岗位申请包")
    (output / "relevance-review.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    sources = json.loads(profile["project_sources"])
    fact_directory = output / "fact-snapshots"
    fact_directory.mkdir()
    for source in sources:
        path = Path(source["path"])
        if sha256(path) != source["sha256"]:
            raise ValueError(f"准备复核期间事实档案发生变化：{path.name}")
        (fact_directory / path.name).write_bytes(path.read_bytes())
    (output / "fact-sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    trace_path = REPO_ROOT / ".artifacts/resume-speed-comparison-20261031/samples/acaea5439b835d4eb614afa7-2-optimized"
    trace = json.loads(next(trace_path.glob("comparison-*.json")).read_text(encoding="utf-8"))
    experiment_profile = context.__class__(Path(r"D:\work"), REPO_ROOT / ".artifacts/resume-speed-comparison-20261031/profile").read_resume_profile()
    preferences = ResumePreferences.model_validate_json(experiment_profile["resume_preferences"])
    before = initial_draft(trace["calls"][0]["response"]["content"], preferences, experiment_profile, "Harness算法实习生")
    after = apply_draft_patch(before, DraftPatch.model_validate_json(trace["calls"][2]["response"]["content"]))
    changes = edit_analysis(before.model_dump(), after.model_dump())
    (output / "recorded-revision.json").write_text(json.dumps({"trace": trace["run_id"],
        "origin": "真实模型审查后修改", "changes": changes,
        "semantic_change_reason": "需要逐项人工判断，程序仅记录操作与字段类别"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"real_application_packages": len(reviews), "fact_sources": len(sources),
            "semantic_review_status": "pending_human_review"}


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    provenance = prepare_reviews(output)
    snapshots = output / "source"
    snapshots.mkdir()
    hashes = {}
    for path in sorted((REPO_ROOT / "jobsearch_agents").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT)
        target = snapshots / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        hashes[str(relative)] = sha256(path)
    results = []
    for task in TASKS:
        directory = output / task.task_id
        directory.mkdir()
        test = REPO_ROOT / "tests/acceptance" / task.test
        (directory / task.test).write_bytes(test.read_bytes())
        started = time.perf_counter()
        with (directory / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.run([sys.executable, "-m", "pytest", str(test), "-q", "-m", "integration",
                                      "--basetemp", str(directory / "workspace"),
                                      "--junitxml", str(directory / "results.xml")],
                                     cwd=REPO_ROOT, stdout=log, stderr=log, check=False)
        tree = ET.parse(directory / "results.xml")
        cases = []
        for case in tree.findall(".//testcase"):
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            status = "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"
            cases.append({"name": case.get("name"), "seconds": float(case.get("time", 0)), "status": status,
                          "failure": ET.tostring(failure if failure is not None else error, encoding="unicode")
                          if failure is not None or error is not None else None})
        if not cases:
            raise ValueError(f"任务未实际执行验收：{task.task_id}")
        record = {**task.model_dump(), "source_sha256": sha256(test),
                  "exit_code": process.returncode, "latency_s": time.perf_counter()-started,
                  "cases": cases, "passed": process.returncode == 0 and all(c["status"] == "passed" for c in cases)}
        results.append(record)
        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"task_id": task.task_id, "passed": record["passed"], "checks": len(cases)}), flush=True)
    summary = {"tasks": len(results), "passed_tasks": sum(r["passed"] for r in results),
               "checks": sum(len(r["cases"]) for r in results), "provenance": provenance,
               "source_sha256": hashes, "results_sha256": sha256(output / "results.json"),
               "scope": "真实历史需求与输出的工具和文件回归验收；岗位语义相关性单独人工审核"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary["passed_tasks"] != summary["tasks"]:
        raise AssertionError("办公任务回归存在失败，详见逐任务日志")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.output.resolve())
    print(json.dumps({key: value for key, value in result.items() if key != "source_sha256"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
