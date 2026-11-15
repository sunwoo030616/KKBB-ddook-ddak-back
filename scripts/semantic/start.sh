#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."
exec .semantic-runtime/venv/bin/python scripts/semantic/server.py \
  --model-dir .semantic-runtime/model \
  --catalog src/main/resources/kb_starbanking_menu_structure_cleaned.json \
  --port "${MENU_SEMANTIC_PORT:-18083}"
