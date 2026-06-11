#!/usr/bin/env bash

CONSOLE_MIN_PYTHON_MAJOR="${CONSOLE_MIN_PYTHON_MAJOR:-3}"
CONSOLE_MIN_PYTHON_MINOR="${CONSOLE_MIN_PYTHON_MINOR:-12}"

python_supports_console_requirements() {
  local python_bin="$1"
  CONSOLE_MIN_PYTHON_MAJOR="$CONSOLE_MIN_PYTHON_MAJOR" \
  CONSOLE_MIN_PYTHON_MINOR="$CONSOLE_MIN_PYTHON_MINOR" \
  "$python_bin" - <<'PY' >/dev/null 2>&1
import os
import sys

major = int(os.environ["CONSOLE_MIN_PYTHON_MAJOR"])
minor = int(os.environ["CONSOLE_MIN_PYTHON_MINOR"])
raise SystemExit(0 if sys.version_info >= (major, minor) else 1)
PY
}

select_console_python() {
  if [[ -n "${CONSOLE_PYTHON:-}" ]]; then
    if python_supports_console_requirements "$CONSOLE_PYTHON"; then
      return 0
    fi
    echo "CONSOLE_PYTHON must be Python ${CONSOLE_MIN_PYTHON_MAJOR}.${CONSOLE_MIN_PYTHON_MINOR}+ for mitmproxy>=12: $CONSOLE_PYTHON" >&2
    exit 1
  fi

  local candidate
  for candidate in python3.12 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && python_supports_console_requirements "$(command -v "$candidate")"; then
      CONSOLE_PYTHON="$(command -v "$candidate")"
      return 0
    fi
    if [[ -x "$candidate" ]] && python_supports_console_requirements "$candidate"; then
      CONSOLE_PYTHON="$candidate"
      return 0
    fi
  done

  echo "Python ${CONSOLE_MIN_PYTHON_MAJOR}.${CONSOLE_MIN_PYTHON_MINOR}+ is required for TraceDeck console dependencies." >&2
  echo "Install Python 3.12+ or set CONSOLE_PYTHON to a compatible interpreter." >&2
  exit 1
}

project_owned_console_venv() {
  local venv_dir="$1"
  case "$venv_dir" in
    "$ROOT_DIR"/.venv|"$ROOT_DIR"/.venv-*|"$ROOT_DIR"/.venv-console|"$ROOT_DIR"/.venv-console*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_console_venv() {
  if [[ -x "$VENV_DIR/bin/python" ]] && ! python_supports_console_requirements "$VENV_DIR/bin/python"; then
    if project_owned_console_venv "$VENV_DIR"; then
      echo "recreate incompatible console venv: $VENV_DIR" >&2
      rm -rf "$VENV_DIR"
    else
      echo "Console venv Python is below ${CONSOLE_MIN_PYTHON_MAJOR}.${CONSOLE_MIN_PYTHON_MINOR}: $VENV_DIR" >&2
      echo "Use a compatible CONSOLE_VENV_DIR or allow TraceDeck to create its project venv." >&2
      exit 1
    fi
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    select_console_python
    "$CONSOLE_PYTHON" -m venv "$VENV_DIR"
  fi
}
