"""LLM-powered cleaning steps — NOT used in the current pipeline.

OpenAI API credits were unavailable, so these steps are skipped.
The active pipeline (pipeline.py) uses rule-based alternatives instead:
  - Column cleaning (column_cleaning.py) replaces Step 4
  - Heuristic type inference in parse_and_consolidate.py replaces Step 5

If API access is restored, these could be re-integrated for higher quality.

Step 4 -- Content Classification & Reclassification:
    For each facility, the LLM filters irrelevant content, reclassifies
    misplaced entries, and rewrites vague statements.

Step 5 -- Infer Missing Structured Fields:
    Heuristic-first inference of facilityTypeId and operatorTypeId,
    with LLM fallback for ambiguous cases.

Requires: OPENAI_API_KEY environment variable.
Optional: OASIS_LLM_MODEL (default: gpt-4o-mini).
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────

DEFAULT_MODEL = "gpt-4o-mini"

# ── Valid specialty enum (inlined from fdr hierarchy, levels 0+1) ─────

VALID_SPECIALTIES: list[str] = [
    "internalMedicine",
    "familyMedicine",
    "pediatrics",
    "generalSurgery",
    "emergencyMedicine",
    "gynecologyAndObstetrics",
    "dentistry",
    "ophthalmology",
    "radiology",
    "pathology",
    "anesthesia",
    "cardiology",
    "nephrology",
    "endocrinologyAndDiabetesAndMetabolism",
    "infectiousDiseases",
    "geriatricsInternalMedicine",
    "hospiceAndPalliativeInternalMedicine",
    "medicalOncology",
    "criticalCareMedicine",
    "orthopedicSurgery",
    "plasticSurgery",
    "cardiacSurgery",
    "otolaryngology",
    "neonatologyPerinatalMedicine",
    "physicalMedicineAndRehabilitation",
    "orthodontics",
    "publicHealth",
    "socialAndBehavioralSciences",
    "maternalFetalMedicineOrPerinatology",
    "neurology",
    "dermatology",
    "urology",
    "psychiatry",
    "pulmonology",
    "gastroenterology",
    "rheumatology",
    "hematology",
    "allergyAndImmunology",
    "nuclearMedicine",
]

# ── Pydantic output models ───────────────────────────────────────────


class CleanedFacilityContent(BaseModel):
    """Structured output for Step 4: cleaned facility content."""

    specialties: list[str] = Field(
        default_factory=list,
        description=(
            "Medical specialties. Use EXACT camelCase names from the allowed list. "
            "Only include specialties clearly mentioned or strongly implied."
        ),
    )
    procedure: list[str] = Field(
        default_factory=list,
        description=(
            "Specific clinical services: medical/surgical interventions, diagnostic "
            "procedures, screenings. Each as a clear declarative statement."
        ),
    )
    equipment: list[str] = Field(
        default_factory=list,
        description=(
            "Physical medical devices and infrastructure: imaging machines, surgical "
            "technologies, lab analyzers, critical utilities. Include models when known."
        ),
    )
    capability: list[str] = Field(
        default_factory=list,
        description=(
            "Medical capabilities: trauma levels, specialized units, clinical programs, "
            "accreditations, care settings, staffing, capacity. "
            "EXCLUDE addresses, contact info, business hours, pricing."
        ),
    )


class FacilityTypeInference(BaseModel):
    """Structured output for Step 5: inferred facility type."""

    facilityTypeId: Optional[Literal["hospital", "pharmacy", "doctor", "clinic", "dentist"]] = Field(
        None,
        description="Type of facility. Choose the single best match based on name and context.",
    )
    operatorTypeId: Optional[Literal["public", "private"]] = Field(
        None,
        description="Whether the facility is publicly or privately operated.",
    )


# ── Prompts ──────────────────────────────────────────────────────────

CONTENT_CLEANING_SYSTEM_PROMPT = """\
You are a medical facility data cleaning expert. You receive raw, messy data \
about a healthcare facility and must clean it into structured categories.

