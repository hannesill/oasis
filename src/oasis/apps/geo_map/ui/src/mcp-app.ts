/**
 * OASIS GeoMap MCP App
 *
 * Interactive healthcare facility map that runs inside Claude Desktop.
 * Uses @modelcontextprotocol/ext-apps SDK to call backend MCP tools.
 * All dependencies (mapbox-gl, three.js) are bundled — no CDN needed.
 */

import {
  App,
  applyDocumentTheme,
  applyHostStyleVariables,
  applyHostFonts,
  type McpUiHostContext,
} from "@modelcontextprotocol/ext-apps";
import { isDevMode, getMockToolResult, getMockGeocodeFacilities } from "./dev-mock";

// Import mapbox-gl and three.js as bundled modules (no CDN!)
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════
// CONFIG — injected from server via ontoolresult
// ═══════════════════════════════════════════════════════════════
let MAPBOX_TOKEN = '';
let ELEVENLABS_API_KEY = '';

// ═══════════════════════════════════════════════════════════════
// MCP APP INIT
// ═══════════════════════════════════════════════════════════════
const app = new App({
  name: "OASIS GeoMap",
  version: "1.0.0",
});

let map: any;
let facilitiesGeoJSON: any = null;
let layerState = { markers: true, heatmap: false, deserts: false };
let current3DModel: string | null = null;
let audioElement: HTMLAudioElement | null = null;
let currentFacilityCoords: [number, number] | null = null;
let desertModeActive = false;
let desertLayersRendered = false;
let desertPulseTimer: ReturnType<typeof setInterval> | null = null;

// Tool result data — stored by ontoolresult, consumed after map loads
let pendingToolData: any = null;

// Ghana region center coordinates [lng, lat] for camera targeting
const REGION_COORDS: Record<string, [number, number]> = {
  'northern': [-0.9057, 9.5439],
  'upper east': [-0.8500, 10.7500],
  'upper west': [-2.1500, 10.2500],
  'greater accra': [-0.1870, 5.6037],
  'ashanti': [-1.5209, 6.7470],
  'western': [-2.1500, 5.3960],
  'eastern': [-0.4500, 6.3300],
  'central': [-1.2000, 5.4600],
  'volta': [0.5000, 6.8000],
  'brong-ahafo': [-1.5000, 7.5000],
  'bono': [-2.3000, 7.5000],
  'bono east': [-1.0500, 7.7500],
  'ahafo': [-2.3500, 7.0000],
  'savannah': [-1.8000, 9.0000],
  'north east': [-0.3500, 10.5000],
  'oti': [0.3000, 7.8000],
  'western north': [-2.3000, 6.3000],
  // Major cities as fallback
  'accra': [-0.1870, 5.6037],
  'kumasi': [-1.6244, 6.6885],
  'tamale': [-0.8393, 9.4008],
  'bolgatanga': [-0.8514, 10.7856],
  'wa': [-2.5099, 10.0601],
  'cape coast': [-1.2466, 5.1036],
  'ho': [0.4667, 6.6000],
  'sunyani': [-2.3266, 7.3349],
  'koforidua': [-0.2558, 6.0940],
  'takoradi': [-1.7554, 4.8986],
};

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════
function $(id: string): HTMLElement { return document.getElementById(id)!; }
function fmtSpec(s: string): string { return s.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()).trim(); }

function showApiStatus(_msg: string, _ok: boolean): void {
  // Status messages are used internally for flow control
}

// ═══════════════════════════════════════════════════════════════
// DESERT HEATMAP — algorithms (noise, distance, filtering, grid)
// ═══════════════════════════════════════════════════════════════

// 2D simplex noise — deterministic, returns [-1, 1]
const _perm = [151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180,151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180];
const _grad3 = [[1,1,0],[-1,1,0],[1,-1,0],[-1,-1,0],[1,0,1],[-1,0,1],[1,0,-1],[-1,0,-1],[0,1,1],[0,-1,1],[0,1,-1],[0,-1,-1]];

function simplex2(x: number, y: number): number {
  const F2 = 0.5 * (Math.sqrt(3.0) - 1.0);
  const G2 = (3.0 - Math.sqrt(3.0)) / 6.0;
  const s = (x + y) * F2;
  const i = Math.floor(x + s), j = Math.floor(y + s);
  const t = (i + j) * G2;
  const x0 = x - (i - t), y0 = y - (j - t);
  const i1 = x0 > y0 ? 1 : 0, j1 = x0 > y0 ? 0 : 1;
  const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2;
  const x2 = x0 - 1.0 + 2.0 * G2, y2 = y0 - 1.0 + 2.0 * G2;
  const ii = i & 255, jj = j & 255;
  const gi0 = _perm[ii + _perm[jj]] % 12;
  const gi1 = _perm[ii + i1 + _perm[jj + j1]] % 12;
  const gi2 = _perm[ii + 1 + _perm[jj + 1]] % 12;
  let n0 = 0, n1 = 0, n2 = 0;
  let t0 = 0.5 - x0 * x0 - y0 * y0;
  if (t0 >= 0) { t0 *= t0; n0 = t0 * t0 * (_grad3[gi0][0] * x0 + _grad3[gi0][1] * y0); }
  let t1 = 0.5 - x1 * x1 - y1 * y1;
  if (t1 >= 0) { t1 *= t1; n1 = t1 * t1 * (_grad3[gi1][0] * x1 + _grad3[gi1][1] * y1); }
  let t2 = 0.5 - x2 * x2 - y2 * y2;
  if (t2 >= 0) { t2 *= t2; n2 = t2 * t2 * (_grad3[gi2][0] * x2 + _grad3[gi2][1] * y2); }
  return 70.0 * (n0 + n1 + n2);
}

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Match terms per facility field for radiology capability detection
const _RADIO_FIELDS: Array<{ names: string[]; terms: string[] }> = [
  { names: ['specialties', 'specialty'], terms: ['radiology', 'imaging'] },
  { names: ['equipment'], terms: ['x-ray', 'xray', 'ct scan', 'ct', 'mri', 'ultrasound', 'imaging', 'radiograph', 'fluoroscop'] },
  { names: ['procedures', 'procedure'], terms: ['x-ray', 'xray', 'ct scan', 'mri', 'ultrasound', 'imaging', 'radiograph'] },
  { names: ['capability'], terms: ['radiology', 'imaging', 'x-ray', 'xray', 'ct', 'mri', 'ultrasound'] },
];

function _checkField(props: any, fieldNames: string[], terms: string[]): boolean {
  for (const fn of fieldNames) {
    const raw = props[fn];
    if (!raw) continue;
    let arr: string[];
    try { arr = typeof raw === 'string' ? JSON.parse(raw) : Array.isArray(raw) ? raw : [raw]; } catch { arr = [String(raw)]; }
    for (const item of arr) {
      const lower = String(item).toLowerCase();
      for (const term of terms) { if (lower.includes(term)) return true; }
    }
  }
  return false;
}

/**
 * For each facility, compute the haversine distance to its nearest neighbor
 * and store it as `properties.distance` (km).
 */
