# OASIS — "Today is gonna be the day..."

## Project Identity

**OASIS** (Orchestrated Agentic System for Intelligent healthcare Synthesis) is a hackathon project. Named after the band behind *Wonderwall*, because we're building the intelligence layer that connects healthcare workers to the communities that need them — "the one that saves you."

**Tone & Vibe:** This project should feel bold, warm, and human. We're building something that matters — connecting doctors to patients in medical deserts — and we're doing it with personality. When in doubt, remember: impressive tech + genuine heart + a touch of rockstar energy = winning demo.

**Demo Easter Eggs:**
- The project name is a Wonderwall reference — lean into it
- Demo may feature a few seconds of Wonderwall playing in the background
- Consider Oasis/Wonderwall-themed naming for features (e.g., "Wonderwall" for the medical desert map, agent responses that occasionally echo lyrics naturally)
- Creative, smile-inducing touches matter as much as technical depth — surprise the judges

## Challenge Context

**Hackathon Challenge:** "Bridging Medical Deserts" — Building Intelligent Document Parsing Agents for the Virtue Foundation. Sponsored by Databricks.

**Goal:** Build an agentic AI intelligence layer for healthcare that can reason, decide, and act to connect medical expertise with hospitals and communities that need it. Reduce time for patients to receive lifesaving treatment by 100x.

**Evaluation Criteria:**
| Criterion | Weight | Our Strategy |
|-----------|--------|-------------|
| Technical Accuracy | 35% | Reliable IDP extraction from free-form text, anomaly detection |
| IDP Innovation | 30% | Structured + unstructured synthesis via OASIS tools + RAG |
| Social Impact | 25% | Interactive medical desert map, coverage gap identification |
| User Experience | 10% | Natural language queries in Claude Desktop, OASIS App with interactive map |

**Core Features Required:**
1. Unstructured Feature Extraction — Parse free-form `procedure`, `equipment`, `capability` columns
2. Intelligent Synthesis — Combine unstructured insights with structured facility schemas
3. Planning System — Accessible system for routing patients to care, usable across experience levels

