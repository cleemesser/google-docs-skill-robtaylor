# gsuite — CLI + Claude Code skill for Google Workspace

A Python CLI (`gsuite`) for Google Docs and Drive operations (with room to grow into Calendar, Gmail, etc.), plus a Claude Code skill that documents the CLI so Claude knows how to call it. The CLI is useful standalone; the skill is just a thin documentation layer on top.

## Features

### Google Docs Operations
- Read document content and structure
- Create new documents
- Insert and append text
- Find and replace text
- Text formatting (bold, italic, underline)
- Insert page breaks and images
- Delete content ranges

### Google Drive Operations
- Upload and download files
- Search across Drive
- Create and list folders
- Share files and folders
- Move and organize files
- Export files to different formats (PDF, PNG, etc.)

## Installation

Two steps: install the CLI, then (optionally) register the Claude skill.

```bash
# 1. Clone somewhere you'll keep it long-term
git clone https://github.com/robtaylor/google-docs-skill.git ~/src/gsuite

# 2. Install the CLI with its own isolated venv (requires uv — https://docs.astral.sh/uv/)
uv tool install ~/src/gsuite
# Now `gsuite` is on PATH. Upgrades: uv tool upgrade gsuite

# 3. (Optional) Link the Claude Code skill
ln -s ~/src/gsuite ~/.claude/skills/google-docs
```

## Setup

1. **Google Cloud credentials** — follow [references/google_cloud_setup.md](references/google_cloud_setup.md) to create a project, enable the Docs and Drive APIs, and download an OAuth 2.0 Desktop client JSON as `~/.claude/.google/client_secret.json`.
2. **Authorize** — run `gsuite auth`. A browser window opens; grant access; the token is captured automatically at `~/.claude/.google/token_gsuite_default.json`. For a named account, pass `--account <name>`.

Once you've linked the skill directory into `~/.claude/skills/`, Claude Code discovers it on the next session and can call `gsuite` on your behalf.

## Usage

See [SKILL.md](SKILL.md) for complete documentation and examples.

### Quick Examples

```bash
# Read a document
gsuite docs read <document_id>

# Create a document
echo '{"title": "My Doc", "content": "Hello World"}' | gsuite docs create

# Upload a file to Drive
gsuite drive upload --file ./myfile.pdf --name "My PDF"

# Search Drive
gsuite drive search --query "name contains 'Report'"
```

## License

MIT License - see [LICENSE](LICENSE) for details.
