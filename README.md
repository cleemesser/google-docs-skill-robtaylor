# Google Docs Skill for Claude Code

A Claude Code skill for managing Google Docs and Google Drive with comprehensive document and file operations.

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

Add this skill to your Claude Code configuration:

```bash
# Clone to your skills directory
git clone https://github.com/robtaylor/google-docs-skill.git ~/.claude/skills/google-docs

# Or add as submodule to your claude-config
cd ~/.claude
git submodule add https://github.com/robtaylor/google-docs-skill.git skills/google-docs
```

## Setup

1. **Install `uv`** — see https://docs.astral.sh/uv/ (required to run the Python entry scripts).
2. **Set up Google Cloud credentials** — follow [references/google_cloud_setup.md](references/google_cloud_setup.md) to create a project, enable the Docs and Drive APIs, and download an OAuth 2.0 Desktop client JSON as `~/.claude/.google/client_secret.json`.
3. **Install Python dependencies** — run `uv sync` in the skill directory.
4. **Authorize** — run `scripts/docs_manager.py auth`. A browser window opens; consent; token is captured automatically.

Tokens are stored per-account at `~/.claude/.google/token_python_<account>.json`.

## Usage

See [SKILL.md](SKILL.md) for complete documentation and examples.

### Quick Examples

```bash
# Read a document
scripts/docs_manager.py read <document_id>

# Create a document
echo '{"title": "My Doc", "content": "Hello World"}' | scripts/docs_manager.py create

# Upload a file to Drive
scripts/drive_manager.py upload --file ./myfile.pdf --name "My PDF"

# Search Drive
scripts/drive_manager.py search --query "name contains 'Report'"
```

## License

MIT License - see [LICENSE](LICENSE) for details.
