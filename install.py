#!/usr/bin/env python3
"""Install the self-contained skill; existing installs are backed up, never merged."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

NAME = 'design-asset-organizer'
FILES = ['SKILL.md', 'README.md', 'LICENSE', 'agents/openai.yaml',
         'references/naming-rules.md', 'scripts/apply_rename_plan.py', 'scripts/doctor.py']


def install(source: Path, target: Path, replace: bool = False):
    source, target = source.resolve(), target.expanduser().absolute()
    if target.is_symlink():
        raise ValueError('安装位置是符号链接，请手动检查，避免覆盖其他目录。')
    target = target.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('安装位置不能与源码目录重叠。')
    if target.exists() and not replace:
        raise ValueError('已存在安装。更新请加 --replace；旧版会自动备份。')
    if target.exists() and not (target / 'SKILL.md').is_file():
        raise ValueError('目标不是 Skill 目录，拒绝替换。--dest 应包含最后一级技能文件夹。')
    for name in FILES:
        if not (source / name).is_file():
            raise ValueError('安装包不完整，缺少：' + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so the final directory rename is atomic.
    with tempfile.TemporaryDirectory(prefix='.dao-install-', dir=target.parent) as tmp:
        staged = Path(tmp) / NAME
        staged.mkdir()
        for name in FILES:
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, destination)
        backup = None
        if target.exists():
            # Outside the scanned skills directory to avoid duplicate discovery.
            backup = target.parent.parent / 'skill-backups' / (target.name + '-' + uuid.uuid4().hex[:12])
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    return target, backup


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='安装图片素材命名 Skill 到 Codex；不需要 pip。')
    parser.add_argument('--dest', type=Path, default=Path.home() / '.agents' / 'skills' / NAME,
                        help='完整目标目录；默认为 ~/.agents/skills/design-asset-organizer')
    parser.add_argument('--replace', action='store_true', help='备份已安装版本后更新')
    args = parser.parse_args()
    if sys.version_info < (3, 9):
        parser.error('需要 Python 3.9 或更新版本；也可按 README 手动复制安装。')
    try:
        target, backup = install(Path(__file__).resolve().parent, args.dest, args.replace)
        print('安装完成：' + str(target))
        if backup:
            print('旧版备份：' + str(backup))
        print('在 Codex 中新建聊天，输入 $design-asset-organizer 并附图。若未识别，请重启 Codex。')
        return 0
    except (OSError, ValueError) as exc:
        print('安装失败：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
