# OASIS Architecture — 1-Minute Video Script
## Following the Logical Flow of the Architecture Diagram

---

## [0:00-0:10] **USER LAYER — The Entry Point**
**Visual:** Highlight USER box → arrow → MCP Client box → 3D map preview appears

**Narration:**
> "It starts with a user asking a question in natural language: 'Where are the surgical deserts in Northern Ghana?' The question flows to Claude Desktop's MCP Client, where Anthropic Claude performs agent reasoning. The result? An interactive 3D map visualization appears right here in Claude Desktop."

**On-screen:**
- USER box highlights
- "Natural Language" arrow animates
- MCP Client box highlights with "Anthropic Claude Agent Reasoning"
- 3D map preview fades in on the right

**Key point:** Natural language → Claude reasoning → Visual output

---

## [0:10-0:22] **ORCHESTRATION LAYER — The Brain**
**Visual:** MCP Protocol arrow animates down → oasis box expands → three registries appear

**Narration:**
> "Behind the scenes, the MCP Protocol connects Claude to our OASIS orchestration server. OASIS is the brain — it manages three critical registries: the Tool Registry routes to our geospatial and data tools, the Dataset Registry handles our 1,002 Ghana healthcare facilities, and the MCP Apps Protocol launches interactive visualizations like our map."

**On-screen:**
- MCP Protocol arrow pulses downward
- oasis box (purple) expands and highlights
- Three registry boxes appear below: Tool Registry, Dataset Registry, MCP Apps Protocol
- Arrows connect oasis to each registry

**Key point:** MCP Protocol → OASIS orchestration → Three registries coordinate everything

---

## [0:22-0:40] **SERVICES LAYER — The Power**
**Visual:** Three service boxes appear left to right, each with their components highlighted

**Narration:**
> "OASIS orchestrates three service layers. First, Geospatial Tools — five functions that find facilities in radius, detect coverage gaps, calculate distances, geocode locations to latitude and longitude, and count facilities. Second, our Geomap Application — powered by Mapbox GL JS for real-time rendering, Three.js for 3D models, creating medical desert heatmaps that visualize gaps in real-time. Third, Databricks Integration — Genie converts natural language to SQL queries, MLflow traces every tool call for citation transparency, and RAG semantic search finds facilities by meaning, not keywords."

**On-screen:**
- Geospatial Tools box (green) highlights → 5 functions list appears
- Geomap Application box (blue) highlights → Mapbox GL JS, Three.js, Real-time rendering, Medical Desert Heatmaps
- Databricks Integration box (orange) highlights → Genie Text-to-SQL, MLFlow Tracing, RAG Semantic Search
- Arrows show data flowing from oasis to each service

**Key point:** Three specialized services — Geospatial, Geomap, Databricks — each with specific capabilities

---

## [0:40-0:55] **DATA LAYER — The Foundation**
**Visual:** Three data boxes appear, showing connections from services above

**Narration:**
> "All services connect to our data foundation. DuckDB Local Analytics stores our VF Ghana Parquet dataset — 1,002 healthcare facilities ready for fast SQL queries. Data Sanity & Anomalies uses Google Geocoding API for precise coordinates, performs column harmonization, and generates anomaly risk summaries to flag data inconsistencies. And our Embeddings Cache stores semantic vectors using both databricks-bge-large-en and all-MiniLM-L6-v2 models, enabling RAG search that understands meaning, not just keywords."

**On-screen:**
- DuckDB box (brown) highlights → "VF Ghana Parquet, 1,002 facilities"
- Data Sanity & Anomalies box (pink) highlights → Google Geocoding API, Column Harmonization, Anomaly Risk Summary
- Embeddings Cache box (grey) highlights → databricks-bge-large-en, all-MiniLM-L6-v2, Hugging Face logo
- Arrows show connections: Geospatial Tools → DuckDB, Geomap → Data Sanity, Databricks → Embeddings Cache

**Key point:** Three data sources — structured analytics, geocoding/anomalies, semantic embeddings

---

## [0:55-1:00] **FULL FLOW — The Complete Picture**
**Visual:** Entire diagram animates, showing complete data flow from USER to DATA and back

**Narration:**
> "One question flows through all four layers — from natural language to orchestration, through specialized services, powered by rich data. That's OASIS: Orchestrated Agentic System for Intelligent Healthcare Synthesis. Bridging medical deserts, one conversation at a time."

