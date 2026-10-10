"""
QueryPilot AI - Member 4
Risk guard and negative-keyword safety checks.

Uses only Python's standard library.
"""

import math


def _number(row, field):
    """Return a finite float, or None for missing/invalid values."""
    value = row.get(field)

    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def evaluate_risk(
    row,
    decision=None,
    proposed_negative_keyword=False,
    high_spend_threshold=100.0,
    min_clicks_for_evidence=20,
):
    """
    Evaluate safety risks for one processed search-term row.

    Args:
        row: Dictionary containing processed search-term metrics.
        decision: Optional dictionary returned by decision_engine.py.
        proposed_negative_keyword: Whether someone proposes excluding
            this search term using a negative keyword.
        high_spend_threshold: Configurable spend threshold in the
            dataset's currency units.
        min_clicks_for_evidence: Click count below which evidence is
            considered insufficient for a confident decision.

    Returns:
        A JSON-compatible dictionary with the decision and risk warnings.
    """
    if not isinstance(row, dict):
        row = dict(row)

    result = dict(decision or {})
    risk_flags = []
    warnings = []
    guard_score = 0

    clicks = _number(row, "clicks")
    cost = _number(row, "cost")
    conversions = _number(row, "conversions")
    conversion_value = _number(row, "conversion_value")

    # 1. Missing or invalid data
    if row.get("is_valid") is False or row.get("is_valid") == 0:
        risk_flags.append("INVALID_DATA")
        warnings.append("The data processor marked this row as invalid.")
        guard_score = max(guard_score, 60)

    validation_issues = row.get("validation_issues")
    if validation_issues is not None:
        if isinstance(validation_issues, str) and validation_issues.strip():
            if validation_issues.strip().lower() not in ("none", "[]", "nan"):
                risk_flags.append("VALIDATION_ISSUES")
                warnings.append("Data validation issues need checking.")
                guard_score = max(guard_score, 60)
        elif isinstance(validation_issues, (list, tuple)) and validation_issues:
            risk_flags.append("VALIDATION_ISSUES")
            warnings.append("Data validation issues need checking.")
            guard_score = max(guard_score, 60)

    missing_metrics = [
        name for name, value in (
            ("clicks", clicks),
            ("cost", cost),
            ("conversions", conversions),
        )
        if value is None
    ]

    if missing_metrics:
        risk_flags.append("MISSING_METRICS")
        warnings.append(
            "Missing or invalid metrics: " + ", ".join(missing_metrics)
        )
        guard_score = max(guard_score, 60)

    # 2. Insufficient evidence
    if clicks is not None and clicks < min_clicks_for_evidence:
        risk_flags.append("INSUFFICIENT_EVIDENCE")
        warnings.append(
            f"Only {clicks:g} clicks; fewer than "
            f"{min_clicks_for_evidence} clicks."
        )
        guard_score = max(guard_score, 30)

    # 3. High spend without conversions
    if (
        cost is not None
        and conversions is not None
        and cost >= high_spend_threshold
        and conversions == 0
    ):
        risk_flags.append("HIGH_SPEND_ZERO_CONVERSIONS")
        warnings.append(
            "Spend has reached the configured threshold without conversions."
        )
        guard_score = max(guard_score, 80)

    # 4. Negative-keyword safety
    negative_keyword_blocked = False

    if proposed_negative_keyword:
        has_conversion = conversions is not None and conversions > 0
        has_conversion_value = (
            conversion_value is not None and conversion_value > 0
        )

        if has_conversion or has_conversion_value:
            negative_keyword_blocked = True
            risk_flags.append("POTENTIALLY_VALUABLE_NEGATIVE_KEYWORD")
            warnings.append(
                "This term has conversion evidence or conversion value. "
                "Do not add it as a negative keyword without review."
            )
            guard_score = max(guard_score, 80)

    # Merge review requirements without removing the engine's own fields.
    needs_review = bool(result.get("needs_review", False))
    needs_review = needs_review or bool(risk_flags)

    # Preserve the engine's decision and reason; add guard information.
    existing_score = _number(result, "risk_score")
    combined_score = max(existing_score or 0, guard_score)

    if combined_score >= 60:
        guard_level = "HIGH"
    elif combined_score >= 25:
        guard_level = "MEDIUM"
    else:
        guard_level = "LOW"

    result.update({
        "needs_review": needs_review,
        "guard_risk_score": guard_score,
        "guard_risk_level": guard_level,
        "risk_score": combined_score,
        "risk_flags": risk_flags,
        "warnings": warnings,
        "negative_keyword_blocked": negative_keyword_blocked,
    })

    # A safety warning may require review, without silently changing
    # the decision engine's decision label.
    if needs_review and not result.get("suggested_action"):
        result["suggested_action"] = "Review this search term manually."

    return result