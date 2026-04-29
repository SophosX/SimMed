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
