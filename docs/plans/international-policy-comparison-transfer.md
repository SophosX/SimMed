# International Policy Comparison and Transfer Logic

Date: 2026-04-29
Status: Product/evidence direction from Alex, to guide implementation

## Decision

SimMed should not only simulate isolated German parameter changes. A major use case is health-policy learning from other countries:

> What did other countries implement, what impact did it have there, and what could plausibly happen if a comparable reform were transferred to Germany?

This is central because health-policy debates often compare countries: waiting times, primary care, gatekeeping, digitalization, hospital structure, financing, workforce, rural access, prevention, and patient satisfaction.

## Product goal

Add an international comparison layer that helps users understand:

1. Which country/reform is being compared?
2. What problem did that country try to solve?
3. What exactly was implemented?
4. What measured impact was reported there?
5. How comparable is that country to Germany?
6. What would need to be adapted for Germany?
7. Which German model parameters/pathways should change?
8. What uncertainty remains?

## Important distinction

Do not treat foreign policy outcomes as directly transferable facts.

A reform can have different effects in Germany because of:

- different financing system
- federalism and self-governance structures
- GKV/PKV split
- physician practice ownership and ambulatory sector structure
- hospital planning by Länder
- workforce mix and professional roles
- digital infrastructure and data governance
- population age structure and morbidity
- political/legal feasibility
- baseline waiting times/access problems

Therefore the app should show:

Foreign evidence -> transfer assessment -> German scenario assumptions -> simulated German impact.

## Proposed UI concept

### Section: “Was machen andere Länder?”

For each policy area, show country cards:

- Country
- Reform/intervention
- Problem addressed
- Reported impact
- Evidence quality
- Similarity to Germany
- Transfer caveat
- Suggested German scenario lever(s)

Example policy areas:

- Primary care / GP gatekeeping
- Physician assistants / task shifting
- Telemedicine and digital front doors
- ePA / national health data infrastructure
- Hospital concentration / regional planning
- Prevention and chronic disease management
- Workforce training and migration
- Rural access incentives
- Payment reform / capitation / value-based care
- Waiting-time guarantees

### Section: “Auf Deutschland übertragen”

When user selects an international example, SimMed should not automatically assume the same effect. It should propose a German scenario translation:

- Which German parameters would change?
- By how much?
- Is the magnitude evidence-backed or exploratory?
- Which KPI pathways are expected to move?
- Which political/stakeholder barriers matter?

### Section: “Impact in Deutschland simulieren”

Then run the German model with those translated assumptions and compare:

- Germany reference projection
- Germany scenario with imported reform logic
- uncertainty/caveat
- related KPIs and political feasibility

## Evidence model for international reforms

Each international policy example should be a structured object:

- country
- policy_name
- implementation_period
- policy_area
- policy_description
- target_problem
- reported_outcomes
- source_ids
- evidence_grade
- effect_size_type
- comparability_to_germany
- transfer_adjustment
- suggested_parameter_changes
- caveats

## Comparability rubric

Score or label comparability in plain language:

- High: similar problem, similar institution, good data, plausible German lever
- Medium: useful signal but institutionally different
- Low: interesting idea, but Germany transfer is highly uncertain

Comparability dimensions:

1. Financing similarity
2. Provider structure similarity
3. Baseline problem similarity
4. Workforce similarity
5. Data/evidence strength
6. Legal/political transferability
7. Cultural/patient-behavior transferability

## Guardrails

- Do not say “Country X improved by 10%, therefore Germany improves by 10%.”
- Always show transfer caveat.
- Use international examples as evidence-informed scenario inputs, not as guaranteed predictions.
- Keep original sources visible.
- Separate measured foreign impact from SimMed’s German translation.
- For politically sensitive reforms, label stakeholder/political text as qualitative orientation, not prediction.

## Recommended implementation sequence

### Slice 1: Data structure only

Create an `international_reforms.py` module with a small curated set of placeholder/example reform records and no automatic model mutation.

### Slice 2: UI explainer page

Add a “Was machen andere Länder?” learning section that explains the transfer logic and shows reform cards.

### Slice 3: Transfer proposal helper

Add a helper that turns a selected reform into proposed German parameter changes, clearly marked as exploratory unless strongly sourced.

### Slice 4: Simulation integration

Allow users to apply a selected reform as a scenario preset, with confirmation and visible caveats.

### Slice 5: Evidence expansion

Research and add real sourced examples from countries and sources such as OECD, WHO/European Observatory, Eurostat, national health ministries, peer-reviewed studies, and institutional reports.

## Research/source priorities

- OECD Health Statistics and country health profiles
- European Observatory on Health Systems and Policies / HiT reports
- WHO Europe
- Eurostat health indicators
- Commonwealth Fund international comparisons
- national health ministry/evaluation reports
- peer-reviewed policy evaluations

## UX principle

The app should feel like a policy lab:

“Here is what Germany currently looks like. Here is what another country tried. Here is the evidence. Here is why it may or may not transfer. Here is the simulated German impact if we translate it carefully.”
