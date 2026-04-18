# Python Port Implementation Plan

**Goal:** Replace the Ruby implementation of this Google Docs/Drive skill with a Python package, preserving the exact CLI contract documented in `SKILL.md`. Add multi-account support. Bump to 2.0.0.

**Architecture:** Small Python package at `scripts/gdocs_skill/` (auth, markdown, docs, drive, cli) with two thin entry scripts at `scripts/docs_manager.py` and `scripts/drive_manager.py`. Managed by `uv` with a `pyproject.toml` + `uv.lock`. Pytest covers the markdown parser only; client code coverage comes from the E2E skill-ci workflow.

**Tech Stack:** Python 3.11+, `uv`, `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `pytest`.

**Reference spec:** `docs/superpowers/specs/2026-04-18-python-port-design.md`

**Branch:** Work on `python`. Do NOT merge to `main` until the full plan is complete and smoke-tested end-to-end.

---

## File Structure (what gets created or modified)

**Created:**
- `pyproject.toml` — package metadata, deps, pytest config
- `uv.lock` — committed lockfile
- `scripts/gdocs_skill/__init__.py` — empty package marker
- `scripts/gdocs_skill/auth.py` — OAuth flow, token storage (multi-account)
- `scripts/gdocs_skill/markdown.py` — markdown → {text, formats, tables}, plus request builders
- `scripts/gdocs_skill/docs.py` — `DocsClient`
- `scripts/gdocs_skill/drive.py` — `DriveClient`
- `scripts/gdocs_skill/cli.py` — shared CLI helpers + `main_docs` / `main_drive` dispatchers
- `scripts/docs_manager.py` — thin executable entry
- `scripts/drive_manager.py` — thin executable entry
- `tests/test_markdown.py` — parser tests

**Modified:**
- `SKILL.md` — version 2.0.0, all `.rb` → `.py` in examples, add `uv sync` setup, add multi-account section, new version history entry
- `README.md` — update Quick Examples and setup
- `CLAUDE.md` — update dependency/architecture sections
- `references/docs_operations.md`, `references/formatting_guide.md`, `references/integration-patterns.md`, `references/troubleshooting.md`, `references/cli-patterns.md` — `.rb` → `.py`, gem → python
- `examples/sample_operations.md` — `.rb` → `.py`

**Deleted:**
- `scripts/docs_manager.rb`
- `scripts/drive_manager.rb`

---

## Phase 1: Foundation

### Task 1: Create `pyproject.toml` and lock dependencies

**Files:**
- Create: `pyproject.toml`
- Create (via tool): `uv.lock`

- [ ] **Step 1: Verify `uv` is on PATH**

Run: `uv --version`
Expected: prints a version string. If not, the implementer must install `uv` before proceeding.

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "gdocs-skill"
version = "2.0.0"
description = "Claude Code skill for Google Docs and Drive operations"
requires-python = ">=3.11"
dependencies = [
  "google-api-python-client>=2.120",
  "google-auth>=2.28",
  "google-auth-oauthlib>=1.2",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Generate lockfile and venv**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`. No errors.

- [ ] **Step 4: Commit foundation**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add pyproject.toml + uv.lock for Python port"
```

### Task 2: Scaffold the `gdocs_skill` package

**Files:**
- Create: `scripts/gdocs_skill/__init__.py`

- [ ] **Step 1: Create empty package marker**

```python
# scripts/gdocs_skill/__init__.py
"""Python implementation of the google-docs Claude Code skill."""
```

- [ ] **Step 2: Verify the package can be imported**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); import gdocs_skill; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/__init__.py
git commit -m "feat: scaffold gdocs_skill package"
```

---

## Phase 2: Auth module (multi-account)

### Task 3: Implement `auth.py` core

**Files:**
- Create: `scripts/gdocs_skill/auth.py`

- [ ] **Step 1: Write the module**

```python
# scripts/gdocs_skill/auth.py
"""OAuth flow and credential storage for the gdocs skill.

Supports multiple accounts via a per-account token file:
~/.claude/.google/token_python_<account>.json
"""
from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/gmail.modify",
]

GOOGLE_DIR = Path.home() / ".claude" / ".google"
CREDENTIALS_PATH = GOOGLE_DIR / "client_secret.json"
OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_PREFIX = "token_python_"


class AuthRequiredError(Exception):
    """Raised when credentials are missing or can't be refreshed."""
    def __init__(self, message: str, auth_url: str | None = None):
        super().__init__(message)
        self.auth_url = auth_url


def token_path(account: str) -> Path:
    return GOOGLE_DIR / f"{TOKEN_PREFIX}{account}.json"


def _load_flow() -> InstalledAppFlow:
    if not CREDENTIALS_PATH.exists():
        raise AuthRequiredError(
            f"client_secret.json not found at {CREDENTIALS_PATH}"
        )
    return InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH), scopes=SCOPES, redirect_uri=OOB_REDIRECT
    )


def get_credentials(account: str = "default") -> Credentials:
    path = token_path(account)
    creds: Credentials | None = None
    if path.exists():
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json())
        return creds

    flow = _load_flow()
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    raise AuthRequiredError(
        "Authorization required. Visit the URL and complete the flow.",
        auth_url=auth_url,
    )


def complete_auth(code: str, account: str = "default") -> None:
    flow = _load_flow()
    flow.fetch_token(code=code)
    GOOGLE_DIR.mkdir(parents=True, exist_ok=True)
    token_path(account).write_text(flow.credentials.to_json())


def build_docs_service(account: str = "default") -> Resource:
    return build("docs", "v1", credentials=get_credentials(account), cache_discovery=False)


def build_drive_service(account: str = "default") -> Resource:
    return build("drive", "v3", credentials=get_credentials(account), cache_discovery=False)


def list_accounts() -> list[str]:
    if not GOOGLE_DIR.exists():
        return []
    suffix = ".json"
    out = []
    for p in sorted(GOOGLE_DIR.iterdir()):
        name = p.name
        if name.startswith(TOKEN_PREFIX) and name.endswith(suffix):
            out.append(name[len(TOKEN_PREFIX) : -len(suffix)])
    return out
```

- [ ] **Step 2: Sanity-check imports**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill import auth; print(auth.SCOPES[0])"`
Expected: prints the Docs scope URL.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/auth.py
git commit -m "feat: add OAuth auth module with multi-account support"
```

---

## Phase 3: Markdown parser (TDD)

**Parser design notes** (derived from reading Ruby `parse_markdown`):

- Parser returns `Parsed(text: str, formats: list[Format], tables: list[TableSpec])`.
- `text` is plain text to insert as one block.
- `formats` is a list of formatting spans with inclusive-start / exclusive-end-ish indices (Ruby emits `end = start + len` for inline text styles and `end = start + len - 1` for paragraph styles; we match Ruby exactly).
- `tables` is a list of table specs to insert *after* text + formatting, each with its `insert_index`.
- Bullet/number/checkbox items are rendered as text prefixes (`• `, `1. `, `☐ `, `☑ `) — NO `createParagraphBullets` API call, matching Ruby.
- Horizontal rule `---` renders as an em-dash line (`———...`), matching Ruby's `"———————————————————————————\n"` (27 em-dashes).
- Code runs get `font_family: Courier New` + `background_color: RGB(0.95, 0.95, 0.95)`.

### Task 4: Test scaffolding and trivial parse

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_markdown.py`
- Create: `scripts/gdocs_skill/markdown.py`

- [ ] **Step 1: Create the test file with the first failing test**

```python
# tests/__init__.py
```

```python
# tests/test_markdown.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gdocs_skill.markdown import parse, Parsed, Format, TableSpec  # noqa: E402


def test_empty_input_returns_empty_parsed():
    result = parse("")
    assert result.text == ""
    assert result.formats == []
    assert result.tables == []
```

- [ ] **Step 2: Run it, see it fail**

