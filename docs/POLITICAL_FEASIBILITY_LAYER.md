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

## Product decision still open

Before implementing political feasibility scores or badges, Alex should decide the product tone:

1. **Neutral explainer:** feasibility notes only, no score.
2. **Decision-support mode:** transparent feasibility rubric, clearly separated from health/economic outcomes.
3. **Competition mode:** feasibility becomes one scoring dimension, with anti-gaming controls and hidden stress tests.

Until that decision is made, keep political feasibility work in docs and explanatory metadata only.
