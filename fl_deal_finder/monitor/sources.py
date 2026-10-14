"""Fetch and parse a county's published surplus list (CSV, HTML table, or PDF).

Every county clerk publishes differently, so each county is a small entry in
``config/counties.json`` that says WHERE the list is, WHAT format it is in, and
WHICH column holds each field.  Adding a county = adding a config entry, no code.
"""

from __future__ import annotations

import csv
import io
import os
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..utils import norm_key, parse_date, parse_money

USER_AGENT = "fl-deal-finder/0.1 (public records research; contact: set FL_DEAL_FINDER_CONTACT)"
FIELDS = ("case_number", "parcel_id", "owner_name", "amount", "sale_date", "address")


@dataclass
class SurplusRecord:
    county: str
    case_number: str
    parcel_id: str
    owner_name: str
    amount: float
    sale_date: str
    address: str
    source: str

    @property
    def key(self) -> str:
        return f"{self.county}|{norm_key(self.case_number) or norm_key(self.parcel_id)}"


# --------------------------------------------------------------------------- fetching

def _robots_allows(url: str) -> bool:
    parts = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # no robots.txt reachable -> treat as allowed
    return rp.can_fetch(USER_AGENT, url)


def fetch_bytes(location: str, delay_seconds: float = 2.0) -> bytes:
    """Read a local path / file:// URL, or politely GET an http(s) URL."""
    if location.startswith("file://"):
        location = location[len("file://"):]
    if not location.startswith(("http://", "https://")):
        return Path(location).read_bytes()

    import requests

    if not _robots_allows(location):
        raise PermissionError(f"robots.txt disallows fetching {location}")
    time.sleep(delay_seconds)  # be polite to county servers
    headers = {"User-Agent": USER_AGENT.replace("set FL_DEAL_FINDER_CONTACT",
                                                os.environ.get("FL_DEAL_FINDER_CONTACT", "n/a"))}
    resp = requests.get(location, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


# --------------------------------------------------------------------------- parsing

def _rows_from_csv(data: bytes, cfg: dict) -> list[dict]:
    text = data.decode(cfg.get("encoding", "utf-8-sig"), errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _rows_from_table(header: list[str], body: list[list[str]]) -> list[dict]:
    header = [" ".join((h or "").split()) for h in header]
    rows = []
    for cells in body:
        cells = [" ".join((c or "").split()) for c in cells]
        if not any(cells) or cells == header:
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _rows_from_html(data: bytes, cfg: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    selector = cfg.get("table_selector", "table")
    tables = soup.select(selector)
    if not tables:
        raise ValueError(f"no table matched selector {selector!r}")
    table = tables[cfg.get("table_index", 0)]
    trs = table.find_all("tr")
    header = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
    body = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])] for tr in trs[1:]]
    return _rows_from_table(header, body)


def _rows_from_pdf(data: bytes, cfg: dict) -> list[dict]:
    import pdfplumber

    rows: list[dict] = []
    header: list[str] | None = None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                # Header repeats on each page in most clerk PDFs; otherwise reuse the first one.
                first = [(c or "").strip() for c in table[0]]
                if header is None or first == header:
                    header, body = first, table[1:]
                else:
                    body = table
                rows.extend(_rows_from_table(header, body))
    return rows


PARSERS = {"csv": _rows_from_csv, "html": _rows_from_html, "pdf": _rows_from_pdf}


def _pick(row: dict, column_spec) -> str:
    """column_spec may be one column name or a list of candidates (first match wins)."""
    candidates = column_spec if isinstance(column_spec, list) else [column_spec]
    lowered = {k.strip().lower(): v for k, v in row.items() if k}
    for name in candidates:
        if name is None:
            continue
        value = lowered.get(str(name).strip().lower())
        if value not in (None, ""):
            return str(value).strip()
    return ""


def parse_county(cfg: dict, data: bytes) -> list[SurplusRecord]:
    fmt = cfg["format"].lower()
    if fmt not in PARSERS:
        raise ValueError(f"unknown format {fmt!r} (use csv, html or pdf)")
    raw_rows = PARSERS[fmt](data, cfg)
    columns = cfg.get("columns", {})
    records = []
    for row in raw_rows:
        values = {f: _pick(row, columns.get(f, f)) for f in FIELDS}
        amount = parse_money(values["amount"])
        if not (values["case_number"] or values["parcel_id"]):
            continue  # blank / footer lines
        if values["case_number"].strip().upper().startswith(("TOTAL", "GRAND TOTAL")):
            continue  # summary row
        sale = parse_date(values["sale_date"])
        records.append(SurplusRecord(
            county=cfg["name"],
            case_number=values["case_number"],
            parcel_id=values["parcel_id"],
            owner_name=values["owner_name"],
            amount=amount,
            sale_date=sale.isoformat() if sale else values["sale_date"],
            address=values["address"],
            source=cfg.get("url", ""),
        ))
    return records