function computeNearestNeighborDistances(geojson: any): void {
  const features = geojson?.features;
  if (!features || features.length === 0) return;

  const coords: Array<{ lat: number; lng: number }> = features.map((f: any) => {
    const [lng, lat] = f.geometry.coordinates;
    return { lat, lng };
  });

  for (let i = 0; i < features.length; i++) {
    let minDist = Infinity;
    for (let j = 0; j < coords.length; j++) {
      if (i === j) continue;
      const d = haversineKm(coords[i].lat, coords[i].lng, coords[j].lat, coords[j].lng);
      if (d < minDist) minDist = d;
    }
    features[i].properties.distance = minDist === Infinity ? null : minDist;
  }
}

function filterRadiologyFacilities(geojson: any): Array<{ lng: number; lat: number; id: string }> {
  const results: Array<{ lng: number; lat: number; id: string }> = [];
  if (!geojson?.features) return results;
  geojson.features.forEach((feat: any, idx: number) => {
    const p = feat.properties || {};
    const isRadio = _RADIO_FIELDS.some(f => _checkField(p, f.names, f.terms));
    if (isRadio && feat.geometry?.coordinates) {
      const [lng, lat] = feat.geometry.coordinates;
      results.push({ lng, lat, id: String(p.pk_unique_id ?? p.id ?? `_idx_${idx}`) });
    }
  });
  return results;
}

function generateDesertGrid(radioFacs: Array<{ lng: number; lat: number }>): any {
  if (radioFacs.length === 0) return { type: 'FeatureCollection', features: [] };
  const latMin = 4.5, latMax = 11.2, lngMin = -3.3, lngMax = 1.3, step = 0.1;
  const points: Array<{ lng: number; lat: number; dist: number }> = [];
  let maxDist = 0;
  for (let lat = latMin; lat <= latMax; lat += step) {
    for (let lng = lngMin; lng <= lngMax; lng += step) {
      let minD = Infinity;
      for (const f of radioFacs) {
        const d = haversineKm(lat, lng, f.lat, f.lng);
        if (d < minD) minD = d;
      }
      points.push({ lng, lat, dist: minD });
      if (minD > maxDist) maxDist = minD;
    }
  }
  return {
    type: 'FeatureCollection',
    features: points.map(pt => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [pt.lng, pt.lat] },
      properties: { heat: maxDist > 0 ? pt.dist / maxDist : 0 },
    })),
  };
}

function generateIsochrone(center: [number, number], radiusKm: number, seed: number): { type: string; coordinates: number[][][] } {
  const [cLng, cLat] = center;
  const verts: number[][] = [];
  const n = 72;
  for (let i = 0; i <= n; i++) {
    const angle = (i % n) * (2 * Math.PI / n);
    // Simplex noise for natural irregularity: 2-3 lobes per rotation
    const nx = seed + Math.cos(angle) * 2.5;
    const ny = seed * 0.7 + Math.sin(angle) * 2.5;
    const distortion = 1.0 + simplex2(nx, ny) * 0.25; // +/-25%
    const r = radiusKm * distortion;
    const lat = cLat + (r / 111.32) * Math.cos(angle);
    const lng = cLng + (r / (111.32 * Math.cos(cLat * Math.PI / 180))) * Math.sin(angle);
    verts.push([lng, lat]);
  }
  return { type: 'Polygon', coordinates: [verts] };
}

