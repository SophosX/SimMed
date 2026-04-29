# Guided Scenario Builder Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a low-risk guided scenario builder to the Streamlit UI so newcomers can understand what they are changing, why delayed effects matter, and which caveats/provenance apply before running a simulation.

**Architecture:** Keep `simulation_core.py` as the only simulation engine. Add lightweight UI helper functions in `app.py` first; if the UI grows, extract them into `ui_guidance.py`. Reuse metadata from `parameter_registry.py` rather than duplicating labels, ranges, evidence grades, caveats, or source IDs.

**Tech Stack:** Python, Streamlit, existing `parameter_registry.py`, pytest/py_compile verification.

---

### Task 1: Add registry-backed scenario guide helper

**Objective:** Create a small helper that turns selected parameter keys into newcomer-friendly guidance text using existing registry metadata.

**Files:**
- Modify: `app.py`
- Test: compile-only for this task unless extracted into a pure helper module

**Step 1: Locate existing sidebar/slider construction**

Run:
```bash
cd /opt/data/projects/health_simulation_app/source
python3 - <<'PY'
from pathlib import Path
text = Path('app.py').read_text()
for needle in ['st.sidebar', 'slider', 'parameter_registry']:
    print(needle, text.find(needle))
PY
```
Expected: positions for existing UI controls.

**Step 2: Add imports without changing model behavior**

In `app.py`, add:
```python
try:
    from parameter_registry import PARAMETER_REGISTRY
except ImportError:
    PARAMETER_REGISTRY = {}
```

**Step 3: Add helper near UI functions**

```python
def format_parameter_guidance(parameter_key: str) -> str:
    """Return concise UI guidance for a parameter using provenance metadata."""
    spec = PARAMETER_REGISTRY.get(parameter_key)
    if spec is None:
        return "Keine Registry-Metadaten verfügbar — Annahme prüfen."
    sources = ", ".join(spec.source_ids) if spec.source_ids else "keine Quelle"
    return (
        f"**{spec.label}** ({spec.unit})  \n"
        f"Standard: `{spec.default}`; plausibler Bereich: `{spec.plausible_min}`–`{spec.plausible_max}`.  \n"
        f"Evidenzgrad: **{spec.evidence_grade}**; Quellen: `{sources}`.  \n"
        f"Caveat: {spec.caveat}"
    )
```

**Step 4: Run compile check**

Run:
```bash
. .venv/bin/activate
python3 -m py_compile app.py parameter_registry.py
```
Expected: no output / exit 0.

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add registry-backed scenario guidance helper"
```

---

### Task 2: Add a newcomer guidance expander to the Streamlit UI

**Objective:** Show selected caveats and source metadata near scenario controls without changing simulation outputs.

**Files:**
- Modify: `app.py`

**Step 1: Insert expander near scenario inputs**

Use the existing slider keys. Example for medical study places:
```python
with st.expander("Was bedeutet diese Annahme?", expanded=False):
    st.markdown(format_parameter_guidance("medizinstudienplaetze"))
    st.info(
        "Wichtig: weniger Studienplätze wirken nicht sofort auf die Versorgung. "
        "Erst nach ca. 6 Jahren beginnt der Absolventen-Effekt; fachärztliche "
        "Kapazität wird typischerweise erst nach 11–13 Jahren deutlich beeinflusst."
    )
```

**Step 2: Run app compile check**

Run:
```bash
. .venv/bin/activate
python3 -m py_compile app.py
```
Expected: pass.

**Step 3: Optional smoke import**

Run:
```bash
. .venv/bin/activate
python3 - <<'PY'
import app
print('OK app import')
PY
```
Expected: import succeeds. If Streamlit import side effects make this noisy, rely on py_compile.

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: show scenario caveats in Streamlit UI"
```

---

### Task 3: Add a short README note for the guided UI pattern

**Objective:** Explain to future contributors that UI controls should surface provenance/caveats from the registry.

**Files:**
- Modify: `README.md`

**Step 1: Add note under Current development policy**

```markdown
- UI controls for policy levers should show registry-backed caveats/provenance near the control, especially when effects are delayed or politically sensitive.
```

**Step 2: Verify docs and tests**

Run:
```bash
. .venv/bin/activate
python3 -m pytest -q
python3 -m py_compile app.py data_sources.py parameter_registry.py provenance.py api.py simulation_core.py tests/test_registries.py tests/test_provenance.py tests/test_simulation_core.py
```
Expected: all tests pass and compile succeeds.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document registry-backed UI guidance policy"
```

---

### Task 4: Keep political feasibility as an explanation layer, not a hidden model assumption

**Objective:** Add political feasibility text only as clearly labeled interpretation until Alex decides how strongly SimMed should position itself.

**Files:**
- Create: `docs/POLITICAL_FEASIBILITY_LAYER.md`

**Step 1: Create a short design note**

```markdown
# Political Feasibility Layer

SimMed should distinguish numeric model outputs from political feasibility interpretation.

Initial rule:
- model outputs stay in `simulation_core.py`
- public institutional assumptions and stakeholder caveats are documented in docs/ and eventually surfaced in UI/API as explanation metadata
- no partisan recommendations are encoded as hidden scoring weights without an explicit product decision
```

**Step 2: Verify no model behavior changed**

Run:
```bash
. .venv/bin/activate
python3 -m pytest -q
```
Expected: existing tests still pass.

**Step 3: Commit**

```bash
git add docs/POLITICAL_FEASIBILITY_LAYER.md
git commit -m "docs: plan political feasibility explanation layer"
```
