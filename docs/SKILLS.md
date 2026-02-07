# Agent Skills

Skills are contextual prompts that teach AI coding assistants how to accomplish specific tasks.

## What Skills Do

Without skills, an AI assistant might guess at APIs or make assumptions about data. With OASIS skills installed, the assistant knows the dataset schema, query patterns, and domain-specific logic.

Skills activate automatically when relevant.

## Installing Skills

```bash
# Interactive tool and skill selection
oasis skills

# Install all skills for specific tools
oasis skills --tools claude

# Install specific skills by name
oasis skills --tools claude --skills vf-schema,idp-extraction

# List installed skills
oasis skills --list
```

Skills are installed to `.claude/skills/` (or equivalent for other tools). AI assistants automatically discover skills in these locations.

## Skill Structure

Each skill is a directory containing a `SKILL.md` file:

```
src/oasis/skills/clinical/
├── vf-schema/
│   └── SKILL.md
├── idp-extraction/
│   └── SKILL.md
└── medical-desert-analysis/
    └── SKILL.md
```

The `SKILL.md` contains:

```markdown
---
name: vf-schema
description: Virtue Foundation Ghana data structure, column semantics, and query patterns
tier: community
category: clinical
---

# VF Ghana Schema Knowledge

[Detailed instructions, SQL examples, domain context...]
```

The frontmatter has four required fields: `name`, `description`, `tier` (one of `validated`, `expert`, `community`), and `category` (`clinical` or `system`). See `src/oasis/skills/SKILL_FORMAT.md` for full details.

## Creating Custom Skills

Create a skill for your research domain:

```markdown
---
name: medical-desert-analysis
description: Identify and characterize healthcare coverage gaps. Triggers on "medical desert", "coverage gap", "underserved area"
tier: community
category: clinical
---

# Medical Desert Analysis

When identifying medical deserts in the VF Ghana dataset:

1. Query facilities by region and specialty
2. Identify regions with no coverage for a given specialty
3. Consider travel distances and population density
4. Cross-reference equipment, procedures, and capabilities

## Standard Query

\`\`\`sql
SELECT
    address_stateOrRegion as region,
    COUNT(*) as facility_count,
    COUNT(CASE WHEN specialties != '[]' THEN 1 END) as with_specialties
FROM vf.facilities
GROUP BY address_stateOrRegion
ORDER BY facility_count
\`\`\`
```

Place in `src/oasis/skills/clinical/medical-desert-analysis/SKILL.md`.

## Tips for Effective Skills

**Be specific about triggers.** The description should clearly indicate when the skill applies.

**Include working code examples.** Show exact imports, function calls, and expected outputs.

**Document edge cases.** What errors might occur? What datasets are required?

**Keep skills focused.** One skill per domain or workflow.
