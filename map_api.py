#!/usr/bin/env python3
"""OASIS Map API — HTTP bridge to MCP geospatial tools.

Exposes the same geospatial tools that Claude Desktop calls via MCP,
but over HTTP so the browser map UI can use them directly.

    Browser  →  GET /api/search  →  FindFacilitiesInRadiusTool  →  DuckDB
    Browser  →  GET /api/gaps    →  FindCoverageGapsTool        →  DuckDB
    Browser  →  GET /api/distance→  CalculateDistanceTool       →  Haversine

Run:
    python map_api.py
    # Open http://localhost:8000
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
os.environ.setdefault("M4_DATA_DIR", str(Path(__file__).parent / "m4_data"))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from m4.core.tools.geospatial import (
    FindFacilitiesInRadiusTool,
    FindFacilitiesInRadiusInput,
    FindCoverageGapsTool,
    FindCoverageGapsInput,
    CalculateDistanceTool,
    CalculateDistanceInput,
    GeocodeFacilitiesTool,
    GeocodeFacilitiesInput,
)
from m4.core.datasets import DatasetRegistry
from m4.config import get_active_dataset

# ── Instantiate tools (same instances MCP server uses) ──
_find = FindFacilitiesInRadiusTool()
_gaps = FindCoverageGapsTool()
_dist = CalculateDistanceTool()
_geo = GeocodeFacilitiesTool()


def _dataset():
    name = get_active_dataset()
    if not name:
        raise RuntimeError("No active dataset. Run: python -m m4.cli use vf-ghana")
    return DatasetRegistry.get(name)


app = FastAPI(title="OASIS Map API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Static files ──

@app.get("/")
async def index():
    return FileResponse("map_local_test.html")


@app.get("/facilities.geojson")
async def facilities_geojson():
    p = Path("facilities.geojson")
    if p.exists():
        return FileResponse(p, media_type="application/json")
    ds = _dataset()
    result = _geo.invoke(ds, GeocodeFacilitiesInput())
    return JSONResponse(result["geojson"])


# ── Tool endpoints ──

@app.get("/api/search")
async def search(
    condition: str = Query(...),
    location: str = Query("Accra"),
    radius_km: float = Query(50.0),
    limit: int = Query(20),
):
    """Calls FindFacilitiesInRadiusTool — the real MCP tool."""
    ds = _dataset()
    t0 = time.time()
    result = _find.invoke(
        ds,
        FindFacilitiesInRadiusInput(
            location=location,
            radius_km=radius_km,
            condition=condition or None,
            limit=limit,
        ),
    )
    return JSONResponse({
        "success": True,
        "tool": "find_facilities_in_radius",
        "elapsed_ms": round((time.time() - t0) * 1000),
        "data": result,
    })


@app.get("/api/gaps")
async def gaps(
    specialty: str = Query(...),
    min_gap_km: float = Query(50.0),
    limit: int = Query(10),
):
    """Calls FindCoverageGapsTool — the real MCP tool."""
    ds = _dataset()
    t0 = time.time()
    result = _gaps.invoke(
        ds,
        FindCoverageGapsInput(
            procedure_or_specialty=specialty,
            min_gap_km=min_gap_km,
            limit=limit,
        ),
    )
    return JSONResponse({
        "success": True,
        "tool": "find_coverage_gaps",
        "elapsed_ms": round((time.time() - t0) * 1000),
        "data": result,
    })


@app.get("/api/distance")
async def distance(
    from_location: str = Query(...),
    to_location: str = Query(...),
):
    """Calls CalculateDistanceTool — the real MCP tool."""
    ds = _dataset()
    result = _dist.invoke(
        ds,
        CalculateDistanceInput(
            from_location=from_location,
            to_location=to_location,
        ),
    )
    return JSONResponse({"success": True, "tool": "calculate_distance", "data": result})


@app.get("/api/geocode")
async def geocode(
    region: str = Query(None),
    facility_type: str = Query(None),
):
    """Calls GeocodeFacilitiesTool — the real MCP tool."""
    ds = _dataset()
    result = _geo.invoke(
        ds,
        GeocodeFacilitiesInput(region=region, facility_type=facility_type),
    )
    return JSONResponse({
        "success": True,
        "tool": "geocode_facilities",
        "geojson": result["geojson"],
        "total_geocoded": result["total_geocoded"],
        "total_not_geocoded": result["total_not_geocoded"],
    })


@app.get("/api/health")
async def health():
    try:
        name = get_active_dataset()
        return {"status": "ok", "dataset": name}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


if __name__ == "__main__":
    print("\n🌍 OASIS Map API")
    print("─" * 40)
    print("  UI:     http://localhost:8000")
    print("  API:    http://localhost:8000/api/search?condition=cardiology&location=Accra")
    print("  Health: http://localhost:8000/api/health")
    print("─" * 40 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