**On-screen:**
- Full diagram visible
- Data flow animates: USER → ORCHESTRATION → SERVICES → DATA
- Then reverse: DATA → SERVICES → ORCHESTRATION → USER (map visualization)
- OASIS logo appears
- "Virtue Foundation Hackathon 2026 · Sponsored by Databricks"

**Key point:** Complete end-to-end flow — question in, insights out

---

## Visual Flow Sequence (Match Diagram Exactly)

### Scene 1: USER Layer (0:00-0:10)
1. USER box appears (light grey, person icon)
2. "Natural Language" arrow animates right
3. MCP Client box appears (light grey, "Anthropic Claude Agent Reasoning")
4. 3D map preview fades in on right side

### Scene 2: ORCHESTRATION Layer (0:10-0:22)
1. MCP Protocol arrow animates down (with "M" icon)
2. oasis box expands (light purple, palm tree icon)
3. Three registry boxes appear below:
   - Tool Registry
   - Dataset Registry
   - MCP Apps Protocol

### Scene 3: SERVICES Layer (0:22-0:40)
1. Geospatial Tools box (green) appears with globe icon
   - List of 5 functions appears
2. Geomap Application box (blue) appears
   - Mapbox GL JS, Three.js, Real-time rendering, Medical Desert Heatmaps
   - Mapbox logo at bottom
3. Databricks Integration box (orange) appears
   - Genie Text-to-SQL, MLFlow Tracing, RAG Semantic Search
   - Databricks logo at bottom

### Scene 4: DATA Layer (0:40-0:55)
1. DuckDB Local Analytics box (brown) appears
   - "VF Ghana Parquet, 1,002 facilities"
   - DuckDB logo
2. Data Sanity & Anomalies box (pink) appears
   - Google Geocoding API, Column Harmonization, Anomaly Risk Summary
   - Google Cloud logo
3. Embeddings Cache box (grey) appears
   - databricks-bge-large-en, all-MiniLM-L6-v2
   - Hugging Face logo

### Scene 5: Full Flow (0:55-1:00)
1. All layers visible simultaneously
2. Data flow animates top to bottom (USER → DATA)
3. Reverse flow animates (DATA → USER, showing map result)
4. OASIS logo + credits

---

## Key Technical Points Per Layer

### USER Layer:
- Natural language input
- Claude Desktop MCP Client
- Agent reasoning
- 3D map visualization output

### ORCHESTRATION Layer:
- MCP Protocol communication
- OASIS server (FastMCP)
- Tool Registry (routes to services)
- Dataset Registry (manages 1,002 facilities)
- MCP Apps Protocol (launches visualizations)

### SERVICES Layer:
- **Geospatial Tools:** 5 functions (find_facilities_in_radius, find_coverage_gaps, calculate_distance, geocode_facilities, count_facilities)
- **Geomap Application:** Mapbox GL JS, Three.js 3D models, real-time rendering, medical desert heatmaps
- **Databricks Integration:** Genie Text-to-SQL, MLFlow Tracing, RAG Semantic Search

### DATA Layer:
- **DuckDB:** VF Ghana Parquet, 1,002 facilities, fast SQL queries
- **Data Sanity & Anomalies:** Google Geocoding API, column harmonization, anomaly risk summary
- **Embeddings Cache:** databricks-bge-large-en, all-MiniLM-L6-v2, Hugging Face models

---

## Connection Arrows to Highlight

1. **USER → MCP Client:** "Natural Language" (horizontal arrow)
2. **MCP Client → oasis:** "MCP Protocol" (downward arrow)
3. **oasis → Services:** Multiple arrows to Geospatial, Geomap, Databricks
4. **Services → Data:** 
   - Geospatial Tools → DuckDB
   - Geomap Application → Data Sanity & Anomalies
   - Databricks Integration → Embeddings Cache

---

## Voiceover Timing Tips

- **Pace:** ~150 words per minute (matches 60-second script)
- **Pauses:** Brief pause after each layer introduction
- **Emphasis:**
  - "OASIS is the brain" (orchestration importance)
  - "Three service layers" (services structure)
  - "Three data sources" (data foundation)
  - "One question flows through all four layers" (complete flow)
- **Tone:** Technical but accessible, confident, clear

---

## Alternative: Faster 45-Second Version

**[0:00-0:08]** USER + ORCHESTRATION (combined)
**[0:08-0:25]** SERVICES (all three together, faster)
**[0:25-0:38]** DATA (all three together, faster)
**[0:38-0:45]** Full flow + closing
