#!/usr/bin/env python3
"""Read-only local diagnostics. No network requests or third-party dependencies."""
import argparse
import json
import os
import platform
import sys
from pathlib import Path


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='检查 Skill 文件、Python 版本和可选素材目录权限。')
    parser.add_argument('--folder', type=Path, help='要检查的素材目录（只读检查，不创建文件）')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    required = ['SKILL.md', 'references/naming-rules.md', 'scripts/apply_rename_plan.py']
    missing = [p for p in required if not (root / p).is_file()]
    result = {'platform': platform.system(), 'python': sys.executable,
              'version': platform.python_version(), 'python_ok': sys.version_info >= (3, 9),
              'skill_root': str(root), 'missing_files': missing,
              'third_party_packages_required': False}
    ok = result['python_ok'] and not missing
    if args.folder:
        folder = args.folder.expanduser().resolve()
        result['folder'] = str(folder)
        result['folder_readable'] = folder.is_dir() and os.access(folder, os.R_OK)
        result['folder_writable_estimate'] = folder.is_dir() and os.access(folder, os.W_OK)
        result['permission_note'] = '只读估计；实际写入仍取决于宿主授权、ACL 和文件占用。'
        ok = ok and result['folder_readable'] and result['folder_writable_estimate']
    result['ok'] = bool(ok)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
