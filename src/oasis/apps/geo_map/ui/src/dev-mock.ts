/**
 * Dev mode mock data for standalone browser preview.
 *
 * When running `npm run dev` (Vite dev server), the MCP host is unavailable.
 * This module provides mock tool results so the map renders with sample data.
 *
 * Set your Mapbox token in ui/.env:
 *   VITE_MAPBOX_TOKEN=pk.ey...
 */

/** Sample facilities scattered across Ghana */
const MOCK_FACILITIES: any[] = [
  { name: "Tamale Teaching Hospital", facility_type: "Teaching Hospital", city: "Tamale", lat: 9.4008, lng: -0.8393, specialties: '["generalSurgery","emergencyMedicine","pediatrics","obstetrics"]', equipment: '["xRay","ultrasound","ventilator"]', capability: '["trauma","bloodBank"]' },
  { name: "Korle Bu Teaching Hospital", facility_type: "Teaching Hospital", city: "Accra", lat: 5.5364, lng: -0.2280, specialties: '["cardiology","neurology","generalSurgery","oncology","orthopedics"]', equipment: '["mri","ctScanner","xRay","ultrasound"]', capability: '["openHeartSurgery","dialysis","icu"]' },
  { name: "Komfo Anokye Teaching Hospital", facility_type: "Teaching Hospital", city: "Kumasi", lat: 6.6940, lng: -1.6280, specialties: '["generalSurgery","emergencyMedicine","obstetrics","orthopedics"]', equipment: '["ctScanner","xRay","ultrasound","ventilator"]', capability: '["trauma","icu","bloodBank"]' },
  { name: "Bolgatanga Regional Hospital", facility_type: "Regional Hospital", city: "Bolgatanga", lat: 10.7856, lng: -0.8514, specialties: '["generalSurgery","emergencyMedicine","pediatrics"]', equipment: '["xRay","ultrasound"]', capability: '["trauma"]' },
  { name: "Wa Regional Hospital", facility_type: "Regional Hospital", city: "Wa", lat: 10.0601, lng: -2.5099, specialties: '["generalSurgery","obstetrics"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Cape Coast Teaching Hospital", facility_type: "Teaching Hospital", city: "Cape Coast", lat: 5.1036, lng: -1.2466, specialties: '["generalSurgery","pediatrics","obstetrics","dermatology"]', equipment: '["xRay","ultrasound","ctScanner"]', capability: '["icu"]' },
  { name: "Ho Municipal Hospital", facility_type: "Municipal Hospital", city: "Ho", lat: 6.6000, lng: 0.4667, specialties: '["generalSurgery","emergencyMedicine"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Sunyani Regional Hospital", facility_type: "Regional Hospital", city: "Sunyani", lat: 7.3349, lng: -2.3266, specialties: '["generalSurgery","obstetrics","pediatrics"]', equipment: '["xRay","ultrasound"]', capability: '["bloodBank"]' },
  { name: "Koforidua Regional Hospital", facility_type: "Regional Hospital", city: "Koforidua", lat: 6.0940, lng: -0.2558, specialties: '["generalSurgery","emergencyMedicine","obstetrics"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Takoradi Hospital", facility_type: "District Hospital", city: "Takoradi", lat: 4.8986, lng: -1.7554, specialties: '["generalSurgery","obstetrics"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Bawku Presbyterian Hospital", facility_type: "District Hospital", city: "Bawku", lat: 11.0579, lng: -0.2389, specialties: '["emergencyMedicine","obstetrics"]', equipment: '["xRay"]', capability: '[]' },
  { name: "Navrongo War Memorial Hospital", facility_type: "District Hospital", city: "Navrongo", lat: 10.8918, lng: -1.0926, specialties: '["generalSurgery","pediatrics"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Techiman Holy Family Hospital", facility_type: "District Hospital", city: "Techiman", lat: 7.5833, lng: -1.9333, specialties: '["obstetrics","pediatrics"]', equipment: '["xRay","ultrasound"]', capability: '["bloodBank"]' },
  { name: "Kintampo Municipal Hospital", facility_type: "Municipal Hospital", city: "Kintampo", lat: 8.0500, lng: -1.7333, specialties: '["generalSurgery"]', equipment: '["xRay"]', capability: '[]' },
  { name: "Yendi Municipal Hospital", facility_type: "Municipal Hospital", city: "Yendi", lat: 9.4427, lng: -0.0108, specialties: '["emergencyMedicine"]', equipment: '["xRay"]', capability: '[]' },
  { name: "Axim Government Hospital", facility_type: "District Hospital", city: "Axim", lat: 4.8700, lng: -2.2400, specialties: '["obstetrics"]', equipment: '["xRay"]', capability: '[]' },
  { name: "Nkawkaw Holy Family Hospital", facility_type: "District Hospital", city: "Nkawkaw", lat: 6.5500, lng: -0.7833, specialties: '["generalSurgery","obstetrics"]', equipment: '["xRay","ultrasound"]', capability: '[]' },
  { name: "Tarkwa Municipal Hospital", facility_type: "Municipal Hospital", city: "Tarkwa", lat: 5.3000, lng: -1.9833, specialties: '["emergencyMedicine","obstetrics"]', equipment: '["xRay"]', capability: '[]' },
];

function toGeoJSON(facilities: any[]): any {
  return {
    type: "FeatureCollection",
    features: facilities.map((f, i) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [f.lng, f.lat] },
      properties: { ...f, pk_unique_id: `mock-${i}` },
    })),
  };
}

/** Mock tool result for geo_map tool */
export function getMockToolResult(): any {
  return {
    config: {
      mapbox_token: import.meta.env.VITE_MAPBOX_TOKEN || "",
      elevenlabs_api_key: "",
    },
    mode: "search",
    query: { location: "Ghana", condition: null, radius_km: 500 },
    summary: "18 mock facilities across Ghana (dev mode)",
    total_found: MOCK_FACILITIES.length,
    center: { lat: 7.9465, lng: -1.0232 },
    highlight_region: null,
    narrative_focus: null,
    initial_zoom: 6.5,
  };
}

/** Mock geocode_facilities response */
export function getMockGeocodeFacilities(): any {
  return { geojson: toGeoJSON(MOCK_FACILITIES) };
}

/** Check if running in dev mode (Vite dev server, no MCP host) */
export function isDevMode(): boolean {
  return import.meta.env.DEV;
}
