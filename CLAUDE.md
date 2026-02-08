# OASIS — "Today is gonna be the day..."

## Project Identity

**OASIS** (Orchestrated Agentic System for Intelligent healthcare Synthesis) is a hackathon project. Named after the band behind *Wonderwall*, because we're building the intelligence layer that connects healthcare resources to the communities that need them — "the one that saves you."

**Tone & Vibe:** Bold, warm, human. Impressive tech + genuine heart + a touch of rockstar energy = winning demo. Lean into the Wonderwall reference — surprise the judges with creative touches.

## Challenge Context

**Hackathon Challenge:** "Bridging Medical Deserts" — Building Intelligent Document Parsing Agents for the Virtue Foundation. Sponsored by Databricks.

**Goal:** Build an IDP agent that extracts and verifies medical facility capabilities from messy, unstructured data — and reasons over it to understand where care truly exists and where it is missing. Reduce time for patients to receive lifesaving treatment by 100x.

**Evaluation Criteria:**
| Criterion | Weight | What Judges Look For | Our Strategy |
|-----------|--------|---------------------|-------------|
| Technical Accuracy | 35% | Reliably handle "Must Have" queries from VF Agent Questions; detect anomalies | OASIS tools for the Must Have query categories |
| IDP Innovation | 30% | Extract + synthesize from unstructured free-form text | Smart tools that parse `procedure`/`equipment`/`capability` and cross-reference with structured data |
| Social Impact | 25% | Identify medical deserts, aid resource allocation | Interactive Mapbox GL JS desert mapper |
| User Experience | 10% | Intuitive for non-technical NGO planners, natural language | Claude Desktop natural language interface |

**Core Features (MVP):**
1. **Unstructured Feature Extraction** — Parse free-form `procedure`, `equipment`, `capability` columns
2. **Intelligent Synthesis** — Combine unstructured insights with structured facility schemas
3. **Planning System** — Accessible system for routing patients to care, adoptable across experience levels and age groups

**Stretch Goals (from challenge):**
1. **Citations** — Row-level citations showing what data supports each claim. Bonus: agentic-step-level citations (which data was used at each reasoning step). *Hint from organizers: use experiment tracking tools like MLflow to trace agent loops.*
2. **Map Visualization** — Interactive map demonstrating conclusions visually
3. **Real-impact Bonus** — Tackle questions from the VF Agent Questions doc (see below). The Databricks team is collaborating with VF to ship an agent by June 7th — our work could feed into that.

**Suggested Tech Stack (from organizers):** RAG + Agentic workflows. They suggest langgraph/crewAI, MLflow, Databricks/FAISS for RAG, Genie for Text2SQL. We deviate intentionally: OASIS/MCP with Claude Desktop instead, DuckDB locally. But we should use Databricks (Vector Search or MLflow) to show we engaged with the sponsor's stack.

**Out of Scope:** BigQuery, OAuth2, any cloud backends beyond Databricks

## VF Agent Questions — The Actual Acceptance Criteria

The VF Agent Questions doc (`Virtue Foundation Agent Questions - Hack Nation.md`) defines **59 questions across 11 categories** with MoSCoW priorities. The **"Must Have" questions are what judges will test for the 35% Technical Accuracy score.** Tackling "Should Have" and beyond earns the real-impact bonus.

**Must Have queries we need to nail:**
- **Basic lookups:** "How many hospitals have cardiology?", "Which region has the most [type] hospitals?" → Genie/Text2SQL equivalent
- **Geospatial:** "How many hospitals treating [condition] within [X] km of [location]?", "Where are the largest cold spots for [procedure]?" → requires geospatial calculation
- **Anomaly detection:** "Which facilities claim unrealistic number of procedures relative to size?", "Where do things that shouldn't move together appear?" (e.g., huge bed count + minimal surgical equipment) → our anomaly tools
- **Resource gaps:** "Which procedures depend on very few facilities?", "Where is oversupply vs scarcity of high-complexity procedures?" → medical desert analysis
- **Workforce:** "Where is the workforce for [subspecialty] actually practicing?" → structured data queries
- **NGO gaps:** "Where are gaps where no organizations work despite evident need?" → desert mapping

**How our tools map to VF's architecture:**
| VF Concept | Our Implementation |
|------------|-------------------|
| Genie Chat (Text2SQL) | `execute_query` tool (DuckDB) |
| Vector Search with Filtering | `extract_capabilities` tool + DuckDB full-text search (stretch: Databricks VS) |
| Medical Reasoning Agent | Claude's native reasoning over tool results |
| Geospatial Calculation | `find_medical_deserts` + `route_patient` tools |
| External Data | Out of scope for hackathon |

## Team & Workload

| Owner | Track | Focus |
|-------|-------|-------|
| Rafi | RAG & Databricks | Databricks Vector Search integration, RAG pipeline |
| Hannes | Orchestration | MCP code execution, multi-step reasoning, integration |
| Jakob | Anomaly Detection | Anomaly detection tools for the Ghana dataset |
| Fourth Member | Map Visualization | Mapbox GL JS interactive map (Medical Desert Mapper app) |

