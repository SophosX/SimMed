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

## 2026-04-29 clarity/UX Slice 1.1: landing hero

Implemented as the first Bühne 1 slice only: add a small top-of-page hero before result tabs/start content that answers “Was ist SimMed?” for first-time users. The block contains one mission sentence, three safe button-like navigation prompts, and a disclaimer that SimMed is not an official forecast. The buttons only store a session-state hint and do not change parameters, run simulations, or introduce model/data changes. Next logical slice remains Bühne 1 Slice 1.2: concrete example scenarios.

## 2026-04-29 next slice: Question-first result explorer

Problem: Even with a reading path and KPI details, users may arrive with practical questions rather than metric names: “Is access worse?”, “Is financing under pressure?”, “Which assumption should I distrust first?”, or “What political friction belongs to my changed lever?”. The result page should offer a compact question-first explorer that routes these questions to already existing KPI, trend, assumption, and political sections.

Small implementation slice:

1. Add a pure `build_result_explorer_topics(agg, params)` helper in `app.py`.
2. Reuse existing structured helpers only: KPI drill-down items, changed-parameter bridge, assumption checks, trend guidance, and political lever detail sections.
3. Return 4-5 topic cards with: question, short answer, strongest related KPI/lever if available, assumption/caveat, and next click.
4. Render it near the top narrative as expandable “Mit welcher Frage willst du starten?”.
5. Add a focused test that verifies question-first routing covers access, financing, assumptions, trend timing, and political feasibility without adding unsupported causal claims.

Guardrail: this is navigation/orchestration only. Do not create new empirical claims, new model effects, or a hidden political score; every answer must be assembled from existing explanation structures and caveats.

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


## 2026-04-29 next slice: Tap-friendly KPI card details

Problem: KPI cards now have desktop hover help and deeper expanders below, but mobile/tablet users may not discover hover text before scrolling. The first result screen should make the same meaning/why/read explanation reachable by tap, without duplicating inconsistent text.

Small implementation slice:

1. Reuse the central `kpi_detail_texts()` content through `kpi_mobile_detail(metric_key)`.
2. Render each visible KPI card with `render_metric_card_with_details(...)`, which keeps the existing HTML card and adds a Streamlit popover labelled “Details zu …”.
3. Switch the dashboard card grid to this renderer so all core KPI cards have the same accessible reading path on desktop and touch devices.
4. Add a focused unit test that guards the mobile detail helper reuses central meaning/why/read copy and includes a fallback for unknown KPIs.

Guardrail: this is accessibility/UX plumbing only. Do not add new claims, model logic or isolated tooltip strings; central KPI explanations remain the single source of truth.


## 2026-04-29 next slice: Prioritize KPI drill-downs by strongest movement

Problem: The result page has complete KPI detail expanders, but their order still follows dashboard categories. After the top narrative names the biggest movements, the drill-down list should continue that reading path by showing the most changed KPIs first.

Small implementation slice:

1. Extend `build_kpi_drilldown_items(agg, params)` with structured numeric `abs_delta`, `pct_delta`, and `effect_strength` fields derived from `_metric_delta_summary(...)`.
2. Sort returned KPI drill-down items by absolute percentage movement descending, so the first expander usually matches what the narrative told the user to inspect.
3. Keep labels, caveats and next-click text unchanged; this is information architecture only.
4. Add a focused test that a sample scenario with a large GKV-Saldo swing places that KPI before lower-movement items and exposes the effect-strength metadata.

Guardrail: Do not change model outputs or invent causality; only reorder and expose already computed movement summaries.

## 2026-04-29 next slice: KPI relationship trail inside drill-downs

Problem: Even with sorted drill-downs, a user can still read one KPI in isolation. The result journey should explicitly say which neighboring indicators make the interpretation safer: finances with contribution/saldo, access with physician density/rural supply, outcomes with mortality/chronicity, and system stress with the underlying drivers.

Small implementation slice:

1. Add a pure `kpi_related_inspections(metric_key)` helper in `app.py` returning short, model-internal related-KPI prompts.
2. Extend `build_kpi_drilldown_items(agg, params)` with a `related_inspections` list for each KPI.
3. Render those prompts inside each KPI expander after the observation, before model drivers, so the reading path becomes: meaning → observation → related checks → drivers → changed levers → assumption → next click.
4. Add a focused test that core KPI drill-downs include relevant related checks and do not rely on new external factual claims.


