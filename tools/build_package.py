#!/usr/bin/env python3
"""Build a portable ZIP from an explicit public-file allowlist."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'README.md', 'install.py', 'agents/openai.yaml',
         'references/naming-rules.md', 'scripts/apply_rename_plan.py', 'scripts/doctor.py']


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    out = ROOT / 'dist' / 'design-asset-organizer.zip'
    for name in FILES:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info = zipfile.ZipInfo('design-asset-organizer/' + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / name).read_bytes())
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(digest + '  ' + out.name + '\n', encoding='ascii')
    print(str(out))
    print('SHA256: ' + digest)


if __name__ == '__main__':
    main()
