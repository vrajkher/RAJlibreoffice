#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p workspace
# Match the user's UID so bind-mounted outputs are owned by that user.
exec docker run --rm -i --init --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e RAJ_WORKSPACE=/workspace \
  -e RAJ_ALLOW_ADVANCED="${RAJ_ALLOW_ADVANCED:-0}" \
  -e RAJ_ALLOW_SCRIPTS="${RAJ_ALLOW_SCRIPTS:-0}" \
  -e RAJ_ALLOW_PYTHON="${RAJ_ALLOW_PYTHON:-0}" \
  -v "$PWD/workspace:/workspace" raj-libreoffice:openai serve --openai
