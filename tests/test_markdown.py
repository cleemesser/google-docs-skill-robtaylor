import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gdocs_skill.markdown import parse, Parsed, Format, TableSpec  # noqa: E402


def test_empty_input_returns_empty_parsed():
    result = parse("")
    assert result.text == ""
    assert result.formats == []
    assert result.tables == []
