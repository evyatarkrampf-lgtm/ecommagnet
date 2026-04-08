#!/usr/bin/env python3
"""
Install a nightly cron job to run sync_to_sheets.py at 6:00 AM.

Usage:
    python3 setup_cron.py          # install the cron job
    python3 setup_cron.py --remove # remove the cron job

The cron entry runs sync_to_sheets.py and appends output to sync.log.
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_SCRIPT = os.path.join(SCRIPT_DIR, "sync_to_sheets.py")
LOG_FILE = os.path.join(SCRIPT_DIR, "sync.log")
CRON_MARKER = "# ecommagnet-sync"


def get_cron_line():
    return f"0 6 * * * /usr/bin/python3 {SYNC_SCRIPT} >> {LOG_FILE} 2>&1 {CRON_MARKER}"


def get_current_crontab():
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return ""


def install():
    current = get_current_crontab()

    # Check if already installed
    if CRON_MARKER in current:
        print("Cron job already installed. Use --remove to remove it first.")
        print(f"Current entry: {get_cron_line()}")
        return

    new_crontab = current.rstrip("\n") + "\n" + get_cron_line() + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        print("✅ Cron job installed successfully!")
        print(f"   Schedule: Every day at 6:00 AM")
        print(f"   Script:   {SYNC_SCRIPT}")
        print(f"   Log:      {LOG_FILE}")
    else:
        print(f"❌ Failed to install cron job: {proc.stderr}")
        sys.exit(1)


def remove():
    current = get_current_crontab()
    if CRON_MARKER not in current:
        print("No ecommagnet cron job found.")
        return

    lines = [line for line in current.splitlines() if CRON_MARKER not in line]
    new_crontab = "\n".join(lines) + "\n" if lines else ""
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        print("✅ Cron job removed.")
    else:
        print(f"❌ Failed to remove cron job: {proc.stderr}")
        sys.exit(1)


def main():
    if "--remove" in sys.argv:
        remove()
    else:
        install()


if __name__ == "__main__":
    main()
