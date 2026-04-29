# Current Germany Baseline and Projection Sources

Date: 2026-04-29
Status: Product/evidence decision from Alex, to guide implementation

## Decision

The SimMed reference should not pretend that we know the true baseline of Germany in 2040.

Instead, the baseline should mean:

> Current Germany baseline: the best available current description of the German health system, then projected forward transparently to 2040 using documented demographic, economic, workforce, morbidity and health-system assumptions from reliable sources.

In the UI this should be explained in plain German:

- “Aktuelle Deutschland-Baseline” = current measured state as far as reliable data exists.
- “Projektion bis 2040” = scenario projection from that current baseline, not a guaranteed forecast.
- “Referenz-Szenario” = the default projection against which user changes are compared.

Recommended UI name:

> Deutschland-Baseline + Referenzprojektion bis 2040

Shorter labels can use:

- Deutschland-Baseline
- Referenzprojektion
- Standardpfad

## What must be sourced

The baseline needs evidence/provenance for at least these blocks:

1. Demography
   - current population
   - age structure where feasible
   - fertility
   - mortality/life expectancy
   - migration assumptions
   - preferred sources: Destatis population statistics and coordinated population projections, Eurostat where useful

2. Economy and financing
   - GDP / wage base proxies
   - income/wage growth assumptions
   - GKV/PKV shares
   - contribution rates
   - federal subsidies
   - health expenditure levels
   - preferred sources: Destatis, BMG, BAS, GKV-Spitzenverband, OECD/Eurostat for comparison

3. Workforce and capacity
   - physician stock
   - physician density
   - regional distribution
   - medical study places
   - retirement/age structure where feasible
   - preferred sources: Bundesärztekammer, KBV/Zi, Destatis higher education/HRK

4. Health status and demand
   - morbidity/chronic disease proxies
   - preventable mortality
   - age-related demand assumptions
   - preferred sources: RKI, GBE-Bund, OECD/Eurostat where relevant

5. Access and regional equity
   - waiting times where available
   - rural/urban access proxies
   - travel/access data if feasible
   - preferred sources: KBV, Zi Versorgungsatlas, BBSR/regional data where feasible

6. Digitalization and telemedicine
   - current adoption proxies
   - ePA/DiGA/telemedicine uptake where data exists
   - preferred sources: gematik, BfArM, BMG, KBV reports

## Projection principle

The app must separate three layers:

### Layer A: Measured current baseline

The most recent available current data. This should be shown with source, period and evidence grade.

### Layer B: External projection assumptions

Examples:

- Destatis population projections
- official/institutional projections where available
- OECD/Eurostat trend projections or comparable external statistics

These are not “truth”, but externally grounded projection inputs.

### Layer C: SimMed model assumptions

Where no good projection exists, SimMed uses explicit assumptions. These must be labeled as model assumptions and not presented as facts.

## User-facing explanation

Every default run should say something like:

“SimMed startet nicht mit einer erfundenen 2040-Welt. Es startet mit der aktuellen Deutschland-Baseline: dem heutigen Stand des Gesundheitssystems, soweit er über Datenquellen beschreibbar ist. Von dort wird ein Referenzpfad bis 2040 simuliert. Dieser Pfad ist keine amtliche Prognose, sondern ein transparenter Vergleichsstandard. Wenn du Parameter änderst, vergleicht SimMed dein Szenario gegen diesen Referenzpfad.”

## Implementation implications

1. Create a baseline/projection module, not just UI text.
2. Each baseline field should have:
   - value
   - unit
   - source_id
   - source period/vintage
   - evidence grade
   - whether it is current measurement, external projection, or SimMed assumption
   - caveat
3. The result screen should compare:
   - current measured baseline
   - reference projection
   - user scenario projection
4. KPI cards should avoid implying that “2040 baseline” is known.
5. The first implementation should create structure and a few high-value sourced examples, then expand source coverage iteratively.

## Open research/API work

Need to inspect and document practical access routes for:

- Destatis GENESIS/API for population and projections
- Eurostat dissemination API for demographic/economic indicators
- OECD data APIs if useful for health expenditure comparisons
- BMG/GBE-Bund tables for health indicators
- BÄK/KBV/Zi available downloadable reports or tables
- gematik/BfArM where digital health adoption data is accessible

## Guardrails

- Do not call the projected 2040 reference path “the baseline in 2040” without caveat.
- Say “Referenzprojektion” or “Standardpfad”, not “we know Germany 2040”.
- Separate current facts, external projections and model assumptions visibly.
- If a data source is not yet connected, label the value as placeholder/assumption rather than hiding it.
