import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RENAME = module('rename', ROOT / 'scripts/apply_rename_plan.py')
INSTALL = module('installer', ROOT / 'install.py')


class RegressionTests(unittest.TestCase):
    def test_swap_and_three_way_cycle_rollback(self):
        for count in (2, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                files = [root / (str(i) + '.jpg') for i in range(count)]
                for i, file in enumerate(files):
                    file.write_bytes(str(i).encode())
                pairs, _ = RENAME.prepare_plan([
                    {'source': str(file), 'target': files[(i + 1) % count].name}
                    for i, file in enumerate(files)], root)
                RENAME.apply_pairs(pairs)
                manifest = root / 'manifest.json'
                RENAME.write_manifest(manifest, pairs)
                RENAME.apply_pairs(RENAME.load_rollback_pairs(manifest))
                self.assertEqual([f.read_bytes() for f in files], [str(i).encode() for i in range(count)])

    def test_unchanged_item_does_not_block_batch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / 'a.JPG', root / 'b.png'
            a.write_bytes(b'a')
            b.write_bytes(b'b')
            pairs, _ = RENAME.prepare_plan([
                {'source': str(a), 'target': a.name},
                {'source': str(b), 'target': 'new.png'}], root)
            RENAME.apply_pairs(pairs)
            self.assertEqual(a.read_bytes(), b'a')
            self.assertEqual((root / 'new.png').read_bytes(), b'b')

    def test_cycle_failure_restores_every_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            files = [root / (str(i) + '.jpg') for i in range(3)]
            for i, f in enumerate(files):
                f.write_bytes(str(i).encode())
            pairs = [(f, files[(i + 1) % 3]) for i, f in enumerate(files)]
            original = RENAME.move_no_overwrite
            calls = 0

            def fail_once(source, target):
                nonlocal calls
                calls += 1
                if calls == 6:
                    raise OSError('simulated failure after two completed moves')
                original(source, target)

            with patch.object(RENAME, 'move_no_overwrite', side_effect=fail_once):
                with self.assertRaises(OSError):
                    RENAME.apply_pairs(pairs)
            self.assertEqual([f.read_bytes() for f in files], [b'0', b'1', b'2'])
            self.assertEqual(len(list(root.iterdir())), 3)

    def test_late_collision_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / 'a.jpg', root / 'b.jpg'
            a.write_bytes(b'original')
            original = RENAME.move_no_overwrite

            def create_collision(source, target):
                if target == b:
                    b.write_bytes(b'other program')
                original(source, target)

            with patch.object(RENAME, 'move_no_overwrite', side_effect=create_collision):
                with self.assertRaises(OSError):
                    RENAME.apply_pairs([(a, b)])
            self.assertEqual(a.read_bytes(), b'original')
            self.assertEqual(b.read_bytes(), b'other program')

    def test_invalid_names_and_duplicate_targets(self):
        for name in ('CON.extra.jpg', 'bad*.jpg', '../a.jpg', 'a.jpg ', '图' * 90 + '.jpg'):
            with self.subTest(name=name), self.assertRaises(RENAME.PlanError):
                RENAME.validate_filename(name)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / 'a.jpg', root / 'b.jpg'
            a.write_bytes(b'a')
            b.write_bytes(b'b')
            with self.assertRaises(RENAME.PlanError):
                RENAME.prepare_plan([{'source':str(a),'target':'same.jpg'},
                                     {'source':str(b),'target':'SAME.jpg'}], root)

    def test_manifest_write_failure_prevents_rename(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'a.jpg'
            source.write_bytes(b'original')
            plan = root / 'plan.json'
            plan.write_text(json.dumps([{'source':str(source),'target':'b.jpg'}]), encoding='utf-8')
            manifest = root / 'existing.json'
            manifest.write_bytes(b'previous recovery record')
            command = [sys.executable, str(ROOT / 'scripts/apply_rename_plan.py'), str(plan),
                       '--apply', '--manifest', str(manifest)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse((root / 'b.jpg').exists())
            self.assertEqual(manifest.read_bytes(), b'previous recovery record')

    def test_absolute_cli_from_unrelated_cwd_preview_apply_rollback(self):
        with tempfile.TemporaryDirectory(prefix='dao 中文 space ') as d:
            root = Path(d)
            source = root / '原图.JPEG'
            source.write_bytes(b'image content')
            plan = root / 'plan.json'
            plan.write_text(json.dumps([{'source':source.name, 'target':'人物＊海报＊摄影＊蓝色＊特写.JPEG'}]), encoding='utf-8-sig')
            manifest = root / 'record.json'
            base = [sys.executable, str(ROOT / 'scripts/apply_rename_plan.py')]

            def run(args):
                return subprocess.run(base + args, cwd=root.parent, capture_output=True,
                                      encoding='utf-8', env=dict(os.environ, PYTHONIOENCODING='ascii'))

            result = run([str(plan)])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(source.exists())
            result = run([str(plan), '--apply', '--manifest', str(manifest)])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(source.exists())
            self.assertEqual(json.loads(manifest.read_text('utf-8'))['status'], 'applied')
            result = run(['--rollback', str(manifest), '--apply'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_bytes(), b'image content')
            result = run(['--rollback', str(manifest), '--apply'])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(source.read_bytes(), b'image content')


class DistributionTests(unittest.TestCase):
    def test_install_update_backup_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'skills' / INSTALL.NAME
            INSTALL.install(ROOT, target)
            marker = target / 'my-settings.txt'
            marker.write_bytes(b'preserve me')
            with self.assertRaises(ValueError):
                INSTALL.install(ROOT, target)
            _, backup = INSTALL.install(ROOT, target, replace=True)
            self.assertEqual((backup / marker.name).read_bytes(), b'preserve me')
            self.assertNotIn(target.parent, backup.parents)
            self.assertFalse(marker.exists())

    def test_failed_update_restores_previous_install(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'skills' / INSTALL.NAME
            INSTALL.install(ROOT, target)
            marker = target / 'marker'
            marker.write_bytes(b'old')
            original = Path.rename

            def fail_staged(source, destination):
                if source.parent.name.startswith('.dao-install-'):
                    raise OSError('simulated install failure')
                return original(source, destination)

            with patch.object(Path, 'rename', fail_staged), self.assertRaises(OSError):
                INSTALL.install(ROOT, target, replace=True)
            self.assertEqual(marker.read_bytes(), b'old')

    def test_installer_rejects_overlap_and_unrelated_destination(self):
        with self.assertRaises(ValueError):
            INSTALL.install(ROOT, ROOT / 'inside')
        with self.assertRaises(ValueError):
            INSTALL.install(ROOT, ROOT / '..' / ROOT.name / 'inside')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                INSTALL.install(ROOT, Path(d), replace=True)

    def test_package_can_be_extracted_installed_and_diagnosed(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/build_package.py')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with zipfile.ZipFile(ROOT / 'dist/design-asset-organizer.zip') as archive:
                self.assertTrue(all(n.startswith('design-asset-organizer/') for n in archive.namelist()))
                self.assertFalse(any('__pycache__' in n for n in archive.namelist()))
                self.assertEqual(archive.read('design-asset-organizer/LICENSE'), (ROOT / 'LICENSE').read_bytes())
                archive.extractall(root)
            installer = root / INSTALL.NAME / 'install.py'
            target = root / 'installed' / INSTALL.NAME
            result = subprocess.run([sys.executable, str(installer), '--dest', str(target)],
                                    cwd=root.parent, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
            result = subprocess.run([sys.executable, str(target / 'scripts/doctor.py')],
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
