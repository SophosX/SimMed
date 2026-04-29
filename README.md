# SimMed Deutschland 2040

SimMed is an experimental simulation platform for exploring long-term policy scenarios in the German health system.

The project started as a Streamlit prototype and is being turned into a more serious, evidence-backed platform with:

- a reusable Monte-Carlo simulation core
- transparent parameter provenance
- a human-facing Streamlit dashboard
- a FastAPI interface for AI agents and external tools
- reproducible scenario manifests
- a roadmap toward competition/leaderboard-style policy simulation

## What problem does SimMed try to solve?

Health-system policy decisions often have delayed, indirect, and uncertain effects. For example:

- reducing medical school places may not affect physician supply immediately, but can matter 6-13 years later
- telemedicine can improve access, but adoption and productivity effects are uncertain
- prevention may cost more in the short term and only improve outcomes later
- hospital beds are not real capacity if staff are missing
- GKV finances depend on income, contribution rates, demographics, morbidity, federal subsidies, and utilization

SimMed lets users change assumptions and policy levers, then simulate possible trajectories for access, workforce, outcomes, and financing.

Important: this is not a validated forecasting model yet. It is a transparent simulation framework under development. Assumptions must remain visible and auditable.

## Current status

The repository currently contains a working Python prototype with tests.

Main capabilities:

- Streamlit UI for interactive scenarios, including a newcomer-friendly “Lernen” page that explains the platform, model logic, political feasibility layer, and roadmap in plain language
- Monte-Carlo simulation over 5-30 years
- German health-system KPIs such as physician density, waiting times, GKV balance, health expenditure, life expectancy proxy, rural access index, and collapse-risk proxy
- parameter registry with evidence grades and caveats
- data-source registry for official German/EU sources
- FastAPI endpoints for agent-facing scenario runs
- scenario manifests with model version, seed, changed parameters, and caveats

## Repository structure

```text
.
├── app.py                         # Streamlit user interface
├── simulation_core.py             # UI-independent simulation engine
├── api.py                         # FastAPI wrapper for agents/tools
├── parameter_registry.py          # Parameter metadata, evidence grades, caveats
├── data_sources.py                # Authoritative source registry
├── provenance.py                  # Ingest records, SHA256 hashing, JSONL logs
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Test configuration
├── docs/
│   ├── IMPLEMENTATION_PLAN.md     # Roadmap from prototype to platform
│   ├── SOURCE_PROVENANCE_POLICY.md# Rules for sources and assumptions
│   ├── AGENT_WORKFLOW.md          # Multi-agent development workflow
│   ├── AGENT_COUNCIL_LOG.md       # Persistent structured reasoning log
│   └── PRODUCT_DIRECTION.md       # Product decisions: explanation mode, later strategy mode
└── tests/
    ├── test_provenance.py
    ├── test_registries.py
    └── test_simulation_core.py
```

## How the architecture fits together

```text
Streamlit UI (app.py)
        │
        ▼
Simulation Core (simulation_core.py)
        │
        ├── parameter metadata (parameter_registry.py)
        ├── source metadata (data_sources.py)
        ├── provenance logging (provenance.py)
        └── API wrapper (api.py)
```

Design principle: the simulation should not depend on Streamlit. The UI, API, tests, and future agent interfaces should all call the same core model.

## Quick start

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Run the Streamlit app:

```bash
streamlit run app.py
```

Run tests:

```bash
python3 -m pytest -q
```

Run a small scenario from Python:

```bash
python3 - <<'PY'
from simulation_core import run_scenario

result = run_scenario(
    {"medizinstudienplaetze": 9000},
    n_runs=20,
    n_years=15,
    seed=42,
)
print(result["scenario_id"])
print(result["final_year_summary"]["aerzte_pro_100k_mean"])
PY
```

Run the API locally:

```bash
uvicorn api:api --reload
```

Example API calls:

```bash
curl http://127.0.0.1:8000/parameters
curl http://127.0.0.1:8000/sources
curl -X POST http://127.0.0.1:8000/scenario-manifest \
  -H 'Content-Type: application/json' \
  -d '{"parameter_changes":{"medizinstudienplaetze":9000},"n_runs":100,"n_years":15,"seed":42}'
```

## Evidence grades

Every important parameter should be linked to one or more sources and assigned an evidence grade.

```text
A = official German administrative/statistical data
B = German institutional or peer-reviewed source, or strong domain evidence
C = international source with German data, e.g. Eurostat/OECD/WHO
D = comparable-country proxy or meta-analysis
E = expert assumption / placeholder
```

The target standard is: every simulation slider and default value should have a source id, unit, plausible range, uncertainty treatment, and caveat.

## Modeling caveats

Some core caveats are intentionally documented in code and scenario manifests:

- medical study places affect physician supply only after a delayed education/training pipeline
- physician headcount is not the same as effective capacity/FTE
- hospital beds are not capacity without staffing
- prevention effects are delayed and may raise short-term cost
- digitalization is not a flat cost reducer
- latent demand, realized utilization, and unmet need should be separated over time

## Multi-agent development workflow

SimMed may use several AI agents, but not all should push directly to `main`.

Recommended roles:

- Integrator/Maintainer: keeps `main` stable, runs tests, commits and pushes verified changes
- Project Manager Agent: reviews priorities, risks, backlog, and next steps
- Designer/UX Agent: improves usability, onboarding, and information hierarchy
- Creative Agent: proposes unusual but product-relevant ideas, then the team discusses whether they fit the app
- Political Health-System Strategist Agent: stress-tests scenarios for German health-policy realism, stakeholder incentives, veto players, and implementation feasibility
- Evidence/Domain Agent: checks assumptions, source quality, and provenance gaps
- Implementation Agent: implements small scoped tasks with tests

See `docs/AGENT_WORKFLOW.md` for the coordination model.

## Current development policy

- Keep `main` stable and tested.
- Prefer small commits.
- Do not add important constants without updating provenance/parameter documentation.
- Do not hide assumptions only in comments.
- Add or update tests for simulation-core and API changes.
- UI controls for policy levers should surface registry-backed caveats/provenance near the control, especially when effects are delayed or politically sensitive.
- Keep political feasibility interpretation clearly separated from numeric model outputs unless Alex explicitly decides to add feasibility scoring.
- Make user-facing explanations understandable for people who are not already inside the project.

## Roadmap

Near-term:

1. Improve README/onboarding and developer workflow.
2. Continue extracting model logic from Streamlit UI into `simulation_core.py`.
3. Expand scenario manifests and reproducibility metadata.
4. Add clearer UI explanations and a guided scenario builder.
5. Strengthen parameter provenance with official German/EU data sources.

Medium-term:

1. Add robust data-ingestion connectors.
2. Add richer API/OpenAPI documentation.
3. Add MCP or other agent-native access.
4. Add scenario comparison, saved scenarios, and exportable reports.
5. Add leaderboard/competition mechanics with anti-gaming controls.

## License / status

Research prototype under active development. Do not treat outputs as medical, legal, or policy advice without independent validation.
