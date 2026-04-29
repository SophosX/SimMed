"""Structured evidence records for AI implementations in healthcare.

The records here are not model-effect sizes. They are an auditable evidence
catalogue for later SimMed modules. Every claim must be traceable to a source or
explicitly labelled as context/signal only.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Literal

EvidenceGrade = Literal["A", "B", "C", "D", "E"]
OutcomeType = Literal[
    "patient_outcome",
    "process_outcome",
    "clinician_workload",
    "cost_billing",
    "safety_quality",
    "equity_access",
    "technical_benchmark_only",
]
StudyDesign = Literal[
    "randomized_trial",
    "pragmatic_trial",
    "prospective_observational",
    "retrospective_observational",
    "systematic_review",
    "narrative_review",
    "institutional_report",
    "social_signal",
    "expert_context",
]
SourceKind = Literal["paper", "report", "trial_registry", "news", "x_signal", "youtube_context"]


@dataclass(frozen=True)
class EvidenceSource:
    id: str
    title: str
    url: str
    kind: SourceKind
    retrieved_via: str
    retrieved_at: str
    quality_note: str
    license_or_terms_note: str
    source_date: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AIHealthcareEvidenceRecord:
    id: str
    name: str
    category: str
    clinical_setting: str
    target_problem: str
    intervention: str
    comparator: str
    measured_outcomes: tuple[str, ...]
    outcome_types: tuple[OutcomeType, ...]
    study_designs: tuple[StudyDesign, ...]
    evidence_grade: EvidenceGrade
    source_ids: tuple[str, ...]
    transferability_to_germany: str
    implementation_requirements: tuple[str, ...]
    risks_and_failure_modes: tuple[str, ...]
    expected_simmed_pathways: tuple[str, ...]
    caveat: str
    model_use_status: Literal["catalog_only", "exploratory_parameter", "model_effect"] = "catalog_only"

    def to_dict(self) -> dict:
        return asdict(self)


EVIDENCE_SOURCES: dict[str, EvidenceSource] = {
    "jama_open_olson_ambient_scribes_2025": EvidenceSource(
        id="jama_open_olson_ambient_scribes_2025",
        title="Use of Ambient AI Scribes to Reduce Administrative Burden and Burnout",
        url="https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2839542",
        kind="paper",
        retrieved_via="Grok web search",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note="Peer-reviewed JAMA Network Open study; useful for clinician workload/burnout signals, not direct proof of patient-outcome improvement.",
        license_or_terms_note="Public article page; verify publisher reuse terms before storing full text beyond citation/metadata.",
    ),
    "nejm_ai_lukac_ambient_scribes_2025": EvidenceSource(
        id="nejm_ai_lukac_ambient_scribes_2025",
        title="Ambient AI Scribes in Clinical Practice: A Randomized Trial",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12768499",
        kind="paper",
        retrieved_via="Grok web search",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note="Randomized trial available via PMC; stronger for documentation/workload outcomes than for downstream patient outcomes.",
        license_or_terms_note="PMC page; check article license before reusing full text. Metadata/citation retained here.",
    ),
    "nejm_ai_afshar_pragmatic_ambient_2025": EvidenceSource(
        id="nejm_ai_afshar_pragmatic_ambient_2025",
        title="A Pragmatic Randomized Controlled Trial of Ambient Artificial Intelligence Scribes",
        url="https://ai.nejm.org/doi/abs/10.1056/AIoa2500945",
        kind="paper",
        retrieved_via="Grok web search",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note="Pragmatic randomized implementation evidence; interpret endpoint mix carefully and avoid patient-outcome overclaiming.",
        license_or_terms_note="Publisher page; store citation/metadata only unless reuse terms permit more.",
    ),
    "jama_open_duggan_clinician_experience_2025": EvidenceSource(
        id="jama_open_duggan_clinician_experience_2025",
        title="Clinician Experiences With Ambient Scribe Technology",
        url="https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2830383",
        kind="paper",
        retrieved_via="Grok web search",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note="Clinician-experience evidence; useful for workflow and perceived burden, weaker for hard outcomes.",
        license_or_terms_note="Public article page; verify reuse terms before storing text.",
    ),
    "phti_ai_delivery_early_impacts_2025": EvidenceSource(
        id="phti_ai_delivery_early_impacts_2025",
        title="PHTI Adoption of AI in Healthcare Delivery Systems: Early Applications and Impacts",
        url="https://phti.org/wp-content/uploads/sites/3/2025/03/PHTI-Adoption-of-AI-in-Healthcare-Delivery-Systems-Early-Applications-Impacts.pdf",
        kind="report",
        retrieved_via="Grok web search",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note="Institutional evaluation/report; useful for implementation and economic caveats, should not override trial evidence.",
        license_or_terms_note="Report PDF; verify PHTI terms before redistributing full text. Store citation/summary only.",
    ),
    "jama_editorial_effectiveness_ambient_scribes_2026": EvidenceSource(
        id="jama_editorial_effectiveness_ambient_scribes_2026",
        title="Effectiveness of Ambient AI Scribes",
        url="https://jamanetwork.com/journals/jama/fullarticle/2847322",
        kind="paper",
        retrieved_via="Grok X search via JAMA_current citation",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note="Editorial/context source highlighting that evidence for patient outcomes and equity remains limited.",
        license_or_terms_note="Publisher page; store citation/metadata only unless reuse terms permit more.",
    ),
    "appl_clin_inform_shin_pediatric_scribes_2025": EvidenceSource(
        id="appl_clin_inform_shin_pediatric_scribes_2025",
        title="The Influence of Artificial Intelligence Scribes on Clinician Experience and Efficiency among Pediatric Subspecialists: A Rapid, Randomized Quality Improvement Trial",
        url="https://pubmed.ncbi.nlm.nih.gov/40675605/",
        kind="paper",
        retrieved_via="PubMed web search + NCBI E-utilities abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note=(
            "Randomized quality-improvement trial in pediatric subspecialists; reported improved clinician experience/burnout, "
            "but no significant change in pajama time, note time or wRVUs. Useful for workload/process nuance, not patient-outcome claims."
        ),
        license_or_terms_note="PubMed metadata/abstract; article copyright belongs to Thieme. Store citation/metadata only unless reuse terms permit more.",
    ),
    "appl_clin_inform_sutton_ai_scribes_review_2025": EvidenceSource(
        id="appl_clin_inform_sutton_ai_scribes_review_2025",
        title="Clinical Implementation of Artificial Intelligence Scribes in Health Care: A Systematic Review",
        url="https://pubmed.ncbi.nlm.nih.gov/40306686/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note=(
            "Systematic review of AI-scribe implementations after 2021; proposes an evaluation framework and reports gaps across "
            "clinician, patient and organizational effects. Use as evidence-map/context for evaluation domains, not as a pooled effect size."
        ),
        license_or_terms_note="PubMed metadata/abstract; article copyright may apply. Store citation/metadata only unless reuse terms permit more.",
    ),
    "ann_emerg_med_ed_adoption_documentation_time_2026": EvidenceSource(
        id="ann_emerg_med_ed_adoption_documentation_time_2026",
        title="Ambient Artificial Intelligence Scribe Adoption and Documentation Time in the Emergency Department",
        url="https://pubmed.ncbi.nlm.nih.gov/41665590/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Retrospective ED audit-log study of 8,740 eligible encounters; ambient AI use was low/skewed and concentrated in lower-acuity, "
            "non-interpreter encounters. When used it was associated with shorter on-shift documentation time and total EHR time, so it is useful "
            "for adoption/selection-bias and emergency-care workflow caveats, not patient-outcome claims."
        ),
        license_or_terms_note="PubMed metadata/abstract; article copyright belongs to the publisher. Store citation/metadata only unless reuse terms permit more.",
    ),
    "ann_emerg_med_ai_vs_human_scribes_2026": EvidenceSource(
        id="ann_emerg_med_ai_vs_human_scribes_2026",
        title="Ambient Artificial Intelligence Versus Human Scribes in the Emergency Department",
        url="https://pubmed.ncbi.nlm.nih.gov/41251650/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Emergency-department quality-improvement pilot comparing AI and human scribes; AI notes had similar adult quality but lower pediatric "
            "quality, and physicians spent more note-section time/contributed more note text with AI. Important negative/mixed comparator evidence."
        ),
        license_or_terms_note="PubMed metadata/abstract; article copyright belongs to the publisher. Store citation/metadata only unless reuse terms permit more.",
    ),
    "ann_intern_med_vha_primary_care_note_quality_2026": EvidenceSource(
        id="ann_intern_med_vha_primary_care_note_quality_2026",
        title="Rapid Evaluation of Artificial Intelligence Technology Used for Ambient Dictation in Primary Care: Comparing the Quality of Documentation of Artificial Intelligence-Generated and Human-Produced Clinical Notes",
        url="https://pubmed.ncbi.nlm.nih.gov/41996184/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Cross-sectional VHA evaluation using standardized primary-care audio cases and blinded PDQI-9 note-quality ratings. "
            "Human-produced notes scored higher than AI-generated notes across cases/domains, with especially large deficits in thoroughness, "
            "organization and usefulness. Important documentation-quality counterweight; simulated cases mean it is not workflow-time or patient-outcome proof."
        ),
        license_or_terms_note="PubMed abstract metadata and publisher DOI metadata only; do not store full article text unless reuse terms permit more.",
    ),
    "cardiovasc_diagn_ther_ambient_scribes_narrative_review_2026": EvidenceSource(
        id="cardiovasc_diagn_ther_ambient_scribes_narrative_review_2026",
        title="Transforming clinical documentation with ambient artificial intelligence (AI) scribes: a narrative review of technology, impact, and implementation",
        url="https://pubmed.ncbi.nlm.nih.gov/41815573/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Narrative review covering studies from January 2019 to June 2025. It summarizes workload/efficiency promise but explicitly warns "
            "about frequent documentation omissions, occasional clinically significant hallucinations, small cohorts, methodological variability, "
            "specialty-specific validation needs and medico-legal/workflow redesign requirements. Treat as implementation/safety context, not a pooled effect size."
        ),
        license_or_terms_note="PubMed metadata/abstract; article copyright belongs to the publisher. Store citation/metadata only unless reuse terms permit more.",
    ),
    "jama_open_multisite_time_visit_quantity_2026": EvidenceSource(
        id="jama_open_multisite_time_visit_quantity_2026",
        title="Changes in Clinician Time Expenditure and Visit Quantity With Adoption of Artificial Intelligence-Powered Scribes: A Multisite Study",
        url="https://pubmed.ncbi.nlm.nih.gov/41920565/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Multisite longitudinal cohort across five US academic health-care institutions introducing AI scribes between June 2023 and August 2025. "
            "The abstract frames outcomes as EHR time expenditure and visit volume after voluntary opt-in access, so it is useful for real-world adoption, "
            "time-use and productivity nuance, but selection/adoption effects mean it is not randomized proof of patient outcomes or German capacity gains."
        ),
        license_or_terms_note="PubMed metadata/abstract and DOI metadata only; do not store full article text unless reuse terms permit more.",
    ),
    "appl_clin_inform_patient_experience_ambient_2026": EvidenceSource(
        id="appl_clin_inform_patient_experience_ambient_2026",
        title="The Effect of Ambient Listening Technology on the Patient Experience",
        url="https://pubmed.ncbi.nlm.nih.gov/41760358/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Observational outpatient survey across departments at a large academic institution with 8,120 patient responses. "
            "Ambient scribe use was associated with a small improvement in one patient-experience domain (perceived time/attention) "
            "and no detectable differences across other surveyed experience domains. Useful as patient-acceptability/process nuance, "
            "not proof of clinical patient outcomes or German-system benefit."
        ),
        license_or_terms_note="PubMed metadata/abstract only; do not store full article text unless publisher reuse terms permit more.",
    ),
    "jamia_clinician_editing_rationale_ambient_2026": EvidenceSource(
        id="jamia_clinician_editing_rationale_ambient_2026",
        title="Clinicians' rationale for editing ambient AI-drafted clinical notes: persistent challenges and implications for improvement",
        url="https://pubmed.ncbi.nlm.nih.gov/42044151/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Semistructured interview study with 30 outpatient clinicians using a commercial ambient AI tool in routine care. "
            "Clinicians edited drafts for clinical accuracy, specialty precision, medico-legal/liability risk, billing/coding standards, "
            "transcription errors, speaker-attribution mistakes, unsupported confident statements, missing clinical details and missing patient context. "
            "Use as implementation/safety and workflow-design evidence, not as proof of time savings, patient outcomes or German capacity gains."
        ),
        license_or_terms_note="PubMed metadata/abstract only; article copyright belongs to the publisher. Store citation/metadata only unless reuse terms permit more.",
    ),
    "jmir_ai_ambient_scribes_rapid_review_2025": EvidenceSource(
        id="jmir_ai_ambient_scribes_rapid_review_2025",
        title="Real-World Evidence Synthesis of Digital Scribes Using Ambient Listening and Generative Artificial Intelligence for Clinician Documentation Workflows: Rapid Review",
        url="https://pubmed.ncbi.nlm.nih.gov/41071988/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2025",
        quality_note=(
            "Rapid review across Ovid MEDLINE, Embase, Web of Science, Cochrane and PubMed Central covering real-world ambient/digital scribe "
            "implementation evidence from 2014 to 2024. Only 6 of 1,450 screened studies met inclusion criteria, with mixed designs including "
            "observational, case-report, peer-matched cohort and survey-based assessments. Use as an evidence-gap map for workflow, satisfaction, "
            "quality and implementation barriers, not as a pooled effect size or proof of German capacity, cost, equity or patient-outcome benefit."
        ),
        license_or_terms_note="PubMed abstract metadata only; article copyright/license may apply. Store citation/metadata only unless reuse terms permit more.",
    ),
    "jmir_med_inform_singapore_time_motion_2026": EvidenceSource(
        id="jmir_med_inform_singapore_time_motion_2026",
        title="Impact of an Ambient AI Scribe Among Clinicians and Patients: Real-World Prospective Observational Time-Motion Study",
        url="https://pubmed.ncbi.nlm.nih.gov/41915701/",
        kind="paper",
        retrieved_via="PubMed E-utilities search + abstract metadata",
        retrieved_at="2026-04-29",
        source_date="2026",
        quality_note=(
            "Prospective within-clinician quality-improvement study at a large academic medical center in Singapore with nine clinicians, "
            "matched observations with and without an in-house ambient scribe, standardized time-motion measurement, and patient surveys. "
            "Useful because it uses direct observation rather than only EHR timestamps, but the small single-center design and QI framing mean "
            "it should remain workflow/patient-engagement nuance, not proof of patient outcomes, German capacity gains or cost savings."
        ),
        license_or_terms_note="PubMed abstract metadata only; article copyright/license may apply. Store citation/metadata only unless reuse terms permit more.",
    ),
    "x_jama_current_ambient_scribes_2026": EvidenceSource(
        id="x_jama_current_ambient_scribes_2026",
        title="JAMA X post: ambient scribes reduce documentation time but patient outcomes/equity evidence limited",
        url="https://x.com/JAMA_current/status/2039364666787271151",
        kind="x_signal",
        retrieved_via="Grok X search",
        retrieved_at="2026-04-29",
        source_date="2026-04-01",
        quality_note="Signal only; useful to discover the JAMA editorial, not a standalone evidence source.",
        license_or_terms_note="X post metadata only; do not treat as primary evidence.",
    ),
    "youtube_stanford_topol_ai_healthcare_2025": EvidenceSource(
        id="youtube_stanford_topol_ai_healthcare_2025",
        title="Stanford AI in Healthcare Series with Eric Topol",
        url="https://www.youtube.com/watch?v=1TonDx9Wh3U",
        kind="youtube_context",
        retrieved_via="Grok web search + transcript attempt",
        retrieved_at="2026-04-29",
        source_date="2025/2026 candidate",
        quality_note="Expert context candidate. Transcript retrieval was blocked by YouTube/IP; not yet ingested. Do not use as model evidence until transcript and cited sources are reviewed.",
        license_or_terms_note="YouTube transcript unavailable from this environment; store URL/candidate only, respect platform terms.",
    ),
}

AI_HEALTHCARE_EVIDENCE: dict[str, AIHealthcareEvidenceRecord] = {
    "ambient_ai_scribes_documentation_burden": AIHealthcareEvidenceRecord(
        id="ambient_ai_scribes_documentation_burden",
        name="Ambient AI scribes for clinical documentation burden",
        category="documentation_ambient_scribes",
        clinical_setting="outpatient and mixed clinical encounters",
        target_problem="clinician documentation burden, after-hours charting, burnout and visit-note workload",
        intervention="ambient audio capture/transcription plus AI-generated clinical note draft reviewed by clinician",
        comparator="usual clinician documentation without ambient AI scribe",
        measured_outcomes=(
            "documentation time / after-hours documentation",
            "clinician burnout, work exhaustion or cognitive load",
            "documentation quality and clinician experience",
            "patient experience where measured",
            "billing/revenue effects remain under evaluation",
        ),
        outcome_types=("clinician_workload", "process_outcome", "cost_billing", "safety_quality"),
        study_designs=(
            "randomized_trial",
            "pragmatic_trial",
            "prospective_observational",
            "institutional_report",
            "systematic_review",
            "narrative_review",
        ),
        evidence_grade="B",
        source_ids=(
            "jama_open_olson_ambient_scribes_2025",
            "nejm_ai_lukac_ambient_scribes_2025",
            "nejm_ai_afshar_pragmatic_ambient_2025",
            "jama_open_duggan_clinician_experience_2025",
            "phti_ai_delivery_early_impacts_2025",
            "jama_editorial_effectiveness_ambient_scribes_2026",
            "appl_clin_inform_shin_pediatric_scribes_2025",
            "appl_clin_inform_sutton_ai_scribes_review_2025",
            "ann_emerg_med_ed_adoption_documentation_time_2026",
            "ann_emerg_med_ai_vs_human_scribes_2026",
            "ann_intern_med_vha_primary_care_note_quality_2026",
            "cardiovasc_diagn_ther_ambient_scribes_narrative_review_2026",
            "jama_open_multisite_time_visit_quantity_2026",
            "appl_clin_inform_patient_experience_ambient_2026",
            "jamia_clinician_editing_rationale_ambient_2026",
            "jmir_ai_ambient_scribes_rapid_review_2025",
            "jmir_med_inform_singapore_time_motion_2026",
        ),
        transferability_to_germany=(
            "Medium: documentation burden and clinician workflow are relevant in Germany, but effects depend on German documentation rules, "
            "EHR integration, reimbursement/coding incentives, data-protection requirements, language quality and clinician acceptance."
        ),
        implementation_requirements=(
            "EHR/PVS/KIS integration and structured note review workflow",
            "German-language medical transcription quality and terminology handling",
            "data-protection, consent and storage rules",
            "clinician training and clear accountability for final documentation",
            "monitoring for documentation quality, billing changes and patient trust",
        ),
        risks_and_failure_modes=(
            "automation bias or unreviewed note errors",
            "privacy/consent concerns from ambient recording",
            "upcoding or billing-intensity changes if documentation becomes more detailed",
            "workflow disruption if drafts are low quality or poorly integrated",
            "unequal benefit if small practices cannot afford or integrate tools",
            "patient-outcome improvement not yet established by this evidence set",
        ),
        expected_simmed_pathways=(
            "clinician_time_available",
            "burnout_rate",
            "administrative_costs_and_upfront_it_costs",
            "documentation_quality_and_billing_intensity",
            "patient_trust_and_privacy_acceptance",
        ),
        caveat=(
            "Current evidence is strongest for workload/process outcomes and clinician experience. SimMed must not convert this directly into "
            "better patient outcomes without separate evidence and German transfer review."
        ),
    ),
    "ai_healthcare_youtube_context_pipeline": AIHealthcareEvidenceRecord(
        id="ai_healthcare_youtube_context_pipeline",
        name="YouTube/expert transcript context for AI healthcare impact",
        category="research_context_pipeline",
        clinical_setting="cross-setting expert discussion and implementation context",
        target_problem="expert talks contain implementation lessons and references that may not appear in trial abstracts",
        intervention="transcript extraction, claim tagging and citation backtracking",
        comparator="unstructured manual viewing without stored transcript provenance",
        measured_outcomes=("claim inventory", "speaker/source context", "links to original evidence where cited"),
        outcome_types=("technical_benchmark_only",),
        study_designs=("expert_context",),
        evidence_grade="E",
        source_ids=("youtube_stanford_topol_ai_healthcare_2025",),
        transferability_to_germany="Low until each transcript claim is linked to primary evidence and German-context caveats.",
        implementation_requirements=(
            "working transcript retrieval or user-provided transcript",
            "hash transcript text and store URL/speaker/date",
            "classify each claim as evidence, expert opinion, anecdote or implementation warning",
            "link cited studies before model use",
        ),
        risks_and_failure_modes=(
            "expert opinion mistaken for empirical evidence",
            "selective quotation",
            "transcript errors or missing context",
            "YouTube/IP transcript access limitations",
        ),
        expected_simmed_pathways=("evidence_discovery", "implementation_context", "expert_review_queue"),
        caveat="Transcript content is context only until citations are traced and reviewed; no model parameters should be changed from YouTube alone.",
    ),
}


def list_ai_healthcare_evidence() -> list[dict]:
    return [record.to_dict() for record in AI_HEALTHCARE_EVIDENCE.values()]


def list_ai_evidence_sources() -> list[dict]:
    return [source.to_dict() for source in EVIDENCE_SOURCES.values()]


def evidence_sources_for_record(record_id: str) -> list[dict]:
    record = AI_HEALTHCARE_EVIDENCE[record_id]
    return [EVIDENCE_SOURCES[source_id].to_dict() for source_id in record.source_ids]


def evidence_quality_summary(record_id: str) -> dict:
    record = AI_HEALTHCARE_EVIDENCE[record_id]
    sources = evidence_sources_for_record(record_id)
    primary_sources = [s for s in sources if s["kind"] in {"paper", "report", "trial_registry"}]
    signal_sources = [s for s in sources if s["kind"] in {"x_signal", "youtube_context", "news"}]
    return {
        "record_id": record_id,
        "evidence_grade": record.evidence_grade,
        "primary_source_count": len(primary_sources),
        "signal_source_count": len(signal_sources),
        "model_use_status": record.model_use_status,
        "bottom_line": record.caveat,
    }


def build_ai_evidence_passport(record_id: str) -> dict:
    """Return a compact UI/API-safe summary for one AI-healthcare evidence record.

    The passport is deliberately conservative: it summarizes what the catalogue
    can support, what it cannot support yet, and the model-use guardrail without
    creating new causal claims or parameter effects.
    """
    record = AI_HEALTHCARE_EVIDENCE[record_id]
    quality = evidence_quality_summary(record_id)
    can_support = ", ".join((*record.outcome_types, *record.measured_outcomes[:3]))
    cannot_support = record.caveat
    if record.evidence_grade == "E" or quality["primary_source_count"] == 0:
        evidence_label = f"Evidence Grade {record.evidence_grade} — context/signal only"
        next_step = "Trace claims to primary evidence before expert review or model use."
    else:
        evidence_label = f"Evidence Grade {record.evidence_grade} — primary sources available"
        next_step = "Expert review should confirm transferability, caveats and whether an exploratory parameter is justified."

    return {
        "id": record.id,
        "headline": record.name,
        "category": record.category,
        "clinical_setting": record.clinical_setting,
        "target_problem": record.target_problem,
        "evidence_label": evidence_label,
        "trust_status": record.model_use_status,
        "model_guardrail": "Noch kein SimMed-Modelleffekt" if record.model_use_status == "catalog_only" else record.model_use_status,
        "what_it_can_support": can_support,
        "what_it_cannot_support_yet": cannot_support,
        "germany_transferability": record.transferability_to_germany,
        "primary_source_count": quality["primary_source_count"],
        "signal_source_count": quality["signal_source_count"],
        "key_risks": list(record.risks_and_failure_modes[:3]),
        "next_review_step": next_step,
    }



def validate_ai_healthcare_evidence() -> list[str]:
    """Return provenance/model-use guardrail violations for the AI evidence catalogue.

    This keeps the catalogue safe to grow in heartbeat-sized slices: weak signal
    sources such as X, YouTube, blogs or news can be stored for discovery, but
    they must not silently become model effects or high-grade evidence.
    """
    errors: list[str] = []
    valid_source_ids = set(EVIDENCE_SOURCES)
    for record in AI_HEALTHCARE_EVIDENCE.values():
        missing_sources = set(record.source_ids) - valid_source_ids
        if missing_sources:
            errors.append(f"{record.id}: unknown source ids {sorted(missing_sources)}")
        if record.model_use_status == "model_effect" and record.evidence_grade in {"D", "E"}:
            errors.append(f"{record.id}: low-grade evidence cannot be a model_effect")
        signal_sources = [EVIDENCE_SOURCES[source_id] for source_id in record.source_ids if source_id in EVIDENCE_SOURCES and EVIDENCE_SOURCES[source_id].kind in {"x_signal", "youtube_context", "news"}]
        primary_sources = [EVIDENCE_SOURCES[source_id] for source_id in record.source_ids if source_id in EVIDENCE_SOURCES and EVIDENCE_SOURCES[source_id].kind in {"paper", "report", "trial_registry"}]
        if signal_sources and not primary_sources and record.evidence_grade != "E":
            errors.append(f"{record.id}: signal-only evidence must stay grade E until traced to primary sources")
        if signal_sources and record.model_use_status != "catalog_only":
            errors.append(f"{record.id}: signal/context records must stay catalog_only until expert review")
        if "patient_outcome" in record.outcome_types and "patient" not in record.caveat.lower():
            errors.append(f"{record.id}: patient-outcome records need an explicit patient-outcome caveat")
    return errors
