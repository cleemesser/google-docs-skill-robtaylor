"""Shared CLI plumbing for docs_manager and drive_manager entry scripts."""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from googleapiclient.errors import HttpError

from .auth import CREDENTIALS_PATH, AuthRequiredError, complete_auth, list_accounts

EXIT_SUCCESS = 0
EXIT_OPERATION_FAILED = 1
EXIT_AUTH_ERROR = 2
EXIT_API_ERROR = 3
EXIT_INVALID_ARGS = 4


def emit(data: dict) -> None:
    print(json.dumps(data, indent=2))


def emit_error(code: str, message: str, **extra: Any) -> None:
    payload: dict[str, Any] = {"status": "error", "error_code": code, "message": message}
    payload.update(extra)
    emit(payload)


def read_json_stdin() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        emit_error("INVALID_JSON", f"Failed to parse JSON stdin: {e}")
        sys.exit(EXIT_INVALID_ARGS)


def require_fields(data: dict, *fields: str, operation: str | None = None) -> None:
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        msg = f"Required fields: {', '.join(fields)}"
        extra = {"operation": operation} if operation else {}
        emit_error("MISSING_REQUIRED_FIELDS", msg, **extra)
        sys.exit(EXIT_INVALID_ARGS)


def pop_account(argv: list[str]) -> tuple[str | None, list[str]]:
    """Strip --account <name> from argv. Returns (account_or_None, remaining_argv)."""
    out = []
    account: str | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--account" and i + 1 < len(argv):
            account = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return account, out


def resolve_account(flag_account: str | None, body: dict | None = None) -> str:
    if flag_account:
        return flag_account
    if body and isinstance(body.get("account"), str) and body["account"]:
        return body["account"]
    env = os.environ.get("GDOCS_ACCOUNT")
    if env:
        return env
    return "default"


def handle_auth_required(e: AuthRequiredError, operation: str) -> None:
    extra: dict[str, Any] = {"operation": operation}
    if e.reason == AuthRequiredError.REASON_MISSING_CLIENT_SECRET:
        extra["instructions"] = [
            "1. Create Google Cloud OAuth 2.0 client credentials (Desktop app type).",
            f"2. Save the downloaded JSON at {CREDENTIALS_PATH}.",
            "3. Re-run the command.",
        ]
        emit_error("AUTH_REQUIRED", str(e), **extra)
        return
    if e.account is not None:
        extra["account"] = e.account
    extra["instructions"] = [
        (
            f"Run: scripts/<script>.py auth --account {e.account}"
            if e.account
            else "Run: scripts/<script>.py auth [--account <name>]"
        ),
        "A browser window will open for you to authorize the skill.",
    ]
    emit_error("AUTH_REQUIRED", str(e), **extra)


def handle_http_error(e: HttpError, operation: str) -> None:
    emit_error("API_ERROR", f"Google API error: {e}", operation=operation)


def run_safely(operation: str, fn) -> None:
    """Invoke fn() and handle exceptions by emitting error JSON + sys.exit."""
    try:
        fn()
    except AuthRequiredError as e:
        handle_auth_required(e, operation)
        sys.exit(EXIT_AUTH_ERROR)
    except HttpError as e:
        handle_http_error(e, operation)
        sys.exit(EXIT_API_ERROR)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        emit_error("OPERATION_FAILED", f"Failed to {operation}: {e}", operation=operation)
        sys.exit(EXIT_OPERATION_FAILED)


def emit_list_accounts() -> None:
    emit({"status": "success", "operation": "list_accounts", "accounts": list_accounts()})


def do_auth(argv: list[str], operation: str = "auth") -> int:
    account, remaining = pop_account(argv)
    # The loopback flow takes no positional args; ignore any extras rather
    # than erroring so users migrating from the old OOB `auth <code>` form
    # don't get a confusing failure on their first attempt.
    del remaining
    try:
        complete_auth(account or "default")
    except AuthRequiredError as e:
        handle_auth_required(e, operation)
        return EXIT_AUTH_ERROR
    except Exception as e:  # noqa: BLE001
        emit_error("AUTH_FAILED", f"Authorization failed: {e}", operation=operation)
        return EXIT_AUTH_ERROR
    emit({"status": "success", "operation": "auth", "account": account or "default"})
    return EXIT_SUCCESS