Run: `uv run pytest tests/test_markdown.py::test_empty_input_returns_empty_parsed -v`
Expected: FAIL with ImportError (markdown.py doesn't exist).

- [ ] **Step 3: Create a minimal markdown.py that passes the first test**

```python
# scripts/gdocs_skill/markdown.py
"""Markdown → Google Docs batchUpdate request builder.

Feature parity with the Ruby implementation. Supports:
- Headings # / ## / ### (HEADING_1/2/3)
- Bold **text**, italic *text*, code `text`
- Bullet (- *), numbered (N.), checkbox (- [ ], - [x]) lists — rendered as literal prefixes
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
    # Remaining cases implemented in later tasks.
    raise NotImplementedError
```

- [ ] **Step 4: Run the test, see it pass**

Run: `uv run pytest tests/test_markdown.py::test_empty_input_returns_empty_parsed -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_markdown.py scripts/gdocs_skill/markdown.py
git commit -m "test: markdown parser scaffold + empty-input case"
```

### Task 5: Plain paragraph parsing

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing test**

```python
# tests/test_markdown.py — append
def test_plain_paragraph():
    result = parse("Hello world")
    assert result.text == "Hello world\n"
    assert result.formats == []
    assert result.tables == []
```

- [ ] **Step 2: Run it, see it fail**

Run: `uv run pytest tests/test_markdown.py::test_plain_paragraph -v`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement block-by-block loop and paragraph handling**

Replace the body of `parse` with:

```python
def parse(markdown: str, base_index: int = 1) -> Parsed:
    result = Parsed()
    if not markdown:
        return result

    lines = markdown.splitlines()
    current_index = base_index
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # ... handlers added in later tasks
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
    out = []
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
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gdocs_skill/markdown.py tests/test_markdown.py
git commit -m "feat: markdown — plain paragraphs + inline formatting"
```

### Task 6: Inline formatting spans

**Files:**
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing test**

```python
# tests/test_markdown.py — append
def test_inline_bold_italic_code():
    result = parse("a **bold** c *it* e `cd` g")
    assert result.text == "a bold c it e cd g\n"
    # "a " len 2 → bold at 1+2=3 … 3+4=7
    assert Format("bold", 3, 7) in result.formats
    # "a bold c " len 9 → italic at 1+9=10 … 10+2=12
    assert Format("italic", 10, 12) in result.formats
    # "a bold c it e " len 14 → code at 1+14=15 … 15+2=17
    assert Format("code", 15, 17) in result.formats
    assert len(result.formats) == 3
```

- [ ] **Step 2: Run, expect PASS** (already implemented via `_process_inline`)

Run: `uv run pytest tests/test_markdown.py::test_inline_bold_italic_code -v`
Expected: PASS. If FAIL, inspect `_process_inline` for off-by-ones.

- [ ] **Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test: inline formatting spans"
```

### Task 7: Headings H1/H2/H3

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing tests**

```python
# tests/test_markdown.py — append
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
```

- [ ] **Step 2: Run, see FAIL** (parser treats `#` as a literal paragraph currently)

- [ ] **Step 3: Add heading handlers**

Inside the `while i < len(lines):` loop, before the paragraph fallthrough, add:

```python
        if line.startswith("# "):
            heading = line[2:] + "\n"
            result.formats.append(Format("heading1", current_index, current_index + len(heading) - 1))
            result.text += heading
            current_index += len(heading)
            i += 1
            continue
        if line.startswith("## "):
            heading = line[3:] + "\n"
            result.formats.append(Format("heading2", current_index, current_index + len(heading) - 1))
            result.text += heading
            current_index += len(heading)
            i += 1
            continue
        if line.startswith("### "):
            heading = line[4:] + "\n"
            result.formats.append(Format("heading3", current_index, current_index + len(heading) - 1))
            result.text += heading
            current_index += len(heading)
            i += 1
            continue
```

- [ ] **Step 4: Run, see PASS**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gdocs_skill/markdown.py tests/test_markdown.py
git commit -m "feat: markdown headings H1/H2/H3"
```

### Task 8: Bullet, numbered, and checkbox lists

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing tests**

```python
# tests/test_markdown.py — append
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
```

- [ ] **Step 2: Run, see FAIL**

- [ ] **Step 3: Add list handlers**

Before the paragraph fallthrough (still inside the while loop), add:

```python
        # Checkbox (must come before bullet)
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
            line.startswith("- [x] ") or line.startswith("* [x] ")
            or line.startswith("- [X] ") or line.startswith("* [X] ")
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
```

- [ ] **Step 4: Run, see PASS**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gdocs_skill/markdown.py tests/test_markdown.py
git commit -m "feat: markdown bullet/numbered/checkbox lists"
```

### Task 9: Horizontal rule and empty lines

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing tests**

```python
# tests/test_markdown.py — append
def test_horizontal_rule():
    result = parse("---")
    assert result.text == "———————————————————————————\n"


def test_empty_line_between_paragraphs():
    result = parse("a\n\nb")
    assert result.text == "a\n\nb\n"
```

- [ ] **Step 2: Run, see FAIL**

- [ ] **Step 3: Add handlers**

Before paragraph fallthrough:

```python
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
```

- [ ] **Step 4: Run, see PASS**

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gdocs_skill/markdown.py tests/test_markdown.py
git commit -m "feat: markdown horizontal rule and empty lines"
```

### Task 10: Tables

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing test**

```python
# tests/test_markdown.py — append
def test_table_2x2_with_separator():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = parse(md)
    # Ruby inserts a single \n as a placeholder at the table position
    assert result.text == "\n"
    assert len(result.tables) == 1
    t = result.tables[0]
    assert t.num_rows == 2
    assert t.num_cols == 2
    assert t.rows == [["A", "B"], ["1", "2"]]
    assert t.insert_index == 1


def test_table_3x2():
    md = "| H1 | H2 |\n|---|---|\n| a | b |\n| c | d |"
    result = parse(md)
    assert result.text == "\n"
    t = result.tables[0]
    assert t.num_rows == 3
    assert t.rows == [["H1", "H2"], ["a", "b"], ["c", "d"]]
```

- [ ] **Step 2: Run, see FAIL**

- [ ] **Step 3: Add table handler**

Before horizontal rule, add:

```python
        if line.startswith("|") and line.endswith("|"):
            rows: list[list[str]] = []
            j = i
            while j < len(lines):
                tl = lines[j].rstrip()
                if not (tl.startswith("|") and tl.endswith("|")):
                    break
                cells = [c.strip() for c in tl[1:-1].split("|")]
                # Skip separator row (all cells are --- or :---:)
                if not all(re.fullmatch(r"[-:]+", c) for c in cells):
                    rows.append(cells)
                j += 1
            if rows:
                result.tables.append(TableSpec(
                    rows=rows,
                    insert_index=current_index,
                    num_rows=len(rows),
                    num_cols=len(rows[0]),
                ))
                result.text += "\n"
                current_index += 1
            i = j
            continue
```

- [ ] **Step 4: Run, see PASS**

Expected: 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gdocs_skill/markdown.py tests/test_markdown.py
git commit -m "feat: markdown tables"
```

### Task 11: Mixed document integration + base_index arithmetic

**Files:**
- Modify: `tests/test_markdown.py`

- [ ] **Step 1: Add failing tests**

```python
# tests/test_markdown.py — append
def test_mixed_document():
    md = "# Title\n\nPara **b**.\n\n- one\n- two"
    result = parse(md)
    assert result.text == "Title\n\nPara b.\n\n• one\n• two\n"
    kinds = [f.kind for f in result.formats]
    assert "heading1" in kinds
    assert "bold" in kinds


def test_base_index_shifts_format_ranges():
    md = "# Hi"
    r_default = parse(md)
    r_offset = parse(md, base_index=100)
    assert r_default.text == r_offset.text
    (orig,) = r_default.formats
    (shifted,) = r_offset.formats
    assert shifted.start == orig.start + 99
    assert shifted.end == orig.end + 99
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/test_markdown.py -v`
Expected: 14 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_markdown.py
git commit -m "test: markdown mixed document + base_index arithmetic"
```

### Task 12: Request builder for formats

**Files:**
- Modify: `scripts/gdocs_skill/markdown.py`

- [ ] **Step 1: Append `build_format_request` to markdown.py**

```python
# at bottom of scripts/gdocs_skill/markdown.py

def build_format_request(fmt: Format) -> dict:
    """Convert a Format to a Google Docs batchUpdate request dict."""
    rng = {"startIndex": fmt.start, "endIndex": fmt.end}
    if fmt.kind == "heading1":
        return {"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"}}
    if fmt.kind == "heading2":
        return {"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"}}
    if fmt.kind == "heading3":
        return {"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "HEADING_3"}, "fields": "namedStyleType"}}
    if fmt.kind == "bold":
        return {"updateTextStyle": {"range": rng, "textStyle": {"bold": True}, "fields": "bold"}}
    if fmt.kind == "italic":
        return {"updateTextStyle": {"range": rng, "textStyle": {"italic": True}, "fields": "italic"}}
    if fmt.kind == "code":
        return {
            "updateTextStyle": {
                "range": rng,
                "textStyle": {
                    "fontFamily": "Courier New",
                    "backgroundColor": {"color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}},
                },
                "fields": "fontFamily,backgroundColor",
            }
        }
    raise ValueError(f"Unknown format kind: {fmt.kind}")
```

- [ ] **Step 2: Quick sanity check (no new test — used by DocsClient)**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill.markdown import build_format_request, Format; print(build_format_request(Format('bold', 1, 5)))"`
Expected: prints a dict with `updateTextStyle` and `bold: True`.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/markdown.py
git commit -m "feat: markdown build_format_request"
```

---

## Phase 4: CLI shared helpers

### Task 13: Implement `cli.py` helpers and error mapping

**Files:**
- Create: `scripts/gdocs_skill/cli.py`

- [ ] **Step 1: Write the module (helpers only; dispatchers added in later tasks)**

```python
# scripts/gdocs_skill/cli.py
"""Shared CLI plumbing for docs_manager and drive_manager entry scripts."""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from googleapiclient.errors import HttpError

from .auth import AuthRequiredError, complete_auth, list_accounts

EXIT_SUCCESS = 0
EXIT_OPERATION_FAILED = 1
EXIT_AUTH_ERROR = 2
EXIT_API_ERROR = 3
EXIT_INVALID_ARGS = 4


def emit(data: dict) -> None:
    print(json.dumps(data, indent=2))


def emit_error(code: str, message: str, **extra: Any) -> None:
    payload: dict[str, Any] = {"status": "error", "error_code": code, "message": message}
    payload.update(extra)
    emit(payload)


def read_json_stdin() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        emit_error("INVALID_JSON", f"Failed to parse JSON stdin: {e}")
        sys.exit(EXIT_INVALID_ARGS)


def require_fields(data: dict, *fields: str, operation: str | None = None) -> None:
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        msg = f"Required fields: {', '.join(fields)}"
        extra = {"operation": operation} if operation else {}
        emit_error("MISSING_REQUIRED_FIELDS", msg, **extra)
        sys.exit(EXIT_INVALID_ARGS)


def pop_account(argv: list[str]) -> tuple[str | None, list[str]]:
    """Strip --account <name> from argv. Returns (account_or_None, remaining_argv)."""
    out = []
    account: str | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--account" and i + 1 < len(argv):
            account = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return account, out


def resolve_account(flag_account: str | None, body: dict | None = None) -> str:
    if flag_account:
        return flag_account
    if body and isinstance(body.get("account"), str) and body["account"]:
        return body["account"]
    env = os.environ.get("GDOCS_ACCOUNT")
    if env:
        return env
    return "default"


def handle_auth_required(e: AuthRequiredError, operation: str) -> None:
    if e.auth_url:
        emit_error(
            "AUTH_REQUIRED",
            str(e),
            operation=operation,
            auth_url=e.auth_url,
            instructions=[
                "1. Visit the authorization URL",
                "2. Grant access to the requested Google services",
                "3. Copy the authorization code",
                "4. Run: scripts/<script>.py auth <code> [--account <name>]",
            ],
        )
    else:
        emit_error("AUTH_REQUIRED", str(e), operation=operation)


def handle_http_error(e: HttpError, operation: str) -> None:
    emit_error("API_ERROR", f"Google API error: {e}", operation=operation)


def run_safely(operation: str, fn):
    """Invoke fn() and handle exceptions by emitting error JSON + sys.exit."""
    try:
        fn()
    except AuthRequiredError as e:
        handle_auth_required(e, operation)
        sys.exit(EXIT_AUTH_ERROR)
    except HttpError as e:
        handle_http_error(e, operation)
        sys.exit(EXIT_API_ERROR)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        emit_error("OPERATION_FAILED", f"Failed to {operation}: {e}", operation=operation)
        sys.exit(EXIT_OPERATION_FAILED)


def emit_list_accounts() -> None:
    emit({"status": "success", "operation": "list_accounts", "accounts": list_accounts()})


def do_auth(argv: list[str], operation: str = "auth") -> int:
    account, remaining = pop_account(argv)
    if not remaining:
        emit_error("MISSING_CODE", "Authorization code required", operation=operation,
                   usage="auth <code> [--account <name>]")
        return EXIT_INVALID_ARGS
    code = remaining[0]
    try:
        complete_auth(code, account or "default")
    except AuthRequiredError as e:
        handle_auth_required(e, operation)
        return EXIT_AUTH_ERROR
    except Exception as e:  # noqa: BLE001
        emit_error("AUTH_FAILED", f"Authorization failed: {e}", operation=operation)
        return EXIT_AUTH_ERROR
    emit({"status": "success", "operation": "auth", "account": account or "default"})
    return EXIT_SUCCESS
```

- [ ] **Step 2: Sanity import check**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill import cli; print(cli.EXIT_AUTH_ERROR)"`
Expected: prints `2`.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/cli.py
git commit -m "feat: shared CLI helpers + error mapping"
```

---

## Phase 5: Docs client, dispatcher, and entry script

### Task 14: Implement `DocsClient` — read/structure/create/delete

**Files:**
- Create: `scripts/gdocs_skill/docs.py`

- [ ] **Step 1: Write the module with first set of methods**

```python
# scripts/gdocs_skill/docs.py
"""Google Docs operations. One method per CLI command."""
from __future__ import annotations

from .auth import build_docs_service
from .markdown import build_format_request, parse


class DocsClient:
    def __init__(self, account: str = "default"):
        self._svc = build_docs_service(account)

    # ---- read / structure / create / delete ----

    def read(self, document_id: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        content = _extract_body_text(doc.get("body", {}).get("content", []))
        return {
            "status": "success",
            "operation": "read",
            "document_id": doc.get("documentId"),
            "title": doc.get("title"),
            "content": content,
            "revision_id": doc.get("revisionId"),
        }

    def structure(self, document_id: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        structure = []
        for element in doc.get("body", {}).get("content", []):
            para = element.get("paragraph")
            if not para:
                continue
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            if not style.startswith("HEADING_"):
                continue
            level = int(style.split("_")[-1])
            text = "".join(
                (e.get("textRun") or {}).get("content", "") for e in para.get("elements", [])
            )
            structure.append({
                "level": level,
                "text": text,
                "start_index": element.get("startIndex"),
                "end_index": element.get("endIndex"),
            })
        return {
            "status": "success",
            "operation": "structure",
            "document_id": doc.get("documentId"),
            "title": doc.get("title"),
            "structure": structure,
        }

    def create(self, title: str, content: str | None = None) -> dict:
        doc = self._svc.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        if content:
            self._svc.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
            ).execute()
        return {
            "status": "success",
            "operation": "create",
            "document_id": doc_id,
            "title": doc.get("title"),
            "revision_id": doc.get("revisionId"),
        }

    def delete(self, document_id: str, start_index: int, end_index: int) -> dict:
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"deleteContentRange": {"range": {"startIndex": start_index, "endIndex": end_index}}}]},
        ).execute()
        return {
            "status": "success",
            "operation": "delete",
            "document_id": document_id,
            "deleted_range": {"start": start_index, "end": end_index},
        }


