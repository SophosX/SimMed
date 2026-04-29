import pandas as pd

from baseline_projection import build_baseline_projection
from international_reforms import list_international_reforms, transfer_reform_to_germany
from simulation_report import build_simulation_report
from app import get_default_params


def _agg():
    return pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 480.0,
            "gkv_saldo_mean": 2.0,
            "wartezeit_fa_mean": 20.0,
            "aerzte_pro_100k_mean": 420.0,
            "lebenserwartung_mean": 79.0,
            "kollaps_wahrscheinlichkeit_mean": 2.0,
            "zufriedenheit_patienten_mean": 70.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 760.0,
            "gkv_saldo_mean": -25.0,
            "wartezeit_fa_mean": 29.0,
            "aerzte_pro_100k_mean": 360.0,
            "lebenserwartung_mean": 81.0,
            "kollaps_wahrscheinlichkeit_mean": 8.0,
            "zufriedenheit_patienten_mean": 62.0,
        },
    ])


def test_baseline_projection_separates_current_external_projection_and_model_assumption():
    baseline = build_baseline_projection()
    assert baseline["name"] == "Deutschland-Baseline + Referenzprojektion bis 2040"
    layers = {item["layer"] for section in baseline["sections"] for item in section["items"]}
    assert {"current_measurement", "external_projection", "simmed_assumption"}.issubset(layers)
    assert all(item["evidence_grade"] for section in baseline["sections"] for item in section["items"])
    assert "keine amtliche Prognose" in baseline["plain_language_summary"]


def test_international_reforms_are_transferable_only_with_caveats():
    reforms = list_international_reforms()
    assert reforms
    reform = reforms[0]
    assert reform["country"]
    assert reform["reported_outcomes"]
    assert reform["comparability_to_germany"] in {"hoch", "mittel", "niedrig"}
    transfer = transfer_reform_to_germany(reform["id"])
    assert transfer["suggested_parameter_changes"]
    assert "nicht 1:1" in transfer["transfer_caveat"]
    assert transfer["confidence"] in {"explorativ", "moderat", "hoch"}


def test_simulation_report_builds_structured_policy_briefing_blocks():
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.1
    report = build_simulation_report(_agg(), params)
    assert report["title"] == "Policy-Briefing"
    section_ids = [section["id"] for section in report["sections"]]
    assert section_ids[:4] == ["executive_summary", "baseline", "scenario_changes", "causal_pathways"]
    assert "kpi_deep_dives" in section_ids
    assert "sources_evidence_assumptions" in section_ids
    combined = " ".join(section["summary"] for section in report["sections"])
    assert "Deutschland-Baseline" in combined
    assert "Telemedizin" in combined
    assert "keine amtliche Prognose" in combined