**Stretch Goals:**
1. Row-level and agentic-step-level citations (use MLflow tracing)
2. Interactive map visualization (Leaflet/Mapbox in OASIS App)
3. Real-impact features from Databricks/VF collaboration

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Claude Desktop                      │
│  ┌───────────────────────────────────────────────┐  │
│  │              OASIS MCP Server                  │  │
│  │  (VF-specific tools)                          │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │           Medical Desert Mapper App            │  │
│  │  (OASIS App — interactive map in Claude Desktop)│  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol
┌──────────────────────┴──────────────────────────────┐
│                    OASIS Core                         │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │ DuckDB   │ │ OASIS Skills │ │ OASIS Tools     │  │
│  │ (VF Data)│ │ (IDP, Anomaly│ │ (Extract, Route,│  │
│  │          │ │  Detection)  │ │  Analyze)       │  │
│  └──────────┘ └──────────────┘ └─────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ Optional
┌──────────────────────┴──────────────────────────────┐
│              Databricks (Stretch)                     │
│  Vector Search (RAG) │ MLflow (Tracing/Citations)    │
└──────────────────────────────────────────────────────┘
```

## Dataset: Virtue Foundation Ghana

**File:** `Virtue Foundation Ghana v0.3 - Sheet1.csv`
**Records:** ~1,002 healthcare facilities in Ghana
**Schema docs:** `Virtue Foundation Scheme Documentation.md`
**Pydantic models:** `prompts_and_pydantic_models/`

### Key Columns

**Structured fields:**
- `name` — Facility name
- `specialties` — JSON array of medical specialty enums (camelCase, e.g. `internalMedicine`)
- `facilityTypeId` — `hospital`, `pharmacy`, `doctor`, `clinic`, `dentist`
- `operatorTypeId` — `public`, `private`
- `affiliationTypeIds` — `faith-tradition`, `philanthropy-legacy`, `community`, `academic`, `government`
- `address_city`, `address_stateOrRegion`, `address_country` — Location
- `numberDoctors`, `capacity`, `area` — Facility metrics

**Free-form text fields (IDP target):**
- `procedure` — JSON array of clinical services (e.g., "Performs emergency cesarean sections")
- `equipment` — JSON array of medical devices (e.g., "Has Siemens CT scanner")
- `capability` — JSON array of care levels (e.g., "Level II trauma center", "24/7 emergency care")

**Metadata:**
- `source_url` — Original data source URL
- `pk_unique_id` — Primary key
- `organization_type` — Always "facility" in this dataset
- `phone_numbers`, `email`, `websites`, `officialWebsite` — Contact info

### Data Quality Notes
- Many fields are `null` or empty JSON arrays `[]`
- Free-form text fields contain the richest information but need parsing
- Some facilities appear duplicated with same `pk_unique_id` but different `content_table_id`
- Specialties are pre-extracted but may be incomplete — cross-check against free-form text
- Address data is inconsistent — some have full addresses, many have only city/country
- Equipment and procedure fields are often empty even for large hospitals — this is a gap to detect

## OASIS Integration Guide

### Custom Dataset Setup

The VF Ghana dataset should be registered as a custom OASIS dataset:

```json
{
  "name": "vf-ghana",
  "description": "Virtue Foundation Ghana Healthcare Facilities",
  "primary_verification_table": "vf.facilities",
  "modalities": ["TABULAR"],
  "schema_mapping": {"": "vf"}
}
```

**Init:** `oasis init vf-ghana --src <path-to-csv>`

### New Tools to Build

Following OASIS's tool protocol pattern (`src/oasis/core/tools/base.py`):

1. **`analyze_facility`** — Deep analysis of a single facility, combining structured + free-form data
2. **`find_medical_deserts`** — Identify geographic areas lacking specific specialties or capabilities
3. **`detect_anomalies`** — Flag suspicious or inconsistent facility claims (e.g., claims trauma capability but no CT scanner)
4. **`route_patient`** — Given a medical need and location, find the nearest capable facility (the "planning system")
5. **`extract_capabilities`** — IDP tool that re-parses free-form text with enhanced extraction

### New OASIS App to Build

**Medical Desert Mapper** — Interactive map app (first OASIS App in this project):
- Leaflet.js or Mapbox GL JS map of Ghana
- Facilities as markers, color-coded by type/specialty
- Heatmap overlay showing coverage density
- Filter controls: specialty, facility type, capability
- Click facility for detail popup
- Highlight "deserts" — regions with no coverage for a given specialty
- The app should be visually stunning — this is the centerpiece of the demo

### New Skills to Build

Following OASIS's skill pattern (`src/oasis/skills/`):

1. **`vf-schema`** — Teaches the agent about VF Ghana data structure, column semantics, and query patterns
2. **`idp-extraction`** — Patterns for parsing free-form medical text into structured facts
3. **`medical-desert-analysis`** — How to identify and characterize healthcare coverage gaps

## Development Conventions

### Code Style
- Python 3.10+, type hints everywhere
- Ruff for linting (line length 88)
- Follow existing OASIS patterns — protocol-based tools, modality filtering, native return types
- Tests in `tests/` with pytest

### OASIS Patterns to Follow
- **Tools return native Python types** (DataFrame, dict, list) — MCP layer in `mcp_server.py` serializes via `serialize_for_mcp()`
- **Proactive compatibility checking** before tool invocation (ToolSelector)
- **Canonical schema names** — `schema.table` format (e.g., `vf.facilities`)
- **Modality-based filtering** — tools declare `required_modalities: frozenset[Modality]`
- **DuckDB only** — no BigQuery, no cloud backends
- **Graceful degradation** — apps return text in non-supporting hosts
- **Skills are markdown** — YAML frontmatter + content in `src/oasis/skills/clinical/<name>/SKILL.md`

### File Organization (what we're adding)
```
src/oasis/
├── core/tools/
│   └── vf_ghana.py          # New VF-specific tools
├── apps/
│   └── desert_mapper/        # New OASIS App (first app — no reference impl exists)
│       ├── __init__.py
│       ├── tool.py           # Tool classes (registered in apps/__init__.py)
│       ├── query_builder.py  # SQL generation for map queries
│       └── ui/               # Vite + Leaflet.js UI bundle
│           ├── src/
│           ├── package.json
│           └── vite.config.ts
└── skills/
    └── clinical/
        ├── vf-schema/SKILL.md
        ├── idp-extraction/SKILL.md
        └── medical-desert-analysis/SKILL.md
