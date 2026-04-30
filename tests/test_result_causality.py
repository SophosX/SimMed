import pandas as pd

from simulation_core import get_default_params
from result_causality import build_causal_result_packet, build_causal_result_layout
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

    assert packet["title"] == "Ergebnisbericht"
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
    assert "dokumentierten Parametern" in packet["method_note"]
    assert "random Internet" not in packet["method_note"]
    assert "Klartext" not in packet["method_note"]


def test_app_causal_overview_reuses_packet_before_dense_kpi_wall():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    overview = build_result_causal_overview(_agg_frame(), params)

    assert overview["title"] == "Ergebnisbericht"
    assert "Relevante Kennzahlen" in overview["subtitle"]
    assert len(overview["relevant_kpis"]) <= 5
    assert "KPI-Wand" not in overview["coherent_story"]
    assert "nicht als amtliche Prognose" in overview["guardrail"]
    assert overview["timeline_windows"][0]["window"] == "Jahr 0–5"


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
    assert "relevante Kennzahlen" in section_text
    assert "Medizinstudienplätze" in section_text
    assert "ab etwa Jahr 6" in section_text
    assert "Belastbarkeit" in packet["story_sections"][-1]["heading"]
    assert "Datenlage" in packet["story_sections"][-1]["text"]


def test_causal_result_packet_exposes_delayed_timeline_windows_for_study_place_cut():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    windows = packet["timeline_windows"]
    assert [row["window"] for row in windows] == ["Jahr 0–5", "Jahr 6–10", "Jahr 11–15"]
    assert "kein unmittelbarer Kapazitäts-Crash" in windows[0]["expected_signal"]
    assert "weniger Absolvent" in windows[1]["expected_signal"]
    assert "Facharzt" in windows[2]["expected_signal"]
    assert "Burnout" in windows[2]["pressure_check"]
    assert "Telemedizin" in windows[1]["adaptation_to_check"]
    assert "nicht amtliche Prognosen" in windows[0]["guardrail"]
    assert "Jahr 6–10" in packet["coherent_story"]


def test_causal_result_packet_has_sequential_free_text_blocks_before_optional_details():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    blocks = packet["free_text_blocks"]
    assert [block["step"] for block in blocks] == [
        "1. Ergebnis",
        "2. Änderung",
        "3. Wirkmechanismus",
        "4. Anpassung",
        "5. Plausibilitätsprüfung",
        "6. Einordnung und Belastbarkeit",
    ]
    combined = " ".join(block["text"] for block in blocks)
    assert "Ärzte pro 100k" in combined
    assert "Medizinstudienplätze" in combined
    assert "Ausbildungs-Pipeline" in combined
    assert "Telemedizin" in combined
    assert "Belastbarkeit" in combined
    assert "random Internet" not in combined
    assert "Klartext" not in combined
    assert all("KPI-Wand" not in block["text"] for block in blocks)
    primary = packet["primary_result_view"]
    assert primary["headline"] == "Ergebnisbericht und anschließende Detailprüfung"
    assert primary["main_blocks"] == blocks
    assert primary["sequential_plain_text"] == packet["sequential_plain_text"]
    assert primary["relevant_kpis"] == packet["relevant_kpis"]
    assert primary["relevant_kpi_summary"] == packet["relevant_kpi_summary"]
    assert primary["adaptation_signal_trace"] == packet["adaptation_signal_trace"]
    assert primary["evidence_assumption_rows"] == packet["evidence_assumption_rows"]
    assert primary["optional_details_after"] == ["KPI-Drilldowns", "Trend", "Policy-Briefing", "Politik/Stakeholder"]


def test_causal_result_packet_exposes_one_sequential_plain_text_story_for_api_clients():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    story = packet["sequential_plain_text"]
    assert story.startswith("Ergebnisbericht")
    assert story.count("\n\n") >= 5
    assert story.index("1. Ergebnis") < story.index("2. Änderung") < story.index("3. Wirkmechanismus")
    assert story.index("3. Wirkmechanismus") < story.index("4. Anpassung") < story.index("5. Plausibilitätsprüfung")
    assert "Medizinstudienplätze" in story
    assert "ab etwa Jahr 6" in story
    assert "Jahr 11–15" in story
    assert "Datenlage" in story
    assert "random Internet" not in story
    assert "Klartext" not in story
    assert "keine freie Web-Recherche" not in story
    assert "KPI-Wand" not in story
    assert packet["primary_result_view"]["sequential_plain_text"] == story


