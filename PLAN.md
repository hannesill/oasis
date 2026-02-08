# Medical Desert Mapper — Enhancement Plan

## Foundation (Already Built)

The `geo_map` MCP App (`src/oasis/apps/geo_map/`) is working end-to-end:
- Python FastMCP server with `_meta.ui.resourceUri` injection
- Mapbox GL JS with dark globe, 3D terrain, space fog, star field
- Facility markers + heatmap + 3D building layers with toggles
- Runtime geocoding via `GHANA_CITY_COORDS` lookup + deterministic jitter
- Search by condition + location + radius (calls `find_facilities_in_radius` via MCP)
- Coverage gap visualization (calls `find_coverage_gaps` via MCP)
- 3D hospital model (three.js) on facility click
- Detail card with specialties, equipment, distance
- `updateModelContext` keeping Claude aware of user's map state
- ElevenLabs TTS narration (auto-plays on click — needs toggle)

**What's missing for the demo:**
1. H3 hex grid — the signature "medical desert" visual
2. Specialty + Region filter dropdowns
3. Patient routing overlay on map
4. Fullscreen support
5. ElevenLabs is auto-play (should be opt-in)

---

## Phase 1: H3 Hex Grid + 3D Extrusion

**Goal:** Add the H3 hexagonal grid layer with inverse-density coloring and 3D extrusion. This is the signature visual — extruded green hexes where facilities cluster, flat red hexes where deserts stretch. Replaces the heatmap as the primary overview layer.

**What to build:**

1. **Add `h3-js` dependency** to `src/oasis/apps/geo_map/ui/package.json`

2. **Hex grid computation** in `mcp-app.ts` (or a new `hex-grid.ts` imported by it):
   - `computeHexGrid(geojson, resolution)`:
     - Convert each facility's lat/lng to H3 index at resolution 4 (~22km edge length, good for Ghana scale)
     - Aggregate: count facilities per hex
     - Return GeoJSON `FeatureCollection` of hex polygons with `count` property
   - `addHexLayer(map, hexGeoJSON)`:
     - Add as `fill-extrusion` layer:
       - `fill-extrusion-height`: interpolate from count (0 → 0m, max → 50000m)
       - `fill-extrusion-color`: low (0-1) = red `#ef4444`, medium (2-5) = amber `#f59e0b`, high (5+) = green `#22c55e`
       - `fill-extrusion-opacity`: 0.7
     - Use `h3.cellToBoundary()` to get hex polygon coordinates
   - `updateHexLayer(map, hexGeoJSON)`: update source data (for filter changes)
   - `removeHexLayer(map)`: clean removal

3. **LOD transitions** in `mcp-app.ts`:
   - Zoom ≤ 8: show hex layer, hide markers
   - Zoom > 8: hide hex layer, show markers
   - Smooth opacity transition over zoom range 7.5–8.5 using Mapbox `interpolate` expressions
   - Keep heatmap as an optional toggle (off by default now, hex grid replaces it as primary)

4. **Add hex grid toggle** to existing layer toggle buttons:
   - New toggle `tog-hexgrid` (on by default)
   - Heatmap toggle becomes off by default

**How to verify:**
- Open map zoomed out (zoom ~6): see hexagonal grid covering Ghana
- Red hexes visible in Northern/Upper regions (few facilities)
- Green extruded hexes in Accra, Kumasi area (dense)
- Zoom in past level 8: hexes fade out, individual markers fade in
- Rotate camera: 3D hex extrusions visible against terrain
- Toggle hex grid off → clean removal

**Key references:**
- h3-js: `latLngToCell(lat, lng, resolution)`, `cellToBoundary(h3Index)`
- Mapbox fill-extrusion layer: https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/#fill-extrusion

---

## Phase 2: Specialty + Region Filters

**Goal:** Add dropdown filters that update markers, hex grid, and search results in real-time. Enables the demo flow: "Show me surgical deserts in Northern Ghana" → filters pre-set, camera flies to region.

**What to build:**

1. **Two dropdown `<select>` elements** in the existing UI (HTML in `mcp-app.html`):
   - Specialty dropdown: populated from `allSpecialties` (already extracted in `loadFacilitiesViaMCP`)
   - Region dropdown: populated from unique `address_stateOrRegion` values
   - Position: integrate into existing control panel (glass card style)
   - Default: "All" for both

