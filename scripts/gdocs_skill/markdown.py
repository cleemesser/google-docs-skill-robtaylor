"""Markdown -> Google Docs batchUpdate request builder.

Feature parity with the Ruby implementation. Supports:
- Headings # / ## / ### (HEADING_1/2/3)
- Bold **text**, italic *text*, code `text`
- Bullet (- *), numbered (N.), checkbox (- [ ], - [x]) lists -- rendered as literal prefixes
- Horizontal rule --- (em-dash line)
- Tables with separator row (| a | b |)

Not supported: nested lists, links, code fences, blockquotes, strikethrough.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Format:
    kind: str  # 'heading1' | 'heading2' | 'heading3' | 'bold' | 'italic' | 'code'
    start: int
    end: int


@dataclass
class TableSpec:
    rows: list[list[str]]
    insert_index: int
    num_rows: int
    num_cols: int


@dataclass
class Parsed:
    text: str = ""
    formats: list[Format] = field(default_factory=list)
    tables: list[TableSpec] = field(default_factory=list)


HR_LINE = "———————————————————————————\n"  # 27 em-dashes + newline
_NUMBERED_RE = re.compile(r"^(\d+)\. (.*)$")


def parse(markdown: str, base_index: int = 1) -> Parsed:
    result = Parsed()
    if not markdown:
        return result
    raise NotImplementedError
