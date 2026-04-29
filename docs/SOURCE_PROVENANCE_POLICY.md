# Source and Provenance Policy

This project must be controllable and auditable. Every serious simulation parameter, data import and model assumption should be traceable.

## Core rule

No important number should live only as an unexplained constant in code.

Every simulation parameter should have:

- parameter key
- human-readable label
- unit
- default value
- plausible min/max or scenario range
- source id(s)
- exact source name / authority
- source URL or access path
- retrieval date or source vintage
- evidence grade A-E
- uncertainty treatment
- transformation method if the raw value is converted
- caveats and known limitations

## Evidence grades

A = official German administrative/statistical data
Examples: Destatis, BMG, Bundesärztekammer, KBV, GKV-Schätzerkreis, BAS.

B = German institutional, scientific or high-quality domain source
Examples: RKI reports, Zi analyses, WIdO, IQTIG, peer-reviewed German studies.

C = international source with German data
Examples: Eurostat, OECD, WHO, IHME.

D = comparable-country proxy or meta-analysis
Used only when German evidence is unavailable.

E = explicit expert assumption / placeholder
Allowed only when visible in UI/docs and sensitivity-tested.

## Where provenance is stored

Current implementation:

- data_sources.py: registry of authoritative data sources and APIs/download routes.
- parameter_registry.py: registry of parameter metadata, source ids, uncertainty and caveats.
- docs/SOURCE_PROVENANCE_POLICY.md: this policy.
- docs/IMPLEMENTATION_PLAN.md: roadmap and architectural assumptions.

Future implementation:

- raw_data/: immutable raw downloads, never silently overwritten.
- data_catalog.sqlite or Postgres tables:
  - source_registry
  - raw_ingest_log
  - parameter_values
  - parameter_transformations
  - scenario_manifests
  - model_versions

## Required ingest log fields

For every external data pull:

- source_id
- source_name
- authority
- URL/API endpoint/download path
- query/table id if applicable
- retrieved_at timestamp
- source_period or reporting year
- file hash/content hash
- license/citation note
- raw file path
- parsing script or function
- output table/parameter keys
- errors/warnings

## Examples of preferred source mapping

- Population, births, mortality, migration: Destatis GENESIS / Regionaldatenbank.
- Physician stock, age, specialty: Bundesärztekammer Ärztestatistik.
- Ambulatory supply and planning: KBV / Zi.
- GKV finance: BMG, GKV-Spitzenverband, Bundesamt für Soziale Sicherung.
- Morbidity/public health: RKI, GBE-Bund, Zi, OECD/Eurostat as comparator.
- Hospitals/beds/cases: Destatis Krankenhausstatistik, InEK, G-BA/IQTIG.
- Medical education pipeline: HRK, Destatis Hochschulstatistik, Stiftung Hochschulzulassung.
- Migration: Destatis, BAMF, Eurostat.
- Digital health: gematik, BfArM DiGA.

## Modeling caveats that must remain visible

- Medical study places affect physician supply only after training delays: roughly 6+ years for graduates and 11-13+ years for specialists.
- Physician headcount is not capacity; FTE, specialty, part-time, age and region matter.
- Hospital beds are not effective capacity unless staffing is modeled.
- Prevention does not create instant global savings; effects are disease-specific, delayed and uncertain.
- Digitalization does not automatically reduce costs; adoption, workflow redesign, upfront investment and demand induction matter.
- Demand and utilization must be separated: low utilization can mean unmet need, not low demand.

## UI requirement

The app should eventually show for each parameter:

- source badge
- evidence grade
- uncertainty description
- caveat text
- link to raw source / ingest record

This is necessary so policy simulations are transparent rather than black-box forecasts.
