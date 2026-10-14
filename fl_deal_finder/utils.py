"""Small parsing helpers shared by every tool."""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

_MONEY_RE = re.compile(r"-?\$?\s*\(?-?[\d,]+(?:\.\d+)?\)?")

DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b. %d, %Y",
)


def parse_money(value) -> float:
    """'$12,345.67' -> 12345.67. Blank/garbage -> 0.0. '(1,000)' -> -1000."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    match = _MONEY_RE.search(text)
    if not match:
        return 0.0
    raw = match.group(0)
    negative = "(" in raw or raw.strip().startswith("-")
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits or digits == ".":
        return 0.0
    amount = float(digits)
    return -amount if negative else amount


def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("  ", " ")
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_bool(value) -> bool:
    return str(value).strip().lower() in {"y", "yes", "true", "1", "x"}


def norm_key(text: str) -> str:
    """Normalize a parcel id / case number so different formats match."""
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def write_csv(path: str | Path, rows: Iterable[dict], fieldnames: list[str] | None = None) -> int:
    rows = list(rows)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
