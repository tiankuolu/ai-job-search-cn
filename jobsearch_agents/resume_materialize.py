# 岗位定制简历落盘：从申请包的 CUSTOMIZE 参数行机械生成各岗位文件夹。
# 每个岗位文件夹 = 简历.tex（基版替换标题/意向行/项目顺序）+ 编译 PDF + 打招呼语.md。
# 版面规则：黑客松与竞赛节固定在项目经历之后；行距自动调优取「仍为一页」的最大值。
# 用法：py -m jobsearch_agents.resume_materialize [--all | --pack 文件名]

import json
import re
import subprocess
import sys
from pathlib import Path

import fitz  # PyMuPDF

RESUME_ROOT = Path(r"C:\Users\28400\Desktop\全部文件夹\卢天阔_AI-Agent简历")
BASE = RESUME_ROOT / "简历基版.tex"
TECTONIC = Path.home() / "AppData" / "Local" / "Programs" / "tectonic" / "tectonic.exe"
EVALUATED = Path(__file__).resolve().parent.parent / "markets" / "china" / "jobs" / "evaluated"

BLOCK_ANCHORS = {
    "paper": r"\textbf{本地论文研读智能体（独立开发）}",
    "trip": r"\textbf{智能旅行规划助手（个人项目）}",
    "jobsearch": r"\textbf{多智能体求职系统（独立开发，生产运行中）}",
}
SPREADS = [1.08, 1.06, 1.04, 1.02, 1.00, 0.98, 0.96, 0.94, 0.92]
CUSTOMIZE_RE = re.compile(
    r"CUSTOMIZE:\s*(\{.*?\})", re.DOTALL
)


def split_blocks(text: str) -> tuple[str, dict[str, str], str]:
    """项目经历章节切成三个主力项目块。"""
    section_start = text.index(r"\section*{项目经历}")
    next_section = text.index(r"\section*{黑客松")
    head = text[:section_start + len(r"\section*{项目经历}") + 1]
    tail = text[next_section:]
    body = text[section_start + len(r"\section*{项目经历}") + 1:next_section]
    positions = {}
    for name, anchor in BLOCK_ANCHORS.items():
        idx = body.index(anchor)
        positions[name] = body.rfind("\n", 0, idx) + 1
    order = sorted(positions.items(), key=lambda kv: kv[1])
    blocks = {}
    for i, (name, start) in enumerate(order):
        end = order[i + 1][1] if i + 1 < len(order) else len(body)
        blocks[name] = body[start:end]
    return head, blocks, tail


def page_stats(pdf: Path) -> tuple[int, float]:
    doc = fitz.open(pdf)
    pages = doc.page_count
    fill = 0.0
    if pages >= 1:
        bottoms = [b[3] for b in doc[0].get_text("blocks") if b[4].strip()]
        fill = (max(bottoms) / doc[0].rect.height) if bottoms else 0.0
    doc.close()
    return pages, fill


def tune_and_compile(tex: Path) -> tuple[float, float] | None:
    original = tex.read_text(encoding="utf-8")
    for spread in SPREADS:
        tex.write_text(original.replace("LINESPREAD", str(spread)), encoding="utf-8")
        pdf = tex.parent / "简历.pdf"
        if pdf.exists():
            pdf.unlink()
        proc = subprocess.run([str(TECTONIC), tex.name], cwd=tex.parent, capture_output=True)
        if proc.returncode != 0 or not pdf.exists():
            continue
        pages, fill = page_stats(pdf)
        if pages == 1:
            target = tex.parent / f"卢天阔-{tex.parent.name.split('-')[0]}-实习简历.pdf"
            for old in tex.parent.glob("卢天阔-*.pdf"):
                if old != pdf:
                    try:
                        old.unlink()
                    except OSError:
                        pass
            try:
                pdf.rename(target)
            except OSError:
                print(f"  注意：{target.name} 被占用，成品保留为 简历.pdf")
            return spread, fill
    return None


def extract_greeting(pack_text: str) -> str:
    start = pack_text.index("## BOSS Greeting")
    end = pack_text.index("## ", start + 4)
    return pack_text[start:end].strip()


def materialize_pack(pack_path: Path, base_head: str, blocks: dict[str, str], base_tail: str,
                     force: bool = False) -> tuple[str, str] | None:
    """从单个申请包解析 CUSTOMIZE 参数并落盘。返回（文件夹名, 状态）。"""
    text = pack_path.read_text(encoding="utf-8")
    match = CUSTOMIZE_RE.search(text)
    if not match:
        return pack_path.name, "缺少 CUSTOMIZE 参数行（旧版申请包），跳过"
    params = json.loads(match.group(1))
    folder = params["folder"]
    order = params["order"]
    if sorted(order) != sorted(BLOCK_ANCHORS):
        return folder, f"order 非法：{order}"
    target_dir = RESUME_ROOT / folder
    if target_dir.exists() and not force:
        return folder, "文件夹已存在，跳过（force 重生成请删除后重跑）"

    tex_text = base_head
    for name in order:
        tex_text += blocks[name]
    tex_text += base_tail
    tex_text = tex_text.replace("{JOB_TITLE}", params["job_title"])
    tex_text = tex_text.replace("{JOB_TAGLINE}", params["job_tagline"])
    target_dir.mkdir(parents=True, exist_ok=True)
    tex = target_dir / "简历.tex"
    tex.write_text(tex_text, encoding="utf-8")

    result = tune_and_compile(tex)
    if result is None:
        return folder, "编译调优失败"

    greeting = extract_greeting(text)
    (target_dir / "打招呼语.md").write_text(
        f"# 打招呼语 — {params['job_title']}\n\n"
        f"来源：{pack_path.name}（完整申请材料见找工作仓库 evaluated 目录）\n\n{greeting}\n",
        encoding="utf-8",
    )
    return folder, f"行距 {result[0]}，填充率 {result[1]:.0%}"


def main(argv: list[str]) -> int:
    if not TECTONIC.exists():
        print(f"tectonic 不存在：{TECTONIC}")
        return 1
    base_text = BASE.read_text(encoding="utf-8")
    if "LINESPREAD" not in base_text:
        print("基版缺少 LINESPREAD 占位符")
        return 1
    missing = [a for a in BLOCK_ANCHORS.values() if a not in base_text]
    if missing:
        print(f"基版锚点缺失：{missing}")
        return 1
    head, blocks, tail = split_blocks(base_text)

    force = "--force" in argv
    packs = sorted(EVALUATED.glob("*-application.md"))
    if "--pack" in argv:
        wanted = argv[argv.index("--pack") + 1]
        packs = [p for p in packs if wanted in p.name]
        if not packs:
            print(f"找不到匹配的申请包：{wanted}")
            return 1

    failures = 0
    for pack in packs:
        name, status = materialize_pack(pack, head, blocks, tail, force=force)
        print(f"{name[:40]} → {status}")
        if "失败" in status or "非法" in status or "缺少" in status:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
