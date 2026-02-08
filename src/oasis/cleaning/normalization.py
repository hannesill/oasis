"""Embedding-based synonym normalization — NOT used in the current pipeline.

Depends on llm_extraction.py (for VALID_SPECIALTIES), which requires
OpenAI API credits that were unavailable. Kept for future use.

Uses sentence-transformers (all-MiniLM-L6-v2) to:
1. Cluster synonymous terms in procedure/equipment/capability columns.
2. Replace cluster members with a canonical representative.
3. Validate specialties against the exact enum via embedding similarity.
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Re-use the valid specialties list from llm_extraction
from oasis.cleaning.llm_extraction import VALID_SPECIALTIES

# ── Embedding helpers ─────────────────────────────────────────────────

_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model():
    """Load the sentence-transformer model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required for synonym normalization. "
            "Install with: pip install sentence-transformers"
        )
    return SentenceTransformer(_MODEL_NAME)


def _embed(model, texts: list[str]) -> np.ndarray:
    """Embed a list of texts, returning normalized vectors."""
    if not texts:
        return np.array([])
    return model.encode(texts, show_progress_bar=False, normalize_embeddings=True)


# ── Synonym clustering ────────────────────────────────────────────────


def _cluster_synonyms(
    terms: list[str],
    embeddings: np.ndarray,
    threshold: float = 0.85,
) -> dict[str, str]:
    """Cluster terms by cosine similarity and pick canonical representatives.

    Returns a mapping from each term to its canonical form.
    The canonical form is the shortest term in the cluster (ties broken by
    frequency, then alphabetical order).
    """
    n = len(terms)
    if n == 0:
        return {}

    # Compute pairwise cosine similarity (embeddings are already normalized)
    sim_matrix = embeddings @ embeddings.T

    # Union-Find for clustering
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                union(i, j)

    # Group terms by cluster
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # Pick canonical representative per cluster
    term_to_canonical: dict[str, str] = {}
    for indices in clusters.values():
        cluster_terms = [terms[i] for i in indices]
        # Pick: shortest term, breaking ties by alphabetical
        canonical = min(cluster_terms, key=lambda t: (len(t), t))
        for t in cluster_terms:
            term_to_canonical[t] = canonical

    return term_to_canonical


def _normalize_column_synonyms(
    df: pd.DataFrame,
    col: str,
    model,
    threshold: float = 0.85,
) -> tuple[pd.DataFrame, int]:
    """Normalize synonyms in a single list column.

    Returns the updated DataFrame and the number of replacements made.
    """
    # Collect all unique terms with their frequencies
    term_counter: Counter = Counter()
    for items in df[col]:
        if isinstance(items, list):
            for item in items:
                term_counter[item] += 1

    unique_terms = list(term_counter.keys())
    if len(unique_terms) < 2:
        return df, 0

    # Embed and cluster
    embeddings = _embed(model, unique_terms)
    term_map = _cluster_synonyms(unique_terms, embeddings, threshold)

    # Count how many terms are being remapped to a different canonical
    replacements = sum(1 for t, c in term_map.items() if t != c)
    if replacements == 0:
        return df, 0

    # Apply normalization
    def _normalize(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            canonical = term_map.get(item, item)
            if canonical.lower() not in seen:
                seen.add(canonical.lower())
                result.append(canonical)
        return result

    df = df.copy()
    df[col] = df[col].apply(lambda items: _normalize(items) if isinstance(items, list) else items)

    return df, replacements


# ── Specialty validation ──────────────────────────────────────────────


def _validate_specialties(df: pd.DataFrame, model) -> tuple[pd.DataFrame, int]:
    """Validate and correct specialty names via embedding similarity.

    Maps each specialty entry to the nearest valid specialty from the enum.
    Only remaps if the similarity is above a threshold; otherwise drops.
    """
    if "specialties" not in df.columns:
        return df, 0

    # Collect unique specialty terms currently in the data
    current_terms: set[str] = set()
    for items in df["specialties"]:
        if isinstance(items, list):
            current_terms.update(items)

    if not current_terms:
        return df, 0

    # Filter out terms that are already valid
    invalid_terms = [t for t in current_terms if t not in VALID_SPECIALTIES]
    if not invalid_terms:
        logger.info("All specialty terms are already valid")
        return df, 0

    # Embed invalid terms and valid specialties
    invalid_embeddings = _embed(model, invalid_terms)
    valid_embeddings = _embed(model, VALID_SPECIALTIES)

    # Find best match for each invalid term
    similarity = invalid_embeddings @ valid_embeddings.T  # (n_invalid, n_valid)
    remap: dict[str, str | None] = {}
    for i, term in enumerate(invalid_terms):
        best_idx = int(np.argmax(similarity[i]))
        best_score = float(similarity[i, best_idx])
        if best_score >= 0.7:
            remap[term] = VALID_SPECIALTIES[best_idx]
            logger.debug("Specialty remap: '%s' -> '%s' (%.3f)", term, VALID_SPECIALTIES[best_idx], best_score)
        else:
            remap[term] = None  # Drop: too dissimilar
            logger.debug("Specialty dropped: '%s' (best match: '%.3f')", term, best_score)

    corrections = sum(1 for v in remap.values() if v is not None)

    # Apply remapping
    def _fix_specialties(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item in VALID_SPECIALTIES:
                mapped = item
            else:
                mapped = remap.get(item)
            if mapped and mapped.lower() not in seen:
                seen.add(mapped.lower())
                result.append(mapped)
        return result

    df = df.copy()
    df["specialties"] = df["specialties"].apply(
        lambda items: _fix_specialties(items) if isinstance(items, list) else items
    )

    logger.info(
        "Specialty validation: %d invalid terms, %d remapped, %d dropped",
        len(invalid_terms),
        corrections,
        len(invalid_terms) - corrections,
    )
    return df, corrections


# ── Public orchestrator ──────────────────────────────────────────────

FREEFORM_COLUMNS = ("procedure", "equipment", "capability")


def run_normalization(df: pd.DataFrame, similarity_threshold: float = 0.85) -> pd.DataFrame:
    """Step 6: Normalize synonyms and validate specialties.

    1. Cluster synonymous terms in procedure/equipment/capability.
    2. Replace cluster members with canonical representatives.
    3. Validate specialties against the exact enum.
    """
    model = _load_model()

    total_replacements = 0

    # Synonym normalization for free-form columns
    for col in FREEFORM_COLUMNS:
        if col in df.columns:
            df, replacements = _normalize_column_synonyms(df, col, model, similarity_threshold)
            if replacements:
                logger.info("Step 6: %s -- %d synonym replacements", col, replacements)
            total_replacements += replacements

    # Specialty validation
    df, specialty_corrections = _validate_specialties(df, model)
    total_replacements += specialty_corrections

    logger.info("Step 6 complete: %d total normalizations applied", total_replacements)
    return df

