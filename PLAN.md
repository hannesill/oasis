# OASIS — Execution Plan

## Current State

M4 infrastructure is solid: DuckDB backend, tool registry, MCP server, serialization — all functional.
Pydantic extraction models and schema docs are ready in `prompts_and_pydantic_models/`.

**Everything OASIS-specific is unbuilt:**
- No VF tools (`vf_ghana.py` does not exist)
- No map app (`desert_mapper/` does not exist)
- No skills (all old clinical skills removed, no VF skills written)
- Dataset not loaded into DuckDB yet

---

## Team Assignments (4 People)

### Person 1: Data + Backend Tools

The foundation everything else depends on.

**Tasks:**
1. Initialize the VF Ghana dataset into DuckDB
   - `m4 init vf-ghana --src "Virtue Foundation Ghana v0.3 - Sheet1.csv"`
   - Verify table is queryable: `SELECT * FROM vf.facilities LIMIT 5`
2. Build `src/m4/core/tools/vf_ghana.py` — 5 core tools:
   - **`analyze_facility`** — Deep analysis of a single facility, combining structured + free-form data
   - **`find_medical_deserts`** — Identify geographic areas lacking specific specialties or capabilities
   - **`detect_anomalies`** — Flag suspicious/inconsistent facility claims (e.g., claims trauma but no CT scanner)
   - **`route_patient`** — Given medical need + location, find nearest capable facility
   - **`extract_capabilities`** — IDP tool that re-parses free-form text with enhanced extraction
3. Register all tools in `src/m4/mcp_server.py`
4. Write basic tests in `tests/` to verify tools return correct results

**Key references:**
- Tool protocol: `src/m4/core/tools/base.py`
- Existing tools for pattern reference: `src/m4/core/tools/tabular.py`
- Tool registration: `src/m4/core/tools/__init__.py`
- MCP registration: `src/m4/mcp_server.py`
- Schema docs: `Virtue Foundation Scheme Documentation.md`
- Pydantic models: `prompts_and_pydantic_models/`

**Why first:** Every other workstream calls these tools. Unblocks Persons 2, 3, and 4.

---

### Person 2: Medical Desert Mapper App (Frontend)

The visual centerpiece of the demo. This is what the judges remember.

**Tasks:**
1. Scaffold `src/m4/apps/desert_mapper/` following M4 app protocol:
   - `__init__.py`
   - `tool.py` — Tool classes (registered in `apps/__init__.py`)
   - `query_builder.py` — SQL generation for map queries
   - `ui/` — Vite + Leaflet.js UI bundle
2. Build the interactive map:
   - Ghana base map with Leaflet.js or Mapbox GL JS
   - Facility markers color-coded by type (hospital=blue, clinic=green, pharmacy=orange, etc.)
   - Coverage heatmap overlay — pulse red for desert zones
   - Filter controls: specialty, facility type, capability level
   - Click-to-inspect: facility detail popup with key stats
   - Patient routing visualization: line/path between patient location and recommended facility
3. Wire the MCP App protocol:
   - `_meta.ui.resourceUri` pointing to bundled HTML resource
   - Graceful degradation for non-supporting hosts
4. Visual polish: animations, transitions, professional color palette — make it stunning

**Key references:**
- M4 Apps guide: `docs/M4_APPS.md`
- App registration: `src/m4/apps/__init__.py`

**Can start immediately** on the UI shell (map, dummy data markers) while waiting for Person 1's tools.

---

### Person 3: Skills + IDP + Anomaly Intelligence

The intelligence layer that makes agent responses smart and domain-aware.

**Tasks:**
1. Write 3 skills in `src/m4/skills/clinical/`:
   - **`vf-schema/SKILL.md`** — Teaches the agent about VF Ghana columns, data types, query patterns, known data quirks (nulls, duplicates, JSON arrays)
   - **`idp-extraction/SKILL.md`** — Patterns for parsing free-form medical text into structured facts; reference the Pydantic models in `prompts_and_pydantic_models/`
   - **`medical-desert-analysis/SKILL.md`** — How to identify and characterize healthcare coverage gaps, what constitutes a "desert," severity scoring
2. Build anomaly detection rules:
   - Claims surgical capability but no surgical equipment listed
   - Claims 24/7 emergency but listed as pharmacy or dentist
   - Large claimed capacity but no doctors listed
   - Specialty claims not supported by procedures/equipment
3. Add citation support — ensure tool responses reference specific data fields so the agent can cite which columns/rows informed its conclusions
4. Test with real natural language queries, tune skill quality

**Key references:**
- Skill format: `src/m4/skills/SKILL_FORMAT.md`
- Skills index: `src/m4/skills/SKILLS_INDEX.md`
- Pydantic models: `prompts_and_pydantic_models/`
- VF schema: `Virtue Foundation Scheme Documentation.md`

