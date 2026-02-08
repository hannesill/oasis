# Medical Desert Mapper — Implementation Plan

## Architecture Decision

**Separate TypeScript MCP server** for the map app, following the proven `map-server` example from `@modelcontextprotocol/ext-apps`. The Python OASIS server continues handling analytical tools (anomalies, routing, IDP). Both connect to Claude Desktop as independent MCP servers.

**Why not extend the Python FastMCP server?**
FastMCP doesn't natively support the `_meta.ui.resourceUri` + `registerAppTool` + `registerAppResource` pattern that MCP Apps requires. The TypeScript SDK has battle-tested helpers. For a hackathon, "works reliably" beats "architecturally pure."

**Reference implementation:** `/tmp/mcp-ext-apps/examples/map-server/` — CesiumJS globe app with geocoding, fullscreen, `updateModelContext`, and CSP configuration.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Map | Mapbox GL JS (3D terrain, extruded layers) |
| Hex grid | `h3-js` (Uber H3 hexagonal spatial index) |
| MCP server | `@modelcontextprotocol/sdk` + `@modelcontextprotocol/ext-apps` |
| UI bundling | Vite + `vite-plugin-singlefile` |
| Geocoding (build-time) | Nominatim (OSM) — Python script during `oasis init` |
| Routing (runtime) | Mapbox Directions API |
| Language | TypeScript (server + UI) |

---

## Directory Structure

```
src/oasis/apps/desert_mapper/
├── server.ts              # MCP server: registerAppTool + registerAppResource
├── main.ts                # Entry point (stdio + HTTP transports)
├── data.ts                # Load geocoded facility data from JSON
├── mcp-app.html           # HTML shell (Vite entry)
├── src/
│   ├── mcp-app.ts         # App lifecycle, Mapbox init, MCP handlers
│   ├── layers/
│   │   ├── markers.ts     # Individual facility markers layer
│   │   └── hex-grid.ts    # H3 hex grid layer with 3D extrusion
│   ├── sidebar.ts         # Rich facility detail sidebar panel
│   ├── filters.ts         # Specialty + Region dropdown controls
│   ├── routing.ts         # Mapbox Directions API integration
│   └── styles.css         # Clean minimal white UI chrome
├── package.json
├── tsconfig.json
├── tsconfig.server.json
├── vite.config.ts
└── dist/                  # Built artifacts (gitignored)
```

---

## Phase 1: Proof of Concept — Map + Hardcoded Markers

**Goal:** A working MCP App that shows a Mapbox GL JS map of Ghana with ~20 hardcoded facility markers. Proves the full stack: TypeScript MCP server → bundled HTML resource → Mapbox rendering inside Claude Desktop.

**What to build:**

1. **Scaffold the project** in `src/oasis/apps/desert_mapper/`:
   - `package.json` — deps: `@modelcontextprotocol/ext-apps`, `@modelcontextprotocol/sdk`, `mapbox-gl`, `zod`, `vite`, `vite-plugin-singlefile`, `cross-env`, `tsx`
   - `tsconfig.json` + `tsconfig.server.json` — (copy pattern from `/tmp/mcp-ext-apps/examples/map-server/`)
   - `vite.config.ts` — use `viteSingleFile()`, input from `INPUT` env var
   - `.gitignore` — `node_modules/`, `dist/`

2. **`server.ts`** — MCP server with:
   - `registerAppResource` serving bundled `dist/mcp-app.html`
   - CSP meta allowing `https://*.mapbox.com` and `https://api.mapbox.com` in both `connectDomains` and `resourceDomains`
   - `registerAppTool("show-desert-map", ...)` with input schema: `{ region?: string, specialty?: string }`. Returns text summary + `_meta` with resource URI
   - The tool handler returns hardcoded facility data as `structuredContent` (20 facilities with name, lat, lng, type, region)

3. **`main.ts`** — Entry point supporting `--stdio` and HTTP modes (copy from map-server example, use `tsx` instead of `bun`)

