# MiroFish Inspiration Review for SimMed

Date: 2026-04-29
Status: Product/UX/architecture review; no implementation yet

## Source reviewed

- GitHub: https://github.com/666ghj/MiroFish
- Demo: https://mirofish-demo.pages.dev/

This review was requested by Alex as inspiration only. It does not import MiroFish code, claims or model logic into SimMed.

## Short conclusion

MiroFish is useful as inspiration for workflow, onboarding, scenario browsing and report interaction. It is not suitable as a modeling or credibility template for SimMed.

SimMed should borrow selected UX and architecture patterns, but reject the broad “predict anything / swarm predicts the future” framing.

Recommended framing for SimMed:

> Evidence-graded policy simulation and deliberation tool, not a future-prediction engine.

## What MiroFish does well

### 1. Strong first-contact clarity

MiroFish immediately communicates:

- one big promise
- one short subtitle
- primary call to action
- GitHub/docs credibility links
- demo examples

SimMed can use the pattern, but with safer wording:

- “Gesundheitspolitik vor Entscheidungen durchspielen”
- “Szenario starten”
- “Methodik / Annahmen ansehen”
- “Policy-Briefing öffnen”

### 2. Demo-first onboarding

The MiroFish demo makes the product feel usable before the user understands all internals.

SimMed adaptation:

- scenario gallery with curated German health-policy examples
- one-click examples such as study places, telemedicine, hospital reform, prevention, nursing staffing
- each scenario card shows: policy lever, target problem, affected KPIs, evidence status, caveat

### 3. Stepwise simulation workflow

MiroFish presents a pipeline:

1. Graph construction
2. Environment setup
3. Start simulation
4. Report generation
5. Deep interaction

SimMed adaptation:

1. Deutschland-Baseline / Referenzpfad verstehen
2. Reform oder internationales Beispiel auswählen
3. Annahmen und Evidenz prüfen
4. Simulation starten
5. Policy-Briefing lesen und vergleichen

### 4. Report as primary artifact

MiroFish treats report generation as a central output, not only as a chart afterthought.

SimMed should continue strengthening the Policy-Briefing as the main artifact:

- executive summary
- baseline/reference projection
- changed levers
- causal pathways
- KPI deep dives
- uncertainty and sensitivity
- evidence/source block
- political feasibility
- export/share

### 5. Progress/task/logging pattern

MiroFish has task state, report folders and agent logs. This is useful conceptually.

SimMed adaptation:

- scenario_id and report_id
- model version
- data vintage
- parameter changes
- source/evidence list
- sensitivity and uncertainty records
- every narrative claim linked to either model output, parameter assumption or source

## What SimMed should not copy

### 1. Overclaiming

Avoid:

- “Predict anything”
- “future rehearsal” as factual claim
- “high-fidelity digital world” unless validated

Use instead:

- “Szenario unter dokumentierten Annahmen”
- “Referenzprojektion, keine amtliche Prognose”
- “plausibler Modellpfad”
- “Sensitivität und Unsicherheit sichtbar”

### 2. Unconstrained LLM/swarm outputs

MiroFish uses LLM/agent-style generation and social simulation. For SimMed, this is dangerous if treated as evidence.

Guardrail:

- LLMs may draft or explain, but not create model facts.
- synthetic agent outputs must never be mixed with evidence data.
- stakeholder simulations are exploratory, not empirical proof.

### 3. Dense graph spectacle as main UI

Graph visuals are impressive but can overwhelm non-experts and mobile users.

SimMed should prefer:

- simple evidence/assumption maps
- pathway cards
- drill-down report blocks
- clear “what changed / why / confidence / next click” structure

### 4. Synthetic activity written back into evidence graph

MiroFish writes simulated activity back into memory/graph layers. For SimMed, this must remain separated.

Required layer separation:

1. Evidence graph: source-backed facts only
2. Assumption graph: explicit scenario/model assumptions
3. Simulation results: generated outputs, clearly synthetic
4. Narrative/report: derived explanation with claim-level provenance

## Team assessment

### Product / UX

Adopt:

- hero-first clarity
- scenario/demo browser
- stepwise guided workflow
- report-first output
- modern but restrained visual polish

Avoid:

- broad prediction promise
- technical graph as default view
- hidden complexity before users know what to do

### Technical architecture

Adopt conceptually:

- frontend/backend separation later
- async task/progress API
- durable report artifacts
- structured logs
- graph as inspection layer, not truth layer

Avoid:

- filesystem-only long-term state as final architecture
- LLM-generated graph facts without citation enforcement
- unconstrained report agents
- cloud memory dependency without governance

### Health-policy / evidence governance

Adopt:

- “sandbox” exploration idea
- stakeholder perspectives as optional qualitative layer
- narrative reports that help non-experts understand tradeoffs

Require guardrails:

- evidence grades
- source dates and jurisdictions
- uncertainty ranges
- sensitivity analysis
- expert-review workflow
- no 1:1 transfer from other countries
- no unsupported “X will happen” language

## Concrete SimMed adaptations

### Adaptation A: Scenario Gallery

A landing section with curated cards:

- “10.000 zusätzliche Medizinstudienplätze”
- “flächendeckende Telemedizin”
- “höherer Pflegeschlüssel”
- “KHVVG / Krankenhausreform”
- “Niederlande-Gatekeeping auf Deutschland übertragen”
- “Schweden-Wartezeitgarantie auf Deutschland übertragen”

Each card:

- target question
- changed levers
- likely affected KPIs
- evidence status
- caveat
- one-click run later

### Adaptation B: Guided 5-step workflow

For non-expert users:

1. Ausgangslage verstehen
2. Reform auswählen
3. Annahmen prüfen
4. Simulation laufen lassen
5. Policy-Briefing lesen

### Adaptation C: Evidence and assumption map

Instead of MiroFish-style dense graph as default, show a simple map:

- data source
- parameter
- model pathway
- KPI
- uncertainty/confidence
- caveat

### Adaptation D: Interactive Policy-Briefing

Strengthen the existing `simulation_report.py`/Policy-Briefing pattern:

- section navigation
- “why did this happen?”
- source/caveat per claim
- exportable memo
- “ask follow-up question” later, but only against report/source/model outputs

### Adaptation E: Agent council as workflow assistants

Agents can help with:

- evidence extraction
- source checking
- assumptions review
- political/institutional review
- report drafting
- critique/audit

They should not become “truth-generating simulated citizens” unless clearly labeled as exploratory.

## Recommendation

Use MiroFish as inspiration for onboarding and workflow, not as a modeling foundation.

Next implementation slice that makes sense:

- Continue the clarity/UX branch with Slice 1.2: example scenario cards / one-click examples.
- Use the MiroFish-inspired “demo-first” pattern, but with SimMed guardrails: every card shows evidence status and caveat before running.

Do not yet implement swarm-agent simulation. If agent-based simulation is considered later, first define evidence layers, calibration strategy and governance boundaries.
