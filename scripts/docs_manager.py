#!/usr/bin/env python3
"""docs_manager — entry script for Google Docs operations.

Re-execs into the skill's own .venv/bin/python so dependencies resolve
regardless of the caller's CWD. Requires `uv sync` to have been run in
the skill directory.
"""
import os
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _SKILL_ROOT / ".venv" / "bin" / "python"


def _bootstrap() -> None:
    try:
        running = Path(sys.executable).resolve()
    except OSError:
        running = None
    if _VENV_PYTHON.exists():
        if running != _VENV_PYTHON.resolve():
            os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), __file__] + sys.argv[1:])
        return
    sys.stderr.write(
        f"error: skill venv not found at {_VENV_PYTHON}\n"
        f"       run `uv sync` in {_SKILL_ROOT} to install dependencies.\n"
    )
    sys.exit(2)


_bootstrap()

sys.path.insert(0, str(_SKILL_ROOT / "scripts"))
from gdocs_skill.cli import main_docs  # noqa: E402

if __name__ == "__main__":
    sys.exit(main_docs(sys.argv[1:]))
