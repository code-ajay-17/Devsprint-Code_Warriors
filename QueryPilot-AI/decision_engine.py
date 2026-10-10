
"""Explainable search-term triage engine for QueryPilotAI."""

from typing import Any, Optional
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
    "triage_confidence_score": "confidence_score",
    "triage_confidence_level": "confidence_level",
    "triage_human_explanation": "human_explanation",
}


def _number(row: dict, *keys: str) -> Optional[float]:
    """Return the first available finite numeric value from the given keys."""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        if math.isfinite(value):
            return value

    return None


def _confidence(row: dict, decision: str) -> int:
    """Rule-based confidence heuristic; this is not a calibrated probability."""
    clicks = _number(row, "clicks")
    conversions = _number(row, "conversions")

    score = 50

    if clicks is not None:
        if clicks >= 100:
            score += 25
        elif clicks >= 50:
            score += 18
        elif clicks >= 20:
            score += 10
        elif clicks < 10:
            score -= 20

    if conversions is not None:
        if conversions >= 10:
            score += 15
        elif conversions >= 3:
            score += 10
        elif conversions == 0:
            score -= 10

    if decision == "HUMAN REVIEW":
        score = min(score, 69)
    elif decision == "IGNORE":
        score = min(score, 65)
    elif decision == "PROMOTE":
        score = max(score, 70)

    return max(5, min(95, int(score)))


def _result(
    decision: str,
    reason: str,
    risk_score: int,
    suggested_action: str,
    needs_review: bool,
    evidence: Optional[list] = None,
    row: Optional[dict] = None,
) -> dict:
    """Build a consistent decision result."""
    risk_score = max(0, min(100, int(risk_score)))

    if risk_score >= 70:
        risk_level = "HIGH"
    elif risk_score >= 35:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    result = {
        "decision": decision,
        "risk_level": risk_level,
        "reason": reason,
        "risk_score": risk_score,
        "suggested_action": suggested_action,
        "evidence": evidence or [],
        "needs_review": bool(needs_review),
    }

    row = row or {}
    confidence = _confidence(row, decision)

    result["confidence_score"] = confidence
    result["confidence_level"] = (
        "HIGH" if confidence >= 80
        else "MEDIUM" if confidence >= 60
        else "LOW"
    )
    result["human_explanation"] = (
        f"{decision}: {reason} "
        f"Recommended next step: {suggested_action}"
    )

    return result


def triage_keyword(
    row: dict,
    min_clicks_for_decision: int = 20,
    low_relevance_threshold: float = 0.20,
) -> dict:
    """Classify one search-term row and return decision and explanation fields."""
    if not hasattr(row, "get"):
        raise TypeError("row must be a dictionary-like object")

    if min_clicks_for_decision < 0:
        raise ValueError("min_clicks_for_decision cannot be negative")

    if not 0 <= low_relevance_threshold <= 1:
        raise ValueError("low_relevance_threshold must be between 0 and 1")

    clicks = _number(row, "clicks")
    conversions = _number(row, "conversions")
    impressions = _number(row, "impressions")
    spend = _number(row, "cost", "spend")
    revenue = _number(row, "conversion_value", "revenue")

    relevance = _number(row, "relevance_score", "relevance")

    evidence = []
    for name, value in (
        ("Impressions", impressions),
        ("Clicks", clicks),
        ("Conversions", conversions),
        ("Spend", spend),
        ("Conversion value", revenue),
    ):
        if value is not None:
            evidence.append(f"{name}: {value:g}")

    def finish(
        decision: str,
        reason: str,
        risk_score: int,
        action: str,
        needs_review: bool,
    ) -> dict:
        return _result(
            decision,
            reason,
            risk_score,
            action,
            needs_review,
            evidence,
            row=row,
        )

    # Invalid negative metrics should be reviewed, not acted upon automatically.
    for name, value in (
        ("impressions", impressions),
        ("clicks", clicks),
        ("conversions", conversions),
        ("cost", spend),
        ("conversion_value", revenue),
    ):
        if value is not None and value < 0:
            return finish(
                "HUMAN REVIEW",
                f"Invalid negative {name} value.",
                90,
                "Correct the source data before making a decision.",
                True,
            )

    if clicks is None or conversions is None:
        return finish(
            "HUMAN REVIEW",
            "Required clicks or conversions metric is missing.",
            75,
            "Check the source data and review manually.",
            True,
        )

    if relevance is not None and not 0 <= relevance <= 1:
        return finish(
            "HUMAN REVIEW",
            "Relevance score must be between 0 and 1.",
            80,
            "Correct the relevance score and review manually.",
            True,
        )

    if relevance is not None and relevance < low_relevance_threshold:
        return finish(
            "BLOCK",
            f"Relevance score {relevance:g} is below threshold "
            f"{low_relevance_threshold:g}.",
            85,
            "Review the term and consider adding a negative keyword.",
            True,
        )

    if clicks < min_clicks_for_decision:
        return finish(
            "HUMAN REVIEW",
            "Insufficient click data for a reliable decision.",
            55,
            "Collect more data before making a final decision.",
            True,
        )

    if conversions > 0:
        if spend is None or revenue is None:
            return finish(
                "HUMAN REVIEW",
                "Conversions exist, but spend or revenue is missing.",
                50,
                "Verify performance metrics before promoting.",
                True,
            )

        if spend <= 0:
            return finish(
                "HUMAN REVIEW",
                "Spend must be positive to assess ROAS reliably.",
                45,
                "Verify spend and conversion value.",
                True,
            )

        roas = revenue / spend
        evidence.append(f"ROAS: {roas:.2f}x")

        if revenue > spend:
            return finish(
                "PROMOTE",
                f"Conversions recorded and ROAS is {roas:.2f}x "
                "(revenue exceeds spend).",
                15,
                "Consider scaling gradually and continue monitoring.",
                False,
            )

        return finish(
            "HUMAN REVIEW",
            f"Conversions recorded, but revenue does not exceed "
            f"spend (ROAS {roas:.2f}x).",
            60,
            "Review target ROAS, margins, and attribution before changing bids.",
            True,
        )

    if spend is not None and spend > 0:
        return finish(
            "HUMAN REVIEW",
            "No conversions recorded despite spend; no approved "
            "blocking spend threshold was provided.",
            65,
            "Review search-term relevance and allowable cost before blocking.",
            True,
        )

    return finish(
        "IGNORE",
        "No conversions recorded and no spend-loss signal is available.",
        40,
        "Monitor the term and collect more performance data.",
        False,
    )


def triage_dataframe(df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Return a copy of the input DataFrame with triage output fields appended."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    result_df = df.copy()

    if df.empty:
        for output_column in OUTPUT_COLUMNS:
            result_df[output_column] = pd.Series(
                index=result_df.index, dtype="object"
            )
        return result_df

    rows = df.to_dict(orient="records")
    decisions = [triage_keyword(row, **kwargs) for row in rows]

    for output_column, result_key in OUTPUT_COLUMNS.items():
        result_df[output_column] = [
            decision[result_key] for decision in decisions
        ]

    return result_df
