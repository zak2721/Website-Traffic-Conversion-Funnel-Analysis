#!/usr/bin/env bash
# One-command reproducible pipeline. Run from the repository root.
#   ./run_pipeline.sh            full run (PostgreSQL steps run if psql can connect)
#   SKIP_SQL=1 ./run_pipeline.sh Python-only
# PostgreSQL connection uses standard libpq env vars (PGHOST, PGUSER, PGDATABASE, ...).
set -euo pipefail
cd "$(dirname "$0")"
export PGDATABASE="${PGDATABASE:-webanalytics}"

echo "== 1/6 Generate synthetic raw data";      python python/generate_sample_data.py > /dev/null
echo "== 2/6 Profile raw data";                 python python/data_quality.py --stage raw > reports/metrics/data_quality_raw.md
echo "== 3/6 Clean data + build star schema";   python python/clean_data.py > /dev/null
python python/data_quality.py --stage processed > reports/metrics/data_quality_processed.md
echo "== 4/6 Analysis tables + figures";        python python/analysis.py | tail -1
python python/build_visual_assets.py

if [[ "${SKIP_SQL:-0}" != "1" ]] && command -v psql >/dev/null && psql -Atc "select 1" >/dev/null 2>&1; then
  echo "== 5/6 PostgreSQL: create, load, run analyses"
  psql -q -v ON_ERROR_STOP=1 -f sql/01_create_tables.sql 2>/dev/null
  psql -q -v ON_ERROR_STOP=1 -f sql/01b_load_data.sql > /dev/null
  for f in sql/0[2-7]_*.sql; do psql -q -v ON_ERROR_STOP=1 -f "$f" > "reports/metrics/sql_output_$(basename "$f" .sql).txt"; done
else
  echo "== 5/6 PostgreSQL step skipped (psql unavailable, cannot connect, or SKIP_SQL=1)"
fi

echo "== 6/6 Notebooks, tests, reconciliation"
python python/build_notebooks.py > /dev/null
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb --log-level=ERROR
python -m pytest -q
python python/reconcile.py
echo "Done."
