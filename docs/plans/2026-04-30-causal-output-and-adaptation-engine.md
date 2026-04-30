# Causal Output and Adaptation Engine Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make SimMed results explain exactly what the simulation output is, why it happened, what the user changed, which adaptation mechanisms were triggered, and where the current model is too weak or counterintuitive.

**Architecture:** Split the work into two tracks: (1) model/engine changes that make causal mechanisms explicit and stronger, and (2) output/explanation changes that expose an auditable input → mechanism → KPI trace. Do not let free text directly mutate model parameters; convert it into reviewed scenario proposals with confidence, assumptions, affected levers, and a safe preview.

**Tech Stack:** Python simulation core, Streamlit UI, FastAPI API, pytest. Evidence/provenance through existing `parameter_registry.py`, `data_sources.py`, `data_ingestion.py`, and future scenario policy taxonomy.

---

## 1. Current-state diagnosis

### How simulations currently come about

The current simulation is **not** a random internet search.

It is a local, deterministic/stochastic Python model in `simulation_core.py`:

- baseline defaults come from `get_default_params()`;
- yearly dynamics run in `_simulate_year(...)`;
- Monte Carlo variation comes from seeded random noise and rare shocks;
- results are aggregated into mean/P5/P95 bands;
- provenance/evidence metadata exists in `parameter_registry.py` and `data_sources.py`;
- the model does **not** currently fetch the internet during a simulation run.

### What is weak right now

1. **Evidence is mostly registry/provenance metadata, not always deeply integrated into equations.**
   The app has source IDs and evidence grades, but many coefficients are still model assumptions or simplified heuristics.

2. **Adaptation mechanisms exist, but are too shallow.**
   Current feedback loops include things like shortage → more immigration/study pipeline, waiting time → more telemedicine, deficit → contribution changes/cuts/subsidy. But these are not yet strong, scenario-specific, or visible enough.

3. **Medical study place cuts do not behave dramatically enough.**
   The model has a `pipeline_buffer`, but if study places are halved, the output should clearly show delayed impact beginning after medical training lag and worsening through the 6–15 year horizon. The current behavior can be damped by migration, telemedicine, baseline workforce, weak dropout/retirement dynamics, and burnout recalculation.

4. **Burnout can move counterintuitively.**
   Current burnout is recalculated from workload using a relatively simple formula. If physician supply drops but demand-side relief/adaptation offsets too much, burnout may fall, which violates Alex’s expected causal intuition unless clearly explained by a compensating mechanism. This needs either model correction or explicit “why did this happen?” trace.

5. **The result output is still too vague.**
   It often says “this changed” and “check caveats,” but not enough:
   - exact output movement by year/window,
   - causal chain,
   - triggered mechanisms,
   - why unexpected signs occurred,
   - what would need to be true for the result to be plausible.

6. **Stellschrauben are too narrow.**
   Important broad policy levers are missing, e.g. payment reform away from DRG/fallpauschale, cutting GKV benefits such as skin-cancer screening, changing coverage, reimbursement, substitution, rationing, referral rules, workforce scope-of-practice, etc.

7. **Free text is not yet safely supported.**
   Users should be able to type “Abrechnungsart weg von Fallpauschalen” or “Hautkrebs-Screening aus GKV streichen,” but the model must parse this into a transparent proposal, not silently invent hidden parameters.

---

## 2. Product target

SimMed should become an **auditable causal scenario simulator**:

1. User changes sliders or enters free text.
2. System maps the change to a typed policy intervention.
3. System identifies affected model levers and assumptions.
4. Simulation runs primary effects and likely adaptation mechanisms over time.
5. Output explains:
   - “Du hast geändert …”
   - “Das Modell hat deshalb diese Primärwirkung angenommen …”
   - “Ab Jahr X wurde dieser Anpassungsmechanismus ausgelöst …”
   - “Diese KPIs bewegten sich konkret …”
   - “Wenn das Ergebnis kontraintuitiv ist, liegt es an Mechanismus Y; wenn Y unplausibel ist, ist diese Modellannahme zu ändern.”

---

## 3. New model concepts