## 2026-04-29 next slice: Policy-Briefing Leitfragen per section

Problem: The report is now structured, but each expander still reads like a short summary. A user who asks “what changed, why, how strong, what assumption, what next?” should see those questions explicitly repeated across the report journey, not infer them from prose.

Small implementation slice:

1. Add structured `guide_questions` to every `build_simulation_report(...)` section: What changed? Why in the model? How strong/where to see strength? Which assumption limits interpretation? What should I inspect next?
2. Render these questions before section points as a tap-friendly checklist inside each report expander.
3. Keep all answers sourced from existing helper outputs (`summary`, bridge, KPI drilldowns, trend guidance, assumption checks, political rubric); do not add new model logic or real-world claims.
4. Add a focused test that the report exposes the guide-question structure and includes the required plain-language prompts.

Guardrail: This is information architecture, not a new claim layer. It should make the existing report easier to read on mobile and for newcomers.

Guardrail: This is explanation/information architecture only. Do not change simulation outputs, political claims, scoring, or empirical assumptions.
## 2026-04-29 next slice: Guided result reading path

Problem: The page now contains narrative, parameter bridge, KPI drill-downs, trend guidance and political sections, but first-time users may still not know in which order to read them or why that order matters. The next small slice should make the result journey explicit without adding another disconnected snippet.

Small implementation slice:

1. Add a pure `build_result_reading_path(agg, params)` helper in `app.py`.
2. The helper should reuse existing narrative/top-change and changed-parameter bridge outputs to return ordered steps: orient, connect changed levers, inspect biggest KPI, read trend timing, then check politics/stakeholders.
3. Render the steps directly inside the top narrative block as an expander labelled “Empfohlene Lesereihenfolge”.
4. Add a focused test that verifies the helper names changed levers, strongest KPI, assumptions/caveats, trend timing and political feasibility as next checks.

Guardrail: This is information architecture only. Do not introduce new empirical claims, model logic or stakeholder assertions; only organize existing explanation layers into a coherent journey.

## 2026-04-29 next slice: Assumption/evidence check for changed levers

Problem: The result journey now shows what moved and which changed levers may matter, but a user can still jump too quickly from “KPI changed” to “policy works”. The result page needs a small explicit checkpoint that says: before drawing a policy conclusion, inspect the evidence grade, source register, uncertainty and caveat for each changed lever.

Small implementation slice:

1. Add a pure `build_changed_parameter_assumption_checks(agg, params)` helper in `app.py` that reuses `build_changed_parameter_impact_bridge(...)` and `parameter_registry.PARAMETER_REGISTRY`.
2. For each changed explained lever, return label, evidence/source summary, model caveat, registry caveat, uncertainty, source/register role and a concrete sanity-check instruction.
3. Render these checks as one expander after “Was bedeuten deine geänderten Hebel?” so it strengthens the existing reading path instead of becoming another top-level snippet.
4. Add a focused test proving prevention/study-place changes show evidence grade, sources, register role, caveat/uncertainty, KPI/time-trend sanity check, and the “not proven real-world effect” warning.

Guardrail: This is evidence/provenance UX only. Do not add new empirical claims, model logic, political stakeholder assertions or scores.

## 2026-04-29 next slice: Policy-Briefing navigation index

Problem: the new Policy-Briefing sections are coherent internally, but a first-time reader still sees six expanders and may not know whether to skim, open everything, or start from a specific concern. The report needs a short navigation index before the expanders so the report behaves like a guided briefing rather than a list of collapsible blocks.

Small implementation slice:

1. Add a pure `build_report_navigation_index(report_sections)` helper in `app.py`.
2. For each report section, return the section title, one short reason to open it, the first guide question, and a stable anchor-style target based on the section id. Add a compact overall reading instruction that says: skim the Executive Summary first, then open the section matching your question.
3. Render this index at the start of `render_simulation_report()` before the detailed expanders. It must be tap-friendly and not depend on hover.
4. Add a focused test verifying that the index covers all six report sections, preserves order, names “Executive Summary”, “Geänderte Hebel”, “KPI”, “Zeitverlauf”, “Evidenz”, and “Politische Umsetzbarkeit”, and includes the concrete “what to open next” instruction.

Guardrail: This is information architecture only. Do not add empirical claims, model logic, new stakeholder assertions, or visual complexity; reuse existing section titles, purposes, and guide questions.

