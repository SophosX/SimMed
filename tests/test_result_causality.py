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


def _public_text(packet):
    parts = [packet.get("result_headline", ""), packet.get("short_answer", ""), packet.get("follow_up_question", "")]
    parts.extend(section.get("body", "") for section in packet.get("result_sections", []))
    parts.extend(row.get("meaning", "") for row in packet.get("relevant_kpis", []))
    return "\n".join(parts)


def test_simplified_public_result_packet_is_short_clear_and_not_meta():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    first_screen = packet["public_result_view"]["first_screen_blocks"]
    assert [block["heading"] for block in first_screen] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert all(len(block["body"]) <= 320 for block in first_screen)
    assert first_screen[0]["primary_answer"] is True
    assert all(block["display"] in {"text", "kpi_rows"} for block in first_screen)
    assert packet["result_headline"].startswith("Weniger Medizinstudienplätze")
    assert packet["public_result_view"]["render_order"] == [
        "result_headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_audit_sections",
    ]
    assert [section["heading"] for section in packet["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(packet["result_sections"]) <= 7
    assert all(len(section["body"]) <= 260 for section in packet["result_sections"])
    assert all(section["body"].count(".") <= 2 for section in packet["result_sections"] if section["heading"] != "Eingriff")
    assert len(packet["short_answer"]) <= 520
    section_by_heading = {section["heading"]: section["body"] for section in packet["result_sections"]}
    assert section_by_heading["Ergebnis"] != packet["result_headline"]
    assert "Kapazitätsdruck" in section_by_heading["Ergebnis"]
    assert "→" not in section_by_heading["Ergebnis"]
    assert "Ärzte pro 100k" in section_by_heading["Relevante Kennzahlen"]
    assert "Facharzt-Wartezeit" in section_by_heading["Relevante Kennzahlen"]
    assert "Ab etwa Jahr 6" in section_by_heading["Warum es passiert"]
    assert "bedeutet" in section_by_heading["Einordnung"].lower()
    assert "Detailkarten" not in packet["short_answer"]
    text = _public_text(packet)
    for banned in ["random Internet", "Klartext", "KPI-Wand", "generated", "helper", "Meta", "Zahlenwand"]:
        assert banned not in text
    assert "Medizinstudienplätze" in packet["short_answer"]
    assert "Ärzte pro 100k" in packet["short_answer"]
    assert "Facharzt-Wartezeit" in packet["short_answer"]
    assert "ab etwa Jahr 6" in packet["short_answer"]
    assert "nächste" in packet["short_answer"].lower()
    assert "Das bedeutet" in packet["short_answer"]
    assert "prüfbaren" in section_by_heading["Einordnung"]


def test_public_result_view_has_single_follow_up_rendering_instruction():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]

    assert view["render_follow_up_after_sections"] is False
    section_by_heading = {section["heading"]: section["body"] for section in view["result_sections"]}
    assert "Nächster Prüfschritt" in section_by_heading
    assert view["follow_up_question"] == packet["follow_up_question"]
    assert section_by_heading["Nächster Prüfschritt"] != view["follow_up_question"]


def test_relevant_kpis_are_public_rows_with_plain_change_and_reading():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    rows = packet["public_result_view"]["relevant_kpis"]

    assert rows
    assert all("plain_change" in row for row in rows)
    assert all("reading" in row for row in rows)
    assert all(len(row["reading"].split()) <= 18 for row in rows)
    assert rows[0]["plain_change"].startswith("430,00 auf 360,00")
    assert rows[0]["reading"] == "Weniger Kapazität: Zugang und Belastung danach gemeinsam prüfen."


def test_public_adaptation_section_is_not_truncated_mid_sentence():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    section_by_heading = {section["heading"]: section["body"] for section in packet["result_sections"]}
    adaptation = section_by_heading["Anpassungen"]
    why = section_by_heading["Warum es passiert"]

    assert "beobachtet: Telemedizin steigt; Burnout steigt" in adaptation
    assert "dämpfender M" not in adaptation
    assert " M Fällt" not in adaptation
    assert adaptation.endswith("Plausibilitätscheck.")
    assert all(section["body"].endswith((".", "?", "!")) for section in packet["result_sections"])
    assert why.startswith("Der Eingriff wirkt verzögert: In Jahr 0–5")
    assert "Ab etwa Jahr 6" in why


def test_public_briefing_uses_clean_german_number_and_input_phrasing():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    section_by_heading = {section["heading"]: section["body"] for section in packet["result_sections"]}
    public_text = _public_text(packet)

    assert "Medizinstudienplätze wurden gesenkt" in section_by_heading["Eingriff"]
    assert "11.000 → 5.500" in section_by_heading["Eingriff"]
    assert "5500.0" not in public_text
    assert "430,00 → 360,00" in public_text
    assert "25,00 → 45,00" in public_text
    assert "wurde gesenkt" not in section_by_heading["Eingriff"]


def test_public_result_view_separates_briefing_from_collapsed_audit_layers():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]

    assert view["briefing_style"] == "single_readable_briefing"
    assert view["deeper_review_default_expanded"] is False
    assert [section["id"] for section in view["audit_sections"]] == [
        "mechanism_audit",
        "evidence_audit",
        "legacy_details",
    ]
    assert all(section["default_expanded"] is False for section in view["audit_sections"])
    assert all("Ergebnis" not in section["title"] for section in view["audit_sections"])
    assert any("Zeitfenster" in section["contains"] for section in view["audit_sections"])
    assert any("vollständige Kennzahlen" in section["contains"] for section in view["audit_sections"])
    assert "collapsed_audit_sections" in view["render_order"]


