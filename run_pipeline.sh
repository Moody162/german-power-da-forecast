#!/usr/bin/env bash
# Runs the full pipeline from scratch.
# Deletes all generated outputs before starting so every run is reproducible.
#
# Usage:
#   bash run_pipeline.sh            # clean + full run
#   bash run_pipeline.sh --skip-ingest  # reuse existing raw data (faster)

set -euo pipefail

SKIP_INGEST=false
for arg in "$@"; do
    [[ "$arg" == "--skip-ingest" ]] && SKIP_INGEST=true
done

echo "=== Cleaning generated outputs ==="
rm -rf data/processed data/qa
rm -rf outputs/figures outputs/tables outputs/predictions outputs/reports outputs/logs outputs/models

if [[ "$SKIP_INGEST" == false ]]; then
    rm -rf data/raw
fi

echo ""
echo "=== Running pipeline ==="

if [[ "$SKIP_INGEST" == false ]]; then
    echo "[1/9] Ingesting data from ENTSO-E..."
    uv run scripts/01_ingest.py
else
    echo "[1/9] Skipping ingestion (--skip-ingest)"
fi

echo "[2/9] Merging series..."
uv run scripts/02_merge.py

echo "[3/9] Running QA checks..."
uv run scripts/03_qa.py

echo "[4/9] Cleaning and imputing..."
uv run scripts/04_clean.py

echo "[5/9] Engineering features..."
uv run scripts/05_features.py

echo "[6/9] Training model..."
uv run scripts/06_train.py

echo "[7/9] Running recursive forecast..."
uv run scripts/07_curve.py

echo "[8/9] Building curve view..."
uv run scripts/08_curve_view.py

echo "[9/9] Generating LLM commentary..."
uv run scripts/09_drivers_commentary.py

echo ""
echo "=== Pipeline complete ==="
