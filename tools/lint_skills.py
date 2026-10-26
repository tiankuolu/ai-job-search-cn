import json
import sys
from pathlib import Path

import frontmatter


ROOT = Path(__file__).resolve().parent.parent


def validate_workspace(root: Path) -> list[str]:
    errors = []
    skills = sorted(root.glob('.agents/skills/*/SKILL.md'))
    if not skills:
        errors.append('未找到技能文件')
    for path in skills:
        metadata = frontmatter.load(path).metadata
        for key in ('name', 'description'):
            if not isinstance(metadata.get(key), str) or not metadata[key].strip():
                errors.append(f'{path.relative_to(root)}：缺少有效的 {key}')
    for relative in (
        'AGENTS.md', 'markets/china/workflows/index.md',
        'markets/china/workflows/runtime.md',
        'markets/china/workflows/setup-profile.md',
        'markets/china/workflows/scrape-jobs.md',
        'markets/china/workflows/analyze-job.md',
        'markets/china/workflows/apply-job.md',
        'markets/china/workflows/rank-jobs.md',
        'markets/china/workflows/interview-prep.md',
    ):
        if not (root / relative).is_file():
            errors.append(f'缺少必需文件：{relative}')
    sources = json.loads((root / 'markets/china/sources.json').read_text(encoding='utf-8'))
    if sources.get('market') != 'china-mainland' or not sources.get('platforms'):
        errors.append('招聘来源缺少中国大陆市场配置')
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    errors = validate_workspace(ROOT)
    if errors:
        print('\n'.join(errors))
        return 1
    print('lint_skills: OK（技能、中国任务入口和招聘来源）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
