import unittest
import pandas as pd

from triage_engine import triage_keyword, triage_dataframe


class TestTriageEngine(unittest.TestCase):

    def test_profitable_term_promoted(self):
        result = triage_keyword({
            "clicks": 50,
            "impressions": 1000,
            "conversions": 5,
            "spend": 100,
            "revenue": 250,
        })
        self.assertEqual(result["decision"], "PROMOTE")

    def test_low_clicks_need_review(self):
        result = triage_keyword({
            "clicks": 2,
            "impressions": 100,
            "conversions": 0,
        })
        self.assertEqual(result["decision"], "HUMAN REVIEW")

    def test_negative_clicks_flagged(self):
        result = triage_keyword({
            "clicks": -5,
            "impressions": 100,
            "conversions": 0,
        })
        self.assertEqual(result["decision"], "HUMAN REVIEW")

    def test_missing_metrics_need_review(self):
        result = triage_keyword({
            "clicks": 50,
            "impressions": 1000,
        })
        self.assertEqual(result["decision"], "HUMAN REVIEW")

    def test_dataframe_keeps_original_columns(self):
        df = pd.DataFrame([{
            "clicks": 50,
            "impressions": 1000,
            "conversions": 5,
            "spend": 100,
            "revenue": 250,
        }])
        result = triage_dataframe(df)
        self.assertIn("clicks", result.columns)
        self.assertIn("triage_decision", result.columns)
        self.assertEqual(len(result), 1)

    def test_click_threshold_is_configurable(self):
        result = triage_keyword({
            "clicks": 10,
            "impressions": 200,
            "conversions": 0,
        }, min_clicks_for_decision=5)
        self.assertEqual(result["decision"], "IGNORE")
        self.assertIn("No conversions recorded", result["reason"])

    def test_low_relevance_flags_block(self):
        result = triage_keyword({
            "clicks": 50,
            "impressions": 1000,
            "conversions": 0,
            "relevance_score": 0.1,
        })
        self.assertEqual(result["decision"], "BLOCK")
        self.assertTrue(result["needs_review"])

    def test_empty_dataframe_keeps_output_columns(self):
        result = triage_dataframe(pd.DataFrame())
        self.assertIn("triage_decision", result.columns)
        self.assertIn("triage_reason", result.columns)
        self.assertEqual(len(result), 0)

    def test_invalid_relevance_threshold_rejected(self):
        with self.assertRaises(ValueError):
            triage_keyword(
                {"clicks": 50, "conversions": 0},
                low_relevance_threshold=1.5,
            )

    def test_zero_click_threshold_is_allowed(self):
        result = triage_keyword({
            "clicks": 10,
            "impressions": 100,
            "conversions": 0,
        }, min_clicks_for_decision=0)
        self.assertEqual(result["decision"], "IGNORE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
