# SimMed Agent Workflow

SimMed can benefit from multiple AI agents, but only if they have clear roles and do not all push directly to `main`.

## Recommended roles

### 1. Integrator / Maintainer Agent

Owner: Kvothe heartbeat.

Responsibilities:

- keep `main` stable
- run tests before every commit
- sync source into the GitHub clone
- commit and push verified increments
- summarize every heartbeat in Telegram
- decide whether proposed work is ready to merge

### 2. Product / Project Manager Agent

Responsibilities:

- review the current state every heartbeat or every few heartbeats
- maintain a short prioritized backlog
- translate vague goals into concrete tasks
- check whether work still serves the product goal: credible, evidence-backed German health-system simulation
- flag scope creep, missing documentation, and unclear assumptions

Outputs should be small and actionable:

- current priority
- why it matters
- next 1-3 tasks
- risks/blockers

### 3. Designer / UX Agent

Responsibilities:

- review the Streamlit interface and user journey
- propose UI structure, labels, visual hierarchy, explanatory text, and onboarding
- make the app understandable for non-technical users
- avoid cosmetic-only redesigns that do not improve decision-making

The designer agent should usually produce a design brief first, then implementation tasks.

### 4. Creative Agent

Responsibilities:

- propose surprising but product-relevant features, metaphors, interaction patterns, scenario ideas, visualizations, narrative hooks, and sharing/game mechanics
- challenge the team to make SimMed engaging without making it unserious
- explicitly mark ideas as low-risk, medium-risk, or speculative
- explain which user problem each idea solves

Creative ideas are not accepted automatically. They must be discussed against fit criteria:

- Does it improve understanding, motivation, or decision quality?
- Does it preserve credibility and avoid gamifying away real-world caveats?
- Can it be implemented without derailing the core roadmap?
- Is it explainable to a newcomer?
- Does Alex need to decide before we proceed?

### 5. Domain / Evidence Agent

Responsibilities:

- inspect model assumptions and parameter provenance
- identify weak evidence grades and missing source links
- propose official German/EU data sources
- ensure model caveats stay visible

### 6. Implementation Agent(s)

Responsibilities:

- implement one small scoped task on a dedicated branch or in a controlled local step
- add/update tests
- avoid unrelated refactors

## Coordination model

Do not let several bots push directly to `main`.

Preferred flow:

1. Project Manager reviews current state and proposes next tasks.
2. Designer/Evidence/Implementation agents work on focused branches or produce briefs.
3. Integrator reviews, runs tests, commits, and pushes to `main`.
4. Heartbeat reports what each role did, what was accepted, and what is next.

## Branching policy

- `main`: stable, tested, pushed by the integrator only.
- `agent/pm-plan`: planning documents and backlog updates.
- `agent/design-ui`: UI/UX proposals and implemented design improvements.
- `agent/evidence`: source/provenance work.
- `agent/core`: simulation-core changes.

For now, the heartbeat may simulate PM/designer review by spawning focused subagents or by writing explicit review sections. As the project grows, move more work into branch/PR workflows.

## Heartbeat report format

Every 30-minute heartbeat should send Alex a German status message with:

1. Änderungen seit dem letzten Heartbeat
2. Projektmanager-Review: Priorität, Risiko, nächster Schritt
3. Designer-Review: UI/UX-Beobachtung oder Vorschlag
4. Tests/Verifikation
5. Git commit/push status
6. Nächster geplanter Schritt

If nothing changed, still report that the system is alive and what was checked.
