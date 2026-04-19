#!/usr/bin/env bash
# Build a richly-formatted Google Doc from a Markdown string.
# Exercises every feature of the Markdown parser end-to-end:
# headings, bold/italic/code, bullet/numbered/checkbox lists, horizontal rule, table.
#
# Usage: examples/create_from_markdown.sh
#        (assumes default account; use examples/multi_account.sh for the multi-account pattern)

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

MARKDOWN='# Python Port Demo

## Formatting samples

Paragraph with **bold**, *italic*, and `inline code`.

## Lists

- bullet one
- bullet two
- bullet three

1. numbered one
2. numbered two

- [ ] unchecked item
- [x] checked item

---

## Table

| Metric | Q3 | Q4 |
|--------|----|----|
| Revenue | $1M | $1.25M |
| Users | 10K | 15K |
'

echo ">> Creating doc..."
RESPONSE=$(jq -n --arg title "Python Port Demo $(date +%Y-%m-%d-%H%M%S)" \
                 --arg markdown "$MARKDOWN" \
                 '{title: $title, markdown: $markdown}' \
            | scripts/docs_manager.py create-from-markdown)

echo "$RESPONSE"

DOC_ID=$(echo "$RESPONSE" | python -c 'import json,sys; print(json.load(sys.stdin)["document_id"])')

echo
echo ">> Done. Open the doc to verify rendering:"
echo "   https://docs.google.com/document/d/$DOC_ID/edit"
echo
echo ">> To clean up later:"
echo "   scripts/drive_manager.py delete --file-id $DOC_ID"
