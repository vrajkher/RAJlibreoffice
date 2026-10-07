#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mode="${1:-standard}"
if [[ "$mode" != standard && "$mode" != openai ]]; then
  echo 'Usage: bash scripts/setup.sh [standard|openai]' >&2
  exit 2
fi
python3 -m venv ".venv-$mode"
if [[ "$mode" == openai ]]; then
  ".venv-$mode/bin/python" -m pip install -e '.[openai]'
else
  ".venv-$mode/bin/python" -m pip install -e . 'mcp>=1.30,<2'
fi
mkdir -p workspace
if ! ".venv-$mode/bin/raj-libreoffice" doctor; then
  echo 'Install LibreOffice/PyUNO using docs/INSTALL.md, or use docs/DOCKER.md.' >&2
  exit 1
fi
echo "Ready. Start with .venv-$mode/bin/raj-libreoffice serve"