**Can start immediately** on skills (they're markdown). Anomaly rules depend on Person 1's data access.

---

### Person 4: Demo Integration + Polish + Stretch Goals

The glue person who makes it all feel like magic on stage.

**Tasks:**
1. End-to-end testing: run the full 3-act demo script in Claude Desktop (see Demo Flow below)
2. Fix integration issues between tools, app, and agent behavior
3. Add demo Easter eggs:
   - Wonderwall-themed touches (project name references, subtle lyric nods)
   - Creative UI elements that make judges smile
4. Stretch goals if time allows:
   - MLflow tracing for row-level citations
   - Databricks vector search for RAG over facility descriptions
5. Prepare the actual demo presentation / recording
6. Write a compelling README or one-pager for judges

**Starts after** Persons 1-3 have initial working versions (~halfway through), then becomes the most critical role. Until then, help Person 1 with dataset setup or Person 3 with skills.

---

## Execution Timeline

```
Phase 1 — Foundation (Parallel start)
├── P1: Dataset init → first 2 tools (analyze_facility, find_medical_deserts)
├── P2: Map UI shell with Ghana basemap + dummy facility markers
├── P3: All 3 skills drafted + anomaly rule spec
└── P4: Help P1/P3, set up Claude Desktop demo environment

Phase 2 — Integration
├── P1: Remaining 3 tools + MCP registration + tests
├── P2: Wire map to real tool query results
├── P3: Tune skills against real queries, refine anomaly logic
└── P4: Start end-to-end demo testing, file integration bugs

Phase 3 — Polish
├── P1: Bug fixes, edge case handling
├── P2: Visual polish, animations, responsive design
├── P3: Citation quality, anomaly tuning, skill refinement
└── P4: Full demo rehearsals, Easter eggs, recording, presentation prep
```

---

## Demo Flow (60-90 seconds)

### Act 1: "I said maybe..." (0-20s)
**The Hook — Show the problem visually.**

Open Claude Desktop. Type naturally:

> "Where are the surgical deserts in Northern Ghana? Show me on a map."

**What happens:**
- Agent reasons over VF Ghana data via `find_medical_deserts` tool
- Launches the Medical Desert Mapper app
- Map zooms to Northern Ghana
- Facilities appear as color-coded markers
- Red zones pulse where no surgical capability exists within a reasonable radius
- Agent narrates: identifies the Upper East, Upper West, and Northern regions as critically underserved for surgical care

**What the judges see:** A beautiful, interactive map that instantly communicates the problem. No slides, no charts — the data speaks through geography.

---

### Act 2: "You're gonna be the one that saves me" (20-50s)
**The Intelligence — Show the agent can think critically.**

Type:

> "This facility in Tamale claims emergency surgery capability. Does the data support that?"

**What happens:**
- Agent runs `detect_anomalies` on the Tamale facility
- Cross-references structured fields (equipment, specialties, capacity, doctors) against free-form claims (procedure, capability text)
- Returns a verdict with citations:
  - "Claims emergency surgery capability in the `capability` field"
  - "However: no surgical equipment listed in `equipment`, no surgical specialties in `specialties`, only 2 doctors listed"
  - "**Confidence: Low.** Recommend on-site verification."
- Each claim links back to the specific data field it came from (row-level citations)

**What the judges see:** The agent doesn't just parrot data — it synthesizes, cross-references, and flags inconsistencies. This is IDP with critical thinking.

---

### Act 3: "After all, you're my wonderwall" (50-75s)
**The Impact — Show the planning system saving a life.**

Type:

> "A patient in Bolgatanga needs an emergency appendectomy. Route them to the nearest capable facility."

**What happens:**
- Agent runs `route_patient` with need=appendectomy, location=Bolgatanga
- Searches facilities with verified surgical capability (filtering out low-confidence claims from Act 2)
- Returns a plan:
  - **Primary:** Tamale Teaching Hospital (150km, ~2.5hr drive) — confirmed surgical capability, 8 surgeons, operating theater listed
  - **Alternative:** Wa Regional Hospital (280km, ~4hr) — backup option
  - **Warning:** No surgical facility within 100km of Bolgatanga — this is a critical gap
- Map updates to show the route, distance, and estimated travel time
- Desert zone around Bolgatanga highlighted in red

**What the judges see:** A real planning system that a healthcare worker with no technical background could use. Type a question, get a life-saving answer.

---

### Closing (75-90s)
**The Emotion — Zoom out to the big picture.**

Pull the map back to show all of Ghana. Coverage overlay visible — green where facilities cluster, red where deserts stretch.

> "Every dot is a facility. Every gap is a patient waiting. OASIS connects them."

Pause. Let it land.

Optional: Wonderwall plays softly for 3 seconds. Smile. Done.

---

## Priority Stack (if short on time)

Cut from bottom up — last item = cut first:

1. **Must have:** Map + `find_medical_deserts` + `route_patient` (the wow factor)
2. **Must have:** `detect_anomalies` + citation support (shows intelligence, hits IDP criteria)
3. **Should have:** `analyze_facility` + `extract_capabilities` (depth tools)
4. **Nice to have:** Skills (they improve agent quality but demo works without them)
5. **Stretch:** Databricks integration, MLflow tracing, vector search RAG
