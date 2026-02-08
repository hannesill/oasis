"""Pipeline orchestrator for the data cleaning process.

Chains all cleaning steps:
  1. Row consolidation & parsing
  2. Address extraction
  3. Geocoding
  4. Free-form field cleaning
  5. Anomaly detection (rule-based and embedding-based)

Each intermediate result is saved as vf_ghana_clean.csv so that individual
steps can also be run standalone.

Requires: GOOGLE_MAPS_API_KEY environment variable.

Usage:
    uv run oasis clean (--skip-geocoding)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Find the project root (directory containing pyproject.toml or oasis_data)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / "oasis_data").exists():
            return current
        current = current.parent
    return Path.cwd()


def _save_csv(df: pd.DataFrame, csv_path: Path) -> None:
    """Save DataFrame to CSV with error handling for locked files."""
    try:
        df.to_csv(csv_path, index=False)
    except PermissionError:
        try:
            if csv_path.exists():
                csv_path.unlink()
            df.to_csv(csv_path, index=False)
            logger.warning("Overwrote existing CSV file: %s", csv_path)
        except PermissionError:
            logger.error(
                "CSV file %s is locked (possibly open in another application). "
                "Cannot write output.",
                csv_path,
            )
            raise


def run_pipeline(
    input_csv: Path | None = None,
    skip_geocoding: bool = False,
) -> pd.DataFrame:
    """Run the full data cleaning pipeline.

    Args:
        input_csv: Path to the raw CSV file. Auto-detected if not provided.
        skip_geocoding: If True, skip the geocoding step (useful when
            GOOGLE_MAPS_API_KEY is not set).

    Returns:
        The cleaned DataFrame.
    """
    pipeline_start = time.time()


    # ── Resolve paths ─────────────────────────────────────────────────

    root = _find_project_root()

    if input_csv is None:
        input_csv = root / "vf-ghana.csv"
        if not input_csv.exists():
            raise FileNotFoundError(
                f"Input CSV not found at {input_csv}. "
                "Provide the path explicitly via input_csv parameter."
            )

    output_csv = root / "vf_ghana_clean.csv"

    logger.info("Pipeline starting: %s -> %s", input_csv, output_csv)


    # ── Step 0: Load data ─────────────────────────────────────────────

    df = pd.read_csv(input_csv)
    logger.info("Loaded %d rows from %s", len(df), input_csv.name)


    # ── Step 1: Row Consolidation & Parsing ───────────────────────────

    from oasis.cleaning.parse_and_consolidate import run_heuristic_steps

    step_start = time.time()
    df = run_heuristic_steps(df)
    logger.info(
        "Step 1 (row consolidation & parsing) completed in %.1fs: %d facilities",
        time.time() - step_start,
        len(df),
    )

    _save_csv(df, output_csv)
    logger.info("Saved step 1 output (%d rows) to %s", len(df), output_csv)


    # ── Step 2: Address Extraction ─────────────────────────────────

    from oasis.cleaning.address_extraction import run_address_extraction

    step_start = time.time()
    df = run_address_extraction(df)
    logger.info(
        "Step 2 (address extraction) completed in %.1fs",
        time.time() - step_start,
    )

    _save_csv(df, output_csv)
    logger.info("Saved step 2 output (%d rows) to %s", len(df), output_csv)


    # ── Step 3: Geocoding (Google) ──────────────────────────────────

    if skip_geocoding:
        logger.info("Skipping step 3 (geocoding) as requested")
    else:
        from oasis.cleaning.geocoding import run_geocoding

        step_start = time.time()
        df = run_geocoding(df)
        logger.info(
            "Step 3 (geocoding) completed in %.1fs",
            time.time() - step_start,
        )

        _save_csv(df, output_csv)
        logger.info("Saved step 3 output (%d rows) to %s", len(df), output_csv)


    # ── Step 4: Free-form Field Cleaning ──────────────────────────────

    from oasis.cleaning.column_cleaning import clean_freeform_columns

    step_start = time.time()
    df = clean_freeform_columns(df)
    logger.info(
        "Step 4 (free-form field cleaning) completed in %.1fs",
        time.time() - step_start,
    )

    _save_csv(df, output_csv)
    logger.info("Saved step 4 output (%d rows) to %s", len(df), output_csv)


    # ── Step 5: Anomaly Detection ──────────────────────────────────

    from oasis.cleaning.anomaly_detection import run_anomaly_detection

    step_start = time.time()
    df = run_anomaly_detection(df)
    logger.info(
        "Step 5 (anomaly detection) completed in %.1fs",
        time.time() - step_start,
    )

    _save_csv(df, output_csv)
    logger.info("Saved step 5 output (%d rows) to %s", len(df), output_csv)

    elapsed = time.time() - pipeline_start
    logger.info(
        "Pipeline complete: %d facilities written to %s (%.1fs total)",
        len(df),
        output_csv,
        elapsed,
    )

    # Summary statistics
    _log_summary(df)

    return df


def _log_summary(df: pd.DataFrame) -> None:
    """Log a summary of the cleaned dataset."""
    logger.info("=== Cleaning Summary ===")
    logger.info("Total facilities: %d", len(df))

    if "facilityTypeId" in df.columns:
        null_ft = df["facilityTypeId"].isna().sum()
        dist = df["facilityTypeId"].value_counts().to_dict()
        logger.info("facilityTypeId: %s (null: %d)", dist, null_ft)

    if "operatorTypeId" in df.columns:
        null_ot = df["operatorTypeId"].isna().sum()
        dist = df["operatorTypeId"].value_counts().to_dict()
        logger.info("operatorTypeId: %s (null: %d)", dist, null_ot)

    if "geo_queries" in df.columns:
        has_query = df["geo_queries"].notna().sum()
        logger.info("Facilities with geo_queries: %d/%d", has_query, len(df))

    if "lat" in df.columns and "long" in df.columns:
        has_coords = df["lat"].notna().sum()
        logger.info("Geocoded coordinates: %d/%d facilities", has_coords, len(df))

    if "anomaly_desc" in df.columns:
        flagged = df["anomaly_desc"].notna().sum()
        logger.info("Anomalies flagged: %d/%d facilities", flagged, len(df))