def test_causal_result_packet_exposes_changed_lever_evidence_and_assumption_limits():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    evidence_rows = packet["evidence_assumption_rows"]
    medical_row = next(row for row in evidence_rows if row["parameter_key"] == "medizinstudienplaetze")
    assert medical_row["evidence_grade"] == "A"
    assert medical_row["source_ids"]
    assert "6" in medical_row["model_role"] or "6" in medical_row["caveat"]
    assert "Annahme" in medical_row["interpretation_limit"]
    assert "Evidenzgrad A" in packet["sequential_plain_text"]
    assert "medizinstudienplaetze" in packet["primary_result_view"]["evidence_assumption_rows"][0]["parameter_key"]


def test_causal_result_packet_explains_why_each_relevant_kpi_was_selected():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    rows = packet["relevant_kpi_summary"]
    assert len(rows) == len(packet["relevant_kpis"])
    first = rows[0]
    assert {"metric_key", "label", "answer_signal", "why_selected", "mechanism_link", "next_check"} <= set(first)
    combined = " ".join(row["why_selected"] + " " + row["mechanism_link"] for row in rows)
    assert "Medizinstudienplätze" in combined
    assert "Ausbildungs-Pipeline" in combined
    assert "Wartezeit" in combined or "Burnout" in combined
    assert packet["primary_result_view"]["relevant_kpi_summary"] == rows
    assert "Ergebnisbericht" in rows[0]["next_check"]
    assert "KPI-Wand" not in rows[0]["next_check"]


def test_causal_result_packet_traces_observed_adaptation_signals_inside_main_story():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    trace = packet["adaptation_signal_trace"]
    assert trace
    telemedicine = next(row for row in trace if row["signal_key"] == "telemedizin_rate")
    burnout = next(row for row in trace if row["signal_key"] == "burnout_rate")
    assert telemedicine["observed_direction"] == "steigt"
    assert "dämpfender Mechanismus" in telemedicine["plain_interpretation"]
    assert burnout["observed_direction"] == "steigt"
    assert "Drucksignal" in burnout["plain_interpretation"]
    assert "nicht eine amtliche Prognose" in telemedicine["guardrail"]
    assert packet["primary_result_view"]["adaptation_signal_trace"] == trace
    assert "Telemedizin steigt" in packet["sequential_plain_text"]
    assert "Burnout steigt" in packet["sequential_plain_text"]


def test_causal_result_packet_builds_cleartext_reading_cards_for_first_view():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    cards = packet["primary_result_view"]["cleartext_reading_cards"]
    assert [card["stage"] for card in cards] == [
        "Ergebnis",
        "Änderung",
        "Wirkmechanismus",
        "Anpassung",
        "Gegencheck",
        "Evidenzgrenze",
    ]
    assert cards[0]["answer_first"].startswith("Der Lauf wird zuerst")
    assert cards[2]["audit_focus"] == "Zeitfenster 0–5 / 6–10 / 11–15 prüfen"
    assert "Telemedizin" in cards[3]["audit_focus"]
    assert "nicht als amtliche Prognose" in cards[-1]["guardrail"]
    assert packet["primary_result_view"]["adaptation_mechanisms"] == packet["adaptation_mechanisms"]
    assert packet["primary_result_view"]["timeline_windows"] == packet["timeline_windows"]


def test_causal_result_layout_keeps_dense_kpis_optional_after_cleartext():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5
    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    layout = build_causal_result_layout(packet)

    assert layout["first_view"] == "Ergebnisbericht"
    assert layout["primary_sequence"] == [
        "coherent_free_text",
        "relevant_kpis",
        "adaptation_mechanisms",
        "counterintuitive_checks",
        "evidence_assumptions",
    ]
    assert layout["dense_kpi_wall"]["mode"] == "optional_expander_after_causal_story"
    assert layout["dense_kpi_wall"]["default_expanded"] is False
    assert "nachgeordnet" in layout["dense_kpi_wall"]["reason"]
    assert "Detailkarten" in layout["dense_kpi_wall"]["label"]
    assert "KPI-Wand" not in layout["dense_kpi_wall"]["label"]
    assert layout["optional_interpretation_layers"]["mode"] == "collapsed_after_primary_causal_packet"
    assert layout["optional_interpretation_layers"]["default_expanded"] is False
    assert layout["optional_interpretation_layers"]["sections"] == [
        "Narrative Zusammenfassung",
        "Entscheidungs-Checkpoints",
        "Storyboard",
        "Unsicherheitsband",
    ]
    assert "keine zweite erste Ergebnisansicht" in layout["optional_interpretation_layers"]["reason"]
    assert "Klartext" not in layout["optional_interpretation_layers"]["reason"]
    assert layout["guardrail"] == packet["guardrail"]
