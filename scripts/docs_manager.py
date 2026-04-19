#!/usr/bin/env -S uv run
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdocs_skill.cli import main_docs

if __name__ == "__main__":
    sys.exit(main_docs(sys.argv[1:]))
