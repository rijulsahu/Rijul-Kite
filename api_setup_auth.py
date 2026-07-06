# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv"]
# ///
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
    def do_GET(self):
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
        pass  # Suppress HTTP server logs

def _capture_request_token(login_url, timeout=120):
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
