import os
from pathlib import Path

from pathvalidate import sanitize_filename


def filesystem_path(path: Path) -> Path:
    absolute = str(path.resolve())
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    return Path("\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute)


def native_path(path: Path) -> Path:
    absolute = str(path.resolve())
    if absolute.startswith("\\\\?\\UNC\\"):
        absolute = "\\\\" + absolute[8:]
    elif absolute.startswith("\\\\?\\"):
        absolute = absolute[4:]
    return Path(absolute)


def browser_file_uri(path: Path) -> str:
    return native_path(path).as_uri()


def resume_filename(company: str | None, title: str, suffix: str) -> str:
    company = (company or "").strip()
    if company in {"公司未注明", "用户提供的岗位正文未注明"}:
        company = ""
    name = sanitize_filename(f"{company}-{title.strip()}", replacement_text="_", platform="Windows", max_len=230)
    return name + suffix


def name_resume_assets(assets: dict, company: str | None, title: str) -> dict:
    renamed = dict(assets)
    for kind in ("html", "pdf", "image"):
        if kind not in assets:
            continue
        source = Path(assets[kind])
        target = source.with_name(resume_filename(company, title, source.suffix))
        if source != target:
            if target.exists():
                raise FileExistsError(f"简历文件已经存在：{target}")
            filesystem_path(source).rename(filesystem_path(target))
        renamed[kind] = str(filesystem_path(target))
    return renamed