function generateAllIsochrones(radioFacs: Array<{ lng: number; lat: number; id: string }>): any {
  const rings: Array<{ label: string; km: number }> = [
    { label: '30min', km: 20 },
    { label: '60min', km: 40 },
    { label: '120min', km: 70 },
  ];
  const features: any[] = [];
  for (const fac of radioFacs) {
    const seed = Math.abs(Math.sin(fac.lng * 73856.093 + fac.lat * 19349.663) * 43758.5453);
    for (const ring of rings) {
      features.push({
        type: 'Feature',
        geometry: generateIsochrone([fac.lng, fac.lat], ring.km, seed + ring.km),
        properties: { ring: ring.label, facilityId: fac.id },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

/**
 * Call an MCP tool via the App SDK and parse the JSON result
 */
async function callTool(name: string, args: Record<string, unknown>): Promise<any> {
  // Dev mode: return mock data instead of calling MCP
  if (isDevMode()) {
    if (name === 'geocode_facilities') return getMockGeocodeFacilities();
    return {};
  }

  const result = await app.callServerTool({ name, arguments: args });
  const textContent = result.content?.find((c: any) => c.type === "text");
  if (textContent && "text" in textContent) {
    const raw = textContent.text as string;
    try {
      return JSON.parse(raw);
    } catch {
      throw new Error(`Failed to parse ${name} response as JSON (got ${raw.slice(0, 120)}…)`);
    }
  }
  throw new Error(`No text content in ${name} response`);
}

// ═══════════════════════════════════════════════════════════════
// MAP INITIALIZATION
// ═══════════════════════════════════════════════════════════════
function initMap(): void {
  if (!MAPBOX_TOKEN) {
    showApiStatus('MAPBOX_TOKEN not set — add it to .env and restart MCP server', false);
    return;
  }
  mapboxgl.accessToken = MAPBOX_TOKEN;

  map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/standard',
    projection: 'globe',
    center: [0, 20],
    zoom: 1.8,
    pitch: 0,
    bearing: 0,
    antialias: true,
  });

  // No navigation controls — scroll/pinch to zoom

  map.on('style.load', () => {
    map.setConfigProperty('basemap', 'lightPreset', 'night');
    map.setConfigProperty('basemap', 'showPointOfInterestLabels', false);
    map.setConfigProperty('basemap', 'showTransitLabels', false);
    map.setConfigProperty('basemap', 'showPlaceLabels', true);
    map.setConfigProperty('basemap', 'showRoadLabels', false);
  });

  map.on('error', (e: any) => {
    $('loader').classList.add('gone');
    showApiStatus('Map error: ' + (e.error?.message || 'unknown'), false);
  });

  map.on('load', () => {
    map.addSource('mapbox-dem', { type: 'raster-dem', url: 'mapbox://mapbox.mapbox-terrain-dem-v1', tileSize: 512, maxzoom: 14 });
    map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });

    // Intro animation — fly to tool-specified target, or default Northern Ghana
    setTimeout(() => {
      $('loader').classList.add('gone');
      const target = resolveToolCameraTarget();
      map.flyTo({
        center: target ? target.center : [-0.9057, 9.5439],
        zoom: target ? target.zoom : 8,
        pitch: target ? target.pitch : 50,
        bearing: -15,
        duration: 3000,
        essential: true,
      });
    }, 400);

    // Load facilities in parallel — layers appear once data is ready
    const dataReady = loadFacilitiesViaMCP().then(() => { addMapLayers(); });

    // Apply tool data after fly-in lands AND data is loaded
    const flyDone = new Promise(resolve => setTimeout(resolve, 3600));
    Promise.all([dataReady, flyDone]).then(() => { applyToolData(); });
  });

  // Timeout fallback — don't leave user stuck on loader forever
  setTimeout(() => {
    const loader = $('loader');
    if (!loader.classList.contains('gone')) {
      loader.classList.add('gone');
      showApiStatus('Map load timed out — check console for errors', false);
    }
  }, 15000);

}

// ═══════════════════════════════════════════════════════════════
// DATA LOADING — via MCP tools
// ═══════════════════════════════════════════════════════════════
async function loadFacilitiesViaMCP(): Promise<void> {
  try {
    showApiStatus('Loading facilities via MCP…', true);
    const data = await callTool('geocode_facilities', {});
    facilitiesGeoJSON = data.geojson || { type: 'FeatureCollection', features: [] };
    computeNearestNeighborDistances(facilitiesGeoJSON);

    showApiStatus(`Loaded ${facilitiesGeoJSON.features.length} facilities`, true);
  } catch (err: any) {
    showApiStatus('Failed to load facilities: ' + err.message, false);
  }
}

// ═══════════════════════════════════════════════════════════════
// 3D MARKER IMAGE — canvas-drawn pin for elevated display
// ═══════════════════════════════════════════════════════════════
function create3DMarkerImage(): HTMLCanvasElement {
  const w = 64;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const cx = w / 2;
  const headY = 28;

  // Outer glow around beacon head
  const glow = ctx.createRadialGradient(cx, headY, 0, cx, headY, 28);
  glow.addColorStop(0, 'rgba(255, 107, 53, 0.7)');
  glow.addColorStop(0.5, 'rgba(255, 107, 53, 0.15)');
  glow.addColorStop(1, 'rgba(255, 107, 53, 0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, w, 56);

  // Stem — thin line from head down to anchor point
  ctx.beginPath();
  ctx.moveTo(cx, headY + 14);
  ctx.lineTo(cx, h - 6);
  ctx.strokeStyle = 'rgba(255, 107, 53, 0.45)';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Ground anchor dot
  ctx.beginPath();
  ctx.arc(cx, h - 4, 3.5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255, 107, 53, 0.25)';
  ctx.fill();

  // Beacon head — outer ring
  ctx.beginPath();
  ctx.arc(cx, headY, 12, 0, Math.PI * 2);
  ctx.fillStyle = '#FF6B35';
  ctx.fill();
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
  ctx.lineWidth = 3;
  ctx.stroke();

  // Beacon head — inner highlight
  ctx.beginPath();
  ctx.arc(cx, headY, 5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
  ctx.fill();

  // Medical cross on beacon (subtle)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.55)';
  ctx.fillRect(cx - 1.2, headY - 6, 2.4, 12);
  ctx.fillRect(cx - 6, headY - 1.2, 12, 2.4);

  return canvas;
}

// ═══════════════════════════════════════════════════════════════
// MAP LAYERS
// ═══════════════════════════════════════════════════════════════
function addMapLayers(): void {
  if (!facilitiesGeoJSON) return;

  map.addSource('facilities', { type: 'geojson', data: facilitiesGeoJSON });

  // Heatmap
  map.addLayer({
    id: 'layer-heatmap', type: 'heatmap', source: 'facilities',
    slot: 'middle',
    layout: { visibility: 'none' },
    paint: {
      'heatmap-weight': ['interpolate', ['linear'], ['length', ['to-string', ['get', 'specialties']]], 10, 0.2, 100, 0.5, 300, 1],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 9, 3],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 4, 6, 30, 9, 50],
      'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'],
        0, 'rgba(0,0,0,0)', 0.1, 'rgba(26,5,48,0.6)', 0.25, 'rgba(107,15,107,0.7)',
        0.4, 'rgba(255,68,68,0.8)', 0.6, 'rgba(255,153,68,0.85)', 0.8, 'rgba(255,238,68,0.9)', 1, 'rgba(255,255,255,1)'
      ],
      'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.8, 12, 0.3],
    }
  });

  // Glow
  map.addLayer({
    id: 'layer-glow', type: 'circle', source: 'facilities',
    slot: 'top',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 8, 12, 12, 18, 16, 24, 20, 30],
      'circle-color': '#FF6B35', 'circle-opacity': 0.2, 'circle-blur': 1,
    }
  });

  // Markers (flat circles — visible at ALL zoom levels)
  map.addLayer({
    id: 'layer-markers', type: 'circle', source: 'facilities',
    slot: 'top',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3, 8, 5, 12, 7, 16, 10, 20, 14],
      'circle-color': '#FF6B35', 'circle-opacity': 1,
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 4, 0.5, 10, 1.5, 16, 2.5],
      'circle-stroke-color': 'rgba(255,255,255,0.9)',
    }
  });

  // Click handlers
  const handleClick = (e: any) => {
    const f = e.features[0];
    const lngLat = e.lngLat;
    map.flyTo({ center: lngLat, zoom: Math.max(map.getZoom(), 14), pitch: 60, duration: 1500 });
    showDetail(f.properties, lngLat);
  };

  map.on('click', 'layer-markers', handleClick);
  map.on('mouseenter', 'layer-markers', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'layer-markers', () => { map.getCanvas().style.cursor = ''; });

  // Glow layer — pointer cursor only (click handled by markers layer above)
  map.on('mouseenter', 'layer-glow', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'layer-glow', () => { map.getCanvas().style.cursor = ''; });

  // 3D elevated markers — hovering pins above buildings at zoom 15+
  map.addImage('marker-3d-pin', create3DMarkerImage(), { pixelRatio: 2 });

  map.addLayer({
    id: 'layer-markers-3d',
    type: 'symbol',
    source: 'facilities',
    slot: 'top',
    minzoom: 15,
    layout: {
      'icon-image': 'marker-3d-pin',
      'icon-size': ['interpolate', ['linear'], ['zoom'], 15, 0.65, 18, 1.0, 20, 1.2],
      'icon-anchor': 'bottom',
      'icon-allow-overlap': true,
      'symbol-placement': 'point',
      'symbol-z-elevate': true,
    },
    paint: {
      'icon-opacity': ['interpolate', ['linear'], ['zoom'], 15, 0, 15.5, 1],
    }
  });

  map.on('click', 'layer-markers-3d', handleClick);
  map.on('mouseenter', 'layer-markers-3d', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'layer-markers-3d', () => { map.getCanvas().style.cursor = ''; });

}

// ═══════════════════════════════════════════════════════════════
// COVERAGE GAPS RENDER
// ═══════════════════════════════════════════════════════════════
function renderDesertGaps(gaps: any[], skipFitBounds = false): void {
  if (map.getSource('desert-gaps')) {
    if (map.getLayer('desert-circles')) map.removeLayer('desert-circles');
    if (map.getLayer('desert-labels')) map.removeLayer('desert-labels');
    map.removeSource('desert-gaps');
  }

  const features = gaps.map(g => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [g.lng, g.lat] },
    properties: { nearest_city: g.nearest_city, distance_km: g.nearest_facility_distance_km, severity: g.severity, nearest_facility: g.nearest_facility_name }
  }));

  map.addSource('desert-gaps', { type: 'geojson', data: { type: 'FeatureCollection', features } });
  map.addLayer({
    id: 'desert-circles', type: 'circle', source: 'desert-gaps',
    slot: 'middle',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 20, 8, 40, 12, 60],
      'circle-color': ['case', ['==', ['get', 'severity'], 'critical'], 'rgba(255,82,82,0.25)', 'rgba(255,152,0,0.2)'],
      'circle-blur': 0.6,
      'circle-stroke-width': 2,
      'circle-stroke-color': ['case', ['==', ['get', 'severity'], 'critical'], 'rgba(255,82,82,0.5)', 'rgba(255,152,0,0.4)'],
    }
  }, 'layer-glow');

  map.addLayer({
    id: 'desert-labels', type: 'symbol', source: 'desert-gaps',
    slot: 'top',
    layout: { 'text-field': ['concat', 'DESERT\n', ['get', 'nearest_city']], 'text-size': 10, 'text-anchor': 'center' },
    paint: { 'text-color': '#FF5252', 'text-halo-color': '#000', 'text-halo-width': 1 },
  });

  if (gaps.length > 0 && !skipFitBounds) {
    const bounds = new mapboxgl.LngLatBounds();
    gaps.forEach(g => bounds.extend([g.lng, g.lat]));
    map.fitBounds(bounds, { padding: 80, pitch: 30, duration: 2000 });
  }
}

