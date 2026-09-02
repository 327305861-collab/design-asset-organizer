import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "apply_rename_plan.py"
SPEC = importlib.util.spec_from_file_location("apply_rename_plan", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RenamePlanTests(unittest.TestCase):
    def test_apply_and_rollback_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.jpg"
            second = root / "b.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            items = [
                {"source": str(first), "target": "金融＊KV＊科技＊蓝紫＊圆环＊中心透视.jpg"},
                {"source": str(second), "target": "人物＊人物介绍＊毛玻璃＊红白＊卡片＊左右构图.png"},
            ]
            pairs, _warnings = MODULE.prepare_plan(items, root)
            MODULE.apply_pairs(pairs)
            self.assertEqual(pairs[0][1].read_bytes(), b"first")
            self.assertEqual(pairs[1][1].read_bytes(), b"second")

            manifest = root / "manifest.json"
            MODULE.write_manifest(manifest, pairs)
            rollback_pairs = MODULE.load_rollback_pairs(manifest)
            MODULE.apply_pairs(rollback_pairs)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")

    def test_rejects_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "a.jpg"
            source.write_bytes(b"source")
            target = root / "金融＊KV＊科技＊蓝紫＊圆环.jpg"
            target.write_bytes(b"existing")
            with self.assertRaises(MODULE.PlanError):
                MODULE.prepare_plan(
                    [{"source": str(source), "target": target.name}], root
                )

    def test_rejects_extension_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "a.jpeg"
            source.write_bytes(b"source")
            with self.assertRaises(MODULE.PlanError):
                MODULE.prepare_plan(
                    [{"source": str(source), "target": "人物＊海报＊摄影＊蓝色＊近景.jpg"}],
                    root,
                )


if __name__ == "__main__":
    unittest.main()
