#!/usr/bin/env bash
# List every configured account, then run `drive list --max-results 3` against
# each one. Verifies that --account actually routes to different tokens and
# returns different data.
#
# Usage: examples/multi_account.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

echo ">> Configured accounts:"
ACCOUNTS_JSON=$(scripts/docs_manager.py list-accounts)
echo "$ACCOUNTS_JSON"

ACCOUNTS=$(echo "$ACCOUNTS_JSON" | python -c '
import json, sys
for a in json.load(sys.stdin)["accounts"]:
    print(a)
')

if [[ -z "$ACCOUNTS" ]]; then
  echo "No accounts configured. Run: scripts/docs_manager.py auth [--account <name>]" >&2
  exit 1
fi

while IFS= read -r account; do
  echo
  echo ">> Account '$account' — first 3 Drive files:"
  scripts/drive_manager.py list --max-results 3 --account "$account" \
    | python -c '
import json, sys
r = json.load(sys.stdin)
print(f"  {r[\"count\"]} files")
for f in r["files"]:
    print(f"  - {f[\"name\"]} ({f[\"mime_type\"]})")
'
done <<< "$ACCOUNTS"