/**
 * Render a pulsing deployment marker at the recommended placement point.
 * Used for narrative_focus="impact" to show where a surgical team should go.
 */
function renderDeploymentMarker(dep: { lat: number; lng: number; nearest_city: string; nearest_facility_distance_km: number }): void {

  // Clean up previous deployment layers
  if (map.getLayer('deploy-pulse-outer')) map.removeLayer('deploy-pulse-outer');
  if (map.getLayer('deploy-pulse-inner')) map.removeLayer('deploy-pulse-inner');
  if (map.getLayer('deploy-label')) map.removeLayer('deploy-label');
  if (map.getSource('deploy-point')) map.removeSource('deploy-point');

  const feature = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [dep.lng, dep.lat] },
      properties: { city: dep.nearest_city, distance_km: dep.nearest_facility_distance_km }
    }]
  };

  map.addSource('deploy-point', { type: 'geojson', data: feature });

  // Outer pulsing ring — animated via opacity + radius
  map.addLayer({
    id: 'deploy-pulse-outer', type: 'circle', source: 'deploy-point',
    slot: 'top',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 40, 9, 60, 12, 80],
      'circle-color': 'rgba(0, 255, 136, 0.15)',
      'circle-stroke-width': 3,
      'circle-stroke-color': 'rgba(0, 255, 136, 0.6)',
    }
  });

  // Inner solid marker
  map.addLayer({
    id: 'deploy-pulse-inner', type: 'circle', source: 'deploy-point',
    slot: 'top',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 10, 9, 16, 12, 22],
      'circle-color': '#00FF88',
      'circle-opacity': 0.9,
      'circle-stroke-width': 3,
      'circle-stroke-color': '#ffffff',
    }
  });

  // Label
  map.addLayer({
    id: 'deploy-label', type: 'symbol', source: 'deploy-point',
    slot: 'top',
    layout: {
      'text-field': ['concat', 'DEPLOY HERE\n', ['get', 'city']],
      'text-size': 13,
      'text-anchor': 'top',
      'text-offset': [0, 2.5],
      'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'],
    },
    paint: {
      'text-color': '#00FF88',
      'text-halo-color': '#000',
      'text-halo-width': 1.5,
    },
  });

  // Pulse animation — oscillate outer ring radius
  let pulsePhase = 0;
  const pulseInterval = setInterval(() => {
    if (!map.getLayer('deploy-pulse-outer')) {
      clearInterval(pulseInterval);
      return;
    }
    pulsePhase += 0.05;
    const scale = 1 + 0.3 * Math.sin(pulsePhase);
    const opacity = 0.15 + 0.1 * Math.sin(pulsePhase);
    const zoom = map.getZoom();
    const baseRadius = zoom < 8 ? 40 : zoom < 10 ? 60 : 80;
    map.setPaintProperty('deploy-pulse-outer', 'circle-radius', baseRadius * scale);
    map.setPaintProperty('deploy-pulse-outer', 'circle-color', `rgba(0, 255, 136, ${opacity})`);
  }, 50);
}

/**
 * Dim facilities outside the highlighted region.
 * Reduces opacity of markers/glow for facilities not in the target region,
 * making the highlighted region visually pop.
 */
function applyRegionHighlight(region: string): void {
  const regionLower = region.toLowerCase();

  // Substring match: check if region property contains the highlight string
  // Handles both "Northern" and "Northern Region" style values
  const inRegionExpr: any = [
    'in', regionLower,
    ['downcase', ['coalesce', ['get', 'region'], '']]
  ];

  // Bright markers in-region, dimmed markers outside
  map.setPaintProperty('layer-markers', 'circle-opacity', [
    'case', inRegionExpr, 1, 0.15
  ]);
  map.setPaintProperty('layer-markers', 'circle-stroke-opacity', [
    'case', inRegionExpr, 0.9, 0.1
  ]);
  map.setPaintProperty('layer-glow', 'circle-opacity', [
    'case', inRegionExpr, 0.2, 0.03
  ]);
}

// ═══════════════════════════════════════════════════════════════
// DESERT HEATMAP — rendering, animation, toggle
// ═══════════════════════════════════════════════════════════════

function renderDesertHeatmap(): void {
  if (!facilitiesGeoJSON || desertLayersRendered) return;
  const radioFacs = filterRadiologyFacilities(facilitiesGeoJSON);
  if (radioFacs.length === 0) return;

  // Tag each facility with _isRadiology for marker styling
  const radioIds = new Set(radioFacs.map(f => f.id));
  facilitiesGeoJSON.features.forEach((feat: any, idx: number) => {
    const p = feat.properties || {};
    const id = String(p.pk_unique_id ?? p.id ?? `_idx_${idx}`);
    feat.properties._isRadiology = radioIds.has(id) ? 1 : 0;
  });
  map.getSource('facilities').setData(facilitiesGeoJSON);

  // Generate & add data sources
  const isochrones = generateAllIsochrones(radioFacs);
  map.addSource('isochrones', { type: 'geojson', data: isochrones });
  const grid = generateDesertGrid(radioFacs);
  map.addSource('desert-grid', { type: 'geojson', data: grid });

  // Desert heatmap layer (starts invisible — animated in)
  map.addLayer({
    id: 'layer-desert-heatmap', type: 'heatmap', source: 'desert-grid',
    slot: 'middle',
    paint: {
      'heatmap-weight': ['get', 'heat'],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 0.5, 6, 1.5, 9, 2.5],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 6, 35, 9, 55],
      'heatmap-opacity': 0,
      'heatmap-color': [
        'interpolate', ['linear'], ['heatmap-density'],
        0, 'rgba(0,0,0,0)',
        0.1, 'rgba(80,0,0,0)',
        0.3, 'rgba(180,0,0,0.3)',
        0.5, 'rgba(255,30,0,0.5)',
        0.7, 'rgba(255,80,0,0.7)',
        0.9, 'rgba(255,200,50,0.85)',
        1.0, 'rgba(255,255,255,0.9)',
      ],
    },
  });

  // Isochrone fill layer
  map.addLayer({
    id: 'layer-isochrone-fill', type: 'fill', source: 'isochrones',
    slot: 'middle',
    paint: {
      'fill-color': [
        'case',
        ['==', ['get', 'ring'], '30min'], '#00FF88',
        ['==', ['get', 'ring'], '60min'], '#FFD740',
        '#FF6B35',
      ],
      'fill-opacity': 0,
    },
  });

  // Isochrone stroke layers (separate for dash patterns)
  map.addLayer({
    id: 'layer-isochrone-stroke-30', type: 'line', source: 'isochrones',
    slot: 'middle',
    filter: ['==', ['get', 'ring'], '30min'],
    paint: { 'line-color': '#00FF88', 'line-width': 1.5, 'line-opacity': 0 },
  });
  map.addLayer({
    id: 'layer-isochrone-stroke-60', type: 'line', source: 'isochrones',
    slot: 'middle',
    filter: ['==', ['get', 'ring'], '60min'],
    paint: { 'line-color': '#FFD740', 'line-width': 1.5, 'line-opacity': 0, 'line-dasharray': [4, 4] },
  });
  map.addLayer({
    id: 'layer-isochrone-stroke-120', type: 'line', source: 'isochrones',
    slot: 'middle',
    filter: ['==', ['get', 'ring'], '120min'],
    paint: { 'line-color': '#FF6B35', 'line-width': 1.5, 'line-opacity': 0, 'line-dasharray': [2, 4] },
  });

  desertLayersRendered = true;
}

