"""
Shared utilities for Amazon Ads API v3.
Used by sync_to_sheets.py, debug_api.py, and other scripts.
"""

import gzip
import io
import json
import time

import requests

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REPORTING_URL = "https://advertising-api.amazon.com/reporting/reports"
PROFILES_URL = "https://advertising-api.amazon.com/v2/profiles"

# Report type configs for each campaign type
REPORT_CONFIGS = {
    "SP": {
        "adProduct": "SPONSORED_PRODUCTS",
        "reportTypeId": "spCampaigns",
        "groupBy": ["campaign"],
        "columns": [
            "campaignName", "impressions", "clicks",
            "cost", "purchases7d", "sales7d",
        ],
    },
    "SB": {
        "adProduct": "SPONSORED_BRANDS",
        "reportTypeId": "sbCampaigns",
        "groupBy": ["campaign"],
        "columns": [
            "campaignName", "impressions", "clicks",
            "cost", "purchases7d", "sales7d",
        ],
    },
    "SD": {
        "adProduct": "SPONSORED_DISPLAY",
        "reportTypeId": "sdCampaigns",
        "groupBy": ["campaign"],
        "columns": [
            "campaignName", "impressions", "clicks",
            "cost", "purchases7d", "sales7d",
        ],
    },
}


def load_credentials(path="credentials.json"):
    """Load credentials from JSON file."""
    with open(path) as f:
        return json.load(f)


def refresh_access_token(client_id, client_secret, refresh_token):
    """Exchange a refresh token for a fresh access token. Returns the access token string."""
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_api_headers(access_token, client_id, profile_id):
    """Return the standard headers dict for Amazon Ads API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/vnd.createasyncreportrequest.v3+json",
    }


def create_report(headers, campaign_type, start_date, end_date):
    """
    Request an async report for the given campaign type (SP/SB/SD).
    Returns the report ID.
    """
    config = REPORT_CONFIGS[campaign_type]
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": config["adProduct"],
            "groupBy": config["groupBy"],
            "columns": config["columns"],
            "reportTypeId": config["reportTypeId"],
            "timeUnit": "SUMMARY",
            "format": "GZIP_JSON",
        },
    }
    resp = requests.post(REPORTING_URL, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()["reportId"]


def poll_report(headers, report_id, max_wait=300, interval=5):
    """
    Poll until the report is COMPLETED or FAILED.
    Returns the report status dict (contains 'url' when completed).
    """
    url = f"{REPORTING_URL}/{report_id}"
    # Use plain GET headers (no Content-Type needed for polling)
    poll_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(url, headers=poll_headers)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "COMPLETED":
            return data
        if status == "FAILED":
            raise RuntimeError(f"Report {report_id} failed: {data}")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Report {report_id} did not complete within {max_wait}s")


def download_report(download_url):
    """Download and decompress a GZIP_JSON report. Returns a list of dicts."""
    resp = requests.get(download_url)
    resp.raise_for_status()
    decompressed = gzip.decompress(resp.content)
    return json.loads(decompressed)


def fetch_campaigns(client_id, client_secret, refresh_token, profile_id, start_date, end_date):
    """
    High-level: fetch SP/SB/SD campaign data for one account.
    Returns dict like {"SP": [...], "SB": [...], "SD": [...]}.
    """
    access_token = refresh_access_token(client_id, client_secret, refresh_token)
    headers = get_api_headers(access_token, client_id, profile_id)
    results = {}
    for ctype in ("SP", "SB", "SD"):
        try:
            report_id = create_report(headers, ctype, start_date, end_date)
            report_data = poll_report(headers, report_id)
            rows = download_report(report_data["url"])
            results[ctype] = rows
        except Exception as e:
            print(f"  Warning: {ctype} report failed — {e}")
            results[ctype] = []
    return results
