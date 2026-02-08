"""OASIS MCP Server - Thin MCP Protocol Adapter.

This module provides the FastMCP server that exposes OASIS tools via MCP protocol.
All business logic is delegated to tool classes in oasis.core.tools.

Architecture:
    mcp_server.py (this file) - MCP protocol adapter
        | delegates to
    core/tools/*.py - Tool implementations (return native types)
        | uses
    core/backends/*.py - Database backends

    The MCP layer uses the serialization module to convert native Python
    types to MCP-friendly strings. Exceptions are caught and formatted.

Tool Surface:
    The MCP tool surface is stable - all tools remain registered regardless of
    the active dataset. Compatibility is enforced per-call via proactive
    capability checking before tool invocation.
"""

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Lightweight .env loader (no python-dotenv dependency)
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    """Load .env from project root into os.environ (setdefault — no overwrite)."""
    # Walk up from this file to find .env next to pyproject.toml
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
            break


_load_dotenv()

# MCP Apps imports
from oasis.apps import init_apps
from oasis.core.datasets import DatasetRegistry
from oasis.core.exceptions import OASISError
from oasis.core.serialization import serialize_for_mcp
from oasis.core.tools import ToolRegistry, ToolSelector, init_tools
from oasis.core.tools.management import ListDatasetsInput, SetDatasetInput
from oasis.core.tools.geospatial import (
    CalculateDistanceInput,
    CountFacilitiesInput,
    FindCoverageGapsInput,
    FindFacilitiesInRadiusInput,
    GeocodeFacilitiesInput,
)
from oasis.core.tools.tabular import (
    ExecuteQueryInput,
    GetDatabaseSchemaInput,
    GetTableInfoInput,
)

# MCP App imports
from oasis.apps.geo_map import RESOURCE_URI as GEO_MAP_URI
from oasis.apps.geo_map import GeoMapInput, get_ui_html

# Create FastMCP server instance
mcp = FastMCP("oasis")

# Initialize systems
init_tools()
init_apps()

# Tool selector for capability-based filtering
_tool_selector = ToolSelector()

# MCP-exposed tool names (for filtering in set_dataset snapshot)
_MCP_TOOL_NAMES = frozenset(
    {
        "list_datasets",
        "set_dataset",
        "get_database_schema",
        "get_table_info",
        "execute_query",
        "count_facilities",
        "find_facilities_in_radius",
        "find_coverage_gaps",
        "calculate_distance",
        "geocode_facilities",
        "geo_map",
    }
)


# ===========================================
# SERIALIZATION HELPERS
# ===========================================


def _serialize_schema_result(result: dict[str, Any]) -> str:
    """Serialize get_database_schema result to MCP string."""
    backend_info = result.get("backend_info", "")
    tables = result.get("tables", [])

    if not tables:
        return f"{backend_info}\n**Available Tables:**\nNo tables found"

    table_list = "\n".join(f"  {t}" for t in tables)
    return f"{backend_info}\n**Available Tables:**\n{table_list}"


def _serialize_table_info_result(result: dict[str, Any]) -> str:
    """Serialize get_table_info result to MCP string."""
    backend_info = result.get("backend_info", "")
    table_name = result.get("table_name", "")
    schema = result.get("schema")
    sample = result.get("sample")

    parts = [
        backend_info,
        f"**Table:** {table_name}",
        "",
        "**Column Information:**",
    ]

    if schema is not None and isinstance(schema, pd.DataFrame):
        parts.append(schema.to_string(index=False))
    else:
        parts.append("(no schema information)")

    if sample is not None and isinstance(sample, pd.DataFrame) and not sample.empty:
        parts.extend(
            [
                "",
                "**Sample Data (first 3 rows):**",
                sample.to_string(index=False),
            ]
        )

    return "\n".join(parts)


