"""Authoritative data-source registry for SimMed Deutschland 2040.

The simulator should not hide assumptions in code comments.  This registry is a
first step toward explicit provenance: every parameter can link to one or more
source ids and show users where values came from.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Literal

EvidenceGrade = Literal["A", "B", "C", "D", "E"]


@dataclass(frozen=True)
class DataSource:
    id: str
    name: str
    authority: str
    coverage: str
    access: str
    formats: tuple[str, ...]
    update_cadence: str
    parameters: tuple[str, ...]
    evidence_grade: EvidenceGrade
    caveats: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["formats"] = list(self.formats)
        d["parameters"] = list(self.parameters)
        return d


DATA_SOURCES: dict[str, DataSource] = {
    "destatis_genesis": DataSource(
        id="destatis_genesis",
        name="Destatis GENESIS / Regionaldatenbank",
        authority="Statistisches Bundesamt / Länder",
        coverage="Germany, federal states, districts, time series",
        access="GENESIS API, Regionaldatenbank, CSV/XLSX/JSON/XML downloads",
        formats=("api", "csv", "xlsx", "json", "xml"),
        update_cadence="varies by table; often annual/quarterly",
        parameters=("population", "age_structure", "mortality", "births", "migration", "hospitals", "beds", "care", "education"),
        evidence_grade="A",
        caveats="Table ids and regional definitions change; store source vintage and geography mapping.",
        url="https://www-genesis.destatis.de/genesis/online",
    ),
    "eurostat": DataSource(
        id="eurostat",
        name="Eurostat dissemination API",
        authority="European Commission / Eurostat",
        coverage="EU harmonized national and NUTS regional indicators",
        access="REST API",
        formats=("json", "tsv", "sdmx"),
        update_cadence="varies; often annual",
        parameters=("population", "health_personnel", "hospital_beds", "mortality", "health_expenditure", "regional_comparators"),
        evidence_grade="C",
        caveats="Excellent for EU comparability; German official sources are preferred for domestic legal/planning details.",
        url="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/",
    ),
    "bmg_gbe": DataSource(
        id="bmg_gbe",
        name="BMG / Gesundheitsberichterstattung des Bundes",
        authority="Bundesministerium für Gesundheit / GBE-Bund",
        coverage="German health indicators",
        access="table downloads and portals",
        formats=("html", "csv", "xlsx"),
        update_cadence="varies by indicator",
        parameters=("morbidity", "mortality", "health_expenditure", "insurance", "care_structures"),
        evidence_grade="A",
        caveats="Many tables are download-based rather than clean API endpoints.",
        url="https://www.gbe-bund.de/",
    ),
    "rki": DataSource(
        id="rki",
        name="Robert Koch-Institut open data and reports",
        authority="RKI",
        coverage="German public health, infection, surveys, chronic disease indicators",
        access="RKI open data, GitHub, SurvStat, reports",
        formats=("csv", "json", "xlsx", "pdf"),
        update_cadence="varies; surveillance can be frequent, surveys periodic",
        parameters=("infection_shocks", "vaccination", "chronic_disease", "risk_factors", "mortality_context"),
        evidence_grade="A",
        caveats="Survey estimates may need confidence intervals and methodological notes.",
        url="https://www.rki.de/",
    ),
    "baek": DataSource(
        id="baek",
        name="Bundesärztekammer Ärztestatistik",
        authority="Bundesärztekammer",
        coverage="German physician workforce by sector, specialty, age, sex",
        access="annual reports/downloads",
        formats=("pdf", "xlsx", "csv"),
        update_cadence="annual",
        parameters=("physician_stock", "specialty_mix", "age_structure", "retirement_risk", "foreign_physicians"),
        evidence_grade="A",
        caveats="Often report/download oriented; distinguish headcount from FTE.",
        url="https://www.bundesaerztekammer.de/",
    ),
    "kbv_zi": DataSource(
        id="kbv_zi",
        name="KBV / Zentralinstitut für die kassenärztliche Versorgung",
        authority="KBV / Zi",
        coverage="Ambulatory SHI physician supply, planning and access indicators",
        access="reports, databases, downloads",
        formats=("pdf", "xlsx", "csv", "html"),
        update_cadence="varies; many annual/quarterly products",
        parameters=("ambulatory_supply", "planning_regions", "physician_density", "contacts", "waiting_time_surveys"),
        evidence_grade="A",
        caveats="Waiting-time data are fragmented/survey-based; label uncertainty.",
        url="https://www.kbv.de/",
    ),
    "gkv_finance": DataSource(
        id="gkv_finance",
        name="BMG / GKV-Spitzenverband / BAS finance statistics",
        authority="BMG, GKV-Spitzenverband, Bundesamt für Soziale Sicherung",
        coverage="GKV insured counts, revenue, expenditure, contribution rates, subsidies",
        access="statistics pages, reports, downloads",
        formats=("pdf", "xlsx", "csv"),
        update_cadence="monthly/quarterly/annual depending on statistic",
        parameters=("gkv_revenue", "gkv_expenditure", "contribution_rate", "insured_counts", "federal_subsidy"),
        evidence_grade="A",
        caveats="Definitions differ by statistic; record vintage and accounting scope.",
        url="https://www.bundesgesundheitsministerium.de/",
    ),
    "hrk_medical_education": DataSource(
        id="hrk_medical_education",
        name="HRK / Destatis / Stiftung Hochschulzulassung medical education data",
        authority="HRK, Destatis, Stiftung Hochschulzulassung",
        coverage="Study places, students, graduates and medical education pipeline",
        access="statistics portals and downloads",
        formats=("pdf", "xlsx", "csv"),
        update_cadence="semester/annual",
        parameters=("medical_study_places", "students", "graduates", "dropout", "training_pipeline"),
        evidence_grade="A",
        caveats="Map study places to later physician supply with explicit 6+ and 11+ year delays.",
        url="https://www.hrk.de/",
    ),
    "gematik_bfarm": DataSource(
        id="gematik_bfarm",
        name="gematik / BfArM digital health data",
        authority="gematik, BfArM",
        coverage="ePA/e-prescription/KIM/DiGA rollout and directories",
        access="dashboards, directories, downloads/APIs where available",
        formats=("html", "csv", "json"),
        update_cadence="varies; some dashboards frequent",
        parameters=("digital_adoption", "telemedicine_proxy", "diga_availability", "interoperability"),
        evidence_grade="A",
        caveats="Adoption metrics do not equal productivity gains; model productivity as uncertain and delayed.",
        url="https://www.gematik.de/",
    ),
    "g_ba_iqtig": DataSource(
        id="g_ba_iqtig",
        name="G-BA / IQTIG quality and benefit-assessment sources",
        authority="Gemeinsamer Bundesausschuss / IQTIG",
        coverage="Germany, statutory quality assurance, benefit assessments and care-quality context",
        access="reports, resolutions, quality indicators and downloads",
        formats=("pdf", "xlsx", "csv", "html"),
        update_cadence="varies by procedure/report",
        parameters=("quality", "benefit_assessment", "staffing_quality", "access_targets"),
        evidence_grade="A",
        caveats="Use exact resolution/report vintage; quality indicators are not direct causal effects without transformation notes.",
        url="https://www.g-ba.de/",
    ),
    "inek": DataSource(
        id="inek",
        name="InEK / German DRG and hospital payment data",
        authority="Institut für das Entgeltsystem im Krankenhaus",
        coverage="German hospital payment catalogues, DRG system data and calculation documents",
        access="catalogues, reports and download files",
        formats=("pdf", "xlsx", "csv", "zip"),
        update_cadence="annual with periodic updates",
        parameters=("drg_catalogue", "hospital_payment", "case_mix", "inpatient_costs"),
        evidence_grade="A",
        caveats="DRG catalogues are payment instruments; convert carefully before using as real resource or quality measures.",
        url="https://www.g-drg.de/",
    ),
}


def list_sources() -> list[dict]:
    return [src.to_dict() for src in DATA_SOURCES.values()]


def sources_for_parameter(parameter: str) -> list[DataSource]:
    p = parameter.lower()
    return [s for s in DATA_SOURCES.values() if any(p in item.lower() or item.lower() in p for item in s.parameters)]


def require_source_ids(ids: Iterable[str]) -> None:
    missing = [sid for sid in ids if sid not in DATA_SOURCES]
    if missing:
        raise KeyError(f"Unknown data source id(s): {', '.join(missing)}")
