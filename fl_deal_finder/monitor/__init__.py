"""Idea #8 - daily monitor of Florida county surplus-funds lists.

Run it once a day (cron / Task Scheduler).  It fetches every enabled county in
``config/counties.json``, compares with what it saw before (SQLite), and reports:

  * new       - fresh surplus just posted: contact the owner first
  * amount_changed - interest added / partial payout
  * removed   - disappeared from the list: probably claimed (useful to know who
                your competition is and how fast claims go)
  * relisted  - came back
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .sources import fetch_bytes, parse_county
from .store import Change, Store


@dataclass
class RunReport:
    changes: list[Change] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)


def load_config(path: str | Path) -> list[dict]:
    cfg = json.loads(Path(path).read_text())
    base = Path(path).resolve().parent.parent  # repo root: relative 'url' paths resolve from here
    counties = []
    for c in cfg["counties"]:
        if not c.get("enabled", True):
            continue
        url = c.get("url", "")
        if url and not url.startswith(("http://", "https://", "file://", "/")):
            c = {**c, "url": str(base / url)}
        counties.append(c)
    return counties


def run(config_path: str | Path, db_path: str | Path, min_amount: float = 0.0,
        delay_seconds: float = 2.0) -> RunReport:
    report = RunReport()
    store = Store(db_path)
    try:
        for county in load_config(config_path):
            name = county["name"]
            if not county.get("url") or "TODO" in county["url"]:
                report.errors[name] = "no URL configured yet"
                continue
            try:
                records = parse_county(county, fetch_bytes(county["url"], delay_seconds))
            except Exception as exc:  # one broken county must not stop the others
                report.errors[name] = f"{type(exc).__name__}: {exc}"
                continue
            report.counts[name] = len(records)
            changes = store.sync_county(name, records)
            report.changes.extend(c for c in changes if c.record.amount >= min_amount or c.kind == "removed")
    finally:
        store.close()
    order = {"new": 0, "relisted": 1, "amount_changed": 2, "removed": 3}
    report.changes.sort(key=lambda c: (order[c.kind], -c.record.amount))
    return report


def send_webhook(report: RunReport, url: str | None = None) -> bool:
    """POST new/changed records as JSON to a webhook (Zapier, Make, Slack workflow, etc.)."""
    url = url or os.environ.get("SURPLUS_WEBHOOK_URL")
    actionable = [c.as_row() for c in report.changes if c.kind in ("new", "relisted", "amount_changed")]
    if not url or not actionable:
        return False
    import requests

    total = sum(r["amount"] for r in actionable)
    payload = {
        "text": f"{len(actionable)} new/changed Florida surplus records (${total:,.0f} total)",
        "records": actionable,
    }
    requests.post(url, json=payload, timeout=30).raise_for_status()
    return True
