# Radiology Desert Heatmap — Feature Spec

## Overview

An inverse heatmap visualization for the OASIS geo_map app that shows **capability deserts** — areas of Ghana far from facilities offering radiology services. The heatmap uses simulated drive-time isochrone rings (not uniform circles) around radiology-capable facilities, with a red "danger" color scheme where the hottest areas represent the most underserved zones.

**Scope:** Frontend-only. No backend changes. Demo-only feature.

---

## Architecture

### Layer Stack (bottom to top)

1. **Desert Heatmap** (`layer-desert-heatmap`) — Mapbox heatmap layer, slot: `middle`
   - Source: Dense grid of virtual GeoJSON points covering all of Ghana
   - Each point's `heat` value = straight-line (Euclidean) distance to the nearest radiology facility
   - Color ramp: **transparent → deep red → bright red → white** (farther = hotter)
   - Covers the entire Ghana bounding box (~500-1000 grid points)
   - Independent of zoom/pan — always complete

2. **Isochrone Rings** (`layer-isochrone-fill` + `layer-isochrone-stroke`) — GeoJSON polygon layers, slot: `middle`
   - Three concentric rings per radiology facility: **30 min, 60 min, 120 min**
   - Polygons generated client-side with **procedural noise distortion** (Perlin/simplex), **20-30% irregularity**
   - Fill: graduated color (green → yellow → orange, decreasing opacity outward)
   - Stroke: **visible ring borders** — subtle dashed or solid lines demarcating each threshold
   - No interactivity (no hover, no click)

3. **Radiology Facility Markers** — Modified existing marker layers
   - Radiology facilities: **bright cyan/white pulsing marker** overlay
   - Non-radiology facilities: **dimmed to ~20% opacity**

### Data Flow

```
facilitiesGeoJSON (already loaded)
  → filter by radiology capability (broad match)
  → for each radiology facility:
      → generate 3 isochrone polygons (30/60/120 min) with procedural noise
  → generate desert grid points across Ghana bounding box
      → for each grid point: heat = min distance to any radiology facility
  → add all sources & layers to map
```

---

## Facility Filtering (Broad Match)

A facility qualifies as "radiology-capable" if **any** of these fields contain matching terms:

| Field | Match Terms |
|-------|------------|
| `specialties` | `radiology`, `imaging` |
| `equipment` | `x-ray`, `xray`, `ct scan`, `ct`, `mri`, `ultrasound`, `imaging`, `radiograph`, `fluoroscop` |
| `procedures` | `x-ray`, `xray`, `ct scan`, `mri`, `ultrasound`, `imaging`, `radiograph` |
| `capability` | `radiology`, `imaging`, `x-ray`, `xray`, `ct`, `mri`, `ultrasound` |

All matching is **case-insensitive substring**. Fields are JSON-encoded string arrays — parse then search each element.

---

## Isochrone Polygon Generation

### Drive-Time to Distance Mapping

| Threshold | Assumed Speed | Radius |
|-----------|--------------|--------|
| 30 min | 40 km/h (mixed road) | ~20 km |
| 60 min | 40 km/h | ~40 km |
| 120 min | 35 km/h (rural roads) | ~70 km |

### Procedural Noise Distortion

- Generate polygon vertices at **5° angular intervals** (72 vertices per ring)
- For each vertex, apply **simplex/Perlin noise** seeded by the facility's coordinates
- Distortion magnitude: **20-30% of the base radius**
- Noise frequency: ~2-3 cycles per full rotation (creates 2-3 "fingers" per ring)
- Inner rings (30 min) should be slightly less distorted than outer rings (120 min)
- Noise is **deterministic** — same facility always produces the same shape

### Ring Styling

| Ring | Fill Color | Fill Opacity | Stroke Color | Stroke Width | Stroke Dash |
|------|-----------|-------------|-------------|-------------|-------------|
| 30 min | `#00FF88` (green) | 0.15 | `#00FF88` | 1.5px | solid |
| 60 min | `#FFD740` (yellow) | 0.10 | `#FFD740` | 1.5px | `[4, 4]` |
| 120 min | `#FF6B35` (orange) | 0.08 | `#FF6B35` | 1.5px | `[2, 4]` |

---

## Desert Heatmap Grid

### Grid Generation

- **Bounding box:** Ghana — lat [4.5, 11.2], lng [-3.3, 1.3]
- **Grid density:** ~0.1° spacing → ~67 × 46 = ~3,000 points
- **Heat value:** For each grid point, compute Euclidean distance (in km) to the nearest radiology facility using Haversine formula
- **Normalization:** Map distance to [0, 1] range where 0 = at facility, 1 = max distance observed

