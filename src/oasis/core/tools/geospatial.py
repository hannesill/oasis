"""Geospatial tools for healthcare facility distance and coverage analysis.

This module provides geospatial intelligence tools for the Virtue Foundation dataset:
- find_facilities_within_radius: Find facilities within X km of a location
- find_coverage_gaps: Identify "cold spots" where critical procedures are absent
- calculate_distance: Get distance between two points
- geocode_facility: Resolve facility addresses to coordinates

Architecture Note:
    Uses Haversine formula for great-circle distance on Earth's surface.
    This is ideal for "within X km" queries without requiring road network data.
    For road-based routing, you'd need OSRM or Google Directions API.

    Coordinates are resolved from a curated Ghana city/region lookup table.
    For production, swap in Mapbox Geocoding API or Nominatim.
"""

import ast
import json
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from oasis.core.backends import get_backend
from oasis.core.datasets import DatasetDefinition, Modality
from oasis.core.exceptions import QueryError
from oasis.core.tools.base import ToolInput

# =============================================================================
# GHANA COORDINATE REFERENCE
# =============================================================================
# Pre-geocoded city/region centers for Ghana.
# This avoids API calls and works offline for the hackathon.
# Format: "city_name_lowercase": (latitude, longitude)

GHANA_CITY_COORDS: dict[str, tuple[float, float]] = {
    # Major cities
    "accra": (5.6037, -0.1870),
    "kumasi": (6.6885, -1.6244),
    "tamale": (9.4008, -0.8393),
    "takoradi": (4.8986, -1.7554),
    "sekondi-takoradi": (4.9340, -1.7137),
    "cape coast": (5.1036, -1.2466),
    "sunyani": (7.3349, -2.3266),
    "ho": (6.6000, 0.4667),
    "koforidua": (6.0940, -0.2558),
    "bolgatanga": (10.7856, -0.8514),
    "wa": (10.0601, -2.5099),
    "tema": (5.6698, -0.0166),
    "obuasi": (6.2020, -1.6614),
    "techiman": (7.5828, -1.9420),
    "nkawkaw": (6.5500, -0.7667),
    "winneba": (5.3500, -0.6333),
    "tarkwa": (5.3000, -1.9833),
    "bawku": (11.0611, -0.2414),
    "kintampo": (8.0500, -1.7333),
    "aflao": (6.1167, 1.1833),
    "ejura": (7.3833, -1.3667),
    "nsawam": (5.8000, -0.3500),
    "suhum": (6.0333, -0.4500),
    "akim oda": (5.9167, -0.9833),
    "prestea": (5.4333, -2.1500),
    "sogakope": (6.0000, 0.6167),
    "hohoe": (7.1500, 0.4667),
    "keta": (5.9167, 0.9833),
    "kpandu": (7.0000, 0.3000),
    "yendi": (9.4333, -0.0167),
    "salaga": (8.5500, -0.5167),
    "damongo": (9.0833, -1.8167),
    "navrongo": (10.8833, -1.0833),
    "tumu": (10.8833, -1.9667),
    "nalerigu": (10.5333, -0.3667),
    "dansoman": (5.5478, -0.2676),
    "cantonments": (5.5667, -0.1667),
    "labone": (5.5600, -0.1700),
    "east legon": (5.6333, -0.1500),
    "adabraka": (5.5583, -0.2100),
    "osu": (5.5500, -0.1833),
    "madina": (5.6833, -0.1667),
    "kasoa": (5.5333, -0.4167),
    "ashaiman": (5.6833, -0.0333),
    "dodowa": (5.8833, -0.0833),
    "nungua": (5.6000, -0.0833),
    "teshie": (5.5833, -0.1000),
    "achimota": (5.6167, -0.2333),
    "circle": (5.5700, -0.2200),
    "kaneshie": (5.5700, -0.2400),
    "mamprobi": (5.5333, -0.2333),
    # Additional cities (2+ facilities)
    "berekum": (7.4534, -2.5840),
    "atebubu": (7.7504, -0.9852),
    "weija": (5.5718, -0.3346),
    "battor": (6.0667, 0.4167),
    "bibiani": (6.4667, -2.3333),
    "oyarifa": (5.7570, -0.1749),
    "sekondi": (4.9268, -1.7577),
    "akwatia": (6.0402, -0.8088),
    "akosombo": (6.3000, 0.0500),
    "walewale": (10.3516, -0.7985),
    "bechem": (7.0858, -2.0298),
    "ejisu": (6.7206, -1.4760),
    "sefwi bekwai": (6.1980, -2.3246),
    "kpando": (6.9954, 0.2931),
    "kwadaso": (6.6740, -1.6766),
    "mampong": (7.0624, -1.4046),
    "dompoase": (6.3124, -1.5330),
    "nkwanta": (8.5070, 0.5871),
    "dzodze": (6.2420, 0.9964),
    "adidome": (6.0657, 0.5071),
    "akatsi": (6.1310, 0.7982),
    "tepa": (7.0072, -2.1696),
    "agona nkwanta": (4.8883, -1.9658),
    "tesano": (5.6000, -0.2170),
    "dome": (5.6500, -0.2361),
    "tikrom": (6.7000, -1.6200),
    "dormaa ahenkro": (7.2671, -2.8677),
    "north kaneshie": (5.5750, -0.2450),
    "enchi": (5.8167, -2.8167),
    "kpandai": (8.4705, -0.0117),
    "sefwi wiawso": (6.2197, -2.5006),
    "gwo": (6.2700, 0.5600),
    "wenchi": (7.7392, -2.1046),
    "kuntanase": (6.5333, -1.4833),
    "darkuman-nyamekye": (5.5600, -0.2350),
    "santasi": (6.6700, -1.6400),
    "mankessim": (5.2728, -1.0155),
    "somanya": (6.1050, -0.0140),
    "breman asikuma": (5.5816, -0.9990),
    "adenta": (5.7142, -0.1542),
    "haatso": (5.6674, -0.1915),
    "duayaw nkwanta": (7.1723, -2.1027),
    "maamobi": (5.5905, -0.1970),
    "kordiabe": (5.9292, 0.0189),
    "agroyesum": (6.4140, -1.8780),
    "adenta municipality": (5.7142, -0.1542),
    "agona swedru": (5.5338, -0.7013),
    "worawora": (7.5192, 0.3701),
    # Notable 1-facility towns (district capitals)
    "axim": (4.8665, -2.2409),
    "bimbilla": (8.8500, 0.0667),
    "bole": (9.0333, -2.4833),
    "goaso": (6.8036, -2.5172),
    "sandema": (10.7347, -1.2906),
    "bekwai": (6.4534, -1.5774),
    "asamankese": (5.8607, -0.6677),
    "dunkwa-on-offin": (5.9698, -1.7831),
    "offinso": (6.9000, -1.6500),
    "karaga": (9.9200, -0.5200),
    "yeji": (8.2167, -0.6500),
    "anloga": (5.7947, 0.8973),
    "bogoso": (5.5667, -2.0167),
    "dixcove": (4.7909, -1.9504),
    "juaboso": (6.3416, -2.8235),
    "tatale": (9.3567, 0.5266),
    "tolon": (9.4309, -1.0646),
    "peki": (6.5231, 0.2275),
    "agogo": (6.8000, -1.0819),
    "apam": (5.2968, -0.7409),
    "nima": (5.5800, -0.1950),
    "nadawli": (10.2000, -2.5000),
    "nkonya": (7.1833, 0.3333),
    "ankaful": (5.2019, -1.0414),
    "asankrangua": (5.8143, -2.4357),
    "eikwe": (4.9649, -2.4709),
    "wiaga": (10.6500, -1.2667),
    "assin-foso": (5.9167, -1.6000),
    "legon": (5.6500, -0.1850),
    "north legon": (5.6600, -0.1800),
    "labadi": (5.5600, -0.1500),
    "dzorwulu": (5.6000, -0.2000),
    "lapaz": (5.6100, -0.2500),
    "kwashieman": (5.5800, -0.2550),
    "odorkor": (5.5700, -0.2700),
    "ridge": (5.5600, -0.2000),
    "james town": (5.5333, -0.2100),
    "agbogbloshie": (5.5500, -0.2250),
    "banda": (8.1667, -2.1333),
    "kumawu": (6.9000, -1.2667),
    "wechiau": (10.1000, -2.6500),
    "new takoradi": (4.9000, -1.7700),
    "kwesimintsim": (4.9100, -1.7800),
    "daffiama": (10.3500, -2.4000),
    # Regions (centroid approximations)
    "greater accra": (5.6037, -0.1870),
    "ashanti": (6.7470, -1.5209),
    "western": (5.3960, -2.1500),
    "eastern": (6.3300, -0.4500),
    "central": (5.4600, -1.2000),
    "northern": (9.5439, -0.9057),
    "upper east": (10.7500, -0.8500),
    "upper west": (10.2500, -2.1500),
    "volta": (6.8000, 0.5000),
    "brong-ahafo": (7.5000, -1.5000),
    "bono": (7.5000, -2.3000),
    "bono east": (7.7500, -1.0500),
    "ahafo": (7.0000, -2.3500),
    "savannah": (9.0000, -1.8000),
    "north east": (10.5000, -0.3500),
    "oti": (7.8000, 0.3000),
    "western north": (6.3000, -2.3000),
}