def _serialize_datasets_result(result: dict[str, Any]) -> str:
    """Serialize list_datasets result to MCP string."""
    active = result.get("active_dataset") or "(unset)"
    backend = result.get("backend", "duckdb")
    datasets = result.get("datasets", {})

    if not datasets:
        return "No datasets detected."

    output = [f"Active dataset: {active}\n"]
    output.append(f"Backend: {'local (DuckDB)' if backend == 'duckdb' else backend}\n")

    for label, info in datasets.items():
        is_active = " (Active)" if info.get("is_active") else ""
        output.append(f"=== {label.upper()}{is_active} ===")

        parquet_icon = "+" if info.get("parquet_present") else "-"
        db_icon = "+" if info.get("db_present") else "-"

        output.append(f"  Local Parquet: {parquet_icon}")
        output.append(f"  Local Database: {db_icon}")
        output.append("")

    return "\n".join(output)


def _serialize_set_dataset_result(result: dict[str, Any]) -> str:
    """Serialize set_dataset result to MCP string."""
    dataset_name = result.get("dataset_name", "")
    warnings = result.get("warnings", [])

    status_msg = f"Active dataset switched to '{dataset_name}'."

    for warning in warnings:
        status_msg += f"\nWarning: {warning}"

    return status_msg


# ==========================================
# MCP TOOLS - Thin adapters to tool classes
# ==========================================