## 2026-04-29 next slice: Policy-Briefing question shortcuts

Problem: even with an index, users may arrive with one concrete question rather than a desire to read six sections. The report should translate common result-reading questions into the exact expander to open, so the page feels guided rather than encyclopedic.

Small implementation slice:

1. Add a pure `build_report_question_shortcuts(report_sections)` helper in `app.py`.
2. Return 5 concise shortcut rows keyed to existing sections only: strongest change, changed lever path, KPI meaning/strength, timing/trend, evidence/political caveat. Each row should include the user question, the recommended section title/id, and why that section answers it.
3. Render these shortcuts inside the existing “Wie lese ich dieses Briefing?” expander before the full section index, as tap-friendly bullets.
4. Add a focused test that verifies every shortcut points to an existing section, covers KPI/trend/evidence/politics, and does not introduce new factual claims beyond existing section metadata.

Guardrail: This is navigation UX only. It must not add model logic, empirical assumptions, stakeholder assertions, or duplicate long explanation copy.

## 2026-04-29 next slice: KPI-specific changed-lever matching

Problem: KPI detail cards currently show the same global list of changed scenario levers in every expander. That is honest but still too shallow: a user who opens “Facharzt-Wartezeit” should immediately see which of their changed levers plausibly connects to that KPI path, while “GKV-Saldo” should not imply the same relevance if the lever only touches access.

Small implementation slice:

1. Add a pure `kpi_matching_changed_levers(metric_key, agg, params)` helper in `app.py`.
2. Reuse `build_changed_parameter_impact_bridge(...)` and its observed KPI pointers; match only already explained changed levers whose KPI pointers include the current KPI label. Return lever label, model path, caveat and next step.
3. Extend `build_kpi_drilldown_items(...)` with `matching_changed_levers` and render it before the fallback global scenario notes. If no direct match exists, explicitly say there is no direct bridge yet and use the global notes only as context.
4. Add a focused test proving Telemedizin appears for Facharzt-Wartezeit but not for an unrelated KPI when the scenario only changes Telemedizin.

Guardrail: This is explanation routing only. Do not add new model effects, external factual claims, political claims or hidden causal scoring; use existing bridge text and simulated KPI pointers.

## 2026-04-29 next slice: Trend rows for selected metrics

Problem: The trend chart explains mixed units, but users still have to hover over the plot to answer the practical question: for each selected line, what was the start value, end value, direction, effect strength, and next KPI card to inspect? Hover is weak on mobile and makes the trend view feel separate from the result reading path.

Small implementation slice:

1. Add a pure `build_trend_metric_reading_rows(agg, selected_labels, choices)` helper in `app.py`.
2. For every selected metric with an available aggregate column, return label, start value, end value, absolute change, percent change, direction, effect strength, a mixed-unit caveat, and a concrete next inspection prompt.
3. Render these rows inside the existing trend-reading expander after the general guidance, so the chart becomes readable even without hover.
4. Add a focused test that the rows expose start/end/effect strength, include the mixed-unit caution, map Facharzt-Wartezeit to the KPI detail next step, and skip missing columns safely.

Guardrail: This is chart-reading UX only. Do not change simulation outputs, add empirical claims, or infer new causality beyond the selected time series.

## 2026-04-29 next slice: KPI detail answer checklist

Problem: KPI expanders already contain the right ingredients, but a newcomer still has to map them back to Alex's core result questions: what changed, why, how strong, which assumptions, and what to inspect next. The card should make this journey explicit at the top before the longer detail text.

Small implementation slice:

1. Add a pure `build_kpi_answer_checklist(item)` helper in `app.py` that derives short answer rows from an existing KPI drill-down item.
2. Return stable rows for exactly the same five questions: `Was hat sich verändert?`, `Warum im Modell?`, `Wie stark?`, `Welche Annahme begrenzt die Lesart?`, and `Was als Nächstes prüfen?`.
3. Render the checklist at the top of each KPI expander before the detailed numbered path. Keep all text derived from existing drill-down fields so this is information architecture, not new causal content.
4. Add a focused test proving the checklist is complete, uses the KPI's observation/effect strength/assumption/next-step fields, and includes direct changed-lever context when available.

Guardrail: This must not add empirical claims or new model effects. It only makes the existing KPI detail card answer the user's questions faster and more coherently.

