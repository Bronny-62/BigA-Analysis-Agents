#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

"$PYTHON_BIN" -m cli.install_runtime_deps --quiet

exec "$PYTHON_BIN" -m cli.main analyze "$@"