def test_first_result_view_has_one_sequential_briefing_with_kpis_in_place():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]
    blocks = view["first_screen_blocks"]

    assert len(blocks) == 7
    assert [block["heading"] for block in blocks] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    kpi_block = blocks[3]
    assert kpi_block["display"] == "kpi_rows"
    assert kpi_block["kpi_refs"] == [row["metric_key"] for row in view["relevant_kpis"]]
    assert "Ärzte pro 100k" in kpi_block["body"]
    assert "Facharzt-Wartezeit" in kpi_block["body"]
    assert "erste Befund" not in kpi_block["body"]
    assert view["briefing_style"] == "single_readable_briefing"
    assert view["primary_blocks"] == blocks
    assert "briefing_summary" not in view
    assert "sections" not in view


def test_public_result_packet_is_minimal_and_does_not_expose_legacy_layers_first():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]

    allowed_public_keys = {
        "briefing_style",
            "render_order",
            "first_screen_policy",
            "headline",
            "briefing_markdown",
            "executive_brief",
            "short_answer",
        "result_sections",
        "first_screen_blocks",
        "primary_blocks",
        "relevant_kpis",
        "follow_up_question",
        "render_follow_up_after_sections",
        "audit_sections",
        "deeper_review_default_expanded",
        "legacy_detail_default_expanded",
        "dense_kpi_default_expanded",
        "audit_expanders",
        "guardrail",
    }
    assert set(view) == allowed_public_keys
    assert view["primary_blocks"] == view["first_screen_blocks"]
    assert all(len(section["body"].split()) <= 38 for section in packet["result_sections"])
    assert packet["short_answer"].count(".") <= 4
    public_text = _public_text(packet)
    for forbidden in ["erste Ansicht", "Detailkarten", "Audit-Layer", "Systemnotizen", "zusammengeklebte"]:
        assert forbidden not in public_text


def test_result_quality_check_uses_public_language_not_internal_process_words():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    quality_text = "\n".join(
        f"{row.get('check', '')} {row.get('evidence', '')} {row.get('why_it_matters', '')}"
        for row in packet.get("briefing_quality_checks", [])
    )

    assert "Professionelle Sprache" in quality_text
    for forbidden in ["Meta", "generated", "helper", "random Internet", "KPI-Wand", "Klartext"]:
        assert forbidden not in quality_text
    assert "Prozessfloskeln" in quality_text


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
    assert len(overview["relevant_kpis"]) <= 4
    assert "KPI-Wand" not in overview["coherent_story"]
    assert "nicht als amtliche Prognose" in overview["guardrail"]
    assert overview["timeline_windows"][0]["window"] == "Jahr 0–5"


def test_professional_briefing_is_single_human_readable_flow_with_consequence_section():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    briefing = packet["professional_briefing"]

    headings = [section["heading"] for section in briefing["sections"]]
    assert headings == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung und Belastbarkeit",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    text = briefing["sequential_text"]
    assert text.index("Ausgangslage") < text.index("Eingriff") < text.index("Berechnete Wirkpfade")
    assert text.index("Relevante Kennzahlen") < text.index("Anpassungsreaktionen") < text.index("Einordnung und Belastbarkeit")
    assert text.index("Was daraus folgt") < text.index("Nächste Prüfentscheidung")
    assert "KPI-Wand" not in text
    assert "random Internet" not in text
    assert "Klartext" not in text
    assert "prüfen" in text


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
    assert primary["headline"] == packet["result_headline"]
    assert primary["short_answer"] == packet["short_answer"]
    assert primary["main_blocks"] == blocks
    assert primary["sequential_plain_text"] == packet["sequential_plain_text"]
    assert primary["relevant_kpis"] == packet["relevant_kpis"]
    assert primary["relevant_kpi_summary"] == packet["relevant_kpi_summary"]
    assert primary["adaptation_signal_trace"] == packet["adaptation_signal_trace"]
    assert primary["evidence_assumption_rows"] == packet["evidence_assumption_rows"]
    assert primary["optional_details_after"] == [
        "Kennzahlen im Detail",
        "Zeitverlauf",
        "Bericht mit Annahmen und Quellen",
        "politische Einordnung",
    ]