### 3.1 Scenario intervention taxonomy

Add a typed layer above raw parameters.

Examples:

- `workforce_training_capacity_change`
  - e.g. halve medical study places.
- `payment_system_reform`
  - e.g. DRG/fallpauschale → hybrid/global budget/value-based payment.
- `benefit_coverage_change`
  - e.g. remove skin-cancer screening from GKV benefit catalog.
- `care_substitution_change`
  - e.g. more delegation to nurses/PAs, pharmacists, digital triage.
- `access_gatekeeping_change`
  - e.g. stronger Hausarztmodell, referral constraints.
- `provider_payment_level_change`
  - EBM/GOÄ/DRG price changes.
- `capacity_policy_change`
  - beds, ambulatory seats, planning rules, rural incentives.
- `digital_process_change`
  - ePA, AI scribes, telemedicine, automation.
- `prevention_public_health_change`
  - prevention budget, screening, vaccination, lifestyle programs.

Each intervention should include:

```python
{
    "id": "...",
    "label": "...",
    "category": "...",
    "user_input": "...",
    "mapped_parameters": [...],
    "primary_effects": [...],
    "likely_adaptations": [...],
    "time_lag_years": {...},
    "evidence_grade": "A/B/C/D/E/mixed",
    "source_ids": [...],
    "assumptions": [...],
    "guardrail": "proposal/model assumption, not proven outcome",
}
```

### 3.2 Adaptation mechanism registry

Create explicit adaptation mechanisms, not hidden small coefficients.

Examples:

- physician shortage → telemedicine acceleration;
- physician shortage → immigration recruitment;
- physician shortage → longer working hours/part-time reversal;
- physician shortage → delegation/substitution to non-physician roles;
- physician shortage → higher burnout and exits;
- waiting-time pressure → private/self-pay migration;
- GKV deficit → contribution increases, federal subsidy, benefit cuts;
- benefit cuts → lower short-term spending but more delayed morbidity/unmet need;
- DRG removal → less case-volume incentive, changed hospital revenue, possibly longer stays/capacity pressure, lower overtreatment depending on assumptions;
- screening removal → short-term savings, later-stage diagnoses, delayed higher treatment cost and avoidable mortality.

Each mechanism needs:

```python
{
    "trigger": "shortage_index > threshold",
    "starts_after_year": 0/1/3/6,
    "strength": "weak/medium/strong",
    "saturation": "cap",
    "affected_kpis": [...],
    "explanation_template": "...",
    "evidence_status": "source-backed / assumption / proxy",
}
```

### 3.3 Causal trace output

Every simulation should produce a machine-readable causal trace:

```python
{
    "changed_inputs": [...],
    "primary_effects": [...],
    "adaptation_events": [...],
    "kpi_movements": [...],
    "counterintuitive_findings": [...],
    "model_limitations": [...]
}
```

This should be included in API output and Streamlit result page.

---

## 4. Implementation tasks

### Task 1: Add regression test for medical study-place crash expectation

**Objective:** Capture Alex’s expected behavior before changing the model.

**Files:**
- Modify: `tests/test_simulation_core.py`

**Test behavior:**

Given default scenario vs. `medizinstudienplaetze` reduced by 50%, over 15 years:

- physician supply should not crash immediately in years 1–5;
- from roughly year 6 onward, the gap vs baseline should widen;
- by year 15, doctors per 100k should be materially lower than baseline;
- burnout should not significantly improve unless an explicit adaptation mechanism explains it;
- output should expose a causal trace explaining the lag.

**Acceptance criteria:**

- Red test fails on current model if the crash is too weak or burnout improves without explanation.
- Green implementation must make the delayed pipeline effect visible and explainable.

### Task 2: Make the physician pipeline cohort-based and lag-explicit

**Objective:** Replace the current coarse `pipeline_buffer` behavior with a clearer cohort pipeline.

**Files:**
- Modify: `simulation_core.py`
- Test: `tests/test_simulation_core.py`

**Implementation direction:**

- Represent student cohorts by years until graduation/licensure.
- Add parameters for:
  - study places,
  - dropout rate,
  - graduation lag,
  - practice-entry share,
  - specialist lag,
  - retirement rate,
  - migration inflow,
  - part-time/FTE conversion.
