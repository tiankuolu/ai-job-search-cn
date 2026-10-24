# 投递状态跟踪：投递之后的闭环管理（岗位/阶段/跟进记录）。
# 状态表存 markets/china/jobs/evaluated/delivery-status.csv（gitignore 内）。

import csv
from datetime import date
from pathlib import Path

STAGES = ["未投递", "已投递", "已读", "约面", "面试中", "挂了", "offer"]
STATUS_FILE = Path(__file__).resolve().parent.parent.parent / "markets" / "china" / "jobs" / "evaluated" / "delivery-status.csv"
COLUMNS = ["job_file", "company", "role", "stage", "applied_date", "last_update", "note"]


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def init_from_evaluated(evaluation_dir: Path, status_path: Path = STATUS_FILE) -> list[dict]:
    """把有评估报告但不在状态表的岗位补进去（阶段=未投递）。返回全表。"""
    rows = _load(status_path)
    known = {r["job_file"] for r in rows}
    for pack in sorted(evaluation_dir.glob("*-application.md")):
        job_file = pack.name.replace("-application.md", ".md")
        if job_file in known:
            continue
        company = "未知"
        role = job_file
        for line in pack.read_text(encoding="utf-8").splitlines():
            if line.startswith("# Application Pack:"):
                # 形如 "# Application Pack: {岗位} @ {公司}"
                rest = line.replace("# Application Pack:", "").strip()
                if "@" in rest:
                    role_part, company_part = rest.rsplit("@", 1)
                    role, company = role_part.strip(), company_part.strip()
                break
        rows.append({
            "job_file": job_file, "company": company, "role": role,
            "stage": "未投递", "applied_date": "", "last_update": date.today().isoformat(),
            "note": "",
        })
    _save(status_path, rows)
    return rows


def set_stage(job_file: str, stage: str, status_path: Path = STATUS_FILE,
              note: str = "", applied: bool = False) -> dict:
    """更新某岗位的投递阶段。岗位不存在或阶段非法就地崩溃。"""
    if stage not in STAGES:
        raise ValueError(f"非法阶段：{stage}，可选 {'/'.join(STAGES)}")
    rows = _load(status_path)
    for row in rows:
        if row["job_file"] == job_file or row["job_file"].startswith(job_file):
            row["stage"] = stage
            row["last_update"] = date.today().isoformat()
            if note:
                row["note"] = note
            if applied and not row["applied_date"]:
                row["applied_date"] = date.today().isoformat()
            _save(status_path, rows)
            return row
    raise KeyError(f"状态表中没有该岗位：{job_file}")


def render_table(rows: list[dict]) -> str:
    """渲染 markdown 状态表，按阶段权重排序（面试中 > 约面 > 已读 > 已投递 > 未投递 > 挂了 > offer）。"""
    weight = {s: i for i, s in enumerate(["面试中", "约面", "已读", "已投递", "offer", "未投递", "挂了"])}
    ordered = sorted(rows, key=lambda r: weight.get(r["stage"], 99))
    lines = [
        "| 岗位 | 公司 | 阶段 | 投递日期 | 最近更新 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for r in ordered:
        lines.append(
            f"| {r['job_file'].replace('.md', '')} | {r['company']} | {r['stage']} "
            f"| {r['applied_date'] or '—'} | {r['last_update']} | {r['note'] or '—'} |"
        )
    return "\n".join(lines)
