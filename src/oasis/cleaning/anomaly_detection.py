"""Anomaly detection for VF Ghana healthcare facility data.

Adds an `anomaly_desc` column to the cleaned DataFrame:
  - None if no anomaly detected
  - A human-readable description of the anomaly if one was found

Rule-based checks:
  1. Type-Service Mismatch (pharmacy claiming surgery, dentist claiming cardiology)
  2. Advanced procedures with no equipment listed
  3. Many specialties but zero supporting evidence (procedures + equipment)
  4. Hospital with essentially zero medical information
  5. Claims imaging services but lists no equipment
  6. Self-contradictory operating hours (24/7 AND limited hours)
  7. Marketing overstatement without substance (vague superlatives, no specifics)

Embedding-based checks (requires sentence-transformers):
  8. Peer-group outliers — capability profile unlike others of the same type
  9. Near-duplicate profiles — different facilities with nearly identical text
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from oasis.cleaning.column_cleaning import safe_parse_list

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Rule-based anomaly detection
# ══════════════════════════════════════════════════════════════════════

# Keywords that indicate surgical/advanced procedures
_SURGICAL_KEYWORDS = re.compile(
    r"\b(surger|surgical|surgery|appendectom|cesarean|c-section|"
    r"laparoscop|arthroscop|craniotom|transplant|amputation|"
    r"open.?heart|bypass|angioplast|mastectom|hysterectom|"
    r"operating\s*(theatre|theater|room)|"
    r"major\s*operation|minor\s*operation)\b",
    re.IGNORECASE,
)

_IMAGING_KEYWORDS = re.compile(
    r"\b(MRI|CT\s*scan|X-ray|ultrasound|fluoroscop|mammograph|"
    r"echocardiogra|angiograph|PET\s*scan|DEXA|bone\s*densit)\b",
    re.IGNORECASE,
)

# Marketing / overstatement language — vague superlatives without specifics
_MARKETING_KEYWORDS = re.compile(
    r"\b(?:state[\s-]of[\s-]the[\s-]art|ultra[\s-]?modern|world[\s-]?class|"
    r"cutting[\s-]?edge|first[\s-]?class|top[\s-]?notch|"
    r"unmatched|unparalleled|premier[e]?|renowned|prestigious|"
    r"voted\s+best|best\s+(?:hospital|clinic|eye|dental)|"
    r"internationally\s+(?:recognized|acclaimed)|"
    r"most\s+advanced|exceptional\s+care)\b",
    re.IGNORECASE,
)

# Concrete equipment: entries that name a specific device, machine, or system
# (as opposed to vague "ultramodern equipment" or "state-of-the-art technology")
_CONCRETE_EQUIPMENT = re.compile(
    r"\b(MRI|CT\s*scan|X-ray|ultrasound|ventilator|defibrillat|"
    r"autoclave|incubator|microscop|centrifuge|ECG|EKG|"
    r"anesthesia\s*machine|monitor|infusion\s*pump|"
    r"Siemens|GE\s+Health|Philips|Mindray|Olympus|"
    r"phacoemulsification|fundus|gonioscop|OCT|"
    r"dialysis|oxygen\s*(plant|generat|concentrat)|"
    r"laparoscop|endoscop|colonoscop|bronchoscop|"
    r"mammograph|fluoroscop|C-arm|linear\s*accelerat|"
    r"blood\s*bank|laboratory|laminar\s*flow)\b",
    re.IGNORECASE,
)

# Specialties that a pharmacy should NOT have
_NON_PHARMACY_SPECIALTIES = {
    "generalSurgery", "cardiology", "neurology", "oncology",
    "orthopedics", "orthopedicSurgery", "neurosurgery",
    "cardiothoracicSurgery", "plasticSurgery", "urology",
    "obstetricsAndGynecology", "vascularSurgery", "thoracicSurgery",
    "pediatricSurgery", "traumaSurgery", "transplantSurgery",
    "emergencyMedicine", "criticalCareMedicine",
}

# Specialties that are NOT dental
_NON_DENTAL_SPECIALTIES = {
    "generalSurgery", "cardiology", "neurology", "oncology",
    "orthopedics", "obstetricsAndGynecology", "pediatrics",
    "internalMedicine", "emergencyMedicine", "criticalCareMedicine",
    "nephrology", "gastroenterology", "pulmonology", "endocrinology",
    "rheumatology", "hematology", "infectiousDiseases",
    "neurosurgery", "cardiothoracicSurgery",
}


def _detect_anomalies_for_row(
    name: str,
    facility_type: str | None,
    specialties: list[str],
    procedures: list[str],
    equipment: list[str],
    capabilities: list[str],
    capacity: float | None,
    num_doctors: float | None,
) -> str | None:
    """Run all rule-based anomaly checks on a single facility."""
    anomalies: list[str] = []

    # Join text for keyword searches
    proc_text = " ".join(procedures).lower()
    equip_text = " ".join(equipment).lower()
    cap_text = " ".join(capabilities).lower()
    all_text = f"{proc_text} {equip_text} {cap_text}"

    num_specialties = len(specialties)
    num_procedures = len(procedures)
    num_equipment = len(equipment)
    num_capabilities = len(capabilities)

    ft = (facility_type or "").lower().strip()

    # ── Rule 1: Pharmacy claiming surgery or advanced specialties ─────
    if ft == "pharmacy":
        pharmacy_bad_specs = [s for s in specialties if s in _NON_PHARMACY_SPECIALTIES]
        if pharmacy_bad_specs:
            anomalies.append(
                f"Pharmacy claims advanced specialties not typical for pharmacies: "
                f"{', '.join(pharmacy_bad_specs)}"
            )
        if _SURGICAL_KEYWORDS.search(all_text):
            anomalies.append(
                "Pharmacy claims surgical procedures or capabilities, "
                "which is inconsistent with a pharmacy facility type"
            )


    # ── Rule 2: Dentist claiming non-dental specialties ───────────────
    if ft == "dentist":
        dentist_bad_specs = [s for s in specialties if s in _NON_DENTAL_SPECIALTIES]
        if dentist_bad_specs:
            anomalies.append(
                f"Dental facility claims non-dental specialties: "
                f"{', '.join(dentist_bad_specs)}"
            )


    # ── Rule 3: Claims surgery but lists zero equipment ───────────────
    if _SURGICAL_KEYWORDS.search(all_text) and num_equipment == 0:
        anomalies.append(
            "Claims surgical procedures/capabilities but has no equipment listed — "
            "may indicate unverified or aspirational claims"
        )


    # ── Rule 4: Many specialties but no supporting evidence ───────────
    if num_specialties >= 6 and num_procedures == 0 and num_equipment == 0:
        anomalies.append(
            f"Claims {num_specialties} specialties but has zero procedures "
            f"and zero equipment listed — breadth of claims lacks supporting evidence"
        )


    # ── Rule 5: Hospital with essentially no medical info ─────────────
    if ft == "hospital" and num_procedures == 0 and num_equipment == 0 and num_capabilities == 0:
        if num_specialties <= 1:
            anomalies.append(
                "Hospital with virtually no medical information — "
                "no procedures, no equipment, no capabilities, "
                "and at most 1 specialty listed"
            )


    # ── Rule 6: Claims advanced imaging in procedures but not in equipment ──
    if num_procedures > 0 and num_equipment == 0:
        imaging_in_proc = _IMAGING_KEYWORDS.findall(proc_text)
        if imaging_in_proc:
            unique_imaging = list(set(m.upper() for m in imaging_in_proc))
            anomalies.append(
                f"Claims imaging services ({', '.join(unique_imaging[:3])}) in procedures "
                f"but lists no equipment at all — equipment should support these claims"
            )


    # ── Rule 7: Contradictory operating hours ─────────────────────────
    has_24_7 = bool(re.search(r"\b(24.?hour|24/7|always open)\b", cap_text, re.IGNORECASE))
    has_limited = bool(re.search(
        r"\b(mon|tue|wed|thu|fri|sat|sun)\b.{0,20}\b\d{1,2}\s*[ap]m\b",
        cap_text, re.IGNORECASE,
    ))
    if has_24_7 and has_limited:
        anomalies.append(
            "Contradictory operating hours — claims 24/7 or always open "
            "but also lists specific limited weekday hours"
        )


    # ── Rule 8: Marketing overstatement without substance ─────────────
    marketing_hits = _MARKETING_KEYWORDS.findall(all_text)
    if marketing_hits:
        num_marketing = len(marketing_hits)
        has_concrete_equip = bool(_CONCRETE_EQUIPMENT.search(equip_text))
        # Case A: heavy marketing (2+) with no concrete equipment at all
        if num_marketing >= 2 and not has_concrete_equip:
            unique_phrases = sorted(set(h.lower() for h in marketing_hits))
            anomalies.append(
                f"Uses {num_marketing} marketing superlatives "
                f"({', '.join(unique_phrases[:4])}) but lists no concrete "
                f"equipment or devices to substantiate claims — "
                f"potential overstatement"
            )
        # Case B: marketing language + zero procedures AND zero equipment
        elif num_marketing >= 1 and num_procedures == 0 and num_equipment == 0:
            unique_phrases = sorted(set(h.lower() for h in marketing_hits))
            anomalies.append(
                f"Marketing language ({', '.join(unique_phrases[:3])}) with "
                f"no procedures and no equipment listed — claims lack "
                f"verifiable evidence"
            )

    if not anomalies:
        return None
    return "; ".join(anomalies)



# ══════════════════════════════════════════════════════════════════════
# Embedding-based anomaly detection
# ══════════════════════════════════════════════════════════════════════

_MODEL_NAME = "all-MiniLM-L6-v2"
_FREEFORM_COLUMNS = ("procedure", "equipment", "capability")

# Thresholds (tuned on the VF Ghana dataset)
_OUTLIER_PERCENTILE = 5          # bottom 5% similarity → outlier
_OUTLIER_ABS_THRESHOLD = 0.15    # also must be below this absolute sim
_DUPLICATE_THRESHOLD = 0.97      # cosine sim ≥ 0.97 → near-duplicate
_MIN_GROUP_SIZE = 5              # skip peer-group check for tiny groups


def _build_text(row: pd.Series) -> str:
    """Concatenate free-form columns into a single string for embedding."""
    parts: list[str] = []
    for col in _FREEFORM_COLUMNS:
        items = safe_parse_list(row.get(col))
        parts.extend(items)
    return " | ".join(parts) if parts else ""


def _detect_peer_outliers(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    texts: list[str],
) -> dict[int, str]:
    """Flag facilities whose embedding is far from their facility-type centroid."""
    if "facilityTypeId" not in df.columns:
        return {}

    anomalies: dict[int, str] = {}

    type_groups: dict[str, list[int]] = {}
    for i, (idx, row) in enumerate(df.iterrows()):
        ft = row.get("facilityTypeId")
        if pd.notna(ft) and str(ft).strip():
            ft_str = str(ft).strip().lower()
            type_groups.setdefault(ft_str, []).append(i)

    for ft, indices in type_groups.items():
        if len(indices) < _MIN_GROUP_SIZE:
            continue

        valid = [i for i in indices if texts[i].strip()]
        if len(valid) < _MIN_GROUP_SIZE:
            continue

        group_embs = embeddings[valid]
        centroid = group_embs.mean(axis=0)
        centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)

        sims = group_embs @ centroid_norm

        percentile_cutoff = float(np.percentile(sims, _OUTLIER_PERCENTILE))
        threshold = min(percentile_cutoff, _OUTLIER_ABS_THRESHOLD)

        for j, sim in enumerate(sims):
            if sim < threshold:
                orig_idx = valid[j]
                df_idx = df.index[orig_idx]
                anomalies[df_idx] = (
                    f"Capability profile is an outlier among {ft}s "
                    f"(similarity to peer group: {sim:.2f}) — "
                    f"this {ft}'s described services are unlike other {ft}s in the dataset"
                )

    return anomalies


def _detect_near_duplicates(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    texts: list[str],
) -> dict[int, str]:
    """Flag facility pairs with nearly identical free-form text."""
    anomalies: dict[int, str] = {}

    has_text = [i for i in range(len(embeddings)) if texts[i].strip()]
    if len(has_text) < 2:
        return {}

    sub_embs = embeddings[has_text]
    sim_matrix = sub_embs @ sub_embs.T

    seen_pairs: set[tuple[int, int]] = set()

    for a_local in range(len(has_text)):
        for b_local in range(a_local + 1, len(has_text)):
            if sim_matrix[a_local, b_local] >= _DUPLICATE_THRESHOLD:
                a_orig = has_text[a_local]
                b_orig = has_text[b_local]

                id_a = df.iloc[a_orig].get("pk_unique_id")
                id_b = df.iloc[b_orig].get("pk_unique_id")
                if id_a == id_b:
                    continue

                pair = (min(a_orig, b_orig), max(a_orig, b_orig))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                name_a = df.iloc[a_orig].get("name", "?")
                name_b = df.iloc[b_orig].get("name", "?")
                sim_val = float(sim_matrix[a_local, b_local])

                idx_a = df.index[a_orig]
                idx_b = df.index[b_orig]

                desc_a = (
                    f"Near-duplicate capability profile with '{name_b}' "
                    f"(ID {id_b}, similarity: {sim_val:.2f}) — "
                    f"may indicate duplicated or copy-pasted data"
                )
                desc_b = (
                    f"Near-duplicate capability profile with '{name_a}' "
                    f"(ID {id_a}, similarity: {sim_val:.2f}) — "
                    f"may indicate duplicated or copy-pasted data"
                )

                anomalies.setdefault(idx_a, "")
                if anomalies[idx_a]:
                    anomalies[idx_a] += "; " + desc_a
                else:
                    anomalies[idx_a] = desc_a

                anomalies.setdefault(idx_b, "")
                if anomalies[idx_b]:
                    anomalies[idx_b] += "; " + desc_b
                else:
                    anomalies[idx_b] = desc_b

    return anomalies


def _run_embedding_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Run embedding-based anomaly detection (peer outliers + near-duplicates).

    Merges results into the existing `anomaly_desc` column.
    Gracefully skips if sentence-transformers is not installed.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning(
            "sentence-transformers not installed — skipping embedding-based "
            "anomaly detection. Install with: pip install sentence-transformers"
        )
        return df

    texts = [_build_text(row) for _, row in df.iterrows()]

    logger.info("Computing embeddings for %d facilities...", len(texts))
    model = SentenceTransformer(_MODEL_NAME)
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    logger.info("Embeddings computed (%d × %d)", *embeddings.shape)

    outlier_anomalies = _detect_peer_outliers(df, embeddings, texts)
    duplicate_anomalies = _detect_near_duplicates(df, embeddings, texts)

    new_flags = 0
    for anomaly_dict in (outlier_anomalies, duplicate_anomalies):
        for idx, desc in anomaly_dict.items():
            existing = df.at[idx, "anomaly_desc"]
            if existing and pd.notna(existing):
                df.at[idx, "anomaly_desc"] = f"{existing}; {desc}"
            else:
                df.at[idx, "anomaly_desc"] = desc
                new_flags += 1

    total_flagged = df["anomaly_desc"].notna().sum()
    logger.info(
        "Embedding checks: %d outliers, %d near-duplicate entries, "
        "%d new facilities flagged (%d total flagged)",
        len(outlier_anomalies),
        len(duplicate_anomalies),
        new_flags,
        total_flagged,
    )

    return df



# ══════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════

def run_anomaly_detection(df: pd.DataFrame) -> pd.DataFrame:
    """Run all anomaly detection on the cleaned DataFrame.

    1. Rule-based checks (per-row heuristics)
    2. Embedding-based checks (peer-group outliers + near-duplicates)

    Adds an `anomaly_desc` column (None if clean, description string if flagged).

    Returns the DataFrame with the new column.
    """
    # ── Phase 1: Rule-based detection ─────────────────────────────────
    anomaly_descs: list[str | None] = []
    rule_count = 0

    for _, row in df.iterrows():
        name = str(row.get("name", ""))
        facility_type = row.get("facilityTypeId")
        if pd.isna(facility_type):
            facility_type = None

        specialties = safe_parse_list(row.get("specialties"))
        procedures = safe_parse_list(row.get("procedure"))
        equipment = safe_parse_list(row.get("equipment"))
        capabilities = safe_parse_list(row.get("capability"))

        cap_val = row.get("capacity")
        capacity = float(cap_val) if cap_val is not None and not pd.isna(cap_val) else None

        doc_val = row.get("numberDoctors")
        num_doctors = float(doc_val) if doc_val is not None and not pd.isna(doc_val) else None

        desc = _detect_anomalies_for_row(
            name=name,
            facility_type=facility_type,
            specialties=specialties,
            procedures=procedures,
            equipment=equipment,
            capabilities=capabilities,
            capacity=capacity,
            num_doctors=num_doctors,
        )
        anomaly_descs.append(desc)
        if desc is not None:
            rule_count += 1

    df["anomaly_desc"] = anomaly_descs

    logger.info(
        "Rule-based detection: %d/%d facilities flagged",
        rule_count,
        len(df),
    )

    # ── Phase 2: Embedding-based detection ────────────────────────────
    df = _run_embedding_checks(df)

    return df
