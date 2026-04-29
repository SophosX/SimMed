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
- mobile/tablet rule: never rely on hover alone; every tooltip explanation must also be available through tap-friendly captions, popovers, or expanders, and KPI grids must remain readable on narrow screens

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

## 2026-04-29 next slice: Trend view reading guide

Problem: the trend chart now has hover and larger lines, but a first-time user can still misread it as one shared unit scale. Because the default chart mixes euros, days, percentages and headcounts, the UI must explicitly teach how to read it before adding more charts.

Small implementation slice:

1. Add a pure `build_trend_view_guidance(selected_labels)` helper in `app.py`.
2. The helper returns: what the lines mean, why units should not be compared directly, what the default three metrics are meant to answer, and what to inspect next.
3. Render this guidance directly above/below the multiselect in `render_main_trend_chart()` so the trend view becomes part of the same reading path.
4. Add a focused test in `tests/test_app_explanations.py` that guards the mixed-unit warning, mean-over-time explanation, and next inspection step.

Guardrail: this is UI explanation only. Do not change model outputs, add new causal claims, or imply that the chart is a validated real-world forecast.

## 2026-04-29 next slice: Political feasibility as lever-by-lever explanation

Problem: the political card now lists supporters and blockers and gives one generic explanation row per stakeholder. A newcomer still has to infer the reading path: which changed lever caused the political friction, why each group appears, what exactly could make implementation hard, and what to inspect next.

Small implementation slice:

1. Add a pure `build_political_lever_detail_sections(political_assessment)` helper in `app.py`.
2. The helper should group information by changed lever and return: lever label, model/policy effect, implementation lag, friction, supporter rows, blocker rows, uncertainty/caveat, strategy checkpoint, and next inspection prompt.
3. Render those sections in the political card as expanders after the high-level overview. Keep the old flat row helper for tests/backward compatibility, but use the new grouped helper for the main reading path.
4. Add a focused test that verifies the grouped details include supporters, blockers, changed lever, implementation lag, friction, caveat, and a concrete next inspection prompt.

Guardrail: stakeholder text remains a qualitative rubric/proposal, not a sourced vote forecast, hidden score, or lobbying recommendation. Do not add new stakeholder claims beyond existing `political_feasibility.py` rules in this slice.

## 2026-04-29 next slice: Changed-parameter impact bridge

Problem: the result page now has a narrative, KPI drill-downs and political lever detail, but users still have to mentally connect their concrete parameter changes to observed KPI movement. The page should explicitly bridge “Du hast X geändert” → “im Modell wirkt das über diesen Pfad” → “diese KPI-Bewegungen solltest du prüfen”.

Small implementation slice:

1. Add a pure `build_changed_parameter_impact_bridge(agg, params)` helper in `app.py`.
2. For the already explained main levers (Telemedizin, ePA/Digitalisierung, Prävention, Medizinstudienplätze, Pflegepersonalschlüssel), return: lever label, concrete change direction, model path, timing/assumption caveat, observed KPI pointers, and next inspection.
3. Render the bridge near the top result narrative as expandable “Was bedeuten deine geänderten Hebel?”.
4. Add a focused test that verifies it names the changed lever, shows start/end KPI pointers, flags delayed/ambiguous effects for prevention/study places, and gives a concrete next click.

Guardrail: this is an explanation bridge only. It must not add new model logic, new stakeholder claims or authoritative real-world claims; use existing simulation outputs and existing caveats.
