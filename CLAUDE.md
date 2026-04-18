# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This repository **is itself a Claude Code skill** — not an application that uses one. The artifact consumed by Claude Code is `SKILL.md` at the root (with YAML frontmatter including `name`, `description`, `version`). Installation is by cloning into `~/.claude/skills/google-docs`. When editing this repo you are editing the skill's surface area.

Primary behavior: two Ruby CLIs — `scripts/docs_manager.rb` and `scripts/drive_manager.rb` — that wrap the Google Docs and Drive APIs and are invoked by Claude through shell commands documented in `SKILL.md`.

## Architecture

Two monolithic Ruby scripts, each ~class + `case command` dispatcher at the bottom:

- `scripts/docs_manager.rb` (~1550 lines): `DocsManager` class. Commands: `auth`, `read`, `structure`, `insert`, `append`, `replace`, `format`, `page-break`, `create`, `create-from-markdown`, `insert`-`from-markdown`, `delete`, `insert-image`, `insert-table`.
- `scripts/drive_manager.rb` (~900 lines): Drive file operations (upload, download, search, list, share, move, copy, delete, folders, metadata).

CLI conventions (shared across both):
- Simple commands take **positional args** (e.g. `read <document_id>`).
- Complex commands take **JSON on stdin** (piped via `echo '{...}' | ...`).
- All commands emit **JSON on stdout** with `status: 'success'|'error'` and operation-specific fields.
- Exit codes: `0` success, `1` operation failed, `2` auth error, `3` API error, `4` invalid args.

**Adding a new command** requires three coordinated edits: (1) a new `def` on the class, (2) a `when '<name>'` branch in the bottom-of-file dispatcher, and (3) documentation in `SKILL.md` (plus the relevant reference file under `references/`). The `valid_commands` array in the `else` branch of the dispatcher must also be updated.

**Markdown → Google Docs pipeline** (in `docs_manager.rb`): `parse_markdown` → `process_inline_formatting` → `build_format_request` emit Google Docs `batchUpdate` requests. This is a bespoke parser, not a library call — changes to Markdown support happen here.

## Authentication

OAuth credentials live at `~/.claude/.google/client_secret.json` (user-provided) and `~/.claude/.google/token.json` (generated). The token is **shared across all Google skills** (Docs, Drive, Sheets, Calendar, Contacts, Gmail) — both scripts request the full scope superset. If you change scopes in one script, update the other to match or re-auth will silently drop the dropped scope.

Tokens auto-refresh on expiry. If refresh fails the script prints an auth URL and exits with code 2; complete auth with `scripts/docs_manager.rb auth <code>`.

## Development

**Dependencies (no Gemfile — installed globally):**
```
gem install google-apis-docs_v1 google-apis-drive_v3 google-apis-sheets_v4 \
            google-apis-calendar_v3 google-apis-people_v1 googleauth
```

**Running a command locally:**
```bash
scripts/docs_manager.rb read <document_id>
echo '{"title":"Test","markdown":"# Hi"}' | scripts/docs_manager.rb create-from-markdown
```

**Tests:** There is no in-repo test suite. CI runs the reusable workflow `robtaylor/skills/.github/workflows/skill-ci.yml@add-skill-ci` (a fork of `anthropics/skills` pending PR #136) with `run_api_test: true` and `run_claude_code_test: true`. This invokes the skill end-to-end against the real APIs using secrets inherited from the repo — there are no unit tests to run individually.

## Versioning

When adding or changing behavior, update **both**:
1. `version` in `SKILL.md` frontmatter (semver).
2. The `## Version History` section at the bottom of `SKILL.md` with a new entry.

Also reflect capability changes in the `key_capabilities` and `when_to_use` frontmatter fields — these drive skill discovery.

## Documentation structure

- `SKILL.md` — primary skill doc, read by Claude when the skill is invoked. Keep command examples executable and in sync with the dispatcher.
- `references/` — deeper docs loaded on demand: `docs_operations.md`, `formatting_guide.md`, `integration-patterns.md`, `troubleshooting.md`, `cli-patterns.md`.
- `examples/sample_operations.md` — workflow recipes.
- `README.md` — public GitHub-facing overview; keep brief and link to `SKILL.md` for detail.
