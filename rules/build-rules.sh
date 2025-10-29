#!/usr/bin/env bash

# === HOW TO SETUP ===
# Run:
: ' 
git submodule add git@github.com:maximilian-armuss-dev/prompts.git rules/external
git submodule update --init --recursive
chmod +x rules/build-rules.sh
sh rules/build-rules.sh. 
'
# === SCRIPT ===
set -e pipefail

SUBMODULE_PATH="rules/external"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OUT="${ROOT}/AGENTS.md"
SEPARATOR="---"
INCLUDE_FILES=(
  "rules/project-structure.md"
  "rules/external/iterative.md"
  "rules/external/python.md"
)

echo "[BUILD] Updating submodule (if needed)…"
git submodule update --init --remote "${SUBMODULE_PATH}"

echo "[BUILD] Building AGENTS.md…"
{
  for f in "${INCLUDE_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
      echo "[BUILD] WARNING: Missing file: $f" >&2
      continue
    fi
    cat "$f"
    echo
    echo
    echo "${SEPARATOR}"
    echo
  done
  echo "# Closing the loop"
  echo 'Everytime the `project-structure.md` has been updated, call `sh rules/build-rules.sh` to rebuild the `AGENTs.md` file.'
} > "$OUT"

echo "[BUILD] Done!"