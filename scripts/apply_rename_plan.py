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
    if name.split('.')[0].upper() in WINDOWS_RESERVED:
        raise PlanError(f"文件名是 Windows 保留名称：{name}")
    if len(name.encode('utf-8')) > 255:
        raise PlanError(f"文件名过长（UTF-8 超过 255 字节）：{name}")


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
        if source.is_symlink():
            raise PlanError(f"暂不处理符号链接：{source}")
        source = source.resolve()
        if not source.is_file():
            raise PlanError(f"第 {index} 项源文件不存在：{source}")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise PlanError(f"第 {index} 项不是支持的图片格式：{source.name}")

        target_name = item["target"]
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

    validate_pairs(pairs)
    unchanged = sum(source == target for source, target in pairs)
    if unchanged:
        warnings.append(f"跳过 {unchanged} 个名称未变化的文件。")
    return [(source, target) for source, target in pairs if source != target], warnings


def validate_pairs(pairs: list[tuple[Path, Path]]) -> None:
    source_keys = [os.path.normcase(str(source)) for source, _ in pairs]
    target_keys = [os.path.normcase(str(target)) for _, target in pairs]
    if len(source_keys) != len(set(source_keys)):
        raise PlanError("同一个源文件在计划中出现多次。")
    if len(target_keys) != len(set(target_keys)):
        raise PlanError("计划中存在重复的目标文件名。")

    source_key_set = set(source_keys)
    source_aliases: dict[str, list[Path]] = {}
    for source, _ in pairs:
        source_aliases.setdefault(str(source).casefold(), []).append(source)
    for source, target in pairs:
        target_key = os.path.normcase(str(target))
        # samefile also catches case aliases on case-insensitive macOS volumes.
        occupied_by_source = target.exists() and any(
            target.samefile(s) for s in source_aliases.get(str(target).casefold(), [])
        )
        if os.path.lexists(target) and target_key not in source_key_set and not occupied_by_source:
            raise PlanError(f"目标文件已存在，拒绝覆盖：{target}")
    # Case folding is deliberately conservative for portable plans.
    folded = [str(target).casefold() for _, target in pairs]
    if len(folded) != len(set(folded)):
        raise PlanError("目标名称仅大小写不同，无法保证跨平台安全。")


def unique_temp_path(source: Path) -> Path:
    while True:
        candidate = source.with_name(f".__dao_tmp_{uuid.uuid4().hex}{source.suffix}")
        if not candidate.exists():
            return candidate


def move_no_overwrite(source: Path, target: Path) -> None:
    if os.name == 'nt':
        source.rename(target)  # Windows rename refuses an existing destination.
    else:
        # A hard link reserves the destination atomically without replacing it.
        os.link(source, target)
        try:
            source.unlink()
        except OSError:
            target.unlink()
            raise


def apply_pairs(pairs: list[tuple[Path, Path]]) -> None:
    validate_pairs(pairs)
    staged: list[tuple[Path, Path, Path]] = []
    completed: list[tuple[Path, Path, Path]] = []
    try:
        for source, target in pairs:
            temp = unique_temp_path(source)
            move_no_overwrite(source, temp)
            staged.append((source, temp, target))
        for source, temp, target in staged:
            move_no_overwrite(temp, target)
            completed.append((source, temp, target))
    except Exception:
        # Free ALL completed targets first: direct target->source breaks cycles.
        for _source, temp, target in reversed(completed):
            if target.exists():
                move_no_overwrite(target, temp)
        for source, temp, _target in reversed(staged):
            if temp.exists() and not source.exists():
                move_no_overwrite(temp, source)
        raise


def default_manifest_path(plan_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = plan_path.with_name(f"rename-manifest-{stamp}.json")
    if candidate.exists():
        candidate = plan_path.with_name(f"rename-manifest-{stamp}-{uuid.uuid4().hex[:8]}.json")
    return candidate


def write_manifest(path: Path, pairs: list[tuple[Path, Path]], status: str = "applied") -> None:
    payload = {
        "version": 1,
        "status": status,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "renames": [
            {"source": str(source), "target": str(target)} for source, target in pairs
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an earlier recovery record.
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def set_manifest_status(path: Path, status: str) -> None:
    payload = load_json(path)
    payload['status'] = status
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_rollback_pairs(manifest_path: Path) -> list[tuple[Path, Path]]:
    payload = load_json(manifest_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("renames"), list) or not payload['renames']:
        raise PlanError("回退清单缺少 renames 数组。")
    if payload.get('status', 'applied') != 'applied':
        raise PlanError("清单未标记为 applied，可能执行中断；请先检查文件位置，再人工恢复。")
    pairs: list[tuple[Path, Path]] = []
    for index, raw in enumerate(payload["renames"], start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("source"), str) or not isinstance(raw.get("target"), str):
            raise PlanError(f"回退清单第 {index} 项格式错误。")
        if not Path(raw['source']).is_absolute() or not Path(raw['target']).is_absolute():
            raise PlanError("回退清单必须使用绝对路径。")
        original = Path(raw["source"])
        renamed = Path(raw["target"])
        if renamed.is_symlink():
            raise PlanError(f"暂不处理符号链接：{renamed}")
        if not renamed.is_file():
            raise PlanError(f"回退源文件不存在：{renamed}")
        pairs.append((renamed, original))
    validate_pairs(pairs)
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
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parse_args()
    try:
        if args.rollback:
            manifest_path = args.rollback.resolve()
            pairs = load_rollback_pairs(manifest_path)
            print_pairs(pairs, "回退预览：" if not args.apply else "正在回退：")
            if args.apply:
                set_manifest_status(manifest_path, 'rollback_prepared')
                apply_pairs(pairs)
                set_manifest_status(manifest_path, 'rolled_back')
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

        if not pairs:
            print("没有需要改名的文件。")
            return 0
        manifest_path = (args.manifest or default_manifest_path(plan_path)).resolve()
        if any(same_path(manifest_path, p) for pair in pairs for p in pair) or same_path(manifest_path, plan_path):
            raise PlanError("回退清单不能占用图片或计划文件的路径。")
        write_manifest(manifest_path, pairs, status='prepared')
        print(f"恢复清单：{manifest_path}")
        apply_pairs(pairs)
        set_manifest_status(manifest_path, 'applied')
        print(f"改名完成。回退清单：{manifest_path}")
        return 0
    except (OSError, PlanError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
