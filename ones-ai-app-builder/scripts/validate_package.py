#!/usr/bin/env python3
import argparse
import sys
import zipfile
from pathlib import Path


def root_entries(archive: zipfile.ZipFile) -> set[str]:
    items = set()
    for name in archive.namelist():
        cleaned = name.strip("/")
        if not cleaned:
            continue
        items.add(cleaned.split("/", 1)[0])
    return items


def validate_static(entries: set[str]) -> list[str]:
    errors = []
    if "index.html" not in entries:
        errors.append("静态包根目录缺少 index.html")
    return errors


def validate_runtime(entries: set[str], archive: zipfile.ZipFile) -> list[str]:
    errors = []
    for required in ("manifest.yaml", "start.sh"):
        if required not in entries:
            errors.append(f"运行包根目录缺少 {required}")
    if "manifest.yaml" in entries:
        content = archive.read("manifest.yaml").decode("utf-8", errors="ignore")
        for key in ("runtime:", "port:", "healthCheckPath:"):
            if key not in content:
                errors.append(f"manifest.yaml 缺少关键字段 {key[:-1]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 ONES AI应用发布平台 ZIP 包结构")
    parser.add_argument("--type", choices=["static", "runtime"], required=True)
    parser.add_argument("--zip", dest="zip_path", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        print(f"ZIP 不存在: {zip_path}", file=sys.stderr)
        return 1

    try:
        with zipfile.ZipFile(zip_path) as archive:
            entries = root_entries(archive)
            if args.type == "static":
                errors = validate_static(entries)
            else:
                errors = validate_runtime(entries, archive)
    except zipfile.BadZipFile:
        print("不是合法的 ZIP 文件", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"校验通过: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
