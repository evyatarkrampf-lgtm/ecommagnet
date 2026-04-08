#!/usr/bin/env python3
"""
Authorize a new Amazon Ads client account.

Usage:
    python3 authorize_account.py

Workflow:
  1. Enter the client name and their Amazon Ads profile ID
  2. Browser opens for Amazon OAuth login (use the CLIENT's Amazon account)
  3. After login, the refresh token is saved to credentials.json

Prerequisite: http://localhost:9999 must be in your Amazon developer app's
Allowed Return URLs.
"""

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
AUTH_URL = "https://www.amazon.com/ap/oa"
REDIRECT_URI = "http://localhost:9999"

# Will be set by the callback handler
authorization_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth redirect on localhost:9999."""

    def do_GET(self):
        global authorization_code
        query = parse_qs(urlparse(self.path).query)

        if "code" in query:
            authorization_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
        else:
            error = query.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Authorization failed: {error}</h1>".encode())

    def log_message(self, format, *args):
        pass  # Suppress request logging


def load_credentials():
    if os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH) as f:
            return json.load(f)
    return {"app": {"client_id": "", "client_secret": ""}, "accounts": {}}


def save_credentials(creds):
    with open(CREDENTIALS_PATH, "w") as f:
        json.dump(creds, f, indent=2)
    print(f"Saved to {CREDENTIALS_PATH}")


def main():
    creds = load_credentials()
    client_id = creds["app"]["client_id"]
    client_secret = creds["app"]["client_secret"]

    if not client_id or not client_secret:
        print("Error: app client_id and client_secret must be set in credentials.json")
        sys.exit(1)

    print("=== Authorize New Amazon Ads Account ===\n")
    account_name = input("Client name (e.g. URIEL MEDITEX): ").strip()
    if not account_name:
        print("Error: client name cannot be empty")
        sys.exit(1)

    profile_id = input("Amazon Ads Profile ID (US): ").strip()
    if not profile_id:
        print("Error: profile ID cannot be empty")
        sys.exit(1)

    # Build the OAuth URL
    auth_params = (
        f"?client_id={client_id}"
        f"&scope=advertising::campaign_management"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
    )
    auth_url = AUTH_URL + auth_params

    print(f"\nOpening browser for authorization...")
    print(f"IMPORTANT: Log in with {account_name}'s Amazon account (not yours).\n")
    webbrowser.open(auth_url)

    # Start local server to capture the redirect
    server = HTTPServer(("localhost", 9999), OAuthCallbackHandler)
    print("Waiting for authorization callback on localhost:9999...")
    server.handle_request()  # Handle one request then stop

    if not authorization_code:
        print("Error: did not receive authorization code")
        sys.exit(1)

    print("Got authorization code. Exchanging for refresh token...")

    # Exchange authorization code for tokens
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
    })

    if resp.status_code != 200:
        print(f"Token exchange failed (HTTP {resp.status_code}):")
        print(resp.text)
        sys.exit(1)

    tokens = resp.json()
    refresh_token = tokens["refresh_token"]

    # Save to credentials
    from datetime import datetime
    creds["accounts"][account_name] = {
        "profile_id_us": profile_id,
        "refresh_token": refresh_token,
        "note": f"Authorized {datetime.now().strftime('%B %d %Y')}",
    }
    save_credentials(creds)

    print(f"\n✅ {account_name} authorized successfully!")
    print(f"   Profile ID: {profile_id}")
    print(f"   Refresh token saved to credentials.json")


if __name__ == "__main__":
    main()