function animateDesertReveal(): void {
  const dur = 2000;
  const t0 = performance.now();
  function easeOut(t: number): number { return 1 - Math.pow(1 - t, 3); }

  function tick() {
    const raw = Math.min((performance.now() - t0) / dur, 1);
    const e = easeOut(raw);

    // 1) Heatmap fade-in
    if (map.getLayer('layer-desert-heatmap'))
      map.setPaintProperty('layer-desert-heatmap', 'heatmap-opacity', e * 0.7);

    // 2) Isochrone fill fade-in (per-ring targets)
    if (map.getLayer('layer-isochrone-fill'))
      map.setPaintProperty('layer-isochrone-fill', 'fill-opacity', [
        'case',
        ['==', ['get', 'ring'], '30min'], e * 0.15,
        ['==', ['get', 'ring'], '60min'], e * 0.10,
        e * 0.08,
      ]);

    // 3) Isochrone strokes fade-in
    for (const s of ['30', '60', '120']) {
      const lid = `layer-isochrone-stroke-${s}`;
      if (map.getLayer(lid)) map.setPaintProperty(lid, 'line-opacity', e * 0.8);
    }

    // 4) Radiology markers: orange -> cyan color transition
    const r = Math.round(255 * (1 - e));
    const g = Math.round(107 + 105 * e);
    const b = Math.round(53 + 202 * e);
    map.setPaintProperty('layer-markers', 'circle-color', [
      'case', ['==', ['get', '_isRadiology'], 1], `rgb(${r},${g},${b})`, '#FF6B35',
    ]);

    // 5) Non-radiology markers: dim opacity 1 -> 0.2
    map.setPaintProperty('layer-markers', 'circle-opacity', [
      'case', ['==', ['get', '_isRadiology'], 1], 1.0, 1.0 - e * 0.8,
    ]);

    // 6) Non-radiology glow: dim
    map.setPaintProperty('layer-glow', 'circle-opacity', [
      'case', ['==', ['get', '_isRadiology'], 1], 0.2, Math.max(0.03, 0.2 * (1 - e)),
    ]);

    // 7) Radiology markers: grow +2px
    map.setPaintProperty('layer-markers', 'circle-radius', [
      'case', ['==', ['get', '_isRadiology'], 1],
      ['interpolate', ['linear'], ['zoom'], 4, 3 + e * 2, 8, 5 + e * 2, 12, 7 + e * 2, 16, 10 + e * 2, 20, 14 + e * 2],
      ['interpolate', ['linear'], ['zoom'], 4, 3, 8, 5, 12, 7, 16, 10, 20, 14],
    ]);

    // 8) Non-radiology stroke: dim
    map.setPaintProperty('layer-markers', 'circle-stroke-color', [
      'case', ['==', ['get', '_isRadiology'], 1],
      'rgba(255,255,255,0.9)',
      `rgba(255,255,255,${(0.9 * (1 - e * 0.89)).toFixed(2)})`,
    ]);

    if (raw < 1) {
      requestAnimationFrame(tick);
    } else {
      // Final zoom-dependent heatmap opacity
      map.setPaintProperty('layer-desert-heatmap', 'heatmap-opacity', [
        'interpolate', ['linear'], ['zoom'], 0, 0.7, 5, 0.6, 12, 0.3,
      ]);
      startDesertPulse();
    }
  }
  requestAnimationFrame(tick);
}

function startDesertPulse(): void {
  if (desertPulseTimer) return;
  const t0 = performance.now();
  desertPulseTimer = setInterval(() => {
    if (!desertModeActive || !map.getLayer('layer-markers')) { stopDesertPulse(); return; }
    const elapsed = (performance.now() - t0) / 1000;
    const pulse = Math.sin(elapsed * 2.5);
    const offset = pulse * 3;
    const glowOp = 0.25 + pulse * 0.1;
    map.setPaintProperty('layer-markers', 'circle-radius', [
      'case', ['==', ['get', '_isRadiology'], 1],
      ['interpolate', ['linear'], ['zoom'], 4, 5 + offset, 8, 7 + offset, 12, 9 + offset, 16, 12 + offset, 20, 16 + offset],
      ['interpolate', ['linear'], ['zoom'], 4, 3, 8, 5, 12, 7, 16, 10, 20, 14],
    ]);
    map.setPaintProperty('layer-glow', 'circle-opacity', [
      'case', ['==', ['get', '_isRadiology'], 1], glowOp, 0.03,
    ]);
  }, 50) as any;
}

function stopDesertPulse(): void {
  if (desertPulseTimer) { clearInterval(desertPulseTimer); desertPulseTimer = null; }
}

function toggleDesertMode(active: boolean): void {
  desertModeActive = active;
  $('desert-legend').classList.toggle('show', active);
  if (active) {
    if (!desertLayersRendered) renderDesertHeatmap();
    if (!desertLayersRendered) { $('desert-legend').classList.remove('show'); return; } // no radiology facilities found

    // Reset opacities for animation
    map.setPaintProperty('layer-desert-heatmap', 'heatmap-opacity', 0);
    map.setPaintProperty('layer-isochrone-fill', 'fill-opacity', 0);
    for (const s of ['30', '60', '120'])
      map.setPaintProperty(`layer-isochrone-stroke-${s}`, 'line-opacity', 0);

    // Ensure visible
    map.setLayoutProperty('layer-desert-heatmap', 'visibility', 'visible');
    map.setLayoutProperty('layer-isochrone-fill', 'visibility', 'visible');
    for (const s of ['30', '60', '120'])
      map.setLayoutProperty(`layer-isochrone-stroke-${s}`, 'visibility', 'visible');

    // Show gap circles too if they exist
    if (map.getLayer('desert-circles')) {
      map.setLayoutProperty('desert-circles', 'visibility', 'visible');
      map.setLayoutProperty('desert-labels', 'visibility', 'visible');
    }

    animateDesertReveal();
  } else {
    stopDesertPulse();
    if (desertLayersRendered) {
      map.setLayoutProperty('layer-desert-heatmap', 'visibility', 'none');
      map.setLayoutProperty('layer-isochrone-fill', 'visibility', 'none');
      for (const s of ['30', '60', '120'])
        map.setLayoutProperty(`layer-isochrone-stroke-${s}`, 'visibility', 'none');
    }
    if (map.getLayer('desert-circles')) {
      map.setLayoutProperty('desert-circles', 'visibility', 'none');
      map.setLayoutProperty('desert-labels', 'visibility', 'none');
    }
    // Restore marker styling
    map.setPaintProperty('layer-markers', 'circle-color', '#FF6B35');
    map.setPaintProperty('layer-markers', 'circle-opacity', 1);
    map.setPaintProperty('layer-markers', 'circle-stroke-color', 'rgba(255,255,255,0.9)');
    map.setPaintProperty('layer-markers', 'circle-radius',
      ['interpolate', ['linear'], ['zoom'], 4, 3, 8, 5, 12, 7, 16, 10, 20, 14]);
    map.setPaintProperty('layer-glow', 'circle-opacity', 0.2);
  }
}

