"""
Shared Google OAuth handling for Calendar + Classroom.

First run: opens a browser window so you can log in and grant access.
After that: reuses/refreshes the cached token.json automatically -
no browser needed on future runs (which matters since this runs
unattended in the background).
"""
import os

# Google's OAuth server sometimes returns a slightly different (but harmless,
# superset) scope list than requested - e.g. bundling in
# classroom.student-submissions.me.readonly alongside classroom.coursework.me.readonly.
# Without this, google-auth-oauthlib raises "Scope has changed" and aborts.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import Config


def get_google_credentials() -> Credentials:
    creds = None

    if os.path.exists(Config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            Config.GOOGLE_TOKEN_FILE, Config.GOOGLE_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                Config.GOOGLE_CREDENTIALS_FILE, Config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(Config.GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds
