"""Heuristic address extraction (Step 3.5).

For each facility, builds a ranked list of geocoding query candidates
stored as a JSON array in the ``geo_queries`` column.  The geocoding step
will try each candidate in order and accept the first precise result.

Candidate order (most likely to be precise first):
  1. {name}                                       – works when Google knows the facility
  2. {name}, {address_city}, Ghana                – adds geographic context
  3. {cleaned_address_line1}, {address_city}, Ghana – specific street address

Address lines are cleaned of parenthetical text, landmark references
("Near …", "Opposite …", "Behind …"), and other noise that degrades
geocoding accuracy.

Usage:
    from oasis.cleaning.address_extraction import run_address_extraction
    df = run_address_extraction(df)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── Address cleaning patterns ─────────────────────────────────────────

# Remove parenthetical text: (Near Mexico Hotel), (Opposite Benab Oil ...)
_PARENTHETICAL = re.compile(r"\([^)]*\)")

# Remove landmark-style prefixes/phrases
_LANDMARK_PHRASES = re.compile(
    r"\b(Near|Opposite|Behind|Close to|Adjacent to|Next to|Beside|In front of|Closest station is)\b[^,]*",
    re.IGNORECASE,
)


def _find_project_root() -> Path:
    """Find the project root (directory containing pyproject.toml or oasis_data)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / "oasis_data").exists():
            return current
        current = current.parent
    return Path.cwd()


def _clean_address(raw: str) -> str:
    """Strip noise from an address string for geocoding.

    Removes parenthetical text, landmark references, and excess whitespace.
    """
    s = _PARENTHETICAL.sub("", raw)
    s = _LANDMARK_PHRASES.sub("", s)
    # Collapse whitespace and strip dangling commas / dots
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(".,;: ")
    return s


def _build_geo_queries(row: pd.Series) -> str:
    """Build a ranked list of geocoding query candidates for a facility row.

    Returns a JSON-encoded list of strings.
    """
    candidates: list[str] = []

    name = row.get("name")
    name = str(name).strip() if pd.notna(name) and str(name).strip() else ""

    city = row.get("address_city")
    city = str(city).strip() if pd.notna(city) and str(city).strip() else ""

    addr1 = row.get("address_line1")
    addr1 = str(addr1).strip() if pd.notna(addr1) and str(addr1).strip() else ""

    # Candidate 1: name only
    if name:
        candidates.append(name)

    # Candidate 2: name + city + Ghana
    if name and city:
        candidates.append(f"{name}, {city}, Ghana")

    # Candidate 3: cleaned address_line1 + city + Ghana
    if addr1:
        cleaned = _clean_address(addr1)
        if cleaned and city:
            q = f"{cleaned}, {city}, Ghana"
            if q not in candidates:
                candidates.append(q)
        elif cleaned:
            q = f"{cleaned}, Ghana"
            if q not in candidates:
                candidates.append(q)

    # Fallback: if we have nothing, try city alone
    if not candidates and city:
        candidates.append(f"{city}, Ghana")

    return json.dumps(candidates, ensure_ascii=False)


def run_address_extraction(df: pd.DataFrame) -> pd.DataFrame:
    """Extract and build ranked geo_queries column.

    Adds column: geo_queries (JSON array of candidate query strings).

    Args:
        df: DataFrame (output of heuristic steps 1-3).

    Returns:
        DataFrame with the new geo_queries column.
    """
    df = df.copy()

    df["geo_queries"] = df.apply(_build_geo_queries, axis=1)

    # Log stats
    n_candidates = df["geo_queries"].apply(lambda s: len(json.loads(s)))
    logger.info(
        "Step 3.5 complete: built geo_queries for %d facilities "
        "(avg %.1f candidates/facility, max %d)",
        len(df),
        n_candidates.mean(),
        n_candidates.max(),
    )

    return df
