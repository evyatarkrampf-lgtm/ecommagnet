#!/usr/bin/env python3
"""
Quick campaign optimization report for an Amazon Ads account.

Usage:
    python3 optimize.py                    # list available accounts
    python3 optimize.py "URIEL MEDITEX"    # show report for one account

Reads ads_data.json (populated by sync_to_sheets.py) and prints a markdown
table with spend, sales, ACOS, ROAS, clicks, orders, plus flags for
over-spenders, zero-conversion campaigns, and inactive campaigns.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from optimize_session import generate_report, load_ads_data


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 optimize.py "ACCOUNT NAME"')
        print()
        try:
            data = load_ads_data()
            accounts = list(data.get("accounts", {}).keys())
            if accounts:
                print("Available accounts:")
                for a in accounts:
                    print(f"  - {a}")
            else:
                print("No accounts in ads_data.json. Run sync_to_sheets.py first.")
        except FileNotFoundError as e:
            print(str(e))
        sys.exit(1)

    account_name = " ".join(sys.argv[1:])
    try:
        print(generate_report(account_name))
    except (FileNotFoundError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