4. **`mcp-app.html`** — minimal HTML shell with a full-screen map container + loading indicator

5. **`src/mcp-app.ts`** — App lifecycle:
   - Create `App` instance, register handlers BEFORE `app.connect()`
   - `ontoolinput`: receive facility data, initialize Mapbox map
   - Init Mapbox GL JS with `MAPBOX_ACCESS_TOKEN` (read from a global injected at build time OR hardcoded for POC)
   - Map style: `mapbox://styles/mapbox/light-v11`
   - Camera: center on Ghana `[-1.0232, 7.9465]`, zoom 6, pitch 60°
   - 3D terrain: `mapbox-dem` source + `map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 })`
   - Add markers as a GeoJSON source with `circle` layer, colored by `facilityTypeId`

6. **`src/styles.css`** — reset + full-screen map, loading spinner

**How to verify:**
```bash
cd src/oasis/apps/desert_mapper
npm install && npm run build
# Start HTTP server:
npm run serve
# Open http://localhost:3001 in browser (basic-host or directly)
# OR configure in Claude Desktop's MCP settings and test there
```
- You should see a 3D map of Ghana with terrain
- ~20 colored markers on the map
- Camera pitched at 60° showing terrain
- No console errors

**Key references:**
- `/tmp/mcp-ext-apps/examples/map-server/server.ts` — exact pattern for registerAppTool + registerAppResource
- `/tmp/mcp-ext-apps/examples/map-server/src/mcp-app.ts` — App lifecycle, fullscreen, updateModelContext
- `/tmp/mcp-ext-apps/examples/map-server/vite.config.ts` — Vite singlefile config
- Mapbox GL JS docs for terrain: https://docs.mapbox.com/mapbox-gl-js/example/add-terrain/

---

## Phase 2: Geocoding + Real Data

**Goal:** Geocode all ~1,002 facilities and display real data on the map. Geocoding happens during `oasis init`, cached as a JSON file.

**What to build:**

1. **`src/oasis/geocoding.py`** — Python geocoding module:
   - Function `geocode_facilities(csv_path: Path, output_path: Path)`
   - Reads the CSV, extracts address fields: `name`, `address_line1`, `address_city`, `address_stateOrRegion`
   - Uses Nominatim (OpenStreetMap) for geocoding with rate limiting (1 req/sec)
   - Query construction: `"{address_line1}, {address_city}, {address_stateOrRegion}, Ghana"` — skip empty fields
   - Fallback: if address fails, try `"{address_city}, {address_stateOrRegion}, Ghana"`, then `"{address_city}, Ghana"`
   - Final fallback: district/region centroid lookup table (hardcoded dict of Ghana regions → lat/lng)
   - Output: JSON file at `oasis_data/geocoded/vf-ghana.json` with schema:
     ```json
     [
       {
         "pk_unique_id": 123,
         "name": "Tamale Teaching Hospital",
         "lat": 9.4075,
         "lng": -0.8393,
         "geocode_quality": "address" | "city" | "region" | "centroid",
         "facilityTypeId": "hospital",
         "operatorTypeId": "public",
         "address_city": "Tamale",
         "address_stateOrRegion": "Northern",
         "specialties": ["surgery", "internalMedicine"],
         "procedure": [...],
         "equipment": [...],
         "capability": [...]
       }
     ]
     ```
   - Progress bar via Rich (consistent with existing `oasis init` UX)
   - Cache: skip facilities already geocoded (check output file)

2. **Integrate into `oasis init`** — in `src/oasis/cli.py`:
   - After CSV→Parquet conversion succeeds, call `geocode_facilities()`
   - Only run geocoding for `vf-ghana` dataset (guard with dataset name check)
   - Print summary: "Geocoded X/1002 facilities (Y address, Z city, W centroid)"

3. **`src/oasis/apps/desert_mapper/data.ts`** — load facility data:
   - Read `oasis_data/geocoded/vf-ghana.json` from disk at server startup
   - Export typed facility array
   - The `show-desert-map` tool handler returns all facilities as `structuredContent`

