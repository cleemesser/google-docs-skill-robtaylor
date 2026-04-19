"""OAuth flow and credential storage for the gsuite CLI.

Supports multiple accounts via a per-account token file:
~/.claude/.google/token_gsuite_<account>.json
"""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/gmail.modify",
]

GOOGLE_DIR = Path.home() / ".claude" / ".google"
CREDENTIALS_PATH = GOOGLE_DIR / "client_secret.json"
TOKEN_PREFIX = "token_gsuite_"


class AuthRequiredError(Exception):
    """Raised when credentials are missing or can't be refreshed.

    `reason` distinguishes setup problems (no client_secret.json on disk)
    from authorization problems (token missing or not refreshable). The CLI
    layer uses it to emit the right remediation instructions.

    Unlike the previous OOB-based flow, there is no URL to display to the
    user — the `auth` CLI subcommand runs an interactive loopback flow via
    `run_local_server()`, which opens a browser and captures the redirect
    locally.
    """

    REASON_MISSING_CLIENT_SECRET = "missing_client_secret"
    REASON_MISSING_TOKEN = "missing_token"

    def __init__(
        self,
        message: str,
        reason: str,
        account: str | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.account = account


def token_path(account: str) -> Path:
    return GOOGLE_DIR / f"{TOKEN_PREFIX}{account}.json"


def _load_flow() -> InstalledAppFlow:
    if not CREDENTIALS_PATH.exists():
        raise AuthRequiredError(
            f"client_secret.json not found at {CREDENTIALS_PATH}",
            reason=AuthRequiredError.REASON_MISSING_CLIENT_SECRET,
        )
    return InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH), scopes=SCOPES
    )


def get_credentials(account: str = "default") -> Credentials:
    path = token_path(account)
    creds: Credentials | None = None
    if path.exists():
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json())
        return creds

    raise AuthRequiredError(
        f"No valid credentials for account '{account}'. "
        f"Run `gsuite auth --account {account}` to authorize.",
        reason=AuthRequiredError.REASON_MISSING_TOKEN,
        account=account,
    )


def complete_auth(account: str = "default") -> None:
    """Run the interactive OAuth loopback flow and persist the token.

    Opens the user's browser and starts a short-lived local HTTP server that
    captures the redirect from Google. Blocks until the user completes the
    flow in the browser. No authorization code needs to be pasted back.
    """
    flow = _load_flow()
    # port=0 asks the OS for a free port; google-auth-oauthlib wires the
    # redirect URI to http://localhost:<port>/ automatically.
    flow.run_local_server(port=0, open_browser=True, prompt="consent")
    GOOGLE_DIR.mkdir(parents=True, exist_ok=True)
    token_path(account).write_text(flow.credentials.to_json())


def build_docs_service(account: str = "default") -> Resource:
    return build(
        "docs", "v1", credentials=get_credentials(account), cache_discovery=False
    )


def build_drive_service(account: str = "default") -> Resource:
    return build(
        "drive", "v3", credentials=get_credentials(account), cache_discovery=False
    )


def list_accounts() -> list[str]:
    if not GOOGLE_DIR.exists():
        return []
    suffix = ".json"
    out = []
    for p in sorted(GOOGLE_DIR.iterdir()):
        name = p.name
        if name.startswith(TOKEN_PREFIX) and name.endswith(suffix):
            out.append(name[len(TOKEN_PREFIX) : -len(suffix)])
    return out