- When study places are halved, cohorts entering after year 0 should be lower; graduates begin dropping after ~6 years; specialist/capacity effect continues into years 11–13.
- Output both headcount and effective capacity/FTE, not only headcount.

### Task 3: Correct burnout/workload coupling

**Objective:** Make burnout respond plausibly to capacity shortage, waiting times, workload, and adaptation pressure.

**Files:**
- Modify: `simulation_core.py`
- Test: `tests/test_simulation_core.py`

**Implementation direction:**

Burnout should depend on:

- demand / effective physician capacity;
- working hours;
- waiting-time pressure;
- shortage severity;
- compensating mechanisms such as telemedicine/delegation;
- delayed recovery rather than instant reset each year.

Add a burnout state equation such as:

```python
burnout_next = burnout_prev + pressure_increase - relief_from_adaptation - recovery
```

Do not fully recompute burnout from scratch every year; keep inertia.

**Acceptance criteria:**

- If doctors fall and no strong adaptation compensates, burnout rises.
- If burnout falls despite doctor shortage, causal trace must name the compensating mechanism and quantify its relief.

### Task 4: Add adaptation mechanism registry

**Objective:** Make adaptation mechanisms explicit and inspectable.

**Files:**
- Create: `adaptation_mechanisms.py`
- Modify: `simulation_core.py`
- Modify: `api.py`
- Test: `tests/test_adaptation_mechanisms.py`

**Implementation direction:**

Add registry entries for at least:

1. physician shortage → telemedicine adoption;
2. physician shortage → immigration recruitment;
3. physician shortage → working-hour pressure;
4. physician shortage → delegation/substitution;
5. GKV deficit → contribution/subsidy/benefit cuts;
6. benefit cut → deferred morbidity and later cost/outcome risk;
7. DRG/payment reform → hospital volume incentive/cost/capacity changes.

Each event emitted during simulation should include:

- year,
- trigger value,
- mechanism id,
- effect direction,
- affected KPIs,
- strength,
- caveat.

### Task 5: Add scenario intervention taxonomy

**Objective:** Allow broader policy levers beyond current sliders.

**Files:**
- Create: `scenario_interventions.py`
- Modify: `api.py`
- Modify: `app.py`
- Test: `tests/test_scenario_interventions.py`

**Initial intervention types:**

- medical study place change;
- DRG/fallpauschale reform;
- GKV benefit cut/addition;
- screening removal/addition;
- telemedicine/digital substitution;
- delegation/scope-of-practice;
- contribution/subsidy reform;
- hospital capacity/payment reform.

Each intervention maps to existing parameters where possible and marks missing model hooks where not possible.

### Task 6: Add free-text scenario parser as proposal, not direct mutation

**Objective:** Let Alex type broad policy changes without unsafe hidden model changes.

**Files:**
- Create: `scenario_text_parser.py`
- Modify: `api.py`
- Modify: `app.py`
- Test: `tests/test_scenario_text_parser.py`

**Behavior:**

Input examples:

- “Fallpauschalen abschaffen und auf Vorhaltebudget umstellen”
- “Hautkrebs-Screening aus GKV streichen”
- “Medizinstudienplätze halbieren”

Parser output:

```python
{
    "status": "proposal_needs_review",
    "recognized_interventions": [...],
    "mapped_parameters": [...],
    "missing_model_hooks": [...],
    "assumptions_to_confirm": [...],
    "preview_explanation": "...",
}
```

Guardrail: free text cannot silently change the model. The user must approve mapped changes.

### Task 7: Add payment reform model hooks

**Objective:** Support “away from DRG/fallpauschale” scenarios.

**Files:**
- Modify: `simulation_core.py`
- Modify: `parameter_registry.py`
- Modify: `data_sources.py`
- Test: `tests/test_payment_reform.py`

**New parameters:**

- `payment_drg_weight` / `fallpauschalen_anteil`;
- `vorhaltebudget_anteil`;
- `volume_incentive_strength`;
- `hospital_efficiency_pressure`;
- `avoidable_admission_reduction`;
- `hospital_financial_stress`.