4. **Update `src/mcp-app.ts`** to render real data:
   - Parse `structuredContent` from tool result
   - Create GeoJSON `FeatureCollection` from facility array
   - Color markers by `facilityTypeId`: hospital=blue, clinic=green, health center=orange, other=gray
   - Size markers by `geocode_quality`: address=large, city=medium, centroid=small (visual honesty)

**How to verify:**
```bash
oasis init vf-ghana --src vf-ghana.csv
# Should see geocoding progress bar
# Check output:
cat oasis_data/geocoded/vf-ghana.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} facilities geocoded')"
# Rebuild and test map:
cd src/oasis/apps/desert_mapper && npm run build && npm run serve
```
- All ~1,002 facilities visible on the map
- Marker colors match facility types
- Facilities cluster in cities (Accra, Kumasi, Tamale) with some spread
- No markers at `[0, 0]` (null island = geocoding bug)

**Key references:**
- Nominatim API: `https://nominatim.openstreetmap.org/search?q={query}&format=json&countrycodes=gh&limit=1`
- Ghana region centroids: Northern (9.5, -1.0), Ashanti (6.75, -1.6), Greater Accra (5.6, -0.19), Western (5.5, -2.0), etc.

---

## Phase 3: H3 Hex Grid + 3D Extrusion

**Goal:** Add the H3 hexagonal grid layer with inverse-density coloring and 3D extrusion. This is the signature visual — extruded green hexes where facilities cluster, flat red hexes where deserts stretch.

**What to build:**

1. **Add `h3-js` dependency** to `package.json`

2. **`src/layers/hex-grid.ts`** — H3 hex layer module:
   - `computeHexGrid(facilities, resolution)`:
     - Convert each facility's lat/lng to H3 index at resolution 4 (for Ghana scale — ~22km edge length)
     - Aggregate: count facilities per hex, sum capability scores
     - Return array of `{ h3Index, center: [lat, lng], count, boundary: [[lat, lng], ...] }`
   - `addHexLayer(map, hexData)`:
     - Compute hex boundaries using `h3.cellToBoundary()`
     - Create GeoJSON `FeatureCollection` of polygons with `count` and `score` properties
     - Add as `fill-extrusion` layer:
       - `fill-extrusion-height`: interpolate from count (0 → 0m, max → 50000m) — these are map-unit meters, adjust for visual impact
       - `fill-extrusion-color`: interpolate from count — low (0-1) = red `#ef4444`, medium (2-5) = amber `#f59e0b`, high (5+) = green `#22c55e`
       - `fill-extrusion-opacity`: 0.7
       - `fill-extrusion-base`: 0
   - `removeHexLayer(map)`: clean removal for filter changes

3. **LOD transition in `src/mcp-app.ts`**:
   - Track map zoom level via `map.on('zoom', ...)`
   - Zoom ≤ 8: show hex layer, hide markers
   - Zoom > 8: hide hex layer, show markers
   - Smooth opacity transition over zoom range 7.5–8.5 using `interpolate` expressions

4. **Update tool to include hex metadata** in `structuredContent`:
   - Pre-compute hex grid on the server side and include in response
   - OR compute client-side from facility data (simpler, preferred for now)

**How to verify:**
- Open map zoomed out (zoom ~6): see hexagonal grid covering Ghana
- Red hexes visible in Northern/Upper regions (few facilities)
- Green extruded hexes in Accra, Kumasi area (dense)
- Zoom in past level 8: hexes fade out, individual markers fade in
- Rotate camera: 3D hex extrusions visible against terrain

**Key references:**
- h3-js: `latLngToCell(lat, lng, resolution)`, `cellToBoundary(h3Index)`
- Mapbox fill-extrusion layer: https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/#fill-extrusion

---

## Phase 4: Filters — Specialty + Region

**Goal:** Two dropdown filters that update both the marker layer and hex grid in real-time.

**What to build:**

