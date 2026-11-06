import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FILES = ["tokens.css", "base.css", "layout.css", "components.css", "shared.css"]
STYLE_DIRS = {
    "paper": "frontend/src/styles",
    "trip": "frontend-react/src/styles",
    "job": "frontend/src/styles",
}
SOURCE_DIRS = {
    "paper": "frontend/src",
    "trip": "frontend-react/src",
    "job": "frontend/src",
}
EXTERNAL_CLASSES = {"nodrag", "nopan", "nowheel", "is-selected"}
CLASS_PATTERN = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
CLASSNAME_PATTERN = re.compile(r"className\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|`([^`]*)`)")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def css_classes(path: Path) -> set[str]:
    return set(CLASS_PATTERN.findall(path.read_text(encoding="utf-8")))


def used_classes(paths: list[Path]) -> set[str]:
    names: set[str] = set()
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for match in CLASSNAME_PATTERN.finditer(source):
            value = next(group for group in match.groups() if group is not None)
            if "${" in value or any(char in value for char in "'\"=?:<>"):
                continue
            names.update(token for token in value.split() if token)
    return names


def inspect(root: Path, app: str) -> dict:
    style_dir = root / STYLE_DIRS[app]
    files = {}
    for name in FILES:
        path = style_dir / name
        files[name] = digest(path.read_text(encoding="utf-8").encode("utf-8"))
    defined = set()
    for name in FILES:
        defined.update(css_classes(style_dir / name))
    source_files = [path for path in (root / SOURCE_DIRS[app]).rglob("*") if path.suffix in {".tsx", ".ts"}]
    used = used_classes(source_files)
    feature_classes = set()
    for path in style_dir.glob("*.css"):
        if path.name not in FILES:
            feature_classes.update(css_classes(path))
    unresolved = sorted(used - defined - feature_classes - EXTERNAL_CLASSES)
    classes = sorted(defined)
    component_classes = sorted(name for name in defined if name.startswith("ui-"))
    return {
        "app": app,
        "files": files,
        "classHash": digest("\n".join(classes).encode()),
        "classCount": len(classes),
        "classes": classes,
        "sharedFiles": {"tokens.css": files["tokens.css"], "shared.css": files["shared.css"]},
        "componentClasses": component_classes,
        "componentHash": digest("\n".join(component_classes).encode()),
        "usedClassCount": len(used),
        "unresolvedClasses": unresolved,
    }


def app_id(root: Path) -> str:
    name = root.name
    if name == "paper-agent":
        return "paper"
    if name == "trip-planner-main":
        return "trip"
    if name == "ai-job-search-cn":
        return "job"
    raise SystemExit(f"无法从目录名判断应用：{name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--app", choices=sorted(STYLE_DIRS))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    app = args.app or app_id(root)
    current = inspect(root, app)
    contract_path = root / "ui-contract.json"
    if args.write:
        contract = {"version": 1, "files": FILES, "apps": {app: current}}
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: current[key] for key in ("app", "classHash", "classCount", "unresolvedClasses")}, ensure_ascii=False))
        return 0
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = contract["apps"].get(app)
    if expected is None:
        print(f"契约文件没有 {app} 的记录", file=sys.stderr)
        return 1
    problems = []
    for name in FILES:
        if name in ("tokens.css", "shared.css"):
            continue
        if current["files"][name] != expected["files"][name]:
            problems.append(f"{name} 哈希不一致：本地 {current['files'][name]}，契约 {expected['files'][name]}")
    for name, shared_hash in contract.get("shared", {}).items():
        if current["files"][name] != shared_hash:
            problems.append(f"共用文件 {name} 哈希不一致：本地 {current['files'][name]}，契约 {shared_hash}")
    if current["componentHash"] != contract.get("componentHash"):
        problems.append(f"组件类名哈希不一致：本地 {current['componentHash']}，契约 {contract.get('componentHash')}")
    if current["sharedFiles"] != contract.get("shared"):
        problems.append(f"共用文件清单不一致：本地 {current['sharedFiles']}，契约 {contract.get('sharedFiles')}")
    if current["classHash"] != expected["classHash"]:
        problems.append(f"类名清单哈希不一致：本地 {current['classHash']}，契约 {expected['classHash']}")
    shared = contract.get("sharedClasses", [])
    missing_shared = sorted(set(shared) - set(current["classes"]))
    if missing_shared:
        problems.append(f"缺少共享类名：{', '.join(missing_shared)}")
    for item in problems:
        print(item, file=sys.stderr)
    print(json.dumps({
        "app": app, "files": current["files"], "classHash": current["classHash"],
        "classCount": current["classCount"], "sharedClasses": len(shared),
        "unresolvedClasses": current["unresolvedClasses"], "problems": problems,
    }, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
