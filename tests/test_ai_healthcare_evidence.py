from ai_healthcare_evidence import (
    AI_HEALTHCARE_EVIDENCE,
    EVIDENCE_SOURCES,
    evidence_quality_summary,
    evidence_sources_for_record,
    list_ai_evidence_sources,
    list_ai_healthcare_evidence,
    validate_ai_healthcare_evidence,
)


def test_ai_evidence_records_have_required_provenance_and_caveats():
    records = list_ai_healthcare_evidence()
    assert records
    for record in records:
        assert record["id"]
        assert record["category"]
        assert record["outcome_types"]
        assert record["study_designs"]
        assert record["evidence_grade"] in {"A", "B", "C", "D", "E"}
        assert record["source_ids"]
        assert record["transferability_to_germany"]
        assert record["implementation_requirements"]
        assert record["risks_and_failure_modes"]
        assert record["expected_simmed_pathways"]
        assert record["caveat"]
        assert record["model_use_status"] == "catalog_only"


def test_ai_evidence_sources_store_origin_quality_and_terms():
    sources = list_ai_evidence_sources()
    assert sources
    for source in sources:
        assert source["id"]
        assert source["title"]
        assert source["url"].startswith("https://")
        assert source["retrieved_via"]
        assert source["retrieved_at"]
        assert source["quality_note"]
        assert source["license_or_terms_note"]


def test_ambient_scribes_record_does_not_overclaim_patient_outcomes():
    record = AI_HEALTHCARE_EVIDENCE["ambient_ai_scribes_documentation_burden"]
    sources = evidence_sources_for_record(record.id)
    summary = evidence_quality_summary(record.id)

    assert record.evidence_grade == "B"
    assert "clinician_workload" in record.outcome_types
    assert "process_outcome" in record.outcome_types
    assert "patient_outcome" not in record.outcome_types
    assert "patient-outcome improvement not yet established" in " ".join(record.risks_and_failure_modes)
    assert "must not convert this directly into better patient outcomes" in record.caveat
    assert summary["primary_source_count"] >= 5
    assert all(source["kind"] in {"paper", "report"} for source in sources)


def test_ambient_scribes_include_pediatric_trial_with_null_time_findings():
    source = EVIDENCE_SOURCES["appl_clin_inform_shin_pediatric_scribes_2025"]
    record = AI_HEALTHCARE_EVIDENCE["ambient_ai_scribes_documentation_burden"]

    assert source.kind == "paper"
    assert source.retrieved_via == "PubMed web search + NCBI E-utilities abstract metadata"
    assert "pediatric subspecialists" in source.quality_note
    assert "no significant change in pajama time" in source.quality_note
    assert "not patient-outcome claims" in source.quality_note
    assert source.id in record.source_ids


def test_youtube_context_pipeline_is_explicitly_grade_e_and_not_model_fact():
    record = AI_HEALTHCARE_EVIDENCE["ai_healthcare_youtube_context_pipeline"]
    summary = evidence_quality_summary(record.id)

    assert record.evidence_grade == "E"
    assert record.model_use_status == "catalog_only"
    assert "context only" in record.caveat
    assert summary["signal_source_count"] == 1
    assert EVIDENCE_SOURCES["youtube_stanford_topol_ai_healthcare_2025"].kind == "youtube_context"
    assert "Transcript retrieval was blocked" in EVIDENCE_SOURCES["youtube_stanford_topol_ai_healthcare_2025"].quality_note


def test_ai_healthcare_catalogue_validation_blocks_signal_overclaiming():
    assert validate_ai_healthcare_evidence() == []

    signal_record = AI_HEALTHCARE_EVIDENCE["ai_healthcare_youtube_context_pipeline"]
    assert signal_record.evidence_grade == "E"
    assert signal_record.model_use_status == "catalog_only"
    assert evidence_quality_summary(signal_record.id)["primary_source_count"] == 0


def test_ai_evidence_passport_summarizes_use_case_without_model_claims():
    from ai_healthcare_evidence import build_ai_evidence_passport

    passport = build_ai_evidence_passport("ambient_ai_scribes_documentation_burden")

    assert passport["id"] == "ambient_ai_scribes_documentation_burden"
    assert passport["headline"] == "Ambient AI scribes for clinical documentation burden"
    assert passport["trust_status"] == "catalog_only"
    assert passport["model_guardrail"] == "Noch kein SimMed-Modelleffekt"
    assert "B" in passport["evidence_label"]
    assert "workload" in passport["what_it_can_support"].lower()
    assert "patient outcomes" in passport["what_it_cannot_support_yet"].lower()
    assert passport["primary_source_count"] >= 4
    assert passport["signal_source_count"] == 0
    assert passport["next_review_step"].startswith("Expert review")


def test_ai_evidence_passport_keeps_youtube_context_as_signal_only():
    from ai_healthcare_evidence import build_ai_evidence_passport

    passport = build_ai_evidence_passport("ai_healthcare_youtube_context_pipeline")

    assert passport["evidence_label"] == "Evidence Grade E — context/signal only"
    assert passport["trust_status"] == "catalog_only"
    assert passport["model_guardrail"] == "Noch kein SimMed-Modelleffekt"
    assert passport["primary_source_count"] == 0
    assert passport["signal_source_count"] == 1
    assert "primary evidence" in passport["next_review_step"]
