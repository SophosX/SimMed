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
