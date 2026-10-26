import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRIVATE_PATHS = (
    'salary_data.json', '.env', '.env.local', 'job_search_tracker.csv',
    'cv/chinese/main_personal.tex', 'cover_letters/chinese/cover_personal.tex',
    '.artifacts/analysis-result.json',
    'runs/trace.json',
)
PUBLIC_PATHS = (
    'AGENTS.md', '.agents/skills/china-job-search/SKILL.md',
    'markets/china/workflows/index.md', 'markets/china/profile/candidate.md',
    'markets/china/sources.json', 'cv/chinese/main_example.tex',
    'cover_letters/chinese/cover_example.tex',
)
FORBIDDEN_SCRIPTS = {'preinstall', 'install', 'postinstall', 'prepare', 'prepack'}


def ignored_paths(paths: tuple[str, ...]) -> set[str]:
    result = subprocess.run(
        ['git', 'check-ignore', '--no-index', '-z', '--stdin'],
        input=('\0'.join(paths) + '\0').encode('utf-8'),
        cwd=ROOT, capture_output=True,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()
    return set(result.stdout.decode('utf-8').rstrip('\0').split('\0')) - {''}


def validate_workspace() -> list[str]:
    errors = []
    ignored = ignored_paths(PRIVATE_PATHS)
    for path in PRIVATE_PATHS:
        if path not in ignored:
            errors.append(f'个人资料路径缺少 Git 忽略保护：{path}')
    for path in ignored_paths(PUBLIC_PATHS):
        errors.append(f'公共工作流或模板被 Git 忽略：{path}')
    if not (ROOT / '.agents/skills/china-job-search/SKILL.md').is_file():
        errors.append('缺少中国求职技能入口')
    for manifest in ROOT.glob('.agents/**/package.json'):
        if 'node_modules' in manifest.parts:
            continue
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise TypeError(f'{manifest}：依赖清单必须为 JSON 对象')
        scripts = data.get('scripts', {})
        if not isinstance(scripts, dict):
            raise TypeError(f'{manifest}：scripts 必须为 JSON 对象')
        for name in FORBIDDEN_SCRIPTS.intersection(scripts):
            errors.append(f'{manifest.relative_to(ROOT)}：禁止自动执行 {name}')
        if 'trustedDependencies' in data:
            errors.append(f'{manifest.relative_to(ROOT)}：禁止启用依赖自动执行')
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    errors = validate_workspace()
    if errors:
        print('\n'.join(errors))
        return 1
    print('security_guards: OK（个人资料保护、公共入口和依赖清单）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
