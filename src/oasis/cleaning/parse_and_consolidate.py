"""Parse, consolidate, and pre-filter raw facility data.

Sub-steps (all part of pipeline Step 1):
  1.1: Parse & Standardize: JSON-parse list columns, normalize empties, fix typos.
  1.2: Row Consolidation: merge multi-row facilities into one row per pk_unique_id.
  1.3: Light Pre-Filter: remove structurally non-medical entries
       (bare phone numbers, bare URLs/emails, bare numeric values).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Column constants ──────────────────────────────────────────────────
LIST_COLUMNS = ("specialties", "procedure", "equipment", "capability")

SCALAR_COLUMNS_PREFER_FIRST = (
    "name",
    "facilityTypeId",
    "operatorTypeId",
    "organization_type",
    "source_url",
    "mongo DB",
    "content_table_id",
    "phone_numbers",
    "email",
    "websites",
    "officialWebsite",
    "yearEstablished",
    "acceptsVolunteers",
    "facebookLink",
    "twitterLink",
    "linkedinLink",
    "instagramLink",
    "logo",
    "address_line1",
    "address_line2",
    "address_line3",
    "address_city",
    "address_stateOrRegion",
    "address_zipOrPostcode",
    "address_country",
    "address_countryCode",
    "countries",
    "missionStatement",
    "missionStatementLink",
    "organizationDescription",
    "affiliationTypeIds",
    "area",
    "numberDoctors",
    "capacity",
    "unique_id",
)

# Address columns that should use most-frequent value during consolidation
# (instead of first-non-null) for better accuracy.
ADDRESS_COLUMNS_MOST_FREQUENT = {
    "address_line1",
    "address_line2",
    "address_line3",
    "address_city",
    "address_stateOrRegion",
    "address_zipOrPostcode",
    "address_country",
    "address_countryCode",
}

DESCRIPTION_COLUMNS = ("description",)

# Typo corrections for facilityTypeId
FACILITY_TYPE_TYPOS = {
    "farmacy": "pharmacy",
}

# ── Step 2 helpers ────────────────────────────────────────────────────

def _parse_json_list(raw: Any) -> list[str]:
    """Parse a raw cell value into a list of strings.

    Handles: JSON arrays like '["a","b"]', null, NaN, empty string, "null", "[]".
    Returns a (possibly empty) Python list of stripped strings.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if s in ("", "null", "[]", "None"):
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        # Single scalar value in JSON
        return [str(parsed).strip()] if str(parsed).strip() else []
    except (json.JSONDecodeError, TypeError):
        # Not JSON -- treat as a single raw text entry
        return [s] if s else []


