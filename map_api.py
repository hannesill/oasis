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

# Load .env before anything else reads os.environ
_env_file = Path(__file__).parent / ".env"
if _env_file.is_file():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

os.environ.setdefault("OASIS_DATA_DIR", str(Path(__file__).parent / "oasis_data"))
os.environ.setdefault("OASIS_DATASET", "vf-ghana")

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from oasis.core.tools.geospatial import (
    FindFacilitiesInRadiusTool,
    FindFacilitiesInRadiusInput,
    FindCoverageGapsTool,
    FindCoverageGapsInput,
    CalculateDistanceTool,
    CalculateDistanceInput,
    GeocodeFacilitiesTool,
    GeocodeFacilitiesInput,
)
from oasis.core.datasets import DatasetRegistry
from oasis.config import get_active_dataset

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


PORT = 8000


@asynccontextmanager
async def lifespan(application: FastAPI):
    print("\n🌍 OASIS Map API")
    print("─" * 40)
    print(f"  UI:     http://localhost:{PORT}")
    print(f"  API:    http://localhost:{PORT}/api/search?condition=cardiology&location=Accra")
    print(f"  Health: http://localhost:{PORT}/api/health")
    print("─" * 40 + "\n", flush=True)
    yield


app = FastAPI(title="OASIS Map API", version="1.0", lifespan=lifespan)


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


@app.get("/api/config")
async def config():
    """Return client-side config (tokens loaded from .env)."""
    return JSONResponse({
        "mapbox_token": os.environ.get("MAPBOX_TOKEN", ""),
        "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY", ""),
    })


@app.get("/api/health")
async def health():
    try:
        name = get_active_dataset()
        return {"status": "ok", "dataset": name}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


if __name__ == "__main__":
    import socket

    # Check if port is already in use before starting
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", PORT)) == 0:
            print(f"\n❌ Port {PORT} is already in use.")
            print("   Kill the existing process first:")
            print(f"   lsof -ti :{PORT} | xargs kill")
            sys.exit(1)

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
