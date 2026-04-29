# AI in Healthcare Impact Module

Date: 2026-04-29
Status: design/research plan before implementation

## Why this module exists

Alex raised a central point: it is not obvious whether software AI / clinical AI solutions actually improve patient care. Many tools promise productivity or better outcomes, but evidence varies strongly by use case, workflow integration, study design and endpoint.

SimMed should therefore not treat AI as a generic productivity multiplier. It should help users ask:

- Which AI implementation is being discussed?
- What outcome is claimed to improve?
- Is the evidence about patient outcomes, clinician workload, process speed, billing, or only technical accuracy?
- What are the risks, implementation costs and adoption barriers?
- What would plausibly happen if implemented in the German health system?

## Product framing

This module is adjacent to the core health-system simulation, but important enough to become a dedicated policy domain.

Recommended label:

**KI im Gesundheitswesen: Nutzen, Risiken und Evidenz**

Not: “AI improves healthcare”.

The module should show uncertainty first.

## AI use-case categories

Start with these structured categories:

1. Clinical decision support
   - diagnosis suggestions
   - treatment recommendations
   - risk scores
   - alerting

2. Documentation / ambient AI scribes
   - automatic note generation
   - coding/billing support
   - reduced after-hours documentation
   - possible upcoding/billing effects

3. Radiology / pathology AI
   - triage
   - detection support
   - workflow prioritization
   - false positives/false negatives

4. Patient triage and chatbots
   - symptom checkers
   - appointment routing
   - digital front doors
   - safety and equity concerns

5. Remote monitoring / chronic care
   - early warning
   - escalation pathways
   - adherence support
   - alert fatigue

6. Operational AI
   - scheduling
   - bed/capacity planning
   - OR utilization
   - workforce allocation

7. Administrative automation
   - prior authorization
   - claims processing
   - referral management
   - documentation burden

## Evidence dimensions to store

Each AI intervention should be stored as structured evidence, not only prose:

- id
- name
- category
- clinical setting
- target users
- target problem
- implementation type
- comparator
- measured outcomes
- outcome type:
  - patient outcome
  - process outcome
  - clinician workload
  - cost/billing
  - safety/quality
  - equity/access
  - technical benchmark only
- study design:
  - RCT
  - prospective trial
  - silent trial
  - observational study
  - before/after
  - systematic review
  - vendor claim
  - expert assumption
- evidence grade A-E
- source URLs / citations
- population and country
- transferability to Germany
- implementation requirements
- risks / failure modes
- adoption lag
- expected affected SimMed parameters
- caveat text

## Research pipeline

Use multiple evidence channels:

### 1. Academic / institutional web search

Use Brave/Grok web search for:

- systematic reviews
- randomized/prospective trials
- JAMA / NEJM AI / Lancet Digital Health / BMJ / Nature Medicine
- WHO / OECD / EU / national evaluations
- health technology assessment reports

Initial Grok web search surfaced examples around:

- ambient AI scribes and documentation burden
- clinical documentation scoping/systematic reviews
- AI voice-to-text documentation reviews
- AI radiology triage studies
- AI clinical decision support outcome trials
- adoption and device-usage studies in NEJM AI

### 2. X/Grok social/news scan

Use Grok/X search for current debate and emerging claims, but treat X only as signal discovery, not evidence.

Initial X scan showed claims/posts about:

- ambient scribes reducing burnout/documentation burden
- radiology AI triage trials
- stroke decision-support outcome claims
- criticism of AI diagnostic performance in difficult radiology cases

All X claims must be traced back to original papers/reports before entering the evidence database.

### 3. YouTube/transcript review

Use YouTube transcripts for expert discussions and implementation context, not primary evidence.

Candidate sources/searches:

- Stanford AI in Healthcare video series
- Eric Topol talks/interviews on AI in healthcare
- NEJM AI / medical AI talks
- Mayo Clinic / Stanford Medicine / UCSF / NHS / WHO talks
- health-system CIO/CMIO talks on ambient scribes, AI triage, documentation burden

Transcript extraction should store:

- video title
- URL
- speaker/organization
- transcript hash
- claims extracted
- whether each claim is expert opinion, cited evidence, or implementation anecdote
- linked original evidence if mentioned

YouTube content must not become model fact unless supported by cited evidence.

## Modeling approach

Do not model AI as one slider.

Create an AI adoption module with separate levers:

- adoption_rate by use-case
- workflow_integration_quality
- clinician_trust / acceptance
- regulatory_readiness
- data_interoperability
- upfront_cost
- maintenance_cost
- training_cost
- time_saved_per_encounter
- false_positive_rate / false_negative_risk where relevant
- alert_fatigue
- equity_risk
- patient_safety_risk
- implementation_lag

Expected affected pathways:

- clinician time and burnout
- documentation burden
- access/waiting time if capacity is freed
- diagnostic timeliness in narrow settings
- costs: upfront increase, possible long-term efficiency, possible billing increases
- patient outcomes only when evidence supports clinical effect
- equity/access could improve or worsen depending on deployment

## UI integration

### Learning page section

Add a dedicated explainer:

“KI im Gesundheitswesen: Was wissen wir wirklich?”

Explain:

- technical accuracy is not the same as patient benefit
- workflow integration matters
- many tools improve process outcomes before patient outcomes are proven
- benefits and harms differ by use case

### Scenario gallery

Add AI scenario cards later:

- “Ambient Scribes in Hausarztpraxen”
- “Radiologie-Triage bei knapper Befundkapazität”
- “KI-Triage / Digital Front Door”
- “AI Decision Support for chronic disease management”

Each card must show evidence status and caveat before simulation.

### Policy-Briefing

Add an AI evidence block when AI levers are changed:

- what AI tool type was assumed
- what evidence supports it
- outcome type: process vs patient outcome
- implementation lag
- risks and uncertainty
- German transferability

## Guardrails

- Never say “AI improves healthcare” globally.
- Always specify use case, setting, comparator and outcome.
- Separate technical performance from patient outcome.
- Separate process efficiency from clinical quality.
- Do not use YouTube/X as primary evidence; use them to discover arguments and sources.
- Label unsupported assumptions as evidence grade E.
- Add expert/human review before model-relevant AI effect sizes are accepted.

## First implementation slice recommendation

Do not change simulation equations yet.

Slice 1:

- Create `ai_healthcare_evidence.py` with structured intervention records and evidence categories.
- Add tests that every AI intervention has outcome_type, evidence_grade, caveat, transferability_to_germany and source_refs.
- Add plan/learning UI section that explains why AI impact is uncertain.
- No numeric effect on KPIs yet.

Slice 2:

- Add transcript ingestion workflow for YouTube expert videos and store claims as “expert/context notes,” not model facts.

Slice 3:

- Add AI scenario gallery cards with explicit evidence/caveat labels.

Slice 4:

- Only after evidence review, add exploratory simulation levers with evidence grade and wide uncertainty.

## Open question for Alex

Should the first AI module focus on:

1. Ambient scribes / documentation burden
   Practical, current, measurable via time/burnout/process outcomes.

2. Radiology / diagnostic AI
   More clinical, stronger safety implications, easier to overclaim.

3. AI triage / digital front door
   Highly relevant for access/waiting times, but evidence and safety are mixed.

Recommendation: start with ambient scribes because benefits are more plausibly measurable as workflow/time/burnout first, without pretending immediate patient-outcome improvement.
