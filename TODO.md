# OASIS — Implementation TODOs for Demo Script

## Critical (demo breaks without these)

### 1. Fix frontend marker visibility DONE
FIXGEO.md has the full plan. In `src/oasis/apps/geo_map/ui/src/mcp-app.ts`:
- Remove `maxzoom: 10` from markers layer
- Extend marker sizing interpolation to zoom 20
- Change flyTo zoom from 16 to 14 on click
- Remove `circle-blur: 0.1`
- Rebuild: `npm run build` in `src/oasis/apps/geo_map/ui/`

### 2. Add region filtering to `FindCoverageGapsTool`
`highlight_region="Northern"` only moves the camera — the SQL query still scans all of Ghana. In `src/oasis/core/tools/geospatial.py`:
- Add `region: str | None` param to `FindCoverageGapsInput`
- Filter facilities SQL with `WHERE address_stateOrRegion ILIKE '%{region}%'`
- Constrain grid generation to region bounding box
- Wire through from `GeoMapTool` in `src/oasis/apps/geo_map/tool.py`

### 3. Build `detect_anomalies` tool (Beat 2 fallback)
Beat 2 calls `search_facility_capabilities` (Databricks RAG) — which doesn't exist yet. If RAG isn't ready, this tool is the only way Beat 2 works. In new file `src/oasis/core/tools/anomaly.py`:
- Cross-reference free-form fields (`procedure`, `equipment`, `capability`) against structured fields (`numberDoctors`, `capacity`, `facilityTypeId`)
- Heuristics: procedure count vs staff, claimed specialties vs equipment, facility type vs capabilities
- Return: `{facility, anomaly_type, severity, free_form_claim, structured_fact}`
- Register in `src/oasis/core/tools/__init__.py` and expose in `mcp_server.py`
- **Fallback script for Beat 2:** Call `detect_anomalies(region="Northern", focus="surgery")` → Claude narrates the worst anomaly. No RAG needed.

### 4. Add optimal placement to `FindCoverageGapsTool` (Beat 3 differentiation)
Beat 3 calls the same tool with the same params as Beat 1. Without distinct output, judges see the same map twice. In `src/oasis/core/tools/geospatial.py`:
- Add `recommend_placement: bool = False` param to `FindCoverageGapsInput`
- When true, compute the centroid of the largest gap cluster (or the single worst gap point)
- Return a `recommended_placement: {lat, lng, rationale, coverage_gain_km2}` field
- Frontend reads this to render a distinct "deploy here" marker (pulsing gold pin, not red zone)
- Wire through from `GeoMapTool` when `narrative_focus="impact"`

### 5. Add `@traced` to core tools
Beat 4 calls `get_citation_trace` but only RAG/Genie calls are traced. The main analysis steps are invisible. In `src/oasis/core/tools/geospatial.py` and `tabular.py`:
- Import `traced` from `oasis.databricks.tracing`
- Wrap key invoke methods or inner functions with `@traced`
- At minimum: `find_coverage_gaps`, `execute_query`, `find_facilities_in_radius`

## Important (demo works but claims are hollow)

### 6. Beat 4 fallback if Databricks tracing isn't ready
`get_citation_trace` depends on MLflow being integrated. If it isn't, Beat 4 has no tool to call. Options (pick one):
- **Option A (visual closer):** Cut the tool call. Camera pulls back to all of Ghana showing every facility + every desert. Claude says one closing line. No citations claim, no Databricks mention — but a strong visual ending.
- **Option B (fake-it-till-you-make-it):** Build a lightweight `get_citation_trace` that returns a static JSON of the tool calls from the current session (tool name, params, timestamp). Not real MLflow tracing, but shows the concept. Risk: judges ask how it works.
- **Recommendation:** Option A is safer for a recorded demo. Option B only if Databricks integration is close.

### 7. Population estimates — add real data or drop the claim
Script claims "~50,000 per gap zone" with no source. Risk: judges ask "where does that number come from?" in Q&A. Options:
- **Better:** Embed Ghana Statistical Service district population data (2021 census) as a CSV/dict. Calculate real affected population per gap zone by summing nearby district populations. Return `affected_population` with a citation to the census.
- **Safer:** Drop population claims entirely. "The nearest surgeon is 180km away" is visceral enough without an unverifiable headcount.

### 8. Add impact mode visualization
`narrative_focus="impact"` is accepted but renders identically to "deserts". In `mcp-app.ts`:
- Differentiate rendering: e.g., size desert circles by population impact, pulse the optimal placement
- Add a "recommended placement" marker style for Beat 3 (gold pulsing pin)
- Rebuild after changes

## Polish

### 9. Anomaly warning badges on map
When `narrative_focus="anomaly"`, mark flagged facilities with warning icons in the map UI. Detail card should show anomaly details in red.
