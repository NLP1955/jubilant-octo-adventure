"""Claude-powered docket reader for the distress scorer (``--llm``).

Needs ``pip install anthropic`` and an ANTHROPIC_API_KEY (or ``ant auth login``).
Uses structured outputs so the answer always matches the schema below.
"""

from __future__ import annotations

import json

from .distress import CASE_TYPES, Signals

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You read Florida court docket entries and public-record filings for a real estate \
investor who recovers surplus funds and buys distressed property. Extract only facts stated in the \
text; never guess. Use an empty string for sale_date when no sale/auction date is stated, and 0 for \
dollar amounts that are not stated. If several sale dates appear, use the most recent rescheduled \
one. owner_pro_se means the property owner/defendant is representing themselves or has no attorney \
of record. court_ordered_sale means a judge ordered the property sold (divorce, partition, or similar). \
summary: one plain-English sentence describing the owner's situation and what happens next."""

SCHEMA = {
    "type": "object",
    "properties": {
        "case_types": {"type": "array", "items": {"type": "string", "enum": list(CASE_TYPES)}},
        "sale_date": {"type": "string", "description": "YYYY-MM-DD or empty string"},
        "final_judgment": {"type": "boolean"},
        "default_entered": {"type": "boolean"},
        "owner_pro_se": {"type": "boolean"},
        "multiple_heirs": {"type": "boolean"},
        "owner_deceased": {"type": "boolean"},
        "court_ordered_sale": {"type": "boolean"},
        "daily_fine": {"type": "number"},
        "lien_amount": {"type": "number"},
        "vacant_or_unsafe": {"type": "boolean"},
        "bankruptcy": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["case_types", "sale_date", "final_judgment", "default_entered", "owner_pro_se",
                 "multiple_heirs", "owner_deceased", "court_ordered_sale", "daily_fine",
                 "lien_amount", "vacant_or_unsafe", "bankruptcy", "summary"],
    "additionalProperties": False,
}

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("The --llm option needs the Anthropic SDK: pip install anthropic") from exc
        _client = anthropic.Anthropic()
    return _client


def extract_signals_llm(text: str) -> Signals:
    client = _get_client()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"<docket>\n{text}\n</docket>"}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        # If a safety classifier declines, retry on Anthropic's recommended fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        # Fall back to the free rules engine rather than losing the record.
        from .distress import extract_signals_rules
        sig = extract_signals_rules(text)
        sig.summary = "(Claude declined this record; rules engine used)"
        return sig

    raw = next(b.text for b in response.content if b.type == "text")
    data = json.loads(raw)
    data["sale_date"] = data.get("sale_date") or None
    data["case_types"] = data.get("case_types") or ["other"]
    return Signals(**data)