def parse_and_standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1.1: Parse JSON arrays, normalize empties, fix typos, strip whitespace."""
    df = df.copy()

    # Parse list columns into actual Python lists
    for col in LIST_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(_parse_json_list)

    # Fix facilityTypeId typos
    if "facilityTypeId" in df.columns:
        df["facilityTypeId"] = (
            df["facilityTypeId"]
            .apply(lambda v: None if pd.isna(v) or str(v).strip() in ("", "null", "None") else str(v).strip())
            .map(lambda v: FACILITY_TYPE_TYPOS.get(v, v) if v else v)
        )

    # Normalize operatorTypeId empties
    if "operatorTypeId" in df.columns:
        df["operatorTypeId"] = df["operatorTypeId"].apply(
            lambda v: None if pd.isna(v) or str(v).strip() in ("", "null", "None") else str(v).strip()
        )

    # Strip whitespace from string scalar columns
    for col in SCALAR_COLUMNS_PREFER_FIRST:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: str(v).strip() if not pd.isna(v) and str(v).strip() not in ("", "null", "None") else None
            )

    for col in DESCRIPTION_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: str(v).strip() if not pd.isna(v) and str(v).strip() not in ("", "null", "None") else None
            )

    logger.info("Step 2 complete: parsed JSON arrays and standardized %d rows", len(df))
    return df


# ── Step 1 helpers ────────────────────────────────────────────────────

# Regex heuristic to deprioritize address-like names
_ADDRESS_LIKE = re.compile(
    r"\b(Rd|Road|St|Street|Ave|Avenue|Ghana|Accra)\b|^\d+[/,]", re.IGNORECASE
)


def _pick_best_name(names: list[str | None]) -> str | None:
    """Pick the best name for a facility from a list of candidates.

    Prefers names that don't look like addresses.
    """
    valid = [n for n in names if n is not None]
    if not valid:
        return None
    # Prefer names without address-like patterns
    non_address = [n for n in valid if not _ADDRESS_LIKE.search(n)]
    if non_address:
        return non_address[0]
    return valid[0]


def _first_non_null(values: list[Any]) -> Any:
    """Return the first non-null value from a list."""
    for v in values:
        if v is not None:
            return v
    return None


def _most_frequent(values: list[Any]) -> Any:
    """Return the most frequent non-null value from a list.

    Ties are broken by first occurrence order.
    Falls back to first non-null if all values are unique.
    """
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    from collections import Counter
    counts = Counter(non_null)
    # most_common returns [(value, count), ...] in order of count
    return counts.most_common(1)[0][0]


def _union_lists(list_of_lists: list[list[str]]) -> list[str]:
    """Union multiple lists with case-insensitive deduplication.

    Preserves the original casing of the first occurrence.
    """
    seen: dict[str, str] = {}  # lowercase -> original
    for lst in list_of_lists:
        for item in lst:
            key = item.lower()
            if key not in seen:
                seen[key] = item
    return list(seen.values())


def _concat_unique_descriptions(descs: list[str | None]) -> str | None:
    """Concatenate unique non-null descriptions."""
    valid = [d for d in descs if d is not None]
    if not valid:
        return None
    # Deduplicate by exact match
    seen: set[str] = set()
    unique: list[str] = []
    for d in valid:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return " ".join(unique) if unique else None


def consolidate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1.2: Group by pk_unique_id and merge into one row per facility."""
    if "pk_unique_id" not in df.columns:
        logger.warning("No 'pk_unique_id' column -- skipping consolidation")
        return df

    before = len(df)
    groups = df.groupby("pk_unique_id", sort=False)

    rows: list[dict[str, Any]] = []
    for pk_id, group in groups:
        row: dict[str, Any] = {"pk_unique_id": pk_id}

        # Name: pick best
        row["name"] = _pick_best_name(group["name"].tolist() if "name" in group.columns else [])

        # Scalar fields: first non-null (or most-frequent for address columns)
        for col in SCALAR_COLUMNS_PREFER_FIRST:
            if col in ("name",):
                continue  # already handled
            if col in group.columns:
                if col in ADDRESS_COLUMNS_MOST_FREQUENT:
                    row[col] = _most_frequent(group[col].tolist())
                else:
                    row[col] = _first_non_null(group[col].tolist())

        # List fields: union
        for col in LIST_COLUMNS:
            if col in group.columns:
                row[col] = _union_lists(group[col].tolist())
            else:
                row[col] = []

        # Description: concatenate unique
        for col in DESCRIPTION_COLUMNS:
            if col in group.columns:
                row[col] = _concat_unique_descriptions(group[col].tolist())

        rows.append(row)

    result = pd.DataFrame(rows)
    logger.info(
        "Step 1 complete: consolidated %d rows -> %d facilities",
        before,
        len(result),
    )
    return result


# ── Step 3: Light Universal Pre-Filter ────────────────────────────────

# Bare phone number: optional +, then digits/spaces/dashes/parens only
_BARE_PHONE = re.compile(
    r"^\+?[\d\s\-().]{6,20}$"
)

# Bare URL: starts with http(s):// or www. and has no other text surrounding it
_BARE_URL = re.compile(
    r"^(https?://|www\.)\S+$", re.IGNORECASE
)

# Bare email
_BARE_EMAIL = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Bare numeric: just digits, commas, dots, optional percent/unit
_BARE_NUMERIC = re.compile(
    r"^[\d,.\s]+(%|km|m|kg|lb|ft)?$"
)


def _is_structural_junk(entry: str) -> bool:
    """Return True if the entry is structurally non-medical (no natural language)."""
    s = entry.strip()
    if not s:
        return True
    if _BARE_PHONE.match(s):
        return True
    if _BARE_URL.match(s):
        return True
    if _BARE_EMAIL.match(s):
        return True
    if _BARE_NUMERIC.match(s):
        return True
    return False


def light_prefilter(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1.3: Remove structurally non-medical entries from list columns.

    Only strips entries that contain zero natural language (bare phone numbers,
    bare URLs/emails, bare numeric values). Everything else passes through to
    the LLM for semantic classification.
    """
    df = df.copy()
    total_removed = 0
    total_kept = 0

    for col in LIST_COLUMNS:
        if col not in df.columns:
            continue

        def _filter_list(items: list[str]) -> list[str]:
            return [item for item in items if not _is_structural_junk(item)]

        before_counts = df[col].apply(len).sum()
        df[col] = df[col].apply(_filter_list)
        after_counts = df[col].apply(len).sum()
        removed = before_counts - after_counts
        total_removed += removed
        total_kept += after_counts

    logger.info(
        "Step 3 complete: removed %d structural-junk entries, kept %d",
        total_removed,
        total_kept,
    )
    return df


# ── Public orchestrator ───────────────────────────────────────────────

def run_heuristic_steps(df: pd.DataFrame) -> pd.DataFrame:
    """Run parse and consolidate steps in order.
    """
    df = parse_and_standardize(df)  # Step 1
    df = consolidate_rows(df)  # Step 2
    df = light_prefilter(df)  # Step 3
    return df

