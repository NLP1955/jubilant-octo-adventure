"""Idea #2 - predict tax deed surplus BEFORE the auction.

How a Florida tax deed sale creates surplus
-------------------------------------------
The clerk sets an *opening bid* (certificate amounts + interest + fees, and for
homestead property one-half of the assessed value - Fla. Stat. 197.502).  If
bidders push the price above the opening bid, the overage is "surplus".  Surplus
first pays government liens and other recorded lienholders, and the remainder
belongs to the former owner (or heirs) - Fla. Stat. 197.582.

So the surplus you can help an owner recover is roughly::

    expected_winning_bid  = max(opening_bid, market_value * bid_ratio)
    expected_surplus      = expected_winning_bid - opening_bid
    expected_owner_share  = expected_surplus - liens that get paid first

``bid_ratio`` is "what fraction of market value do winning bids reach in this
county for this property type".  The defaults below are conservative
placeholders - run ``calibrate`` on the county's own past sale results to
replace them with real numbers.  That calibration is the edge: most people
eyeball each file; this ranks the whole sale list before auction day.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from datetime import date

from .utils import parse_bool, parse_date, parse_money

# Fraction of market value that winning tax-deed bids typically reach.
# PLACEHOLDERS - calibrate per county with `calibrate` (see README).
DEFAULT_BID_RATIOS: dict[str, float] = {
    "single_family": 0.70,
    "townhouse": 0.62,
    "condo": 0.50,          # weak 2026 condo market + assessment risk
    "multi_family": 0.65,
    "mobile_home": 0.40,
    "commercial": 0.55,
    "vacant_land": 0.35,
    "other": 0.45,
}

PROPERTY_TYPE_ALIASES = {
    "sfr": "single_family", "single family": "single_family", "single_family": "single_family",
    "residential": "single_family", "house": "single_family",
    "condo": "condo", "condominium": "condo",
    "townhouse": "townhouse", "townhome": "townhouse",
    "duplex": "multi_family", "multi family": "multi_family", "multi_family": "multi_family",
    "mobile home": "mobile_home", "mobile_home": "mobile_home", "manufactured": "mobile_home",
    "vacant": "vacant_land", "vacant land": "vacant_land", "vacant_land": "vacant_land", "land": "vacant_land",
    "commercial": "commercial",
}


def normalize_property_type(raw: str) -> str:
    key = str(raw or "").strip().lower().replace("-", " ")
    return PROPERTY_TYPE_ALIASES.get(key, PROPERTY_TYPE_ALIASES.get(key.replace(" ", "_"), "other"))


@dataclass
class SurplusPrediction:
    case_number: str
    county: str
    parcel_id: str
    sale_date: str
    property_type: str
    situs_address: str
    owner_name: str
    opening_bid: float
    market_value: float
    known_liens: float
    bid_ratio: float
    expected_winning_bid: float
    expected_surplus: float
    expected_owner_share: float
    sale_probability: float
    priority_score: float
    days_until_sale: int | None
    tags: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        row = asdict(self)
        row["tags"] = "; ".join(self.tags)
        for key in ("opening_bid", "market_value", "known_liens", "expected_winning_bid",
                    "expected_surplus", "expected_owner_share", "priority_score"):
            row[key] = round(row[key], 2)
        return row


def _sale_probability(market_value: float, opening_bid: float, ratio: float) -> float:
    """Chance the parcel actually sells (vs. going to the 'lands available' list).

    If the realistic bid level is below the opening bid, few bidders show up.
    """
    if opening_bid <= 0 or market_value <= 0:
        return 0.3
    coverage = (market_value * ratio) / opening_bid
    if coverage >= 2.0:
        return 0.95
    if coverage >= 1.2:
        return 0.85
    if coverage >= 1.0:
        return 0.6
    if coverage >= 0.7:
        return 0.35
    return 0.15


def predict_one(row: dict, bid_ratios: dict[str, float] | None = None,
                today: date | None = None) -> SurplusPrediction:
    ratios = {**DEFAULT_BID_RATIOS, **(bid_ratios or {})}
    today = today or date.today()

    county = row.get("county", "")
    ptype = normalize_property_type(row.get("property_type", ""))
    # County-specific ratio ("Miami-Dade:condo") wins over the statewide one.
    ratio = ratios.get(f"{county.lower()}:{ptype}", ratios.get(ptype, ratios["other"]))

    opening_bid = parse_money(row.get("opening_bid"))
    # Prefer a real market estimate (Zillow/Redfin/comps) over the appraiser's just value.
    market_value = parse_money(row.get("estimated_market_value")) or parse_money(row.get("just_market_value"))
    known_liens = parse_money(row.get("known_liens"))

    expected_bid = max(opening_bid, market_value * ratio)
    expected_surplus = max(0.0, expected_bid - opening_bid)
    owner_share = max(0.0, expected_surplus - known_liens)
    p_sale = _sale_probability(market_value, opening_bid, ratio)

    tags: list[str] = []
    if parse_bool(row.get("homestead")):
        tags.append("homestead (opening bid includes 1/2 assessed value)")
    if parse_bool(row.get("owner_deceased")):
        tags.append("owner deceased - heir search")
    state = str(row.get("owner_mailing_state", "")).strip().upper()
    if state and state != "FL":
        tags.append(f"out-of-state owner ({state})")
    if known_liens and known_liens >= expected_surplus > 0:
        tags.append("liens may absorb surplus")
    if market_value <= 0:
        tags.append("NO MARKET VALUE - add one")
    if p_sale < 0.4:
        tags.append("may not sell (lands available risk)")
    if ptype == "condo":
        tags.append("condo - check association assessments")

    sale_dt = parse_date(row.get("sale_date"))
    days_until = (sale_dt - today).days if sale_dt else None
    if days_until is not None and 0 <= days_until <= 14:
        tags.append("sale within 14 days")

    # Dollars you can expect to be recoverable, weighted by chance it sells.
    priority = owner_share * p_sale

    return SurplusPrediction(
        case_number=row.get("case_number", ""),
        county=county,
        parcel_id=row.get("parcel_id", ""),
        sale_date=sale_dt.isoformat() if sale_dt else row.get("sale_date", ""),
        property_type=ptype,
        situs_address=row.get("situs_address", ""),
        owner_name=row.get("owner_name", ""),
        opening_bid=opening_bid,
        market_value=market_value,
        known_liens=known_liens,
        bid_ratio=ratio,
        expected_winning_bid=expected_bid,
        expected_surplus=expected_surplus,
        expected_owner_share=owner_share,
        sale_probability=p_sale,
        priority_score=priority,
        days_until_sale=days_until,
        tags=tags,
    )


def predict(rows: list[dict], bid_ratios: dict[str, float] | None = None,
            min_owner_share: float = 0.0, today: date | None = None) -> list[SurplusPrediction]:
    preds = [predict_one(r, bid_ratios, today) for r in rows]
    preds = [p for p in preds if p.expected_owner_share >= min_owner_share]
    return sorted(preds, key=lambda p: p.priority_score, reverse=True)


def calibrate(history: list[dict], min_samples: int = 5) -> dict[str, float]:
    """Learn bid ratios from PAST sales.

    ``history`` rows need: property_type, winning_bid, and estimated_market_value
    or just_market_value (optionally county).  Returns ``{"condo": 0.48,
    "miami-dade:condo": 0.52, ...}`` using the median ratio, ignoring outliers.
    """
    buckets: dict[str, list[float]] = {}
    for row in history:
        mv = parse_money(row.get("estimated_market_value")) or parse_money(row.get("just_market_value"))
        bid = parse_money(row.get("winning_bid"))
        if mv <= 0 or bid <= 0:
            continue
        r = bid / mv
        if not 0.05 <= r <= 3.0:  # data errors
            continue
        ptype = normalize_property_type(row.get("property_type", ""))
        buckets.setdefault(ptype, []).append(r)
        county = str(row.get("county", "")).strip().lower()
        if county:
            buckets.setdefault(f"{county}:{ptype}", []).append(r)
    return {k: round(statistics.median(v), 3) for k, v in sorted(buckets.items()) if len(v) >= min_samples}
