# FL Deal Finder

Python tools for Florida surplus-funds and distressed-property investors.

| Command | Idea | What it does |
|---|---|---|
| `predict` / `calibrate` | **#2 Surplus prediction** | Ranks *upcoming* tax deed sales by how much surplus they are likely to leave for the former owner, **before** the auction. |
| `distress` | **#7 Distress score** | Reads court/docket text (foreclosure, probate, divorce, HOA lien, code enforcement) and scores each property by urgency, stacking every filing on the same parcel. Optional `--llm` mode has Claude read the filings. |
| `monitor` | **#8 County surplus monitor** | Checks every configured county's surplus list, remembers what it saw, and reports **new**, **changed**, **removed (probably claimed)**, and **relisted** records. Can post alerts to a webhook (Zapier, Slack, Make). |

Everything in `sample_data/` is **made-up example data** so you can try the tools right away.

## Setup

```bash
pip install -r requirements.txt
```

## 1. Predict surplus before a tax deed sale (#2)

Build a CSV of the upcoming sale list (from the clerk's tax deed auction site) with these columns:

`case_number, county, parcel_id, sale_date, property_type, situs_address, owner_name, owner_mailing_state, owner_deceased, homestead, opening_bid, just_market_value, estimated_market_value, known_liens`

- `just_market_value` comes from the property appraiser. `estimated_market_value` (optional, e.g. from Zillow/Redfin/comps) is used instead when present.
- `known_liens` are mortgages, judgments, and other liens that get paid from surplus before the owner.

```bash
# Optional but recommended: learn how high bids really go in your county
python -m fl_deal_finder calibrate --history sample_data/past_tax_deed_results.csv --out config/bid_ratios.json

python -m fl_deal_finder predict --input sample_data/upcoming_tax_deed_sales.csv --ratios config/bid_ratios.json
```

The math:

```
expected winning bid = max(opening bid, market value x bid ratio)
expected surplus     = expected winning bid - opening bid
expected owner share = expected surplus - known liens
priority             = expected owner share x chance the parcel sells
```

The default bid ratios are rough placeholders. **Calibrate with your county's past results** (columns: `county, property_type, just_market_value or estimated_market_value, winning_bid`). That calibration is what makes the ranking accurate. Results go to `output/surplus_predictions.csv`.

## 2. Distress score from court records (#7)

Input CSV: `parcel_id, address, case_number, filed_date, text`. Use one row per filing or docket. `text` is the docket entries or filing text copied from the clerk's case search.

```bash
python -m fl_deal_finder distress --input sample_data/dockets.csv            # free rules engine
python -m fl_deal_finder distress --input sample_data/dockets.csv --llm      # Claude reads each filing
```

Signals detected: foreclosure / HOA foreclosure / probate / divorce / partition / code enforcement / tax deed cases, final judgment, default, **owner pro se**, **multiple heirs**, owner deceased, **court-ordered sale**, **daily code fines**, vacant/unsafe, and **scheduled sale dates** (sales within 30 days are marked urgent). Several case types on the same parcel add a stacking bonus. **Bankruptcy** cases are marked `HOLD`, because the automatic stay limits contact about the property; talk to an attorney first.

`--llm` needs `pip install anthropic` and an `ANTHROPIC_API_KEY`. It uses structured outputs, so results always come back in the same format. If Claude declines a record, the tool falls back to the rules engine for that record.

## 3. Daily county surplus monitor (#8)

Try it with the sample data, which simulates two days:

```bash
python -m fl_deal_finder monitor --config sample_data/counties.day1.json --delay 0
python -m fl_deal_finder monitor --config sample_data/counties.day2.json --delay 0
```

To use real counties, edit `config/counties.json`. It already lists 41 Florida counties, all disabled. For each county you want:

1. Find the clerk's published surplus list (search the site for "surplus", "excess proceeds", or "unclaimed funds").
2. Set `url` (a web link, or a local file path if you got the list through a public records request), `format` (`csv`, `html`, or `pdf`), and match `columns` to the list's headers.
3. Set `"enabled": true`.

Then run it daily, for example with cron at 7:05 every morning:

```
5 7 * * * cd /path/to/repo && python -m fl_deal_finder monitor --min-amount 5000 --webhook >> monitor.log 2>&1
```

Set `SURPLUS_WEBHOOK_URL` to a Zapier / Make / Slack webhook to get alerts on your phone. History is stored in `data/surplus.sqlite`.

The monitor checks `robots.txt`, waits between requests (`--delay`), and identifies itself. Set `FL_DEAL_FINDER_CONTACT` to your email.

## Legal guardrails (read this)

- **Surplus fee agreements are regulated.** See Fla. Stat. 45.032–45.033 (foreclosure surplus) and 197.582 (tax deed surplus). Have a Florida attorney review your agreements.
- **Calls and texts:** the Florida Telephone Solicitation Act and the federal TCPA restrict automated calls and texts. Use compliant outreach.
- **Scraping:** use only public records and follow each site's terms. Some counties provide lists only through a public records request.
- **Bankruptcy:** do not pursue properties under an automatic stay without counsel.
- These tools rank leads. They do not give legal advice. Verify every amount with the clerk before contacting anyone.

## Tests

```bash
python -m unittest discover -s tests -v
```
