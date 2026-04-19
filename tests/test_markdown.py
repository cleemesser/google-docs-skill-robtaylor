import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gdocs_skill.markdown import parse, Parsed, Format, TableSpec  # noqa: E402


def test_empty_input_returns_empty_parsed():
    result = parse("")
    assert result.text == ""
    assert result.formats == []
    assert result.tables == []


def test_plain_paragraph():
    result = parse("Hello world")
    assert result.text == "Hello world\n"
    assert result.formats == []
    assert result.tables == []


def test_inline_bold_italic_code():
    result = parse("a **bold** c *it* e `cd` g")
    assert result.text == "a bold c it e cd g\n"
    assert Format("bold", 3, 7) in result.formats
    assert Format("italic", 10, 12) in result.formats
    assert Format("code", 15, 17) in result.formats
    assert len(result.formats) == 3
