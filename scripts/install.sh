#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/install.sh [simple|full]

Modes:
  simple  Install only the required base dependencies for wao.
  full    Install all optional dependencies, Chromium for body fetching,
          and download the semantic model assets.

Environment:
  PYTHON_BIN  Python executable to use. Default: python3
EOF
}

log() {
  printf '==> %s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

MODE="${1:-simple}"

case "$MODE" in
  simple|full)
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    die "unknown install mode: $MODE"
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "missing Python executable: $PYTHON_BIN"
test -f "$ROOT_DIR/pyproject.toml" || die "pyproject.toml not found under $ROOT_DIR"

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("wao requires Python 3.10+")
PY

install_simple() {
  log "Installing wao base dependencies"
  (
    cd "$ROOT_DIR"
    "$PYTHON_BIN" -m pip install .
  )
}

install_full() {
  log "Installing wao full dependency set"
  (
    cd "$ROOT_DIR"
    "$PYTHON_BIN" -m pip install '.[all]'
  )

  log "Installing Playwright Chromium"
  "$PYTHON_BIN" -m playwright install chromium

  log "Downloading wao semantic model assets"
  (
    cd "$ROOT_DIR"
    "$PYTHON_BIN" -m wao model download
  )
}

smoke_check() {
  log "Running smoke check"
  (
    cd "$ROOT_DIR"
    "$PYTHON_BIN" -m wao topics >/dev/null
  )
}

log "Repository root: $ROOT_DIR"
log "Python: $PYTHON_BIN"
log "Mode: $MODE"

if [ "$MODE" = "simple" ]; then
  install_simple
else
  install_full
fi

smoke_check

log "Install finished"
if [ "$MODE" = "simple" ]; then
  printf 'Next steps: run `%s -m wao trend` or `wao trend` in your active environment.\n' "$PYTHON_BIN"
else
  printf 'Next steps: try `%s -m wao summary --fetch-body` or `wao summary --fetch-body`.\n' "$PYTHON_BIN"
fi