// ═══════════════════════════════════════════════════════════════
// DETAIL CARD + 3D MODEL + NARRATION
// ═══════════════════════════════════════════════════════════════
function emptyLabel(val: any): string {
  if (val === null || val === undefined || val === '' || val === 'NaN' || val === 'nan' || val === 'None' || val === 'null') return 'Not existing';
  const s = String(val).trim();
  return s.length === 0 ? 'Not existing' : s;
}

function setInfoVal(id: string, val: any): void {
  const el = $(id);
  const display = emptyLabel(val);
  el.textContent = display;
  el.classList.toggle('empty', display === 'Not existing');
}

function parseJsonArray(raw: any): string[] {
  if (!raw || raw === '' || raw === 'null' || raw === 'None') return [];
  try {
    const arr = typeof raw === 'string' ? JSON.parse(raw) : Array.isArray(raw) ? raw : [raw];
    return arr.filter(Boolean).map((s: any) => String(s).trim()).filter((s: string) => s.length > 0);
  } catch { return []; }
}

function renderChips(containerId: string, countId: string, items: string[], chipClass: string, limit: number = 15): void {
  $(countId).textContent = String(items.length);
  const html = items.length > 0
    ? items.slice(0, limit).map(c => `<span class="cap-chip ${chipClass}">${c}</span>`).join('')
      + (items.length > limit ? `<span class="cap-chip ${chipClass}">+${items.length - limit}</span>` : '')
    : '<span class="cap-chip empty-tag">Not existing</span>';
  $(containerId).innerHTML = html;
}

function formatPhone(raw: any): string {
  if (!raw || raw === '' || raw === 'null' || raw === 'None') return '';
  try {
    const arr = typeof raw === 'string' ? JSON.parse(raw) : Array.isArray(raw) ? raw : [raw];
    const phones = arr.filter(Boolean).map((s: any) => String(s).trim()).filter((s: string) => s.length > 0);
    return phones.length > 0 ? phones[0] : '';
  } catch {
    return String(raw).trim();
  }
}

function showDetail(props: any, lngLat: any): void {
  // Header
  $('d-name').textContent = props.name || '—';
  $('d-type').textContent = props.facility_type || 'Facility';

  // Operator type badge
  const opEl = $('d-operator');
  const opType = emptyLabel(props.operator_type);
  if (opType !== 'Not existing') {
    opEl.textContent = opType;
    opEl.style.display = '';
  } else {
    opEl.style.display = 'none';
  }

  // Stats
  const specsCount = parseJsonArray(props.specialties).length;
  $('d-specs-total').textContent = specsCount > 0 ? String(specsCount) : '—';
  $('d-dist').textContent = props.distance != null ? props.distance.toFixed(1) + ' km' : '—';
  $('d-city').textContent = props.city || '—';

  // Info rows
  setInfoVal('d-region', props.region);
  setInfoVal('d-address', props.address);
  setInfoVal('d-phone', formatPhone(props.phone));
  setInfoVal('d-year', props.year_established);

  // Description
  const desc = emptyLabel(props.description);
  const descSection = $('d-desc-section');
  if (desc !== 'Not existing') {
    $('d-desc').textContent = desc.length > 200 ? desc.slice(0, 200) + '...' : desc;
    descSection.style.display = '';
  } else {
    descSection.style.display = 'none';
  }

  // Specialties (cyan tags)
  const specs = parseJsonArray(props.specialties);
  renderChips('d-specs', 'd-specs-count', specs.map(fmtSpec), 'spec');

  // Procedures (green tags)
  const procs = parseJsonArray(props.procedures);
  renderChips('d-procs', 'd-procs-count', procs, 'proc');

  // Equipment (yellow tags)
  const equip = parseJsonArray(props.equipment);
  renderChips('d-equip', 'd-equip-count', equip, 'equip');

  // Capabilities (purple tags)
  const caps = parseJsonArray(props.capability);
  renderChips('d-caps', 'd-caps-count', caps, 'capab');

  $('detail-card').classList.add('show');

  const coords: [number, number] = lngLat ? [lngLat.lng, lngLat.lat] : (props.coords || [0, 0]);
  currentFacilityCoords = coords;
  add3DHospitalModel(coords, props.name || 'Hospital');
  if (ELEVENLABS_API_KEY) narrateFacility(props);
}

function closeDetail(): void {
  $('detail-card').classList.remove('show');
  if (current3DModel && map.getLayer(current3DModel)) {
    map.removeLayer(current3DModel);
    current3DModel = null;
  }
  if (audioElement) { audioElement.pause(); audioElement = null; }
}

// ═══════════════════════════════════════════════════════════════
// LAYER TOGGLES
// ═══════════════════════════════════════════════════════════════
function toggleLayer(name: string): void {
  (layerState as any)[name] = !(layerState as any)[name];
  const on = (layerState as any)[name];
  const btn = document.getElementById(`tog-${name}`);
  if (btn) btn.classList.toggle('on', on);

  switch (name) {
    case 'markers':
      map.setLayoutProperty('layer-markers', 'visibility', on ? 'visible' : 'none');
      map.setLayoutProperty('layer-glow', 'visibility', on ? 'visible' : 'none');
      if (map.getLayer('layer-markers-3d')) {
        map.setLayoutProperty('layer-markers-3d', 'visibility', on ? 'visible' : 'none');
      }
      break;
    case 'heatmap':
      map.setLayoutProperty('layer-heatmap', 'visibility', on ? 'visible' : 'none');
      $('heatmap-legend').classList.toggle('show', on);
      break;
    case 'deserts':
      toggleDesertMode(on);
      break;
  }
}