def _extract_body_text(elements: list[dict]) -> str:
    parts = []
    for el in elements:
        if "paragraph" in el:
            para = el["paragraph"]
            parts.append("".join(
                (e.get("textRun") or {}).get("content", "") for e in para.get("elements", [])
            ))
        elif "table" in el:
            rows = []
            for row in el["table"].get("tableRows", []):
                cells = [_extract_body_text(cell.get("content", [])) for cell in row.get("tableCells", [])]
                rows.append(" | ".join(cells))
            parts.append("\n".join(rows))
    return "\n".join(parts)
```

- [ ] **Step 2: Sanity import check**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill.docs import DocsClient; print('ok')"`
Expected: prints `ok` (no auth happens at import).

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/docs.py
git commit -m "feat: DocsClient — read/structure/create/delete"
```

### Task 15: Extend `DocsClient` — insert/append/replace/format/page_break

**Files:**
- Modify: `scripts/gdocs_skill/docs.py`

- [ ] **Step 1: Append methods to `DocsClient`**

Insert the following code **inside the `DocsClient` class body**, after `delete` and before the module-level `_extract_body_text` function (use the existing indentation of `def read` etc. as a guide):

```python
    # ---- text manipulation ----

    def insert(self, document_id: str, text: str, index: int = 1) -> dict:
        result = self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertText": {"location": {"index": index}, "text": text}}]},
        ).execute()
        return {
            "status": "success",
            "operation": "insert",
            "document_id": document_id,
            "inserted_at": index,
            "text_length": len(text),
            "revision_id": result.get("documentId"),
        }

    def append(self, document_id: str, text: str) -> dict:
        doc = self._svc.documents().get(documentId=document_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text}}]},
        ).execute()
        return {
            "status": "success",
            "operation": "append",
            "document_id": document_id,
            "appended_at": end_index,
            "text_length": len(text),
        }

    def replace(self, document_id: str, find: str, replace: str, match_case: bool = False) -> dict:
        result = self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"replaceAllText": {
                "containsText": {"text": find, "matchCase": match_case},
                "replaceText": replace,
            }}]},
        ).execute()
        occurrences = result.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
        return {
            "status": "success",
            "operation": "replace",
            "document_id": document_id,
            "find": find,
            "replace": replace,
            "occurrences": occurrences,
        }

    def format(self, document_id: str, start_index: int, end_index: int,
               bold: bool | None = None, italic: bool | None = None, underline: bool | None = None) -> dict:
        style: dict = {}
        if bold is not None:
            style["bold"] = bold
        if italic is not None:
            style["italic"] = italic
        if underline is not None:
            style["underline"] = underline
        fields = ",".join(style.keys())
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"updateTextStyle": {
                "range": {"startIndex": start_index, "endIndex": end_index},
                "textStyle": style,
                "fields": fields,
            }}]},
        ).execute()
        return {
            "status": "success",
            "operation": "format",
            "document_id": document_id,
            "range": {"start": start_index, "end": end_index},
            "formatting": style,
        }

    def page_break(self, document_id: str, index: int) -> dict:
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertPageBreak": {"location": {"index": index}}}]},
        ).execute()
        return {
            "status": "success",
            "operation": "page_break",
            "document_id": document_id,
            "inserted_at": index,
        }
