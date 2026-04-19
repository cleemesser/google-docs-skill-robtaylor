# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This repository **is itself a Claude Code skill** — not an application that uses one. The artifact consumed by Claude Code is `SKILL.md` at the root (with YAML frontmatter including `name`, `description`, `version`). Installation is by cloning into `~/.claude/skills/google-docs`. When editing this repo you are editing the skill's surface area.

Primary behavior: a small Python package at `scripts/gdocs_skill/` with two thin entry scripts — `scripts/docs_manager.py` and `scripts/drive_manager.py` — that wrap the Google Docs and Drive APIs and are invoked by Claude through shell commands documented in `SKILL.md`.

## Architecture

Python package + thin entry scripts:

- `scripts/gdocs_skill/auth.py` — OAuth flow, multi-account tokens at `~/.claude/.google/token_python_<account>.json`. Raises `AuthRequiredError` with an auth URL when credentials are missing.
- `scripts/gdocs_skill/markdown.py` — pure Markdown → `Parsed(text, formats, tables)` parser and `build_format_request`. Offline-testable; covered by `tests/test_markdown.py`.
- `scripts/gdocs_skill/docs.py` — `DocsClient` wrapping `googleapiclient` for Docs operations. One method per CLI command. Markdown methods orchestrate three `batchUpdate` calls (text, formats in reverse, tables in reverse) to preserve insertion indices — matching the Ruby ordering.
- `scripts/gdocs_skill/drive.py` — `DriveClient` for Drive operations. One method per CLI command.
- `scripts/gdocs_skill/cli.py` — shared helpers (`emit`, `read_json_stdin`, `pop_account`, `resolve_account`, `run_safely`) and the two command dispatchers (`main_docs`, `main_drive`).
- `scripts/docs_manager.py`, `scripts/drive_manager.py` — thin executable entry scripts (shebang `#!/usr/bin/env -S uv run`) that import the dispatchers.

CLI conventions (preserved from the previous Ruby version):
- `docs_manager.py`: simple commands take **positional args** (`read <id>`); mutating commands take **JSON on stdin**.
- `drive_manager.py`: every command takes `--flag-style` args.
- Both emit **JSON on stdout** with `status: 'success'|'error'` and operation-specific fields.
- Exit codes: `0` success, `1` operation failed, `2` auth error, `3` API error, `4` invalid args.
- All commands accept `--account <name>` to target a specific Google account. Precedence: flag > JSON `account` field > `GDOCS_ACCOUNT` env > `"default"`.

**Adding a new command** touches three places: (1) a method on `DocsClient` or `DriveClient`, (2) a `match` arm in the corresponding dispatcher in `cli.py` (plus the `valid_commands` set used for early rejection), (3) documentation in `SKILL.md` and the relevant reference file under `references/`.

**Markdown → Google Docs pipeline** (in `markdown.py`): `parse()` → `_parse_blocks`/`_process_inline` → `build_format_request()` emit Google Docs `batchUpdate` requests. This is a bespoke parser, not a library call — changes to Markdown support happen here. Bullets, numbered items, and checkboxes are rendered as literal text prefixes (`• `, `N. `, `☐ `, `☑ `), not as `createParagraphBullets` API calls, matching the shipped behaviour.

## Authentication

OAuth client credentials at `~/.claude/.google/client_secret.json` (user-provided). Per-account tokens at `~/.claude/.google/token_python_<account>.json` (generated, native `google-auth` JSON format).

Tokens auto-refresh on expiry. If refresh fails or no token exists for the requested account, `get_credentials` raises `AuthRequiredError`; the CLI dispatcher emits a JSON error with code `AUTH_REQUIRED` and exits with code 2. Authorize with `scripts/docs_manager.py auth [--account <name>]` — the script runs `InstalledAppFlow.run_local_server()` which opens the user's browser and captures the redirect on a short-lived local HTTP server (no code paste, no deprecated OOB flow).

The full Google scope superset (Docs, Drive, Sheets, Calendar, Contacts, Gmail) is requested so a single token works for any Python Google skill in this family. Any existing Ruby-format `~/.claude/.google/token.json` from the previous version is left untouched.

## Development

**Dependencies:** managed via `uv` + `pyproject.toml`. After cloning, run `uv sync` in the skill directory to create `.venv/` and install runtime + dev deps.

**Running a command locally:**
```bash
scripts/docs_manager.py read <document_id>
echo '{"title":"Test","markdown":"# Hi"}' | scripts/docs_manager.py create-from-markdown
```

**Tests:** `uv run pytest` runs the markdown parser tests in `tests/test_markdown.py` (~15 cases). The API-touching code in `docs.py`/`drive.py` is covered only by the end-to-end skill-ci workflow — there are no mocking-based unit tests.

**CI:** reusable workflow at `robtaylor/skills/.github/workflows/skill-ci.yml@add-skill-ci` (a fork of `anthropics/skills` pending PR #136) with `run_api_test: true` and `run_claude_code_test: true`.

## Versioning

When adding or changing behavior, update **both**:
1. `version` in `SKILL.md` frontmatter (semver) and `version` in `pyproject.toml`.
2. The `## Version History` section at the bottom of `SKILL.md` with a new entry.

Also reflect capability changes in the `key_capabilities` and `when_to_use` frontmatter fields — these drive skill discovery.

## Documentation structure

- `SKILL.md` — primary skill doc, read by Claude when the skill is invoked. Keep command examples executable and in sync with the dispatchers.
- `references/` — deeper docs loaded on demand: `docs_operations.md`, `formatting_guide.md`, `integration-patterns.md`, `troubleshooting.md`, `cli-patterns.md`.
- `examples/sample_operations.md` — workflow recipes.
- `README.md` — public GitHub-facing overview; keep brief and link to `SKILL.md` for detail.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` — design specs and implementation plans from the Superpowers brainstorming/writing-plans workflow. Not loaded by the skill at runtime.
