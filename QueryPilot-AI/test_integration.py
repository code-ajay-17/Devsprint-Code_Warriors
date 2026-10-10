
from decision_engine import triage_keyword
from risk_guard import evaluate_risk

row = {
    "search_term": "buy running shoes",
    "clicks": 50,
    "cost": 150,
    "conversions": 0,
    "conversion_value": 0,
    "is_valid": True,
}

# Call Member 2's actual decision engine
decision = triage_keyword(row)

print("Engine decision:", decision)

# Apply Member 4's risk guard
result = evaluate_risk(row, decision=decision)

print("\nFinal result:")
for key in (
    "decision",
    "risk_level",
    "reason",
    "risk_score",
    "suggested_action",
    "needs_review",
    "guard_risk_level",
    "risk_flags",
    "warnings",
):
    print(f"{key}: {result.get(key)}")

assert isinstance(result, dict)
assert result.get("decision") in {
    "PROMOTE", "PAUSE", "BLOCK", "HUMAN REVIEW", "IGNORE"
}
assert isinstance(result.get("needs_review"), bool)

print("\nACTUAL INTEGRATION TEST PASSED!")