2. **Filter logic** in `mcp-app.ts`:
   - On specialty change: filter the `facilities` GeoJSON source using `map.setFilter()`
   - On region change:
     - Filter GeoJSON source
     - Fly camera to region bounds (use `GHANA_CITY_COORDS` region centroids already in geospatial.py — pass via tool result or hardcode client-side)
   - **Recompute hex grid** from filtered subset (call `computeHexGrid` with filtered features)
   - Update hex layer source data

3. **`ontoolinput` integration**: if Claude passes `condition` or `region` in `geo_map` tool args, pre-set the dropdown filters on load and trigger the filter logic

**How to verify:**
- Select "surgery" → only surgery facilities visible, hex grid updates to show surgery deserts
- Select "Northern" → camera flies to Northern Ghana, only Northern facilities shown
- Combine both → intersection filter
- Reset to "All" → full dataset restored
- Claude launches map with `{ condition: "surgery", location: "Northern" }` → filters pre-set

---

## Phase 3: Patient Routing Overlay

**Goal:** Show real road routes on the map. Supports demo step 3: "Route a patient in Bolgatanga to emergency appendectomy."

**What to build:**

1. **Routing function** in `mcp-app.ts` (or new `routing.ts`):
   - `fetchRoute(origin: [lng, lat], destination: [lng, lat])`:
     - Call Mapbox Directions API: `https://api.mapbox.com/directions/v5/mapbox/driving/{origin};{destination}?geometries=geojson&access_token={token}`
     - Parse response: route geometry (GeoJSON LineString), duration, distance
   - `addRouteLayer(map, routeGeometry)`:
     - Line color: `#3b82f6` (blue), width 4, dashed pattern
   - `addRouteInfo(duration, distance)`:
     - Overlay card: "2hr 30min — 150km"
   - `removeRoute(map)`: clean up route layer + info overlay

2. **"Route to this facility" button** in the detail card:
   - Add button to existing `detail-card` HTML
   - On click: show instruction toast "Click the map to set patient location"
   - On next map click: use that point as origin, facility as destination
   - Call `fetchRoute`, render route line + info card
   - Fly camera to show full route bounds

3. **`updateModelContext` with route info**:
   - After route displayed: "Route: Bolgatanga → Tamale Teaching Hospital. 150km, ~2.5hr drive."

**How to verify:**
- Click facility → detail card → "Route to this facility"
- Click somewhere on map as patient origin
- Blue dashed route line appears following real roads
- Info card shows distance and duration
- Camera adjusts to show full route

**Note:** Mapbox Directions API uses the same `MAPBOX_TOKEN`. The request is made client-side from the iframe — verify CSP allows `api.mapbox.com` (it should, since map tiles already load from there).

---

## Phase 4: Polish

**Goal:** Small improvements that elevate the demo experience.

**What to build:**

1. **Fullscreen support**:
   - Add fullscreen toggle button (top-right, next to nav controls)
   - Call `app.requestDisplayMode({ mode: "fullscreen" })` on click
   - Handle `onhostcontextchanged` for display mode transitions
   - Keyboard: `F` to toggle fullscreen

2. **ElevenLabs narration toggle**:
   - Add a small speaker icon toggle to the detail card (muted by default)
   - Only call `narrateFacility()` when toggle is on
   - Remove auto-play behavior from `showDetail()`

3. **Hex grid legend**:
   - Small legend card (bottom-left) when hex layer is visible
   - Red = 0-1 facilities, Amber = 2-5, Green = 5+
   - Shows what the extrusion height and colors mean

**How to verify:**
- Fullscreen button works in Claude Desktop
- Narration only plays when speaker icon is toggled on
- Legend appears/disappears with hex grid toggle

---

## Environment Variables

| Variable | Purpose | Where |
|----------|---------|-------|
| `MAPBOX_TOKEN` | Mapbox GL JS + Directions API | Read by `mcp_server.py`, passed to UI via `ontoolresult` config |
| `ELEVENLABS_API_KEY` | TTS narration (optional) | Read by `mcp_server.py`, passed to UI via `ontoolresult` config |

---

## Data Flow (Current)

```
vf-ghana.csv
    │
    └── oasis init ──→ Parquet ──→ DuckDB
                                     │
                    geo_map tool ─────┘
                         │
                         ├── ontoolresult → config (tokens)
                         │
                         └── UI calls MCP tools at runtime:
                              │
                              ├── geocode_facilities → GeoJSON → markers + hex grid
                              ├── find_facilities_in_radius → search results
                              └── find_coverage_gaps → desert circles
```
