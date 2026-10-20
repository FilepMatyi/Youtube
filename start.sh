#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$project_root/.venv/bin/python" ]]; then
  echo "The local Python environment is missing. Follow the install steps in README.md first." >&2
  exit 1
fi
"$project_root/.venv/bin/python" -m streamlit run "$project_root/app.py" --server.address localhost