def test_causal_result_packet_exposes_one_sequential_plain_text_story_for_api_clients():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    story = packet["sequential_plain_text"]
    assert story.startswith("Ergebnisbericht")
    assert story.count("\n\n") >= 5
    assert story.index("Ausgangslage") < story.index("Eingriff") < story.index("Berechnete Wirkpfade")
    assert story.index("Berechnete Wirkpfade") < story.index("Relevante Kennzahlen") < story.index("Anpassungsreaktionen")
    assert story.index("Anpassungsreaktionen") < story.index("Einordnung und Belastbarkeit") < story.index("Nächste Prüfentscheidung")
    assert "Medizinstudienplätze" in story
    assert "ab Jahr 6" in story
    assert "Jahr 11–15" in story
    assert "Datenlage" in packet["legacy_numbered_story"]
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
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert layout["dense_kpi_wall"]["mode"] == "collapsed_after_result_briefing"
    assert layout["dense_kpi_wall"]["default_expanded"] is False
    assert "unter der ersten Lesefassung" in layout["dense_kpi_wall"]["reason"]
    assert "Weitere Kennzahlen" in layout["dense_kpi_wall"]["label"]
    assert "KPI-Wand" not in layout["dense_kpi_wall"]["label"]
    assert layout["optional_interpretation_layers"]["mode"] == "collapsed_after_result_briefing"
    assert layout["optional_interpretation_layers"]["default_expanded"] is False
    assert layout["optional_interpretation_layers"]["sections"] == [
        "Narrative Zusammenfassung",
        "Entscheidungs-Checkpoints",
        "Storyboard",
        "Unsicherheitsband",
    ]
    assert "mehrere konkurrierende Erklärblöcke" in layout["optional_interpretation_layers"]["reason"]
    assert "Klartext" not in layout["optional_interpretation_layers"]["reason"]
    assert layout["guardrail"] == packet["guardrail"]


def test_causal_result_packet_reads_like_professional_sequential_briefing():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    briefing = packet["professional_briefing"]
    headings = [section["heading"] for section in briefing["sections"]]
    assert headings == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung und Belastbarkeit",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    text = briefing["sequential_text"]
    assert text.startswith("Ergebnisbericht\n\nAusgangslage")
    assert text.index("Ausgangslage") < text.index("Eingriff") < text.index("Berechnete Wirkpfade")
    assert text.index("Berechnete Wirkpfade") < text.index("Relevante Kennzahlen") < text.index("Anpassungsreaktionen")
    assert text.index("Anpassungsreaktionen") < text.index("Einordnung und Belastbarkeit") < text.index("Nächste Prüfentscheidung")
    assert "Medizinstudienplätze" in text
    assert "Jahr 6" in text
    assert "Jahr 11" in text
    assert "Telemedizin" in text
    assert "Burnout" in text
    assert "Modelllauf" in text
    assert "nächste" in briefing["sections"][-1]["body"].lower()
    assert "random Internet" not in text
    assert "Klartext" not in text
    assert "KPI-Wand" not in text
    assert packet["primary_result_view"]["professional_briefing"] == briefing


def test_professional_briefing_has_human_first_view_kpi_cards_without_meta_table_language():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    briefing = packet["professional_briefing"]
    assert briefing["lead_paragraph"].startswith("Dieser Lauf wird als Wirkungskette")
    assert "wenige relevante Kennzahlen" in briefing["lead_paragraph"]
    assert "erst ab Jahr 6" in briefing["lead_paragraph"]
    assert briefing["section_flow"] == [
        "Ausgangslage",
        "Eingriff",
        "berechneter Wirkpfad",
        "relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung",
        "nächste Prüfentscheidung",
    ]
    assert packet["primary_result_view"]["lead_paragraph"] == briefing["lead_paragraph"]
    cards = briefing["first_view_kpi_cards"]
    assert 1 <= len(cards) <= 4
    assert {
        "label",
        "movement",
        "value_line",
        "interpretation_tone",
        "why_it_matters",
        "what_to_check_next",
    } <= set(cards[0])
    assert any(card["label"] == "Facharzt-Wartezeit" for card in cards)
    assert any("Ausbildungs-Pipeline" in card["why_it_matters"] for card in cards)
    assert any(card["interpretation_tone"] in {"eher belastend", "eher entlastend"} for card in cards)
    assert all("→" in card["value_line"] for card in cards)
    combined = " ".join(
        card["movement"] + " " + card["value_line"] + " " + card["why_it_matters"] + " " + card["what_to_check_next"]
        for card in cards
    )
    assert "answer_first" not in combined
    assert "Audit" not in combined
    assert "Lesekarten" not in combined
    assert "KPI-Wand" not in combined
    assert packet["primary_result_view"]["first_view_kpi_cards"] == cards


def test_primary_result_view_declares_single_sequential_briefing_before_optional_audit_layers():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    first_view = packet["primary_result_view"]

    assert first_view["render_sequence"] == [
        "headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_detailprüfung",
    ]
    assert first_view["first_view_briefing_cards"][0]["stage"] == "Ausgangslage"
    assert first_view["next_check"]["label"] == "Nächster Prüfschritt"
    assert first_view["next_check"]["text"] == first_view["follow_up_question"]
    assert "Puffer" in first_view["next_check"]["text"] or "Kapazitätslücke" in first_view["next_check"]["text"]
    assert first_view["optional_audit_layers"]["expanded_by_default"] is False
    assert first_view["optional_audit_layers"]["reason"].startswith("Detailprüfungen bleiben verfügbar")
    assert "keine zweite erste Ergebnisansicht" not in first_view["optional_audit_layers"]["reason"]


def test_professional_briefing_exposes_human_reader_brief_without_table_first_language():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    briefing = packet["professional_briefing"]

    assert briefing["reader_brief"].startswith("Ausgangslage: ")
    assert "\n\nEingriff: " in briefing["reader_brief"]
    assert "\n\nBerechnete Wirkpfade: " in briefing["reader_brief"]
    assert "\n\nRelevante Kennzahlen: " in briefing["reader_brief"]
    assert "\n\nAnpassungsreaktionen: " in briefing["reader_brief"]
    assert "\n\nEinordnung und Belastbarkeit: " in briefing["reader_brief"]
    assert "\n\nWas daraus folgt: " in briefing["reader_brief"]
    assert "\n\nNächste Prüfentscheidung: " in briefing["reader_brief"]
    assert "Tabelle" not in briefing["reader_brief"]
    assert "DataFrame" not in briefing["reader_brief"]
    assert "KPI-Wand" not in briefing["reader_brief"]
    assert packet["primary_result_view"]["professional_briefing_text"] == briefing["reader_brief"]


def test_public_result_view_provides_one_readable_briefing_markdown_without_duplicate_first_views():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]
    briefing = view["briefing_markdown"]

    assert briefing.startswith("### Weniger Medizinstudienplätze")
    assert briefing.count("#### Ergebnis") == 1
    assert briefing.count("#### Eingriff") == 1
    assert briefing.count("#### Warum es passiert") == 1
    assert briefing.count("#### Relevante Kennzahlen") == 1
    assert briefing.count("#### Anpassungen") == 1
    assert briefing.count("#### Einordnung") == 1
    assert briefing.count("#### Nächster Prüfschritt") == 1
    assert "Medizinstudienplätze" in briefing
    assert "ab etwa Jahr 6" in briefing
    assert "Ärzte pro 100k" in briefing
    assert "Facharzt-Wartezeit" in briefing
    assert "Vertiefung" not in briefing
    assert "Audit" not in briefing
    assert "helper" not in briefing.lower()
    assert view["first_screen_policy"] == "one_briefing_then_collapsed_audit"
    assert view["legacy_detail_default_expanded"] is False
    assert view["dense_kpi_default_expanded"] is False