```

- [ ] **Step 2: Import check (quick syntax verification)**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill.docs import DocsClient; print([m for m in dir(DocsClient) if not m.startswith('_')])"`
Expected: lists insert/append/replace/format/page_break/read/structure/create/delete.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/docs.py
git commit -m "feat: DocsClient — insert/append/replace/format/page_break"
```

### Task 16: Extend `DocsClient` — insert_image, insert_table

**Files:**
- Modify: `scripts/gdocs_skill/docs.py`

- [ ] **Step 1: Append methods to `DocsClient`**

Insert the following code **inside the `DocsClient` class body**, after `page_break`:

```python
    # ---- images and tables ----

    def insert_image(self, document_id: str, image_url: str,
                     index: int | None = None, width: float | None = None, height: float | None = None) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        req: dict = {"insertInlineImage": {"location": {"index": index}, "uri": image_url}}
        obj_size: dict = {}
        if width is not None:
            obj_size["width"] = {"magnitude": width, "unit": "PT"}
        if height is not None:
            obj_size["height"] = {"magnitude": height, "unit": "PT"}
        if obj_size:
            req["insertInlineImage"]["objectSize"] = obj_size
        result = self._svc.documents().batchUpdate(
            documentId=document_id, body={"requests": [req]},
        ).execute()
        return {
            "status": "success",
            "operation": "insert_image",
            "document_id": document_id,
            "inserted_at": index,
            "image_url": image_url,
            "revision_id": result.get("documentId"),
        }

    def insert_table(self, document_id: str, rows: int, cols: int,
                     index: int | None = None, data: list[list[str]] | None = None) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        self._insert_table_at(document_id, rows, cols, index, data)
        return {
            "status": "success",
            "operation": "insert_table",
            "document_id": document_id,
            "rows": rows,
            "columns": cols,
            "inserted_at": index,
        }

    def _insert_table_at(self, document_id: str, rows: int, cols: int,
                         index: int, data: list[list[str]] | None) -> None:
        """Insert a table shell, then populate cells from `data` in reverse order
        (to preserve indices). Matches Ruby `insert_table_internal`."""
        self._svc.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertTable": {
                "rows": rows, "columns": cols, "location": {"index": index},
            }}]},
        ).execute()
        if not data:
            return
        doc = self._svc.documents().get(documentId=document_id).execute()
        table_el = None
        for el in doc["body"].get("content", []):
            if el.get("table") and el.get("startIndex", 0) >= index:
                table_el = el
                break
        if not table_el:
            return
        cell_requests = []
        # Reverse row × col so earlier insertions don't shift later ones
        for row_idx in range(len(data) - 1, -1, -1):
            if row_idx >= rows:
                continue
            row_data = data[row_idx]
            for col_idx in range(len(row_data) - 1, -1, -1):
                if col_idx >= cols:
                    continue
                tr = table_el["table"]["tableRows"][row_idx]
                tc = tr["tableCells"][col_idx]
                cell_start = tc["content"][0]["startIndex"]
                cell_requests.append({
                    "insertText": {"location": {"index": cell_start}, "text": str(row_data[col_idx])}
                })
        if cell_requests:
            self._svc.documents().batchUpdate(
                documentId=document_id, body={"requests": cell_requests},
            ).execute()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/gdocs_skill/docs.py