# Known landmarks in Ghana for query support
GHANA_LANDMARKS: dict[str, tuple[float, float]] = {
    "korle bu teaching hospital": (5.5347, -0.2282),
    "komfo anokye teaching hospital": (6.6929, -1.6260),
    "tamale teaching hospital": (9.4100, -0.8450),
    "cape coast teaching hospital": (5.1100, -1.2500),
    "ridge hospital": (5.5650, -0.2000),
    "37 military hospital": (5.5800, -0.1900),
    "university of ghana": (5.6508, -0.1869),
    "kwame nkrumah circle": (5.5700, -0.2200),
    "kotoka international airport": (5.6052, -0.1718),
    "makola market": (5.5500, -0.2000),
    "independence square": (5.5380, -0.1930),
}


# =============================================================================
# GOLDEN-ANGLE SPIRAL DISTRIBUTION
# =============================================================================
# Distributes N points evenly in a circle around a center — no overlaps,
# deterministic, and looks natural. Used instead of random jitter so that
# facilities in the same city spread across the urban footprint.

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))  # ~137.508°


def _spiral_offset(
    index: int, total: int, base_lat: float, base_lng: float
) -> tuple[float, float]:
    """Return (lat, lng) for the index-th point in a Fermat spiral of `total` points."""
    if total <= 1:
        return (base_lat, base_lng)

    # Scale radius by cluster size
    if total <= 5:
        max_r = 0.01  # ~1.1 km
    elif total <= 20:
        max_r = 0.025  # ~2.8 km
    elif total <= 50:
        max_r = 0.045  # ~5.0 km
    elif total <= 100:
        max_r = 0.065  # ~7.2 km
    else:
        max_r = 0.09  # ~10 km (Accra's 309)

    r = max_r * math.sqrt(index / total)
    theta = index * GOLDEN_ANGLE
    lat_off = r * math.cos(theta)
    lng_off = r * math.sin(theta) / max(math.cos(math.radians(base_lat)), 0.01)
    return (base_lat + lat_off, base_lng + lng_off)


