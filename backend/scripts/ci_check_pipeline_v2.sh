#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[check] ruff app/ml/pipeline.py"
ruff check app/ml/pipeline.py

echo "[check] ruff app/ml/alignment_service.py app/ml/ocr_service.py"
ruff check app/ml/alignment_service.py app/ml/ocr_service.py

echo "[check] py_compile pipeline/alignment/ocr"
python -m py_compile app/ml/pipeline.py app/ml/alignment_service.py app/ml/ocr_service.py

echo "[ok] pipeline v2 static checks passed"
