# Baseline, Change and Evidence Redesign

Date: 2026-04-29
Status: Discussion plan before implementation

## Why this exists

Alex pointed out that SimMed is not yet clear enough about three fundamental questions:

1. What exactly is the standard/baseline health-system scenario?
2. What exactly did the user change compared with that baseline?
3. Why did these changes move other values, and which sources/evidence support the assumptions?

This should not be solved with isolated UI snippets. It needs a structured product, model and evidence design.

## Product principle

Every scenario result must be readable as:

Baseline -> user changes -> model pathways -> changed outcomes -> evidence/provenance -> caveats/uncertainty.

A first-time user should be able to say:

- This is the assumed default German health-system trajectory.
- I changed these specific levers.
- These model pathways were activated.
- These KPIs moved because of those pathways.
- These assumptions are evidence-backed, weak, or still placeholders.
- Here is what I should inspect next.

## Required user-facing sections

### 1. The Standard: What is the baseline?

A dedicated baseline card/page should explain:

- baseline year and model version
- default demographic assumptions
- default financing assumptions
- default workforce/capacity assumptions
- default morbidity/prevention/digitalization assumptions
- data vintage and source quality summary
- what is official data vs scenario assumption
- what the baseline is not: not an official forecast, but a transparent reference scenario

### 2. You changed these levers

After every simulation, show a compact diff against baseline:

- changed parameter label
- baseline value
- user value
- absolute difference
- percentage difference where meaningful
- evidence grade/source status
- immediate model role in plain language

This must be mobile-friendly and tap-friendly. No critical information only in hover.

### 3. Therefore these pathways changed

Group changed levers by causal pathway:

- Demography and demand
- Morbidity and prevention
- Workforce and training pipeline
- Access and waiting times
- Rural/regional distribution
- Financing/GKV pressure
- Digitalization/telemedicine
- Political feasibility/implementation friction

For each group explain:

- what the changed lever does in the model
- whether the effect is immediate or delayed
- whether the effect is direct or indirect
- what caveat/uncertainty matters
- which KPIs should move if the model behaves logically

### 4. Therefore these KPIs moved

For each important changed KPI:

- baseline-start value
- scenario-end value
- size of movement
- direction and whether this is good/bad/ambiguous
- likely contributing changed levers
- related KPIs to inspect
- uncertainty/caveat

Avoid only showing percentages. Percentages need interpretation.

### 5. Evidence and resources

Every important parameter and causal claim should have visible provenance:

- source name and source type
- evidence grade A-E
- whether it is official data, institutional evidence, literature, proxy, or assumption
- source period/vintage where available
- caveat in plain German

The UI should distinguish:

- strongly sourced baseline facts
- scenario assumptions
- simplified model relationships
- unsupported/placeholder areas that need research

## Implementation strategy

Do not implement all at once. Use small slices, but each slice must fit the full structure above.

### Slice A: Baseline definition object

Create a central baseline summary helper/module that reuses defaults and parameter registry metadata.
Output should be structured data, not only markdown.

Fields:

- model_version
- baseline_year
- reference_scenario_name
- baseline_sections
- parameters included
- source/evidence summary
- caveats

### Slice B: Scenario diff object

Create a helper that compares params to get_default_params() and returns structured changed-lever records.
Each record should include label, baseline, scenario, difference, percent difference, model role, evidence grade, source ids and caveat.

### Slice C: Pathway explanation object

Map changed parameters to pathway groups and expected KPI directions.
This should be explicit and testable.

### Slice D: Result explanation bridge

Connect scenario diff + pathways + observed KPI changes.
UI should answer: “You changed X; this affects Y pathway; therefore watch Z KPIs; in this run they moved like this.”

### Slice E: Evidence/resource panel

Show sources and evidence grades in a clean, mobile-friendly panel.
No new claim should be shown as a fact unless it has provenance or is labeled as assumption.

## Open questions for Alex

1. Should the baseline be called “Standard-Szenario”, “Referenz-Szenario”, or “Deutschland 2040 Baseline”?
2. Should the app always show baseline-vs-scenario side by side, or only after the user changes something?
3. How aggressive should evidence warnings be? Subtle badge vs prominent warning when a parameter is weakly sourced.
4. Should the next implementation focus first on the baseline definition page or the after-simulation “you changed this” diff?

## Recommendation

Start with Slice A + B together:

- Define the baseline formally.
- Show what changed from baseline.

Reason: without this, all later “why did results change?” explanations are floating in the air.

Only after Alex agrees on naming and UX framing should this become a larger UI change.