git commit -m "feat: DocsClient — insert_image and insert_table"
```

### Task 17: Extend `DocsClient` — create_from_markdown, insert_from_markdown

**Files:**
- Modify: `scripts/gdocs_skill/docs.py`

- [ ] **Step 1: Append markdown methods to `DocsClient`**

Insert the following code **inside the `DocsClient` class body**, after `insert_table` and its helper `_insert_table_at` (and before the module-level `_extract_body_text`):

```python
    # ---- markdown ----

    def create_from_markdown(self, title: str, markdown: str) -> dict:
        doc = self._svc.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        parsed = parse(markdown, base_index=1)
        self._apply_parsed(doc_id, parsed, base_index=1)
        return {
            "status": "success",
            "operation": "create_from_markdown",
            "document_id": doc_id,
            "title": title,
            "revision_id": doc.get("revisionId"),
            "tables_inserted": len(parsed.tables),
        }

    def insert_from_markdown(self, document_id: str, markdown: str, index: int | None = None) -> dict:
        if index is None:
            doc = self._svc.documents().get(documentId=document_id).execute()
            index = doc["body"]["content"][-1]["endIndex"] - 1
        parsed = parse(markdown, base_index=index)
        self._apply_parsed(document_id, parsed, base_index=index)
        return {
            "status": "success",
            "operation": "insert_from_markdown",
            "document_id": document_id,
            "inserted_at": index,
            "text_length": len(parsed.text),
            "formats_applied": len(parsed.formats),
        }

    def _apply_parsed(self, document_id: str, parsed, base_index: int) -> None:
        # 1. Insert plain text at base_index
        if parsed.text:
            self._svc.documents().batchUpdate(
                documentId=document_id,
                body={"requests": [{"insertText": {"location": {"index": base_index}, "text": parsed.text}}]},
            ).execute()
        # 2. Apply formatting in reverse order (preserve indices)
        format_requests = [build_format_request(f) for f in reversed(parsed.formats)]
        if format_requests:
            self._svc.documents().batchUpdate(
                documentId=document_id, body={"requests": format_requests},
            ).execute()
        # 3. Insert tables in reverse order
        for table in reversed(parsed.tables):
            self._insert_table_at(document_id, table.num_rows, table.num_cols,
                                  table.insert_index, table.rows)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/gdocs_skill/docs.py
git commit -m "feat: DocsClient — create_from_markdown and insert_from_markdown"
```

### Task 18: Implement `main_docs` dispatcher in `cli.py`

**Files:**
- Modify: `scripts/gdocs_skill/cli.py`

- [ ] **Step 1: Append the dispatcher to `cli.py`**

```python
# at bottom of scripts/gdocs_skill/cli.py

def main_docs(argv: list[str]) -> int:
    if not argv:
        emit_error("MISSING_COMMAND", "Usage: docs_manager.py <command> [...]")
        return EXIT_INVALID_ARGS

    # Auth is handled without account-requiring initialization
    if argv[0] == "auth":
        return do_auth(argv[1:], operation="auth")

    if argv[0] == "list-accounts":
        emit_list_accounts()
        return EXIT_SUCCESS

    flag_account, remaining = pop_account(argv)
    command = remaining[0]

    # Commands that take JSON on stdin
    stdin_commands = {
        "insert", "append", "replace", "format", "page-break",
        "create", "create-from-markdown", "insert-from-markdown",
        "delete", "insert-image", "insert-table",
    }

    body: dict | None = None
    if command in stdin_commands:
        body = read_json_stdin()

    account = resolve_account(flag_account, body)

    def run():
        # Import here so `list-accounts` and `auth` don't require credentials to load
        from .docs import DocsClient
        client = DocsClient(account=account)
        match command:
            case "read":
                if len(remaining) < 2:
                    emit_error("MISSING_DOCUMENT_ID", "Document ID required", operation="read")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.read(remaining[1]))
            case "structure":
                if len(remaining) < 2:
                    emit_error("MISSING_DOCUMENT_ID", "Document ID required", operation="structure")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.structure(remaining[1]))
            case "insert":
                require_fields(body, "document_id", "text", operation="insert")
                emit(client.insert(body["document_id"], body["text"], body.get("index", 1)))
            case "append":
                require_fields(body, "document_id", "text", operation="append")
                emit(client.append(body["document_id"], body["text"]))
            case "replace":
                require_fields(body, "document_id", "find", "replace", operation="replace")
                emit(client.replace(body["document_id"], body["find"], body["replace"],
                                    body.get("match_case", False)))
            case "format":
                require_fields(body, "document_id", "start_index", "end_index", operation="format")
                emit(client.format(body["document_id"], body["start_index"], body["end_index"],
                                   body.get("bold"), body.get("italic"), body.get("underline")))
            case "page-break":
                require_fields(body, "document_id", "index", operation="page_break")
                emit(client.page_break(body["document_id"], body["index"]))
            case "create":
                require_fields(body, "title", operation="create")
                emit(client.create(body["title"], body.get("content")))
            case "create-from-markdown":
                require_fields(body, "title", "markdown", operation="create_from_markdown")
                emit(client.create_from_markdown(body["title"], body["markdown"]))
            case "insert-from-markdown":
                require_fields(body, "document_id", "markdown", operation="insert_from_markdown")
                emit(client.insert_from_markdown(body["document_id"], body["markdown"], body.get("index")))
            case "delete":
                require_fields(body, "document_id", "start_index", "end_index", operation="delete")
                emit(client.delete(body["document_id"], body["start_index"], body["end_index"]))
            case "insert-image":
                require_fields(body, "document_id", "image_url", operation="insert_image")
                emit(client.insert_image(body["document_id"], body["image_url"],
                                         body.get("index"), body.get("width"), body.get("height")))
            case "insert-table":
                require_fields(body, "document_id", "rows", "cols", operation="insert_table")
                emit(client.insert_table(body["document_id"], body["rows"], body["cols"],
                                         body.get("index"), body.get("data")))
            case _:
                emit_error("INVALID_COMMAND", f"Unknown command: {command}",
                           valid_commands=sorted([
                               "auth", "read", "structure", "insert", "append", "replace",
                               "format", "page-break", "create", "create-from-markdown",
                               "insert-from-markdown", "delete", "insert-image", "insert-table",
                               "list-accounts",
                           ]))
                sys.exit(EXIT_INVALID_ARGS)

    run_safely(command, run)
    return EXIT_SUCCESS
```

- [ ] **Step 2: Commit**

```bash
git add scripts/gdocs_skill/cli.py
git commit -m "feat: docs_manager CLI dispatcher"
```

### Task 19: Entry script `scripts/docs_manager.py`

**Files:**
- Create: `scripts/docs_manager.py`

- [ ] **Step 1: Write the entry**

```python
#!/usr/bin/env -S uv run
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdocs_skill.cli import main_docs

if __name__ == "__main__":
    sys.exit(main_docs(sys.argv[1:]))
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/docs_manager.py`

- [ ] **Step 3: Smoke-test unknown-command error path (no auth needed)**

Run: `scripts/docs_manager.py bogus-command`
Expected: JSON error with `"error_code": "INVALID_COMMAND"` and exit code 4.

Caveat: if `uv run` (via shebang) fails to find the project from the current CWD, run from the skill root or use `uv run scripts/docs_manager.py bogus-command`. See spec Risks.

- [ ] **Step 4: Smoke-test list-accounts (no auth needed if no tokens exist)**

Run: `scripts/docs_manager.py list-accounts`
Expected: JSON `{"status": "success", "operation": "list_accounts", "accounts": [...]}`.

- [ ] **Step 5: Smoke-test a real docs call against a known test doc (requires auth)**

If you have an authed `token_python_default.json`:
Run: `scripts/docs_manager.py read <document_id>`
Expected: the document content as JSON.

If not authed: expect `AUTH_REQUIRED` error with an auth URL. Complete auth with `scripts/docs_manager.py auth <code>` and retry.

- [ ] **Step 6: Commit**

```bash
git add scripts/docs_manager.py
git commit -m "feat: docs_manager.py executable entry script"
```

---

## Phase 6: Drive client, dispatcher, and entry script

### Task 20: Implement `DriveClient`

**Files:**
- Create: `scripts/gdocs_skill/drive.py`

- [ ] **Step 1: Write the module**

```python
# scripts/gdocs_skill/drive.py
"""Google Drive operations. One method per CLI command.
Uses --flag-style CLI args (unlike docs_manager which uses JSON stdin)."""
from __future__ import annotations

import mimetypes
import os

from googleapiclient.http import MediaFileUpload

from .auth import build_drive_service

