#!/usr/bin/env bash
# Demonstrate append, insert-from-markdown, replace, and structure against
# an existing Google Doc.
#
# Usage: examples/edit_existing_doc.sh <document_id>
#
# Tip: run examples/create_from_markdown.sh first to produce a doc to edit.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <document_id>" >&2
  exit 64
fi

DOC_ID="$1"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

echo ">> 1. Current structure (headings):"
gsuite docs structure "$DOC_ID"

echo
echo ">> 2. Appending a plain-text paragraph..."
jq -n --arg doc_id "$DOC_ID" \
      --arg text "\n\nPlain text appended by examples/edit_existing_doc.sh." \
      '{document_id: $doc_id, text: $text}' \
  | gsuite docs append

echo
echo ">> 3. Inserting a formatted Markdown section at end..."
jq -n --arg doc_id "$DOC_ID" \
      --arg md "\n\n## Appendix\n\nThis section has **bold** and *italic* text plus a list:\n\n- new item 1\n- new item 2" \
      '{document_id: $doc_id, markdown: $md}' \
  | gsuite docs insert-from-markdown

echo
echo ">> 4. Find-and-replace..."
jq -n --arg doc_id "$DOC_ID" \
      '{document_id: $doc_id, find: "bold", replace: "BOLD"}' \
  | gsuite docs replace

echo
echo ">> 5. Structure after edits:"
gsuite docs structure "$DOC_ID"

echo
echo ">> Open the doc to inspect: https://docs.google.com/document/d/$DOC_ID/edit"
