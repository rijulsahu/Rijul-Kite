# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv"]
# ///
"""Kite Connect authentication and session-caching module.

Handles the full OAuth-style login flow for Zerodha Kite Connect:
opens a browser to the Kite login URL, captures the ``request_token``
via a local HTTP callback server, exchanges it for an ``access_token``,
and caches the token in ``.kite_session.json`` for reuse.

Cached tokens are considered valid until 6 AM IST on the day following
their generation, matching Kite's server-side expiry schedule.  On next
run the module checks the cache first and skips the browser login when a
valid token exists.

Usage::

    from api_setup_auth import kite
    holdings = kite.holdings()

Security notes:
    - Credentials are loaded from a ``.env`` file via ``python-dotenv``
      and must never be hard-coded or committed.
    - The session file is written atomically and restricted to the current
      OS user (``icacls`` on Windows, ``chmod 600`` on POSIX).

Author: Rijul Sahu
Portfolio: https://rijul.cloud
"""
import getpass
import logging
import os
import json
import tempfile
import webbrowser
from datetime import datetime, time, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import sys
import subprocess

load_dotenv()
logging.basicConfig(level=logging.WARNING)

_api_key = os.getenv("KITE_API_KEY")
_api_secret = os.getenv("KITE_API_SECRET")
if not _api_key or not _api_secret:
    raise EnvironmentError("KITE_API_KEY and KITE_API_SECRET must be set in .env")

SESSION_FILE = os.path.join(os.path.dirname(__file__), ".kite_session.json")
REDIRECT_PORT = 8000

# Kite tokens expire at 6 AM IST each day
def _get_cached_token():
    """Return a cached Kite access token if one exists and has not expired.

    Reads ``.kite_session.json`` from the module directory and returns the
    stored ``access_token`` string when it is still valid.  A token is
    considered valid as long as the current time is before 6 AM IST on the
    calendar day following the day the token was saved.

    Returns:
        str | None: The cached access token, or ``None`` if no valid cache
        exists or the cache cannot be read.
    """
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            session = json.load(f)
        saved_at = datetime.fromisoformat(session["saved_at"])
        now = datetime.now()
        # Token expires at next 6 AM after generation
        if saved_at.hour < 6:
            expiry = datetime.combine(saved_at.date(), time(6, 0))
        else:
            expiry = datetime.combine(saved_at.date() + timedelta(days=1), time(6, 0))
        if now < expiry:
            return session["access_token"]
    except Exception:
        pass
    return None

def _save_token(access_token):
    """Persist a Kite access token to disk with restrictive OS permissions.

    Writes ``access_token`` and the current ISO timestamp to
    ``.kite_session.json`` using an atomic write (temp-file + rename) to
    avoid partial reads.  The file is restricted to the current OS user
    via ``icacls`` on Windows or ``chmod 600`` on POSIX before the rename.

    Args:
        access_token (str): The Kite Connect access token to cache.

    Raises:
        subprocess.CalledProcessError: If the Windows ``icacls`` permission
            command fails.
        OSError: If the file cannot be written or renamed.
    """
    payload = json.dumps({"access_token": access_token, "saved_at": datetime.now().isoformat()})
    dir_ = os.path.dirname(SESSION_FILE)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix=".kite_session_tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        # Apply restrictive permissions before moving into place
        if sys.platform == "win32":
            username = getpass.getuser()
            subprocess.run(
                ["icacls", tmp_path, "/inheritance:r", "/grant:r", f"{username}:F"],
                check=True, capture_output=True
            )
        else:
            os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, SESSION_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

_request_token_holder = [None]

class _KiteCallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the Kite OAuth request token.

    Kite Connect redirects the browser to the configured redirect URI after
    a successful login.  The redirect URL includes ``?request_token=<token>``
    as a query parameter.  This handler extracts that token and stores it in
    ``_request_token_holder[0]``, then returns a simple HTML confirmation
    page so the user knows they can close the browser tab.

    HTTP server logs are suppressed to keep console output clean.
    """

    def do_GET(self):
        """Handle GET requests and extract the ``request_token`` query parameter."""
        params = parse_qs(urlparse(self.path).query)
        if "request_token" in params:
            _request_token_holder[0] = params["request_token"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Authenticated! You can close this tab.</h2></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
    def log_message(self, *args):
        """Suppress default HTTP server access log output."""
        pass  # Suppress HTTP server logs

def _capture_request_token(login_url, timeout=120):
    """Open the Kite login URL and wait for the OAuth callback request token.

    Starts a local ``HTTPServer`` on ``127.0.0.1:REDIRECT_PORT``, opens the
    ``login_url`` in the default system browser, then polls for incoming
    requests until either the ``request_token`` is captured or the timeout
    elapses.

    Args:
        login_url (str): The Kite Connect login URL returned by
            ``KiteConnect.login_url()``.
        timeout (int): Maximum seconds to wait for the callback.  Defaults
            to 120 seconds.

    Returns:
        str | None: The captured ``request_token`` string, or ``None`` if
        the timeout was reached without receiving a valid callback.
    """
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _KiteCallbackHandler)
    server.timeout = 5  # Poll interval; outer loop enforces total timeout
    webbrowser.open(login_url)
    print("Browser opened — please log in to Kite...")
    deadline = datetime.now() + timedelta(seconds=timeout)
    while datetime.now() < deadline:
        server.handle_request()
        if _request_token_holder[0]:
            break
    server.server_close()
    return _request_token_holder[0]

def get_kite():
    """Return an authenticated ``KiteConnect`` instance.

    Checks the on-disk session cache first.  When a valid token exists the
    function sets it on the client and returns immediately, avoiding a
    browser login.  Otherwise it launches the full OAuth flow:

    1. Opens the Kite login URL in the default browser.
    2. Waits for the OAuth callback via the local HTTP server.
    3. Exchanges the ``request_token`` for an ``access_token``.
    4. Caches the token to ``.kite_session.json``.

    Returns:
        KiteConnect: A fully authenticated Kite Connect client ready for
        API calls.

    Raises:
        RuntimeError: If the browser login times out or the request token
            is not captured within the timeout window.
        EnvironmentError: If ``KITE_API_KEY`` or ``KITE_API_SECRET`` are
            not set (raised at module import time).
    """
    kite = KiteConnect(api_key=_api_key)

    cached = _get_cached_token()
    if cached:
        print("Using cached session token.")
        kite.set_access_token(cached)
        return kite

    request_token = _capture_request_token(kite.login_url())
    if not request_token:
        raise RuntimeError("Failed to capture request token — login timed out or was cancelled.")

    data = kite.generate_session(request_token, api_secret=_api_secret)
    access_token = data["access_token"]
    _save_token(access_token)
    kite.set_access_token(access_token)
    print("Authentication successful.")
    return kite

kite = get_kite()
