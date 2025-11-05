#!/bin/sh
set -euo pipefail

log() {
    printf '%s | %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

STATE_FILE_PATH="${STATE_FILE_PATH:-/code/processed_update_ids.json}"
HF_CACHE_ROOT="${HUGGINGFACE_HUB_CACHE:-${HOME:-/code}/.cache/huggingface}"

ensure_state_file() {
    STATE_DIR="$(dirname "${STATE_FILE_PATH}")"
    mkdir -p "${STATE_DIR}"
    if [ ! -f "${STATE_FILE_PATH}" ]; then
        log "Creating state file at ${STATE_FILE_PATH}."
        touch "${STATE_FILE_PATH}"
    fi
    chown root:root "${STATE_FILE_PATH}" || true
}

ensure_huggingface_cache() {
    CACHE_DIR="${HF_CACHE_ROOT}"
    mkdir -p "${CACHE_DIR}"
    chmod -R 775 "${CACHE_DIR}" || true
}

ensure_huggingface_cache
ensure_state_file

if [ "$#" -eq 0 ]; then
    set -- python /code/app/main.py
fi

log "Launching application: $*"
exec "$@"
