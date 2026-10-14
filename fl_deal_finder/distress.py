"""Idea #7 - a distress score built by *reading* court and docket text.

List-stacking tools only know "this parcel is on the lis pendens list".  This
reads the actual docket entries and pulls out the details that decide whether a
deal is urgent and solvable: is a sale date set, is the owner unrepresented
(pro se), are there multiple heirs, is a daily code fine running, is there a
bankruptcy stay, etc.

Two engines produce the same ``Signals`` object:
  * ``extract_signals_rules``  - free, offline, regex based (default)
  * ``llm.extract_signals_llm`` - Claude reads the text (``--llm``), catches
    things regexes miss

Records are grouped by parcel so several filings against the same property
"stack" into one score.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date

from .utils import norm_key, parse_date, parse_money

CASE_TYPES = ("foreclosure", "hoa_foreclosure", "probate", "divorce", "partition",
              "code_enforcement", "tax_deed", "eviction", "other")


@dataclass
class Signals:
    case_types: list[str] = field(default_factory=list)
    sale_date: str | None = None          # ISO date of a scheduled foreclosure/tax sale
    final_judgment: bool = False
    default_entered: bool = False
    owner_pro_se: bool = False            # owner has no attorney
    multiple_heirs: bool = False
    owner_deceased: bool = False
    court_ordered_sale: bool = False      # divorce/partition order to sell
    daily_fine: float = 0.0               # code enforcement fine per day
    lien_amount: float = 0.0              # largest dollar lien/judgment mentioned
    vacant_or_unsafe: bool = False
    bankruptcy: bool = False              # automatic stay - do NOT pursue without counsel
    summary: str = ""

    def merge(self, other: "Signals") -> "Signals":
        merged = Signals()
        for f in fields(Signals):
            a, b = getattr(self, f.name), getattr(other, f.name)
            if f.name == "case_types":
                value = sorted(set(a) | set(b))
            elif f.name == "sale_date":
                dates = [d for d in (a, b) if d]
                value = max(dates) if dates else None  # latest = most recently (re)scheduled
            elif f.name == "summary":
                value = " | ".join(s for s in (a, b) if s)
            elif isinstance(a, bool):
                value = a or b
            else:
                value = max(a, b)
            setattr(merged, f.name, value)
        return merged


# --------------------------------------------------------------------------- rules engine

_P = lambda *pats: re.compile("|".join(pats), re.I)  # noqa: E731

CASE_PATTERNS = {
    "hoa_foreclosure": _P(r"\b(home ?owners|condominium|condo|property owners)'? ?association\b.*\bforeclos",
                          r"\bclaim of lien\b.*\bassociation\b", r"\bassociation\b.*\bclaim of lien\b"),
    "foreclosure": _P(r"\blis pendens\b", r"\bforeclos", r"\bmortgage foreclosure\b"),
    "probate": _P(r"\bpetition for (summary |formal )?administration\b", r"\bletters of administration\b",
                  r"\bestate of\b", r"\bdecedent\b", r"\bpersonal representative\b", r"\bprobate\b"),
    "divorce": _P(r"\bdissolution of marriage\b", r"\bdivorce\b", r"\bmarital (home|residence)\b"),
    "partition": _P(r"\bpartition\b"),
    "code_enforcement": _P(r"\bcode enforcement\b", r"\bnotice of violation\b", r"\bcode (compliance|violation)\b",
                           r"\bspecial magistrate\b"),
    "tax_deed": _P(r"\btax deed\b", r"\btax certificate\b"),
    "eviction": _P(r"\beviction\b", r"\bpossession of (real )?property\b"),
}

FLAG_PATTERNS = {
    "final_judgment": _P(r"\bfinal judgment\b", r"\bsummary judgment\b.*\bgranted\b"),
    "default_entered": _P(r"\bdefault (was )?entered\b", r"\bclerk'?s default\b", r"\bdefault judgment\b"),
    "owner_pro_se": _P(r"\bpro se\b", r"\bself[- ]represented\b", r"\bunrepresented\b", r"\bno attorney\b"),
    "multiple_heirs": _P(r"\bheirs\b", r"\bbeneficiaries\b", r"\bunknown (heirs|spouses?|devisees)\b"),
    "owner_deceased": _P(r"\bdeceased\b", r"\bdecedent\b", r"\bestate of\b", r"\bdeath certificate\b"),
    "court_ordered_sale": _P(r"\border(ed)? (to sell|the sale of|for sale)\b",
                             r"\b(marital|subject) (home|residence|property) (shall|is to) be sold\b",
                             r"\bjudgment of partition\b"),
    "vacant_or_unsafe": _P(r"\bvacant\b", r"\babandoned\b", r"\bunsafe structure\b", r"\bboarded\b",
                           r"\bunsecured structure\b", r"\bcondemn"),
    "bankruptcy": _P(r"\bbankruptcy\b", r"\bautomatic stay\b", r"\bchapter (7|11|13)\b"),
}

_DATE = r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})"
SALE_DATE_RE = re.compile(
    r"(?:sale|auction)[^.\n]{0,80}?(?:on|for|set|scheduled|date)[^.\n]{0,20}?" + _DATE, re.I)
DAILY_FINE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)\s*(?:per|a|/|each)\s*day", re.I)
MONEY_RE = re.compile(r"\$\s?([\d,]{4,}(?:\.\d{2})?)")


def extract_signals_rules(text: str) -> Signals:
    s = Signals()
    for ctype, pat in CASE_PATTERNS.items():
        if pat.search(text):
            s.case_types.append(ctype)
    if "hoa_foreclosure" in s.case_types and "foreclosure" in s.case_types:
        s.case_types.remove("foreclosure")
    if not s.case_types:
        s.case_types = ["other"]
    for flag, pat in FLAG_PATTERNS.items():
        if pat.search(text):
            setattr(s, flag, True)

    sale_dates = [d for d in (parse_date(m) for m in SALE_DATE_RE.findall(text)) if d]
    if sale_dates:
        s.sale_date = max(sale_dates).isoformat()  # latest = most recently rescheduled
    fines = [parse_money(m) for m in DAILY_FINE_RE.findall(text)]
    if fines:
        s.daily_fine = max(fines)
    amounts = [parse_money(m) for m in MONEY_RE.findall(text)]
    if amounts:
        s.lien_amount = max(amounts)
    return s


# --------------------------------------------------------------------------- scoring

WEIGHTS = {
    # case types
    "foreclosure": 18, "hoa_foreclosure": 16, "probate": 14, "divorce": 10, "partition": 14,
    "code_enforcement": 10, "tax_deed": 18, "eviction": 4, "other": 0,
    # flags
    "final_judgment": 12, "default_entered": 8, "owner_pro_se": 8, "multiple_heirs": 8,
    "owner_deceased": 8, "court_ordered_sale": 14, "vacant_or_unsafe": 8,
}


@dataclass
class DistressResult:
    parcel_id: str
    address: str
    case_numbers: list[str]
    score: int
    urgency: str
    days_until_sale: int | None
    reasons: list[str]
    signals: Signals
    engine: str

    def as_row(self) -> dict:
        sig = asdict(self.signals)
        return {
            "parcel_id": self.parcel_id,
            "address": self.address,
            "score": self.score,
            "urgency": self.urgency,
            "days_until_sale": self.days_until_sale if self.days_until_sale is not None else "",
            "case_numbers": "; ".join(self.case_numbers),
            "case_types": "; ".join(sig.pop("case_types")),
            "reasons": "; ".join(self.reasons),
            "summary": sig.pop("summary"),
            "engine": self.engine,
            **sig,
        }


def score_signals(s: Signals, today: date | None = None) -> tuple[int, str, int | None, list[str]]:
    today = today or date.today()
    reasons: list[str] = []
    points = 0.0

    for ctype in s.case_types:
        w = WEIGHTS.get(ctype, 0)
        if w:
            points += w
            reasons.append(f"{ctype.replace('_', ' ')} filing")
    real_types = [c for c in s.case_types if c != "other"]
    if len(real_types) >= 2:  # stacked distress, e.g. probate + code fines + foreclosure
        bonus = 6 * (len(real_types) - 1)
        points += bonus
        reasons.append(f"{len(real_types)} different case types stacked")

    for flag in ("final_judgment", "default_entered", "owner_pro_se", "multiple_heirs",
                 "owner_deceased", "court_ordered_sale", "vacant_or_unsafe"):
        if getattr(s, flag):
            points += WEIGHTS[flag]
            reasons.append(flag.replace("_", " "))

    if s.daily_fine:
        points += min(12, 4 + s.daily_fine / 50)
        reasons.append(f"code fine accruing ${s.daily_fine:,.0f}/day")

    days = None
    if s.sale_date:
        sale = parse_date(s.sale_date)
        if sale:
            days = (sale - today).days
            if days < 0:
                reasons.append("sale date already passed - check for surplus")
            elif days <= 30:
                points += 15
                reasons.append(f"sale in {days} days")
            elif days <= 90:
                points += 8
                reasons.append(f"sale in {days} days")

    if s.bankruptcy:
        points *= 0.5
        reasons.append("BANKRUPTCY/automatic stay - talk to an attorney before any contact about the property")

    score = int(max(0, min(100, round(points))))
    if s.bankruptcy:
        urgency = "hold"
    elif (days is not None and 0 <= days <= 30) or score >= 70:
        urgency = "high"
    elif score >= 40:
        urgency = "medium"
    else:
        urgency = "low"
    return score, urgency, days, reasons


def group_by_parcel(records: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in records:
        key = norm_key(r.get("parcel_id")) or norm_key(r.get("address")) or norm_key(r.get("case_number"))
        groups.setdefault(key, []).append(r)
    return groups


def score_records(records: list[dict], use_llm: bool = False, today: date | None = None,
                  llm_extractor=None) -> list[DistressResult]:
    """records: dicts with parcel_id, address, case_number, text (one row per docket/filing)."""
    if use_llm and llm_extractor is None:
        from .llm import extract_signals_llm as llm_extractor  # lazy: only needs anthropic when used

    results = []
    for _, rows in group_by_parcel(records).items():
        combined = Signals()
        for r in rows:
            text = r.get("text", "")
            sig = llm_extractor(text) if use_llm else extract_signals_rules(text)
            combined = combined.merge(sig)
        if len(combined.case_types) > 1 and "other" in combined.case_types:
            combined.case_types.remove("other")
        score, urgency, days, reasons = score_signals(combined, today)
        first = rows[0]
        results.append(DistressResult(
            parcel_id=first.get("parcel_id", ""),
            address=first.get("address", ""),
            case_numbers=sorted({r.get("case_number", "") for r in rows if r.get("case_number")}),
            score=score, urgency=urgency, days_until_sale=days, reasons=reasons,
            signals=combined, engine="claude" if use_llm else "rules",
        ))
    order = {"high": 0, "medium": 1, "low": 2, "hold": 3}
    return sorted(results, key=lambda r: (order[r.urgency], -r.score))