def main_docs(argv: list[str]) -> int:
    if not argv:
        emit_error("MISSING_COMMAND", "Usage: docs_manager.py <command> [...]")
        return EXIT_INVALID_ARGS

    if argv[0] == "auth":
        return do_auth(argv[1:], operation="auth")

    if argv[0] == "list-accounts":
        emit_list_accounts()
        return EXIT_SUCCESS

    flag_account, remaining = pop_account(argv)
    if not remaining:
        emit_error("MISSING_COMMAND", "Usage: docs_manager.py <command> [...]")
        return EXIT_INVALID_ARGS
    command = remaining[0]

    stdin_commands = {
        "insert",
        "append",
        "replace",
        "format",
        "page-break",
        "create",
        "create-from-markdown",
        "insert-from-markdown",
        "delete",
        "insert-image",
        "insert-table",
    }
    positional_commands = {"read", "structure"}
    all_commands = stdin_commands | positional_commands

    if command not in all_commands:
        emit_error(
            "INVALID_COMMAND",
            f"Unknown command: {command}",
            valid_commands=sorted(all_commands | {"auth", "list-accounts"}),
        )
        return EXIT_INVALID_ARGS

    body: dict | None = None
    if command in stdin_commands:
        body = read_json_stdin()

    account = resolve_account(flag_account, body)

    def run():
        from .docs import DocsClient

        client = DocsClient(account=account)
        match command:
            case "read":
                if len(remaining) < 2:
                    emit_error(
                        "MISSING_DOCUMENT_ID",
                        "Document ID required",
                        operation="read",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.read(remaining[1]))
            case "structure":
                if len(remaining) < 2:
                    emit_error(
                        "MISSING_DOCUMENT_ID",
                        "Document ID required",
                        operation="structure",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.structure(remaining[1]))
            case "insert":
                require_fields(body, "document_id", "text", operation="insert")
                emit(
                    client.insert(
                        body["document_id"], body["text"], body.get("index", 1)
                    )
                )
            case "append":
                require_fields(body, "document_id", "text", operation="append")
                emit(client.append(body["document_id"], body["text"]))
            case "replace":
                require_fields(
                    body, "document_id", "find", "replace", operation="replace"
                )
                emit(
                    client.replace(
                        body["document_id"],
                        body["find"],
                        body["replace"],
                        body.get("match_case", False),
                    )
                )
            case "format":
                require_fields(
                    body,
                    "document_id",
                    "start_index",
                    "end_index",
                    operation="format",
                )
                emit(
                    client.format(
                        body["document_id"],
                        body["start_index"],
                        body["end_index"],
                        body.get("bold"),
                        body.get("italic"),
                        body.get("underline"),
                    )
                )
            case "page-break":
                require_fields(
                    body, "document_id", "index", operation="page_break"
                )
                emit(client.page_break(body["document_id"], body["index"]))
            case "create":
                require_fields(body, "title", operation="create")
                emit(client.create(body["title"], body.get("content")))
            case "create-from-markdown":
                require_fields(
                    body, "title", "markdown", operation="create_from_markdown"
                )
                emit(client.create_from_markdown(body["title"], body["markdown"]))
            case "insert-from-markdown":
                require_fields(
                    body,
                    "document_id",
                    "markdown",
                    operation="insert_from_markdown",
                )
                emit(
                    client.insert_from_markdown(
                        body["document_id"], body["markdown"], body.get("index")
                    )
                )
            case "delete":
                require_fields(
                    body,
                    "document_id",
                    "start_index",
                    "end_index",
                    operation="delete",
                )
                emit(
                    client.delete(
                        body["document_id"],
                        body["start_index"],
                        body["end_index"],
                    )
                )
            case "insert-image":
                require_fields(
                    body, "document_id", "image_url", operation="insert_image"
                )
                emit(
                    client.insert_image(
                        body["document_id"],
                        body["image_url"],
                        body.get("index"),
                        body.get("width"),
                        body.get("height"),
                    )
                )
            case "insert-table":
                require_fields(
                    body, "document_id", "rows", "cols", operation="insert_table"
                )
                emit(
                    client.insert_table(
                        body["document_id"],
                        body["rows"],
                        body["cols"],
                        body.get("index"),
                        body.get("data"),
                    )
                )
            case _:
                # Unreachable: guarded by all_commands check above.
                raise AssertionError(f"unhandled command: {command}")

    run_safely(command, run)
    return EXIT_SUCCESS


def _parse_drive_flags(argv: list[str]) -> dict:
    """Parse --flag-style args used by drive_manager (mirrors Ruby parse_args)."""
    out: dict = {}
    i = 0
    mapping = {
        "--file": "file",
        "--file-id": "file_id",
        "--folder-id": "folder_id",
        "--parent-id": "parent_id",
        "--output": "output",
        "--name": "name",
        "--query": "query",
        "--email": "email",
        "--role": "role",
        "--type": "type",
        "--mime-type": "mime_type",
        "--domain": "domain",
        "--export-as": "export_as",
    }
    while i < len(argv):
        tok = argv[i]
        if tok in mapping and i + 1 < len(argv):
            out[mapping[tok]] = argv[i + 1]
            i += 2
            continue
        if tok == "--max-results" and i + 1 < len(argv):
            out["max_results"] = int(argv[i + 1])
            i += 2
            continue
        if tok == "--permanent":
            out["permanent"] = True
            i += 1
            continue
        i += 1
    return out


