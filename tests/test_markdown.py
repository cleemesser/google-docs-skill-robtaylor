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


def test_heading1():
    result = parse("# Title")
    assert result.text == "Title\n"
    # Ruby: end = start + len("Title\n") - 1 = 1 + 6 - 1 = 6
    assert result.formats == [Format("heading1", 1, 6)]


def test_heading2():
    result = parse("## Sub")
    assert result.text == "Sub\n"
    assert result.formats == [Format("heading2", 1, 4)]


def test_heading3():
    result = parse("### Small")
    assert result.text == "Small\n"
    assert result.formats == [Format("heading3", 1, 6)]


def test_bullet_list():
    result = parse("- one\n- two\n- three")
    assert result.text == "• one\n• two\n• three\n"
    assert result.formats == []


def test_numbered_list():
    result = parse("1. alpha\n2. beta")
    assert result.text == "1. alpha\n2. beta\n"
    assert result.formats == []


def test_checkbox_unchecked_and_checked():
    result = parse("- [ ] todo\n- [x] done")
    assert result.text == "☐ todo\n☑ done\n"


def test_horizontal_rule():
    result = parse("---")
    assert result.text == "———————————————————————————\n"


def test_empty_line_between_paragraphs():
    result = parse("a\n\nb")
    assert result.text == "a\n\nb\n"