_EXT_MIME = {
    ".excalidraw": "application/json",
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html", ".htm": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".zip": "application/zip",
    ".csv": "text/csv",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml", ".yml": "application/x-yaml",
}

_EXPORT_DEFAULT = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "image/png",
}


def detect_mime_type(file_path: str) -> str:
    _, ext = os.path.splitext(file_path.lower())
    return _EXT_MIME.get(ext) or mimetypes.guess_type(file_path)[0] or "application/octet-stream"


def _file_dict(f: dict) -> dict:
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "mime_type": f.get("mimeType"),
        "web_view_link": f.get("webViewLink"),
        "web_content_link": f.get("webContentLink"),
        "parents": f.get("parents"),
        "created_time": f.get("createdTime"),
        "modified_time": f.get("modifiedTime"),
        "size": f.get("size"),
    }


class DriveClient:
    FIELDS_BASIC = "id, name, mimeType, webViewLink, webContentLink, parents, createdTime, modifiedTime, size"

    def __init__(self, account: str = "default"):
        self._svc = build_drive_service(account)

    def upload(self, file: str, name: str | None = None,
               folder_id: str | None = None, mime_type: str | None = None) -> dict:
        if not os.path.exists(file):
            return {"status": "error", "error_code": "FILE_NOT_FOUND",
                    "operation": "upload", "message": f"File not found: {file}"}
        mt = mime_type or detect_mime_type(file)
        metadata: dict = {"name": name or os.path.basename(file)}
        if folder_id:
            metadata["parents"] = [folder_id]
        media = MediaFileUpload(file, mimetype=mt, resumable=False)
        created = self._svc.files().create(body=metadata, media_body=media, fields=self.FIELDS_BASIC).execute()
        return {"status": "success", "operation": "upload", "file": _file_dict(created)}

    def download(self, file_id: str, output: str, export_as: str | None = None) -> dict:
        meta = self._svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
        if meta["mimeType"].startswith("application/vnd.google-apps."):
            export_mime = export_as or _EXPORT_DEFAULT.get(meta["mimeType"], "application/pdf")
            data = self._svc.files().export(fileId=file_id, mimeType=export_mime).execute()
            with open(output, "wb") as fh:
                fh.write(data)
            return {"status": "success", "operation": "export",
                    "file_id": file_id, "output_path": output, "export_mime_type": export_mime}
        request = self._svc.files().get_media(fileId=file_id)
        with open(output, "wb") as fh:
            fh.write(request.execute())
        return {"status": "success", "operation": "download",
                "file_id": file_id, "output_path": output,
                "name": meta["name"], "mime_type": meta["mimeType"]}

    def list_files(self, folder_id: str | None = None, max_results: int = 100) -> dict:
        query = ["trashed = false"]
        if folder_id:
            query.append(f"'{folder_id}' in parents")
        results = self._svc.files().list(
            q=" and ".join(query), pageSize=max_results,
            fields=f"nextPageToken, files({self.FIELDS_BASIC})",
        ).execute()
        files = [_file_dict(f) for f in results.get("files", [])]
        return {"status": "success", "operation": "list",
                "folder_id": folder_id, "files": files,
                "next_page_token": results.get("nextPageToken"), "count": len(files)}

    def search(self, query: str, max_results: int = 100) -> dict:
        full_query = query if "trashed" in query else f"{query} and trashed = false"
        results = self._svc.files().list(
            q=full_query, pageSize=max_results,
            fields=f"nextPageToken, files({self.FIELDS_BASIC})",
        ).execute()
        files = [_file_dict(f) for f in results.get("files", [])]
        return {"status": "success", "operation": "search",
                "query": query, "files": files,
                "next_page_token": results.get("nextPageToken"), "count": len(files)}

    def get_metadata(self, file_id: str) -> dict:
        fields = ("id, name, mimeType, webViewLink, webContentLink, parents, "
                  "createdTime, modifiedTime, size, description, starred, trashed, "
                  "owners, permissions")
        f = self._svc.files().get(fileId=file_id, fields=fields).execute()
        return {"status": "success", "operation": "get_metadata", "file": {
            **_file_dict(f),
            "description": f.get("description"),
            "starred": f.get("starred"),
            "trashed": f.get("trashed"),
            "owners": [{"email": o.get("emailAddress"), "name": o.get("displayName")}
                       for o in (f.get("owners") or [])],
            "permissions": [{"id": p.get("id"), "type": p.get("type"),
                             "role": p.get("role"), "email": p.get("emailAddress")}
                            for p in (f.get("permissions") or [])],
        }}

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        metadata: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            metadata["parents"] = [parent_id]
        result = self._svc.files().create(
            body=metadata, fields="id, name, mimeType, webViewLink, parents, createdTime",
        ).execute()
        return {"status": "success", "operation": "create_folder", "folder": {
            "id": result["id"], "name": result["name"],
            "web_view_link": result.get("webViewLink"),
            "parents": result.get("parents"),
            "created_time": result.get("createdTime"),
        }}

    def move(self, file_id: str, folder_id: str) -> dict:
        f = self._svc.files().get(fileId=file_id, fields="parents").execute()
        previous = ",".join(f.get("parents") or [])
        result = self._svc.files().update(
            fileId=file_id, addParents=folder_id, removeParents=previous,
            body={}, fields="id, name, parents, webViewLink",
        ).execute()
        return {"status": "success", "operation": "move", "file": {
            "id": result["id"], "name": result["name"],
            "parents": result.get("parents"),
            "web_view_link": result.get("webViewLink"),
        }}

    def share(self, file_id: str, email: str | None = None,
              role: str = "reader", type: str | None = None, domain: str | None = None) -> dict:
        perm_type = type or ("user" if email else "anyone")
        body: dict = {"type": perm_type, "role": role}
        if email and perm_type == "user":
            body["emailAddress"] = email
        if domain and perm_type == "domain":
            body["domain"] = domain
        permission = self._svc.permissions().create(
            fileId=file_id, body=body, fields="id, type, role, emailAddress",
        ).execute()
        info = self._svc.files().get(fileId=file_id, fields="webViewLink, webContentLink").execute()
        return {"status": "success", "operation": "share",
                "permission": {"id": permission["id"], "type": permission["type"],
                               "role": permission["role"], "email": permission.get("emailAddress")},
                "web_view_link": info.get("webViewLink"),
                "web_content_link": info.get("webContentLink")}

    def delete(self, file_id: str, permanent: bool = False) -> dict:
        if permanent:
            self._svc.files().delete(fileId=file_id).execute()
        else:
            self._svc.files().update(fileId=file_id, body={"trashed": True}).execute()
        return {"status": "success", "operation": "delete",
                "file_id": file_id, "permanent": permanent}

    def copy(self, file_id: str, name: str | None = None, folder_id: str | None = None) -> dict:
        body: dict = {}
        if name:
            body["name"] = name
        if folder_id:
            body["parents"] = [folder_id]
        result = self._svc.files().copy(
            fileId=file_id, body=body,
            fields="id, name, mimeType, webViewLink, parents, createdTime",
        ).execute()
        return {"status": "success", "operation": "copy", "file": {
            "id": result["id"], "name": result["name"],
            "mime_type": result.get("mimeType"),
            "web_view_link": result.get("webViewLink"),
            "parents": result.get("parents"),
            "created_time": result.get("createdTime"),
        }}

    def update(self, file_id: str, file: str, name: str | None = None) -> dict:
        if not os.path.exists(file):
            return {"status": "error", "error_code": "FILE_NOT_FOUND",
                    "operation": "update", "message": f"File not found: {file}"}
        mt = detect_mime_type(file)
        body: dict = {}
        if name:
            body["name"] = name
        media = MediaFileUpload(file, mimetype=mt, resumable=False)
        result = self._svc.files().update(
            fileId=file_id, media_body=media, body=body,
            fields="id, name, mimeType, webViewLink, modifiedTime, size",
        ).execute()
        return {"status": "success", "operation": "update", "file": {
            "id": result["id"], "name": result["name"],
            "mime_type": result.get("mimeType"),
            "web_view_link": result.get("webViewLink"),
            "modified_time": result.get("modifiedTime"),
            "size": result.get("size"),
        }}
