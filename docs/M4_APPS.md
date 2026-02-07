# M4 Apps: Interactive Tools in Claude Desktop

M4 Apps bring interactivity to data exploration workflows. While traditional MCP tools return text responses, M4 Apps render interactive UIs directly within your AI client — enabling real-time exploration, visual feedback, and iterative refinement without switching applications.

## How M4 Apps Work

M4 Apps use the MCP Apps protocol to serve interactive UIs alongside tool responses. When you call an app tool:

1. **Tool returns data**: The backend tool processes the request and returns structured data
2. **UI renders**: The host (Claude Desktop, etc.) renders the app's UI in an iframe
3. **Bidirectional communication**: The UI calls backend tools for live updates
4. **Results stay in context**: The AI sees the final results for follow-up questions

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Desktop                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │                    Chat                           │   │
│  │  User: Show me surgical deserts in Northern Ghana │   │
│  │  Claude: [Launches Medical Desert Mapper]        │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Medical Desert Mapper UI               │   │
│  │  ┌──────────┐ ┌───────────────────────────────┐  │   │
│  │  │ Filters  │ │ Map View                      │  │   │
│  │  │ Spec: .. │ │ [Leaflet Map of Ghana]        │  │   │
│  │  │ Type: .. │ │ [Facility Markers]            │  │   │
│  │  │ Region:  │ │ [Desert Heatmap]              │  │   │
│  │  └──────────┘ └───────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
           │                         │
           │ MCP Protocol            │ Tool calls
           ▼                         ▼
┌─────────────────────────────────────────────────────────┐
│                    M4 MCP Server                         │
│  desert_mapper (launches UI)                            │
│  query_facilities (handles live updates)                │
└─────────────────────────────────────────────────────────┘
```

## Requirements

M4 Apps require:
- **Host support**: A client that implements the MCP Apps protocol (Claude Desktop 1.x+)
- **M4 initialized**: An active dataset (`m4 init vf-ghana --src ...`)
- **MCP connection**: M4 configured in your client (`m4 config claude`)

Apps gracefully degrade in hosts without MCP Apps support — you'll get text-based results instead of the interactive UI.

## Building an M4 App

Apps live in `src/m4/apps/`. Each app has:

### Directory Structure

```
src/m4/apps/desert_mapper/
├── __init__.py
├── tool.py            # Tool classes (registered in apps/__init__.py)
├── query_builder.py   # SQL generation for map queries
└── ui/                # Vite + Leaflet.js UI bundle
    ├── src/
    │   ├── index.html
    │   ├── main.ts
    │   └── styles.css
    ├── package.json
    └── vite.config.ts
```

### Tool Class

The app tool must declare `_meta.ui.resourceUri` pointing to a bundled HTML resource:

```python
from dataclasses import dataclass
from m4.core.datasets import DatasetDefinition, Modality
from m4.core.tools.base import ToolInput, ToolOutput

@dataclass
class DesertMapperInput(ToolInput):
    specialty: str | None = None
    region: str | None = None

class DesertMapperTool:
    name = "desert_mapper"
    description = "Interactive map of healthcare facilities and medical deserts in Ghana"
    input_model = DesertMapperInput
    output_model = ToolOutput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = frozenset({"vf-ghana"})

    def invoke(
        self, dataset: DatasetDefinition, params: DesertMapperInput
    ) -> ToolOutput:
        # Query facilities, build response
        # The _meta.ui.resourceUri in MCP registration points to the bundled HTML
        ...
```

### UI Bundle

The UI is a Vite-bundled single HTML file that uses the MCP Apps SDK for host communication:

```typescript
// src/main.ts
import { McpAppsClient } from '@anthropic-ai/mcp-apps-sdk';

const client = new McpAppsClient();

// Call backend tools from the UI
const result = await client.callTool('query_facilities', {
  specialty: 'surgery',
  region: 'Northern'
});

// Render results on the map
renderFacilities(result);
```

Build with Vite to produce a single inlined HTML file:

```bash
cd src/m4/apps/desert_mapper/ui
npm install
npm run build  # Produces dist/index.html
```

### Registration

Register the app in `src/m4/apps/__init__.py`:

```python
from .desert_mapper.tool import DesertMapperTool

def init_apps():
    ToolRegistry.register(DesertMapperTool())
```

The MCP server exposes the tool with `_meta.ui.resourceUri` pointing to the bundled HTML resource. See `mcp_server.py` for the resource registration pattern.

## Technical Notes

- UIs are built with Vite and bundled as single-file HTML (all CSS/JS inlined)
- Apps use the MCP Apps SDK (`@anthropic-ai/mcp-apps-sdk`) for host communication
- Backend tools handle data queries; UIs handle presentation
- The UI communicates with backend tools via `client.callTool()` — no direct database access
