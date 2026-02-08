# Medical Desert Mapper — 45-Second Demo Plan

## Foundation (Already Built)

The `geo_map` MCP App (`src/oasis/apps/geo_map/`) is working:
- Mapbox GL JS with dark globe
- Facility markers + heatmap layers
- Runtime geocoding via `GHANA_CITY_COORDS`
- Coverage gap visualization (calls `find_coverage_gaps`)
- Detail card with specialties, equipment, distance

## 45-50 Second Demo Flow (Screen Studio — speed-controlled, not live)

```
0:00 - 0:10  "Where are surgical deserts in Northern Ghana?"
             → Hex grid appears, red zones pulse, camera flies to Northern region

0:10 - 0:20  Click worst gap → "150km to nearest surgeon"
             Click anomalous facility → "Claims 50 surgeries/month, only 2 staff"

0:20 - 0:35  "Where should we place one new surgeon?"
             → Impact heatmap overlay, click optimal zone
             → "Would serve 50,000 people currently without access"

0:35 - 0:50  "As a Ghana healthcare official, what's my single most
              impactful next action?"
             → Model reasons in chat over desert + anomaly data
             → "Deploy a surgical team to [location]"
             → Map flies to that location, impact radius lights up
             → Presenter: "One question. One answer. That's OASIS."
```

## What's Missing (Priority Order)

**Must Build:**
1. ⭐ **Model → UI data passing** — Eliminate duplicate queries, enable model control
2. ⭐ **H3 hex grid** — THE signature visual (red = deserts, green = coverage)
3. ⭐ **Anomaly highlighting** — Warning badges on problematic facilities
4. ⭐ **Impact heatmap** — Shows where new facilities help most

**Cut from scope:**
- ❌ Interactive filters (model controls everything, no user interaction in 45 sec)
- ❌ Patient routing (doesn't score high enough for time cost)
- ❌ 3D buildings, ElevenLabs narration (distractions)
- ❌ Fullscreen, polish (no time)
- ❌ Bidirectional commands (too complex)

---

## Phase 1: Model → UI Data Flow ✅ DONE

Model passes query results directly to UI via `ontoolresult`. Tool accepts `mode`, `condition`, `highlight_region`, `narrative_focus`, `initial_zoom`. UI renders facilities/gaps from tool result without duplicate queries. Camera flies to highlighted region.

---

## Phase 2: H3 Hex Grid ⭐ 3 hours

**Goal:** THE signature visual. Red hexes = medical deserts, green = coverage. 3D extrusion by density.

**Build:**

1. **Add `h3-js`** to `package.json`

2. **Hex grid** in `mcp-app.ts`:
   - `computeHexGrid(facilities, resolution=4)` → count per hex
   - `addHexLayer(map, hexGeoJSON)`:
     - `fill-extrusion` layer
     - Color: 0-1 facilities = red `#ef4444`, 2-5 = amber, 5+ = green `#22c55e`
     - Height: 0 → 0m, max → 40000m
   - Auto-show at zoom ≤ 8 (hide markers)
   - Auto-hide at zoom > 8 (show markers)

3. **Pulse animation** on red hexes (deserts):
   - Subtle opacity pulse: 0.5 → 0.8 → 0.5 (2 sec cycle)
   - Only on hexes with count = 0

**Verify:** `geo_map(mode="deserts", condition="surgery")` → Red hexes pulse in Northern Ghana, green extrusions in Accra

---

## Phase 3: Anomaly + Impact Overlay ⭐ 5 hours

**Goal:** Demo beats #2 ("Does this facility really do surgery?") and #4 ("Where to place a surgeon?"). Show data inconsistencies and optimal resource placement.

**Build:**

1. **Anomaly detection**:
   - Call `detect_anomalies` MCP tool on map load
   - Store anomaly list
   - On facility click: check if anomalous
   - If yes:
     - ⚠️ badge on marker
     - Red pulse outline on card
     - Anomaly section in detail card:
       - "Claims 50 surgeries/month but only 2 staff"
       - Confidence score
   - If `narrative_focus="anomaly"`: auto-fly to worst anomaly, open card

2. **Impact heatmap**:
   - If `narrative_focus="impact"`:
     - Generate grid across Ghana (same as `find_coverage_gaps`)
     - For each red hex (low density):
       - Calculate population that would gain access if facility added
       - Color: deep red (high impact) → yellow → transparent
     - Add as overlay layer
   - On click of impact zone:
     - Card: "Placing facility here → 50,000 people gain access"
     - Show which deserts it would close

**Verify:**
- `geo_map(narrative_focus="anomaly")` → Flies to worst facility, anomaly card open
- `geo_map(narrative_focus="impact")` → Impact heatmap active, click shows coverage gain

---

## Execution Plan

**Total: 12 hours** — Build phases sequentially in priority order:

1. **Phase 1** ~~(4h)~~ — Model → UI data flow ✅ DONE
2. **Phase 2** (3h) — H3 hex grid [SIGNATURE VISUAL]
3. **Phase 3** (5h) — Anomaly + Impact [DEMO BEATS #2 + #4]

**Assignment:**
- **Hannes:** Phase 1 (data flow, tool params)
- **Fourth Member (Map Dev):** Phase 2 (h3-js, hex rendering)
- **Jakob:** Phase 3 (anomaly integration, impact heatmap)

**Required env vars:**
- `MAPBOX_TOKEN` (get from Mapbox, free tier)
- `OASIS_DATASET=vf-ghana`

**Cut features** (don't build):
- Interactive filters (model controls everything)
- Patient routing (doesn't score high enough)
- 3D buildings, narration, fullscreen
- Bidirectional commands (too risky for 45 sec)

**Demo script rehearsal:**
```bash
# Test exact demo flow
oasis use vf-ghana

# Beat 1: Deserts
geo_map(mode="deserts", condition="surgery", highlight_region="Northern", initial_zoom=7, narrative_focus="deserts")
# Expect: Red hexes pulse in Northern Ghana, camera flies there

# Beat 2: Anomaly (click interactions — Screen Studio controls mouse)
geo_map(narrative_focus="anomaly")
# Expect: Fly to facility with ⚠️ badge, card shows "Claims 50 surgeries, only 2 staff"

# Beat 3: Impact
geo_map(narrative_focus="impact", condition="surgery")
# Expect: Heatmap shows optimal placement, click → "50,000 people gain access"

# Beat 4: Actionable recommendation (the closer)
# User types: "As a Ghana healthcare official, what's my single most impactful next action?"
# Expect: Model reasons in chat, recommends specific location, map flies there, impact radius highlights
```