TASKS (do all three):
1. FILTER: Remove entries that are NOT medically relevant:
   - Physical addresses, directions, location descriptions
   - Phone numbers, emails, website URLs, social media links/stats
   - Business hours, pricing, insurance info
   - Cross-references to other facilities (e.g., "Listed as related place to X")
   - Generic marketing text with no medical specifics
   EXCEPTION: If an entry mixes relevant and irrelevant info (e.g., "Located at \
Liberation Rd -- offers 24-hour emergency services"), extract ONLY the medical part.

2. RECLASSIFY: Move misplaced entries to the correct category:
   - Specialty names found in capability/procedure → specialties
   - Equipment mentions found in capability → equipment
   - Procedure descriptions found in capability → procedure
   - Capability descriptions found in procedure → capability

3. REWRITE: Normalize entries into clear, declarative statements:
   - Use plain English, present tense
   - Include quantities when available (e.g., "Has 12 ICU beds")
   - Each fact must be self-contained

SPECIALTY NAMES (use EXACT camelCase):
""" + "\n".join(f"- {s}" for s in VALID_SPECIALTIES) + """

CATEGORY DEFINITIONS:
- specialties: Medical specialty areas (from the list above ONLY)
- procedure: Clinical services performed -- surgeries, diagnostic tests, screenings, treatments
- equipment: Physical devices and infrastructure -- imaging machines, surgical tech, lab analyzers, utilities
- capability: Care levels and programs -- trauma levels, specialized units, clinical programs, \
accreditations, care settings, staffing, patient capacity

Return ONLY medically relevant, correctly categorized content.
"""

FIELD_INFERENCE_SYSTEM_PROMPT = """\
You classify healthcare facilities based on their name, description, and capabilities.

facilityTypeId:
- hospital: Full-service healthcare institutions with inpatient beds, emergency departments, \
operating rooms. Includes "Medical Center", "Health Center", "Primary Health Center".
- clinic: Outpatient-focused facilities, smaller practices, specialized clinics. \
Includes "Health Post", "CHPS Compound".
- pharmacy: Drug dispensaries, pharmacies, chemists.
- dentist: Dental practices, dental clinics, orthodontic centers.
- doctor: Individual physician practices, consulting rooms. Look for "Dr." or single-provider names.

operatorTypeId:
- public: Government-run facilities. Indicators: "government", "district", "regional", \
"municipal", "teaching hospital", "polyclinic", "CHPS", "health center" (in Ghana context), \
affiliation with Ghana Health Service.
- private: Privately-owned facilities. Indicators: "private", individual names, \
commercial-sounding names, no government affiliation.

If insufficient evidence for either field, return null for that field.
"""


# ── OpenAI client helper ─────────────────────────────────────────────


def get_openai_client():
    """Create and return an OpenAI client. Raises if OPENAI_API_KEY is not set."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for LLM cleaning steps. "
            "Install it with: pip install openai"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it with: set OPENAI_API_KEY=sk-..."
        )
    return OpenAI(api_key=api_key)


def call_llm_structured(client, system_prompt: str, user_prompt: str, response_model: type[BaseModel], max_retries: int = 3):
    """Call OpenAI with structured output and exponential backoff retry."""
    model = os.environ.get("OASIS_LLM_MODEL", DEFAULT_MODEL)

    for attempt in range(max_retries):
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_model,
            )
            result = completion.choices[0].message.parsed
            # Track token usage
            usage = completion.usage
            if usage:
                logger.debug(
                    "Tokens: %d prompt + %d completion = %d total",
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )
            return result, usage
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 2 ** attempt
                logger.warning("Rate limited, retrying in %ds...", wait)
                time.sleep(wait)
                continue
            if attempt < max_retries - 1:
                logger.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
                time.sleep(1)
                continue
            raise

    raise RuntimeError(f"LLM call failed after {max_retries} retries")


# ── Step 4: Content Classification & Reclassification ─────────────────


def _build_facility_user_prompt(row: pd.Series) -> str:
    """Build the user prompt for a single facility."""
    parts = [f"Facility: {row.get('name', 'Unknown')}"]

    desc = row.get("description")
    if desc:
        parts.append(f"Description: {desc}")

    org_desc = row.get("organizationDescription")
    if org_desc:
        parts.append(f"Organization Description: {org_desc}")

    for col in ("specialties", "procedure", "equipment", "capability"):
        items = row.get(col, [])
        if items:
            parts.append(f"Current {col}: {items}")

    return "\n".join(parts)


