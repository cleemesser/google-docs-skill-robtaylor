# Python Port — Design Spec

**Date:** 2026-04-18
**Status:** Approved (awaiting implementation plan)
**Branch:** `python`

## Goal

Translate the two Ruby scripts (`scripts/docs_manager.rb`, `scripts/drive_manager.rb`) to Python, replacing them entirely. The external CLI contract consumed by Claude through `SKILL.md` is preserved exactly; only the implementation language and runtime change. One new capability (multi-account support) is added as part of the port.

## Summary of decisions

| Axis | Decision |
|------|----------|
| Ruby coexistence | **Replace.** Delete Ruby; Python on `python` branch. Major version bump 1.2.0 → 2.0.0. |
| Python runner | **`uv`.** Required on user's machine. |
| Dependency management | **`pyproject.toml` + `uv sync`.** Single source of truth for deps. |
| CLI contract | **Preserved.** Same command names, JSON fields, output shapes, exit codes. |
| Internal layout | **Small package** under `scripts/gdocs_skill/`, thin entry scripts in `scripts/`. |
| Python version | **3.11+** (for `match` statements and `X | None` typing). |
| Tests | **pytest for markdown parser only** (~12 cases). No CLI/client mocking tests. |
| Auth library | **`google-auth` + `google-auth-oauthlib` + `google-api-python-client`** (direct analogues of the Ruby gems). |
| Token format | **Native Python format** (`Credentials.to_json()`), not Ruby-compatible. |
| Token path | **`~/.claude/.google/token_python_<account>.json`** (separate from any Ruby skill's `token.json`). |
| Multi-account | **Supported** via `--account <name>` CLI flag, `"account"` JSON field, or `GDOCS_ACCOUNT` env var. |

## Repository layout after the port

```
scripts/
  docs_manager.py          # thin entry, ~10 lines, shebang: #!/usr/bin/env -S uv run --script
  drive_manager.py         # thin entry, ~10 lines, same shebang
  gdocs_skill/
    __init__.py
    auth.py                # OAuth flow, token storage, scope list, multi-account support
    docs.py                # DocsClient: one method per Docs CLI command
    drive.py               # DriveClient: one method per Drive CLI command
    markdown.py            # Markdown → batchUpdate request list (pure, no network)
    cli.py                 # JSON stdin/stdout helpers, dispatchers (main_docs, main_drive)
tests/
  test_markdown.py         # ~12 cases covering the parser
pyproject.toml
uv.lock                    # committed
```

Ruby files (`scripts/docs_manager.rb`, `scripts/drive_manager.rb`) deleted in the same commit series. `references/` and `examples/` kept as prose; updated only where they reference Ruby/gem specifics.

## Module design

### `gdocs_skill/auth.py`

Single source of truth for OAuth. Both `DocsClient` and `DriveClient` call into it.

```python
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/gmail.modify",
]
CREDENTIALS_PATH = Path.home() / ".claude" / ".google" / "client_secret.json"
TOKEN_DIR        = Path.home() / ".claude" / ".google"

def token_path(account: str) -> Path: ...              # TOKEN_DIR / f"token_python_{account}.json"
def get_credentials(account: str = "default") -> Credentials: ...
def complete_auth(code: str, account: str = "default") -> None: ...
def build_docs_service(account: str = "default") -> Resource: ...
def build_drive_service(account: str = "default") -> Resource: ...
def list_accounts() -> list[str]: ...                  # parse filenames in TOKEN_DIR
```

Behaviour preserved from Ruby:
- Same auth-required error shape on missing credentials: `{"status":"error","error_code":"AUTH_REQUIRED","auth_url":"...","instructions":[...]}` + exit code 2.
- Same `auth <code>` subcommand on both entry scripts to complete the flow, now with optional `--account <name>`.
- Token auto-refresh on expiry (`google-auth` handles this; call `creds.refresh(Request())` when `creds.expired and creds.refresh_token`).
- Full scope superset requested so a single token works for any Google skill in the Python family.

Behaviour changed from Ruby:
- Token file naming: `token_python_<account>.json` (Ruby used fixed `token.json`).
- Token format: native Python (`Credentials.to_json()`); not interoperable with Ruby `googleauth` token format.
- Multi-account: account is a first-class parameter; default is `"default"`.

### `gdocs_skill/markdown.py`

Pure module. No network. The one place with real logic density and the reason we have tests.

```python
def build_create_requests(markdown: str) -> list[dict]:
    """Requests for create-from-markdown (empty new doc, start index 1)."""

def build_insert_requests(markdown: str, index: int) -> list[dict]:
    """Requests for insert-from-markdown at a given index."""
```

Internal pipeline (three small helpers, mirroring Ruby structure):

1. `_parse_blocks(markdown: str) -> list[Block]` — line-oriented block parse: headings (`#`/`##`/`###`), paragraphs, bullet/numbered/checkbox lists, horizontal rules, tables.
2. `_inline_spans(text: str) -> list[Span]` — inline parse for `**bold**`, `*italic*`, `` `code` ``.
3. `_block_to_requests(block, base_index) -> (list[dict], new_index)` — emit `insertText`, `updateTextStyle`, `updateParagraphStyle`, `createParagraphBullets`, table, and horizontal-rule requests, tracking the running index.

Features supported (feature parity with current Ruby — no additions):
- Headings: `#`, `##`, `###` → HEADING_1/2/3
- Bold `**text**`, italic `*text*`
- Code `` `text` `` (Courier New, grey background)
- Bullet lists (`- `, `* `), numbered lists (`1. `)
- Checkboxes `- [ ]`, `- [x]`
- Horizontal rules (`---`)
- Tables with separator row (`| a | b |`)

Features explicitly not supported (unchanged from Ruby): nested lists, links, image markdown, code fences, blockquotes, strikethrough. Falls through as plain text or silently ignored.

### `gdocs_skill/docs.py` — `DocsClient`

```python
class DocsClient:
    def __init__(self, account: str = "default"):
        self._svc = build_docs_service(account)

    def read(self, document_id: str) -> dict: ...
    def structure(self, document_id: str) -> dict: ...
    def insert(self, document_id: str, text: str, index: int = 1) -> dict: ...
    def append(self, document_id: str, text: str) -> dict: ...
    def replace(self, document_id: str, find: str, replace: str, match_case: bool = False) -> dict: ...
    def format(self, document_id: str, start_index: int, end_index: int,
               bold=None, italic=None, underline=None) -> dict: ...
    def page_break(self, document_id: str, index: int) -> dict: ...
    def create(self, title: str, content: str | None = None) -> dict: ...
    def create_from_markdown(self, title: str, markdown: str) -> dict: ...
    def insert_from_markdown(self, document_id: str, markdown: str, index: int | None = None) -> dict: ...
    def delete(self, document_id: str, start_index: int, end_index: int) -> dict: ...
    def insert_image(self, document_id: str, image_url: str, index=None, width=None, height=None) -> dict: ...
    def insert_table(self, document_id: str, rows: int, cols: int, index=None, data=None) -> dict: ...
```

Each method returns the exact JSON shape the Ruby version returns. Markdown methods delegate to `gdocs_skill.markdown.build_*_requests()` then call `batchUpdate`. `append` reads the doc first to find end index. `replace` uses the `replaceAllText` request. `insert_image` and `insert_table` preserve all sizing/positioning rules from `SKILL.md` §8–9.

### `gdocs_skill/drive.py` — `DriveClient`

```python
class DriveClient:
    def __init__(self, account: str = "default"):
        self._svc = build_drive_service(account)

    def upload(self, file: str, name: str | None = None, folder_id: str | None = None) -> dict: ...
    def download(self, file_id: str, output: str, export_as: str | None = None) -> dict: ...
    def list_recent(self, max_results: int = 20) -> dict: ...
    def search(self, query: str, max_results: int = 50) -> dict: ...
    def share(self, file_id: str, email=None, role="reader", type="user", domain=None) -> dict: ...
    def create_folder(self, name: str, parent_id: str | None = None) -> dict: ...
    def move(self, file_id: str, folder_id: str) -> dict: ...
    def copy(self, file_id: str, name: str | None = None) -> dict: ...
    def update(self, file_id: str, file: str) -> dict: ...
    def delete(self, file_id: str) -> dict: ...
    def get_metadata(self, file_id: str) -> dict: ...
```

Thin wrappers. `export_as` on `download` uses `files.export` for Google-native formats (Docs→PDF etc.) and `files.get_media` for binaries, matching Ruby. Output dicts match the `{"status":"success","operation":"upload","file":{...}}` shape documented in `SKILL.md`.

### `gdocs_skill/cli.py`

Shared CLI plumbing and the two command dispatchers.

```python
EXIT_SUCCESS          = 0
EXIT_OPERATION_FAILED = 1
EXIT_AUTH_ERROR       = 2
EXIT_API_ERROR        = 3
EXIT_INVALID_ARGS     = 4

def read_json_stdin() -> dict: ...
def emit(data: dict) -> None: ...                      # json.dumps(indent=2) + print
def emit_error(code: str, message: str, **extra) -> None: ...
def require_fields(data: dict, *fields) -> None: ...   # exits EXIT_INVALID_ARGS on miss

def parse_account(argv: list[str]) -> tuple[str, list[str]]:
    """Strip --account <name> from argv. Returns (account, argv_without_flag).
    Precedence: --account flag > JSON "account" field (handled per-command) > GDOCS_ACCOUNT env > 'default'."""

def main_docs(argv: list[str]) -> int: ...             # dispatcher for docs_manager.py
def main_drive(argv: list[str]) -> int: ...            # dispatcher for drive_manager.py
```

Dispatchers use `match command:` statements with one arm per CLI command. Top-level `try/except` maps exceptions to the Ruby error shape:
- `google.auth.exceptions.RefreshError` / missing-creds → `AUTH_ERROR` + exit 2
- `googleapiclient.errors.HttpError` → `API_ERROR` + exit 3
- Any other exception → `OPERATION_FAILED` + exit 1
- Argument-validation failures → `INVALID_ARGS` + exit 4

### Entry scripts

`scripts/docs_manager.py` and `scripts/drive_manager.py` are ~10 lines each:

```python
#!/usr/bin/env -S uv run
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from gdocs_skill.cli import main_docs
sys.exit(main_docs(sys.argv[1:]))
```

Chmod'd executable. **Preferred invocation:** `scripts/docs_manager.py read <id>` (no `uv run` prefix) when the user's CWD is the skill root — `uv run` in the shebang resolves `pyproject.toml` by searching upward from CWD.

**Fallback invocation:** if `SKILL.md`'s invocations must work from arbitrary CWDs (e.g. Claude runs commands from the user's project dir, not the skill dir), the shebang-based approach is fragile. In that case we either (a) prefix every `SKILL.md` example with `uv run --project /absolute/path/to/skill`, or (b) drop the package layout back to PEP 723 inline deps in the entry scripts. Which applies is determined by empirical check during implementation (step 4 smoke-test). See Risks.

