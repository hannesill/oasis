"""M4 MCP Server - Thin MCP Protocol Adapter.

This module provides the FastMCP server that exposes M4 tools via MCP protocol.
All business logic is delegated to tool classes in m4.core.tools.

Architecture:
    mcp_server.py (this file) - MCP protocol adapter
        ↓ delegates to
    core/tools/*.py - Tool implementations (return native types)
        ↓ uses
    core/backends/*.py - Database backends

    The MCP layer uses the serialization module to convert native Python
    types to MCP-friendly strings. Exceptions are caught and formatted.

Tool Surface:
    The MCP tool surface is stable - all tools remain registered regardless of
    the active dataset. Compatibility is enforced per-call via proactive
    capability checking before tool invocation.
"""

from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP

# MCP Apps imports
from m4.apps import init_apps
from m4.core.datasets import DatasetRegistry
from m4.core.exceptions import M4Error
from m4.core.serialization import serialize_for_mcp
from m4.core.tools import ToolRegistry, ToolSelector, init_tools
from m4.core.tools.management import ListDatasetsInput, SetDatasetInput
from m4.core.tools.notes import (
    GetNoteInput,
    ListPatientNotesInput,
    SearchNotesInput,
)
from m4.core.tools.geospatial import (
    CalculateDistanceInput,
    CountFacilitiesInput,
    FindCoverageGapsInput,
    FindFacilitiesInRadiusInput,
    GeocodeFacilitiesInput,
)
from m4.apps.geo_map import RESOURCE_URI as GEO_MAP_URI, get_ui_html, GeoMapInput
from m4.core.tools.tabular import (
    ExecuteQueryInput,
    GetDatabaseSchemaInput,
    GetTableInfoInput,
)

# Create FastMCP server instance
mcp = FastMCP("m4")

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
        "search_notes",
        "get_note",
        "list_patient_notes",
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

        parquet_icon = "✅" if info.get("parquet_present") else "❌"
        db_icon = "✅" if info.get("db_present") else "❌"

        output.append(f"  Local Parquet: {parquet_icon}")
        output.append(f"  Local Database: {db_icon}")
        output.append("")

    return "\n".join(output)


def _serialize_set_dataset_result(result: dict[str, Any]) -> str:
    """Serialize set_dataset result to MCP string."""
    dataset_name = result.get("dataset_name", "")
    warnings = result.get("warnings", [])

    status_msg = f"✅ Active dataset switched to '{dataset_name}'."

    for warning in warnings:
        status_msg += f"\n⚠️ {warning}"

    return status_msg


def _serialize_search_notes_result(result: dict[str, Any]) -> str:
    """Serialize search_notes result to MCP string."""
    backend_info = result.get("backend_info", "")
    query = result.get("query", "")
    snippet_length = result.get("snippet_length", 300)
    results = result.get("results", {})

    if not results or all(df.empty for df in results.values()):
        tables = ", ".join(results.keys()) if results else "notes"
        return f"{backend_info}\n**No matches found** for '{query}' in {tables}."

    output_parts = [
        backend_info,
        f"**Search:** '{query}' (showing snippets of ~{snippet_length} chars)",
    ]

    for table, df in results.items():
        if not df.empty:
            output_parts.append(f"\n**{table.upper()}:**\n{df.to_string(index=False)}")

    output_parts.append(
        "\n**Tip:** Use `get_note(note_id)` to retrieve full text of a specific note."
    )

    return "\n".join(output_parts)


def _serialize_get_note_result(result: dict[str, Any]) -> str:
    """Serialize get_note result to MCP string."""
    backend_info = result.get("backend_info", "")
    note_id = result.get("note_id", "")
    subject_id = result.get("subject_id", "")
    text = result.get("text", "")
    note_length = result.get("note_length", 0)
    truncated = result.get("truncated", False)

    parts = [backend_info, ""]

    if truncated:
        parts.append(f"**Note (truncated, original length: {note_length} chars):**")
    else:
        parts.append(f"**Note {note_id} (subject_id: {subject_id}):**")

    parts.append(text)

    if truncated:
        parts.append("\n[...truncated...]")

    return "\n".join(parts)


