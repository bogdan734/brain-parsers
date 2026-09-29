#!/usr/bin/env bash
# Runs the whole pipeline: PostgreSQL -> migrations -> 3 parsers -> CSV export -> DB dump.
# Usage: ./scripts/run_all.sh
# Env: SECURITY_CHECK_TIMEOUT (seconds) - how long browser parsers wait for a manual security check.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
export PYTHONUNBUFFERED=1

cd "$ROOT"

echo "==> Starting PostgreSQL"
docker compose up -d db || exit 1
until docker exec brain-parsers-db pg_isready -U brain -d brain >/dev/null 2>&1; do
    sleep 1
done

echo "==> Applying migrations"
(cd braincomua_project && "$PYTHON" manage.py migrate --noinput) || exit 1

failed=""
cd "$ROOT/modules"
for script in 1_parse_bs4.py 1_parse_selenium.py 1_parse_playwright.py; do
    echo
    echo "==> $script"
    "$PYTHON" "$script" || failed="$failed $script"
done

echo
echo "==> Exporting CSV"
"$PYTHON" 2_export_csv.py || exit 1

echo "==> Dumping database"
docker exec brain-parsers-db pg_dump -U brain --no-owner brain > "$ROOT/results/brain_dump.sql.tmp" || exit 1
mv "$ROOT/results/brain_dump.sql.tmp" "$ROOT/results/brain_dump.sql"

echo
if [ -n "$failed" ]; then
    echo "==> Finished with errors in:$failed"
    exit 1
fi
echo "==> All done: results/products.csv, results/brain_dump.sql"