# =============================================================================
# HAVERSINE DISTANCE
# =============================================================================

EARTH_RADIUS_KM = 6371.0


def _clean_val(v: Any) -> Any:
    """Coerce pandas NaN/NaT to None so json.dumps produces valid JSON."""
    if v is None:
        return None
    if isinstance(v, float) and (pd.isna(v) or math.isnan(v)):
        return None
    if pd.isna(v):
        return None
    return v


def _parse_list_field(v: Any) -> list[str]:
    """Parse a CSV list field into a proper Python list of strings.

    The VF Ghana CSV stores array fields as Python repr strings with single
    quotes, e.g. "['item1', 'item2']".  JSON.parse on the frontend chokes on
    single quotes, so we normalise here and return a real list.
    """
    if v is None:
        return []
    if isinstance(v, list):
        return [str(s).strip() for s in v if s]
    s = str(v).strip()
    if not s or s in ("[]", "None", "null", "nan"):
        return []
    # Try Python literal first (handles single-quoted lists)
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except (ValueError, SyntaxError):
        pass
    # Try JSON
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except (json.JSONDecodeError, TypeError):
        pass
    # Last resort: treat the whole string as a single item
    return [s] if s else []


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great-circle distance between two points on Earth.

    Uses the Haversine formula for accuracy on a sphere.

    Args:
        lat1, lon1: Coordinates of point 1 (degrees)
        lat2, lon2: Coordinates of point 2 (degrees)

    Returns:
        Distance in kilometers
    """
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def resolve_location(location_name: str) -> tuple[float, float] | None:
    """Resolve a location name to (latitude, longitude).

    Checks landmarks first, then cities, then regions.
    Case-insensitive fuzzy matching.

    Args:
        location_name: Name of a city, region, or landmark in Ghana

    Returns:
        (lat, lng) tuple or None if not found
    """
    name = location_name.strip().lower()

    # Check landmarks first (most specific)
    if name in GHANA_LANDMARKS:
        return GHANA_LANDMARKS[name]

    # Check cities
    if name in GHANA_CITY_COORDS:
        return GHANA_CITY_COORDS[name]

    # Fuzzy match: check if any key contains the search term
    for key, coords in GHANA_LANDMARKS.items():
        if name in key or key in name:
            return coords

    for key, coords in GHANA_CITY_COORDS.items():
        if name in key or key in name:
            return coords

    return None


# =============================================================================
# TOOL INPUTS
# =============================================================================


@dataclass
class FindFacilitiesInRadiusInput(ToolInput):
    """Input for finding facilities within a radius of a location."""

    location: str  # City name, landmark, or "lat,lng"
    radius_km: float = 50.0
    condition: str | None = None  # Optional: filter by specialty/procedure
    limit: int = 20


@dataclass
class FindCoverageGapsInput(ToolInput):
    """Input for finding geographic cold spots."""

    procedure_or_specialty: str  # e.g., "cardiology", "cataract surgery"
    min_gap_km: float = 50.0  # Minimum distance to consider a "gap"
    region: str | None = None  # e.g., "Northern" — constrain to this region
    limit: int = 10


@dataclass
class CalculateDistanceInput(ToolInput):
    """Input for calculating distance between two locations."""

    from_location: str  # City/landmark name or "lat,lng"
    to_location: str  # City/landmark name or "lat,lng"


@dataclass
class GeocodeFacilitiesInput(ToolInput):
    """Input for geocoding all facilities and returning with coordinates."""

    region: str | None = None  # Optional: filter by region
    facility_type: str | None = None  # Optional: filter by facility type


@dataclass
class CountFacilitiesInput(ToolInput):
    """Input for counting facilities by condition/specialty."""

    condition: str | None = None  # Optional: filter by specialty/procedure
    region: str | None = None  # Optional: filter by region


# =============================================================================
# HELPER: Parse coordinates
# =============================================================================


def _parse_location(location: str) -> tuple[float, float]:
    """Parse a location string into (lat, lng).

    Accepts:
        - "lat,lng" format (e.g., "5.6037,-0.1870")
        - City/landmark name (e.g., "Accra", "Korle Bu Teaching Hospital")

    Raises:
        QueryError if location cannot be resolved
    """
    # Try "lat,lng" format first
    if "," in location:
        parts = location.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return (lat, lng)
            except ValueError:
                pass  # Not a coordinate, try name resolution

    # Resolve by name
    coords = resolve_location(location)
    if coords is None:
        raise QueryError(
            f"Could not resolve location '{location}'. "
            f"Try using coordinates (lat,lng) or a known Ghana city/landmark. "
            f"Known cities include: {', '.join(sorted(list(GHANA_CITY_COORDS.keys())[:15]))}..."
        )
    return coords


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================


class FindFacilitiesInRadiusTool:
    """Find facilities NEAR a specific location (geospatial search with distance).

    Answers questions mentioning LOCATION or PROXIMITY:
    - "Hospitals near Accra" → Use this tool
    - "What clinics are within 50 km of Tamale?" → Use this tool
    - "Closest cardiology centers to Kumasi" → Use this tool

    DO NOT use for total counts without location (use CountFacilitiesTool instead).

    Uses Haversine formula for great-circle distance calculation.

    Returns:
        dict with facilities list, distances from location, and summary statistics
    """

    name = "find_facilities_in_radius"
    description = (
        "Find facilities NEAR a location within a radius (requires location parameter). "
        "Returns facilities sorted by distance from the specified location. "
        "Use ONLY when user mentions a location, proximity, or 'near'/'within X km'."
    )
    input_model = FindFacilitiesInRadiusInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    def invoke(
        self, dataset: DatasetDefinition, params: FindFacilitiesInRadiusInput
    ) -> dict[str, Any]:
        """Find facilities within radius.

        Algorithm:
        1. Resolve location to (lat, lng)
        2. Query all facilities with city info from DuckDB
        3. Geocode each facility using city lookup
        4. Filter by Haversine distance
        5. Optionally filter by condition/specialty
        6. Sort by distance ascending

        Returns:
            dict with:
                - center: dict with location info
                - radius_km: float
                - condition_filter: str | None
                - facilities: list[dict] - sorted by distance
                - total_found: int
                - summary: str
        """
        center = _parse_location(params.location)
        backend = get_backend()

        # Build SQL query - get all facilities with location data
        condition_filter_sql = ""
        if params.condition:
            cond = params.condition.replace("'", "''")
            condition_filter_sql = f"""
                AND (
                    LOWER(specialties) LIKE '%{cond.lower()}%'
                    OR LOWER(procedure) LIKE '%{cond.lower()}%'
                    OR LOWER(capability) LIKE '%{cond.lower()}%'
                    OR LOWER(equipment) LIKE '%{cond.lower()}%'
                    OR LOWER(description) LIKE '%{cond.lower()}%'
                )
            """

        sql = f"""
            SELECT
                name,
                address_city,
                address_stateOrRegion,
                address_line1,
                specialties,
                procedure,
                equipment,
                capability,
                facilityTypeId,
                description,
                phone_numbers,
                unique_id,
                lat,
                "long"
            FROM "vf"."vf_ghana"
            WHERE 1=1
                {condition_filter_sql}
        """

        result = backend.execute_query(sql, dataset)
        if not result.success:
            raise QueryError(result.error or "Query failed")

        df = result.dataframe
        if df is None or df.empty:
            return {
                "center": {
                    "location": params.location,
                    "lat": center[0],
                    "lng": center[1],
                },
                "radius_km": params.radius_km,
                "condition_filter": params.condition,
                "facilities": [],
                "total_found": 0,
                "summary": f"No facilities found matching criteria near {params.location}.",
            }

        # Resolve coordinates: use DB lat/long when available, fall back to city lookup
        facilities = []
        for _, row in df.iterrows():
            db_lat = row.get("lat")
            db_lng = row.get("long")

            # Use DB coordinates if valid
            if (
                db_lat is not None
                and db_lng is not None
                and not pd.isna(db_lat)
                and not pd.isna(db_lng)
            ):
                f_lat, f_lng = float(db_lat), float(db_lng)
            else:
                # Fall back to city-based geocoding
                city = str(row.get("address_city", "")).strip()
                facility_coords = resolve_location(city) if city else None
                if facility_coords is None:
                    addr = str(row.get("address_line1", "")).strip()
                    if addr:
                        facility_coords = resolve_location(addr)
                if facility_coords is None:
                    region = str(row.get("address_stateOrRegion", "")).strip()
                    if region:
                        facility_coords = resolve_location(region)
                if facility_coords is None:
                    continue
                f_lat, f_lng = facility_coords

            dist = haversine_distance(center[0], center[1], f_lat, f_lng)
            if dist <= params.radius_km:
                facilities.append(
                    {
                        "name": _clean_val(row.get("name")) or "Unknown",
                        "city": str(row.get("address_city") or "").strip(),
                        "region": _clean_val(row.get("address_stateOrRegion")) or "",
                        "distance_km": round(dist, 2),
                        "lat": f_lat,
                        "lng": f_lng,
                        "facility_type": _clean_val(row.get("facilityTypeId")) or "",
                        "specialties": _parse_list_field(row.get("specialties")),
                        "procedures": _parse_list_field(row.get("procedure")),
                        "equipment": _parse_list_field(row.get("equipment")),
                        "capability": _parse_list_field(row.get("capability")),
                        "description": _clean_val(row.get("description")) or "",
                        "unique_id": _clean_val(row.get("unique_id")) or "",
                    }
                )

        # Sort by distance
        facilities.sort(key=lambda x: x["distance_km"])

        # Limit results
        total_found = len(facilities)
        facilities = facilities[: params.limit]

        # Build summary
        cond_text = f" treating {params.condition}" if params.condition else ""
        summary = (
            f"Found {total_found} facilities{cond_text} within "
            f"{params.radius_km} km of {params.location}. "
        )
        if facilities:
            closest = facilities[0]
            summary += (
                f"Closest: {closest['name']} in {closest['city']} "
                f"({closest['distance_km']} km away)."
            )

        return {
            "center": {
                "location": params.location,
                "lat": center[0],
                "lng": center[1],
            },
            "radius_km": params.radius_km,
            "condition_filter": params.condition,
            "facilities": facilities,
            "total_found": total_found,
            "summary": summary,
        }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True


# Approximate bounding boxes for Ghana's regions (for grid constraint)
GHANA_REGION_BOUNDS: dict[str, dict[str, float]] = {
    "northern": {"lat_min": 8.5, "lat_max": 10.5, "lng_min": -2.5, "lng_max": 0.5},
    "upper east": {"lat_min": 10.2, "lat_max": 11.2, "lng_min": -1.3, "lng_max": 0.0},
    "upper west": {"lat_min": 9.6, "lat_max": 11.0, "lng_min": -3.0, "lng_max": -1.5},
    "ashanti": {"lat_min": 6.0, "lat_max": 7.5, "lng_min": -2.5, "lng_max": -0.5},
    "greater accra": {"lat_min": 5.3, "lat_max": 6.0, "lng_min": -0.5, "lng_max": 0.5},
    "western": {"lat_min": 4.5, "lat_max": 6.0, "lng_min": -3.3, "lng_max": -1.5},
    "eastern": {"lat_min": 5.5, "lat_max": 7.0, "lng_min": -1.5, "lng_max": 0.5},
    "central": {"lat_min": 5.0, "lat_max": 6.0, "lng_min": -2.0, "lng_max": -0.5},
    "volta": {"lat_min": 5.5, "lat_max": 8.5, "lng_min": -0.5, "lng_max": 1.2},
    "brong-ahafo": {"lat_min": 6.5, "lat_max": 8.5, "lng_min": -3.0, "lng_max": -0.5},
    "bono": {"lat_min": 7.0, "lat_max": 8.5, "lng_min": -3.0, "lng_max": -1.5},
    "bono east": {"lat_min": 7.0, "lat_max": 8.5, "lng_min": -1.5, "lng_max": 0.0},
    "ahafo": {"lat_min": 6.5, "lat_max": 7.5, "lng_min": -3.0, "lng_max": -1.5},
    "savannah": {"lat_min": 8.0, "lat_max": 10.0, "lng_min": -2.5, "lng_max": -0.5},
    "north east": {"lat_min": 10.0, "lat_max": 11.0, "lng_min": -0.5, "lng_max": 0.5},
    "oti": {"lat_min": 7.5, "lat_max": 9.0, "lng_min": -0.5, "lng_max": 1.0},
    "western north": {"lat_min": 5.5, "lat_max": 7.0, "lng_min": -3.0, "lng_max": -2.0},
}


class FindCoverageGapsTool:
    """Identify geographic cold spots where critical procedures are absent.

    Answers questions like:
    - "Where are the largest geographic cold spots where cardiac surgery is absent within 100 km?"
    - "Which areas have no ophthalmology within 50 km?"

    Algorithm:
    1. Find all facilities offering the specified procedure/specialty
    2. Create a grid of points across the target area
    3. For each grid point, find nearest facility distance
    4. Return grid points where nearest facility > min_gap_km

    Returns:
        dict with gap locations, severity, and nearest facility info
    """

    name = "find_coverage_gaps"
    description = (
        "Identify geographic 'cold spots' — areas where a critical medical "
        "procedure or specialty is absent within a specified distance. "
        "Reveals medical deserts and coverage gaps. "
        "Optionally filter by region (e.g. 'Northern') to focus the analysis."
    )
    input_model = FindCoverageGapsInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    # Ghana bounding box for grid generation (full country fallback)
    GHANA_BOUNDS = {
        "lat_min": 4.5,
        "lat_max": 11.2,
        "lng_min": -3.3,
        "lng_max": 1.3,
    }
    GRID_STEP = 0.5  # ~55km resolution

    def _get_bounds(self, region: str | None) -> dict[str, float]:
        """Get bounding box for grid generation, constrained to region if given."""
        if region:
            key = region.strip().lower()
            # Try exact match first, then substring match
            if key in GHANA_REGION_BOUNDS:
                return GHANA_REGION_BOUNDS[key]
            for rname, bounds in GHANA_REGION_BOUNDS.items():
                if key in rname or rname in key:
                    return bounds
        return self.GHANA_BOUNDS

    def invoke(
        self, dataset: DatasetDefinition, params: FindCoverageGapsInput
    ) -> dict[str, Any]:
        backend = get_backend()

        # Find facilities with the specified capability
        spec = params.procedure_or_specialty.replace("'", "''").lower()

        region_filter_sql = ""
        if params.region:
            region_esc = params.region.replace("'", "''")
            region_filter_sql = (
                f"AND LOWER(address_stateOrRegion) LIKE "
                f"'%{region_esc.lower()}%'"
            )

        sql = f"""
            SELECT
                name,
                address_city,
                address_stateOrRegion,
                specialties,
                procedure,
                equipment,
                capability,
                facilityTypeId,
                unique_id,
                lat,
                "long"
            FROM "vf"."vf_ghana"
            WHERE (
                    LOWER(specialties) LIKE '%{spec}%'
                    OR LOWER(procedure) LIKE '%{spec}%'
                    OR LOWER(capability) LIKE '%{spec}%'
                    OR LOWER(equipment) LIKE '%{spec}%'
                    OR LOWER(description) LIKE '%{spec}%'
                )
                {region_filter_sql}
        """

        result = backend.execute_query(sql, dataset)
        if not result.success:
            raise QueryError(result.error or "Query failed")

        df = result.dataframe

        # Resolve coordinates: use DB lat/long when available, fall back to city lookup
        facility_coords: list[dict] = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                db_lat = row.get("lat")
                db_lng = row.get("long")
                city = str(row.get("address_city", "")).strip()

                if (
                    db_lat is not None
                    and db_lng is not None
                    and not pd.isna(db_lat)
                    and not pd.isna(db_lng)
                ):
                    f_lat, f_lng = float(db_lat), float(db_lng)
                else:
                    coords = resolve_location(city) if city else None
                    if coords is None:
                        rgn = str(row.get("address_stateOrRegion", "")).strip()
                        coords = resolve_location(rgn)
                    if coords is None:
                        continue
                    f_lat, f_lng = coords

                facility_coords.append(
                    {
                        "name": row.get("name", "Unknown"),
                        "city": city,
                        "lat": f_lat,
                        "lng": f_lng,
                    }
                )

        region_label = f" in {params.region}" if params.region else " in Ghana"

        if not facility_coords:
            return {
                "procedure_or_specialty": params.procedure_or_specialty,
                "region": params.region,
                "min_gap_km": params.min_gap_km,
                "total_facilities_found": 0,
                "gaps": [],
                "gap_count": 0,
                "summary": (
                    f"No facilities found offering "
                    f"'{params.procedure_or_specialty}'{region_label}. "
                    f"The entire area is a coverage gap for this service."
                ),
            }

        # Generate grid — constrained to region if specified
        bounds = self._get_bounds(params.region)
        gaps = []
        lat = bounds["lat_min"]
        while lat <= bounds["lat_max"]:
            lng = bounds["lng_min"]
            while lng <= bounds["lng_max"]:
                # Find nearest facility to this grid point
                min_dist = float("inf")
                nearest_facility = None
                for fc in facility_coords:
                    dist = haversine_distance(lat, lng, fc["lat"], fc["lng"])
                    if dist < min_dist:
                        min_dist = dist
                        nearest_facility = fc

                if min_dist >= params.min_gap_km:
                    # Find nearest known city to this gap point
                    gap_city = "Unknown area"
                    min_city_dist = float("inf")
                    for city_name, (clat, clng) in GHANA_CITY_COORDS.items():
                        cd = haversine_distance(lat, lng, clat, clng)
                        if cd < min_city_dist:
                            min_city_dist = cd
                            gap_city = city_name.title()

                    gaps.append(
                        {
                            "lat": round(lat, 4),
                            "lng": round(lng, 4),
                            "nearest_city": gap_city,
                            "nearest_facility_name": (
                                nearest_facility["name"]
                                if nearest_facility
                                else "None"
                            ),
                            "nearest_facility_distance_km": round(min_dist, 2),
                            "severity": (
                                "critical"
                                if min_dist > params.min_gap_km * 2
                                else "moderate"
                            ),
                        }
                    )

                lng += self.GRID_STEP
            lat += self.GRID_STEP

        # Sort by severity (distance to nearest facility)
        gaps.sort(key=lambda x: x["nearest_facility_distance_km"], reverse=True)
        gaps = gaps[: params.limit]

        summary = (
            f"Found {len(gaps)} coverage gap areas where "
            f"'{params.procedure_or_specialty}' is absent within "
            f"{params.min_gap_km} km{region_label}. "
            f"{len(facility_coords)} facilities offer this service. "
        )
        if gaps:
            worst = gaps[0]
            summary += (
                f"Worst gap: near {worst['nearest_city']} — "
                f"nearest facility is {worst['nearest_facility_distance_km']} km away."
            )

        return {
            "procedure_or_specialty": params.procedure_or_specialty,
            "region": params.region,
            "min_gap_km": params.min_gap_km,
            "total_facilities_found": len(facility_coords),
            "gaps": gaps,
            "gap_count": len(gaps),
            "summary": summary,
        }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True


class CalculateDistanceTool:
    """Calculate the distance between two locations.

    Simple utility tool that returns great-circle distance in kilometers.

    Returns:
        dict with distance, from/to info
    """

    name = "calculate_distance"
    description = (
        "Calculate the straight-line distance (km) between two locations in Ghana. "
        "Accepts city names, landmarks, or lat/lng coordinates."
    )
    input_model = CalculateDistanceInput

    required_modalities: frozenset[Modality] = frozenset()  # No data needed
    supported_datasets: frozenset[str] | None = None  # Works for any dataset

    def invoke(
        self, dataset: DatasetDefinition, params: CalculateDistanceInput
    ) -> dict[str, Any]:
        from_coords = _parse_location(params.from_location)
        to_coords = _parse_location(params.to_location)

        dist = haversine_distance(
            from_coords[0], from_coords[1], to_coords[0], to_coords[1]
        )

        return {
            "from": {
                "location": params.from_location,
                "lat": from_coords[0],
                "lng": from_coords[1],
            },
            "to": {
                "location": params.to_location,
                "lat": to_coords[0],
                "lng": to_coords[1],
            },
            "distance_km": round(dist, 2),
            "summary": (
                f"Distance from {params.from_location} to {params.to_location}: "
                f"{round(dist, 2)} km (straight-line / great-circle)."
            ),
        }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        return True


class CountFacilitiesTool:
    """Count TOTAL facilities across ALL of Ghana (NO geospatial/distance filtering).

    Answers questions about TOTAL COUNTS without location:
    - "How many hospitals have cardiology?" → Returns total across Ghana
    - "How many facilities offer surgery?" → Returns total count
    - "What's the total count of clinics in Northern region?" → Returns regional total

    DO NOT use for location-based queries like "near Accra" or "within X km".

    Returns:
        dict with total count and breakdown by region/type
    """

    name = "count_facilities"
    description = (
        "Count TOTAL facilities across all of Ghana by condition/specialty/procedure. "
        "Returns aggregate statistics WITHOUT geospatial filtering. "
        "Use ONLY when user asks 'how many TOTAL' without mentioning location or distance."
    )
    input_model = CountFacilitiesInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    def invoke(
        self, dataset: DatasetDefinition, params: CountFacilitiesInput
    ) -> dict[str, Any]:
        """Count facilities matching criteria.

        Returns:
            dict with:
                - total_count: int
                - condition_filter: str | None
                - region_filter: str | None
                - breakdown: dict with counts by region
                - sample_facilities: list of top 5 facilities
        """
        backend = get_backend()

        # Build SQL query
        where_clauses = ["1=1"]
        
        if params.condition:
            cond = params.condition.replace("'", "''")
            where_clauses.append(f"""(
                LOWER(specialties) LIKE '%{cond.lower()}%'
                OR LOWER(procedure) LIKE '%{cond.lower()}%'
                OR LOWER(capability) LIKE '%{cond.lower()}%'
                OR LOWER(equipment) LIKE '%{cond.lower()}%'
                OR LOWER(description) LIKE '%{cond.lower()}%'
            )""")
        
        if params.region:
            region = params.region.replace("'", "''")
            where_clauses.append(f"LOWER(address_stateOrRegion) LIKE '%{region.lower()}%'")

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM "vf"."vf_ghana"
            WHERE {where_sql}
        """
        
        count_result = backend.execute_query(count_sql, dataset)
        if not count_result.success or count_result.dataframe is None:
            raise QueryError("Failed to count facilities")
        
        total_count = int(count_result.dataframe.iloc[0]["total"])

        # Regional breakdown
        breakdown_sql = f"""
            SELECT 
                COALESCE(address_stateOrRegion, 'Unknown') as region,
                COUNT(*) as count
            FROM "vf"."vf_ghana"
            WHERE {where_sql}
            GROUP BY address_stateOrRegion
            ORDER BY count DESC
        """
        
        breakdown_result = backend.execute_query(breakdown_sql, dataset)
        breakdown = {}
        if breakdown_result.success and breakdown_result.dataframe is not None:
            for _, row in breakdown_result.dataframe.iterrows():
                breakdown[row["region"]] = int(row["count"])

        # Sample facilities
        sample_sql = f"""
            SELECT name, address_city, address_stateOrRegion, specialties
            FROM "vf"."vf_ghana"
            WHERE {where_sql}
            LIMIT 5
        """
        
        sample_result = backend.execute_query(sample_sql, dataset)
        sample_facilities = []
        if sample_result.success and sample_result.dataframe is not None:
            for _, row in sample_result.dataframe.iterrows():
                sample_facilities.append({
                    "name": row.get("name", "Unknown"),
                    "city": row.get("address_city", ""),
                    "region": row.get("address_stateOrRegion", ""),
                    "specialties": _parse_list_field(row.get("specialties")),
                })

        # Build summary
        cond_text = f" with {params.condition}" if params.condition else ""
        region_text = f" in {params.region}" if params.region else " across Ghana"
        summary = f"Found {total_count} facilities{cond_text}{region_text}."

        return {
            "total_count": total_count,
            "condition_filter": params.condition,
            "region_filter": params.region,
            "breakdown_by_region": breakdown,
            "sample_facilities": sample_facilities,
            "summary": summary,
        }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True