1. **`src/filters.ts`** — filter control module:
   - Extract unique specialties from facility data (parse JSON arrays from `specialties` field)
   - Extract unique regions from `address_stateOrRegion` field
   - Render two `<select>` elements with "All" as default option
   - Position: top-left corner over the map, white card with subtle shadow
   - On change: emit custom event with current filter state `{ specialty: string | null, region: string | null }`

2. **Filter logic in `src/mcp-app.ts`**:
   - Listen for filter changes
   - Filter the facility GeoJSON source: `map.setFilter('facilities-layer', ['all', ...predicates])`
   - Recompute hex grid from filtered facilities (call `computeHexGrid` with filtered subset)
   - Update hex layer source data
   - Fly-to animation: when region filter changes, fly camera to that region's bounds

3. **`ontoolinput` integration**: if Claude passes `specialty` or `region` in tool args, pre-set the filters on load

**How to verify:**
- Select "surgery" → only facilities with surgery specialty visible, hex grid updates
- Select "Northern" → camera flies to Northern Ghana, only Northern facilities visible
- Select "surgery" + "Northern" → combination filter works
- Reset to "All" → everything visible again
- When Claude launches with `{ region: "Northern" }`, map starts focused on Northern Ghana

---

## Phase 5: Rich Sidebar Panel

**Goal:** Click any facility marker to open a detailed slide-in panel from the right.

**What to build:**

1. **`src/sidebar.ts`** — sidebar component:
   - Panel: 360px wide, slides in from right with CSS transform transition
   - Header: facility name + close button (×)
   - Sections:
     - **Type badge**: hospital/clinic/health center + public/private
     - **Location**: city, region, address
     - **Specialties**: rendered as colored pill badges
     - **Equipment**: bullet list parsed from JSON array
     - **Capabilities**: bullet list parsed from JSON array
     - **Procedures**: bullet list parsed from JSON array
     - **Geocode quality**: small indicator (address/city/centroid)
   - "Route to this facility" button (wired in Phase 7)
   - Close on: × button, clicking map, pressing Escape

2. **Marker click handler in `src/mcp-app.ts`**:
   - `map.on('click', 'facilities-layer', (e) => ...)`
   - Extract feature properties from click event
   - All core fields come from the pre-loaded facility data (no backend call needed for MVP)
   - Open sidebar with facility data
   - Fly camera to clicked facility with slight offset (account for sidebar width)

3. **`updateModelContext` on sidebar open**:
   - When user clicks a facility, call `app.updateModelContext()` with facility summary
   - This keeps Claude informed: "User is viewing Tamale Teaching Hospital — specialties: surgery, internal medicine. Equipment: X-ray, ultrasound..."
   - Enables Claude to offer relevant follow-ups

**How to verify:**
- Click a facility marker → sidebar slides in from right
- All fields populated (name, type, specialties, equipment, etc.)
- Close with × button → sidebar slides out
- Click different facility → sidebar updates
- In Claude Desktop: Claude's next response references the facility you clicked

---

## Phase 6: MCP Integration + Claude Desktop

**Goal:** Wire the map as a fully functional MCP App in Claude Desktop. Claude can launch it and set initial viewport.

**What to build:**

1. **Claude Desktop config** — add the desert mapper server:
   ```json
   {
     "mcpServers": {
       "oasis": { "command": "oasis", "args": ["mcp"] },
       "desert-mapper": {
         "command": "npx",
         "args": ["tsx", "src/oasis/apps/desert_mapper/main.ts", "--stdio"]
       }
     }
   }
   ```
   OR provide an `oasis config claude-map` CLI command that adds this automatically.

2. **Tool description tuning** in `server.ts`:
   - Make `show-desert-map` description clear for Claude: "Display an interactive 3D map of healthcare facilities and medical deserts in Ghana. Shows H3 hex grid with 3D extrusion (red = underserved, green = well-served). Supports filtering by medical specialty and geographic region."
   - Input schema: `{ specialty?: string, region?: string }`
   - Claude will call this tool when users ask about medical deserts, facility coverage, or geographic analysis