```

- [ ] **Step 2: Import check**

Run: `uv run python -c "import sys; sys.path.insert(0, 'scripts'); from gdocs_skill.drive import DriveClient; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/gdocs_skill/drive.py
git commit -m "feat: DriveClient with all Drive operations"
```

### Task 21: `main_drive` dispatcher in `cli.py`

**Files:**
- Modify: `scripts/gdocs_skill/cli.py`

- [ ] **Step 1: Append the dispatcher**

```python
# at bottom of scripts/gdocs_skill/cli.py

def _parse_drive_flags(argv: list[str]) -> dict:
    """Parse --flag-style args used by drive_manager (mirrors the Ruby parse_args)."""
    out: dict = {}
    i = 0
    mapping = {
        "--file": "file", "--file-id": "file_id", "--folder-id": "folder_id",
        "--parent-id": "parent_id", "--output": "output", "--name": "name",
        "--query": "query", "--email": "email", "--role": "role", "--type": "type",
        "--mime-type": "mime_type", "--domain": "domain", "--export-as": "export_as",
    }
    while i < len(argv):
        tok = argv[i]
        if tok in mapping and i + 1 < len(argv):
            out[mapping[tok]] = argv[i + 1]
            i += 2
            continue
        if tok == "--max-results" and i + 1 < len(argv):
            out["max_results"] = int(argv[i + 1])
            i += 2
            continue
        if tok == "--permanent":
            out["permanent"] = True
            i += 1
            continue
        i += 1
    return out


def main_drive(argv: list[str]) -> int:
    if not argv:
        emit_error("MISSING_COMMAND", "Usage: drive_manager.py <command> [...]")
        return EXIT_INVALID_ARGS

    if argv[0] == "auth":
        return do_auth(argv[1:], operation="auth")

    if argv[0] == "list-accounts":
        emit_list_accounts()
        return EXIT_SUCCESS

    flag_account, remaining = pop_account(argv)
    command = remaining[0]
    opts = _parse_drive_flags(remaining[1:])
    account = resolve_account(flag_account)

    def run():
        from .drive import DriveClient
        client = DriveClient(account=account)
        match command:
            case "upload":
                if not opts.get("file"):
                    emit_error("MISSING_FILE", "File path required: --file <path>", operation="upload")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.upload(opts["file"], opts.get("name"), opts.get("folder_id"), opts.get("mime_type")))
            case "download":
                if not (opts.get("file_id") and opts.get("output")):
                    emit_error("MISSING_ARGS", "--file-id and --output required", operation="download")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.download(opts["file_id"], opts["output"], opts.get("export_as")))
            case "list":
                emit(client.list_files(opts.get("folder_id"), opts.get("max_results", 100)))
            case "search":
                if not opts.get("query"):
                    emit_error("MISSING_QUERY", "--query required", operation="search")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.search(opts["query"], opts.get("max_results", 100)))
            case "get-metadata":
                if not opts.get("file_id"):
                    emit_error("MISSING_FILE_ID", "--file-id required", operation="get_metadata")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.get_metadata(opts["file_id"]))
            case "create-folder":
                if not opts.get("name"):
                    emit_error("MISSING_NAME", "--name required", operation="create_folder")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.create_folder(opts["name"], opts.get("parent_id") or opts.get("folder_id")))
            case "move":
                if not (opts.get("file_id") and opts.get("folder_id")):
                    emit_error("MISSING_ARGS", "--file-id and --folder-id required", operation="move")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.move(opts["file_id"], opts["folder_id"]))
            case "share":
                if not opts.get("file_id"):
                    emit_error("MISSING_FILE_ID", "--file-id required", operation="share")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.share(opts["file_id"], opts.get("email"),
                                  opts.get("role", "reader"), opts.get("type"), opts.get("domain")))
            case "delete":
                if not opts.get("file_id"):
                    emit_error("MISSING_FILE_ID", "--file-id required", operation="delete")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.delete(opts["file_id"], opts.get("permanent", False)))
            case "copy":
                if not opts.get("file_id"):
                    emit_error("MISSING_FILE_ID", "--file-id required", operation="copy")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.copy(opts["file_id"], opts.get("name"), opts.get("folder_id")))
            case "update":
                if not (opts.get("file_id") and opts.get("file")):
                    emit_error("MISSING_ARGS", "--file-id and --file required", operation="update")
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.update(opts["file_id"], opts["file"], opts.get("name")))
            case _:
                emit_error("UNKNOWN_COMMAND", f"Unknown command: {command}",
                           hint="Run drive_manager.py --help")
                sys.exit(EXIT_INVALID_ARGS)

    run_safely(command, run)
    return EXIT_SUCCESS
```

- [ ] **Step 2: Commit**

```bash
git add scripts/gdocs_skill/cli.py
git commit -m "feat: drive_manager CLI dispatcher"
```

### Task 22: Entry script `scripts/drive_manager.py`

**Files:**
- Create: `scripts/drive_manager.py`

- [ ] **Step 1: Write the entry**

```python
#!/usr/bin/env -S uv run
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdocs_skill.cli import main_drive

if __name__ == "__main__":
    sys.exit(main_drive(sys.argv[1:]))
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/drive_manager.py`

- [ ] **Step 3: Smoke-test list-accounts and unknown command**

Run: `scripts/drive_manager.py list-accounts`
Expected: JSON success with accounts list.

Run: `scripts/drive_manager.py bogus`
Expected: JSON error with `"error_code": "UNKNOWN_COMMAND"`.

- [ ] **Step 4: Smoke-test a real drive call (requires auth)**

Run: `scripts/drive_manager.py list --max-results 5`
Expected: JSON with up to 5 files.

- [ ] **Step 5: Commit**

```bash
git add scripts/drive_manager.py
git commit -m "feat: drive_manager.py executable entry script"
```

---

## Phase 7: Delete Ruby and migrate docs

### Task 23: Delete Ruby scripts

**Files:**
- Delete: `scripts/docs_manager.rb`
- Delete: `scripts/drive_manager.rb`

- [ ] **Step 1: Verify Python scripts are working**

Re-run smoke tests from Task 19 step 3-4 and Task 22 step 3. If any fail, stop and fix before deleting Ruby.

- [ ] **Step 2: Remove Ruby files**

Run: `git rm scripts/docs_manager.rb scripts/drive_manager.rb`

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove Ruby implementation, replaced by Python port"
```

### Task 24: Update `SKILL.md`

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Frontmatter — bump version to 2.0.0**

Find:
```yaml
version: 1.2.0
```
Replace with:
```yaml
version: 2.0.0
```

- [ ] **Step 2: Global rename `.rb` → `.py` in command examples**

Run: `sed -i '' 's|docs_manager\.rb|docs_manager.py|g' SKILL.md`
Run: `sed -i '' 's|drive_manager\.rb|drive_manager.py|g' SKILL.md`

- [ ] **Step 3: Add `uv sync` setup step to the Authentication Setup section**

Find the "Authentication Setup" section, prepend a new subsection above "First Time Setup":

```markdown
**Prerequisites**:
- `uv` installed (https://docs.astral.sh/uv/).
- After cloning the skill, run `uv sync` in the skill directory to install Python dependencies.
```

- [ ] **Step 4: Update the `Dependencies:` footer**

Find:
```
**Dependencies**: Ruby with `google-apis-docs_v1`, `google-apis-drive_v3`, `googleauth` gems (shared with other Google skills)
```
Replace with:
```
**Dependencies**: Python 3.11+ with `google-api-python-client`, `google-auth`, `google-auth-oauthlib` (managed via `uv`).
```