@mcp.tool()
def list_datasets() -> str:
    """List all available datasets and their status.

    Returns:
        A formatted string listing available datasets, indicating which one is active,
        and showing availability of local database.
    """
    try:
        tool = ToolRegistry.get("list_datasets")
        dataset = DatasetRegistry.get_active()
        result = tool.invoke(dataset, ListDatasetsInput())
        return _serialize_datasets_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def set_dataset(dataset_name: str) -> str:
    """Switch the active dataset.

    Args:
        dataset_name: The name of the dataset to switch to.

    Returns:
        Confirmation message with supported tools snapshot, or error if not found.
    """
    try:
        # Check if target dataset exists before switching
        target_dataset_def = DatasetRegistry.get(dataset_name.lower())

        tool = ToolRegistry.get("set_dataset")
        dataset = DatasetRegistry.get_active()
        result = tool.invoke(dataset, SetDatasetInput(dataset_name=dataset_name))
        output = _serialize_set_dataset_result(result)

        # Append supported tools snapshot if dataset is valid
        if target_dataset_def is not None:
            output += _tool_selector.get_supported_tools_snapshot(
                target_dataset_def, _MCP_TOOL_NAMES
            )

        return output
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_database_schema() -> str:
    """Discover what data is available in the database.

    **When to use:** Start here to understand what tables exist.

    Returns:
        List of all available tables in the database with current backend info.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility(
            "get_database_schema", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("get_database_schema")
        result = tool.invoke(dataset, GetDatabaseSchemaInput())
        return _serialize_schema_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_table_info(table_name: str, show_sample: bool = True) -> str:
    """Explore a specific table's structure and see sample data.

    **When to use:** After identifying relevant tables from get_database_schema().

    Args:
        table_name: Exact table name (case-sensitive).
        show_sample: Whether to include sample rows (default: True).

    Returns:
        Table structure with column names, types, and sample data.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility("get_table_info", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("get_table_info")
        result = tool.invoke(
            dataset, GetTableInfoInput(table_name=table_name, show_sample=show_sample)
        )
        return _serialize_table_info_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def execute_query(sql_query: str) -> str:
    """Execute SQL queries to analyze data.

    **Recommended workflow:**
    1. Use get_database_schema() to list tables
    2. Use get_table_info() to examine structure
    3. Write your SQL query with exact names

    Args:
        sql_query: Your SQL SELECT query (SELECT only).

    Returns:
        Query results or helpful error messages.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility("execute_query", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("execute_query")
        result = tool.invoke(dataset, ExecuteQueryInput(sql_query=sql_query))
        # Result is a DataFrame - serialize it
        return serialize_for_mcp(result)
    except OASISError as e:
        return f"**Error:** {e}"


# ==========================================
# GEOSPATIAL TOOLS
# ==========================================


@mcp.tool()
def count_facilities(
    condition: str | None = None,
    region: str | None = None,
) -> str:
    """📊 Count TOTAL facilities across ALL of Ghana by condition (NO geospatial filtering).

    ⚠️ USE THIS when user asks for TOTAL COUNT without mentioning distance/proximity:
    - "How many hospitals have cardiology?" → Use this tool
    - "How many facilities offer surgery?" → Use this tool
    - "Total count of cardiology hospitals?" → Use this tool

    ❌ DO NOT USE for location-based queries (use find_facilities_in_radius instead):
    - "Hospitals near Accra" → DON'T use this tool
    - "Within 50km of Kumasi" → DON'T use this tool

    Args:
        condition: Medical condition, specialty, or procedure to filter by.
        region: Optional region name to filter by (e.g., "Greater Accra", "Northern").

    Returns:
        Total count across entire Ghana with regional breakdown and sample facilities.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility("count_facilities", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("count_facilities")
        result = tool.invoke(
            dataset,
            CountFacilitiesInput(
                condition=condition,
                region=region,
            ),
        )
        return serialize_for_mcp(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def find_facilities_in_radius(
    location: str,
    radius_km: float = 50.0,
    condition: str | None = None,
    limit: int = 20,
) -> str:
    """🌍 Find facilities NEAR a specific location (with distance/proximity).

    ⚠️ USE THIS ONLY when user mentions a LOCATION or PROXIMITY:
    - "Hospitals near Accra" → Use this tool
    - "Within 50 km of Tamale" → Use this tool
    - "Closest cardiology centers to Kumasi" → Use this tool

    ❌ DO NOT USE for total counts without location (use count_facilities instead):
    - "How many hospitals have cardiology?" → Use count_facilities
    - "Total cardiology facilities" → Use count_facilities

    Args:
        location: City name, landmark, or "lat,lng" coordinates (REQUIRED).
        radius_km: Search radius in kilometers (default: 50).
        condition: Optional medical condition, specialty, or procedure to filter by.
        limit: Maximum number of results (default: 20).

    Returns:
        Facilities within radius with distances from the specified location, sorted by proximity.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility(
            "find_facilities_in_radius", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("find_facilities_in_radius")
        result = tool.invoke(
            dataset,
            FindFacilitiesInRadiusInput(
                location=location,
                radius_km=radius_km,
                condition=condition,
                limit=limit,
            ),
        )
        return json.dumps(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def find_coverage_gaps(
    procedure_or_specialty: str,
    min_gap_km: float = 50.0,
    region: str | None = None,
) -> str:
    """🏜️ Find medical deserts — areas lacking critical medical capabilities.

    Identifies regions where a given specialty or procedure is absent within
    a configurable radius.

    Args:
        procedure_or_specialty: The specialty or procedure to check for.
        min_gap_km: Minimum distance to flag as a desert (default: 50 km).
        region: Optional region name (e.g. "Northern") to constrain the analysis.

    Returns:
        List of desert areas with severity rankings.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility(
            "find_coverage_gaps", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("find_coverage_gaps")
        result = tool.invoke(
            dataset,
            FindCoverageGapsInput(
                procedure_or_specialty=procedure_or_specialty,
                min_gap_km=min_gap_km,
                region=region,
            ),
        )
        return json.dumps(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def calculate_distance(
    location_a: str,
    location_b: str,
) -> str:
    """📏 Calculate the distance between two locations in Ghana.

    Uses the Haversine formula for great-circle distance.

    Args:
        location_a: First location (city name or "lat,lng").
        location_b: Second location (city name or "lat,lng").

    Returns:
        Distance in kilometers between the two locations.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility(
            "calculate_distance", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("calculate_distance")
        result = tool.invoke(
            dataset,
            CalculateDistanceInput(
                from_location=location_a,
                to_location=location_b,
            ),
        )
        return json.dumps(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def geocode_facilities(
    region: str | None = None,
    facility_type: str | None = None,
) -> str:
    """🌐 Export geocoded facilities as GeoJSON.

    Args:
        region: Optional region to filter by.
        facility_type: Optional facility type to filter by.

    Returns:
        GeoJSON FeatureCollection with facility coordinates and metadata.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility(
            "geocode_facilities", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("geocode_facilities")
        result = tool.invoke(
            dataset,
            GeocodeFacilitiesInput(
                region=region,
                facility_type=facility_type,
            ),
        )
        return json.dumps(result)
    except OASISError as e:
        return f"**Error:** {e}"


# ==========================================
# GEO MAP MCP APP
# ==========================================


@mcp.resource(GEO_MAP_URI, mime_type="text/html;profile=mcp-app")
def geo_map_ui() -> str:
    """Serve the geo map UI HTML bundle."""
    return get_ui_html()


@mcp.tool()
def geo_map(
    location: str = "Accra",
    condition: str | None = None,
    radius_km: float = 50.0,
    mode: str = "search",
    highlight_region: str | None = None,
    narrative_focus: str | None = None,
    initial_zoom: float = 6.0,
) -> str:
    """🗺️ Launch interactive healthcare map. Opens a visual map inside Claude.

    Use this to visually show hospitals, medical deserts, and coverage on a 3D map.

    Args:
        location: Center location for the map (default: Accra).
        condition: Medical condition or specialty to highlight.
        radius_km: Search radius in kilometers (default: 50).
        mode: "search" for facility search, "deserts" for coverage gaps.
        highlight_region: Region to fly to and highlight (e.g. "Northern").
        narrative_focus: Controls the demo narrative — "deserts", "anomaly", or "impact".
        initial_zoom: Initial camera zoom level (default: 6.0).

    Returns:
        Map data with facility locations and summary.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility("geo_map", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("geo_map")
        result = tool.invoke(
            dataset,
            GeoMapInput(
                location=location,
                condition=condition,
                radius_km=radius_km,
                mode=mode,
                highlight_region=highlight_region,
                narrative_focus=narrative_focus,
                initial_zoom=initial_zoom,
            ),
        )

        response = {
            **result,
            "config": {
                "mapbox_token": os.environ.get("MAPBOX_TOKEN", ""),
                "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY", ""),
            },
        }
        return json.dumps(response)
    except OASISError as e:
        return f"**Error:** {e}"


# Inject _meta.ui.resourceUri into the geo_map tool
def _inject_geo_map_meta() -> None:
    """Inject _meta.ui.resourceUri into the geo_map tool."""
    try:
        tool_manager = mcp._tool_manager
        tool_obj = tool_manager._tools.get("geo_map")
        if tool_obj is None:
            return

        original_to_mcp = tool_obj.to_mcp_tool

        def patched_to_mcp(**overrides: Any) -> Any:
            overrides.setdefault("_meta", {"ui": {"resourceUri": GEO_MAP_URI}})
            return original_to_mcp(**overrides)

        object.__setattr__(tool_obj, "to_mcp_tool", patched_to_mcp)
    except (AttributeError, TypeError):
        pass


_inject_geo_map_meta()


# Inject _meta.ui.csp into the geo_map resource content so Claude Desktop's
# sandbox allows Mapbox tile/API requests and ElevenLabs narration.
def _inject_geo_map_csp() -> None:
    """Patch resources/read handler to add CSP domains to geo-map resource."""
    import mcp.types as mcp_types

    fastmcp_server = globals()["mcp"]  # module-level FastMCP instance
    low_level = fastmcp_server._mcp_server
    original_handler = low_level.request_handlers.get(mcp_types.ReadResourceRequest)
    if original_handler is None:
        return

    _CSP_META = {
        "ui": {
            "csp": {
                "connectDomains": [
                    "https://api.mapbox.com",
                    "https://events.mapbox.com",
                    "https://tiles.mapbox.com",
                    "https://api.elevenlabs.io",
                ],
                "resourceDomains": [
                    "https://api.mapbox.com",
                    "https://tiles.mapbox.com",
                ],
            }
        }
    }

    async def patched_handler(req: mcp_types.ReadResourceRequest) -> Any:
        result = await original_handler(req)
        # Inject _meta.ui.csp into geo-map resource content items
        if str(req.params.uri) == GEO_MAP_URI and hasattr(result, "root"):
            read_result = result.root
            if hasattr(read_result, "contents"):
                for item in read_result.contents:
                    item.meta = _CSP_META
        return result

    low_level.request_handlers[mcp_types.ReadResourceRequest] = patched_handler


_inject_geo_map_csp()


# ------------------------------------------
# Databricks integration (Genie, RAG, MLflow)
# ------------------------------------------
from oasis.databricks import register_databricks_tools

register_databricks_tools(mcp)



def main():
    """Main entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