**Integration contract:** Agree early on JSON shapes that tools return and the map consumes.

## Key Technical Challenges

**Multi-step dataframe reasoning in MCP:** Current MCP tools are text-in/text-out, insufficient for complex analysis. **Approach:** Design "smart tools" that run full pipelines internally (SQL → parse → cross-reference → structured result) rather than requiring model-orchestrated dataframe passes. Investigate MCP code execution as a complementary option.

**Databricks integration:** Vector Search for RAG primarily satisfies eval criteria — 987 rows don't need it. If time is tight, prioritize **MLflow tracing for citations** (directly maps to stretch goal #1 and supports the 35% Technical Accuracy criterion) over RAG.

## Architecture

Claude Desktop → OASIS MCP Server (VF tools) + Medical Desert Mapper App (interactive map)
→ OASIS Core: DuckDB (VF data) + Skills (IDP, Anomaly) + Tools (Extract, Route, Analyze)
→ Optional: Databricks Vector Search (RAG) + MLflow (Tracing/Citations)

## Dataset: Virtue Foundation Ghana

~1,002 healthcare facilities in Ghana. Schema docs: `Virtue Foundation Scheme Documentation.md`. Pydantic models: `prompts_and_pydantic_models/`.

**Key insight:** Free-form fields (`procedure`, `equipment`, `capability`) are JSON arrays of strings — richest data. Many fields are null/empty — detecting these gaps IS the feature. Specialties may be incomplete vs free-form text. Some facilities duplicated (same `pk_unique_id`, different `content_table_id`).

## What to Build

### Tools (following protocol in `src/oasis/core/tools/base.py`)
1. **`analyze_facility`** — Deep analysis combining structured + free-form data
2. **`find_medical_deserts`** — Geographic areas lacking specific specialties/capabilities (covers VF geospatial + resource gap queries)
3. **`detect_anomalies`** — Flag inconsistent facility claims (covers VF anomaly detection Must Haves: unrealistic procedure counts, mismatched infrastructure signals)
4. **`route_patient`** — Nearest capable facility for a medical need + location (the "planning system")
5. **`extract_capabilities`** — IDP re-parsing of free-form text with enhanced extraction (covers VF validation queries)

### Medical Desert Mapper App
Mapbox GL JS map (chosen for 3D), facilities as colored markers, heatmap overlay, filter controls, facility detail sidebar, desert highlighting. Centerpiece of the demo. See `docs/OASIS_APPS.md` for protocol, `src/oasis/apps/__init__.py` for registration.

### Skills (in `src/oasis/skills/`)
Skills are markdown files with YAML frontmatter. The framework supports `clinical` and `system` categories. See `src/oasis/skills/SKILL_FORMAT.md` for the spec and `SKILLS_INDEX.md` for the index.

## Development Conventions

- Python 3.10+, type hints, Ruff (line length 88), pytest
- **Tools return native Python types** — MCP layer serializes via `serialize_for_mcp()`
- **Canonical schema names** — `schema.table` format (e.g., `vf.facilities`)
- **Modality-based filtering** — tools declare `required_modalities: frozenset[Modality]`
- **DuckDB only** — no cloud backends (except optional Databricks for RAG/tracing)
- **Skills are markdown** — YAML frontmatter in `src/oasis/skills/<category>/<name>/SKILL.md`
- Branch: `main` (hackathon, move fast). Don't commit secrets or node_modules.

## Demo Script (under 2 minutes — bonus for conciseness)

1. **"I said maybe..."** — "Where are the surgical deserts in Northern Ghana?" → Map launches, red zones pulse
2. **"You're gonna be the one that saves me"** — "Does this Tamale facility really do emergency surgery?" → Anomaly detection with citations
3. **"After all, you're my wonderwall"** — "Route a patient in Bolgatanga to emergency appendectomy" → Planning system with route on map
4. **Strategic recommendation** — "Where should we place one new surgeon to close the biggest gap?" → ROI-based resource allocation on map
5. **Closing** — Full Ghana coverage overlay. Every dot a facility, every gap a patient waiting.

## Quick Reference

| What | Where |
|------|-------|
| Challenge description | `docs/challenge/CHALLENGE.md` |
| VF Agent Questions (acceptance criteria) | `docs/challenge/Virtue Foundation Agent Questions - Hack Nation.md` |
| VF Ghana data | `vf-ghana.csv` |
| Schema docs | `docs/challenge/Virtue Foundation Scheme Documentation.md` |
| Tool protocol | `src/oasis/core/tools/base.py` |
| MCP server | `src/oasis/mcp_server.py` |
| Apps guide | `docs/OASIS_APPS.md` |
| Dev guide | `docs/DEVELOPMENT.md` |
| Custom datasets | `docs/CUSTOM_DATASETS.md` |
