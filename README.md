# SimMed Deutschland 2040 – Development Notes

This repository currently contains a Streamlit prototype in app.py.

## Run locally

python3 -m pip install -r requirements.txt
streamlit run app.py

## Test

python3 -m pytest -q

## New credibility layer

The following modules were added:

- simulation_core.py: UI-independent Monte-Carlo simulation core with scenario runner for API/agent use.
- api.py: FastAPI wrapper around the simulation core plus parameter/source discovery endpoints.
  - `POST /scenario-manifest` returns a reproducibility manifest before execution (model version, seed, run bounds, changed-parameter provenance, scenario_id, caveats).
  - `POST /simulate` returns the same manifest embedded with the KPI summary so agent runs are traceable.
- data_sources.py: authoritative data-source registry for German/EU health-system data.
- parameter_registry.py: parameter metadata with source ids, units, plausible ranges, evidence grade, uncertainty and caveats.
- docs/IMPLEMENTATION_PLAN.md: roadmap from prototype to serious platform.
- docs/SOURCE_PROVENANCE_POLICY.md: mandatory policy for documenting which sources are used, how they are accessed, how raw data is logged, and which caveats must stay visible.

## Documentation rule

Every serious parameter and every data import must be auditable. Do not add important constants without documenting source id, unit, vintage/retrieval date, uncertainty treatment and caveat in parameter_registry.py or a future ingest log.

## Evidence grades

A = official German administrative/statistical data
B = German institutional or peer-reviewed evidence, or strong domain source
C = international source with German data such as Eurostat/OECD/WHO
D = comparable-country proxy or meta-analysis
E = expert assumption / placeholder

The target standard is: every simulation slider and default value must be linked to at least one source id and have an uncertainty treatment.
