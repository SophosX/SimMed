# SimMed Product Direction

This document records Alex's product direction decisions so future agents do not re-open settled questions unless there is a strong reason.

## Political explanation mode decision

Decision: implement Option 2 first.

Option 2 means: SimMed should not only show model outputs, but also explain the decision context in a transparent, understandable way.

For each important scenario/reform, the app should eventually explain:

- What does the model predict?
- Why does this effect happen?
- Which assumptions drive the result?
- Who benefits?
- Who is burdened?
- Who might politically block or support it?
- How realistic is implementation?
- What are delayed effects or unintended consequences?

Tone:

- clear and understandable for non-experts
- politically realistic, but not party-propagandistic
- transparent about assumptions and uncertainty
- no unexplained black-box conclusions

## Later direction: Strategy Mode

Alex also explicitly wants Option 3 later: a political strategy mode.

Strategy Mode should eventually go beyond explanation and help users explore how a reform could be implemented politically:

- sequencing: what needs to happen first?
- coalition-building: who must be convinced or compensated?
- veto players: who can block the reform?
- framing: how could the reform be communicated?
- trade packages: what compromises make it feasible?
- timing: what is realistic within legislative cycles?

This should not be the first implementation priority. Build the transparent decision/feasibility rubric first, then use it as the foundation for strategy mode.

## Explanation quality requirement

Alex emphasized that the platform must explain things very clearly.

Every major output should answer, in plain language:

- Why did SimMed arrive at this result?
- Why does this policy lever cause this effect?
- Which chain of effects is assumed?
- What is uncertain?
- What would a user need to understand before trusting or challenging the result?

Avoid jargon where possible. If technical terms are necessary, explain them immediately.

Bad:

> The intervention improves access through capacity-side elasticity.

Better:

> More doctors improve access only after a delay, because students need years of training before they become practicing physicians. In the short term, this policy barely changes waiting times.

## Expertenrat governance

External AI systems, internal agents, and human experts may eventually submit claims, source suggestions, parameter updates, or model-change proposals. These submissions are not trusted facts by default.

Required workflow:

1. `submitted`: contribution is only a proposal.
2. `triaged`: Integrator or project lead checks whether it is relevant and verifiable.
3. `expert_reviewed`: a reviewer with a named role records source/assumption rationale.
4. `accepted` or `rejected`: the Integrator records the decision.
5. `integrated`: only accepted contributions may enter code/model/docs, with provenance, tests, and Git history.

Plain-language rule: no external AI output should silently change SimMed's assumptions. It must be attributable, reviewable, and reversible.