## CLI contract

Commands and JSON shapes are preserved exactly from Ruby. Two additions:

1. **`--account <name>` accepted on every command** (including positional-arg ones). Also accepted as `"account"` in JSON stdin for commands that read stdin. Also honours `GDOCS_ACCOUNT` env var.
2. **New `list-accounts` command** on both entry scripts: prints `{"status":"success","accounts":["default","work",...]}` by listing token files in `~/.claude/.google/`.

Precedence (highest wins): CLI flag > JSON field > env var > `"default"`.

## Multi-account examples

```bash
# First-time auth for a named account
scripts/docs_manager.py auth 4/ABC123... --account work

# Use a specific account for one command
scripts/docs_manager.py read <doc_id> --account work

# JSON-input commands can specify account in the body
echo '{"title":"X","account":"work"}' | scripts/docs_manager.py create

# Set default for the shell session
export GDOCS_ACCOUNT=work
scripts/docs_manager.py read <doc_id>    # uses 'work'

# List configured accounts
scripts/docs_manager.py list-accounts
```

## Testing

`tests/test_markdown.py` — pytest, ~12 cases asserting on returned request-list structure (not live docs):

1. Single H1
2. Single H2
3. Single H3
4. Paragraph with bold / italic / code / mixed inline
5. Bullet list (3 items)
6. Numbered list (3 items)
7. Checkbox unchecked and checked
8. Horizontal rule
9. 2×2 table
10. 3×2 table with header separator
11. Mixed integration case: H1 + paragraph + list + table
12. Empty input + index-arithmetic check (`build_insert_requests(md, 100)` is `build_create_requests(md)` shifted by 99)

