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
let layerState = { markers: true, heatmap: false, buildings: false, deserts: false };
let current3DModel: string | null = null;
let audioElement: HTMLAudioElement | null = null;
let allSpecialties: string[] = [];

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

function showApiStatus(msg: string, ok: boolean): void {
  console.log(`[OASIS] ${ok ? '✅' : '⚠️'} ${msg}`);
}

/**
 * Call an MCP tool via the App SDK and parse the JSON result
 */
async function callTool(name: string, args: Record<string, unknown>): Promise<any> {
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
    style: 'mapbox://styles/mapbox/dark-v11',
    projection: 'globe',
    center: [0, 20],
    zoom: 1.8,
    pitch: 0,
    bearing: 0,
    antialias: true,
  });

  // No navigation controls — scroll/pinch to zoom

  map.on('style.load', () => {
    map.setFog({
      color: 'rgb(10,10,30)',
      'high-color': 'rgb(30,50,120)',
      'horizon-blend': 0.08,
      'space-color': 'rgb(5,5,15)',
      'star-intensity': 0.95,
    });
  });

  map.on('error', (e: any) => {
    console.error('Mapbox error:', e.error || e);
    $('loader').classList.add('gone');
    showApiStatus('Map error: ' + (e.error?.message || 'unknown'), false);
  });

  map.on('load', async () => {
    map.addSource('mapbox-dem', { type: 'raster-dem', url: 'mapbox://mapbox.mapbox-terrain-dem-v1', tileSize: 512, maxzoom: 14 });
    map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });
    map.addLayer({ id: 'sky', type: 'sky', paint: { 'sky-type': 'atmosphere', 'sky-atmosphere-sun': [0, 90], 'sky-atmosphere-sun-intensity': 15 } });

    // Load facilities via MCP tool
    await loadFacilitiesViaMCP();
    addMapLayers();

    // Determine intro camera target — tool data can override the default
    const toolTarget = resolveToolCameraTarget();

    // Intro animation
    setTimeout(() => {
      $('loader').classList.add('gone');
      if (toolTarget) {
        // Model-driven fly-to (highlight_region or search center)
        map.flyTo({ center: toolTarget.center, zoom: toolTarget.zoom, pitch: toolTarget.pitch, bearing: -15, duration: 4000, essential: true });
      } else {
        // Default: fly to Ghana overview
        map.flyTo({ center: [-1.0232, 7.9465], zoom: 6.5, pitch: 50, bearing: -15, duration: 4000, essential: true });
      }
    }, 2200);

    // Apply tool data (deserts, search results, narrative focus) after a short delay
    // so the fly-to animation has started
    setTimeout(() => { applyToolData(); }, 2800);
  });

  // Timeout fallback — don't leave user stuck on loader forever
  setTimeout(() => {
    const loader = $('loader');
    if (!loader.classList.contains('gone')) {
      loader.classList.add('gone');
      showApiStatus('Map load timed out — check console for errors', false);
    }
  }, 15000);

  map.on('zoom', () => { if (map.getZoom() >= 14 && !layerState.buildings) toggleLayer('buildings'); });
}

// ═══════════════════════════════════════════════════════════════
// DATA LOADING — via MCP tools
// ═══════════════════════════════════════════════════════════════
async function loadFacilitiesViaMCP(): Promise<void> {
  try {
    showApiStatus('Loading facilities via MCP…', true);
    const data = await callTool('geocode_facilities', {});
    facilitiesGeoJSON = data.geojson || { type: 'FeatureCollection', features: [] };

    // Compute stats
    const cities = new Set<string>();
    const specs = new Set<string>();
    facilitiesGeoJSON.features.forEach((f: any) => {
      const p = f.properties;
      if (p.city) cities.add(p.city);
      try { JSON.parse(p.specialties || '[]').forEach((s: string) => specs.add(s)); } catch (e) { /* ignore */ }
    });

    allSpecialties = [...specs].sort();

    showApiStatus(`Loaded ${facilitiesGeoJSON.features.length} facilities`, true);
  } catch (err: any) {
    console.error('Failed to load facilities via MCP:', err);
    showApiStatus('Failed to load facilities: ' + err.message, false);
  }
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
  }, 'waterway-label');

  // Glow
  map.addLayer({
    id: 'layer-glow', type: 'circle', source: 'facilities',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 8, 12, 12, 18],
      'circle-color': '#FF6B35', 'circle-opacity': 0.15, 'circle-blur': 1,
    }
  });

  // Markers (flat circles)
  map.addLayer({
    id: 'layer-markers', type: 'circle', source: 'facilities',
    maxzoom: 10,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 5, 10, 8],
      'circle-color': '#FF6B35', 'circle-opacity': 0.85,
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 4, 0.5, 10, 2],
      'circle-stroke-color': 'rgba(255,255,255,0.6)', 'circle-blur': 0.1,
    }
  });

  // 3D Buildings from Mapbox tiles
  const labelLayer = map.getStyle().layers.find((l: any) => l.type === 'symbol' && l.layout?.['text-field']);
  map.addLayer({
    id: 'layer-buildings', source: 'composite', 'source-layer': 'building',
    filter: ['==', 'extrude', 'true'], type: 'fill-extrusion', minzoom: 13,
    layout: { visibility: 'none' },
    paint: {
      'fill-extrusion-color': ['interpolate', ['linear'], ['get', 'height'], 0, '#1a1a3e', 20, '#2a2a5e', 50, '#4a3a7e'],
      'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 13, 0, 14.5, ['get', 'height']],
      'fill-extrusion-base': ['interpolate', ['linear'], ['zoom'], 13, 0, 14.5, ['get', 'min_height']],
      'fill-extrusion-opacity': 0.75,
    }
  }, labelLayer ? labelLayer.id : undefined);

  // Click handlers
  const handleClick = (e: any) => {
    const f = e.features[0];
    const lngLat = e.lngLat;
    map.flyTo({ center: lngLat, zoom: Math.max(map.getZoom(), 16), pitch: 60, duration: 1500 });
    if (!layerState.buildings) toggleLayer('buildings');
    showDetail(f.properties, lngLat);
  };

  map.on('click', 'layer-markers', handleClick);
  map.on('mouseenter', 'layer-markers', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'layer-markers', () => { map.getCanvas().style.cursor = ''; });
}

