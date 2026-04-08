#!/usr/bin/env python3
"""
Nightly sync: fetch Amazon Ads campaign data → Google Sheets + ads_data.json.

For each authorized account in credentials.json:
  1. Fetch SP/SB/SD campaign reports via Amazon Ads Reporting API v3
  2. Write to a per-account Google Spreadsheet (one tab per campaign type)
  3. Save all data locally to ads_data.json

Usage:
    python3 sync_to_sheets.py

Dependencies: requests, gspread, google-auth
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials as ServiceCredentials

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from amazon_ads_api import load_credentials, fetch_campaigns

# Paths
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")
GOOGLE_CREDS_PATH = os.path.join(SCRIPT_DIR, "google_credentials.json")
ADS_DATA_PATH = os.path.join(SCRIPT_DIR, "ads_data.json")
LOG_PATH = os.path.join(SCRIPT_DIR, "sync.log")

# Google Sheets scope
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers for the spreadsheet
SHEET_HEADERS = ["Campaign", "Impressions", "Clicks", "Cost", "Orders (7d)", "Sales (7d)"]

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def get_google_sheets_client():
    """Authenticate with Google Sheets using service account."""
    if not os.path.exists(GOOGLE_CREDS_PATH):
        log.warning(f"Google credentials not found at {GOOGLE_CREDS_PATH} — skipping Sheets sync")
        return None
    creds = ServiceCredentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_spreadsheet(gc, spreadsheet_name):
    """Open an existing spreadsheet or create a new one."""
    try:
        return gc.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        log.info(f"  Creating new spreadsheet: {spreadsheet_name}")
        return gc.create(spreadsheet_name)


def write_to_sheet(spreadsheet, tab_name, rows):
    """Write campaign data to a specific tab in the spreadsheet."""
    # Get or create the worksheet
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=len(rows) + 1, cols=len(SHEET_HEADERS))

    # Build the data grid
    data = [SHEET_HEADERS]
    for row in rows:
        data.append([
            row.get("campaignName", ""),
            row.get("impressions", 0),
            row.get("clicks", 0),
            round(row.get("cost", 0.0), 2),
            row.get("purchases7d", 0),
            round(row.get("sales7d", 0.0), 2),
        ])

    worksheet.update(range_name="A1", values=data)
    log.info(f"    {tab_name}: {len(rows)} campaigns written")


def sync_account(app_creds, account_name, account_info, gc, start_date, end_date):
    """Sync one account: fetch data + write to Sheets. Returns campaign dict."""
    log.info(f"Syncing: {account_name}")

    # Fetch from Amazon Ads API
    campaigns = fetch_campaigns(
        client_id=app_creds["client_id"],
        client_secret=app_creds["client_secret"],
        refresh_token=account_info["refresh_token"],
        profile_id=account_info["profile_id_us"],
        start_date=start_date,
        end_date=end_date,
    )

    total = sum(len(v) for v in campaigns.values())
    log.info(f"  Fetched {total} campaigns (SP:{len(campaigns['SP'])} SB:{len(campaigns['SB'])} SD:{len(campaigns['SD'])})")

    # Write to Google Sheets (if available)
    if gc:
        spreadsheet_name = f"Ecommagnet - {account_name}"
        spreadsheet = get_or_create_spreadsheet(gc, spreadsheet_name)
        for ctype in ("SP", "SB", "SD"):
            write_to_sheet(spreadsheet, ctype, campaigns[ctype])

    return campaigns


def main():
    log.info("=" * 60)
    log.info("Ecommagnet Ads Sync — starting")

    # Load credentials
    creds = load_credentials(CREDENTIALS_PATH)
    app_creds = creds["app"]
    accounts = creds["accounts"]

    if not accounts:
        log.error("No accounts in credentials.json. Run authorize_account.py first.")
        sys.exit(1)

    # Date range: last 30 days
    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    log.info(f"Period: {start_date} to {end_date}")

    # Google Sheets client (optional — sync still saves locally even without it)
    gc = get_google_sheets_client()

    # Sync each account
    all_data = {}
    for account_name, account_info in accounts.items():
        try:
            campaigns = sync_account(app_creds, account_name, account_info, gc, start_date, end_date)
            all_data[account_name] = campaigns
        except Exception as e:
            log.error(f"  FAILED: {account_name} — {e}")
            all_data[account_name] = {}

    # Save to ads_data.json
    output = {
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period": {"start": start_date, "end": end_date},
        "accounts": all_data,
    }
    with open(ADS_DATA_PATH, "w") as f:
        json.dump(output, f, indent=2)
    log.info(f"Saved to {ADS_DATA_PATH}")

    log.info("Sync complete.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