3. **`ontoolresult` + `ontoolinput` fine-tuning**:
   - `ontoolinput`: receive args (region, specialty), pre-set filters, fly camera to region
   - `ontoolresult`: receive full facility data, render everything
   - Handle edge case: app loads before tool result (show loading spinner, hide on data arrival)

4. **Fullscreen support** (from map-server example):
   - Fullscreen toggle button (top-right)
   - `app.requestDisplayMode({ mode: "fullscreen" })`
   - Handle `onhostcontextchanged` for display mode changes
   - Keyboard: Escape to exit, Ctrl+Enter to toggle

5. **`sendSizeChanged`** — tell host preferred inline height (500px)

**How to verify:**
- Open Claude Desktop with both MCP servers configured
- Type: "Where are the surgical deserts in Northern Ghana?"
- Claude calls `show-desert-map` with `{ specialty: "surgery", region: "Northern" }`
- Map appears inline in Claude Desktop, pre-filtered and pre-zoomed
- Click fullscreen button → map expands
- Click a facility → sidebar shows details
- Claude's next response references the map state

---

## Phase 7: Patient Routing

**Goal:** Mapbox Directions API integration for real road routing from a patient location to a facility.

**What to build:**

1. **`src/routing.ts`** — routing module:
   - `fetchRoute(origin: [lng, lat], destination: [lng, lat])`: call Mapbox Directions API
     - `https://api.mapbox.com/directions/v5/mapbox/driving/{origin};{destination}?geometries=geojson&access_token={token}`
   - Parse response: route geometry (GeoJSON LineString), duration, distance
   - `addRouteLayer(map, routeGeometry)`: add route as a `line` layer
     - Line color: `#3b82f6` (blue), width 4, dashed pattern
     - Animate with line-dasharray offset
   - `addRouteInfo(map, duration, distance)`: overlay card with "2hr 30min • 150km"
   - `removeRoute(map)`: clean up route layer + info overlay

2. **Sidebar "Route to" button** (from Phase 5):
   - On click: prompt user to click map for origin location (show instruction toast)
   - On map click: use that point as origin, facility as destination
   - Call `fetchRoute`, render route line + info card
   - Fly camera to show full route

3. **MCP tool for routing** — `query-route` tool (app-only, `visibility: ["app"]`):
   - Input: `{ origin_lat, origin_lng, destination_lat, destination_lng }`
   - Server-side: call Mapbox Directions API, return route geometry + metadata
   - This allows the route to be fetched server-side (avoids CORS/CSP issues in iframe)

4. **`updateModelContext` with route info**:
   - After route is displayed, update model context: "Route displayed: Bolgatanga → Tamale Teaching Hospital. 150km, ~2.5hr drive via N10."

**How to verify:**
- Click a facility → sidebar opens → click "Route to this facility"
- Click somewhere on the map as origin
- Blue dashed route line appears following real roads
- Info card shows distance and duration
- Camera adjusts to show full route
- In Claude Desktop: Claude mentions the route in its next response

---

## Environment Variables

| Variable | Purpose | Where |
|----------|---------|-------|
| `MAPBOX_ACCESS_TOKEN` | Mapbox GL JS + Directions API | Injected at Vite build time (UI) + available at runtime (server for Directions API) |
| `OASIS_DATA_DIR` | Path to `oasis_data/` | Server reads geocoded JSON from here |

---

## Data Flow Summary

```
vf-ghana.csv
    │
    ├── oasis init ──→ Parquet ──→ DuckDB (Python OASIS server)
    │
    └── oasis init ──→ Geocoding ──→ oasis_data/geocoded/vf-ghana.json
                                         │
                                         └── desert_mapper/server.ts reads at startup
                                              │
                                              └── show-desert-map tool returns as structuredContent
                                                   │
                                                   └── mcp-app.ts receives via ontoolresult
                                                        │
                                                        ├── Markers layer
                                                        ├── H3 hex grid layer
                                                        ├── Filters
                                                        └── Sidebar (on click)
```