// ═══════════════════════════════════════════════════════════════
// COVERAGE GAPS RENDER
// ═══════════════════════════════════════════════════════════════
function renderDesertGaps(gaps: any[]): void {
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
    layout: { 'text-field': ['concat', 'DESERT\n', ['get', 'nearest_city']], 'text-size': 10, 'text-anchor': 'center' },
    paint: { 'text-color': '#FF5252', 'text-halo-color': '#000', 'text-halo-width': 1 },
  });

  if (gaps.length > 0) {
    const bounds = new mapboxgl.LngLatBounds();
    gaps.forEach(g => bounds.extend([g.lng, g.lat]));
    map.fitBounds(bounds, { padding: 80, pitch: 30, duration: 2000 });
  }
}

// ═══════════════════════════════════════════════════════════════
// DETAIL CARD + 3D MODEL + NARRATION
// ═══════════════════════════════════════════════════════════════
function showDetail(props: any, lngLat: any): void {
  $('d-name').textContent = props.name || '—';
  $('d-type').textContent = props.facility_type || 'Facility';

  let specs: string[] = [];
  try { specs = JSON.parse(props.specialties || '[]'); } catch (e) { /* ignore */ }
  $('d-specs').textContent = String(specs.length);
  $('d-dist').textContent = props.distance != null ? props.distance.toFixed(1) + ' km' : '—';
  $('d-city').textContent = props.city || '—';

  let equip: string[] = [];
  try { equip = JSON.parse(props.equipment || '[]').filter(Boolean); } catch (e) { /* ignore */ }
  const chips = [...specs.map(fmtSpec), ...equip];
  $('d-caps').innerHTML = chips.slice(0, 12).map(c => `<span class="cap-chip">${c}</span>`).join('') + (chips.length > 12 ? `<span class="cap-chip">+${chips.length - 12}</span>` : '');

  $('detail-card').classList.add('show');

  const coords = lngLat ? [lngLat.lng, lngLat.lat] : (props.coords || [0, 0]);
  add3DHospitalModel(coords, props.name || 'Hospital');
  narrateFacility(props);
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
      break;
    case 'heatmap':
      map.setLayoutProperty('layer-heatmap', 'visibility', on ? 'visible' : 'none');
      $('heatmap-legend').classList.toggle('show', on);
      break;
    case 'buildings':
      map.setLayoutProperty('layer-buildings', 'visibility', on ? 'visible' : 'none');
      break;
    case 'deserts':
      if (map.getLayer('desert-circles')) {
        map.setLayoutProperty('desert-circles', 'visibility', on ? 'visible' : 'none');
        map.setLayoutProperty('desert-labels', 'visibility', on ? 'visible' : 'none');
      }
      break;
  }
}

// ═══════════════════════════════════════════════════════════════
// 3D HOSPITAL MODEL (three.js)
// ═══════════════════════════════════════════════════════════════
function add3DHospitalModel(coords: number[], name: string): void {
  if (!THREE) return;
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
      this.map.triggerRepaint();
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
  } catch (err) {
    console.error('ElevenLabs narration error:', err);
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
  if (!pendingToolData) return null;

  const data = pendingToolData;
  const initialZoom = data.initial_zoom || 6.0;

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

  // -- Desert mode: render gap circles directly --
  if (data.mode === 'deserts' && data.gaps?.length > 0) {
    renderDesertGaps(data.gaps);
    layerState.deserts = true;
    $('tog-deserts').classList.add('on');

    // Turn on heatmap for visual density context
    if (!layerState.heatmap) toggleLayer('heatmap');

    showApiStatus(`${data.gap_count || data.gaps.length} coverage gaps for ${data.query?.condition || 'specialty'}`, true);
  }

  // -- Narrative focus overlays --
  if (data.narrative_focus === 'deserts' && !layerState.heatmap) {
    toggleLayer('heatmap');
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
  } catch (err) {
    console.error('Failed to parse geo_map tool result:', err);
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
// CONNECT TO HOST
// ═══════════════════════════════════════════════════════════════
app.connect().then(() => {
  const ctx = app.getHostContext();
  if (ctx) applyHostContext(ctx);

  // Request initial iframe height from the host
  app.sendSizeChanged({ width: 0, height: 600 });

  console.log('[OASIS] Connected to Claude Desktop via MCP');
});