Runs via `uv run pytest`. No mocking of Google API clients — the client modules are thin enough that their coverage comes from the E2E `skill-ci` workflow, not unit tests.

## CI

Current CI (`.github/workflows/ci.yml`) calls the reusable workflow at `robtaylor/skills/.github/workflows/skill-ci.yml@add-skill-ci`. Plan:

1. **Inspect** the reusable workflow to confirm it handles a `pyproject.toml`-only skill (Python path detection, `uv sync`, pytest run).
2. **If yes:** leave `ci.yml` unchanged; the workflow picks up the Python skill correctly.
3. **If no:** add a small local job before the reusable call that installs `uv`, runs `uv sync`, and runs `uv run pytest`. Leave the reusable workflow for the E2E test.

This verification is a prerequisite step in the implementation plan, not a post-hoc fix.

## Packaging

`pyproject.toml`:

```toml
[project]
name = "gdocs-skill"
version = "2.0.0"
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

`uv.lock` committed. No ruff/mypy in this port (explicit non-goal — can be added later as a focused PR).

## Docs updates

- **`SKILL.md`** — frontmatter `version: 2.0.0`; command examples `.rb` → `.py`; add setup step "Run `uv sync` in skill directory once after cloning" before auth setup; update Dependencies footer from Ruby gems to Python packages; add short "Multi-Account Support" section; new `2.0.0` entry in Version History summarising the port.
- **`README.md`** — "Quick Examples" `.rb` → `.py`; setup section updated; mention `uv`.
- **`CLAUDE.md`** — update "Dependencies (no Gemfile)" → `uv sync`; update line counts; update architecture section to reflect package layout.
- **`references/*.md`, `examples/sample_operations.md`** — grep for `.rb`, `ruby`, `gem`; update inline. Prose-only changes.

## Implementation order

The implementation plan (produced by the `writing-plans` skill next) will likely sequence as:

1. Add `pyproject.toml` and run `uv lock` (empty project, deps only).
2. Write `gdocs_skill/auth.py` including multi-account support; smoke-test against real auth.
3. Port the markdown parser + its tests. Offline and verifiable — do early.
4. Port `DocsClient` + `cli.py` docs dispatcher + `scripts/docs_manager.py` entry; smoke-test end-to-end against a test doc.
5. Port `DriveClient` + drive dispatcher + `scripts/drive_manager.py` entry; smoke-test against a test file.
6. Add `list-accounts` command.
7. Delete Ruby files.
8. Update `SKILL.md`, `README.md`, `CLAUDE.md`, references, examples.
9. Verify CI picks up the Python skill (see CI section); adjust if needed.
10. Commit `2.0.0` bump and new version-history entry.

## Non-goals

- Nested list support, markdown links, code fences, or any other parser feature not in the current Ruby implementation.
- CLI UX cleanup (underscore vs hyphen consistency, better `--help`, etc.) — tracked separately.
- Mocking-based tests for `DocsClient`/`DriveClient`.
- Linting/type-checking setup (ruff, mypy).
- Migrating Ruby token format. Users re-auth once; other Ruby Google skills' `token.json` is left untouched.

## Risks

- **CI reusable workflow compatibility.** Mitigated by step 9 in the implementation order: verify before relying on it.
- **Index-arithmetic parity in markdown parser.** The Ruby parser's exact output isn't fully specified in prose; during porting, reference Ruby output on a small set of inputs to pin behaviour before finalising tests. Mitigation: the markdown parser is ported early (step 3), so regressions are caught before any API client code lands.
- **`googleapiclient.errors.HttpError` shape vs Ruby `Google::Apis::ClientError` message text.** Error messages in the JSON output may differ verbatim even when the error conditions are identical. Acceptable — Claude reads `error_code` and `status`, not the free-text `message`.
- **Shebang-based `uv run` and CWD.** `#!/usr/bin/env -S uv run` resolves `pyproject.toml` by searching upward from the user's CWD, not from the script's location. If Claude invokes `/path/to/skill/scripts/docs_manager.py` from a CWD that has no ancestor `pyproject.toml`, `uv run` will fail or use the wrong project. Mitigation: verify invocation behaviour empirically in step 4. Fallbacks in order of preference: (a) document that commands run from the skill root (matches current Ruby skill norm); (b) prefix examples with `uv run --project <skill_path>`; (c) revert to PEP 723 inline deps in the entry scripts, duplicating dep list across two files.