// ═══════════════════════════════════════════════════════════════
// 3D HOSPITAL MODEL (three.js)
// ═══════════════════════════════════════════════════════════════
function add3DHospitalModel(coords: number[], name: string): void {
  if (current3DModel && map.getLayer(current3DModel)) map.removeLayer(current3DModel);

  const merc = mapboxgl.MercatorCoordinate.fromLngLat(coords, 0);
  const modelTransform = {
    translateX: merc.x, translateY: merc.y, translateZ: merc.z,
    rotateX: Math.PI / 2, rotateY: 0, rotateZ: 0,
    scale: merc.meterInMercatorCoordinateUnits()
  };

  const layerId = '3d-model-hospital';
  current3DModel = layerId;

  const customLayer = {
    id: layerId, type: 'custom', renderingMode: '3d',
    onAdd(mapInstance: any, gl: WebGLRenderingContext) {
      this.camera = new THREE.Camera();
      this.scene = new THREE.Scene();
      this.clock = new THREE.Clock();

      this.scene.add(new THREE.AmbientLight(0xccddff, 0.6));
      const sun = new THREE.DirectionalLight(0xffffff, 1.0);
      sun.position.set(50, -80, 120);
      this.scene.add(sun);
      const fill = new THREE.DirectionalLight(0x8899cc, 0.4);
      fill.position.set(-40, 60, 80);
      this.scene.add(fill);

      const wallMat = new THREE.MeshPhongMaterial({ color: 0xf0f0f0, specular: 0x222222, shininess: 30 });
      const glassMat = new THREE.MeshPhongMaterial({ color: 0x88ccff, specular: 0xffffff, shininess: 100, opacity: 0.6, transparent: true });
      const accentMat = new THREE.MeshPhongMaterial({ color: 0xFF6B35, specular: 0xff8855, shininess: 60 });
      const crossMat = new THREE.MeshPhongMaterial({ color: 0xff0000, emissive: 0xff2200, emissiveIntensity: 0.5 });
      const roofMat = new THREE.MeshPhongMaterial({ color: 0x445566 });
      const padMat = new THREE.MeshPhongMaterial({ color: 0x334455 });

      const hospital = new THREE.Group();

      const mainBody = new THREE.Mesh(new THREE.BoxGeometry(60, 30, 40), wallMat);
      mainBody.position.set(0, 0, 20);
      hospital.add(mainBody);

      for (let f = 0; f < 5; f++) {
        const z = 5 + f * 8;
        hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(56, 0.5, 4), glassMat), { position: new THREE.Vector3(0, -15.3, z) }));
        hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(56, 0.5, 4), glassMat), { position: new THREE.Vector3(0, 15.3, z) }));
        hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(0.5, 26, 4), glassMat), { position: new THREE.Vector3(-30.3, 0, z) }));
        hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(0.5, 26, 4), glassMat), { position: new THREE.Vector3(30.3, 0, z) }));
      }

      const wingGeo = new THREE.BoxGeometry(20, 20, 16);
      const wingL = new THREE.Mesh(wingGeo, wallMat); wingL.position.set(-40, 0, 8); hospital.add(wingL);
      const wingR = new THREE.Mesh(wingGeo, wallMat); wingR.position.set(40, 0, 8); hospital.add(wingR);

      const stripe = new THREE.Mesh(new THREE.BoxGeometry(62, 31, 2), accentMat); stripe.position.set(0, 0, 41); hospital.add(stripe);
      const roof = new THREE.Mesh(new THREE.BoxGeometry(64, 33, 1), roofMat); roof.position.set(0, 0, 42); hospital.add(roof);
      const padCircle = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 0.3, 32), padMat); padCircle.rotation.x = Math.PI / 2; padCircle.position.set(0, 0, 42.5); hospital.add(padCircle);

      const hMat = new THREE.MeshPhongMaterial({ color: 0xffffff });
      hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(1, 6, 0.2), hMat), { position: new THREE.Vector3(-2, 0, 42.8) }));
      hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(1, 6, 0.2), hMat), { position: new THREE.Vector3(2, 0, 42.8) }));
      hospital.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(5, 1, 0.2), hMat), { position: new THREE.Vector3(0, 0, 42.8) }));

      const canopy = new THREE.Mesh(new THREE.BoxGeometry(16, 8, 1), accentMat); canopy.position.set(0, -19, 10); hospital.add(canopy);
      const cH = new THREE.Mesh(new THREE.BoxGeometry(8, 0.5, 2), crossMat); cH.position.set(0, -15.5, 22); hospital.add(cH);
      const cV = new THREE.Mesh(new THREE.BoxGeometry(2, 0.5, 8), crossMat); cV.position.set(0, -15.5, 22); hospital.add(cV);

      this.beacon = new THREE.PointLight(0xff0000, 2, 200); this.beacon.position.set(0, 0, 48); hospital.add(this.beacon);
      hospital.add(new THREE.Mesh(new THREE.BoxGeometry(100, 60, 0.5), new THREE.MeshPhongMaterial({ color: 0x445544 })));

      this.scene.add(hospital);
      this.map = mapInstance;
      this.renderer = new THREE.WebGLRenderer({ canvas: mapInstance.getCanvas(), context: gl, antialias: true });
      this.renderer.autoClear = false;
    },
    render(gl: WebGLRenderingContext, matrix: number[]) {
      if (this.beacon && this.clock) {
        this.beacon.intensity = 1 + Math.sin(this.clock.getElapsedTime() * 3) * 1.5;
      }
      const rX = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), modelTransform.rotateX);
      const rY = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(0, 1, 0), modelTransform.rotateY);
      const rZ = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(0, 0, 1), modelTransform.rotateZ);
      const m = new THREE.Matrix4().fromArray(matrix);
      const l = new THREE.Matrix4()
        .makeTranslation(modelTransform.translateX, modelTransform.translateY, modelTransform.translateZ)
        .scale(new THREE.Vector3(modelTransform.scale, -modelTransform.scale, modelTransform.scale))
        .multiply(rX).multiply(rY).multiply(rZ);
      this.camera.projectionMatrix = m.multiply(l);
      this.renderer.resetState();
      this.renderer.render(this.scene, this.camera);
    }
  };

  map.addLayer(customLayer);
}

// ═══════════════════════════════════════════════════════════════
// ELEVENLABS NARRATION
// ═══════════════════════════════════════════════════════════════
async function narrateFacility(props: any): Promise<void> {
  if (audioElement) { audioElement.pause(); audioElement = null; }
  if (!ELEVENLABS_API_KEY) return;

  let specs: string[] = [];
  try { specs = JSON.parse(props.specialties || '[]'); } catch (e) { /* ignore */ }
  const text = `${props.name || 'This facility'}. ${props.city ? 'Located in ' + props.city + '.' : ''} ${specs.length > 0 ? 'Specialties include ' + specs.slice(0, 3).map(s => s.replace(/([A-Z])/g, ' $1')).join(', ') + '.' : ''}`;

  try {
    const response = await fetch('https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM', {
      method: 'POST',
      headers: { 'Accept': 'audio/mpeg', 'Content-Type': 'application/json', 'xi-api-key': ELEVENLABS_API_KEY },
      body: JSON.stringify({ text, model_id: 'eleven_monolingual_v1', voice_settings: { stability: 0.5, similarity_boost: 0.5 } })
    });
    if (response.ok) {
      const audioBlob = await response.blob();
      audioElement = new Audio(URL.createObjectURL(audioBlob));
      audioElement.play();
    }
  } catch {
    // Narration unavailable — continue silently
  }
}

// ═══════════════════════════════════════════════════════════════
// HOST CONTEXT — theme, safe areas
// ═══════════════════════════════════════════════════════════════
function applyHostContext(ctx: McpUiHostContext): void {
  if (ctx.theme) applyDocumentTheme(ctx.theme);
  if (ctx.styles?.variables) applyHostStyleVariables(ctx.styles.variables);
  if (ctx.styles?.css?.fonts) applyHostFonts(ctx.styles.css.fonts);
  if (ctx.safeAreaInsets) {
    const { top, right, bottom, left } = ctx.safeAreaInsets;
    document.body.style.padding = `${top}px ${right}px ${bottom}px ${left}px`;
  }
}

// ═══════════════════════════════════════════════════════════════
// MODEL → UI DATA FLOW — render tool results directly
// ═══════════════════════════════════════════════════════════════

/**
 * Resolve camera target from pending tool data.
 * Called before the intro fly-to to override the default Ghana overview.
 */