class GeocodeFacilitiesTool:
    """Geocode all facilities and return with lat/lng coordinates.

    Returns facility data enriched with coordinates for map rendering.
    This is the bridge between the backend data and the map UI.

    Returns:
        dict with GeoJSON-compatible features list
    """

    name = "geocode_facilities"
    description = (
        "Geocode healthcare facilities and return as map-ready data with "
        "coordinates. Useful for map visualization and spatial analysis. "
        "Returns GeoJSON-compatible format."
    )
    input_model = GeocodeFacilitiesInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    def invoke(
        self, dataset: DatasetDefinition, params: GeocodeFacilitiesInput
    ) -> dict[str, Any]:
        backend = get_backend()

        filters = []
        if params.region:
            region = params.region.replace("'", "''")
            filters.append(
                f"LOWER(address_stateOrRegion) LIKE '%{region.lower()}%'"
            )
        if params.facility_type:
            ft = params.facility_type.replace("'", "''")
            filters.append(f"LOWER(facilityTypeId) LIKE '%{ft.lower()}%'")

        where_clause = " AND ".join(filters) if filters else "1=1"

        sql = f"""
            SELECT
                name,
                address_city,
                address_stateOrRegion,
                address_line1,
                specialties,
                procedure,
                equipment,
                capability,
                facilityTypeId,
                operatorTypeId,
                description,
                phone_numbers,
                unique_id,
                capacity,
                numberDoctors,
                yearEstablished,
                lat,
                "long"
            FROM "vf"."vf_ghana"
            WHERE {where_clause}
        """

        result = backend.execute_query(sql, dataset)
        if not result.success:
            raise QueryError(result.error or "Query failed")

        df = result.dataframe
        features = []
        geocoded = 0
        not_geocoded = 0

        if df is not None and not df.empty:
            for _, row in df.iterrows():
                db_lat = row.get("lat")
                db_lng = row.get("long")

                # Use DB coordinates if valid
                if (
                    db_lat is not None
                    and db_lng is not None
                    and not pd.isna(db_lat)
                    and not pd.isna(db_lng)
                ):
                    f_lat, f_lng = float(db_lat), float(db_lng)
                else:
                    # Fall back to city-based geocoding
                    city = str(row.get("address_city", "")).strip()
                    coords = resolve_location(city) if city else None
                    if coords is None:
                        region = str(row.get("address_stateOrRegion", "")).strip()
                        coords = resolve_location(region)
                    if coords is None:
                        not_geocoded += 1
                        continue
                    f_lat, f_lng = coords

                geocoded += 1
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [f_lng, f_lat],
                    },
                    "properties": {
                        "name": _clean_val(row.get("name")) or "Unknown",
                        "city": str(row.get("address_city") or "").strip(),
                        "region": _clean_val(row.get("address_stateOrRegion")) or "",
                        "address": _clean_val(row.get("address_line1")) or "",
                        "facility_type": _clean_val(row.get("facilityTypeId")) or "",
                        "operator_type": _clean_val(row.get("operatorTypeId")) or "",
                        "specialties": _parse_list_field(row.get("specialties")),
                        "procedures": _parse_list_field(row.get("procedure")),
                        "equipment": _parse_list_field(row.get("equipment")),
                        "capability": _parse_list_field(row.get("capability")),
                        "description": _clean_val(row.get("description")) or "",
                        "phone": _clean_val(row.get("phone_numbers")) or "",
                        "capacity": _clean_val(row.get("capacity")) or "",
                        "num_doctors": _clean_val(row.get("numberDoctors")) or "",
                        "year_established": _clean_val(row.get("yearEstablished")) or "",
                        "unique_id": _clean_val(row.get("unique_id")) or "",
                    },
                }
                features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        return {
            "geojson": geojson,
            "total_geocoded": geocoded,
            "total_not_geocoded": not_geocoded,
            "summary": (
                f"Geocoded {geocoded} facilities. "
                f"{not_geocoded} could not be geocoded (unknown city). "
                f"Data returned in GeoJSON format ready for map rendering."
            ),
        }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True

