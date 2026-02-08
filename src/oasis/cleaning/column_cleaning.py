"""Clean junk entries from free-form list columns (capability, procedure, equipment).

The VF Ghana dataset was scraped from various websites (LinkedIn, Facebook, hospital
pages, directories). The extraction grabbed everything — addresses, phone numbers,
social-media metadata — and dumped it into free-form columns alongside real medical
data. This module removes that junk using regex pattern matching.

This is a fallback for when LLM-based extraction (llm_extraction.py) is unavailable (e.g., API credits exhausted).
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Capability junk patterns ─────────────────────────────────────────
# These patterns identify entries in the capability column that are NOT
# medical capabilities but rather address/contact/meta information that
# leaked in from web scraping.

_CAPABILITY_JUNK_PATTERNS: list[re.Pattern] = [
    # Location / address
    re.compile(r"^Located\b", re.IGNORECASE),
    re.compile(r"^Has a location at\b", re.IGNORECASE),
    re.compile(r"^Location:", re.IGNORECASE),
    re.compile(r"^Primary location:", re.IGNORECASE),
    re.compile(r"^Headquarters:", re.IGNORECASE),
    re.compile(r"^Street address:", re.IGNORECASE),
    re.compile(r"^Address:", re.IGNORECASE),
    re.compile(r"^P\.?O\.?\s*Box\b", re.IGNORECASE),
    # Contact info
    re.compile(r"^Phone:", re.IGNORECASE),
    re.compile(r"^Telephone:", re.IGNORECASE),
    re.compile(r"^Contact number:", re.IGNORECASE),
    re.compile(r"^Email:", re.IGNORECASE),
    re.compile(r"^Website:", re.IGNORECASE),
    re.compile(r"^Fax:", re.IGNORECASE),
    # LinkedIn / Facebook / social media metadata
    re.compile(r"^Company size:", re.IGNORECASE),
    re.compile(r"^Type:\s*(Nonprofit|Public|Private|Company)", re.IGNORECASE),
    re.compile(r"^Industry:", re.IGNORECASE),
    re.compile(r"^Founded\b", re.IGNORECASE),
    re.compile(r"^Specialties:", re.IGNORECASE),  # duplicates specialties column
    re.compile(r"^Mission:", re.IGNORECASE),
    re.compile(r"^Vision:", re.IGNORECASE),
    re.compile(r"^Page created\b", re.IGNORECASE),
    re.compile(r"^Has \d+ (likes|followers|check-ins)", re.IGNORECASE),
    re.compile(r"^Is an unofficial page\b", re.IGNORECASE),
    re.compile(r"^Is categorized as\b", re.IGNORECASE),
    re.compile(r"^Page shows\b", re.IGNORECASE),
    re.compile(r"^Registered with\b", re.IGNORECASE),
    re.compile(r"^Listed (as|in|on)\b", re.IGNORECASE),
    re.compile(r"^Listed categories:", re.IGNORECASE),
    # Generic non-medical
    re.compile(r"^Managed by\b", re.IGNORECASE),
    re.compile(r"^Established in\b", re.IGNORECASE),
]

# Lighter junk patterns for procedure/equipment columns (less polluted)
_PROCEDURE_EQUIPMENT_JUNK: list[re.Pattern] = [
    re.compile(r"^Located\b", re.IGNORECASE),
    re.compile(r"^Phone:", re.IGNORECASE),
    re.compile(r"^Email:", re.IGNORECASE),
    re.compile(r"^Address:", re.IGNORECASE),
    re.compile(r"^Contact\b", re.IGNORECASE),
    re.compile(r"^Website:", re.IGNORECASE),
]


# ── Helpers ──────────────────────────────────────────────────────────

def safe_parse_list(raw: Any) -> list[str]:
    """Parse a cell value that looks like a Python list literal into an actual list.

    Handles: Python list literals ['a', 'b'], JSON arrays, null, NaN,
    empty strings, "[]", "nan", "None", "null", and malformed strings.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if s in ("", "[]", "nan", "None", "null"):
        return []
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [str(parsed).strip()] if str(parsed).strip() else []
    except (ValueError, SyntaxError):
        return [s] if s else []


def list_to_csv_str(items: list[str]) -> str:
    """Convert a list back to a string representation for CSV storage."""
    if not items:
        return "[]"
    return str(items)


def _is_junk_capability(entry: str) -> bool:
    """Return True if a capability entry is address/contact/meta junk."""
    s = entry.strip()
    for pat in _CAPABILITY_JUNK_PATTERNS:
        if pat.search(s):
            return True
    return False


def _is_junk_proc_equip(entry: str) -> bool:
    """Return True if a procedure/equipment entry is address/contact junk."""
    s = entry.strip()
    for pat in _PROCEDURE_EQUIPMENT_JUNK:
        if pat.search(s):
            return True
    return False


# ── Public API ────────────────────────────────────────────────────────

def clean_freeform_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove address/contact/meta junk from capability, procedure, and equipment columns.

    The capability column is the most polluted (addresses, phone numbers, LinkedIn
    metadata, etc.). Procedure and equipment columns get a lighter cleaning pass.

    Returns a copy of the DataFrame with cleaned columns.
    """
    df = df.copy()

    if "capability" in df.columns:
        before_total = 0
        after_total = 0

        def _clean_cap(raw):
            nonlocal before_total, after_total
            items = safe_parse_list(raw)
            before_total += len(items)
            cleaned = [item for item in items if not _is_junk_capability(item)]
            after_total += len(cleaned)
            return list_to_csv_str(cleaned)

        df["capability"] = df["capability"].apply(_clean_cap)
        logger.info(
            "Capability cleaning: removed %d junk entries, kept %d",
            before_total - after_total,
            after_total,
        )

    for col in ("procedure", "equipment"):
        if col in df.columns:
            def _clean_col(raw):
                items = safe_parse_list(raw)
                cleaned = [item for item in items if not _is_junk_proc_equip(item)]
                return list_to_csv_str(cleaned)

            df[col] = df[col].apply(_clean_col)

    return df