**Model behavior:**

- Lower DRG weight may reduce volume incentives and some expenditure growth.
- It may increase budget rigidity/capacity stress depending on implementation.
- Output must distinguish cost relief, capacity risk, quality/outcome uncertainty.

### Task 8: Add benefit coverage / screening model hooks

**Objective:** Support scenarios like “Hautkrebs-Screening aus GKV streichen.”

**Files:**
- Modify: `simulation_core.py`
- Modify: `parameter_registry.py`
- Test: `tests/test_benefit_coverage.py`

**New parameters:**

- `gkv_benefit_generosity_index`;
- `screening_coverage_index`;
- `out_of_pocket_shift_index`;
- `delayed_diagnosis_risk`;
- `unmet_need_index`.

**Model behavior:**

- Short-term GKV spending may fall.
- Out-of-pocket burden and unmet need may rise.
- Some morbidity/mortality/cost effects should appear with delay.
- Output must flag evidence uncertainty and disease-specific simplification.

### Task 9: Add causal result packet

**Objective:** Replace vague result text with a structured explanation packet.

**Files:**
- Create: `result_causality.py`
- Modify: `api.py`
- Modify: `app.py`
- Test: `tests/test_result_causality.py`

**Packet fields:**

```python
{
    "headline": "Was kam heraus?",
    "changed_inputs": [...],
    "top_kpi_movements": [...],
    "why_these_outputs": [...],
    "adaptation_mechanisms_triggered": [...],
    "timeline": [...],
    "counterintuitive_findings": [...],
    "confidence_and_evidence": [...],
    "what_to_check_next": [...],
}
```

For each KPI movement include:

- start/end value;
- year/window of largest movement;
- direction;
- effect strength;
- related changed input;
- related adaptation events;
- caveat.

### Task 10: Add counterintuitive-result detector

**Objective:** Catch outputs like “medical study places halved, burnout falls.”

**Files:**
- Modify: `result_causality.py`
- Test: `tests/test_result_causality.py`

**Rules:**

Detect patterns such as:

- physician supply down but burnout down;
- benefit cuts reduce spending with no unmet-need/morbidity caveat;
- telemedicine up but waiting time unchanged and no adoption caveat;
- GKV spending down but patient burden/outcomes unmentioned;
- prevention up but immediate huge savings.

Output should say:

- “This is counterintuitive.”
- “The model explanation is …”
- “If this is not intended, inspect/change mechanism X.”

### Task 11: Redesign result UI around causal packet

