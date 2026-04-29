"""Expert-council workflow primitives for external SimMed contributions.

External AI or human inputs are treated as proposals, not trusted facts. This
module keeps the review states explicit so later API/UI work can expose the
same governance path without letting unreviewed submissions change the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

ContributionState = Literal[
    "submitted",
    "triaged",
    "expert_reviewed",
    "accepted",
    "rejected",
    "integrated",
]

_ALLOWED_TRANSITIONS: dict[ContributionState, tuple[ContributionState, ...]] = {
    "submitted": ("triaged", "rejected"),
    "triaged": ("expert_reviewed", "rejected"),
    "expert_reviewed": ("accepted", "rejected"),
    "accepted": ("integrated",),
    "rejected": (),
    "integrated": (),
}

_REVIEW_REQUIRED_STATES: set[ContributionState] = {
    "expert_reviewed",
    "accepted",
    "rejected",
    "integrated",
}


@dataclass(frozen=True)
class ReviewRecord:
    """A reviewer decision with role and plain-language rationale."""

    reviewer_id: str
    reviewer_role: str
    rationale: str
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, str]:
        return {
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role,
            "rationale": self.rationale,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True)
class ContributionProposal:
    """A submitted claim, dataset, parameter change, or model-change proposal."""

    contribution_id: str
    title: str
    submitted_by: str
    source_type: Literal["human", "external_ai", "internal_agent"]
    summary: str
    affected_parameters: tuple[str, ...] = ()
    evidence_links: tuple[str, ...] = ()
    state: ContributionState = "submitted"
    reviews: tuple[ReviewRecord, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "contribution_id": self.contribution_id,
            "title": self.title,
            "submitted_by": self.submitted_by,
            "source_type": self.source_type,
            "summary": self.summary,
            "affected_parameters": list(self.affected_parameters),
            "evidence_links": list(self.evidence_links),
            "state": self.state,
            "reviews": [review.to_dict() for review in self.reviews],
        }


def transition_contribution(
    proposal: ContributionProposal,
    new_state: ContributionState,
    review: ReviewRecord | None = None,
) -> ContributionProposal:
    """Return a proposal in ``new_state`` after validating council workflow rules."""

    allowed = _ALLOWED_TRANSITIONS[proposal.state]
    if new_state not in allowed:
        raise ValueError(f"Invalid contribution transition: {proposal.state} -> {new_state}")
    if new_state in _REVIEW_REQUIRED_STATES and review is None:
        raise ValueError(f"Transition to {new_state!r} requires reviewer identity and rationale")

    reviews = proposal.reviews + ((review,) if review is not None else ())
    return ContributionProposal(
        contribution_id=proposal.contribution_id,
        title=proposal.title,
        submitted_by=proposal.submitted_by,
        source_type=proposal.source_type,
        summary=proposal.summary,
        affected_parameters=proposal.affected_parameters,
        evidence_links=proposal.evidence_links,
        state=new_state,
        reviews=reviews,
    )


def plain_language_workflow_summary() -> list[str]:
    """Explain the governance workflow for UI/API documentation."""

    return [
        "Neue KI- oder Expertenbeiträge sind zuerst nur Vorschläge.",
        "Ein Integrator triagiert: Ist der Beitrag relevant, verständlich und prüfbar?",
        "Fachliche Reviewer prüfen Quellen, Annahmen und mögliche Nebenwirkungen.",
        "Erst akzeptierte Beiträge dürfen mit Tests, Provenienz und Git-Historie ins Modell integriert werden.",
    ]
