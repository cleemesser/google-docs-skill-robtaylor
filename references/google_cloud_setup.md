# Google Cloud Project Setup

One-time setup to create the OAuth 2.0 client credentials this skill needs. After completing these steps you'll have a `client_secret.json` file to place at `~/.claude/.google/client_secret.json`.

## 1. Create or pick a project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Project selector (top of page) → **New Project**. Name it whatever — it's only visible to you. An existing project works too.
3. Make sure the selector shows the project you want to use for the next steps.

## 2. Enable the APIs

**APIs & Services → Library**, then enable each of these:

- **Google Docs API**
- **Google Drive API**

Optional — only needed if you plan to use sibling skills with the same token:

- Google Sheets API
- Google Calendar API
- People API (Contacts)
- Gmail API

The skill requests scopes for all six so one token can serve any Python Google skill in this family. If you skip an API, commands against that service will fail with a `PERMISSION_DENIED` error, but anything you *did* enable continues to work.

## 3. Configure the OAuth consent screen

**APIs & Services → OAuth consent screen**.

1. **User Type**: `External` (unless your Google account is part of a Workspace domain, in which case `Internal` is simpler — see [Refresh token expiry](#refresh-token-expiry) below).
2. **App information**: any app name and your own email are fine.
3. **Scopes**: leave blank. You don't need to pre-declare scopes; they're requested at auth time.
4. **Test users**: add the Google account(s) you plan to authenticate with. For External user type, only listed test users can complete the auth flow while the app is in "Testing" status.
5. Save.

## 4. Create the OAuth client

**APIs & Services → Credentials → Create Credentials → OAuth client ID**.

1. **Application type**: `Desktop app`. (Not "Web application" — Desktop app is the right type for CLI tools and supports the loopback redirect flow this skill uses.)
2. **Name**: anything; only visible to you.
3. Click **Create**.

## 5. Download the JSON

In the dialog that appears (or from the Credentials list), **Download JSON**. You'll get a file named something like `client_secret_<long-id>.apps.googleusercontent.com.json`.

Move and rename it:

```bash
mkdir -p ~/.claude/.google
mv ~/Downloads/client_secret_*.apps.googleusercontent.com.json \
   ~/.claude/.google/client_secret.json
```

That's it — run `gsuite docs auth` and a browser will open for the consent flow.

## Refresh token expiry

Google's current policy for OAuth apps:

- **Internal** (Workspace-only): refresh tokens are long-lived. No verification required. Simplest option, but only available if your Google account is part of a Google Workspace domain.
- **External, Testing status**: refresh tokens **expire after 7 days**. You'll need to re-run `auth` weekly. This is fine for personal use and doesn't require Google to verify your app.
- **External, In production status**: refresh tokens are long-lived, but because this skill requests Drive/Docs (sensitive) and Gmail (restricted) scopes, Google requires you to go through their app verification process — a form, a YouTube demo video, and a response wait of days to weeks. Worth it if you use the skill daily; overkill if you don't mind re-authing occasionally.

**Practical recommendation:** keep the app in Testing status unless weekly re-auth is annoying enough to justify the verification paperwork.

## Sanity-check your setup

```bash
ls -l ~/.claude/.google/client_secret.json
```

Should exist and be readable. Then:

```bash
gsuite docs auth
```

Browser opens, you grant access, the script writes `~/.claude/.google/token_gsuite_default.json`, and exits with `status: success`. You're done.
