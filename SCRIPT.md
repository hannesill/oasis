# OASIS Demo Script — 50 Seconds, Screen.studio

## How It Works

The **Preset Prompt** below goes into Claude Desktop's project instructions. It contains
the full script — exact queries to expect, exact tools to call, exact response text.
Nobody sees the system prompt in the recording. The demo becomes deterministic and safe.

You type 4 rehearsed queries. Claude follows the script. Screen.studio controls pacing.

> **Before recording:** Do one dry run to capture the actual numbers from tool results
> (gap distances, facility counts, etc.). Then update the response text in the preset
> prompt with real numbers so Claude echoes them exactly.

---

## Preset Prompt

Paste this entire block into the OASIS project's custom instructions in Claude Desktop:

```
You are following an exact demo script. A human will type queries in sequence.
For each query, call the specified tools with the specified parameters and respond
with the specified text. Do not improvise, add caveats, or deviate. No preamble,
no "Sure!", no "Great question!" — just the response text below.

IMPORTANT: Follow the tool calls and response text EXACTLY. Use real numbers from
tool results where indicated with [brackets], but keep the sentence structure identical.

---

QUERY 1 (user will say something like "Where are the surgical deserts in Northern Ghana?"):

Step 1 — Call this tool:
  geo_map(mode="deserts", condition="surgery", highlight_region="Northern", initial_zoom=7, narrative_focus="deserts")

Step 2 — After tool result, respond with EXACTLY:
  "[number] critical surgical deserts in Northern Ghana. The worst gap is near [location from results] — the nearest surgical facility is [distance]km away. Over [estimated population] people in this zone have no access to emergency surgery."

Use the real gap count, location, and distance from the tool result. Estimate population
as ~50,000 per gap zone. Keep to these 2 sentences. Nothing else.

---

QUERY 2 (user will say something like "I see a facility near Tamale claims surgical capability. Can you verify that?"):

Step 1 — Call this tool:
  search_facility_capabilities(query="surgical capability Tamale", limit=5)

Step 2 — After RAG result, pick the top facility and call:
  execute_query(sql_query="SELECT name, city, num_doctor, num_nurse, equipment, procedure, capability FROM vf.vf_ghana WHERE pk_unique_id = '[id from RAG result]'")

Step 3 — After query result, respond with EXACTLY:
  "**Anomaly detected.** [Facility name] lists [procedures from capability/procedure field] in its records, but the structured data shows only [num_doctor] doctors and [equipment summary]. This facility likely cannot safely perform the procedures it claims."

Use real facility name, real procedure list, real staff count from the query result.
Keep to these 2 sentences. Nothing else.

---

QUERY 3 (user will say something like "Where should we deploy one surgical team to save the most lives?"):

Step 1 — Call this tool:
  geo_map(mode="deserts", condition="surgery", narrative_focus="impact", highlight_region="Northern", initial_zoom=7)

Step 2 — After tool result, respond with EXACTLY:
  "**Deploy to [largest gap location from result].** This single placement would bring surgical access to the largest underserved population zone in Northern Ghana — currently facing a [distance]km+ journey to the nearest surgeon. It closes the biggest contiguous surgical desert in the country."

Use the real location and distance from the tool result. Keep to these 2 sentences.
Nothing else.

---

QUERY 4 (user will say something like "Show me the evidence trail"):

Step 1 — Call this tool:
  get_citation_trace(limit=5)

Step 2 — After tool result, respond with EXACTLY:
  "Every step traced. Every claim sourced — from the RAG semantic search through the SQL verification to the geospatial gap analysis. Full data lineage, powered by MLflow on Databricks."

Exactly this text. Nothing else.
```

---

## What You Type (Rehearse These)

| Beat | You type | Time budget |
|------|----------|-------------|
| 1 | "Where are the surgical deserts in Northern Ghana?" | 0:02-0:15 |
| 2 | "I see a facility near Tamale claims surgical capability. Can you verify that?" | 0:15-0:30 |
| 3 | "Where should we deploy one surgical team to save the most lives?" | 0:30-0:45 |
| 4 | "Show me the evidence trail" | 0:45-0:50 |

