
"""
QueryPilotAI - Data Processor
PS-01: Search Term Triage Engine

Responsibilities:
1. Load the search terms dataset.
2. Validate records and flag data-quality issues.
3. Calculate performance metrics.
4. Export processed data for the decision engine.

This module does NOT make final promote/block/ignore decisions.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

REQUIRED_COLUMNS = [
    "row_id",
    "search_term",
    "match_type",
    "campaign",
    "ad_group",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
]

COUNT_COLUMNS = [
    "row_id",
    "impressions",
    "clicks",
    "conversions",
]

NUMERIC_COLUMNS = [
    "row_id",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
]


# --------------------------------------------------
# 2. Load the dataset
# --------------------------------------------------

def load_data(file_path=None):
    """
    Load the official search-term CSV dataset.

    If file_path is not supplied, look for
    search_terms_report.csv beside this Python file.
    """

    if file_path is None:
        file_path = (
            Path(__file__).resolve().parent
            / "search_terms_report.csv"
        )
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}\n"
            "Place search_terms_report.csv beside "
            "data_processor.py or provide its full path."
        )

    df = pd.read_csv(file_path)

    print(f"Dataset loaded successfully: {file_path.name}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    return df


# --------------------------------------------------
# 3. Validate the dataset
# --------------------------------------------------

def validate_data(df):
    """
    Validate required fields and metric constraints.

    Returns a copy of the DataFrame with:
    - is_valid: True when no validation issues exist
    - validation_issues: explanation of any issues

    Invalid rows are flagged, not deleted.
    """

    df = df.copy()

    # Check required columns first.
    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    # Create a list of issues for each row.
    issues = [[] for _ in range(len(df))]

    def flag(mask, message):
        """Add an issue to each row matching the mask."""
        mask = pd.Series(mask, index=df.index).fillna(True)

        for position, matched in enumerate(mask.to_numpy()):
            if matched:
                issues[position].append(message)

    # Required text fields must not be empty.
    for col in [
        "search_term",
        "match_type",
        "campaign",
        "ad_group",
    ]:
        text = df[col].astype("string").str.strip()

        flag(
            text.isna() | text.eq(""),
            f"Missing or empty {col}",
        )

    # Normalize categorical and search-term text.
    df["search_term"] = (
        df["search_term"].astype("string").str.strip()
    )

    df["match_type"] = (
        df["match_type"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    for col in ["campaign", "ad_group"]:
        df[col] = df[col].astype("string").str.strip()

    # Match type must be one of the documented values.
    flag(
        ~df["match_type"].isin(["broad", "phrase", "exact"]),
        "Unknown match_type",
    )

    # Convert numeric columns safely.
    # Bad values become NaN and are flagged below.
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

        flag(
            df[col].isna(),
            f"Missing or non-numeric {col}",
        )

        flag(
            df[col].notna() & ~np.isfinite(df[col]),
            f"Non-finite {col}",
        )

    # Count and ID fields must be whole numbers.
    for col in COUNT_COLUMNS:
        flag(
            df[col].notna()
            & np.isfinite(df[col])
            & (df[col] % 1 != 0),
            f"Non-integer {col}",
        )

    # Numeric values must not be negative.
    for col in [
        "impressions",
        "clicks",
        "cost",
        "conversions",
        "conversion_value",
    ]:
        flag(
            df[col].notna() & (df[col] < 0),
            f"Negative {col}",
        )

    # Check relationships between metrics.
    flag(
        df["clicks"].notna()
        & df["impressions"].notna()
        & (df["clicks"] > df["impressions"]),
        "Clicks exceed impressions",
    )

    flag(
        df["conversions"].notna()
        & df["clicks"].notna()
        & (df["conversions"] > df["clicks"]),
        "Conversions exceed clicks",
    )

    # row_id should be unique.
    flag(
        df["row_id"].notna()
        & df["row_id"].duplicated(keep=False),
        "Duplicate row_id",
    )

    df["validation_issues"] = [
        "; ".join(row_issues) for row_issues in issues
    ]

    df["is_valid"] = [
        len(row_issues) == 0 for row_issues in issues
    ]

    invalid_count = int((~df["is_valid"]).sum())

    print("\nValidation completed.")
    print(f"Valid rows: {len(df) - invalid_count:,}")
    print(f"Rows with issues: {invalid_count:,}")

    return df


# --------------------------------------------------
# 4. Calculate performance metrics
# --------------------------------------------------

def calculate_metrics(df):
    """
    Add CTR, conversion rate, CPA and ROAS.

    Rates are expressed as percentages.
    Undefined ratios are represented by NaN.
    """

    df = df.copy()

    # Click-through rate: clicks / impressions
    df["ctr"] = (
        df["clicks"]
        .div(df["impressions"].replace(0, np.nan))
        * 100
    )

    # Conversion rate: conversions / clicks
    df["conversion_rate"] = (
        df["conversions"]
        .div(df["clicks"].replace(0, np.nan))
        * 100
    )

    # Cost per acquisition: cost / conversions
    df["cpa"] = (
        df["cost"]
        .div(df["conversions"].replace(0, np.nan))
    )

    # Return on ad spend: conversion value / cost
    df["roas"] = (
        df["conversion_value"]
        .div(df["cost"].replace(0, np.nan))
    )

    print("\nPerformance metrics calculated.")

    return df


# --------------------------------------------------
# 5. Process the dataset
# --------------------------------------------------

def process_data(file_path=None):
    """
    Run the complete processing pipeline.

    Returns the processed DataFrame.
    """

    df = load_data(file_path)
    df = validate_data(df)
    df = calculate_metrics(df)

    return df


# --------------------------------------------------
# 6. Export processed data
# --------------------------------------------------

def save_processed_data(
    df,
    output_path="processed_search_terms.csv",
):
    """
    Export processed records, including validation flags
    and calculated metrics.
    """

    output_path = Path(output_path)

    df.to_csv(output_path, index=False)

    print(f"\nProcessed data saved to: {output_path.resolve()}")

    return output_path


# --------------------------------------------------
# 7. Run directly for testing
# --------------------------------------------------

if __name__ == "__main__":
    processed_df = process_data()

    print("\nFirst 5 processed rows:")
    print(
        processed_df[
            [
                "search_term",
                "match_type",
                "clicks",
                "cost",
                "conversions",
                "ctr",
                "conversion_rate",
                "cpa",
                "roas",
                "is_valid",
            ]
        ].head().to_string(index=False)
    )

    save_processed_data(processed_df)