def _serialize_list_patient_notes_result(result: dict[str, Any]) -> str:
    """Serialize list_patient_notes result to MCP string."""
    backend_info = result.get("backend_info", "")
    subject_id = result.get("subject_id", "")
    notes = result.get("notes", {})

    if not notes or all(df.empty for df in notes.values()):
        return f"{backend_info}\n**No notes found** for subject_id {subject_id}."

    output_parts = [
        backend_info,
        f"**Notes for subject_id {subject_id}:**",
    ]

    for table, df in notes.items():
        if not df.empty:
            output_parts.append(
                f"\n**{table.upper()} NOTES:**\n{df.to_string(index=False)}"
            )

    output_parts.append(
        "\n**Tip:** Use `get_note(note_id)` to retrieve full text of a specific note."
    )

    return "\n".join(output_parts)


# ==========================================
# MCP TOOLS - Thin adapters to tool classes
# ==========================================


@mcp.tool()
def list_datasets() -> str:
    """📋 List all available datasets and their status.

    Returns:
        A formatted string listing available datasets, indicating which one is active,
        and showing availability of local database.
    """
    try:
        tool = ToolRegistry.get("list_datasets")
        dataset = DatasetRegistry.get_active()
        result = tool.invoke(dataset, ListDatasetsInput())
        return _serialize_datasets_result(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def set_dataset(dataset_name: str) -> str:
    """🔄 Switch the active dataset.

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
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_database_schema() -> str:
    """📚 Discover what data is available in the database.

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
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_table_info(table_name: str, show_sample: bool = True) -> str:
    """🔍 Explore a specific table's structure and see sample data.

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
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def execute_query(sql_query: str) -> str:
    """🚀 Execute SQL queries to analyze data.

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
    except M4Error as e:
        return f"**Error:** {e}"


# ==========================================
# CLINICAL NOTES TOOLS
# ==========================================


@mcp.tool()
def search_notes(
    query: str,
    note_type: str = "all",
    limit: int = 5,
    snippet_length: int = 300,
) -> str:
    """🔍 Search clinical notes by keyword.

    Returns snippets around matches to prevent context overflow.
    Use get_note() to retrieve full text of specific notes.

    **Note types:** 'discharge' (summaries), 'radiology' (reports), or 'all'

    Args:
        query: Search term to find in notes.
        note_type: Type of notes to search ('discharge', 'radiology', or 'all').
        limit: Maximum number of results per note type (default: 5).
        snippet_length: Characters of context around matches (default: 300).

    Returns:
        Matching snippets with note IDs for follow-up retrieval.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility("search_notes", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("search_notes")
        result = tool.invoke(
            dataset,
            SearchNotesInput(
                query=query,
                note_type=note_type,
                limit=limit,
                snippet_length=snippet_length,
            ),
        )
        return _serialize_search_notes_result(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_note(note_id: str, max_length: int | None = None) -> str:
    """📄 Retrieve full text of a specific clinical note.

    **Warning:** Clinical notes can be very long. Consider using
    search_notes() first to find relevant notes, or use max_length
    to truncate output.

    Args:
        note_id: The note ID (e.g., from search_notes or list_patient_notes).
        max_length: Optional maximum characters to return (truncates if exceeded).

    Returns:
        Full note text, or truncated version if max_length specified.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility("get_note", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("get_note")
        result = tool.invoke(
            dataset,
            GetNoteInput(note_id=note_id, max_length=max_length),
        )
        return _serialize_get_note_result(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def list_patient_notes(
    subject_id: int,
    note_type: str = "all",
    limit: int = 20,
) -> str:
    """📋 List available clinical notes for a patient.

    Returns note metadata (IDs, types, lengths) without full text.
    Use get_note(note_id) to retrieve specific notes.

    Args:
        subject_id: Patient identifier.
        note_type: Type of notes to list ('discharge', 'radiology', or 'all').
        limit: Maximum notes to return (default: 20).

    Returns:
        List of available notes with metadata for the patient.
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility(
            "list_patient_notes", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("list_patient_notes")
        result = tool.invoke(
            dataset,
            ListPatientNotesInput(
                subject_id=subject_id,
                note_type=note_type,
                limit=limit,
            ),
        )
        return _serialize_list_patient_notes_result(result)
    except M4Error as e:
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
    except M4Error as e:
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
        return serialize_for_mcp(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def find_coverage_gaps(
    procedure_or_specialty: str,
    min_gap_km: float = 50.0,
    limit: int = 10,
) -> str:
    """🏜️ Find medical deserts — areas where critical care is absent.

    Identifies geographic "cold spots" where a procedure or specialty
    has no nearby facility within the specified distance.

    Use for questions like:
    - "Where are the largest cold spots for cardiac surgery?"
    - "Which areas have no ophthalmology within 100 km?"

    Args:
        procedure_or_specialty: Medical procedure or specialty to check coverage for.
        min_gap_km: Minimum distance (km) to consider a gap (default: 50).
        limit: Maximum gap locations to return (default: 10).

    Returns:
        Coverage gap locations with severity and nearest facility info.
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
                limit=limit,
            ),
        )
        return serialize_for_mcp(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def calculate_distance(
    from_location: str,
    to_location: str,
) -> str:
    """📏 Calculate straight-line distance between two locations in Ghana.

    Uses the Haversine formula for great-circle distance.
    Accepts city names, landmarks, or lat/lng coordinates.

    Args:
        from_location: Starting point (city name, landmark, or "lat,lng").
        to_location: Destination point (city name, landmark, or "lat,lng").

    Returns:
        Distance in kilometers between the two locations.
    """
    try:
        dataset = DatasetRegistry.get_active()

        tool = ToolRegistry.get("calculate_distance")
        result = tool.invoke(
            dataset,
            CalculateDistanceInput(
                from_location=from_location,
                to_location=to_location,
            ),
        )
        return serialize_for_mcp(result)
    except M4Error as e:
        return f"**Error:** {e}"


@mcp.tool()
def geocode_facilities(
    region: str | None = None,
    facility_type: str | None = None,
) -> str:
    """📍 Geocode facilities and return map-ready GeoJSON data.

    Returns facility data enriched with lat/lng coordinates in GeoJSON format.
    Use this to populate map visualizations.

    Args:
        region: Optional region filter (e.g., "Northern", "Ashanti").
        facility_type: Optional facility type filter (e.g., "hospital", "clinic").

    Returns:
        GeoJSON FeatureCollection with geocoded facilities.
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
        return serialize_for_mcp(result)
    except M4Error as e:
        return f"**Error:** {e}"


# ==========================================
# GEO MAP APP — Interactive map webview
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
) -> str:
    """🗺️ Launch interactive healthcare map. Opens a visual map inside Claude.

    Use when the user asks:
    - "Show hospitals near Accra"
    - "Where are medical deserts for cardiology?"
    - "Map facilities within 100km of Tamale"
    - Any question involving locations, distances, or maps

    Args:
        location: City, landmark, or "lat,lng" (default: Accra)
        condition: Medical condition/specialty to filter by
        radius_km: Search radius in km (default: 50)
        mode: "search" for nearby facilities, "deserts" for coverage gaps

    Returns:
        Text summary + interactive map webview
    """
    try:
        dataset = DatasetRegistry.get_active()

        compat_result = _tool_selector.check_compatibility("geo_map", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("geo_map")
        result = tool.invoke(dataset, GeoMapInput(
            location=location,
            condition=condition,
            radius_km=radius_km,
            mode=mode,
        ))
        return serialize_for_mcp(result)
    except M4Error as e:
        return f"**Error:** {e}"


# ==========================================
# _meta.ui.resourceUri INJECTION
# ==========================================


def _inject_geo_map_meta() -> None:
    """Inject _meta.ui.resourceUri into the geo_map tool.

    FastMCP doesn't expose _meta via the decorator, so we monkey-patch
    the tool's to_mcp_tool method to include it.  This is what tells
    Claude Desktop to render our HTML resource as a webview.
    """
    try:
        tool_manager = mcp._tool_manager
        tool_obj = tool_manager._tools.get("geo_map")
        if tool_obj is None:
            return

        original_to_mcp = tool_obj.to_mcp_tool

        def patched_to_mcp(**overrides: Any) -> Any:
            overrides.setdefault("_meta", {"ui": {"resourceUri": GEO_MAP_URI}})
            return original_to_mcp(**overrides)

        # Bypass Pydantic's __setattr__ validation
        object.__setattr__(tool_obj, "to_mcp_tool", patched_to_mcp)
    except (AttributeError, TypeError):
        # FastMCP internals may change; fail silently
        pass


# Apply the _meta injection
_inject_geo_map_meta()


def main():
    """Main entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