```

Note: The cohort_builder reference app was removed. For building the Desert Mapper app,
reference `docs/OASIS_APPS.md` for the protocol and `src/oasis/apps/__init__.py` for registration.
The app tool needs to declare `_meta.ui.resourceUri` pointing to a bundled HTML resource.

### Git Workflow
- Branch: `main` (hackathon, move fast)
- Commit messages: concise, imperative, no fluff
- Don't commit secrets, large data files, or node_modules

## Demo Script (60-90 seconds)

### Act 1: "I said maybe..." (0-20s)
Open Claude Desktop. Natural language query:
> "Where are the surgical deserts in Northern Ghana? Show me on a map."

Agent reasons over VF data, launches the Medical Desert Mapper app. Map zooms to Northern Ghana, red zones pulse where no surgical capability exists.

### Act 2: "You're gonna be the one that saves me" (20-50s)
> "This facility in Tamale claims emergency surgery capability. Does the data support that?"

Agent runs anomaly detection — cross-references equipment, procedures, and capabilities. Flags: "Claims emergency surgery but has no listed surgical equipment or operating theater. Confidence: Low. Recommend verification."

Citations show exactly which data fields were checked.

### Act 3: "After all, you're my wonderwall" (50-75s)
> "A patient in Bolgatanga needs an emergency appendectomy. Route them to care."

Agent runs the planning system — finds nearest facility with surgical capability, estimates travel, suggests alternatives. Shows route on the map.

### Closing (75-90s)
Pull back to show the full map of Ghana with coverage overlay. Text on screen: every dot is a facility, every gap is a patient waiting. OASIS connects them.

## Codebase State (Post-Cleanup)

What remains:

**Core (kept):**
- `src/oasis/mcp_server.py` — MCP server (FastMCP), stripped of cohort builder + OAuth2
- `src/oasis/api.py` — Python API (set_dataset, execute_query, get_schema, etc.)
- `src/oasis/cli.py` — CLI (oasis init, oasis use, oasis status, oasis config, oasis skills)
- `src/oasis/config.py` — Config management (oasis_data/config.json)
- `src/oasis/data_io.py` — CSV-to-Parquet conversion, dataset initialization
- `src/oasis/core/tools/` — Tool protocol, registry, tabular tools, notes tools, management
- `src/oasis/core/backends/duckdb.py` — DuckDB backend (only backend now)
- `src/oasis/core/datasets.py` — DatasetRegistry, DatasetDefinition, Modality enum
- `src/oasis/core/validation.py` — SQL security validation
- `src/oasis/core/serialization.py` — MCP result serialization

**Infrastructure shells (kept, empty — we fill these):**
- `src/oasis/apps/__init__.py` — App registration (init_apps with empty body, ready for our apps)
- `src/oasis/skills/installer.py` — Skill installation system (no skills content, ready for ours)
- `src/oasis/skills/SKILL_FORMAT.md` — How to write skills (reference doc)
- `src/oasis/skills/SKILLS_INDEX.md` — Skill catalog format

**Removed (not needed for OASIS):**
- BigQuery backend, OAuth2 auth, derived tables (MIMIC-IV SQL)
- All clinical skills (SOFA, sepsis, KDIGO, etc.)
- All system skills (oasis-api, oasis-research, MIMIC mappings)
- Cohort Builder app (reference app — gone, we build our own from scratch)
- Webapp (marketing site), benchmarks

## Quick Reference

| What | Where |
|------|-------|
| Challenge description | `CHALLENGE.md` |
| VF Ghana data | `Virtue Foundation Ghana v0.3 - Sheet1.csv` |
| Schema docs | `Virtue Foundation Scheme Documentation.md` |
| Pydantic models | `prompts_and_pydantic_models/` |
| MCP server | `src/oasis/mcp_server.py` |
| Python API | `src/oasis/api.py` |
| Tool protocol + registry | `src/oasis/core/tools/base.py`, `registry.py` |
| Tabular tools (execute_query etc.) | `src/oasis/core/tools/tabular.py` |
| DuckDB backend | `src/oasis/core/backends/duckdb.py` |
| Apps infrastructure | `src/oasis/apps/__init__.py` (empty, add ours here) |
| Skills infrastructure | `src/oasis/skills/installer.py`, `SKILL_FORMAT.md` |
| Custom dataset guide | `docs/CUSTOM_DATASETS.md` |
| OASIS Apps guide | `docs/OASIS_APPS.md` |
| Tool reference | `docs/TOOLS.md` |
| Dev guide (adding tools) | `docs/DEVELOPMENT.md` |
| Skills guide | `docs/SKILLS.md` |