function resolveToolCameraTarget(): { center: [number, number]; zoom: number; pitch: number } | null {
  if (!pendingToolData) {
    return null;
  }

  const data = pendingToolData;
  const initialZoom = data.initial_zoom || 6.0;

  // Priority 0: impact mode with recommended deployment — zoom to that point
  if (data.narrative_focus === 'impact' && data.recommended_deployment) {
    const dep = data.recommended_deployment;
    return { center: [dep.lng, dep.lat], zoom: 13, pitch: 55 };
  }

  // Priority 1: explicit highlight_region
  if (data.highlight_region) {
    const regionKey = data.highlight_region.toLowerCase();
    const coords = REGION_COORDS[regionKey];
    if (coords) {
      return { center: coords, zoom: initialZoom, pitch: 45 };
    }
  }

  // Priority 2: search mode with center
  if (data.mode === 'search' && data.center?.lat && data.center?.lng) {
    return { center: [data.center.lng, data.center.lat], zoom: Math.max(initialZoom, 8), pitch: 45 };
  }

  // Priority 3: deserts mode — fit to gaps handled by renderDesertGaps
  // but if we have a custom zoom, at least go to Ghana center at that zoom
  if (data.mode === 'deserts' && initialZoom !== 6.0) {
    return { center: [-1.0232, 7.9465], zoom: initialZoom, pitch: 45 };
  }

  return null;
}

/**
 * Apply pending tool data to the map.
 * Renders deserts/search results from the tool result directly,
 * so the UI doesn't need a separate user interaction.
 */
function applyToolData(): void {
  if (!pendingToolData) return;

  const data = pendingToolData;
  pendingToolData = null;

  const hasHighlightRegion = !!data.highlight_region;

  // -- Region highlighting: dim facilities outside the target region --
  if (hasHighlightRegion) {
    applyRegionHighlight(data.highlight_region);
  }

  // -- Desert mode: render heatmap + gap circles --
  if (data.mode === 'deserts') {
    // Update desert legend title with the condition name
    const condition = data.query?.condition || data.condition || 'Radiology';
    const conditionLabel = condition.charAt(0).toUpperCase() + condition.slice(1);
    $('desert-legend-title').textContent = `${conditionLabel} Deserts`;

    if (data.gaps?.length > 0) {
      renderDesertGaps(data.gaps, hasHighlightRegion);
    }
    toggleDesertMode(true);
    layerState.deserts = true;
    $('tog-deserts').classList.add('on');
    showApiStatus(`${data.gap_count || data.gaps?.length || 0} coverage gaps for ${data.query?.condition || 'specialty'}`, true);
  }

  // -- Narrative focus overlays --
  if (data.narrative_focus === 'deserts' && !desertModeActive) {
    toggleDesertMode(true);
    layerState.deserts = true;
    $('tog-deserts').classList.add('on');
  }

  // -- Impact mode: add pulsing deployment marker at recommended point --
  if (data.narrative_focus === 'impact' && data.recommended_deployment) {
    renderDeploymentMarker(data.recommended_deployment);
  }
}

// ═══════════════════════════════════════════════════════════════
// MCP APP LIFECYCLE
// ═══════════════════════════════════════════════════════════════

// Called when the geo_map tool is first invoked
app.ontoolinput = () => {
  // Show loading state
  $('loader').classList.remove('gone');
};

// Called when the geo_map tool result is received
app.ontoolresult = (result: any) => {
  try {
    const textContent = result?.content?.find((c: any) => c.type === 'text');
    if (textContent && 'text' in textContent) {
      const data = JSON.parse(textContent.text as string);

      // Extract config (Mapbox token, ElevenLabs key)
      if (data.config) {
        MAPBOX_TOKEN = data.config.mapbox_token || '';
        ELEVENLABS_API_KEY = data.config.elevenlabs_api_key || '';
      }

      // Store full tool data — applied after map + facilities load
      pendingToolData = data;
    }
  } catch {
    // Tool result parsing failed — map will still initialize
  }

  initMap();
};

// Handle host context changes (theme, safe area, display modes)
app.onhostcontextchanged = (ctx) => {
  applyHostContext(ctx);
  if (ctx.displayMode) {
    currentDisplayMode = ctx.displayMode;
    const btn = document.getElementById('tog-fullscreen');
    if (btn) btn.classList.toggle('on', currentDisplayMode === 'fullscreen');
    setTimeout(() => map?.resize(), 100);
  }
};

// Handle teardown
app.onteardown = async () => {
  if (audioElement) { audioElement.pause(); audioElement = null; }
  return {};
};

// ═══════════════════════════════════════════════════════════════
// FULLSCREEN TOGGLE
// ═══════════════════════════════════════════════════════════════
let currentDisplayMode: string = 'inline';

async function toggleFullscreen(): Promise<void> {
  const newMode = currentDisplayMode === 'fullscreen' ? 'inline' : 'fullscreen';
  const result = await app.requestDisplayMode({ mode: newMode });
  currentDisplayMode = result.mode;
  const btn = document.getElementById('tog-fullscreen');
  if (btn) btn.classList.toggle('on', currentDisplayMode === 'fullscreen');
  setTimeout(() => map?.resize(), 100);
}

// ═══════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════
$('btn-close-detail').addEventListener('click', closeDetail);
$('btn-recenter').addEventListener('click', () => {
  if (currentFacilityCoords && map) {
    map.flyTo({ center: currentFacilityCoords, zoom: 17, pitch: 60, bearing: -15, duration: 1500 });
  }
});
$('tog-fullscreen').addEventListener('click', toggleFullscreen);

// Layer toggle buttons
document.querySelectorAll('[data-layer]').forEach(btn => {
  btn.addEventListener('click', () => {
    toggleLayer((btn as HTMLElement).dataset.layer!);
  });
});

// Navigation pill buttons
document.querySelectorAll('[data-fly]').forEach(btn => {
  btn.addEventListener('click', () => {
    const [lng, lat, zoom] = (btn as HTMLElement).dataset.fly!.split(',').map(Number);
    map.flyTo({ center: [lng, lat], zoom, pitch: 45, bearing: -15, duration: 2500 });
  });
});

// ═══════════════════════════════════════════════════════════════
// CONNECT TO HOST (or start in dev mode)
// ═══════════════════════════════════════════════════════════════
if (isDevMode()) {
  // Dev mode: skip MCP connection, inject mock data, init map directly
  const mockResult = getMockToolResult();
  MAPBOX_TOKEN = mockResult.config.mapbox_token;
  ELEVENLABS_API_KEY = mockResult.config.elevenlabs_api_key || '';
  pendingToolData = mockResult;
  if (!MAPBOX_TOKEN) {
    document.getElementById('loader')!.innerHTML = `
      <div style="color:#FF6B35;font-size:16px;text-align:center;padding:20px;font-family:system-ui">
        <div style="font-size:32px;margin-bottom:16px">🗺️</div>
        <strong>VITE_MAPBOX_TOKEN not set</strong><br><br>
        Create <code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px">src/oasis/apps/geo_map/ui/.env</code> with:<br>
        <code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px">VITE_MAPBOX_TOKEN=pk.ey...</code><br><br>
        Then restart <code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px">npm run dev</code>
      </div>`;
  } else {
    initMap();
  }
} else {
  app.connect().then(() => {
    const ctx = app.getHostContext();
    if (ctx) applyHostContext(ctx);

    // Request initial iframe height from the host
    app.sendSizeChanged({ width: 0, height: 600 });

    // Connected to Claude Desktop via MCP
  });
}

