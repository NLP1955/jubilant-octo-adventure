"""Command line:  python -m fl_deal_finder <command> ...

  predict    rank upcoming tax deed sales by expected surplus        (idea #2)
  calibrate  learn county bid ratios from past sale results          (idea #2)
  distress   score properties by reading docket / court text         (idea #7)
  monitor    check county surplus lists and report what changed      (idea #8)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .utils import read_csv, write_csv


def _money(x: float) -> str:
    return f"${x:,.0f}"


def cmd_predict(args) -> int:
    from .surplus_predictor import predict

    ratios = json.loads(Path(args.ratios).read_text()) if args.ratios else None
    preds = predict(read_csv(args.input), ratios, min_owner_share=args.min_surplus)
    write_csv(args.out, (p.as_row() for p in preds))
    print(f"{len(preds)} sales ranked -> {args.out}\n")
    print(f"{'#':>3}  {'county':<12} {'case':<16} {'type':<13} {'open bid':>10} {'exp. owner $':>12} {'p(sale)':>7}  tags")
    for i, p in enumerate(preds[: args.top], 1):
        print(f"{i:>3}  {p.county[:12]:<12} {p.case_number[:16]:<16} {p.property_type:<13} "
              f"{_money(p.opening_bid):>10} {_money(p.expected_owner_share):>12} {p.sale_probability:>7.0%}  "
              f"{'; '.join(p.tags)}")
    return 0


def cmd_calibrate(args) -> int:
    from .surplus_predictor import calibrate

    ratios = calibrate(read_csv(args.history), min_samples=args.min_samples)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(ratios, indent=2))
    print(json.dumps(ratios, indent=2))
    print(f"\nsaved -> {args.out}   (use with: predict --ratios {args.out})")
    return 0


def cmd_distress(args) -> int:
    from .distress import score_records

    results = score_records(read_csv(args.input), use_llm=args.llm)
    write_csv(args.out, (r.as_row() for r in results))
    print(f"{len(results)} properties scored ({'Claude' if args.llm else 'rules'} engine) -> {args.out}\n")
    for r in results[: args.top]:
        print(f"[{r.urgency.upper():<6}] {r.score:>3}  {r.parcel_id:<22} {r.address}")
        print(f"            {'; '.join(r.reasons)}")
        if r.signals.summary and args.llm:
            print(f"            {r.signals.summary}")
    return 0


def cmd_monitor(args) -> int:
    from . import monitor

    report = monitor.run(args.config, args.db, min_amount=args.min_amount, delay_seconds=args.delay)
    for county, n in report.counts.items():
        print(f"  checked {county:<16} {n:>4} records")
    for county, err in report.errors.items():
        print(f"  SKIPPED {county:<16} {err}")
    if not report.counts and not report.errors:
        print(f"No counties enabled in {args.config} - fill in a county's url/columns and set enabled: true.")
        return 1

    if not report.changes:
        print("\nNo changes since last run.")
    else:
        out = args.out or "output/surplus_changes.csv"
        write_csv(out, (c.as_row() for c in report.changes))
        print(f"\n{len(report.changes)} changes -> {out}")
        for c in report.changes[: args.top]:
            r = c.record
            extra = f" (was {_money(c.old_amount)})" if c.old_amount is not None and c.kind != "removed" else ""
            print(f"  {c.kind.upper():<15} {r.county:<12} {r.case_number:<18} {_money(r.amount):>10}{extra}  {r.owner_name}")
    if args.webhook or args.webhook_url:
        sent = monitor.send_webhook(report, args.webhook_url)
        print("\nwebhook sent" if sent else "\nwebhook: nothing to send (or no URL set)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fl_deal_finder", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("predict", help="rank upcoming tax deed sales by expected surplus")
    p.add_argument("--input", required=True, help="CSV of upcoming tax deed sales")
    p.add_argument("--out", default="output/surplus_predictions.csv")
    p.add_argument("--ratios", help="JSON from the calibrate command")
    p.add_argument("--min-surplus", type=float, default=0.0, help="hide sales below this expected owner share")
    p.add_argument("--top", type=int, default=15)
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("calibrate", help="learn bid ratios from past tax deed results")
    p.add_argument("--history", required=True, help="CSV of past sales with winning_bid")
    p.add_argument("--out", default="config/bid_ratios.json")
    p.add_argument("--min-samples", type=int, default=5)
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("distress", help="score properties from docket/court text")
    p.add_argument("--input", required=True, help="CSV with parcel_id, address, case_number, text")
    p.add_argument("--out", default="output/distress_scores.csv")
    p.add_argument("--llm", action="store_true", help="have Claude read each docket (needs anthropic + API key)")
    p.add_argument("--top", type=int, default=15)
    p.set_defaults(func=cmd_distress)

    p = sub.add_parser("monitor", help="check county surplus lists for changes")
    p.add_argument("--config", default="config/counties.json")
    p.add_argument("--db", default="data/surplus.sqlite")
    p.add_argument("--out", help="CSV of changes (default output/surplus_changes.csv)")
    p.add_argument("--min-amount", type=float, default=0.0)
    p.add_argument("--delay", type=float, default=2.0, help="seconds between county requests")
    p.add_argument("--webhook", action="store_true", help="POST changes to $SURPLUS_WEBHOOK_URL")
    p.add_argument("--webhook-url", help="POST changes to this URL")
    p.add_argument("--top", type=int, default=25)
    p.set_defaults(func=cmd_monitor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
