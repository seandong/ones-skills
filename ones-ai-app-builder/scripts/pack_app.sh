#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "用法: $0 <source_dir> <output_zip>" >&2
  exit 1
fi

SOURCE_DIR="$1"
OUTPUT_ZIP="$2"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "源目录不存在: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_ZIP")"
rm -f "$OUTPUT_ZIP"

(
  cd "$SOURCE_DIR"
  zip -r -X "$OUTPUT_ZIP" .
)

echo "$OUTPUT_ZIP"
