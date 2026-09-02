#!/usr/bin/env python3
"""Validate, apply, or roll back a collision-safe image rename plan."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
INVALID_WINDOWS_CHARS = set('<>:"/\\|?*')
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class PlanError(ValueError):
    """Raised when a rename plan is unsafe or malformed."""


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise PlanError(f"找不到文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"JSON 格式错误：{exc}") from exc


def extract_items(payload: object) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        payload = payload.get("renames")
    if not isinstance(payload, list) or not payload:
        raise PlanError("改名计划必须是非空数组，或包含非空 renames 数组。")
    items: list[dict[str, str]] = []
    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise PlanError(f"第 {index} 项必须是对象。")
        source = raw.get("source")
        target = raw.get("target")
        if not isinstance(source, str) or not source.strip():
            raise PlanError(f"第 {index} 项缺少 source。")
        if not isinstance(target, str) or not target.strip():
            raise PlanError(f"第 {index} 项缺少 target。")
        items.append({"source": source, "target": target})
    return items


def validate_filename(name: str) -> None:
    if name in {".", ".."} or Path(name).name != name:
        raise PlanError(f"target 只能是同目录中的文件名：{name}")
    if any(char in INVALID_WINDOWS_CHARS or ord(char) < 32 for char in name):
        raise PlanError(f"文件名含 Windows 不允许的字符：{name}")
    if name.endswith((" ", ".")):
        raise PlanError(f"文件名不能以空格或句点结尾：{name}")
    if Path(name).stem.upper() in WINDOWS_RESERVED:
        raise PlanError(f"文件名是 Windows 保留名称：{name}")


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def prepare_plan(items: Iterable[dict[str, str]], base_dir: Path) -> tuple[list[tuple[Path, Path]], list[str]]:
    pairs: list[tuple[Path, Path]] = []
    warnings: list[str] = []

    for index, item in enumerate(items, start=1):
        source = Path(item["source"]).expanduser()
        if not source.is_absolute():
            source = base_dir / source
        source = source.resolve()
        if not source.is_file():
            raise PlanError(f"第 {index} 项源文件不存在：{source}")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise PlanError(f"第 {index} 项不是支持的图片格式：{source.name}")

        target_name = item["target"].strip()
        validate_filename(target_name)
        target_path = Path(target_name)
        if not target_path.suffix:
            target_name += source.suffix
        elif target_path.suffix != source.suffix:
            raise PlanError(
                f"第 {index} 项必须原样保留扩展名 {source.suffix}：{target_name}"
            )
        validate_filename(target_name)
        target = source.with_name(target_name)

        stem = target.stem
        keyword_count = len([part for part in stem.split("＊") if part])
        if "＊" not in stem:
            warnings.append(f"第 {index} 项未使用全角分隔符＊：{target.name}")
        if not 5 <= keyword_count <= 8:
            warnings.append(f"第 {index} 项关键词数量为 {keyword_count}，建议 5–8 个：{target.name}")
        if not 20 <= len(stem) <= 45:
            warnings.append(f"第 {index} 项名称长度为 {len(stem)}，建议 20–45 个字符：{target.name}")
        pairs.append((source, target))

    source_keys = [os.path.normcase(str(source)) for source, _ in pairs]
    target_keys = [os.path.normcase(str(target)) for _, target in pairs]
    if len(source_keys) != len(set(source_keys)):
        raise PlanError("同一个源文件在计划中出现多次。")
    if len(target_keys) != len(set(target_keys)):
        raise PlanError("计划中存在重复的目标文件名。")

    source_key_set = set(source_keys)
    for source, target in pairs:
        if same_path(source, target):
            raise PlanError(f"源文件名与目标文件名相同：{source.name}")
        target_key = os.path.normcase(str(target))
        if target.exists() and target_key not in source_key_set:
            raise PlanError(f"目标文件已存在，拒绝覆盖：{target}")

    return pairs, warnings


def unique_temp_path(source: Path) -> Path:
    while True:
        candidate = source.with_name(f".__dao_tmp_{uuid.uuid4().hex}{source.suffix}")
        if not candidate.exists():
            return candidate


def apply_pairs(pairs: list[tuple[Path, Path]]) -> None:
    staged: list[tuple[Path, Path, Path]] = []
    completed: list[tuple[Path, Path, Path]] = []
    try:
        for source, target in pairs:
            temp = unique_temp_path(source)
            source.rename(temp)
            staged.append((source, temp, target))
        for source, temp, target in staged:
            temp.rename(target)
            completed.append((source, temp, target))
    except Exception:
        for source, _temp, target in reversed(completed):
            if target.exists() and not source.exists():
                target.rename(source)
        for source, temp, _target in reversed(staged):
            if temp.exists() and not source.exists():
                temp.rename(source)
        raise


def default_manifest_path(plan_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = plan_path.with_name(f"rename-manifest-{stamp}.json")
    if candidate.exists():
        candidate = plan_path.with_name(f"rename-manifest-{stamp}-{uuid.uuid4().hex[:8]}.json")
    return candidate


def write_manifest(path: Path, pairs: list[tuple[Path, Path]]) -> None:
    payload = {
        "version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "renames": [
            {"source": str(source), "target": str(target)} for source, target in pairs
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_rollback_pairs(manifest_path: Path) -> list[tuple[Path, Path]]:
    payload = load_json(manifest_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("renames"), list):
        raise PlanError("回退清单缺少 renames 数组。")
    pairs: list[tuple[Path, Path]] = []
    for index, raw in enumerate(payload["renames"], start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("source"), str) or not isinstance(raw.get("target"), str):
            raise PlanError(f"回退清单第 {index} 项格式错误。")
        original = Path(raw["source"]).resolve()
        renamed = Path(raw["target"]).resolve()
        if not renamed.is_file():
            raise PlanError(f"回退源文件不存在：{renamed}")
        if original.exists() and not same_path(original, renamed):
            raise PlanError(f"原文件名已被占用，拒绝覆盖：{original}")
        pairs.append((renamed, original))
    return pairs


def print_pairs(pairs: list[tuple[Path, Path]], heading: str) -> None:
    print(heading)
    for index, (source, target) in enumerate(pairs, start=1):
        print(f"{index:02d}｜{source.name} → {target.name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="安全预检、执行或回退图片批量改名计划。")
    parser.add_argument("plan", nargs="?", type=Path, help="UTF-8 JSON 改名计划")
    parser.add_argument("--apply", action="store_true", help="实际执行；省略时只预览")
    parser.add_argument("--manifest", type=Path, help="指定执行后写入的回退清单路径")
    parser.add_argument("--rollback", type=Path, help="使用已有清单回退改名")
    args = parser.parse_args()
    if bool(args.plan) == bool(args.rollback):
        parser.error("必须且只能提供 plan 或 --rollback。")
    if args.manifest and args.rollback:
        parser.error("回退模式不能同时使用 --manifest。")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.rollback:
            manifest_path = args.rollback.resolve()
            pairs = load_rollback_pairs(manifest_path)
            print_pairs(pairs, "回退预览：" if not args.apply else "正在回退：")
            if args.apply:
                apply_pairs(pairs)
                print("回退完成。")
            else:
                print("仅预览；添加 --apply 后执行。")
            return 0

        plan_path = args.plan.resolve()
        items = extract_items(load_json(plan_path))
        pairs, warnings = prepare_plan(items, plan_path.parent)
        print_pairs(pairs, "改名预览：" if not args.apply else "正在改名：")
        for warning in warnings:
            print(f"警告：{warning}", file=sys.stderr)
        if not args.apply:
            print("预检通过；添加 --apply 后执行。")
            return 0

        apply_pairs(pairs)
        manifest_path = (args.manifest or default_manifest_path(plan_path)).resolve()
        write_manifest(manifest_path, pairs)
        print(f"改名完成。回退清单：{manifest_path}")
        return 0
    except (OSError, PlanError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
