"""
Optimize session helpers — read ads_data.json, compute metrics, and format
a campaign report for a single account.

Used by:
  - optimize.py (CLI wrapper)
  - the assistant directly (imported and called in a chat session)

Design:
  - Pure functions, no global state.
  - No external dependencies beyond stdlib.
  - All paths default to the script's directory so it works from cron or any cwd.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ADS_DATA = os.path.join(SCRIPT_DIR, "ads_data.json")
DEFAULT_CREDENTIALS = os.path.join(SCRIPT_DIR, "credentials.json")

DEFAULT_TARGET_ACOS = 25.0
NOCV_CLICKS_THRESHOLD = 10

# Flag priority order for sorting (lower index = shown first)
FLAG_PRIORITY = {"OVER": 0, "NOCV": 1, "OFF": 2}


def load_ads_data(path=None):
    """Load ads_data.json. Raises FileNotFoundError if sync has never run."""
    path = path or DEFAULT_ADS_DATA
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run 'python3 sync_to_sheets.py' first."
        )
    with open(path) as f:
        return json.load(f)


def load_account_config(account_name, path=None):
    """
    Return the account's entry from credentials.json.
    Case-insensitive match on account name.
    Raises KeyError with the list of available accounts if not found.
    """
    path = path or DEFAULT_CREDENTIALS
    with open(path) as f:
        creds = json.load(f)
    accounts = creds.get("accounts", {})

    # Case-insensitive lookup
    target = account_name.strip().lower()
    for name, info in accounts.items():
        if name.lower() == target:
            return name, info

    available = ", ".join(accounts.keys()) or "(none)"
    raise KeyError(
        f"Account '{account_name}' not found. Available: {available}"
    )


def get_target_acos(account_config, default=DEFAULT_TARGET_ACOS):
    """Return target_acos from config, or default if missing."""
    value = account_config.get("target_acos")
    if value is None:
        print(
            f"Warning: target_acos not set for this account. Using default {default}%.",
            file=sys.stderr,
        )
        return default
    return float(value)


def calculate_metrics(row):
    """
    Compute ACOS, ROAS, CTR for a single campaign row.
    Returns None for each metric when its denominator is zero.
    """
    impressions = row.get("impressions", 0) or 0
    clicks = row.get("clicks", 0) or 0
    cost = row.get("cost", 0.0) or 0.0
    sales = row.get("sales7d", 0.0) or 0.0

    acos = (cost / sales * 100) if sales > 0 else None
    roas = (sales / cost) if cost > 0 else None
    ctr = (clicks / impressions * 100) if impressions > 0 else None
    return {"acos": acos, "roas": roas, "ctr": ctr}


def get_flags(row, metrics, target_acos):
    """
    Return a list of flag strings for the campaign.
    OFF   — impressions == 0 or cost == 0 (dead campaign)
    NOCV  — clicks >= 10 and orders == 0 (traffic, no conversion)
    OVER  — ACOS > target_acos (over-spender)
    """
    flags = []
    impressions = row.get("impressions", 0) or 0
    cost = row.get("cost", 0.0) or 0.0
    clicks = row.get("clicks", 0) or 0
    orders = row.get("purchases7d", 0) or 0

    if impressions == 0 or cost == 0:
        flags.append("OFF")
    else:
        if clicks >= NOCV_CLICKS_THRESHOLD and orders == 0:
            flags.append("NOCV")
        if metrics["acos"] is not None and metrics["acos"] > target_acos:
            flags.append("OVER")
    return flags


def build_enriched_rows(account_data, target_acos):
    """
    Flatten SP/SB/SD campaign lists into one list of enriched rows.
    Each enriched row has: type, campaignName, impressions, clicks, cost,
    orders, sales, acos, roas, ctr, flags.
    """
    enriched = []
    for campaign_type in ("SP", "SB", "SD"):
        rows = account_data.get(campaign_type, []) or []
        for row in rows:
            metrics = calculate_metrics(row)
            flags = get_flags(row, metrics, target_acos)
            enriched.append({
                "type": campaign_type,
                "campaignName": row.get("campaignName", ""),
                "impressions": row.get("impressions", 0) or 0,
                "clicks": row.get("clicks", 0) or 0,
                "cost": row.get("cost", 0.0) or 0.0,
                "orders": row.get("purchases7d", 0) or 0,
                "sales": row.get("sales7d", 0.0) or 0.0,
                "acos": metrics["acos"],
                "roas": metrics["roas"],
                "ctr": metrics["ctr"],
                "flags": flags,
            })
    return enriched


def _sort_key(row):
    """Sort flagged campaigns first (OVER → NOCV → OFF), then healthy by spend desc."""
    if row["flags"]:
        best = min(FLAG_PRIORITY.get(f, 99) for f in row["flags"])
        return (0, best, -row["cost"])
    return (1, 0, -row["cost"])


def _fmt_money(v):
    return f"${v:,.2f}"


def _fmt_pct(v):
    return f"{v:.1f}%" if v is not None else "-"


def _fmt_roas(v):
    return f"{v:.2f}x" if v is not None else "-"


def format_markdown_report(account_name, enriched_rows, target_acos, period, synced_at):
    """Return the full markdown report as a single string."""
    lines = []
    lines.append(f"# {account_name} — Optimization Report")
    lines.append("")
    start = period.get("start") or "?"
    end = period.get("end") or "?"
    lines.append(f"**Period:** {start} to {end}")
    lines.append(f"**Last synced:** {synced_at or 'never'}")
    lines.append(f"**Target ACOS:** {target_acos:.1f}%")
    lines.append("")
    lines.append("## Campaigns")
    lines.append("")

    if not enriched_rows:
        lines.append("_No campaigns found for this account. Run sync_to_sheets.py._")
        return "\n".join(lines)

    headers = ["Flags", "Campaign", "Type", "Spend", "Sales",
               "ACOS%", "ROAS", "Clicks", "Orders"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    # Sort: flagged first, then by spend
    sorted_rows = sorted(enriched_rows, key=_sort_key)

    total_spend = 0.0
    total_sales = 0.0
    flag_counts = {"OVER": 0, "NOCV": 0, "OFF": 0}

    for row in sorted_rows:
        flag_str = ",".join(row["flags"]) if row["flags"] else ""
        lines.append("| " + " | ".join([
            flag_str,
            row["campaignName"],
            row["type"],
            _fmt_money(row["cost"]),
            _fmt_money(row["sales"]),
            _fmt_pct(row["acos"]),
            _fmt_roas(row["roas"]),
            str(row["clicks"]),
            str(row["orders"]),
        ]) + " |")
        total_spend += row["cost"]
        total_sales += row["sales"]
        for f in row["flags"]:
            if f in flag_counts:
                flag_counts[f] += 1

    # Summary
    blended_acos = (total_spend / total_sales * 100) if total_sales > 0 else None
    total_flagged = sum(1 for r in sorted_rows if r["flags"])

    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total spend: {_fmt_money(total_spend)}")
    lines.append(f"- Total sales: {_fmt_money(total_sales)}")
    lines.append(f"- Blended ACOS: {_fmt_pct(blended_acos)}")
    lines.append(
        f"- Flagged: {total_flagged} "
        f"(OVER: {flag_counts['OVER']}, "
        f"NOCV: {flag_counts['NOCV']}, "
        f"OFF: {flag_counts['OFF']})"
    )
    return "\n".join(lines)


def generate_report(account_name, ads_data_path=None, creds_path=None):
    """
    Top-level entry point. Loads data, computes metrics, returns markdown report.
    Raises FileNotFoundError or KeyError with clear messages on failure.
    """
    ads_data = load_ads_data(ads_data_path)
    resolved_name, account_config = load_account_config(account_name, creds_path)
    target_acos = get_target_acos(account_config)

    account_data = ads_data.get("accounts", {}).get(resolved_name, {})
    enriched = build_enriched_rows(account_data, target_acos)

    return format_markdown_report(
        account_name=resolved_name,
        enriched_rows=enriched,
        target_acos=target_acos,
        period=ads_data.get("period", {}),
        synced_at=ads_data.get("synced_at"),
    )