def classify_and_reclassify(df: pd.DataFrame) -> pd.DataFrame:
    """Step 4: LLM-based content classification, filtering, and reclassification.

    For each facility, sends all content to the LLM to:
    1. Filter out non-medical entries
    2. Reclassify misplaced entries
    3. Rewrite vague entries into clear statements
    """
    client = get_openai_client()
    df = df.copy()

    total_prompt_tokens = 0
    total_completion_tokens = 0
    processed = 0
    skipped = 0

    for idx in df.index:
        row = df.loc[idx]

        # Skip facilities with no content to clean
        has_content = any(
            len(row.get(col, [])) > 0
            for col in ("specialties", "procedure", "equipment", "capability")
        )
        has_desc = bool(row.get("description")) or bool(row.get("organizationDescription"))

        if not has_content and not has_desc:
            skipped += 1
            continue

        user_prompt = _build_facility_user_prompt(row)

        try:
            result, usage = call_llm_structured(
                client,
                CONTENT_CLEANING_SYSTEM_PROMPT,
                user_prompt,
                CleanedFacilityContent,
            )

            # Validate specialties against allowed list
            result.specialties = [s for s in result.specialties if s in VALID_SPECIALTIES]

            df.at[idx, "specialties"] = result.specialties
            df.at[idx, "procedure"] = result.procedure
            df.at[idx, "equipment"] = result.equipment
            df.at[idx, "capability"] = result.capability

            if usage:
                total_prompt_tokens += usage.prompt_tokens
                total_completion_tokens += usage.completion_tokens

            processed += 1
            if processed % 50 == 0:
                logger.info("Step 4 progress: %d/%d facilities processed", processed, len(df))

        except Exception as e:
            logger.error("Step 4 failed for facility '%s': %s", row.get("name", "?"), e)
            # Keep original data on failure
            continue

    logger.info(
        "Step 4 complete: processed %d, skipped %d (no content). "
        "Tokens: %d prompt + %d completion = %d total",
        processed,
        skipped,
        total_prompt_tokens,
        total_completion_tokens,
        total_prompt_tokens + total_completion_tokens,
    )
    return df


# ── Step 5: Infer Missing Structured Fields ──────────────────────────

# Heuristic patterns for facilityTypeId
_FACILITY_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(hospital|medical cent[er]{2}|health cent[er]{2}|primary health)\b", re.I), "hospital"),
    (re.compile(r"\bpharmac", re.I), "pharmacy"),
    (re.compile(r"\b(dental|dentist|orthodont)", re.I), "dentist"),
    (re.compile(r"\bclinic\b|\bhealth post\b|\bCHPS\b", re.I), "clinic"),
    (re.compile(r"\bDr\.?\s", re.I), "doctor"),
]

# Heuristic patterns for operatorTypeId
_OPERATOR_PUBLIC_PATTERNS = re.compile(
    r"\b(government|public|district|regional|municipal|teaching|polyclinic|"
    r"ghana health service|GHS|CHPS|national)\b",
    re.I,
)
_OPERATOR_PRIVATE_PATTERNS = re.compile(
    r"\b(private|privately)\b",
    re.I,
)


def _heuristic_facility_type(name: str | None) -> str | None:
    """Try to infer facilityTypeId from the facility name."""
    if not name:
        return None
    for pattern, ftype in _FACILITY_TYPE_PATTERNS:
        if pattern.search(name):
            return ftype
    return None


def _heuristic_operator_type(
    name: str | None,
    description: str | None,
    org_description: str | None,
) -> str | None:
    """Try to infer operatorTypeId from name and descriptions."""
    texts = [t for t in (name, description, org_description) if t]
    combined = " ".join(texts)
    if not combined:
        return None
    if _OPERATOR_PUBLIC_PATTERNS.search(combined):
        return "public"
    if _OPERATOR_PRIVATE_PATTERNS.search(combined):
        return "private"
    return None


