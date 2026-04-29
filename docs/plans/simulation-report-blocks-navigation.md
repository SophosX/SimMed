# Simulation Report Blocks and Drill-Down Navigation

Date: 2026-04-29
Status: Product/UX direction from Alex, plan before implementation

## Decision

SimMed should not only show dashboard output cards. After a simulation, users should be able to open a structured, article-like report view made of clear blocks.

Goal:

> The dashboard gives the quick overview. A separate report/detail page explains the simulation step by step so a non-expert can read into the result logically.

This report should feel like a structured policy briefing generated from the simulation, not like scattered charts.

## Navigation concept

After simulation, show two levels:

### 1. Dashboard / quick output

Current style:

- KPI cards
- short narrative summary
- changed levers
- trend chart
- political feasibility preview

Purpose: “What happened at a glance?”

### 2. Report / block view

A clickable/tap-friendly action from the dashboard:

- “Auswertung als Bericht öffnen”
- “Simulation Schritt für Schritt verstehen”
- “Policy-Briefing ansehen”

This opens a separate tab/page/section in Streamlit with structured blocks.

## Report block structure

Recommended order:

### Block 1: Executive Summary

Plain German, 5-8 sentences:

- What scenario was simulated?
- What changed compared with Germany baseline/reference projection?
- What are the most important outcomes?
- What is the biggest tradeoff?
- What should the user inspect next?

### Block 2: Germany Baseline and Reference Projection

Explain:

- current measured Germany baseline
- what is projected to 2040
- what is source-backed vs model assumption
- why this is a reference projection, not an official forecast

### Block 3: Your Scenario Changes

Show changed levers:

- baseline value
- scenario value
- difference
- evidence/source status
- model role
- caveat

This must be mobile-friendly and tap-friendly.

### Block 4: Causal Pathways

Explain the activated pathways:

- demography/demand
- morbidity/prevention
- workforce/training pipeline
- access/waiting time
- financing/GKV pressure
- regional equity
- digitalization/telemedicine
- political feasibility

Each pathway should answer:

- What changed?
- Why does this matter?
- Is the effect immediate or delayed?
- Which KPIs should move?

### Block 5: KPI Deep Dives

For each relevant KPI:

- meaning
- start/end movement
- whether movement is good/bad/ambiguous
- likely drivers
- uncertainty/caveat
- related KPIs
- next inspection

Sort by relevance/size of movement, not arbitrary order.

### Block 6: International Comparison

If selected/applicable:

- what other country did
- measured impact there
- evidence quality
- comparability to Germany
- transfer caveats
- German scenario translation

Important: do not claim foreign effects transfer 1:1.

### Block 7: Political and Implementation Feasibility

Explain:

- possible supporters
- possible blockers
- why they appear
- implementation lag
- institutional friction
- legal/federal/self-governance issues
- caveat: qualitative orientation, not prediction

### Block 8: Sources, Evidence and Assumptions

Show source/evidence block:

- source list
- evidence grades
- current measurement vs external projection vs SimMed assumption
- weak/placeholder areas
- what data should be improved next

## UX requirements

- Mobile/tablet first: no critical info only in hover.
- Blocks must be collapsible or navigable by anchor/table of contents.
- Each block should have a short title, plain summary and optional deeper detail.
- Users should never have to guess what to click next.
- Every block should link back to related dashboard KPIs where possible.

## Implementation strategy

Do not immediately build a large complex UI. Build reusable structured report data first.

### Slice 1: Report data model/helper

Create a helper such as `simulation_report.py` or app-level function:

- `build_simulation_report(agg, params)`

Returns structured sections:

- id
- title
- short_summary
- detail_items
- caveats
- related_kpis
- evidence_refs

No new model logic.

### Slice 2: Streamlit report page/tab

Add a tab/button after simulation:

- “Bericht” or “Policy-Briefing”

Render the structured sections as blocks/expanders.

### Slice 3: Link dashboard to report

From KPI cards or result summary, provide tap-friendly navigation/cues:

- “Mehr im Bericht: KPI Deep Dive”
- “Mehr im Bericht: Warum bewegt sich das?”

### Slice 4: Baseline/evidence integration

Connect report blocks to baseline/reference projection and source/evidence database once that data layer exists.

## Open question for Alex

Recommended name options:

1. “Bericht”
   Simple, understandable.

2. “Policy-Briefing”
   More professional, policy-lab feeling.

3. “Auswertung”
   Neutral and German, but less exciting.

Recommendation: use “Policy-Briefing” as main label and explain it as “strukturierte Auswertung”.

## Guardrails

- Do not generate unsupported policy facts.
- The report is an explanation of the simulation, not a replacement for evidence review.
- Keep short summary and deep detail separated.
- Reuse central helpers for KPI explanations, changed levers, political sections and future baseline/evidence storage.
