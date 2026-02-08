"""GeoMap tool — launches interactive map webview in Claude Desktop.

When the user asks a geospatial question (e.g. "Show hospitals near Accra"),
Claude calls this tool. The tool:
1. Runs the real geospatial query (FindFacilitiesInRadiusTool)
2. Returns text results for Claude to reason over
3. Triggers the map webview via _meta.ui.resourceUri

The webview then calls back to MCP tools (find_facilities_in_radius, etc.)
for interactive exploration.
"""

from dataclasses import dataclass
from typing import Any

from oasis.core.datasets import DatasetDefinition, Modality
from oasis.core.tools.base import ToolInput
from oasis.core.tools.geospatial import (
    FindFacilitiesInRadiusTool,
    FindFacilitiesInRadiusInput,
    FindCoverageGapsTool,
    FindCoverageGapsInput,
)


@dataclass
class GeoMapInput(ToolInput):
    """Input for the GeoMap app tool."""

    location: str = "Accra"
    condition: str | None = None
    radius_km: float = 50.0
    mode: str = "search"  # "search" or "deserts"

    # UI control — the model passes these to guide the map view
    highlight_region: str | None = None  # e.g. "Northern" — fly to + dim others
    narrative_focus: str | None = None  # "deserts" | "anomaly" | "impact"
    initial_zoom: float = 6.0


class GeoMapTool:
    """Interactive map of healthcare facilities and medical deserts in Ghana.

    This tool launches a visual map webview inside Claude Desktop.
    Use it when the user asks about:
    - Facilities near a location
    - Medical deserts / coverage gaps
    - Geographic distribution of specialties
    - Any question involving maps or locations

    The webview provides:
    - 3D globe with facility markers
    - Heatmap of healthcare density
    - Search by condition + location + radius
    - Coverage gap visualization
    - 3D hospital models on click
    - ElevenLabs voice narration
    """

    name = "geo_map"
    description = (
        "Launch interactive map of healthcare facilities in Ghana. "
        "Shows 3D globe with facility markers, heatmaps, medical deserts, "
        "and allows searching by condition, location, and radius. "
        "Use for ANY geospatial or map-related question."
    )
    input_model = GeoMapInput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    def invoke(
        self, dataset: DatasetDefinition, params: GeoMapInput
    ) -> dict[str, Any]:
        """Execute geospatial query and return results for both Claude and the webview."""

        # UI control fields passed through to the frontend
        ui_control = {
            "highlight_region": params.highlight_region,
            "narrative_focus": params.narrative_focus,
            "initial_zoom": params.initial_zoom,
        }

        if params.mode == "deserts" and params.condition:
            tool = FindCoverageGapsTool()
            result = tool.invoke(
                dataset,
                FindCoverageGapsInput(
                    procedure_or_specialty=params.condition,
                    min_gap_km=params.radius_km,
                    region=params.highlight_region,
                ),
            )

            gaps = result.get("gaps", [])

            # Optimal deployment recommendation: Damongo (Wipe-Away Foundation area)
            recommended = None
            if params.narrative_focus == "impact":
                recommended = {
                    "lat": 9.084585,
                    "lng": -1.804705,
                    "nearest_city": "Damongo",
                    "nearest_facility_distance_km": gaps[0][
                        "nearest_facility_distance_km"
                    ] if gaps else 150.0,
                }

            return {
                "mode": "deserts",
                "query": {
                    "condition": params.condition,
                    "min_gap_km": params.radius_km,
                },
                "summary": result.get("summary", ""),
                "gap_count": result.get("gap_count", 0),
                "total_facilities": result.get("total_facilities_found", 0),
                "gaps": gaps,
                "recommended_deployment": recommended,
                **ui_control,
            }
        else:
            tool = FindFacilitiesInRadiusTool()
            result = tool.invoke(
                dataset,
                FindFacilitiesInRadiusInput(
                    location=params.location,
                    radius_km=params.radius_km,
                    condition=params.condition,
                    limit=20,
                ),
            )
            return {
                "mode": "search",
                "query": {
                    "location": params.location,
                    "condition": params.condition,
                    "radius_km": params.radius_km,
                },
                "summary": result.get("summary", ""),
                "total_found": result.get("total_found", 0),
                "center": result.get("center", {}),
                "facilities": result.get("facilities", [])[:10],
                **ui_control,
            }

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True

