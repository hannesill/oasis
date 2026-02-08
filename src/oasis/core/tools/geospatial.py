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
# HAVERSINE DISTANCE
# =============================================================================

EARTH_RADIUS_KM = 6371.0


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
                unique_id
            FROM "vf"."vf_ghana"
            WHERE address_city IS NOT NULL
                AND TRIM(address_city) != ''
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

        # Geocode and filter by distance
        # Add small per-facility jitter so facilities in the same city
        # get distinct coordinates and slightly different distances.
        import random
        import hashlib

        facilities = []
        for _, row in df.iterrows():
            city = str(row.get("address_city", "")).strip()
            if not city:
                continue

            facility_coords = resolve_location(city)
            if facility_coords is None:
                # Try with address_line1
                addr = str(row.get("address_line1", "")).strip()
                if addr:
                    facility_coords = resolve_location(addr)
            if facility_coords is None:
                # Try region
                region = str(row.get("address_stateOrRegion", "")).strip()
                if region:
                    facility_coords = resolve_location(region)
            if facility_coords is None:
                continue

            # Deterministic jitter based on facility name (reproducible)
            name_str = str(row.get("name", ""))
            seed = int(hashlib.md5(name_str.encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
            lat_jitter = rng.uniform(-0.008, 0.008)  # ~0.9 km
            lng_jitter = rng.uniform(-0.008, 0.008)
            jittered_lat = facility_coords[0] + lat_jitter
            jittered_lng = facility_coords[1] + lng_jitter

            dist = haversine_distance(
                center[0], center[1], jittered_lat, jittered_lng
            )

            if dist <= params.radius_km:
                facilities.append(
                    {
                        "name": row.get("name", "Unknown"),
                        "city": city,
                        "region": row.get("address_stateOrRegion", ""),
                        "distance_km": round(dist, 2),
                        "lat": jittered_lat,
                        "lng": jittered_lng,
                        "facility_type": row.get("facilityTypeId", ""),
                        "specialties": row.get("specialties", ""),
                        "procedures": row.get("procedure", ""),
                        "equipment": row.get("equipment", ""),
                        "capability": row.get("capability", ""),
                        "unique_id": row.get("unique_id", ""),
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


class FindCoverageGapsTool:
    """Identify geographic cold spots where critical procedures are absent.

    Answers questions like:
    - "Where are the largest geographic cold spots where cardiac surgery is absent within 100 km?"
    - "Which areas have no ophthalmology within 50 km?"

    Algorithm:
    1. Find all facilities offering the specified procedure/specialty
    2. Create a grid of points across Ghana
    3. For each grid point, find nearest facility distance
    4. Return grid points where nearest facility > min_gap_km

    Returns:
        dict with gap locations, severity, and nearest facility info
    """

    name = "find_coverage_gaps"
    description = (
        "Identify geographic 'cold spots' — areas where a critical medical "
        "procedure or specialty is absent within a specified distance. "
        "Reveals medical deserts and coverage gaps."
    )
    input_model = FindCoverageGapsInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    # Ghana bounding box for grid generation
    GHANA_BOUNDS = {
        "lat_min": 4.5,
        "lat_max": 11.2,
        "lng_min": -3.3,
        "lng_max": 1.3,
    }
    GRID_STEP = 0.5  # ~55km resolution

    def invoke(
        self, dataset: DatasetDefinition, params: FindCoverageGapsInput
    ) -> dict[str, Any]:
        backend = get_backend()

        # Find facilities with the specified capability
        spec = params.procedure_or_specialty.replace("'", "''").lower()
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
                unique_id
            FROM "vf"."vf_ghana"
            WHERE address_city IS NOT NULL
                AND TRIM(address_city) != ''
                AND (
                    LOWER(specialties) LIKE '%{spec}%'
                    OR LOWER(procedure) LIKE '%{spec}%'
                    OR LOWER(capability) LIKE '%{spec}%'
                    OR LOWER(equipment) LIKE '%{spec}%'
                    OR LOWER(description) LIKE '%{spec}%'
                )
        """

        result = backend.execute_query(sql, dataset)
        if not result.success:
            raise QueryError(result.error or "Query failed")

        df = result.dataframe

        # Geocode facilities
        facility_coords: list[dict] = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                city = str(row.get("address_city", "")).strip()
                coords = resolve_location(city)
                if coords is None:
                    region = str(row.get("address_stateOrRegion", "")).strip()
                    coords = resolve_location(region)
                if coords:
                    facility_coords.append(
                        {
                            "name": row.get("name", "Unknown"),
                            "city": city,
                            "lat": coords[0],
                            "lng": coords[1],
                        }
                    )

        if not facility_coords:
            return {
                "procedure_or_specialty": params.procedure_or_specialty,
                "min_gap_km": params.min_gap_km,
                "total_facilities_found": 0,
                "gaps": [],
                "summary": (
                    f"No facilities found offering '{params.procedure_or_specialty}'. "
                    f"The entire country is a coverage gap for this service."
                ),
            }

        # Generate grid across Ghana
        gaps = []
        lat = self.GHANA_BOUNDS["lat_min"]
        while lat <= self.GHANA_BOUNDS["lat_max"]:
            lng = self.GHANA_BOUNDS["lng_min"]
            while lng <= self.GHANA_BOUNDS["lng_max"]:
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
            f"{params.min_gap_km} km. "
            f"{len(facility_coords)} facilities offer this service in Ghana. "
        )
        if gaps:
            worst = gaps[0]
            summary += (
                f"Worst gap: near {worst['nearest_city']} — "
                f"nearest facility is {worst['nearest_facility_distance_km']} km away."
            )

        return {
            "procedure_or_specialty": params.procedure_or_specialty,
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
                    "specialties": row.get("specialties", ""),
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
                description,
                phone_numbers,
                unique_id,
                capacity,
                numberDoctors
            FROM "vf"."vf_ghana"
            WHERE address_city IS NOT NULL
                AND TRIM(address_city) != ''
                AND {where_clause}
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
                city = str(row.get("address_city", "")).strip()
                coords = resolve_location(city)

                if coords is None:
                    region = str(row.get("address_stateOrRegion", "")).strip()
                    coords = resolve_location(region)

                if coords is None:
                    not_geocoded += 1
                    continue

                geocoded += 1

                # Deterministic jitter based on facility name (reproducible)
                import hashlib
                import random

                name_str = str(row.get("name", ""))
                seed = int(hashlib.md5(name_str.encode()).hexdigest()[:8], 16)
                rng = random.Random(seed)
                lat_offset = rng.uniform(-0.005, 0.005)
                lng_offset = rng.uniform(-0.005, 0.005)

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            coords[1] + lng_offset,
                            coords[0] + lat_offset,
                        ],
                    },
                    "properties": {
                        "name": row.get("name", "Unknown"),
                        "city": city,
                        "region": row.get("address_stateOrRegion", ""),
                        "facility_type": row.get("facilityTypeId", ""),
                        "specialties": row.get("specialties", ""),
                        "procedures": row.get("procedure", ""),
                        "equipment": row.get("equipment", ""),
                        "capability": row.get("capability", ""),
                        "description": row.get("description", ""),
                        "capacity": row.get("capacity", ""),
                        "num_doctors": row.get("numberDoctors", ""),
                        "unique_id": row.get("unique_id", ""),
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

