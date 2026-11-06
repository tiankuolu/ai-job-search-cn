import argparse
import json
import secrets
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--pdftoppm", type=Path, required=True)
parser.add_argument("--java-home", type=Path, required=True)
parser.add_argument("--gradle", type=Path, required=True)
parser.add_argument("--browser-channel", choices=["chrome", "msedge"], required=True)
args = parser.parse_args()
for tool in (args.pdftoppm, args.gradle, args.java_home / "bin" / "java.exe", args.java_home / "bin" / "javac.exe"):
    if not tool.is_file():
        raise FileNotFoundError(f"运行依赖不存在：{tool}")
root = Path(__file__).resolve().parents[1] / "runs" / "delivery"
root.mkdir(parents=True, exist_ok=True)
path = root / "settings.json"
if path.exists():
    settings = json.loads(path.read_text(encoding="utf-8"))
else:
    settings = {"bridge_url": "http://127.0.0.1:9527", "bridge_token": secrets.token_urlsafe(32)}
settings.update(java_home=str(args.java_home.resolve()), gradle=str(args.gradle.resolve()),
                browser_channel=args.browser_channel, tools={
    "browser_channel": args.browser_channel, "pdftoppm": str(args.pdftoppm.resolve()),
})
path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
print("本地投递服务配置已保存，凭据保存在 runs/delivery/settings.json")
