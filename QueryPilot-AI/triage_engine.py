"""Search-term triage decision engine.

This module is intentionally rule-based and explainable. Thresholds are
configurable and should be validated against the team's business requirements.
"""

from __future__ import annotations

from typing import Any, Mapping
import math
import pandas as pd


OUTPUT_COLUMNS = {
    "triage_decision": "decision",
    "triage_risk_level": "risk_level",
    "triage_reason": "reason",
    "triage_risk_score": "risk_score",
    "triage_suggested_action": "suggested_action",
    "triage_evidence": "evidence",
    "triage_needs_review": "needs_review",
}


def _number(row: Mapping[str, Any], *keys: str) -> float | None:
    """Return the first present, finite numeric value; None if unavailable."""
    for key in keys:
        if key in row and row[key] is not None:
            try:
                value = float(row[key])
            except (TypeError, ValueError):
                return None
            if not math.isfinite(value):
                return None
            return value
    return None


def _validate_threshold(name: str, value: float, *, minimum: float, maximum: float | None = None) -> None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        if maximum is None:
            raise ValueError(f"{name} must be >= {minimum}")
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


def triage_keyword(
    row: Mapping[str, Any],
    min_clicks_for_decision: int = 20,
    low_relevance_threshold: float = 0.2,
) -> dict[str, Any]:
    """Classify one search term.

    Accepted aliases:
      clicks, impressions, conversions,
      spend/cost, revenue/conversion_value,
      optional relevance_score (0.0 to 1.0).

    Decision labels: PROMOTE, BLOCK, IGNORE, HUMAN REVIEW.
    """
    _validate_threshold("min_clicks_for_decision", min_clicks_for_decision, minimum=0)
    _validate_threshold("low_relevance_threshold", low_relevance_threshold, minimum=0, maximum=1)

    if not isinstance(row, Mapping):
        row = {}

    clicks = _number(row, "clicks")
    impressions = _number(row, "impressions")
    conversions = _number(row, "conversions")
    spend = _number(row, "spend", "cost")
    revenue = _number(row, "revenue", "conversion_value")
    relevance = _number(row, "relevance_score")

    def result(decision: str, reason: str, risk_score: int, action: str,
               needs_review: bool = False, evidence: list[str] | None = None) -> dict[str, Any]:
        score = max(0, min(100, int(risk_score)))
        level = "LOW" if score < 34 else ("MEDIUM" if score < 67 else "HIGH")
        return {
            "decision": decision,
            "risk_level": level,
            "reason": reason,
            "risk_score": score,
            "suggested_action": action,
            "evidence": evidence or [],
            "needs_review": needs_review,
        }

    # Validate available metrics first.
    for name, value in (("clicks", clicks), ("impressions", impressions),
                        ("conversions", conversions), ("spend/cost", spend),
                        ("revenue/conversion_value", revenue)):
        if value is not None and value < 0:
            return result("HUMAN REVIEW", f"Invalid negative {name} value.", 90,
                          "Correct the source data before making a decision.", True)
    if clicks is None or conversions is None:
        return result("HUMAN REVIEW", "Required clicks or conversions metric is missing.",
                      75, "Check the source data and review manually.", True)
    if impressions is None:
        return result("HUMAN REVIEW", "Required impressions metric is missing.",
                      70, "Check the source data and review manually.", True)
    if relevance is not None and not 0 <= relevance <= 1:
        return result("HUMAN REVIEW", "Relevance score must be between 0 and 1.",
                      80, "Correct the relevance score and review manually.", True)

    evidence = [f"Clicks: {clicks:g}", f"Conversions: {conversions:g}"]
    if spend is not None:
        evidence.append(f"Spend/cost: {spend:g}")
    if revenue is not None:
        evidence.append(f"Revenue/conversion value: {revenue:g}")
    if relevance is not None:
        evidence.append(f"Relevance score: {relevance:g}")

    # Low relevance is a strong block recommendation, but remains reviewable.
    if relevance is not None and relevance < low_relevance_threshold:
        return result("BLOCK", f"Relevance score {relevance:g} is below the threshold "
                      f"{low_relevance_threshold:g}.", 85,
                      "Review the term and add it as a negative keyword if appropriate.",
                      True, evidence)

    if clicks < min_clicks_for_decision:
        return result("HUMAN REVIEW", "Insufficient click data for a reliable decision.",
                      55, "Collect more data before making a final decision.", True, evidence)

    if conversions > 0:
        if spend is None or revenue is None:
            return result("HUMAN REVIEW",
                          "Conversions exist, but spend or revenue is missing.",
                          50, "Verify performance metrics before promoting.", True, evidence)
        if spend == 0:
            return result("HUMAN REVIEW", "Spend is zero, so ROAS cannot be assessed reliably.",
                          45, "Verify spend and conversion value.", True, evidence)
        roas = revenue / spend
        evidence.append(f"ROAS: {roas:.2f}x")
        if revenue > spend:
            return result("PROMOTE", f"Conversions recorded and ROAS is {roas:.2f}x "
                          "(revenue exceeds spend).", 15,
                          "Consider scaling gradually and continue monitoring.", False, evidence)
        return result("HUMAN REVIEW", f"Conversions recorded, but revenue does not exceed spend "
                      f"(ROAS {roas:.2f}x).", 60,
                      "Review target ROAS, margins, and attribution before changing bids.",
                      True, evidence)

    # No conversions: do not block based on spend alone without an approved spend limit.
    if spend is not None and spend > 0:
        return result("HUMAN REVIEW", "No conversions recorded despite spend; no approved "
                      "blocking spend threshold was provided.", 65,
                      "Review search-term relevance and allowable cost before blocking.", True, evidence)

    return result("IGNORE", "No conversions recorded and no spend-loss signal is available.",
                  20, "Keep monitoring; reconsider when more evidence is available.", False, evidence)


def triage_dataframe(df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Return a copy of df with triage output columns appended."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    result_df = df.copy()
    if df.empty:
        for output_column in OUTPUT_COLUMNS:
            result_df[output_column] = pd.Series(index=result_df.index, dtype="object")
        return result_df

    decisions = [triage_keyword(row, **kwargs) for row in df.to_dict(orient="records")]
    for output_column, result_key in OUTPUT_COLUMNS.items():
        result_df[output_column] = [decision[result_key] for decision in decisions]
    return result_df
