import pandas as pd

from simulation_core import get_default_params
from result_causality import build_causal_result_packet
from app import build_result_causal_overview


def _agg_frame():
    return pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "burnout_rate_mean": 12.0,
            "wartezeit_fa_mean": 25.0,
            "gkv_saldo_mean": -2.0,
            "telemedizin_rate_mean": 5.0,
            "versorgungsindex_rural_mean": 72.0,
        },
        {
            "jahr": 2032,
            "aerzte_pro_100k_mean": 415.0,
            "burnout_rate_mean": 16.0,
            "wartezeit_fa_mean": 31.0,
            "gkv_saldo_mean": -6.0,
            "telemedizin_rate_mean": 8.0,
            "versorgungsindex_rural_mean": 68.0,
        },
        {
            "jahr": 2041,
            "aerzte_pro_100k_mean": 360.0,
            "burnout_rate_mean": 23.0,
            "wartezeit_fa_mean": 45.0,
            "gkv_saldo_mean": -12.0,
            "telemedizin_rate_mean": 18.0,
            "versorgungsindex_rural_mean": 56.0,
        },
    ])


def test_causal_result_packet_prioritizes_relevant_kpis_and_coherent_freetext():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    assert packet["title"] == "Simulationsergebnis in Klartext"
    assert packet["relevant_kpis"][0]["metric_key"] in {"aerzte_pro_100k", "wartezeit_fa", "burnout_rate"}
    assert len(packet["relevant_kpis"]) <= 4
    assert "Medizinstudienplätze" in packet["coherent_story"]
    assert "ab etwa Jahr 6" in packet["coherent_story"]
    assert "Ärzte pro 100k" in packet["coherent_story"]
    assert "Burnout" in packet["coherent_story"]
    assert "Anpassungsmechanismen" in packet["coherent_story"]
    assert packet["reading_order"] == [
        "1 · geänderte Eingriffe",
        "2 · relevante KPIs",
        "3 · Wirkpfad und Timing",
        "4 · Anpassungsmechanismen",
        "5 · Gegencheck/Caveat",
    ]
    assert "keine random Internet-Suche" in packet["method_note"]


def test_app_causal_overview_reuses_packet_before_dense_kpi_wall():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    overview = build_result_causal_overview(_agg_frame(), params)

    assert overview["title"] == "Simulationsergebnis in Klartext"
    assert "Wenige relevante KPIs" in overview["subtitle"]
    assert len(overview["relevant_kpis"]) <= 5
    assert "KPI-Wand" not in overview["coherent_story"]
    assert "keine amtliche Prognose" in overview["guardrail"]


def test_causal_result_packet_flags_counterintuitive_burnout_drop_under_physician_shortage():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5
    agg = _agg_frame().copy()
    agg.loc[2, "burnout_rate_mean"] = 8.0

    packet = build_causal_result_packet(agg, params, max_kpis=4)

    findings = " ".join(item["finding"] for item in packet["counterintuitive_findings"])
    assert "Burnout sinkt trotz sinkender Arztkapazität" in findings
    assert "Telemedizin" in packet["counterintuitive_findings"][0]["possible_model_explanation"]
    assert "Mechanismus prüfen" in packet["counterintuitive_findings"][0]["operator_action"]


def test_causal_result_packet_contains_structured_story_sections_for_api_and_ui():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    assert [section["id"] for section in packet["story_sections"]] == [
        "output",
        "changed_inputs",
        "mechanisms",
        "adaptation",
        "counterintuitive_checks",
        "evidence_assumptions",
    ]
    section_text = " ".join(section["text"] for section in packet["story_sections"])
    assert "wenige relevante KPIs" in section_text
    assert "Medizinstudienplätze" in section_text
    assert "ab etwa Jahr 6" in section_text
    assert "keine amtliche Prognose" in packet["story_sections"][-1]["text"]
