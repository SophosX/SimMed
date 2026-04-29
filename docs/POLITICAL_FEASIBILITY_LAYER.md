# Political Feasibility Layer

SimMed should distinguish numeric simulation outputs from political feasibility interpretation.

## Purpose

German health-system reform is constrained by institutions, veto players, financing channels, federal-state responsibilities, professional self-governance, and implementation capacity. A scenario can look numerically attractive while being politically implausible or administratively slow.

The political feasibility layer should help users interpret scenarios without turning the model into partisan advocacy.

## Initial rules

- Keep numeric model behavior in `simulation_core.py` and provenance-backed parameters in `parameter_registry.py`.
- Treat political feasibility as an explanation/interpretation layer unless Alex explicitly decides to add it to scoring.
- Clearly separate public institutional analysis from advocacy or campaign messaging.
- Do not encode hidden political preferences as model constants or leaderboard weights.
- When a feasibility statement relies on assumptions rather than a cited source, label it as an assumption.

## Stakeholder dimensions to consider

For major policy levers, later feasibility notes should identify likely incentives or constraints for:

- BMG and federal budget actors
- Länder, especially for hospital planning/investment
- GKV-Spitzenverband, sickness funds, PKV-Verband, and contributor groups
- KBV/KVen and ambulatory-care physicians
- DKG and hospital operators
- BÄK, medical faculties, and workforce pipeline actors
- G-BA/IQTIG and quality/regulatory bodies
- patient groups, rural communities, Pflege actors, and media framing

## Product decision

Alex chose the direction:

1. **Build now — decision-support mode:** a transparent feasibility rubric, clearly separated from health/economic outcomes.
2. **Later — strategy mode:** sequencing, coalitions, veto players, framing, compensation/trade packages, and legislative timing.

This means feasibility can be implemented as an explanation/API layer now, but it must not silently become a hidden model constant, partisan recommendation, or leaderboard score.

## Current implementation notes

`political_feasibility.py` now returns three plain-language layers for the API and UI:

- `lever_notes`: why each changed lever matters, likely supporters/blockers, implementation lag, caveat, and a first `strategy_foundation` sentence.
- `stakeholder_overview`: aggregated supporters/blockers so users can see who may benefit, carry costs, or slow implementation.
- `next_strategy_mode_step`: explicit reminder that Option 3 is later, not forgotten.

The stakeholder overview is intentionally qualitative: it is an orientation map, not a vote forecast, campaign plan, or lobbying recommendation.
