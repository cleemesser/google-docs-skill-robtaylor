# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two things in one repo:

1. **A Python CLI tool**, `gsuite`, that wraps Google Workspace APIs (currently Docs + Drive; room to grow into Calendar, Gmail, etc.). Installable via `uv tool install .` — produces a `gsuite` binary on PATH with its own isolated venv.
2. **A Claude Code skill** (`SKILL.md` + `references/` + `examples/`) that documents the CLI so Claude invokes it correctly. Installed by linking this directory into `~/.claude/skills/google-docs`.

The skill files are just docs around an independently-installable tool. Claude discovers the skill from `~/.claude/skills/` and reads `SKILL.md`; when it needs to run a command it calls `gsuite <group> <cmd>` assuming the CLI is on PATH.

## Architecture

Flat Python package at the repo root:

- `gsuite/auth.py` — OAuth flow. Per-account tokens at `~/.claude/.google/token_gsuite_<account>.json`. Raises `AuthRequiredError` with distinct `reason` values (`missing_client_secret` vs `missing_token`) so the CLI layer can emit the right remediation instructions.
- `gsuite/markdown.py` — pure Markdown → `Parsed(text, formats, tables)` parser and `build_format_request`. Offline-testable; covered by `tests/test_markdown.py` (~15 cases).
- `gsuite/docs.py` — `DocsClient` wrapping `googleapiclient` for Docs operations. One method per CLI command. Markdown methods orchestrate three `batchUpdate` calls (text, formats in reverse, tables in reverse) to preserve insertion indices.
- `gsuite/drive.py` — `DriveClient` for Drive operations. One method per CLI command.
- `gsuite/cli.py` — top-level `main(argv)` dispatcher plus per-group `main_docs` / `main_drive`. Shared helpers (`emit`, `read_json_stdin`, `pop_account`, `resolve_account`, `run_safely`).

CLI conventions:
- `gsuite auth [--account <name>]` — interactive browser loopback OAuth.
- `gsuite list-accounts` — lists configured accounts (reads `~/.claude/.google/token_gsuite_*.json`).
- `gsuite docs <cmd>` — docs commands. Simple commands take positional args (`read <id>`, `structure <id>`); mutating commands take JSON on stdin.
- `gsuite drive <cmd>` — drive commands. All take `--flag-style` args (`--file-id`, `--output`, etc.).
- Both groups emit JSON on stdout with `status: 'success'|'error'` and operation-specific fields.
- Exit codes: `0` success, `1` operation failed, `2` auth error, `3` API error, `4` invalid args.
- `--account <name>` accepted on every command. Precedence: flag > JSON `account` field (stdin-based docs commands only) > `GSUITE_ACCOUNT` env > `"default"`.

**Adding a new command** touches three places: (1) a method on `DocsClient` or `DriveClient`, (2) a `match` arm in the corresponding dispatcher in `cli.py` plus the `valid_commands` set used for early rejection, (3) documentation in `SKILL.md` and the relevant reference file under `references/`.

**Markdown → Google Docs pipeline** (in `markdown.py`): `parse()` → `_parse_blocks` / `_process_inline` → `build_format_request()` emit Google Docs `batchUpdate` requests. This is a bespoke parser, not a library call — changes to Markdown support happen here. Bullets, numbered items, and checkboxes are rendered as literal text prefixes (`• `, `N. `, `☐ `, `☑ `), not as `createParagraphBullets` API calls, matching the shipped Ruby-era behaviour.

## Authentication

OAuth client credentials at `~/.claude/.google/client_secret.json` (user-provided — see `references/google_cloud_setup.md`). Per-account tokens at `~/.claude/.google/token_gsuite_<account>.json` (generated, native `google-auth` JSON format).

Tokens auto-refresh on expiry. If refresh fails or no token exists for the requested account, `get_credentials` raises `AuthRequiredError`; the CLI dispatcher emits a JSON error with code `AUTH_REQUIRED` and exits with code 2. Authorize with `gsuite auth [--account <name>]` — the CLI runs `InstalledAppFlow.run_local_server()` which opens the user's browser and captures the redirect on a short-lived local HTTP server (no code paste, no deprecated OOB flow).

The full Google scope superset (Docs, Drive, Sheets, Calendar, Contacts, Gmail) is requested so a single token works for any Python Google skill in this family.

**Account labels are local-only.** The `<account>` component of the filename is not communicated to Google — it's just how the tool picks which token file to load. The Google identity bound to a token is decided by which account the user selected in the browser consent window during `auth`. Two implications that show up in user-reported issues:
1. To authenticate a *second* Google identity, the user must pick a different account in the browser (account switcher or incognito window); passing `--account new` alone doesn't force a fresh identity.
2. Two differently-named token files can end up bound to the same Google identity if the user consented as the same person twice. There's no detection of this — if a bug report says "both my accounts return the same data", check this first.

**Tokens are portable.** Token files are ordinary JSON; copying `token_gsuite_<name>.json` between machines (with the same `client_secret.json`) gives the same account access on the new machine. Refresh tokens are long-lived per Google's OAuth policy. `list_accounts()` enumerates whatever files happen to be in `GOOGLE_DIR` — so "removing an account" is literally `rm`, and revocation on Google's side (e.g. lost/stolen token file) must be done at https://myaccount.google.com/permissions.

## Development

**Dependencies:** managed via `uv` + `pyproject.toml`. Two distinct install paths:

- **For development** (working on this repo): `uv sync` creates `.venv/` and installs the package in editable mode. Use `uv run gsuite <cmd>` or activate the venv.
- **For use** (installing the CLI system-wide): `uv tool install .` gives the tool its own isolated venv and puts `gsuite` on PATH.

**Running a command locally during development:**
```bash
uv run gsuite docs read <document_id>
echo '{"title":"Test","markdown":"# Hi"}' | uv run gsuite docs create-from-markdown
```

**Tests:** `uv run pytest` runs the markdown parser tests in `tests/test_markdown.py`. The API-touching code in `docs.py` / `drive.py` is covered only by the end-to-end skill-ci workflow — there are no mocking-based unit tests.

**CI:** reusable workflow at `robtaylor/skills/.github/workflows/skill-ci.yml@add-skill-ci` (a fork of `anthropics/skills` pending PR #136) with `run_api_test: true` and `run_claude_code_test: true`. A local `pytest` job runs before the reusable workflow.

## Versioning

When adding or changing behavior, update **both**:
1. `version` in `pyproject.toml` (this is the canonical version) and `version` in `SKILL.md` frontmatter.
2. The `## Version History` section at the bottom of `SKILL.md` with a new entry.

Also reflect capability changes in the `key_capabilities` and `when_to_use` frontmatter fields — these drive skill discovery.

## Documentation structure

- `SKILL.md` — primary skill doc, read by Claude when the skill is invoked. Keep command examples executable and in sync with the dispatcher.
- `references/` — deeper docs loaded on demand: `google_cloud_setup.md`, `docs_operations.md`, `formatting_guide.md`, `integration-patterns.md`, `troubleshooting.md`, `cli-patterns.md`.
- `examples/` — runnable shell scripts (`create_from_markdown.sh`, `edit_existing_doc.sh`, `drive_roundtrip.sh`, `multi_account.sh`) and a reference doc (`sample_operations.md`).
- `README.md` — public GitHub-facing overview; keep brief and link to `SKILL.md` for detail.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` — design specs and implementation plans from the Superpowers brainstorming/writing-plans workflow. Not loaded by the skill at runtime.
