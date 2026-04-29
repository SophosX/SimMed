from expert_council import (
    ContributionProposal,
    ReviewRecord,
    plain_language_workflow_summary,
    transition_contribution,
)


def test_external_ai_submission_starts_as_untrusted_proposal():
    proposal = ContributionProposal(
        contribution_id="c-001",
        title="OECD claim about physician supply",
        submitted_by="external-agent",
        source_type="external_ai",
        summary="Claims Germany needs a physician supply update.",
        affected_parameters=("aerzte_gesamt",),
        evidence_links=("https://example.org/source",),
    )

    data = proposal.to_dict()

    assert data["state"] == "submitted"
    assert data["source_type"] == "external_ai"
    assert data["reviews"] == []


def test_contribution_requires_review_before_acceptance():
    proposal = ContributionProposal(
        contribution_id="c-002",
        title="Prevention effect adjustment",
        submitted_by="domain-expert",
        source_type="human",
        summary="Suggests narrowing prevention uncertainty.",
    )

    triaged = transition_contribution(proposal, "triaged")
    reviewed = transition_contribution(
        triaged,
        "expert_reviewed",
        ReviewRecord(
            reviewer_id="reviewer-1",
            reviewer_role="Evidence/Domain Agent",
            rationale="Source is plausible but still needs parameter-registry mapping.",
        ),
    )
    accepted = transition_contribution(
        reviewed,
        "accepted",
        ReviewRecord(
            reviewer_id="integrator",
            reviewer_role="Integrator",
            rationale="Accepted for implementation with provenance and tests.",
        ),
    )

    assert accepted.state == "accepted"
    assert len(accepted.reviews) == 2


def test_invalid_or_unreviewed_transitions_are_blocked():
    proposal = ContributionProposal(
        contribution_id="c-003",
        title="Unsafe direct model change",
        submitted_by="external-agent",
        source_type="external_ai",
        summary="Attempts to skip review.",
    )

    try:
        transition_contribution(proposal, "accepted")
    except ValueError as exc:
        assert "Invalid contribution transition" in str(exc)
    else:
        raise AssertionError("direct acceptance should be blocked")

    triaged = transition_contribution(proposal, "triaged")
    try:
        transition_contribution(triaged, "expert_reviewed")
    except ValueError as exc:
        assert "requires reviewer identity" in str(exc)
    else:
        raise AssertionError("expert review without reviewer rationale should be blocked")


def test_workflow_summary_is_plain_language():
    summary = plain_language_workflow_summary()

    assert len(summary) >= 4
    assert any("Vorschläge" in line for line in summary)
    assert any("Quellen" in line for line in summary)
    assert all("elasticity" not in line.lower() for line in summary)
