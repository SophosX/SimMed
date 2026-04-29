# Results Experience Redesign Plan

Goal: Make SimMed results understandable and valuable after a user changes parameters and runs a simulation.

## Problem

Current dashboard shows many numbers but not enough explanation. Users see percentage changes and short text, but do not clearly understand:

- what changed
- why it changed
- which parameter caused it
- how strong the effect is
- which assumptions matter
- why political supporters/blockers are listed
- what to inspect next

## Product direction

Build an “Ergebnis verstehen” layer.

Each result area should answer:

1. What does this metric mean?
2. What happened in this run?
3. Why did it happen?
4. Which changed parameter is probably relevant?
5. What assumption should the user question?
6. What should the user inspect next?

## Implementation slices

### Slice 1: Result narrative summary

Add a top result summary above KPI cards:

- “Was ist in dieser Simulation passiert?”
- 3-5 most important changes
- plain-language interpretation
- link-like hints to explore KPI details below

### Slice 2: KPI drill-down cards

Improve current KPI explanations:

- every core KPI gets an expander
- include metric meaning, observed start/end, direction, likely drivers, caveats, next inspection
- avoid only showing percentage changes

### Slice 3: Political feasibility explanations

Replace plain bullet supporters/blockers with explanatory rows:

- stakeholder/group
- why they may support/block
- affected lever
- uncertainty caveat

### Slice 4: Trend view redesign

Make trend chart easier:

- one primary chart
- visible axis labels
- hover values
- short “how to read this” text
- default to 3 important metrics only

### Slice 5: Parameter-impact mapping

Connect changed parameters to result explanations:

- “You changed X”
- expected effect path
- observed KPI direction
- warning if effect is delayed or ambiguous

## Guardrails

- Do not claim causality beyond model logic.
- If uncertain, say uncertain.
- Research/source real-world claims later before making them authoritative.
- Keep UI clear; do not bury users in walls of text.

## Verification

Run:

```bash
python3 -m pytest -q
python3 -m py_compile app.py
python3 - <<'PY'
from simulation_core import get_default_params, run_simulation
p=get_default_params(); p['telemedizin_rate']=0.2
print(run_simulation(p, n_runs=20, n_years=2, base_seed=5)[0].shape)
PY
```

## 2026-04-29 heartbeat refinement

Alex's quality bar: the results page must become a coherent reading path, not another pile of snippets. The intended journey is:

1. **Orient first:** show a short narrative above KPI cards: what changed most, whether the movement is good/bad/ambiguous, and what to open next.
2. **Drill down:** every important KPI should expose meaning, start/end values, strength of movement, likely model drivers, caveats and next inspection.
3. **Read trends:** trend charts need explicit reading guidance: lines show model means over time; different units should not be over-compared as if one axis made them equivalent.
4. **Connect politics to levers:** supporters/blockers must be explained per changed lever, including why the group appears, what uncertainty remains, and how it relates to implementation lag/friction.
5. **Stay honest:** all political/stakeholder text remains a transparent hypothesis/rubric, not a sourced vote forecast.

Implemented slice: top result narrative plus lever-level political stakeholder rows are live and test-covered.

## 2026-04-29 next slice: KPI drill-down reading path

Problem: the KPI section still explains many cards as separate snippets. The next small slice should make every drill-down follow the same reading order so a newcomer knows exactly what to do:

1. **Bedeutung:** what this KPI measures in plain language.
2. **Beobachtung:** start value, end value, absolute change and effect strength.
3. **Warum im Modell:** model drivers already encoded in the simulation; do not add new causal facts.
4. **Geänderte Hebel:** scenario levers that may matter, clearly labelled as model interpretation.
5. **Annahme prüfen:** main caveat/assumption.
6. **Nächster Klick:** concrete next chart/KPI/political section to inspect.

Implementation guardrail: add a pure helper that returns structured drill-down items, test that it includes observation/strength/next-step fields, then render from that helper. Keep the UI expandable; no extra isolated text blocks.