**Objective:** Make the result page answer Alex’s exact questions first.

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_explanations.py`

**New order:**

1. **Kurzantwort: Was ist rausgekommen?**
2. **Was hast du geändert?**
3. **Warum kam dieses Ergebnis zustande?**
4. **Welche Anpassungsmechanismen wurden ausgelöst?**
5. **Wann im Zeitraum passiert es?**
6. **Was ist kontraintuitiv oder unsicher?**
7. **Welche Annahmen/Evidenz tragen das?**
8. **Welche Stellschraube solltest du als nächstes prüfen?**

### Task 12: Evidence/source policy for model coefficients

**Objective:** Keep the model broad without pretending every mechanism is perfectly sourced.

**Files:**
- Create/Modify: `docs/SIMULATION_EVIDENCE_POLICY.md`
- Modify: `parameter_registry.py`
- Test: `tests/test_registries.py`

**Policy:**

Do not restrict only to “good studies,” because policy simulations also need institutional reports, administrative data, legal rules, and expert assumptions. Instead classify every coefficient as:

- A: official German administrative/statistical source;
- B: German institutional/peer-reviewed evidence;
- C: international/OECD/WHO/Eurostat transferable evidence;
- D: proxy/comparable-country/mechanism literature;
- E: explicit expert/model assumption.

The result output must show this grade and caveat. Users can filter later by “only A/B assumptions,” but default simulation can include lower-grade assumptions if visibly labelled.

### Task 13: Add “spectacular but plausible” stress mode

**Objective:** Let scenarios show strong adaptation dynamics without overclaiming baseline mode.

**Files:**
- Modify: `simulation_core.py`
- Modify: `app.py`
- Test: `tests/test_simulation_core.py`

Add a scenario setting:

- `adaptation_intensity = conservative | expected | stress`

Meaning:

- conservative: weaker feedbacks;
- expected: default;
- stress: stronger response loops, stronger non-linearities, more visible crashes/adaptations.

Guardrail: stress mode is not “more true”; it is a sensitivity/stress-test lens.

### Task 14: API surfacing

**Objective:** Agents and UI should get the same explanation, not duplicate logic.

**Files:**
- Modify: `api.py`
- Test: `tests/test_api.py`

Expose:

- `/scenario-text/parse`;
- `/interventions/catalog`;
- `/adaptation-mechanisms/catalog`;
- in `/simulate`: `causal_result_packet`, `adaptation_events`, `counterintuitive_findings`.

### Task 15: Verification and release

Run:

```bash
cd /opt/data/projects/github/SimMed
. /opt/data/projects/health_simulation_app/source/.venv/bin/activate
python -m pytest -q
python -m py_compile simulation_core.py app.py api.py result_causality.py adaptation_mechanisms.py scenario_interventions.py scenario_text_parser.py
python - <<'PY'
from simulation_core import get_default_params, run_simulation
p = get_default_params()
p['medizinstudienplaetze'] = p['medizinstudienplaetze'] * 0.5
df, reg = run_simulation(p, n_runs=300, n_years=15, base_seed=42)
print(df[df['jahr'].isin([2026, 2032, 2041])][['jahr','aerzte_pro_100k_mean','burnout_rate_mean','telemedizin_rate_mean','wartezeit_fa_mean']])
PY
```

Acceptance:

- tests pass;
- the 15-year med-study-place scenario shows lagged physician/capacity pressure or explicitly explains why not;
- burnout cannot silently improve under shortage without a named compensating mechanism;
- result page shows a causal packet, not vague prose;
- free-text proposals are parsed but not directly applied without review.

---

## 5. Immediate next implementation order

1. Test and fix medical study-place lag/crash behavior.
2. Add explicit adaptation mechanism trace.
3. Add causal result packet.
4. Redesign result UI to render causal packet first.
5. Add free-text parser as proposal-only.
6. Add DRG/payment and GKV benefit/screening policy hooks.
7. Add evidence/source policy filtering and labels.

This order fixes the trust problem first: the model must produce plausible dynamics and explain them before adding many new knobs.


## 8. Heartbeat implementation update — causal packet/API and delayed training-pressure regression

Implemented safe slice:

- `result_causality.py` now returns `story_sections` as a structured sequential German explanation for UI/API: Output → changed inputs → mechanisms → adaptation → counterintuitive checks → evidence/assumptions.
- `/simulate` now embeds `causal_result_packet`, generated from the run's yearly aggregate summary, so agent/API clients get the same answer-first result layer as Streamlit.
- `simulation_core.run_scenario(...)` now returns `annual_summary` to support causal packets without re-running simulations in API code.
- `render_dashboard(...)` now renders the causal overview before the older narrative/checkpoint/KPI/detail layers.
- A regression test now captures Alex's medical-study-place-halving expectation: year 1 should not crash immediately, year 6 should show delayed capacity pressure, final waiting time should be worse than start, and burnout must not silently improve under the shortage scenario.
- Model change is deliberately narrow: halving study places adds an explicit delayed `pipeline_pressure` from year 6 onward. It increases waiting-time pressure and sets a burnout floor unless visible adaptation mechanisms later compensate. This is labeled in code as a SimMed assumption, not an official forecast.

Next safe slices:

1. Replace the large KPI grid with a compact relevant-KPI renderer driven only by `causal_result_packet['relevant_kpis']`, leaving old KPI details behind an expander.
2. Expand the causal packet with year-window traces (`0–5`, `6–10`, `11–15`) so the free-text story can say exactly when the delayed crash begins and worsens.
3. Extract adaptation mechanisms into a small registry rather than keeping all mechanism text inside `result_causality.py` and `simulation_core.py`.