---

## What the Viewer Sees

### Pre-roll (0:00-0:02)
Screen.studio overlay. Dark screen. Text fades in: **"OASIS — Bridging Medical Deserts"**
Cut to Claude Desktop. Clean chat. No map yet.

### Beat 1: THE QUESTION (0:02-0:15)
- You type (sped up to ~1s)
- Claude responds with 2 sentences + launches map
- 3D globe rotates to Ghana, camera flies to Northern region
- Heatmap pulses red where surgery doesn't exist within 50km
- Green clusters in the south — the contrast is stark

**What judges think:** One sentence → full geospatial analysis with 3D visualization.

### Beat 2: THE INVESTIGATION (0:15-0:30)
- You type (sped up)
- Claude calls RAG search (Databricks!), then SQL cross-reference
- Response names a specific facility, specific anomaly
- Map zooms to the facility, warning badge appears

**What judges think:** The agent read free-form text, cross-referenced structured data, caught a lie. No dashboard does that.

### Beat 3: THE RECOMMENDATION (0:30-0:45)
- You type (sped up)
- Claude calls impact analysis, map transitions to impact overlay
- Bright zone pulses at optimal deployment location
- Response gives specific location, specific impact

**What judges think:** From analysis to actionable decision in one question.

### Beat 4: THE CLOSER (0:45-0:50)
- You type (sped up)
- Citation trace appears — tool calls, data sources, reasoning steps
- Claude's final line: "Every step traced. Every claim sourced."
- Map pulls back to all of Ghana. Fade to black.

**End card:** "OASIS — Today is gonna be the day..."

---

## Scoring Strategy

| Criterion | Weight | Beat | How We Score |
|-----------|--------|------|--------------|
| Technical Accuracy | 35% | All | Real tools, real data, real results — RAG, SQL, geospatial, anomaly |
| IDP Innovation | 30% | 2 | Free-form text extraction + structured cross-reference + anomaly detection |
| Social Impact | 25% | 3 | Actionable deployment recommendation with population impact |
| User Experience | 10% | All | Entire demo is natural language. No menus, no training |

**Databricks:** RAG search (Beat 2) + MLflow citations (Beat 4). Sponsor stack, visibly used.

**The implicit argument:** Nobody says "this beats a web app." But the judges watch a conversation that produces maps, catches data fraud, makes placement decisions, and cites its sources. They draw the conclusion.

---

## Screen.studio Editing

- **Speed up typing** to near-instant (~0.5s per query)
- **Cut Claude's thinking time** to 1-2s (actually takes 5-10s)
- **Hold on map transitions** — let camera fly animations play at real speed (the wow moments)
- **Zoom Screen.studio into the map** during Beat 2 — make the warning badge visible
- **Keep chat visible** alongside the map — the conversation IS the UI
- **Don't cut response streaming** — let text appear naturally, just skip the wait before it starts

---

## Tool Calls Reference

| Beat | Tools Called | Databricks? |
|------|-------------|-------------|
| 1 | `geo_map` (deserts mode) | No |
| 2 | `search_facility_capabilities` → `execute_query` | Yes (RAG) |
| 3 | `geo_map` (impact mode) | No |
| 4 | `get_citation_trace` | Yes (MLflow) |

---

## Dry Run Checklist

Before recording, run through once and capture:

- [ ] Beat 1: How many gaps returned? What's the worst location and distance?
- [ ] Beat 2: Which facility does RAG return for "surgical capability Tamale"? What's its pk_unique_id? What do staff/equipment numbers look like?
- [ ] Beat 3: What location does the impact analysis highlight?
- [ ] Beat 4: Does `get_citation_trace` return cleanly?
- [ ] Update the preset prompt with real numbers from the dry run
- [ ] Verify map animations look good at each beat
- [ ] Time the full flow — target under 2 minutes raw, 50s after Screen.studio cuts