- [ ] **Step 5: Add a "Multi-Account Support" section before "Authentication Setup"**

```markdown
## Multi-Account Support

All commands accept an optional `--account <name>` flag to target a specific Google account. Precedence (highest wins):

1. `--account <name>` CLI flag
2. `"account"` field in JSON stdin body (for stdin-based commands)
3. `GDOCS_ACCOUNT` environment variable
4. `"default"`

**First-time auth for a named account**:
```bash
scripts/docs_manager.py auth <code> --account work
```

**Using a specific account for one command**:
```bash
scripts/docs_manager.py read <doc_id> --account work
```

**JSON-input commands accept `account` in the body**:
```bash
echo '{"title":"X","account":"work"}' | scripts/docs_manager.py create
```

**Set default for a shell session**:
```bash
export GDOCS_ACCOUNT=work
scripts/docs_manager.py read <doc_id>
```

**List configured accounts**:
```bash
scripts/docs_manager.py list-accounts
```

Tokens are stored per-account at `~/.claude/.google/token_python_<account>.json`.
```

- [ ] **Step 6: Add 2.0.0 entry to Version History**

Find the `## Version History` section and prepend:

```markdown
- **2.0.0** (2026-04-18) - Port from Ruby to Python. External CLI contract preserved exactly (same command names, JSON shapes, exit codes). New multi-account support via `--account`. Managed by `uv`; requires `uv sync` after cloning. Token format is now Python native (`google-auth`), stored at `~/.claude/.google/token_python_<account>.json` — existing Ruby token at `token.json` is untouched.
```

- [ ] **Step 7: Visually inspect SKILL.md to make sure nothing is broken**

Run: `uv run python -c "open('SKILL.md').read()"`
Expected: no exception.

- [ ] **Step 8: Commit**

```bash
git add SKILL.md
git commit -m "docs: SKILL.md 2.0.0 — Python invocations, uv setup, multi-account"
```

### Task 25: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rename `.rb` → `.py` in examples**

Run: `sed -i '' 's|docs_manager\.rb|docs_manager.py|g' README.md`
Run: `sed -i '' 's|drive_manager\.rb|drive_manager.py|g' README.md`

- [ ] **Step 2: Update Setup section to mention `uv sync`**

Open `README.md` and change the Setup section to add:

```markdown
5. **Install dependencies** - Run `uv sync` in the skill directory (`uv` is required; see https://docs.astral.sh/uv/).
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README — Python invocations and uv setup"
```

### Task 26: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the "Architecture" section**

Replace the "Two monolithic Ruby scripts" paragraph with:

```markdown
Python package at `scripts/gdocs_skill/` with thin entry scripts:

- `scripts/gdocs_skill/auth.py` — OAuth flow, multi-account tokens at `~/.claude/.google/token_python_<account>.json`.
- `scripts/gdocs_skill/markdown.py` — pure Markdown → `{text, formats, tables}` parser. Has pytest coverage.
- `scripts/gdocs_skill/docs.py` — `DocsClient` wrapping `googleapiclient` for Docs operations.
- `scripts/gdocs_skill/drive.py` — `DriveClient` for Drive operations.
- `scripts/gdocs_skill/cli.py` — shared CLI helpers, `main_docs` and `main_drive` dispatchers.
- `scripts/docs_manager.py` and `scripts/drive_manager.py` — thin executable entry scripts (shebang: `#!/usr/bin/env -S uv run`).

Adding a new command still touches three places: a method on `DocsClient`/`DriveClient`, a `match` arm in `cli.py`, and an example in `SKILL.md`.
```

- [ ] **Step 2: Update the "Development" section**

Replace the Ruby dependency/gem block with:

```markdown
**Dependencies:** Managed via `uv` + `pyproject.toml`. Run `uv sync` after cloning to create `.venv/`.

**Running a command locally:**
```bash
scripts/docs_manager.py read <document_id>
echo '{"title":"Test","markdown":"# Hi"}' | scripts/docs_manager.py create-from-markdown
```

**Tests:** Unit tests cover the markdown parser only. Run: `uv run pytest`. The E2E skill-ci workflow exercises the API-touching code against real Google services.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — reflect Python package layout"
```

### Task 27: Update references and examples

**Files:**
- Modify: `references/docs_operations.md`, `references/formatting_guide.md`, `references/integration-patterns.md`, `references/troubleshooting.md`, `references/cli-patterns.md`
- Modify: `examples/sample_operations.md`

- [ ] **Step 1: Bulk rename**

Run:
```bash
for f in references/*.md examples/*.md; do
  sed -i '' 's|docs_manager\.rb|docs_manager.py|g' "$f"
  sed -i '' 's|drive_manager\.rb|drive_manager.py|g' "$f"
done
```

- [ ] **Step 2: Spot-check each file**

Run: `grep -n "\.rb\|gem\|ruby\|googleauth\|Ruby" references/*.md examples/*.md`
Expected: any remaining hits are incidental (e.g. "ruby" inside a word). Inspect and manually fix any prose references to Ruby specifics (e.g. "install the gems" → "install with `uv sync`").

- [ ] **Step 3: Commit**

```bash
git add references/ examples/
git commit -m "docs: references and examples — Python invocations"
```

---

## Phase 8: CI verification

### Task 28: Verify CI handles the Python skill

**Files:**
- Possibly: `.github/workflows/ci.yml`

- [ ] **Step 1: Read the reusable workflow**

Fetch / read `https://raw.githubusercontent.com/robtaylor/skills/add-skill-ci/.github/workflows/skill-ci.yml` and check whether it:
- Detects `pyproject.toml` and sets up Python + `uv`.
- Runs `uv sync` and `uv run pytest`.
- Handles the absence of a `Gemfile` gracefully.

- [ ] **Step 2: Decide**

- **If the workflow handles Python:** leave `.github/workflows/ci.yml` unchanged.
- **If not:** add a local `pytest` job before the reusable call. Skeleton:

```yaml
# .github/workflows/ci.yml
name: Skill CI

on:
  push:
    branches: [main, python]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read
  id-token: write
  pull-requests: write

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest -v

  test-skill:
    needs: pytest
    uses: robtaylor/skills/.github/workflows/skill-ci.yml@add-skill-ci
    with:
      skill_path: "."
      run_api_test: true
      run_claude_code_test: true
    secrets: inherit
```

- [ ] **Step 3: If modified, commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest before the E2E skill-ci workflow"
```

### Task 29: Final verification and branch state

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: all markdown tests PASS.

- [ ] **Step 2: Visual walk through `git log`**

Run: `git log --oneline origin/main..HEAD`
Expected: a clean sequence of commits corresponding to the tasks above.

- [ ] **Step 3: Check nothing Ruby remains**

Run: `ls scripts/*.rb 2>/dev/null; grep -rn "\.rb\|Gemfile\|gem install" --include="*.md" --include="*.yml" . || true`
Expected: no Ruby files; only incidental `.rb` matches in historical doc sections, if any.

- [ ] **Step 4: Smoke-test end-to-end once more**

If auth is set up:
```bash
echo '{"title":"Python Port Smoke Test","markdown":"# Hi\n\nHello from **Python**."}' | scripts/docs_manager.py create-from-markdown
```
Expected: JSON success with document_id. Visit the doc in a browser to confirm formatting rendered correctly (heading + bold).

- [ ] **Step 5: Optional — push the branch**

```bash
git push -u origin python
```

Do NOT merge to main until the user confirms the port is working.

---

## Non-goals / deferred

These are explicitly NOT part of this plan — track separately if desired:

- Nested list support, markdown links, code fences, blockquotes, strikethrough.
- CLI UX cleanup (underscore vs hyphen consistency, richer `--help`).
- Mocking-based tests for `DocsClient`/`DriveClient`.
- Linter/type-checker setup (ruff, mypy).
- Migrating the Ruby `token.json` to Python format (users re-auth once).
