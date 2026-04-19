"""OAuth flow and credential storage for the gdocs skill.

Supports multiple accounts via a per-account token file:
~/.claude/.google/token_python_<account>.json
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
OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_PREFIX = "token_python_"


class AuthRequiredError(Exception):
    """Raised when credentials are missing or can't be refreshed."""

    def __init__(self, message: str, auth_url: str | None = None):
        super().__init__(message)
        self.auth_url = auth_url


def token_path(account: str) -> Path:
    return GOOGLE_DIR / f"{TOKEN_PREFIX}{account}.json"


def _load_flow() -> InstalledAppFlow:
    if not CREDENTIALS_PATH.exists():
        raise AuthRequiredError(
            f"client_secret.json not found at {CREDENTIALS_PATH}"
        )
    return InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH), scopes=SCOPES, redirect_uri=OOB_REDIRECT
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

    flow = _load_flow()
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    raise AuthRequiredError(
        "Authorization required. Visit the URL and complete the flow.",
        auth_url=auth_url,
    )


def complete_auth(code: str, account: str = "default") -> None:
    flow = _load_flow()
    flow.fetch_token(code=code)
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
