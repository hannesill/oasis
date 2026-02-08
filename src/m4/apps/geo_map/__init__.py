"""GeoMap MCP App.

An interactive 3D map for exploring healthcare facilities in Ghana.
Shows facility locations, heatmaps, medical deserts, and 3D building models.

Components:
    - GeoMapTool: Entry point tool that triggers UI rendering
    - FindFacilitiesInRadiusTool: Backend tool for geospatial search (in core/tools/geospatial.py)
    - ui: HTML resource serving
"""

from m4.apps.geo_map.tool import GeoMapInput, GeoMapTool
from m4.apps.geo_map.ui import RESOURCE_URI, get_ui_html

__all__ = [
    "RESOURCE_URI",
    "GeoMapInput",
    "GeoMapTool",
    "get_ui_html",
]
