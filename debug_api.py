#!/usr/bin/env python3
"""
Test whether an account's Amazon Ads token works.

Usage:
    python3 debug_api.py                    # tests the first account
    python3 debug_api.py "URIEL MEDITEX"    # tests a specific account

What it does:
  1. Refreshes the access token
  2. Calls GET /v2/profiles to verify API access
  3. Prints the HTTP status and raw response

If you see HTTP 200 → the token works, sync will succeed.
If you see HTTP 403 → re-authorize by running authorize_account.py.
"""

import json
import os
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from amazon_ads_api import load_credentials, refresh_access_token, PROFILES_URL


def main():
    creds_path = os.path.join(SCRIPT_DIR, "credentials.json")
    creds = load_credentials(creds_path)
    app = creds["app"]
    accounts = creds["accounts"]

    if not accounts:
        print("No accounts in credentials.json. Run authorize_account.py first.")
        sys.exit(1)

    # Pick account
    if len(sys.argv) > 1:
        account_name = sys.argv[1]
    else:
        account_name = next(iter(accounts))

    if account_name not in accounts:
        print(f"Account '{account_name}' not found. Available: {', '.join(accounts.keys())}")
        sys.exit(1)

    account = accounts[account_name]
    profile_id = account["profile_id_us"]
    print(f"Testing: {account_name} (profile_id: {profile_id})")
    print("=" * 50)

    # Step 1: Refresh token
    print("\n1. Refreshing access token...")
    try:
        access_token = refresh_access_token(
            app["client_id"], app["client_secret"], account["refresh_token"]
        )
        print(f"   ✅ Got access token: {access_token[:20]}...")
    except Exception as e:
        print(f"   ❌ Token refresh failed: {e}")
        sys.exit(1)

    # Step 2: Call profiles endpoint
    print("\n2. Calling GET /v2/profiles...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": app["client_id"],
    }
    resp = requests.get(PROFILES_URL, headers=headers)

    print(f"   HTTP {resp.status_code}")
    print(f"   Headers: {dict(resp.headers)}")
    print(f"\n   Response body:")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)

    # Verdict
    print("\n" + "=" * 50)
    if resp.status_code == 200:
        print("✅ SUCCESS — Token works. Sync should succeed.")
        profiles = resp.json()
        if profiles:
            print(f"   Found {len(profiles)} profile(s):")
            for p in profiles:
                print(f"   - {p.get('accountInfo', {}).get('name', 'N/A')} "
                      f"(profileId: {p.get('profileId')}, marketplace: {p.get('countryCode')})")
    elif resp.status_code == 403:
        print("❌ FAILED (403) — Token is invalid or expired.")
        print("   Fix: Run 'python3 authorize_account.py' and log in with the client's Amazon account.")
    else:
        print(f"❌ FAILED (HTTP {resp.status_code}) — Unexpected error.")
        print("   Check the response above for details.")


if __name__ == "__main__":
    main()
