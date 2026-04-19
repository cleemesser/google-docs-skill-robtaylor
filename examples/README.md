# Examples

Runnable shell scripts that exercise the `gsuite docs` and `gsuite drive` CLIs end-to-end. Each script is self-contained, chdir's to the skill root on its own, and prints the JSON responses as it goes so you can see what's happening.

**Prerequisites**:
- Auth is set up for at least the `default` account (see `../references/google_cloud_setup.md`).
- `jq` and `python3` on your PATH (used to construct and parse JSON safely without shell-escaping pitfalls).

## Scripts

| Script | What it does |
|---|---|
| [`create_from_markdown.sh`](create_from_markdown.sh) | Builds a richly-formatted Google Doc from a Markdown string. Prints the document URL. Exercises the Markdown parser end-to-end: headings, bold/italic/code, lists, checkboxes, horizontal rule, table. |
| [`edit_existing_doc.sh <doc_id>`](edit_existing_doc.sh) | Takes a Google Doc ID. Demonstrates append, insert-from-markdown, replace, and structure against an existing doc. |
| [`drive_roundtrip.sh`](drive_roundtrip.sh) | Creates a local file, uploads it, searches for it, downloads it back, diffs it, then cleans up. End-to-end Drive sanity check. |
| [`multi_account.sh`](multi_account.sh) | Lists configured accounts and runs `drive list --max-results 3` against each one. Useful for verifying `--account` routes to a different token. |

## See also

- [`sample_operations.md`](sample_operations.md) — a reference doc of individual commands and their JSON shapes (non-executable; paste snippets as needed).