def main_drive(argv: list[str]) -> int:
    if not argv:
        emit_error("MISSING_COMMAND", "Usage: drive_manager.py <command> [...]")
        return EXIT_INVALID_ARGS

    if argv[0] == "auth":
        return do_auth(argv[1:], operation="auth")

    if argv[0] == "list-accounts":
        emit_list_accounts()
        return EXIT_SUCCESS

    flag_account, remaining = pop_account(argv)
    if not remaining:
        emit_error("MISSING_COMMAND", "Usage: drive_manager.py <command> [...]")
        return EXIT_INVALID_ARGS
    command = remaining[0]

    valid_commands = {
        "upload",
        "download",
        "list",
        "search",
        "get-metadata",
        "create-folder",
        "move",
        "share",
        "delete",
        "copy",
        "update",
    }
    if command not in valid_commands:
        emit_error(
            "UNKNOWN_COMMAND",
            f"Unknown command: {command}",
            valid_commands=sorted(valid_commands | {"auth", "list-accounts"}),
        )
        return EXIT_INVALID_ARGS

    opts = _parse_drive_flags(remaining[1:])
    account = resolve_account(flag_account)

    def run():
        from .drive import DriveClient

        client = DriveClient(account=account)
        match command:
            case "upload":
                if not opts.get("file"):
                    emit_error(
                        "MISSING_FILE",
                        "File path required: --file <path>",
                        operation="upload",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.upload(
                        opts["file"],
                        opts.get("name"),
                        opts.get("folder_id"),
                        opts.get("mime_type"),
                    )
                )
            case "download":
                if not (opts.get("file_id") and opts.get("output")):
                    emit_error(
                        "MISSING_ARGS",
                        "--file-id and --output required",
                        operation="download",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.download(
                        opts["file_id"], opts["output"], opts.get("export_as")
                    )
                )
            case "list":
                emit(
                    client.list_files(
                        opts.get("folder_id"), opts.get("max_results", 100)
                    )
                )
            case "search":
                if not opts.get("query"):
                    emit_error(
                        "MISSING_QUERY",
                        "--query required",
                        operation="search",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.search(opts["query"], opts.get("max_results", 100)))
            case "get-metadata":
                if not opts.get("file_id"):
                    emit_error(
                        "MISSING_FILE_ID",
                        "--file-id required",
                        operation="get_metadata",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.get_metadata(opts["file_id"]))
            case "create-folder":
                if not opts.get("name"):
                    emit_error(
                        "MISSING_NAME",
                        "--name required",
                        operation="create_folder",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.create_folder(
                        opts["name"],
                        opts.get("parent_id") or opts.get("folder_id"),
                    )
                )
            case "move":
                if not (opts.get("file_id") and opts.get("folder_id")):
                    emit_error(
                        "MISSING_ARGS",
                        "--file-id and --folder-id required",
                        operation="move",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.move(opts["file_id"], opts["folder_id"]))
            case "share":
                if not opts.get("file_id"):
                    emit_error(
                        "MISSING_FILE_ID",
                        "--file-id required",
                        operation="share",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.share(
                        opts["file_id"],
                        opts.get("email"),
                        opts.get("role", "reader"),
                        opts.get("type"),
                        opts.get("domain"),
                    )
                )
            case "delete":
                if not opts.get("file_id"):
                    emit_error(
                        "MISSING_FILE_ID",
                        "--file-id required",
                        operation="delete",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(client.delete(opts["file_id"], opts.get("permanent", False)))
            case "copy":
                if not opts.get("file_id"):
                    emit_error(
                        "MISSING_FILE_ID",
                        "--file-id required",
                        operation="copy",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.copy(
                        opts["file_id"], opts.get("name"), opts.get("folder_id")
                    )
                )
            case "update":
                if not (opts.get("file_id") and opts.get("file")):
                    emit_error(
                        "MISSING_ARGS",
                        "--file-id and --file required",
                        operation="update",
                    )
                    sys.exit(EXIT_INVALID_ARGS)
                emit(
                    client.update(
                        opts["file_id"], opts["file"], opts.get("name")
                    )
                )
            case _:
                raise AssertionError(f"unhandled command: {command}")

    run_safely(command, run)
    return EXIT_SUCCESS
