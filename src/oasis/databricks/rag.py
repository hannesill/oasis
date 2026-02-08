"""RAG-powered semantic search over facility free-form text.

Embeds the procedure, equipment, and capability columns from the
VF Ghana dataset and enables semantic similarity search. Embeddings
are computed once and cached to oasis_data/embeddings/vf-ghana.npz.

Falls back to DuckDB keyword search when embeddings unavailable.
"""

import json
import logging
import os
from pathlib import Path

import numpy as np

from oasis.core.backends import get_backend
from oasis.core.datasets import DatasetRegistry

logger = logging.getLogger(__name__)

_engine: "FacilitySearchEngine | None" = None

_FREEFORM_COLUMNS = ("procedure", "equipment", "capability")
_DATA_DIR = Path(os.environ.get("OASIS_DATA_DIR", "oasis_data"))
_CACHE_DIR = _DATA_DIR / "embeddings"
_CACHE_FILE = _CACHE_DIR / "vf-ghana.npz"


# ------------------------------------------------------------------
# Core search engine
# ------------------------------------------------------------------


class FacilitySearchEngine:
    """Lazily-initialized semantic (or keyword) search over facilities."""

    def __init__(self):
        self._texts: list[str] = []
        self._ids: list[str] = []
        self._names: list[str] = []
        self._cities: list[str] = []
        self._embeddings: np.ndarray | None = None
        self._model = None
        self._loaded = False

    def _load_facility_data(self) -> None:
        """Pull free-form text from DuckDB."""
        dataset = DatasetRegistry.get_active()
        backend = get_backend()

        sql = """
            SELECT pk_unique_id, name, address_city,
                   procedure, equipment, capability
            FROM vf.vf_ghana
        """
        result = backend.execute_query(sql, dataset)
        if result.error or result.dataframe is None:
            raise RuntimeError(f"Failed to load facility data: {result.error}")

        for _, row in result.dataframe.iterrows():
            self._ids.append(str(row.get("pk_unique_id", "")))
            self._names.append(str(row.get("name", "")))
            self._cities.append(str(row.get("address_city", "")))

            parts = []
            for col in _FREEFORM_COLUMNS:
                raw = row.get(col)
                if raw and str(raw) not in ("null", "[]", ""):
                    try:
                        items = json.loads(str(raw))
                        if isinstance(items, list):
                            parts.extend(str(i) for i in items)
                        else:
                            parts.append(str(items))
                    except (json.JSONDecodeError, TypeError):
                        parts.append(str(raw))

            self._texts.append(" | ".join(parts) if parts else "")

        logger.info("Loaded %d facilities for RAG", len(self._texts))

    def _load_or_compute_embeddings(self) -> None:
        """Load cached embeddings or compute fresh ones."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.info("sentence-transformers not installed — keyword search only")
            return

        # Try cache first (instant)
        if _CACHE_FILE.exists():
            try:
                self._embeddings = np.load(str(_CACHE_FILE))["embeddings"]
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Loaded cached embeddings (%d vectors)", len(self._embeddings))
                return
            except Exception:
                logger.warning("Cache load failed — recomputing")

        # Compute fresh (takes ~2s on Apple Silicon)
        logger.info("Computing embeddings for %d facilities...", len(self._texts))
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._embeddings = self._model.encode(
            self._texts, show_progress_bar=False, normalize_embeddings=True,
        )

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(str(_CACHE_FILE), embeddings=self._embeddings)
        logger.info("Saved embeddings cache → %s", _CACHE_FILE)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_facility_data()
            self._load_or_compute_embeddings()
            self._loaded = True

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search facilities by semantic similarity or keyword match."""
        self._ensure_loaded()
        if self._embeddings is not None and self._model is not None:
            return self._semantic_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _semantic_search(self, query: str, top_k: int) -> list[dict]:
        """Cosine similarity search."""
        query_emb = self._model.encode([query], normalize_embeddings=True)
        scores = (self._embeddings @ query_emb.T).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]

        results = []
        for i in top_idx:
            if scores[i] < 0.1:
                continue
            results.append({
                "pk_unique_id": self._ids[i],
                "name": self._names[i],
                "city": self._cities[i],
                "relevance_score": round(float(scores[i]), 3),
                "matching_text": self._texts[i][:300],
            })
        return results

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback: DuckDB ILIKE keyword search."""
        dataset = DatasetRegistry.get_active()
        backend = get_backend()

        words = [w.strip() for w in query.split() if len(w.strip()) > 2]
        if not words:
            words = [query]

        word_clauses = []
        for word in words:
            col_clauses = [f"{col} ILIKE '%{word}%'" for col in _FREEFORM_COLUMNS]
            word_clauses.append(f"({' OR '.join(col_clauses)})")

        sql = f"""
            SELECT pk_unique_id, name, address_city,
                   procedure, equipment, capability
            FROM vf.vf_ghana
            WHERE {' OR '.join(word_clauses)}
            LIMIT {top_k}
        """
        result = backend.execute_query(sql, dataset)
        if result.error or result.dataframe is None:
            return []

        rows = []
        for _, row in result.dataframe.iterrows():
            text_parts = []
            for col in _FREEFORM_COLUMNS:
                val = row.get(col)
                if val and str(val) not in ("null", "[]"):
                    text_parts.append(str(val))
            rows.append({
                "pk_unique_id": str(row.get("pk_unique_id", "")),
                "name": str(row.get("name", "")),
                "city": str(row.get("address_city", "")),
                "relevance_score": None,
                "matching_text": " | ".join(text_parts)[:300],
            })
        return rows


def _get_engine() -> FacilitySearchEngine:
    global _engine
    if _engine is None:
        _engine = FacilitySearchEngine()
    return _engine


# ------------------------------------------------------------------
# MCP tool
# ------------------------------------------------------------------


def register_rag_tools(mcp) -> None:
    """Register the RAG search tool with the MCP server."""

    from oasis.databricks.tracing import traced

    @traced
    def _do_search(query: str, top_k: int) -> list[dict]:
        return _get_engine().search(query, top_k)

    @mcp.tool()
    def search_facility_capabilities(query: str, top_k: int = 10) -> str:
        """Search facility procedures, equipment, and capabilities via semantic RAG.

        Finds facilities whose free-form text descriptions match your query
        by *meaning*, not just exact keywords. Uses pre-computed semantic
        embeddings over the procedure, equipment, and capability fields.

        Good for questions like:
        - "Find facilities that can perform emergency surgery"
        - "Which facilities have imaging equipment?"
        - "Hospitals with maternal care capabilities"

        Args:
            query: Natural language description of the capability you're looking for.
            top_k: Maximum number of matching facilities to return (default: 10).

        Returns:
            Matching facilities ranked by relevance with name, location, and
            matching text from procedure/equipment/capability fields.
        """
        try:
            results = _do_search(query, top_k)
            if not results:
                return f"No facilities found matching: '{query}'"

            method = (
                "semantic similarity"
                if results[0].get("relevance_score") is not None
                else "keyword match"
            )
            parts = [f"**Found {len(results)} facilities** (via {method})\n"]

            for i, r in enumerate(results, 1):
                score = (
                    f" (relevance: {r['relevance_score']})"
                    if r.get("relevance_score") is not None
                    else ""
                )
                parts.append(f"**{i}. {r['name']}**{score}")
                parts.append(f"   City: {r['city']}")
                parts.append(f"   ID: {r['pk_unique_id']}")
                parts.append(f"   Capabilities: {r['matching_text']}")
                parts.append("")

            return "\n".join(parts)

        except Exception as e:
            return f"**Error during search:** {e}"
