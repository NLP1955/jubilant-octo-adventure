"""SQLite memory of every surplus record ever seen, so each run reports only what changed."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .sources import SurplusRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS surplus (
    key          TEXT PRIMARY KEY,
    county       TEXT NOT NULL,
    case_number  TEXT,
    parcel_id    TEXT,
    owner_name   TEXT,
    amount       REAL,
    sale_date    TEXT,
    address      TEXT,
    source       TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'listed'   -- listed | removed
);
CREATE INDEX IF NOT EXISTS surplus_county ON surplus(county);
"""


@dataclass
class Change:
    kind: str                 # new | amount_changed | removed | relisted
    record: SurplusRecord
    old_amount: float | None = None

    def as_row(self) -> dict:
        r = self.record
        return {
            "change": self.kind, "county": r.county, "case_number": r.case_number,
            "parcel_id": r.parcel_id, "owner_name": r.owner_name, "amount": round(r.amount, 2),
            "old_amount": "" if self.old_amount is None else round(self.old_amount, 2),
            "sale_date": r.sale_date, "address": r.address, "source": r.source,
        }


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def sync_county(self, county: str, records: list[SurplusRecord], now: str | None = None) -> list[Change]:
        """Compare today's list for one county with what we stored; persist and return changes."""
        now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self.conn.cursor()
        existing = {row["key"]: row for row in cur.execute("SELECT * FROM surplus WHERE county = ?", (county,))}
        changes: list[Change] = []
        seen: set[str] = set()

        for rec in records:
            if rec.key in seen:
                continue
            seen.add(rec.key)
            old = existing.get(rec.key)
            if old is None:
                changes.append(Change("new", rec))
                cur.execute(
                    "INSERT INTO surplus (key, county, case_number, parcel_id, owner_name, amount, sale_date,"
                    " address, source, first_seen, last_seen, status) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'listed')",
                    (rec.key, rec.county, rec.case_number, rec.parcel_id, rec.owner_name, rec.amount,
                     rec.sale_date, rec.address, rec.source, now, now))
                continue
            if old["status"] == "removed":
                changes.append(Change("relisted", rec, old["amount"]))
            elif abs((old["amount"] or 0) - rec.amount) >= 0.01:
                changes.append(Change("amount_changed", rec, old["amount"]))
            cur.execute(
                "UPDATE surplus SET owner_name=?, amount=?, sale_date=?, address=?, source=?, last_seen=?,"
                " status='listed' WHERE key=?",
                (rec.owner_name, rec.amount, rec.sale_date, rec.address, rec.source, now, rec.key))

        # Records that disappeared were most likely claimed/paid out (or sent to the state).
        for key, old in existing.items():
            if key not in seen and old["status"] == "listed":
                rec = SurplusRecord(old["county"], old["case_number"], old["parcel_id"], old["owner_name"],
                                    old["amount"] or 0.0, old["sale_date"], old["address"], old["source"])
                changes.append(Change("removed", rec, old["amount"]))
                cur.execute("UPDATE surplus SET status='removed', last_seen=? WHERE key=?", (now, key))

        self.conn.commit()
        return changes

    def listed(self, min_amount: float = 0.0) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM surplus WHERE status='listed' AND amount >= ? ORDER BY amount DESC", (min_amount,)))
