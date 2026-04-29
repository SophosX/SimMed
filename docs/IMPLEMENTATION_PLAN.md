# SimMed Platform Implementation Plan

> For Hermes: use subagent-driven-development for larger follow-up changes.

Goal: Turn the current single-file Streamlit simulator into a serious, evidence-backed, agent-accessible platform for German health-system simulations and competition-style scenario design.

Architecture: Keep the Streamlit prototype usable, but introduce a modular core: parameter registry, source/provenance registry, simulation engine, REST/OpenAPI layer, MCP/agent layer, social evidence connectors, and leaderboard/scenario storage. Every parameter must carry source, unit, confidence, date, uncertainty range, and caveats.

Tech stack: Python, Streamlit, Pandas/Numpy/Scipy, Plotly, optional FastAPI/OpenAPI, SQLite/Postgres, Pydantic, pytest, SALib later for sensitivity analysis.

## Phase 0: Stabilize current prototype

1. Add requirements.txt and basic tests.
2. Add a parameter provenance registry without breaking Streamlit.
3. Add data-source registry for authoritative German/EU sources.
4. Add documentation for model assumptions, limitations and data source quality.
5. Add a low-risk API wrapper that can run predefined scenarios from agents.

## Phase 1: Credible scientific MVP

Modules:
- demographics by age/cohort instead of a single aging multiplier
- physician workforce pipeline with delayed effects: study places -> graduates after ~6 years -> specialists after ~11-13 years
- GKV finance with contributors, pensioners, wages, subsidies, morbidity-weighted expenditure
- demand vs realized utilization vs unmet need
- prevention and digitalization as delayed, uncertain effects, not instant savings
- uncertainty distributions and scenario ranges
- parameter evidence scoring A-E

Priority scenario:
- Reduce or increase medical study places from a chosen year and show delayed long-term impact on physician FTE, access, waiting-time proxy, unmet need, GKV costs and contribution pressure.

## Phase 2: Data ingestion layer

Build source connectors for:
- Destatis GENESIS / Regionaldatenbank
- Eurostat
- BMG / GBE-Bund
- RKI
- Bundesärztekammer
- KBV / Zi
- G-BA / IQTIG
- InEK / Krankenhausverzeichnis
- GKV-Spitzenverband / BAS / PKV-Verband
- HRK / Destatis Hochschulstatistik / Stiftung Hochschulzulassung
- BAMF / Destatis migration
- gematik / BfArM DiGA

Store raw ingests immutable with retrieval timestamp, source URL, license/citation, geography, unit, denominator and transformation code.

## Phase 3: Agent platform

Expose:
- REST/OpenAPI endpoints: list parameters, run scenario, compare scenarios, get provenance, submit competition scenario
- MCP server for agent-native access
- scenario manifests as JSON with model version, data vintage, parameter changes, seed and scoring rubric

Agent permissions:
- read-only public data by default
- explicit write scope for creating scenarios
- rate limits and budget limits for simulation runs

## Phase 4: Social evidence and game layer

Integrations:
- Brave Search: web evidence discovery
- xAI/Grok/X search: social/news/X context
- Reddit API: community sentiment and policy discussions
- Discord/Telegram: community notifications and submission workflows
- X/LinkedIn later for social sharing

Competition:
- users submit policy bundles under budget and constraints
- score on multi-objective rubric: health outcomes, equity, access, financial sustainability, robustness, implementation realism
- hidden stress tests to prevent overfitting
- public reproducibility manifest and leaderboard
- moderation, anti-spam, anti-collusion and provenance requirements

## Phase 5: Advanced modeling

Only after MVP calibration:
- regional model by Bundesland/planning area
- specialty-specific workforce
- hospital network/capacity model
- disease-specific progression
- agent-based/microsimulation for heterogeneity and equity questions

## Immediate tasks implemented now

- Create source registry and parameter registry modules.
- Add tests validating provenance and source metadata.
- Add docs for credible parameters and architecture.
- Extract UI-independent simulation_core.py and agent-facing FastAPI wrapper.
- Add reproducible scenario manifests (`build_scenario_manifest`, `POST /scenario-manifest`) with model version, seed, run bounds, changed-parameter provenance, scenario_id and core model caveats.
- Package an updated zip for Alex.
