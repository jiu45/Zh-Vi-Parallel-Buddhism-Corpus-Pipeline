#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/../.." && pwd)"
python="${PYTHON:-${repo_dir}/.venv-q4/bin/python}"
if [[ -z "${PYTHON:-}" && ! -x "$python" ]]; then
  python=python3.11
fi
exec "$python" "${script_dir}/run_pipeline.py" "$@"
