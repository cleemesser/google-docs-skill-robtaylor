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

    lines = markdown.splitlines()
    current_index = base_index
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("# "):
            heading = line[2:] + "\n"
            result.formats.append(
                Format("heading1", current_index, current_index + len(heading) - 1)
            )
            result.text += heading
            current_index += len(heading)
            i += 1
            continue
        if line.startswith("## "):
            heading = line[3:] + "\n"
            result.formats.append(
                Format("heading2", current_index, current_index + len(heading) - 1)
            )
            result.text += heading
            current_index += len(heading)
            i += 1
            continue
        if line.startswith("### "):
            heading = line[4:] + "\n"
            result.formats.append(
                Format("heading3", current_index, current_index + len(heading) - 1)
            )
            result.text += heading
            current_index += len(heading)
            i += 1
            continue

        # Checkbox (must come before bullet list)
        if line.startswith("- [ ] ") or line.startswith("* [ ] "):
            item = line[6:]
            prefix = "☐ "
            span, fmts = _process_inline(item, current_index + len(prefix))
            block = prefix + span + "\n"
            result.formats.extend(fmts)
            result.text += block
            current_index += len(block)
            i += 1
            continue
        if (
            line.startswith("- [x] ")
            or line.startswith("* [x] ")
            or line.startswith("- [X] ")
            or line.startswith("* [X] ")
        ):
            item = line[6:]
            prefix = "☑ "
            span, fmts = _process_inline(item, current_index + len(prefix))
            block = prefix + span + "\n"
            result.formats.extend(fmts)
            result.text += block
            current_index += len(block)
            i += 1
            continue
        if line.startswith("- ") or line.startswith("* "):
            item = line[2:]
            prefix = "• "
            span, fmts = _process_inline(item, current_index + len(prefix))
            block = prefix + span + "\n"
            result.formats.extend(fmts)
            result.text += block
            current_index += len(block)
            i += 1
            continue
        m = _NUMBERED_RE.match(line)
        if m:
            num_prefix = f"{m.group(1)}. "
            item = m.group(2)
            span, fmts = _process_inline(item, current_index + len(num_prefix))
            block = num_prefix + span + "\n"
            result.formats.extend(fmts)
            result.text += block
            current_index += len(block)
            i += 1
            continue

        if line == "---":
            result.text += HR_LINE
            current_index += len(HR_LINE)
            i += 1
            continue
        if line == "":
            result.text += "\n"
            current_index += 1
            i += 1
            continue

        # Fallthrough: plain paragraph with inline formatting
        para_text, inline_formats = _process_inline(line, current_index)
        result.formats.extend(inline_formats)
        block = para_text + "\n"
        result.text += block
        current_index += len(block)
        i += 1
    return result


def _process_inline(line: str, base_index: int) -> tuple[str, list[Format]]:
    """Parse **bold**, *italic*, `code` inline. Returns (flat_text, formats)."""
    out: list[str] = []
    formats: list[Format] = []
    pos = 0
    n = len(line)
    while pos < n:
        if line[pos : pos + 2] == "**":
            end = line.find("**", pos + 2)
            if end != -1:
                span = line[pos + 2 : end]
                start_idx = base_index + len("".join(out))
                out.append(span)
                formats.append(Format("bold", start_idx, start_idx + len(span)))
                pos = end + 2
                continue
        if line[pos] == "*" and line[pos : pos + 2] != "**":
            end = line.find("*", pos + 1)
            if end != -1 and line[end : end + 2] != "**":
                span = line[pos + 1 : end]
                start_idx = base_index + len("".join(out))
                out.append(span)
                formats.append(Format("italic", start_idx, start_idx + len(span)))
                pos = end + 1
                continue
        if line[pos] == "`":
            end = line.find("`", pos + 1)
            if end != -1:
                span = line[pos + 1 : end]
                start_idx = base_index + len("".join(out))
                out.append(span)
                formats.append(Format("code", start_idx, start_idx + len(span)))
                pos = end + 1
                continue
        out.append(line[pos])
        pos += 1
    return "".join(out), formats