### Heatmap Color Ramp

```
0.0 → transparent (at a radiology facility)
0.1 → rgba(80, 0, 0, 0.0)    (very close, no heat)
0.3 → rgba(180, 0, 0, 0.3)   (30-60 min away)
0.5 → rgba(255, 30, 0, 0.5)  (60-120 min)
0.7 → rgba(255, 80, 0, 0.7)  (2+ hours)
0.9 → rgba(255, 200, 50, 0.85) (severe desert)
1.0 → rgba(255, 255, 255, 0.9) (worst desert — white hot)
```

### Heatmap Layer Config

```javascript
{
  type: 'heatmap',
  paint: {
    'heatmap-weight': ['get', 'heat'],
    'heatmap-intensity': [interpolate, zoom-based: 0→0.5, 6→1.5, 9→2.5],
    'heatmap-radius': [interpolate, zoom-based: 0→8, 6→35, 9→55],
    'heatmap-opacity': [interpolate, zoom-based: 0→0.7, 5→0.6, 12→0.3],
    'heatmap-color': [see ramp above]
  }
}
```

---

## Toggle Button

- **Replaces** the existing "Deserts" button in the toolbar
- **Label:** "Deserts" (same label, new behavior)
- **Behavior:** Toggles visibility of:
  - `layer-desert-heatmap`
  - `layer-isochrone-fill`
  - `layer-isochrone-stroke`
  - Radiology marker highlighting (cyan pulse + dimming others)
- **State:** Off by default. Toggled on when `mode='deserts'` is received from tool call.

---

## Reveal Animation

### Simultaneous Radiate-Outward (~2 seconds)

When the desert layer is toggled on:

1. **Frame 0:** All desert layers added but heatmap radius = 0, isochrone fill opacity = 0
2. **Frames 0–2000ms:**
   - Heatmap radius animates from 0 → target value (eased with `ease-out-cubic`)
   - Isochrone polygon fill opacity fades from 0 → target
   - Isochrone stroke opacity fades from 0 → target
   - Radiology markers pulse begins
   - Non-radiology markers dim from 100% → 20% opacity
3. **Animation driven by `requestAnimationFrame`** with timestamp-based progress

All radiology facilities radiate simultaneously — single expanding frontier of red.

---

## Radiology Facility Marker Style

When desert mode is active:

| Property | Radiology Facilities | Non-Radiology Facilities |
|----------|---------------------|-------------------------|
| Circle color | `#00D4FF` (cyan) | `#FF6B35` (orange, unchanged) |
| Circle opacity | 1.0 | 0.2 |
| Circle radius | +2px larger than normal | Normal |
| Stroke color | `#FFFFFF` | `#FFFFFF` |
| Stroke opacity | 0.9 | 0.1 |
| Glow | Pulsing cyan glow (animated) | Hidden |

Pulsing cyan glow: radius oscillates ±3px via `sin(elapsed * 2.5)`, opacity oscillates 0.15–0.35.

---

## Implementation Notes

### No Backend Changes

- All data comes from `facilitiesGeoJSON` already loaded in the frontend
- Grid points generated entirely in JavaScript
- Isochrone polygons generated entirely in JavaScript
- Noise function: Use a lightweight simplex noise implementation (~50 lines, embed in the file)

### Performance Considerations

- ~3,000 grid points is well within Mapbox heatmap performance limits
- Isochrone polygons: if ~10-20 radiology facilities × 3 rings = 30-60 polygons, trivial
- Animation: use a single `requestAnimationFrame` loop, not per-layer timers

### Key Functions to Add

1. `filterRadiologyFacilities(geojson)` → returns filtered FeatureCollection
2. `generateIsochrone(center, radiusKm, seed)` → returns GeoJSON Polygon
3. `generateDesertGrid(radiologyFacilities)` → returns GeoJSON FeatureCollection of points with `heat` property
4. `renderDesertHeatmap(radiologyFacilities)` → adds all layers to map
5. `animateDesertReveal()` → handles the radiate-outward animation
6. `toggleDesertMode(active)` → orchestrates show/hide + marker dimming

### Files to Modify

- `src/oasis/apps/geo_map/ui/src/mcp-app.ts` — all changes in this file
- `src/oasis/apps/geo_map/ui/src/mcp-app.html` — update "Deserts" button if needed (likely no change since we're replacing behavior)

---

## Out of Scope

- Backend tool changes
- Mapbox Isochrone API calls
- Hover/click interactivity on desert zones
- Legend card
- Real road network data
- Viewport-dependent grid regeneration
