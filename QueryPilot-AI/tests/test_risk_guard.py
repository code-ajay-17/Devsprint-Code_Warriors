import unittest
from risk_guard import evaluate_risk
class TestRiskGuard(unittest.TestCase):
    def test_high_spend_zero_conversions(self):
        result = evaluate_risk({
            "clicks": 50, "cost": 150, "conversions": 0,
            "conversion_value": 0, "is_valid": True,
        })
        self.assertIn("HIGH_SPEND_ZERO_CONVERSIONS", result["risk_flags"])
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["guard_risk_level"], "HIGH")
    def test_low_clicks_flags_insufficient_evidence(self):
        result = evaluate_risk({
            "clicks": 5, "cost": 10, "conversions": 0,
            "is_valid": True,
        })
        self.assertIn("INSUFFICIENT_EVIDENCE", result["risk_flags"])
        self.assertTrue(result["needs_review"])

    def test_missing_metrics_need_review(self):
        result = evaluate_risk({
            "clicks": None, "cost": 10, "conversions": 0,
        })
        self.assertIn("MISSING_METRICS", result["risk_flags"])
        self.assertTrue(result["needs_review"])

    def test_valuable_term_is_protected_from_negative_keyword(self):
        result = evaluate_risk({
            "clicks": 40, "cost": 30, "conversions": 3,
            "conversion_value": 100, "is_valid": True,
        }, proposed_negative_keyword=True)

        self.assertTrue(result["negative_keyword_blocked"])
        self.assertIn(
            "POTENTIALLY_VALUABLE_NEGATIVE_KEYWORD",
            result["risk_flags"],
        )

    def test_existing_decision_fields_are_preserved(self):
        decision = {
            "decision": "PROMOTE",
            "risk_level": "LOW",
            "reason": "Good conversion performance",
            "risk_score": 10,
            "suggested_action": "Keep monitoring",
            "needs_review": False,
        }
        result = evaluate_risk({
            "clicks": 100, "cost": 20, "conversions": 5,
            "conversion_value": 100, "is_valid": True,
        }, decision=decision)

        self.assertEqual(result["decision"], "PROMOTE")
        self.assertEqual(result["reason"], decision["reason"])
        self.assertFalse(result["needs_review"])
        self.assertEqual(result["guard_risk_level"], "LOW")

    def test_nan_metrics_need_review(self):
        result = evaluate_risk({
            "clicks": float("nan"), "cost": 10,
            "conversions": 0, "is_valid": True,
        })
        self.assertIn("MISSING_METRICS", result["risk_flags"])
        self.assertTrue(result["needs_review"])

    def test_existing_high_risk_is_preserved(self):
        decision = {
            "decision": "HUMAN REVIEW",
            "risk_level": "HIGH",
            "reason": "Conflicting evidence",
            "risk_score": 90,
            "suggested_action": "Review manually",
            "needs_review": True,
        }
        result = evaluate_risk({
            "clicks": 100, "cost": 20, "conversions": 5,
            "conversion_value": 100, "is_valid": True,
        }, decision=decision)

        self.assertEqual(result["decision"], "HUMAN REVIEW")
        self.assertEqual(result["risk_score"], 90)
        self.assertTrue(result["needs_review"])
    def test_zero_conversions_with_low_spend_is_not_high_spend_risk(self):
        result = evaluate_risk({
            "clicks": 30, "cost": 10, "conversions": 0,
            "conversion_value": 0, "is_valid": True,
        })
        self.assertNotIn(
            "HIGH_SPEND_ZERO_CONVERSIONS",
            result["risk_flags"],
        )
if __name__ == "__main__":
    unittest.main()