def test_public_result_packet_is_short_clear_and_not_a_legacy_helper_dump():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    public_text = "\n".join(
        [packet["result_headline"], packet["short_answer"], packet["follow_up_question"]]
        + [section["heading"] + "\n" + section["body"] for section in packet["result_sections"]]
        + [row["label"] + "\n" + row["meaning"] for row in packet["relevant_kpis"]]
    )

    assert [section["heading"] for section in packet["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(packet["result_sections"]) <= 7
    assert all(len(section["body"]) <= 280 for section in packet["result_sections"])
    assert "Medizinstudienplätze" in packet["short_answer"]
    assert "ab etwa Jahr 6" in packet["short_answer"]
    assert any(row["label"] in packet["short_answer"] for row in packet["relevant_kpis"][:2])
    public_view = packet["public_result_view"]
    assert public_view["render_order"] == [
        "result_headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_audit_sections",
    ]
    assert public_view["first_screen_blocks"][0]["heading"] == "Ergebnis"
    assert "professional_briefing" not in public_view
    assert "legacy_numbered_story" not in public_view
    for banned in [
        "random Internet",
        "Klartext",
        "KPI-Wand",
        "generated",
        "helper",
        "Legacy",
        "DataFrame",
        "zweite erste Ergebnisansicht",
    ]:
        assert banned not in public_text


def test_professional_briefing_does_not_invent_study_place_path_when_no_lever_changed():
    params = get_default_params()

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    text = packet["professional_briefing"]["sequential_text"]

    assert "Keine zentrale Stellschraube" in text
    assert "Medizinstudienplätze wurde" not in text
    assert "Bei weniger Medizinstudienplätzen" not in text
    assert "ab Jahr 6 erreicht die kleinere Kohorte" not in text
    assert packet["timeline_windows"] == []
    assert packet["adaptation_mechanisms"] == []
    assert packet["primary_result_view"]["next_check"]["label"] == "Nächster Prüfschritt"


def test_financing_scenario_prioritizes_finance_kpis_without_pipeline_language():
    params = get_default_params()
    params["gkv_beitragssatz"] = params["gkv_beitragssatz"] + 1.0

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    kpi_keys = [row["metric_key"] for row in packet["relevant_kpis"]]
    briefing_text = packet["professional_briefing"]["sequential_text"]
    public_text = " ".join([
        packet["coherent_story"],
        packet["public_briefing_text"],
        packet["professional_briefing"]["reader_summary"],
        packet["policy_readiness_summary"]["why"],
    ])

    assert kpi_keys[0] == "gkv_saldo"
    assert "GKV-Saldo" in packet["relevant_kpis"][0]["label"]
    assert "Medizinstudienplätze" not in briefing_text
    assert "Medizinstudienplätze" not in public_text
    assert "Ausbildungs-Pipeline" not in briefing_text
    assert "Ausbildungs-Lag" not in public_text
    assert "Finanzierung" in briefing_text
    assert "Kapazitätsdruck" not in packet["professional_briefing"]["sections"][6]["body"]
    assert packet["timeline_windows"] == []
    assert packet["adaptation_signal_trace"] == []


def test_result_briefing_quality_check_guards_first_view_style_and_sequence():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    checks = packet["briefing_quality_checks"]

    assert [check["check"] for check in checks] == [
        "Ein roter Faden",
        "Wenige relevante KPIs",
        "Anpassung sichtbar",
        "Professionelle Sprache",
        "Belastbarkeit begrenzt",
    ]
    assert all(check["status"] == "erfüllt" for check in checks)
    combined = " ".join(check["evidence"] + " " + check["why_it_matters"] for check in checks)
    assert "Ausgangslage → Eingriff → Wirkpfad" in combined
    assert "4 relevante Kennzahlen" in combined
    assert "Telemedizin" in combined and "Burnout" in combined
    assert "keine amtliche Prognose" in combined
    assert "random Internet" not in combined
    assert "Klartext" not in combined
    assert packet["primary_result_view"]["briefing_quality_checks"] == checks


def test_causal_result_packet_exposes_compact_briefing_cards_for_first_view():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    cards = packet["first_view_briefing_cards"]

    assert [card["stage"] for card in cards] == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung und Belastbarkeit",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    assert packet["primary_result_view"]["first_view_briefing_cards"] == cards
    assert all(card["answer"] and len(card["answer"]) <= 360 for card in cards)
    assert all(card["why_it_matters"] and card["next_step"] for card in cards)
    combined = " ".join(card["answer"] + " " + card["why_it_matters"] + " " + card["next_step"] for card in cards)
    assert "ab Jahr 6" in combined
    assert "Telemedizin" in combined and "Burnout" in combined
    assert "keine amtliche Prognose" in combined
    assert "random Internet" not in combined
    assert "Klartext" not in combined


def test_simplified_public_causal_packet_is_concise_and_serious():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    public = packet["public_result_view"]
    public_text = " ".join(
        [
            packet["result_headline"],
            packet["short_answer"],
            public["headline"],
            public["short_answer"],
            public.get("follow_up_question", ""),
        ]
        + [section["heading"] + " " + section["body"] for section in packet["result_sections"]]
        + [row["label"] + " " + row.get("meaning", "") for row in packet["relevant_kpis"]]
    )

    assert packet["result_headline"] == public["headline"]
    assert packet["short_answer"] == public["short_answer"]
    assert packet["primary_result_view"]["headline"] == packet["result_headline"]
    assert packet["primary_result_view"]["short_answer"] == packet["short_answer"]
    assert [section["heading"] for section in packet["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(packet["result_sections"]) <= 7
    assert all(len(section["body"]) <= 300 for section in packet["result_sections"])
    assert len(packet["short_answer"].split(". ")) <= 4
    assert "Medizinstudienplätze" in packet["short_answer"]
    assert "Jahr 6" in packet["short_answer"] and "Jahr 11" in packet["short_answer"]
    assert "Wartezeit" in public_text or "Ärzte" in public_text
    assert "Puffer" in packet["follow_up_question"] or "Kapazitätslücke" in packet["follow_up_question"]
    banned_terms = [
        "random Internet",
        "Klartext",
        "KPI-Wand",
        "causal_result_packet",
        "generated",
        "helper",
        "Audit-Layer",
        "Kurz gesagt",
        "Zahlen zu tapezieren",
        "Relevante KPIs",
        "KPI-Drilldowns",
        "KPI-Karten",
    ]
    for term in banned_terms:
        assert term not in public_text
    assert "Kennzahlen" in public_text
    assert packet["public_result_view"]["briefing_markdown"].count("####") == len(packet["result_sections"])
    assert "#### Ergebnis\n\n" in packet["public_result_view"]["briefing_markdown"]
    assert "#### Relevante Kennzahlen" in packet["public_result_view"]["briefing_markdown"]
    assert all("KPI" not in section["heading"] for section in packet["result_sections"])


def test_public_result_view_declares_one_non_duplicative_first_screen_flow():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]

    assert view["briefing_style"] == "single_readable_briefing"
    assert view["render_order"] == [
        "result_headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_audit_sections",
    ]
    assert "briefing_markdown" not in view["render_order"]
    assert view["deeper_review_default_expanded"] is False
    assert view["dense_kpi_default_expanded"] is False
    assert len(view["audit_sections"]) == 3


def test_primary_result_view_uses_plain_public_language_without_legacy_kpi_jargon():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    primary = packet["primary_result_view"]
    public = packet["public_result_view"]
    public_payload = " ".join(
        [
            primary["headline"],
            primary["short_answer"],
            primary["next_check"]["label"],
            primary["next_check"]["text"],
            public["briefing_markdown"],
        ]
        + [section["heading"] + " " + section["body"] for section in primary["result_sections"]]
        + [block["heading"] + " " + block["body"] for block in primary["first_screen_blocks"]]
        + [section["heading"] + " " + section["body"] for section in packet["professional_briefing"]["sections"]]
    )

    assert "Relevante Kennzahlen" in public_payload
    assert "Relevante KPIs" not in public_payload
    assert "KPI-" not in public_payload
    assert "Audit-Layer" not in public_payload
    assert "helper" not in public_payload
    assert len(primary["result_sections"]) <= 7
    assert all(len(section["body"]) <= 300 for section in primary["result_sections"])
    assert primary["audit_sections"] == public["audit_sections"]


def test_first_view_public_copy_avoids_internal_packet_and_wall_jargon():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    layout = build_causal_result_layout(packet)

    public_fragments = [
        packet["professional_briefing"]["lead_paragraph"],
        packet["primary_result_view"]["headline"],
        packet["primary_result_view"]["optional_audit_layers"]["reason"],
        layout["dense_kpi_wall"]["label"],
        layout["dense_kpi_wall"]["reason"],
        layout["optional_interpretation_layers"]["label"],
        layout["optional_interpretation_layers"]["reason"],
    ]
    public_fragments.extend(card["next_step"] for card in packet["first_view_briefing_cards"])
    public_text = " ".join(public_fragments)

    assert "causal_result_packet" not in public_text
    assert "KPI-Wand" not in public_text
    assert "answer_first" not in public_text
    assert "Audit-Layer" not in public_text
    assert "Ergebnisbericht" in public_text
    assert "Detailprüfung" in public_text
    assert "Kurz gesagt" not in public_text
    assert "Zahlen zu tapezieren" not in public_text


def test_public_result_view_is_one_short_briefing_without_duplicate_opening_widgets():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    public = packet["public_result_view"]

    assert public["briefing_style"] == "single_readable_briefing"
    assert public["render_order"] == [
        "result_headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_audit_sections",
    ]
    assert [section["heading"] for section in public["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(public["result_sections"]) <= 7
    assert all(len(section["body"]) <= 260 for section in public["result_sections"])
    assert public["legacy_detail_default_expanded"] is False
    assert public["dense_kpi_default_expanded"] is False
    text = " ".join(
        [public["headline"], public["short_answer"], public["follow_up_question"]]
        + [section["heading"] + " " + section["body"] for section in public["result_sections"]]
    )
    assert "Medizinstudienplätze" in text
    assert "Wartezeit" in text or "Ärzte" in text
    assert "ab etwa Jahr 6" in text
    assert "keine amtliche Prognose" in text
    for term in ["random Internet", "Klartext", "KPI-Wand", "generated", "helper", "Audit-Layer", "Kurz gesagt", "Zahlen zu tapezieren"]:
        assert term not in text


def test_public_result_view_uses_kennzahlen_not_kpi_jargon_in_visible_copy():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    public = packet["public_result_view"]

    def collect_strings(value):
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for nested in value.values() for item in collect_strings(nested)]
        if isinstance(value, list):
            return [item for nested in value for item in collect_strings(nested)]
        return []

    visible_text = " ".join(collect_strings(public))
    assert "Kennzahlen" in visible_text
    assert "KPI" not in visible_text
    assert "Detailkarten" not in visible_text


def test_causal_result_layout_uses_reader_friendly_detail_labels_without_kpi_jargon():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    layout = build_causal_result_layout(packet)
    detail_text = " ".join(layout.get("optional_details_after", []))

    assert layout["first_view"] == "Ergebnisbericht"
    assert "Kennzahlen" in detail_text
    assert "KPI" not in detail_text
    assert "Detailkarten" not in detail_text
    assert "Policy-Briefing" not in detail_text
    assert "Ergebnisbericht" in layout["dense_kpi_wall"]["label"]


def test_professional_briefing_exposes_single_public_storyline_for_first_result_view():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    briefing = packet["professional_briefing"]
    storyline = briefing["public_storyline"]

    assert storyline.startswith("Ergebnisbericht\n\nAusgangslage\n")
    expected_order = [
        "Ausgangslage",
        "Eingriff",
        "Wirkpfad der Simulation",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    positions = [storyline.index(heading) for heading in expected_order]
    assert positions == sorted(positions)
    assert storyline.count("Einordnung\n") == 1
    assert "Warum das wichtig ist:" not in storyline
    assert "Kurz gesagt:" not in storyline
    assert "random Internet" not in storyline
    assert "KPI-Wand" not in storyline
    assert "causal_result_packet" not in storyline
    assert "Medizinstudienplätze" in storyline
    assert "Jahr 6" in storyline and "Jahr 11" in storyline
    assert "Telemedizin" in storyline and "Burnout" in storyline
    assert packet["primary_result_view"]["public_storyline"] == storyline


def test_causal_packet_has_plain_consequence_and_readiness_summary_for_first_view():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    summary = packet["policy_readiness_summary"]

    assert summary["headline"] == "Was daraus folgt"
    assert summary["current_read"] in {"prüfpflichtig", "beobachten", "belastbar innerhalb der Modellannahmen"}
    assert "Medizinstudienplätze" in summary["why"]
    assert "ab Jahr 6" in summary["why"]
    assert "Telemedizin" in summary["before_decision"]
    assert "Burnout" in summary["before_decision"]
    assert summary["recommended_next_step"].startswith("Zuerst")
    assert "keine amtliche Prognose" in summary["guardrail"]
    assert packet["primary_result_view"]["policy_readiness_summary"] == summary
    assert "result_sections" in packet["primary_result_view"]["render_sequence"]
    assert "collapsed_detailprüfung" in packet["primary_result_view"]["render_sequence"]


def test_first_view_briefing_cards_include_consequence_card_without_jargon():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    cards = packet["first_view_briefing_cards"]
    consequence_card = next(card for card in cards if card["stage"] == "Was daraus folgt")

    assert "prüfbare Linie" in consequence_card["answer"]
    assert "Nächste Prüfentscheidung" in consequence_card["next_step"] or "Prüfentscheidung" in consequence_card["next_step"]
    combined = " ".join(str(value) for card in cards for value in card.values())
    assert "Audit-Layer" not in combined
    assert "random Internet" not in combined
    assert "KPI-Wand" not in combined


def test_professional_briefing_exposes_reader_ready_narrative_blocks():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    briefing = packet["professional_briefing"]
    narrative = briefing["narrative_blocks"]

    headings = [block["heading"] for block in narrative]
    assert headings == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung und Belastbarkeit",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    assert all(block["body"].strip() for block in narrative)
    assert all(block["reader_hint"].startswith("Warum das wichtig ist:") for block in narrative)
    assert "Ab Jahr 6" in briefing["reader_summary"] or "ab Jahr 6" in briefing["reader_summary"]
    assert "keine amtliche Prognose" in briefing["reader_summary"]
    assert "kein Wirksamkeitsnachweis" in briefing["reader_summary"]
    assert len(briefing["first_view_kpi_cards"]) <= 4

    combined = " ".join(
        str(value)
        for block in narrative
        for value in block.values()
    ) + " " + briefing["reader_summary"]
    banned = [
        "random Internet",
        "KPI-Wand",
        "Audit-Layer",
        "causal_result_packet",
        "render_sequence",
        "guardrail",
    ]
    assert not any(term in combined for term in banned)


def test_causal_packet_exposes_public_briefing_sequence_for_api_and_ui_clients():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    sequence = packet["public_briefing_sequence"]

    assert [step["stage"] for step in sequence] == [
        "Ausgangslage",
        "Eingriff",
        "Wirkpfad der Simulation",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    assert packet["primary_result_view"]["public_briefing_sequence"] == sequence
    assert sequence[2]["body"].startswith("Der Eingriff läuft")
    assert "ab Jahr 6" in sequence[2]["body"]
    assert "Jahr 11–15" in sequence[2]["body"]
    assert "Telemedizin" in sequence[4]["body"]
    assert "Burnout" in sequence[4]["body"]
    assert "keine amtliche Prognose" in sequence[5]["body"]
    assert "erst fachlich prüfen" in sequence[-1]["body"].lower()
    assert all(step["body"].strip() and step["reader_hint"].startswith("Warum das wichtig ist:") for step in sequence)
    public_text = " ".join(step["stage"] + " " + step["body"] + " " + step["reader_hint"] for step in sequence)
    banned = ["random Internet", "Klartext", "KPI-Wand", "Audit-Layer", "guardrail", "render_sequence", "causal_result_packet"]
    assert not any(term in public_text for term in banned)


def test_causal_packet_public_storyline_is_one_complete_human_briefing_block():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    storyline = packet["public_briefing_text"]

    expected_order = [
        "Ergebnisbericht",
        "Ausgangslage",
        "Eingriff",
        "Wirkpfad der Simulation",
        "Relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    positions = [storyline.index(label) for label in expected_order]
    assert positions == sorted(positions)
    assert storyline.count("Einordnung\n") == 1
    assert "ab Jahr 6" in storyline
    assert "Jahr 11–15" in storyline
    assert "Telemedizin" in storyline
    assert "Burnout" in storyline
    assert "keine amtliche Prognose" in storyline
    assert "kein Wirksamkeitsnachweis" in storyline
    banned = ["random Internet", "Klartext", "KPI-Wand", "Audit-Layer", "guardrail", "render_sequence", "causal_result_packet"]
    assert not any(term in storyline for term in banned)


def test_public_causal_packet_is_short_clear_and_free_of_meta_terms():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    assert packet["result_headline"]
    assert "Medizinstudienplätze" in packet["short_answer"]
    assert any(kpi["label"] in packet["short_answer"] for kpi in packet["relevant_kpis"][:2])
    assert "weil" in packet["short_answer"].lower() or "über" in packet["short_answer"].lower()
    assert packet["follow_up_question"]
    assert len(packet["result_sections"]) <= 7
    assert [section["heading"] for section in packet["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    public_text = " ".join(
        [packet["result_headline"], packet["short_answer"], packet["follow_up_question"]]
        + [section["body"] for section in packet["result_sections"]]
    )
    banned = ["random Internet", "Klartext", "KPI-Wand", "generated", "helper", "Widget", "Meta"]
    for term in banned:
        assert term not in public_text
    assert all(len(section["body"].split()) <= 75 for section in packet["result_sections"])


def test_relevant_kpis_have_plain_meaning_for_first_result_view():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    assert 1 <= len(packet["relevant_kpis"]) <= 4
    for row in packet["relevant_kpis"]:
        assert row["label"]
        assert "start" in row and "end" in row
        assert row["direction"] in {"steigt", "sinkt", "stabil"}
        assert row.get("meaning")
        assert "amtliche Prognose" not in row["meaning"]


def test_public_result_view_is_one_briefing_not_overlapping_explanation_layers():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    view = packet["public_result_view"]

    assert view["briefing_style"] == "single_readable_briefing"
    assert view["primary_blocks"] == view["first_screen_blocks"]
    assert view["deeper_review_default_expanded"] is False
    assert "first_screen_note" not in view
    assert "briefing_summary" not in view
    assert "sections" not in view
    assert "Nächster Prüfschritt" in [section["heading"] for section in view["primary_blocks"]]
    public_text = " ".join(
        [view["headline"], view["short_answer"]]
        + [section["body"] for section in view["primary_blocks"]]
    )
    for term in ["Widget", "helper", "generated", "Meta", "Audit-Layer", "KPI-Wand"]:
        assert term not in public_text



def test_result_layout_uses_human_first_view_names_not_internal_widget_language():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5
    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    view = packet["public_result_view"]
    layout = build_causal_result_layout(packet)

    assert view["render_order"] == [
        "result_headline",
        "short_answer",
        "result_sections",
        "relevant_kpis",
        "follow_up_question",
        "collapsed_audit_sections",
    ]
    assert layout["primary_sequence"] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    public_layout_text = " ".join(
        [
            layout["dense_kpi_wall"]["label"],
            layout["dense_kpi_wall"]["reason"],
            layout["optional_interpretation_layers"]["label"],
            layout["optional_interpretation_layers"]["reason"],
        ]
    )
    banned = ["KPI-Wand", "Widget", "generated", "helper", "Audit-Layer", "render", "causal_result_packet"]
    assert not any(term in public_layout_text for term in banned)
    assert "Weitere Prüfung" in layout["optional_interpretation_layers"]["label"]


def test_public_result_packet_is_short_clear_and_not_meta_language():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)

    assert packet["result_headline"]
    assert "Medizinstudienplätze" in packet["short_answer"]
    assert "Jahr 6" in packet["short_answer"]
    assert any(kpi["label"] in packet["short_answer"] for kpi in packet["relevant_kpis"][:2])
    assert packet["short_answer"].count(". ") <= 3

    assert [section["heading"] for section in packet["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(packet["result_sections"]) <= 7
    assert all(len(section["body"]) <= 240 for section in packet["result_sections"])

    public_text = " ".join(
        [packet["result_headline"], packet["short_answer"], packet["follow_up_question"]]
        + [section["heading"] + " " + section["body"] for section in packet["result_sections"]]
        + [kpi.get("label", "") + " " + kpi.get("meaning", "") for kpi in packet["relevant_kpis"]]
    )
    banned = [
        "random Internet",
        "Klartext",
        "KPI-Wand",
        "generated",
        "helper",
        "Widget",
        "Audit-Layer",
        "render",
        "causal_result_packet",
    ]
    assert not any(term in public_text for term in banned)
    assert "keine amtliche Prognose" in public_text
    assert "kein Wirksamkeitsnachweis" in public_text


def test_public_causal_packet_is_short_clear_and_not_meta_layered():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    public = packet["public_result_view"]

    assert [section["heading"] for section in public["result_sections"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(public["result_sections"]) <= 7
    assert all(len(section["body"]) <= 190 for section in public["result_sections"])
    assert len(public["short_answer"].split(". ")) <= 4

    public_text = " ".join(
        [public["headline"], public["short_answer"], public["follow_up_question"], public["briefing_markdown"]]
        + [section["body"] for section in public["result_sections"]]
        + [row["meaning"] for row in public["relevant_kpis"]]
    )
    for banned in [
        "random Internet",
        "Klartext",
        "KPI-Wand",
        "generated",
        "helper",
        "Meta",
        "Audit",
        "Lesekarten",
    ]:
        assert banned not in public_text

    assert "Medizinstudienplätze" in public["short_answer"]
    assert "Facharzt" in public["short_answer"] or "Wartezeit" in public["short_answer"]
    assert "ab etwa Jahr 6" in public["short_answer"]
    assert "nächster Check" in public["short_answer"] or "Nächster" in public["follow_up_question"]


def test_public_relevant_kpis_are_compact_rows_with_plain_meaning():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    rows = packet["public_result_view"]["relevant_kpis"]

    assert 1 <= len(rows) <= 4
    assert {"label", "start", "end", "direction", "meaning"} <= set(rows[0])
    assert all(len(row["meaning"]) <= 150 for row in rows)
    assert any(row["label"] == "Facharzt-Wartezeit" for row in rows)
    assert all("Tabelle" not in row["meaning"] and "Widget" not in row["meaning"] for row in rows)


def test_public_result_view_exposes_single_executive_brief_for_first_screen():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] * 0.5

    packet = build_causal_result_packet(_agg_frame(), params, max_kpis=4)
    brief = packet["public_result_view"]["executive_brief"]

    assert brief["title"] == packet["result_headline"]
    assert brief["lead"] == packet["short_answer"]
    assert [block["heading"] for block in brief["blocks"]] == [
        "Ergebnis",
        "Eingriff",
        "Warum es passiert",
        "Relevante Kennzahlen",
        "Anpassungen",
        "Einordnung",
        "Nächster Prüfschritt",
    ]
    assert len(brief["blocks"]) <= 7
    assert all(block["kind"] in {"text", "kpi_rows"} for block in brief["blocks"])
    assert brief["blocks"][3]["kind"] == "kpi_rows"
    assert brief["blocks"][3]["rows"] == packet["public_result_view"]["relevant_kpis"][:4]
    assert brief["audit_hint"] == "Details bleiben darunter geschlossen: Zeitfenster, Evidenz, vollständige Kennzahlen und politische Einordnung."

    visible_text = " ".join(
        [brief["title"], brief["lead"], brief["audit_hint"]]
        + [block["heading"] + " " + block["body"] for block in brief["blocks"]]
        + [row.get("label", "") + " " + row.get("meaning", "") for row in brief["blocks"][3]["rows"]]
    )
    for banned in ["random Internet", "Klartext", "KPI-Wand", "generated", "helper", "Meta", "Widget", "Audit-Layer"]:
        assert banned not in visible_text
    assert "ab etwa Jahr 6" in visible_text
    assert "keine amtliche Prognose" in visible_text
    assert "kein Wirksamkeitsnachweis" in visible_text
