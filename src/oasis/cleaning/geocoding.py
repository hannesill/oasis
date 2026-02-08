"""Google Geocoding API integration with cascading queries (Step 4).

For each facility, tries each candidate query from the geo_queries column
(produced by address_extraction) in order.  Accepts the first result whose
location_type is precise (ROOFTOP, RANGE_INTERPOLATED, or GEOMETRIC_CENTER).

If no precise result is found but an APPROXIMATE result exists, the
APPROXIMATE coordinates are kept (geocode_status = "approximate") so the
facility remains usable.  Only rows where all candidates fail entirely
get geocode_status = "error" with empty lat/long.

Requires: GOOGLE_MAPS_API_KEY environment variable.

Usage:
    from oasis.cleaning.geocoding import run_geocoding
    df = run_geocoding(df)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ── Google Geocoding configuration ────────────────────────────────────

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# location_type values we consider precise enough to accept
ACCEPTED_LOCATION_TYPES = {"ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER"}


def _find_project_root() -> Path:
    """Find the project root (directory containing pyproject.toml or oasis_data)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / "oasis_data").exists():
            return current
        current = current.parent
    return Path.cwd()


def _get_api_key() -> str:
    """Return the Google Maps API key from the environment."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "GOOGLE_MAPS_API_KEY environment variable is not set. "
            "Set it before running the geocoding step."
        )
    return key


# ── Google Geocoding API call ─────────────────────────────────────────

def _geocode_google(
    query: str, api_key: str
) -> tuple[float | None, float | None, str | None]:
    """Call the Google Geocoding API for a single query.

    Returns:
        (latitude, longitude, location_type) or (None, None, None) on
        error / no results.  location_type is one of ROOFTOP,
        RANGE_INTERPOLATED, GEOMETRIC_CENTER, APPROXIMATE, or None.
    """
    params = {
        "address": query,
        "key": api_key,
    }

    try:
        resp = requests.get(GOOGLE_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            geometry = result.get("geometry", {})
            location = geometry.get("location", {})
            location_type = geometry.get("location_type")

            lat = float(location["lat"])
            lng = float(location["lng"])
            return lat, lng, location_type

        if data.get("status") == "ZERO_RESULTS":
            logger.debug("No results for query: '%s'", query)
        elif data.get("status") != "OK":
            logger.warning(
                "Google Geocoding API status '%s' for '%s': %s",
                data.get("status"),
                query,
                data.get("error_message", ""),
            )

        return None, None, None

    except requests.RequestException as e:
        logger.warning("Google Geocoding request failed for '%s': %s", query, e)
        return None, None, None


# ── Cascade logic ────────────────────────────────────────────────────

def _geocode_cascade(
    queries: list[str], api_key: str
) -> tuple[float | None, float | None, str | None, str | None, str]:
    """Try each candidate query in order; accept the first precise result.

    If no precise result is found, falls back to the first APPROXIMATE
    result (keeping its coordinates) so the facility is still usable.

    Returns:
        (lat, long, location_type, query_used, status)
        status is "ok" | "approximate" | "error"
    """
    # Store the first APPROXIMATE result as a fallback
    approx_lat: float | None = None
    approx_lng: float | None = None
    approx_location_type: str | None = None
    approx_query: str | None = None

    for query in queries:
        if not query or not query.strip():
            continue

        lat, lng, location_type = _geocode_google(query, api_key)

        if lat is not None and location_type in ACCEPTED_LOCATION_TYPES:
            # Precise result — accept immediately
            return lat, lng, location_type, query, "ok"

        if lat is not None and approx_lat is None:
            # First APPROXIMATE — remember it as fallback
            approx_lat = lat
            approx_lng = lng
            approx_location_type = location_type
            approx_query = query

    # Exhausted all candidates — fall back to APPROXIMATE if available
    if approx_lat is not None:
        return approx_lat, approx_lng, approx_location_type, approx_query, "approximate"

    # All failed entirely
    return None, None, None, None, "error"


# ── Public orchestrator ──────────────────────────────────────────────

def run_geocoding(df: pd.DataFrame) -> pd.DataFrame:
    """Geocode all facilities using cascading Google Geocoding queries.

    Reads the geo_queries column (JSON array of candidate queries) and adds:
        - lat, long              – coordinates (only if precise)
        - geocode_status         – "ok" | "approximate" | "error"
        - geocode_location_type  – location_type from the accepted result
        - geocode_query_used     – which candidate query produced the result

    For each facility, tries candidates in order and accepts the first
    precise result (ROOFTOP / RANGE_INTERPOLATED / GEOMETRIC_CENTER).

    Args:
        df: DataFrame with a geo_queries column (JSON array).

    Returns:
        DataFrame with geocoding result columns.
    """
    api_key = _get_api_key()
    df = df.copy()

    # Pre-initialise output columns
    df["lat"] = None
    df["long"] = None
    df["geocode_status"] = None
    df["geocode_location_type"] = None
    df["geocode_query_used"] = None

    total = len(df)
    accepted = 0
    approximate = 0
    errors = 0

    for idx in df.index:
        raw = df.at[idx, "geo_queries"] if "geo_queries" in df.columns else None

        # Parse candidate list
        if pd.isna(raw) or not str(raw).strip():
            df.at[idx, "geocode_status"] = "error"
            errors += 1
            continue

        try:
            queries = json.loads(str(raw))
            if not isinstance(queries, list):
                queries = [str(queries)]
        except (json.JSONDecodeError, TypeError):
            queries = [str(raw)]

        lat, lng, location_type, query_used, status = _geocode_cascade(
            queries, api_key
        )

        df.at[idx, "lat"] = lat
        df.at[idx, "long"] = lng
        df.at[idx, "geocode_status"] = status
        df.at[idx, "geocode_location_type"] = location_type
        df.at[idx, "geocode_query_used"] = query_used

        if status == "ok":
            accepted += 1
        elif status == "approximate":
            approximate += 1
        else:
            errors += 1

        processed = accepted + approximate + errors
        if processed % 50 == 0:
            logger.info(
                "Geocoding progress: %d/%d (accepted: %d, approximate: %d, errors: %d)",
                processed,
                total,
                accepted,
                approximate,
                errors,
            )

    logger.info(
        "Geocoding complete: %d/%d accepted, %d approximate, %d errors.",
        accepted,
        total,
        approximate,
        errors,
    )

    return df


# ── Standalone entry-point ────────────────────────────────────────────


def main() -> None:
    """Read vf_ghana_clean.csv, geocode, and overwrite."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

    root = _find_project_root()
    csv_path = root / "vf_ghana_clean.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found at {csv_path}")

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    df = run_geocoding(df)

    df.to_csv(csv_path, index=False)
    logger.info("Saved %d rows to %s", len(df), csv_path)


if __name__ == "__main__":
    main()
