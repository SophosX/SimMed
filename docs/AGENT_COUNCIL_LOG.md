# Agent Council Log

This file records the structured multi-agent reasoning used to build SimMed.

Purpose:

- keep the Project Manager, Designer, Creative Agent, Political Health-System Strategist, Evidence/Domain Agent, Implementation Agents, and Integrator aligned
- make each heartbeat nachvollziehbar for future agents
- preserve why decisions were made, not only what changed
- surface important questions to Alex instead of silently choosing product direction

## How to use this log

Every meaningful heartbeat should append a short entry.

Entries should be concise but structured:

```text
## YYYY-MM-DD HH:MM Europe/Berlin — Heartbeat N

### Context
What changed since the previous entry? What files/modules are relevant?

### Project Manager
Priority, risk, next 1-3 tasks.

### Designer / UX
Observation about usability, onboarding, information hierarchy, or visual design.

### Creative Agent
One unusual/product-relevant idea and a short fit discussion.

### Political Health-System Strategist
Political realism, stakeholder incentives, veto players, framing, implementation feasibility.

### Evidence / Domain
Source/provenance/model-validity concerns.

### Integrator Decision
What will be accepted now, deferred, rejected, or escalated to Alex?

### Question to Alex
Only if an important decision is needed. Include concrete options/tradeoffs.

### Verification / Git
Tests, commit hash, push status, artifact path.
```

## 2026-04-29 14:30 Europe/Berlin — Council Log Initialized

### Context
Alex requested an explicit Agent Council Log so future heartbeat runs and agent roles can understand what was discussed and build on prior reasoning. Existing roles are documented in `docs/AGENT_WORKFLOW.md` and summarized in `README.md`.

### Project Manager
Priority: make the autonomous development process auditable before adding more complex app features.
Risk: without a persistent council log, heartbeat reports disappear into chat context and later agents may repeat debates or miss Alex's preferences.
Next tasks:
1. Add this persistent council log.
2. Update the heartbeat prompt to append future council entries.
3. Keep entries concise enough to remain maintainable.

### Designer / UX
A visible council log also improves trust for collaborators reading the repository: they can see that SimMed is not built by random autonomous edits, but by a structured review process.

### Creative Agent
Idea: later expose a simplified “Why did SimMed choose this next step?” timeline inside the app or project docs. Fit: useful for transparency, but not urgent for the UI; keep it as a docs-only process first.

### Political Health-System Strategist
For a politically sensitive health-system simulator, auditability is crucial. Users and stakeholders will care not only about outputs, but about who/what perspective shaped the model. The log should separate political feasibility analysis from advocacy.

### Evidence / Domain
Council entries should not replace source/provenance documentation. Model parameters still belong in `parameter_registry.py`, source routes in `data_sources.py`, and source policy in `docs/SOURCE_PROVENANCE_POLICY.md`.

### Integrator Decision
Accepted: create `docs/AGENT_COUNCIL_LOG.md` and require future heartbeats to append structured entries when meaningful work or decisions occur.
Deferred: app-facing visualization of the council process.

### Question to Alex
No immediate decision required; Alex already confirmed this log is desired.

### Verification / Git
Pending at creation time: tests, zip refresh, commit, push.


## 2026-04-29 15:29 Europe/Berlin — Heartbeat: Feasibility Layer Planning

### Context
Reviewed `README.md`, `docs/AGENT_WORKFLOW.md`, `docs/AGENT_COUNCIL_LOG.md`, and `app.py`. Added a docs-only implementation plan for a guided scenario builder and a new political feasibility layer design note; no simulation behavior changed.

### Project Manager
Priority: improve newcomer comprehension and preserve strategic/political interpretation boundaries before adding more UI/features. Risk: if feasibility is mixed into numeric outputs too early, SimMed may appear partisan or opaque. Next tasks: (1) implement registry-backed UI caveat helpers, (2) add API/docs examples for scenario manifests, (3) strengthen official-source provenance for weak parameters.

### Designer / UX
The Streamlit UI still contains many controls and hard-coded assumptions; a guided scenario builder should put caveats and provenance directly next to the policy lever so non-technical users understand delayed effects before reading charts.

### Creative Agent
Idea: add a “Reform Radar” explainer panel that shows stakeholder friction and implementation lag as a separate narrative overlay. Fit: improves understanding and motivation; credible if separated from model outputs; avoids unserious gamification if framed as interpretation; feasible as docs/UI metadata first; explainable to newcomers; Alex should decide before it becomes a score.

### Political Health-System Strategist
Political feasibility should be treated as a power/institution layer: BMG can propose, but Länder, KVen/KBV, DKG, GKV-Spitzenverband, BÄK, medical faculties, and budget actors can delay, reshape, or block implementation. Public institutional analysis is useful, but hidden political weights would be risky without a clear product decision.

### Evidence / Domain
No new numeric assumptions were added. The political feasibility document explicitly keeps assumptions out of `simulation_core.py` and requires labeling/citing feasibility claims later.

### Integrator Decision
Accepted safe documentation changes: `docs/plans/2026-04-29-guided-scenario-builder.md`, `docs/POLITICAL_FEASIBILITY_LAYER.md`, and README policy notes. Deferred implementation of feasibility scoring and UI badges until Alex chooses product tone.

### Question to Alex
How should SimMed handle political feasibility long-term? Options: (1) neutral explainer notes only, (2) transparent decision-support rubric separated from health/economic outputs, (3) competition scoring dimension with anti-gaming controls.

### Verification / Git
`python3 -m pytest -q` passed (9 tests). `py_compile` passed for app/core/API/registry/provenance/tests. Zip refreshed at `/opt/data/cache/documents/health_simulation_app_updated.zip`. Synced to GitHub clone, committed as `300f92a`, and pushed to `main`.

## 2026-04-29 14:45 Europe/Berlin — Product Direction: Explanation Mode

### Context
Alex clarified the political explanation direction. He wants Option 2 implemented now and Option 3 later.

### Project Manager
Priority: build a clear transparent decision/feasibility rubric before adding a full strategy simulator. This creates the foundation for later strategy mode without overcomplicating the app immediately.

### Designer / UX
The app must explain results in plain language: why SimMed reached a conclusion, why a policy lever causes effects, and what assumptions are uncertain. Explanations should be visible in the platform, not hidden in docs only.

### Creative Agent
Future idea: turn causal chains into “effect cards” or a readable timeline, e.g. “Policy change → delayed workforce effect → access change → financial side-effect.” Fit: strong, because it helps users understand without making the app unserious.

### Political Health-System Strategist
Accepted direction: transparent decision rubric now. Later, strategy mode should add sequencing, coalitions, veto players, framing, compensation, and legislative timing. This should remain politically realistic but not partisan.

### Evidence / Domain
Explanations must cite assumptions and uncertainty, not just tell stories. Parameter provenance and caveats still belong in the registries and source docs.

### Integrator Decision
Create `docs/PRODUCT_DIRECTION.md` to record: Option 2 now, Option 3 strategy mode later, and clear explanation quality as a platform requirement.

### Question to Alex
No open question: Alex decided Option 2 now and Option 3 later.

### Verification / Git
Pending: tests, zip refresh, commit, push.
