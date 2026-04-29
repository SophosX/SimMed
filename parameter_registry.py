"""Parameter provenance registry for SimMed.

This is deliberately separate from app.py so the simulation can evolve from
hard-coded comments to auditable evidence-backed defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal

from data_sources import require_source_ids

EvidenceGrade = Literal["A", "B", "C", "D", "E"]


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    unit: str
    default: Any
    plausible_min: float | int | None
    plausible_max: float | int | None
    source_ids: tuple[str, ...]
    evidence_grade: EvidenceGrade
    uncertainty: str
    model_role: str
    caveat: str = ""

    def __post_init__(self) -> None:
        require_source_ids(self.source_ids)
        if self.plausible_min is not None and self.plausible_max is not None:
            if self.plausible_min > self.plausible_max:
                raise ValueError(f"Invalid range for {self.key}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_ids"] = list(self.source_ids)
        return d


PARAMETER_REGISTRY: dict[str, ParameterSpec] = {
    "bevoelkerung_mio": ParameterSpec(
        key="bevoelkerung_mio",
        label="Bevölkerung",
        unit="million people",
        default=84.4,
        plausible_min=70.0,
        plausible_max=95.0,
        source_ids=("destatis_genesis",),
        evidence_grade="A",
        uncertainty="scenario band from Destatis population projection; not independent normal noise",
        model_role="demographic stock baseline",
    ),
    "geburtenrate": ParameterSpec(
        key="geburtenrate",
        label="Zusammengefasste Geburtenziffer",
        unit="children per woman",
        default=1.35,
        plausible_min=0.8,
        plausible_max=2.5,
        source_ids=("destatis_genesis",),
        evidence_grade="A",
        uncertainty="scenario band / triangular distribution",
        model_role="birth inflow in demographic cohort model",
    ),
    "netto_zuwanderung": ParameterSpec(
        key="netto_zuwanderung",
        label="Netto-Zuwanderung",
        unit="people/year",
        default=300_000,
        plausible_min=0,
        plausible_max=800_000,
        source_ids=("destatis_genesis",),
        evidence_grade="A",
        uncertainty="wide scenario distribution; correlated with age structure and workforce inflow",
        model_role="population inflow and possible workforce inflow proxy",
    ),
    "urban_anteil": ParameterSpec(
        key="urban_anteil",
        label="Urbanisierungsgrad",
        unit="share of population",
        default=0.77,
        plausible_min=0.50,
        plausible_max=0.95,
        source_ids=("destatis_genesis",),
        evidence_grade="A",
        uncertainty="official settlement/region statistics; future urbanization is scenario-driven",
        model_role="splits access pressure between urban and rural supply modules",
        caveat="This is not yet a district-level settlement model; treat as a simplified scenario lever.",
    ),
    "einkommen_durchschnitt": ParameterSpec(
        key="einkommen_durchschnitt",
        label="Durchschnittliches Bruttoeinkommen",
        unit="EUR/person/year",
        default=45_000,
        plausible_min=25_000,
        plausible_max=80_000,
        source_ids=("destatis_genesis", "gkv_finance"),
        evidence_grade="A",
        uncertainty="income distribution and contribution caps are simplified into one average scenario value",
        model_role="GKV revenue base before contribution rate and insured-share assumptions",
        caveat="Averages hide distribution, employment status and contribution-assessment ceilings.",
    ),
    "einkommens_wachstum": ParameterSpec(
        key="einkommens_wachstum",
        label="Nominales Einkommenswachstum",
        unit="share/year",
        default=0.02,
        plausible_min=0.0,
        plausible_max=0.06,
        source_ids=("destatis_genesis", "gkv_finance"),
        evidence_grade="B",
        uncertainty="future macroeconomic wage growth is a scenario assumption, not an official forecast",
        model_role="annual growth factor for the contribution-revenue base",
        caveat="Does not yet model employment, pensioner share or wage distribution separately.",
    ),
    "pkv_schwelle": ParameterSpec(
        key="pkv_schwelle",
        label="Versicherungspflichtgrenze",
        unit="EUR/year",
        default=69_300,
        plausible_min=50_000,
        plausible_max=90_000,
        source_ids=("gkv_finance",),
        evidence_grade="A",
        uncertainty="legal policy parameter; behavioral switching response is simplified",
        model_role="threshold lever for possible GKV/PKV distribution pressure",
        caveat="Not a full insurance-choice model; distributional and labor-market effects are simplified.",
    ),
    "aerzte_gesamt": ParameterSpec(
        key="aerzte_gesamt",
        label="Ärztinnen und Ärzte gesamt",
        unit="headcount",
        default=421_000,
        plausible_min=200_000,
        plausible_max=600_000,
        source_ids=("baek",),
        evidence_grade="A",
        uncertainty="official headcount; capacity requires FTE conversion",
        model_role="physician stock baseline",
        caveat="Do not treat headcount as capacity; use FTE, specialty, age and region where possible.",
    ),
    "aerzte_pro_100k_urban": ParameterSpec(
        key="aerzte_pro_100k_urban",
        label="Ärztedichte urban",
        unit="physicians per 100,000 population",
        default=280,
        plausible_min=150,
        plausible_max=500,
        source_ids=("kbv_zi", "baek"),
        evidence_grade="B",
        uncertainty="regional ambulatory supply data exist, but this prototype compresses specialties and planning regions into one urban scenario lever",
        model_role="urban ambulatory access capacity proxy",
        caveat="This is not yet a specialty- or district-level Bedarfsplanung model; headcount density still needs FTE/productivity context.",
    ),
    "aerzte_pro_100k_rural": ParameterSpec(
        key="aerzte_pro_100k_rural",
        label="Ärztedichte ländlich",
        unit="physicians per 100,000 population",
        default=160,
        plausible_min=80,
        plausible_max=300,
        source_ids=("kbv_zi", "baek"),
        evidence_grade="B",
        uncertainty="regional supply evidence is stronger than the simplified urban/rural split used here",
        model_role="rural ambulatory access capacity proxy",
        caveat="Use as a scenario lever, not as a claim about a specific Landkreis; specialty mix and travel time are simplified.",
    ),
    "hausarztpraxen": ParameterSpec(
        key="hausarztpraxen",
        label="Hausarztpraxen",
        unit="practices",
        default=55_000,
        plausible_min=30_000,
        plausible_max=80_000,
        source_ids=("kbv_zi",),
        evidence_grade="B",
        uncertainty="practice counts need mapping to active physicians, opening hours and regional coverage",
        model_role="primary-care access and demand-buffer proxy",
        caveat="A practice is not a fixed capacity unit; team size, part-time work and delegation are not fully modeled yet.",
    ),
    "fachpraxen": ParameterSpec(
        key="fachpraxen",
        label="Facharztpraxen",
        unit="practices",
        default=45_000,
        plausible_min=20_000,
        plausible_max=80_000,
        source_ids=("kbv_zi",),
        evidence_grade="B",
        uncertainty="specialty-specific practice structures are collapsed into one scenario lever",
        model_role="specialist access and waiting-time capacity proxy",
        caveat="Does not yet distinguish specialties with very different bottlenecks and referral patterns.",
    ),
    "mvz_anzahl": ParameterSpec(
        key="mvz_anzahl",
        label="Medizinische Versorgungszentren",
        unit="centers",
        default=4_500,
        plausible_min=1_000,
        plausible_max=15_000,
        source_ids=("kbv_zi",),
        evidence_grade="B",
        uncertainty="MVZ counts are observable, but ownership, staffing and substitution effects are simplified",
        model_role="ambulatory organization and access-flexibility proxy",
        caveat="More MVZ does not automatically mean more net capacity; local staffing and ownership effects need separate treatment.",
    ),
    "krankenhaeuser": ParameterSpec(
        key="krankenhaeuser",
        label="Krankenhäuser",
        unit="hospitals",
        default=1_900,
        plausible_min=800,
        plausible_max=3_000,
        source_ids=("destatis_genesis", "bmg_gbe"),
        evidence_grade="A",
        uncertainty="official counts are strong; reform scenarios change roles, case mix and regional access, not only counts",
        model_role="stationary-care structure and spillover proxy",
        caveat="Hospital count alone says little about staffed beds, emergency access or quality; avoid treating it as direct capacity.",
    ),
    "krankenhausbetten": ParameterSpec(
        key="krankenhausbetten",
        label="Krankenhausbetten",
        unit="beds",
        default=480_000,
        plausible_min=200_000,
        plausible_max=700_000,
        source_ids=("destatis_genesis", "bmg_gbe"),
        evidence_grade="A",
        uncertainty="bed statistics are official, but usable capacity depends on staff, occupancy and case mix",
        model_role="inpatient capacity and ambulatory spillover proxy",
        caveat="Beds are not capacity unless staffing and occupancy are modeled explicitly.",
    ),
    "patienten_pro_quartal": ParameterSpec(
        key="patienten_pro_quartal",
        label="Patienten je Arzt und Quartal",
        unit="patients/physician/quarter",
        default=900,
        plausible_min=400,
        plausible_max=1_500,
        source_ids=("kbv_zi",),
        evidence_grade="B",
        uncertainty="contact/case volume evidence exists, but this prototype uses one productivity lever across physicians",
        model_role="ambulatory throughput and waiting-time pressure lever",
        caveat="Higher throughput can mean better access or rushed care; quality and unmet need are not fully represented yet.",
    ),
    "arbeitszeit_stunden": ParameterSpec(
        key="arbeitszeit_stunden",
        label="Ärztliche Arbeitszeit",
        unit="hours/week",
        default=50,
        plausible_min=35,
        plausible_max=70,
        source_ids=("baek", "kbv_zi"),
        evidence_grade="B",
        uncertainty="working-time distributions differ by sector, sex, age, employment model and specialty",
        model_role="FTE conversion and realized-capacity proxy",
        caveat="A simple weekly-hours slider cannot capture administrative burden, delegation or part-time mix in detail.",
    ),
    "medizinstudienplaetze": ParameterSpec(
        key="medizinstudienplaetze",
        label="Medizinstudienplätze pro Jahr",
        unit="places/year",
        default=11_000,
        plausible_min=5_000,
        plausible_max=25_000,
        source_ids=("hrk_medical_education", "destatis_genesis"),
        evidence_grade="A",
        uncertainty="official education data plus uncertain dropout and practice-entry rates",
        model_role="delayed physician inflow; effect starts after ~6 years and specialist effect after ~11-13 years",
        caveat="Never apply study-place changes instantly to physician supply.",
    ),
    "gkv_beitragssatz": ParameterSpec(
        key="gkv_beitragssatz",
        label="Allgemeiner GKV-Beitragssatz",
        unit="percent of contributory income",
        default=14.6,
        plausible_min=12.0,
        plausible_max=18.0,
        source_ids=("gkv_finance",),
        evidence_grade="A",
        uncertainty="policy parameter; future response should be endogenous or scenario-driven",
        model_role="GKV revenue calculation",
    ),
    "gkv_zusatzbeitrag": ParameterSpec(
        key="gkv_zusatzbeitrag",
        label="Durchschnittlicher GKV-Zusatzbeitrag",
        unit="percent of contributory income",
        default=1.7,
        plausible_min=0.0,
        plausible_max=4.0,
        source_ids=("gkv_finance",),
        evidence_grade="A",
        uncertainty="policy/finance response variable",
        model_role="GKV revenue calculation and sustainability output",
    ),
    "gkv_anteil": ParameterSpec(
        key="gkv_anteil",
        label="GKV-Versichertenanteil",
        unit="share of population",
        default=0.88,
        plausible_min=0.70,
        plausible_max=0.95,
        source_ids=("gkv_finance",),
        evidence_grade="A",
        uncertainty="official insured-count statistics, but future switching dynamics are simplified",
        model_role="allocates population and revenue/expenditure pressure to statutory insurance",
        caveat="Does not yet distinguish members, dependents, pensioners and contribution status.",
    ),
    "staatliche_subventionen": ParameterSpec(
        key="staatliche_subventionen",
        label="Bundeszuschuss an die GKV",
        unit="billion EUR/year",
        default=14.5,
        plausible_min=0.0,
        plausible_max=30.0,
        source_ids=("gkv_finance",),
        evidence_grade="A",
        uncertainty="budget policy scenario; future federal financing is politically uncertain",
        model_role="direct public-finance support in the GKV revenue calculation",
        caveat="Counter-financing and federal-budget tradeoffs are not yet modeled.",
    ),
    "telemedizin_rate": ParameterSpec(
        key="telemedizin_rate",
        label="Telemedizin-Startrate",
        unit="share of contacts",
        default=0.05,
        plausible_min=0.0,
        plausible_max=0.6,
        source_ids=("gematik_bfarm", "kbv_zi"),
        evidence_grade="B",
        uncertainty="adoption curve; productivity effect uncertain and delayed",
        model_role="care substitution and access/productivity module",
        caveat="Telemedicine can substitute some visits but can also induce demand; avoid flat cost-saving assumptions.",
    ),
    "digitalisierung_epa": ParameterSpec(
        key="digitalisierung_epa",
        label="ePA-Nutzungsrate",
        unit="share of insured/users",
        default=0.15,
        plausible_min=0.0,
        plausible_max=1.0,
        source_ids=("gematik_bfarm",),
        evidence_grade="B",
        uncertainty="rollout/adoption evidence is observable, but productivity effects are delayed and uncertain",
        model_role="digital coordination and documentation lever with uncertain productivity effect",
        caveat="Adoption is not the same as better outcomes; implementation cost, usability and trust matter.",
    ),
    "praeventionsbudget": ParameterSpec(
        key="praeventionsbudget",
        label="Präventionsbudget",
        unit="billion EUR/year",
        default=8.0,
        plausible_min=0.0,
        plausible_max=30.0,
        source_ids=("bmg_gbe", "gkv_finance", "rki"),
        evidence_grade="B",
        uncertainty="disease-specific effect sizes with lag; often long-term and uncertain",
        model_role="prevention intervention cost and morbidity reduction module",
        caveat="Prevention should not be modeled as immediate global cost reduction.",
    ),
}


def list_parameters() -> list[dict]:
    return [p.to_dict() for p in PARAMETER_REGISTRY.values()]


def get_parameter(key: str) -> ParameterSpec:
    return PARAMETER_REGISTRY[key]


def evidence_summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for spec in PARAMETER_REGISTRY.values():
        counts[spec.evidence_grade] = counts.get(spec.evidence_grade, 0) + 1
    return counts
