"""Run with:  python -m unittest discover -s tests -v"""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fl_deal_finder import distress, llm, monitor
from fl_deal_finder.monitor.sources import parse_county
from fl_deal_finder.surplus_predictor import calibrate, predict, predict_one
from fl_deal_finder.utils import parse_date, parse_money, read_csv

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "sample_data"
TODAY = date(2026, 10, 14)


class TestUtils(unittest.TestCase):
    def test_parse_money(self):
        self.assertEqual(parse_money("$12,345.67"), 12345.67)
        self.assertEqual(parse_money("(1,000)"), -1000)
        self.assertEqual(parse_money(""), 0.0)
        self.assertEqual(parse_money("n/a"), 0.0)

    def test_parse_date(self):
        self.assertEqual(parse_date("11/04/2026"), date(2026, 11, 4))
        self.assertEqual(parse_date("September 3, 2026"), date(2026, 9, 3))
        self.assertIsNone(parse_date("someday"))


class TestSurplusPredictor(unittest.TestCase):
    def test_basic_math(self):
        p = predict_one({"opening_bid": "10000", "just_market_value": "200000", "property_type": "Single Family",
                         "known_liens": "5000"}, {"single_family": 0.5}, TODAY)
        self.assertEqual(p.expected_winning_bid, 100000)
        self.assertEqual(p.expected_surplus, 90000)
        self.assertEqual(p.expected_owner_share, 85000)

    def test_liens_can_absorb_everything(self):
        p = predict_one({"opening_bid": "10000", "just_market_value": "100000", "property_type": "condo",
                         "known_liens": "90000"}, {"condo": 0.5}, TODAY)
        self.assertEqual(p.expected_owner_share, 0)
        self.assertIn("liens may absorb surplus", p.tags)

    def test_county_specific_ratio_wins(self):
        p = predict_one({"county": "Broward", "opening_bid": "0", "just_market_value": "100",
                         "property_type": "condo"}, {"condo": 0.5, "broward:condo": 0.8}, TODAY)
        self.assertEqual(p.bid_ratio, 0.8)

    def test_ranking_on_sample(self):
        preds = predict(read_csv(SAMPLES / "upcoming_tax_deed_sales.csv"), today=TODAY)
        scores = [p.priority_score for p in preds]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(preds[0].case_number, "2026-TD-001104")

    def test_calibrate(self):
        ratios = calibrate(read_csv(SAMPLES / "past_tax_deed_results.csv"))
        self.assertAlmostEqual(ratios["condo"], 0.433, places=3)
        self.assertIn("sample county:single_family", ratios)


class TestDistress(unittest.TestCase):
    def test_rules_extraction(self):
        s = distress.extract_signals_rules(
            "Final Judgment of Foreclosure. Sale set for 11/04/2026. Unknown heirs. Defendant pro se. "
            "Fine of $250 per day.")
        self.assertIn("foreclosure", s.case_types)
        self.assertEqual(s.sale_date, "2026-11-04")
        self.assertTrue(s.final_judgment and s.multiple_heirs and s.owner_pro_se)
        self.assertEqual(s.daily_fine, 250)

    def test_hoa_foreclosure_not_double_counted(self):
        s = distress.extract_signals_rules("Condominium Association files to foreclose claim of lien.")
        self.assertIn("hoa_foreclosure", s.case_types)
        self.assertNotIn("foreclosure", s.case_types)

    def test_stacking_and_ordering(self):
        results = distress.score_records(read_csv(SAMPLES / "dockets.csv"), today=TODAY)
        top = results[0]
        self.assertEqual(top.parcel_id, "01-2345-000-0040")
        self.assertEqual(len(top.case_numbers), 3)
        self.assertEqual(top.urgency, "high")
        self.assertEqual(results[-1].urgency, "hold")  # bankruptcy goes last

    def test_llm_extractor_parses_structured_output(self):
        payload = {"case_types": ["probate"], "sale_date": "", "final_judgment": False, "default_entered": False,
                   "owner_pro_se": False, "multiple_heirs": True, "owner_deceased": True,
                   "court_ordered_sale": False, "daily_fine": 0, "lien_amount": 0, "vacant_or_unsafe": False,
                   "bankruptcy": False, "summary": "Owner died; two heirs."}
        fake = mock.MagicMock()
        fake.beta.messages.create.return_value = SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])
        with mock.patch.object(llm, "_client", fake):
            s = llm.extract_signals_llm("Estate of X ...")
        self.assertEqual(s.case_types, ["probate"])
        self.assertIsNone(s.sale_date)
        kwargs = fake.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")

    def test_llm_refusal_falls_back_to_rules(self):
        fake = mock.MagicMock()
        fake.beta.messages.create.return_value = SimpleNamespace(stop_reason="refusal", content=[])
        with mock.patch.object(llm, "_client", fake):
            s = llm.extract_signals_llm("Lis pendens recorded.")
        self.assertIn("foreclosure", s.case_types)


class TestMonitor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_day_over_day_changes(self):
        db = self.tmp / "s.sqlite"
        r1 = monitor.run(SAMPLES / "counties.day1.json", db, delay_seconds=0)
        self.assertEqual({c.kind for c in r1.changes}, {"new"})
        self.assertEqual(len(r1.changes), 4)  # TOTAL row skipped
        self.assertEqual(monitor.run(SAMPLES / "counties.day1.json", db, delay_seconds=0).changes, [])
        r2 = monitor.run(SAMPLES / "counties.day2.json", db, delay_seconds=0)
        kinds = sorted(c.kind for c in r2.changes)
        self.assertEqual(kinds, ["amount_changed", "new", "new", "removed"])
        r3 = monitor.run(SAMPLES / "counties.day1.json", db, delay_seconds=0)
        self.assertIn("relisted", {c.kind for c in r3.changes})

    def test_unconfigured_counties_are_skipped(self):
        cfg = self.tmp / "c.json"
        cfg.write_text(json.dumps({"counties": [{"name": "X", "format": "csv", "url": "TODO"}]}))
        report = monitor.run(cfg, self.tmp / "s.sqlite", delay_seconds=0)
        self.assertIn("X", report.errors)

    def test_pdf_parsing(self):
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

        pdf_path = self.tmp / "list.pdf"
        data = [["Case Number", "Owner", "Surplus Amount"],
                ["2026-TD-1", "OWNER ONE", "$1,234.00"], ["2026-TD-2", "OWNER TWO", "$55,000.00"]]
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black")]))
        SimpleDocTemplate(str(pdf_path), pagesize=letter).build([table])
        recs = parse_county({"name": "P", "format": "pdf", "columns": {
            "case_number": "Case Number", "owner_name": "Owner", "amount": "Surplus Amount"}},
            pdf_path.read_bytes())
        self.assertEqual([r.amount for r in recs], [1234.0, 55000.0])


if __name__ == "__main__":
    unittest.main()