## 2026-04-29 next slice: Lever bridge to exact KPI drill-down targets

Problem: The changed-parameter bridge already names observed KPI traces, but a user still has to translate those traces into the exact detail cards to open. This is a small coherence gap in the journey “I changed X → what moved → where do I click next?”.

Small implementation slice:

1. Extend `build_changed_parameter_impact_bridge(agg, params)` with a `drilldown_targets` list for each changed lever.
2. Each target should reuse existing KPI labels and pointer text only: metric key, label, observed trace, and the exact recommended detail-card prompt.
3. Render these targets inside the existing changed-lever expander after observed KPI traces, so users get an explicit click path without adding a new standalone UI block.
4. Add a focused test proving Medizinstudienplätze links to Ärzte pro 100k, Facharzt-Wartezeit, and ländliche Versorgung targets with existing start/end traces and a KPI-detail next step.

Guardrail: This is navigation UX only. Do not add model effects, empirical claims, political claims, or a hidden causal score; every target is derived from existing bridge KPI pointers.
## 2026-04-29 next slice: Question explorer reading paths

Problem: The question-first explorer gives a practical entry question, answer, caveat and next click, but it still reads as five compact cards. A user who starts from a question should see the same coherent mini-journey inside each card: result signal → changed lever/model path → assumption/evidence check → exact next section.

Small implementation slice:

1. Extend `build_result_explorer_topics(agg, params)` with a `reading_path` list on every topic.
2. Build each path only from existing structured fields: KPI drill-down observation/effect strength, changed-parameter bridge, assumption checks, trend guidance, and political lever detail sections.
3. Render the path under each question in the existing expander so it deepens the current result explorer rather than adding a new standalone snippet.
4. Add a focused test proving every topic has ordered steps covering signal, reason/model path, assumption/caveat, and next inspection, and that political wording remains a qualitative rubric/not a vote forecast.

Guardrail: This is navigation/information architecture only. Do not add new empirical claims, model effects, causal scores, or stakeholder assertions; each step must point back to already existing explanation structures.


## 2026-04-29 next slice: KPI assumption trace for matched levers

Problem: KPI detail cards can now identify which changed levers match a KPI, and the separate assumption-check block shows evidence/caveats per lever. A user still has to connect those two sections manually before trusting or questioning a KPI explanation.

Small implementation slice:

1. Add a pure `build_kpi_assumption_trace(item, assumption_checks)` helper in `app.py`.
2. For each KPI drill-down item, match its direct changed levers to existing changed-lever assumption checks and return compact rows: lever label, evidence/source summary, model caveat, registry caveat, uncertainty, and the exact sanity-check instruction.
3. Extend `build_kpi_drilldown_items(...)` and `render_kpi_deep_dive(...)` so the evidence checkpoint appears inside the KPI expander directly after the matched-lever context.
4. Add a focused test proving a KPI matched to Telemedizin exposes the existing evidence/caveat/sanity-check row, while unrelated KPIs stay explicit that no direct assumption trace exists.

Guardrail: This is explanation routing only. Do not add new empirical claims, model effects, data-source claims, or political stakeholder assertions; reuse only existing assumption-check fields and parameter registry metadata.

## 2026-04-29 next slice: Political result checkpoints

Problem: The political lever detail explains supporters/blockers, but users still have to jump back mentally to the changed-lever bridge and KPI details to judge whether political friction is worth the simulated effect. The political section should therefore show a compact, evidence-safe checkpoint: which observed KPI traces belong to this lever, which detail cards to open, and why this remains a qualitative rubric rather than a vote forecast.

Small implementation slice:

1. Add a pure `build_political_result_checkpoints(political_sections, bridge_items)` helper in `app.py`.
2. Match political lever sections to existing changed-parameter bridge items by normalized labels only; do not invent new stakeholder or model claims.
3. Return for each matched lever: label, political friction/lag, observed KPI traces, exact KPI detail targets, caveat, and next step.
4. Render these checkpoints inside the existing political lever expander after the uncertainty block, so the journey becomes changed lever → simulated KPI traces → political friction → next inspection.
5. Add a focused test proving Medizinstudienplätze gets KPI targets and the not-a-vote-forecast caveat, while unmatched political sections safely return no checkpoint.

Guardrail: This is cross-navigation only. Reuse existing political sections and changed-parameter bridge fields; do not add empirical claims, vote predictions, lobbying advice, or new causal effects.
