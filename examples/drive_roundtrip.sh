#!/usr/bin/env bash
# End-to-end Drive sanity check: create a local file, upload, search, download,
# diff the result, then delete from Drive.
#
# Usage: examples/drive_roundtrip.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

NAME="drive-roundtrip-$(date +%s).txt"
LOCAL_PATH="$WORKDIR/$NAME"
RETURNED_PATH="$WORKDIR/returned-$NAME"

printf 'Hello from %s\nLine 2\nLine 3\n' "$(date)" > "$LOCAL_PATH"

echo ">> 1. Uploading $LOCAL_PATH as '$NAME'..."
UPLOAD=$(gsuite drive upload --file "$LOCAL_PATH")
echo "$UPLOAD"
FILE_ID=$(echo "$UPLOAD" | python -c 'import json,sys; print(json.load(sys.stdin)["file"]["id"])')

echo
echo ">> 2. Searching by name..."
gsuite drive search --query "name = '$NAME'"

echo
echo ">> 3. Downloading back to $RETURNED_PATH..."
gsuite drive download --file-id "$FILE_ID" --output "$RETURNED_PATH"

echo
echo ">> 4. Diffing original vs downloaded..."
if diff -q "$LOCAL_PATH" "$RETURNED_PATH"; then
  echo "   ✓ files match"
else
  echo "   ✗ files DIFFER" >&2
  exit 1
fi

echo
echo ">> 5. Deleting from Drive (moves to trash)..."
gsuite drive delete --file-id "$FILE_ID"

echo
echo ">> Round-trip complete."