def infer_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Step 5: Infer missing facilityTypeId and operatorTypeId.

    Uses heuristics first, then falls back to LLM for ambiguous cases.
    """
    df = df.copy()

    # Phase 1: Heuristic inference
    heuristic_facility = 0
    heuristic_operator = 0

    for idx in df.index:
        row = df.loc[idx]

        if row.get("facilityTypeId") is None:
            inferred = _heuristic_facility_type(row.get("name"))
            if inferred:
                df.at[idx, "facilityTypeId"] = inferred
                heuristic_facility += 1

        if row.get("operatorTypeId") is None:
            inferred = _heuristic_operator_type(
                row.get("name"),
                row.get("description"),
                row.get("organizationDescription"),
            )
            if inferred:
                df.at[idx, "operatorTypeId"] = inferred
                heuristic_operator += 1

    logger.info(
        "Step 5 heuristics: inferred %d facilityTypeId, %d operatorTypeId",
        heuristic_facility,
        heuristic_operator,
    )

    # Phase 2: LLM fallback for remaining nulls
    needs_facility = df["facilityTypeId"].isna() if "facilityTypeId" in df.columns else pd.Series(dtype=bool)
    needs_operator = df["operatorTypeId"].isna() if "operatorTypeId" in df.columns else pd.Series(dtype=bool)
    needs_llm = needs_facility | needs_operator
    llm_indices = df.index[needs_llm].tolist()

    if not llm_indices:
        logger.info("Step 5 complete: no LLM calls needed (all fields inferred by heuristics)")
        return df

    try:
        client = get_openai_client()
    except (ImportError, EnvironmentError) as e:
        logger.warning("Step 5: LLM unavailable (%s). %d fields remain null.", e, len(llm_indices))
        return df

    total_prompt_tokens = 0
    total_completion_tokens = 0
    llm_inferred = 0

    for idx in llm_indices:
        row = df.loc[idx]

        parts = [f"Facility: {row.get('name', 'Unknown')}"]
        desc = row.get("description")
        if desc:
            parts.append(f"Description: {desc}")
        org_desc = row.get("organizationDescription")
        if org_desc:
            parts.append(f"Organization Description: {org_desc}")

        # Include capabilities as context
        for col in ("specialties", "capability"):
            items = row.get(col, [])
            if items:
                parts.append(f"{col}: {items}")

        user_prompt = "\n".join(parts)

        try:
            result, usage = call_llm_structured(
                client,
                FIELD_INFERENCE_SYSTEM_PROMPT,
                user_prompt,
                FacilityTypeInference,
            )

            if row.get("facilityTypeId") is None and result.facilityTypeId:
                df.at[idx, "facilityTypeId"] = result.facilityTypeId
            if row.get("operatorTypeId") is None and result.operatorTypeId:
                df.at[idx, "operatorTypeId"] = result.operatorTypeId

            if usage:
                total_prompt_tokens += usage.prompt_tokens
                total_completion_tokens += usage.completion_tokens

            llm_inferred += 1
            if llm_inferred % 50 == 0:
                logger.info("Step 5 LLM progress: %d/%d", llm_inferred, len(llm_indices))

        except Exception as e:
            logger.error("Step 5 LLM failed for '%s': %s", row.get("name", "?"), e)
            continue

    logger.info(
        "Step 5 complete: LLM processed %d facilities. "
        "Tokens: %d prompt + %d completion = %d total",
        llm_inferred,
        total_prompt_tokens,
        total_completion_tokens,
        total_prompt_tokens + total_completion_tokens,
    )

    # Report remaining nulls
    remaining_facility = df["facilityTypeId"].isna().sum() if "facilityTypeId" in df.columns else 0
    remaining_operator = df["operatorTypeId"].isna().sum() if "operatorTypeId" in df.columns else 0
    if remaining_facility or remaining_operator:
        logger.warning(
            "Still null after Step 5: %d facilityTypeId, %d operatorTypeId",
            remaining_facility,
            remaining_operator,
        )

    return df


# ── Public orchestrator ──────────────────────────────────────────────


def run_llm_steps(df: pd.DataFrame) -> pd.DataFrame:
    """Run Steps 4 and 5 in sequence. Requires OPENAI_API_KEY."""
    df = classify_and_reclassify(df)  # Step 4
    df = infer_missing_fields(df)  # Step 5
    return df

