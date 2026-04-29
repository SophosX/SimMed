import pandas as pd

from app import (
    _changed_policy_lever_notes,
    _direction_word,
    build_changed_parameter_assumption_checks,
    _parameter_control_help,
    _parameter_effect_hint,
    _parameter_evidence_badge,
    _parameter_provenance_help,
    build_changed_parameter_impact_bridge,
    build_changed_lever_question_cards,
    build_changed_lever_result_audit_trail,
    build_kpi_answer_checklist,
    build_learning_connector_execution_status,
    build_learning_data_passport_overview,
    build_learning_data_readiness_backlog,
    build_learning_parameter_data_workflow_cards,
    build_kpi_assumption_trace,
    build_kpi_drilldown_items,
    build_kpi_drilldown_navigation,
    build_kpi_explanations,
    build_kpi_result_story,
    build_landing_hero_content,
    build_scenario_gallery_cards,
    build_scenario_gallery_guided_apply_plan,
    build_scenario_gallery_manifest_previews,
    build_political_lever_detail_sections,
    build_political_result_checkpoints,
    build_political_stakeholder_rows,
    build_result_decision_checkpoints,
    build_result_explorer_topics,
    build_result_narrative_summary,
    build_result_reading_path,
    build_result_storyboard,
    build_report_navigation_index,
    build_report_question_shortcuts,
    build_simulation_report,
    build_trend_changed_lever_timing,
    build_trend_metric_reading_rows,
    build_trend_view_guidance,
    get_default_params,
    kpi_data_status_badge,
    kpi_hover_help,
    kpi_matching_changed_levers,
    kpi_mobile_detail,
    kpi_related_inspections,
    learning_page_next_actions,
    metric_card,
    kpi_mobile_detail,
    render_metric_card_with_details,
    plain_language_workflow_summary,
    sidebar_quick_start_steps,
)


def test_data_status_badges_are_backward_compatible_without_registry_field():
    # UI helpers must not crash while source-cache/import coverage evolves.
    evidence_badge = _parameter_evidence_badge("bevoelkerung_mio")
    assert "aus Daten" in evidence_badge
    assert "Evidenz A" in evidence_badge
    provenance_help = _parameter_provenance_help("bevoelkerung_mio")
    assert "Datenlinie" in provenance_help
    assert "Import" in provenance_help or "snapshot" in provenance_help
    kpi_badge = kpi_data_status_badge("gesundheitsausgaben_mrd")
    assert "Daten" in kpi_badge or "Annahme" in kpi_badge



def test_learning_data_passport_overview_separates_registry_cache_and_transformation():
    overview = build_learning_data_passport_overview(limit=6)

    assert overview["title"].startswith("Datenpass")
    assert "Registry-Status" in overview["plain_language_note"]
    assert "Rohdaten-Cache" in overview["plain_language_note"]
    assert "kein Beweis" in overview["plain_language_note"]
    assert overview["counts"]["total_parameters"] >= overview["counts"]["source_backed_registry"]
    assert overview["counts"]["assumption_registry"] >= 1
    assert "reviewed_transformations" in overview["counts"]
    assert 1 <= len(overview["rows"]) <= 6
    first_row = overview["rows"][0]
    assert {"Parameter", "Register", "Evidenz", "Rohdaten-Cache", "Geprüfte Transformation", "Hinweis"} <= set(first_row)
    combined = " ".join(str(value) for row in overview["rows"] for value in row.values())
    assert "aus Daten" in combined or "Annahme, nicht aus Daten" in combined
    assert "nicht automatisch integriert" in combined or "Keine geprüfte Transformation" in combined



def test_learning_data_readiness_backlog_prioritizes_safe_data_gates():
    backlog = build_learning_data_readiness_backlog(limit=5)

    assert backlog["title"].startswith("Nächste Daten-Schritte")
    assert "kein Import-Knopf" in backlog["plain_language_note"]
    assert backlog["summary"]["total_items"] >= len(backlog["rows"])
    assert "snapshot_needed" in backlog["summary"]["counts_by_gate"]
    assert "kein Wirkungsbeweis" in backlog["summary"]["plain_language_note"]
    assert backlog["summary"]["primary_focus"]["next_action"]
    assert [gate["gate"] for gate in backlog["gate_plan"]] == [
        "snapshot_needed",
        "transformation_review_needed",
        "explicit_model_integration_needed",
        "monitor_only",
    ]
    assert all("guardrail" in gate for gate in backlog["gate_plan"])
    assert "Manifest" in backlog["gate_plan"][0]["why_this_gate"]
    assert backlog["connector_queue"]
    connector = backlog["connector_queue"][0]
    assert {"source_label", "open_parameter_count", "connector_next_action", "guardrail"} <= set(connector)
    assert "SHA256-Manifest" in connector["connector_next_action"]
    assert "keine automatische" in connector["guardrail"]
    assert backlog["connector_snapshot_requests"]
    request = backlog["connector_snapshot_requests"][0]
    assert request["table_code"] in {"12411-0001", "23111-0001"}
    assert "endpoint_url" in request
    assert "not a model import" in request["guardrail"]
    assert 1 <= len(backlog["rows"]) <= 5
    first = backlog["rows"][0]
    assert {"Parameter", "Nächstes Gate", "Aktion", "Guardrail"} <= set(first)
    combined = " ".join(str(value) for row in backlog["rows"] for value in row.values())
    assert "Rohdaten" in combined or "Transformation" in combined
    assert "kein" in combined.lower() and "Modell" in combined


def test_learning_connector_execution_status_keeps_dry_run_and_cache_gates_separate():
    status = build_learning_connector_execution_status(limit=3)

    assert status["title"].startswith("Connector-Ausführung")
    assert "Dry-run" in status["plain_language_note"]
    assert "kein Rohdaten-Cache" in status["plain_language_note"]
    assert status["rows"]
    assert 1 <= len(status["rows"]) <= 3
    first = status["rows"][0]
    assert {
        "Parameter",
        "Status",
        "Request",
        "Cache",
        "Transformation",
        "Sichere Reihenfolge",
        "Review-Checkliste",
        "Nächster sicherer Schritt",
        "Guardrail",
    } <= set(first)
    combined = " ".join(str(value) for row in status["rows"] for value in row.values())
    assert "geplant, nicht ausgeführt" in combined
    assert "Dry-run prüfen" in combined
    assert "Explizite Modellintegration" in combined
    assert "kein Netzwerkabruf" in combined
    assert "nicht Modellintegration" in combined
    assert "Transformation" in combined
    assert "Nenner" in combined
    assert "SHA256" in combined



def test_learning_parameter_data_workflow_cards_explain_why_data_is_not_model_ready():
    cards = build_learning_parameter_data_workflow_cards(limit=3)

    assert cards["title"].startswith("Warum ist ein Datenpunkt")
    assert "Datenpass" in cards["plain_language_note"]
    assert "Connector-Plan" in cards["plain_language_note"]
    assert "ohne Netzwerkabruf" in cards["plain_language_note"]
    assert cards["rows"]
    assert 1 <= len(cards["rows"]) <= 3
    first = cards["rows"][0]
    assert {
        "Parameter",
        "Register",
        "Nächstes Gate",
        "Nächster sicherer Schritt",
        "Rohdaten-Cache",
        "Transformation",
        "Review-Start",
        "API",
        "Guardrail",
    } <= set(first)
    combined = " ".join(str(value) for row in cards["rows"] for value in row.values())
    assert "GET /data-readiness/" in combined
    assert "SHA256" in combined or "Rohdaten" in combined
    assert "keine Registry- oder Modellmutation" in combined
    assert "kein Policy-Wirkungsbeweis" in combined



def test_landing_hero_content_sets_first_contact_expectations():
    content = build_landing_hero_content()
    combined_actions = " ".join(action["label"] + " " + action["description"] for action in content["actions"])

    assert content["title"] == "Was ist SimMed?"
    assert len(content["mission"].split(".")) <= 2
    assert "Gesundheitssystem" in content["mission"]
    assert len(content["actions"]) == 3
    assert "Was passiert, wenn" in combined_actions
    assert "Stellschrauben verstehen" in combined_actions
    assert "Ergebnis lesen" in combined_actions
    assert "keine amtliche Prognose" in content["disclaimer"]


def test_scenario_gallery_cards_offer_safe_guided_starts_without_model_claims():
    cards = build_scenario_gallery_cards()
    combined = " ".join(
        " ".join(str(value) for value in card.values()) for card in cards
    )

    assert len(cards) >= 3
    assert {"id", "title", "question", "parameter_changes", "workflow", "guardrail"}.issubset(cards[0])
    assert any("Medizinstudienplätze" in card["title"] for card in cards)
    assert any("Telemedizin" in card["title"] for card in cards)
    assert "Ausgangslage verstehen" in combined
    assert "Annahmen prüfen" in combined
    assert "Policy-Briefing lesen" in combined
    assert "keine amtliche Prognose" in combined
    assert "nicht automatisch" in combined
    assert all(card["parameter_changes"] for card in cards)
    all_keys = {key for card in cards for key in card["parameter_changes"]}
    assert "praeventionsbudget" in all_keys
    assert "praevention_budget" not in all_keys


def test_scenario_gallery_manifest_previews_are_reproducible_and_read_only():
    previews = build_scenario_gallery_manifest_previews(n_runs=100, n_years=15, seed=42)

    assert len(previews) == len(build_scenario_gallery_cards())
    assert all(preview["scenario_id"] for preview in previews)
    assert all(preview["api_endpoint"] == "POST /scenario-manifest" for preview in previews)
    assert all(preview["simulate_endpoint"] == "POST /simulate" for preview in previews)
    assert all("kein Apply-Button" in preview["guardrail"] for preview in previews)
    assert all("kein Simulationslauf" in preview["guardrail"] for preview in previews)
    assert all("keine amtliche Prognose" in preview["guardrail"] for preview in previews)

    prevention_preview = next(
        preview for preview in previews if preview["card_id"] == "prevention_finance_tradeoff"
    )
    prevention_param = prevention_preview["changed_parameters"][0]
    assert prevention_preview["parameter_changes"] == {"praeventionsbudget": 10.0}
    assert prevention_param["key"] == "praeventionsbudget"
    assert prevention_param["registered"] is True
    assert prevention_param["evidence_grade"] in {"A", "B", "C", "D", "E"}


def test_scenario_gallery_guided_apply_plan_bridges_cards_to_manual_run_without_mutation():
    plans = build_scenario_gallery_guided_apply_plan(n_runs=100, n_years=15, seed=42)
    combined = " ".join(str(value) for plan in plans for value in plan.values())

    assert len(plans) == len(build_scenario_gallery_cards())
    first = plans[0]
    assert {
        "card_id",
        "scenario_id",
        "manual_sidebar_steps",
        "api_payload",
        "copy_hint",
        "reading_order",
        "guardrail",
    } <= set(first)
    assert all(plan["manual_sidebar_steps"] for plan in plans)
    assert all("parameter_changes" in plan["api_payload"] for plan in plans)
    assert "Werte manuell in der Sidebar setzen" in combined
    assert "POST /simulate" in combined
    assert "Ergebnis-Storyboard öffnen" in combined
    assert "KPI-Detailkarte" in combined
    assert "kein automatischer Apply-Button" in combined
    assert "keine Session-State-Mutation" in combined
    assert "kein Simulationslauf" in combined
    assert "keine amtliche Prognose" in combined
    assert "kein Wirksamkeitsnachweis" in combined
    assert "keine Lobbying-Empfehlung" in combined

    medical_plan = next(plan for plan in plans if plan["card_id"] == "medical_training_pipeline")
    assert medical_plan["api_payload"]["parameter_changes"] == {"medizinstudienplaetze": 9000}
    step = medical_plan["manual_sidebar_steps"][0]
    assert step["parameter_key"] == "medizinstudienplaetze"
    assert "Sidebar-Regler" in step["instruction"]
    assert step["evidence_grade"] in {"A", "B", "C", "D", "E"}


def test_direction_word_uses_plain_language_and_preference_direction():
    assert _direction_word(2.0, higher_is_better=True) == "verbessert"
    assert _direction_word(-2.0, higher_is_better=True) == "verschlechtert"
    assert _direction_word(2.0, higher_is_better=False) == "verschlechtert"
    assert _direction_word(0.01, higher_is_better=False) == "kaum verändert"


def test_build_kpi_explanations_mentions_core_causal_assumptions():
    agg = pd.DataFrame(
        [
            {
                "jahr": 2026,
                "wartezeit_fa_mean": 20.0,
                "gkv_saldo_mean": 1.0,
                "versorgungsindex_rural_mean": 70.0,
            },
            {
                "jahr": 2040,
                "wartezeit_fa_mean": 28.0,
                "gkv_saldo_mean": -4.0,
                "versorgungsindex_rural_mean": 62.0,
            },
        ]
    )

    explanations = build_kpi_explanations(agg, {"telemedizin_rate": 0.2})

    assert [item["status"] for item in explanations] == [
        "verschlechtert",
        "verschlechtert",
        "verschlechtert",
    ]
    combined_text = " ".join(
        f"{item['title']} {item['body']} {item['assumption']}" for item in explanations
    )
    assert "Facharzt-Wartezeit" in combined_text
    assert "GKV-Saldo" in combined_text
    assert "ländliche Versorgung" in combined_text
    assert "Kopfzahl ist nicht automatisch Kapazität" in combined_text
    assert "11–13 Jahren" in combined_text
    assert "keine zusätzliche Prognose" not in combined_text
    assert "Telemedizin wurde auf" in explanations[0]["scenario_focus"]


def test_parameter_provenance_help_uses_registry_plain_language():
    help_text = _parameter_provenance_help("medizinstudienplaetze", "UI-Hinweis")

    assert "Evidenzgrad A" in help_text
    assert "hrk_medical_education" in help_text
    assert "delayed physician inflow" in help_text
    assert "Never apply study-place changes instantly" in help_text
    assert "UI-Hinweis" in help_text


def test_parameter_control_help_combines_evidence_and_action_guidance():
    help_text = _parameter_control_help("medizinstudienplaetze", "UI-Hinweis")

    assert "Evidenzgrad A" in help_text
    assert "hrk_medical_education" in help_text
    assert "UI-Hinweis" in help_text
    assert "Was passiert beim Ändern?" in help_text
    assert "Facharztkapazität" in help_text


def test_finance_and_demography_controls_now_have_combined_registry_help():
    income_help = _parameter_control_help("einkommen_durchschnitt")
    gkv_share_help = _parameter_control_help("gkv_anteil")
    epa_help = _parameter_control_help("digitalisierung_epa")

    assert "Evidenzgrad A" in income_help
    assert "GKV revenue base" in income_help
    assert "Was passiert beim Ändern?" in income_help
    assert "Evidenzgrad A" in gkv_share_help
    assert "insured-count" in gkv_share_help
    assert "Was passiert beim Ändern?" in gkv_share_help
    assert "Evidenzgrad B" in epa_help
    assert "Adoption is not the same as better outcomes" in epa_help
    assert "Was passiert beim Ändern?" in epa_help


def test_versorgung_controls_now_have_combined_registry_help():
    rural_help = _parameter_control_help("aerzte_pro_100k_rural")
    bed_help = _parameter_control_help("krankenhausbetten")
    throughput_help = _parameter_control_help("patienten_pro_quartal")

    assert "Evidenzgrad B" in rural_help
    assert "kbv_zi" in rural_help
    assert "Was passiert beim Ändern?" in rural_help
    assert "ländlich" in rural_help
    assert "Evidenzgrad A" in bed_help
    assert "staffing" in bed_help
    assert "Was passiert beim Ändern?" in bed_help
    assert "Evidenzgrad B" in throughput_help
    assert "throughput" in throughput_help
    assert "Was passiert beim Ändern?" in throughput_help


def test_remaining_pipeline_finance_and_policy_controls_have_registry_help():
    pipeline_help = _parameter_control_help("einwanderung_aerzte")
    copay_help = _parameter_control_help("zuzahlungen_gkv")
    prevention_help = _parameter_control_help("praevention_effektivitaet")
    waiting_target_help = _parameter_control_help("wartezeit_grenze_tage")

    assert "Evidenzgrad B" in pipeline_help
    assert "annual external inflow" in pipeline_help
    assert "Was passiert beim Ändern?" in pipeline_help
    assert "Evidenzgrad B" in copay_help
    assert "patient cost-sharing" in copay_help
    assert "Was passiert beim Ändern?" in copay_help
    assert "Evidenzgrad D" in prevention_help
    assert "scenario assumption" in prevention_help
    assert "Was passiert beim Ändern?" in prevention_help
    assert "Evidenzgrad B" in waiting_target_help
    assert "does not create appointments" in waiting_target_help
    assert "Was passiert beim Ändern?" in waiting_target_help


def test_parameter_evidence_badge_is_short_and_registry_based():
    badge = _parameter_evidence_badge("medizinstudienplaetze")

    assert badge == "🟢 Annahme, nicht aus Daten · Evidenz A · hrk_medical_education, destatis_genesis"
    assert _parameter_evidence_badge("unregistriert") == "⚪ Evidenz offen · Register fehlt"


def test_parameter_effect_hint_explains_action_and_flags_simplifications():
    aging_hint = _parameter_effect_hint("alterungsfaktor")
    bed_hint = _parameter_effect_hint("krankenhausbetten")
    unknown_hint = _parameter_effect_hint("noch_offen")

    assert "Was passiert beim Ändern?" in aging_hint
    assert "altersbedingte Nachfrage" in aging_hint
    assert "Vereinfachte Annahme" in aging_hint
    finance_hint = _parameter_effect_hint("staatliche_subventionen")
    policy_hint = _parameter_effect_hint("wartezeit_grenze_tage")

    assert "Personal vorhanden" in bed_hint
    assert "Bund" in finance_hint and "GKV" in finance_hint
    assert "erzeugt keine Termine automatisch" in policy_hint
    assert "noch nicht mit einer eigenen Kurz-Erklärung" in unknown_hint


def test_changed_policy_lever_notes_names_only_changed_scenario_levers():
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1000
    params["praeventionsbudget"] = params["praeventionsbudget"] + 0.5

    notes = _changed_policy_lever_notes(params)
    combined = " ".join(notes)

    assert len(notes) == 2
    assert "weniger Medizinstudienplätze" in combined
    assert "Präventionsbudget wurde erhöht" in combined
    assert "Telemedizin" not in combined
    assert "kaum sofort" in combined


def test_sidebar_quick_start_steps_make_first_action_clear():
    steps = sidebar_quick_start_steps()
    combined = " ".join(steps)

    assert len(steps) == 3
    assert "Szenario" in combined
    assert "Simulation" in combined
    assert "Was hat sich verändert" in combined
    assert "Wer unterstützt? Wer bremst?" in combined
    assert "Klartext-Erklärung" in combined


def test_learning_page_next_actions_are_concrete_for_newcomers():
    actions = learning_page_next_actions()
    combined = " ".join(f"{item['title']} {item['body']}" for item in actions)

    assert len(actions) == 3
    assert "Seitenleiste" in combined
    assert "Simulation starten" in combined
    assert "Was hat sich verändert" in combined
    assert "Wer unterstützt oder bremst" in combined


def test_learning_page_reuses_expert_council_plain_language_workflow():
    steps = plain_language_workflow_summary()
    combined = " ".join(steps)

    assert len(steps) >= 4
    assert "Vorschläge" in combined
    assert "nicht direkt" in combined
    assert "Quellen" in combined
    assert "Git-Historie" in combined


def test_result_narrative_summary_prioritizes_change_and_next_step():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "wartezeit_fa_mean": 20.0,
            "gkv_saldo_mean": 2.0,
            "versorgungsindex_rural_mean": 70.0,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "kollaps_wahrscheinlichkeit_mean": 5.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 34.0,
            "gkv_saldo_mean": -4.0,
            "versorgungsindex_rural_mean": 67.0,
            "gesundheitsausgaben_mrd_mean": 560.0,
            "kollaps_wahrscheinlichkeit_mean": 7.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.1

    summary = build_result_narrative_summary(agg, params)
    combined = " ".join([summary["headline"], summary["lead"], summary["scenario_text"], summary["next_step"]] + [item["sentence"] for item in summary["top_changes"]])

    assert summary["headline"] == "Was ist in dieser Simulation passiert?"
    assert len(summary["top_changes"]) == 3
    assert "stark" in combined or "deutlich" in combined
    assert "Telemedizin" in combined
    assert "größte Veränderung öffnen" in combined
    assert "Zeitverlauf prüfen" in combined


def test_political_stakeholder_rows_explain_why_group_appears():
    from political_feasibility import assess_political_feasibility

    assessment = assess_political_feasibility({"medizinstudienplaetze": 8000})
    rows = build_political_stakeholder_rows(assessment)
    combined = " ".join(f"{row['role']} {row['stakeholder']} {row['lever']} {row['why']} {row['caveat']}" for row in rows)

    assert rows
    assert "Unterstützer" in combined
    assert "Bremser" in combined
    assert "Medizinstudienplätze" in combined
    assert "Umsetzung" in combined
    assert "politische Reibung" in combined
    assert "6+ Jahre" in combined or "11–13+ Jahre" in combined
    assert "keine validierte" in combined or "Modellkern" in combined


def test_political_lever_detail_sections_create_coherent_reading_path():
    from political_feasibility import assess_political_feasibility

    assessment = assess_political_feasibility({"medizinstudienplaetze": 8000})
    sections = build_political_lever_detail_sections(assessment)
    combined = " ".join(
        f"{section['label']} {section['effect']} {section['implementation_lag']} {section['political_friction']} "
        f"{section['caveat']} {section['strategy_checkpoint']} {section['next_inspection']} "
        + " ".join(f"{row['role']} {row['stakeholder']} {row['why']}" for row in section['supporters'] + section['blockers'])
        for section in sections
    )

    assert len(sections) == 1
    assert sections[0]["supporters"]
    assert sections[0]["blockers"]
    assert "Medizinstudienplätze" in combined
    assert "Verzögerung" in combined or "6+ Jahre" in combined
    assert "politische Reibung" in combined
    assert "Zuständigkeit" in combined or "Finanzierung" in combined
    assert "Unsicherheit" not in sections[0]["next_inspection"]
    assert "Prüfe als Nächstes" in combined
    assert "KPI-Detailkarten" in combined
    assert "keine validierte" in combined or "Modellkern" in combined

def test_kpi_drilldown_items_follow_coherent_reading_path():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "bip_anteil_mean": 12.0,
            "gkv_beitragssatz_mean": 16.0,
            "gkv_saldo_mean": 2.0,
            "lebenserwartung_mean": 81.0,
            "wartezeit_fa_mean": 20.0,
            "aerzte_pro_100k_mean": 420.0,
            "kollaps_wahrscheinlichkeit_mean": 5.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 575.0,
            "bip_anteil_mean": 13.5,
            "gkv_beitragssatz_mean": 17.2,
            "gkv_saldo_mean": -3.0,
            "lebenserwartung_mean": 81.4,
            "wartezeit_fa_mean": 31.0,
            "aerzte_pro_100k_mean": 405.0,
            "kollaps_wahrscheinlichkeit_mean": 9.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.1

    items = build_kpi_drilldown_items(agg, params)
    combined = " ".join(
        f"{item['title']} {item['meaning']} {item['observation']} {item['drivers']} {item['scenario_focus']} {item['assumption']} {item['next_step']}"
        for item in items
    )

    assert len(items) == 8
    assert all("Start" in item["observation"] and "Ende" in item["observation"] for item in items)
    assert all("Veränderung" in item["observation"] for item in items)
    assert all(item["next_step"] for item in items)
    assert "Telemedizin wurde auf" in combined
    assert "Zeitverlauf" in combined
    assert "politische" in combined
    assert "Kopfzahl allein" in combined


def test_kpi_drilldown_items_prioritize_strongest_movement():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "bip_anteil_mean": 12.0,
            "gkv_beitragssatz_mean": 16.0,
            "gkv_saldo_mean": 2.0,
            "lebenserwartung_mean": 81.0,
            "wartezeit_fa_mean": 20.0,
            "aerzte_pro_100k_mean": 420.0,
            "kollaps_wahrscheinlichkeit_mean": 5.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 525.0,
            "bip_anteil_mean": 12.2,
            "gkv_beitragssatz_mean": 16.3,
            "gkv_saldo_mean": -4.0,
            "lebenserwartung_mean": 81.1,
            "wartezeit_fa_mean": 24.0,
            "aerzte_pro_100k_mean": 410.0,
            "kollaps_wahrscheinlichkeit_mean": 6.0,
        },
    ])

    items = build_kpi_drilldown_items(agg, get_default_params())

    assert items[0]["key"] == "gkv_saldo"
    assert items[0]["effect_strength"] in {"deutlich", "stark"}
    assert abs(items[0]["pct_delta"]) >= abs(items[1]["pct_delta"])


def test_kpi_drilldowns_include_related_inspection_trails():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "gkv_saldo_mean": 2.0,
            "wartezeit_fa_mean": 20.0,
            "aerzte_pro_100k_mean": 420.0,
            "versorgungsindex_rural_mean": 70.0,
            "kollaps_wahrscheinlichkeit_mean": 5.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 560.0,
            "gkv_saldo_mean": -3.0,
            "wartezeit_fa_mean": 31.0,
            "aerzte_pro_100k_mean": 405.0,
            "versorgungsindex_rural_mean": 66.0,
            "kollaps_wahrscheinlichkeit_mean": 8.0,
        },
    ])

    items = build_kpi_drilldown_items(agg, get_default_params())
    by_key = {item["key"]: item for item in items}

    assert "GKV-Saldo" in " ".join(kpi_related_inspections("gesundheitsausgaben_mrd"))
    assert "Ärzte pro 100.000" in " ".join(by_key["wartezeit_fa"]["related_inspections"])
    assert "Ländliche Versorgung" in " ".join(by_key["aerzte_pro_100k"]["related_inspections"])
    assert "Wartezeit" in " ".join(by_key["kollaps_wahrscheinlichkeit"]["related_inspections"])
    assert all(item["related_inspections"] for item in items)

def test_trend_view_guidance_warns_about_mixed_units_and_next_step():
    guidance = build_trend_view_guidance(["Gesundheitsausgaben", "Facharzt-Wartezeit", "GKV-Beitragssatz"])
    combined = " ".join(guidance.values())

    assert "Mittelwerte" in combined
    assert "Jahr für Jahr" in combined
    assert "unterschiedliche Einheiten" in combined
    assert "nicht direkt vergleichen" in combined
    assert "Gesundheitsausgaben" in combined
    assert "Facharzt-Wartezeit" in combined
    assert "GKV-Beitragssatz" in combined
    assert "KPI-Detailkarte" in combined
    assert "keine amtliche Prognose" in combined



def test_changed_parameter_impact_bridge_connects_inputs_to_kpi_pointers():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "chroniker_rate_mean": 42.0,
            "lebenserwartung_mean": 81.0,
            "aerzte_pro_100k_mean": 420.0,
            "wartezeit_fa_mean": 20.0,
            "versorgungsindex_rural_mean": 70.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 560.0,
            "chroniker_rate_mean": 39.0,
            "lebenserwartung_mean": 81.8,
            "aerzte_pro_100k_mean": 405.0,
            "wartezeit_fa_mean": 31.0,
            "versorgungsindex_rural_mean": 66.0,
        },
    ])
    params = get_default_params()
    params["praeventionsbudget"] = params["praeventionsbudget"] + 0.6
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1000

    items = build_changed_parameter_impact_bridge(agg, params)
    combined = " ".join(
        f"{item['label']} {item['change']} {item['model_path']} {' '.join(item['observed_kpis'])} {item['caveat']} {item['next_step']}"
        for item in items
    )

    assert len(items) == 2
    assert "Präventionsbudget" in combined
    assert "Medizinstudienplätze" in combined
    assert "Start" in combined and "Ende" in combined
    assert "verzögert" in combined
    assert "6 Jahren" in combined and "11–13 Jahren" in combined
    assert "Nächster Klick" in combined
    assert "Zeitverlauf" in combined


def test_changed_parameter_bridge_exposes_exact_kpi_drilldown_targets():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 420.0,
            "wartezeit_fa_mean": 20.0,
            "versorgungsindex_rural_mean": 70.0,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 405.0,
            "wartezeit_fa_mean": 31.0,
            "versorgungsindex_rural_mean": 66.0,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1000

    item = build_changed_parameter_impact_bridge(agg, params)[0]
    targets = item["drilldown_targets"]
    combined_targets = " ".join(
        f"{target['metric_key']} {target['label']} {target['observed']} {target['next_step']}"
        for target in targets
    )

    assert [target["metric_key"] for target in targets] == [
        "aerzte_pro_100k",
        "wartezeit_fa",
        "versorgungsindex_rural",
    ]
    assert "Start" in combined_targets and "Ende" in combined_targets
    assert "KPI-Detailkarte" in combined_targets
    assert "Wartezeit" in combined_targets
    assert "ländlich" in combined_targets or "Land" in combined_targets


def test_kpi_mobile_detail_reuses_central_detail_copy():
    detail = kpi_mobile_detail("gesundheitsausgaben_mrd")
    combined = " ".join(detail.values())

    assert "Gesamtausgaben" in combined
    assert "Alterung" in combined
    assert "automatisch schlecht" in combined

    fallback = kpi_mobile_detail("noch_unbekannt")
    assert "Erklärung ergänzt" in fallback["meaning"]
    assert "Detailkarten" in fallback["why"]
    assert "Zeitverlauf" in fallback["read"]


def test_metric_cards_expose_hover_explanations_for_core_kpis():
    help_text = kpi_hover_help("gesundheitsausgaben_mrd")
    assert "Gesamtausgaben" in help_text
    assert "Warum verändert" in help_text
    html = metric_card("Gesundheitsausgaben", "767 Mrd. €", 61.9, False, "metric-card", help_text)
    assert 'title="' in html
    assert "ⓘ" in html
    assert "Gesamtausgaben" in html

    required = [
        "bip_anteil",
        "gkv_beitragssatz",
        "gkv_saldo",
        "lebenserwartung",
        "vermeidbare_mortalitaet",
        "chroniker_rate",
        "bevoelkerung_mio",
        "aerzte_pro_100k",
        "wartezeit_fa",
        "versorgungsindex_rural",
        "gini_versorgung",
        "burnout_rate",
        "telemedizin_rate",
        "kollaps_wahrscheinlichkeit",
        "zufriedenheit_patienten",
    ]
    for key in required:
        text = kpi_hover_help(key)
        assert "Warum" in text
        assert "Lesart" in text


def test_mobile_kpi_detail_is_tap_friendly_and_renderer_exists():
    detail = kpi_mobile_detail("wartezeit_fa")
    assert "Bedeutung" not in detail["meaning"]  # content, not a preformatted label
    assert "Warum" not in detail["why"]
    assert "Wartezeit" in detail["meaning"] or "fachärztliche" in detail["meaning"]
    assert callable(render_metric_card_with_details)

def test_changed_parameter_assumption_checks_expose_evidence_and_caveats():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "chroniker_rate_mean": 42.0,
            "lebenserwartung_mean": 81.0,
            "aerzte_pro_100k_mean": 420.0,
            "wartezeit_fa_mean": 20.0,
            "versorgungsindex_rural_mean": 70.0,
        },
        {
            "jahr": 2040,
            "gesundheitsausgaben_mrd_mean": 560.0,
            "chroniker_rate_mean": 39.0,
            "lebenserwartung_mean": 81.8,
            "aerzte_pro_100k_mean": 405.0,
            "wartezeit_fa_mean": 31.0,
            "versorgungsindex_rural_mean": 66.0,
        },
    ])
    params = get_default_params()
    params["praeventionsbudget"] = params["praeventionsbudget"] + 0.5
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1000

    checks = build_changed_parameter_assumption_checks(agg, params)
    combined = " ".join(
        f"{check['label']} {check['evidence']} {check['model_caveat']} {check['registry_caveat']} {check['uncertainty']} {check['source_hint']} {check['sanity_check']}"
        for check in checks
    )

    assert len(checks) == 2
    assert "Präventionsbudget" in combined
    assert "Medizinstudienplätze" in combined
    assert "Evidenzgrad" in combined
    assert "Quellen" in combined
    assert "Registerrolle" in combined
    assert "Unsicherheit" in combined or "uncertainty" in combined.lower()
    assert "KPI-Spuren" in combined and "Zeitverlauf" in combined
    assert "keine gesicherte Realwelt-Wirkung" in combined


def test_kpi_drilldowns_match_changed_levers_to_specific_kpis():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 70.0,
            "gkv_saldo_mean": -2.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 26.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 73.0,
            "gkv_saldo_mean": -3.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15

    wait_matches = kpi_matching_changed_levers("wartezeit_fa", agg, params)
    saldo_matches = kpi_matching_changed_levers("gkv_saldo", agg, params)
    items = {item["key"]: item for item in build_kpi_drilldown_items(agg, params)}

    assert [item["label"] for item in wait_matches] == ["Telemedizin"]
    assert saldo_matches == []
    assert "Telemedizin" in items["wartezeit_fa"]["lever_context"]
    assert "keine direkte Brücke" in items["gkv_saldo"]["lever_context"]
    assert "nicht als direkte Ursache" in items["gkv_saldo"]["lever_context"]


def test_kpi_assumption_trace_links_direct_changed_levers_to_evidence_checks():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 70.0,
            "gkv_saldo_mean": -2.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 26.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 73.0,
            "gkv_saldo_mean": -3.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15

    checks = build_changed_parameter_assumption_checks(agg, params)
    items = {item["key"]: item for item in build_kpi_drilldown_items(agg, params)}
    wait_trace = build_kpi_assumption_trace(items["wartezeit_fa"], checks)
    saldo_trace = build_kpi_assumption_trace(items["gkv_saldo"], checks)
    combined = " ".join(
        f"{row['label']} {row['evidence']} {row['model_caveat']} {row['registry_caveat']} {row['uncertainty']} {row['sanity_check']}"
        for row in wait_trace
    )

    assert [row["label"] for row in wait_trace] == ["Telemedizin"]
    assert items["wartezeit_fa"]["assumption_trace"] == wait_trace
    assert saldo_trace == []
    assert items["gkv_saldo"]["assumption_trace"] == []
    assert "Evidenzgrad" in combined
    assert "Unsicherheit" in combined
    assert "keine gesicherte Realwelt-Wirkung" in combined


def test_kpi_answer_checklist_answers_core_result_questions_from_existing_item():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 70.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 26.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 73.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15
    item = {item["key"]: item for item in build_kpi_drilldown_items(agg, params)}["wartezeit_fa"]

    checklist = build_kpi_answer_checklist(item)
    questions = [row["question"] for row in checklist]
    combined = " ".join(f"{row['question']} {row['answer']}" for row in checklist)

    assert questions == [
        "Was hat sich verändert?",
        "Warum im Modell?",
        "Wie stark?",
        "Welche Annahme begrenzt die Lesart?",
        "Was als Nächstes prüfen?",
    ]
    assert item["observation"] in combined
    assert "Effektstärke" in combined and item["effect_strength"] in combined
    assert "Telemedizin" in combined
    assert item["assumption"] in combined
    assert item["next_step"] in combined



def test_result_reading_path_guides_full_result_journey():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "gkv_saldo_mean": -5.0,
            "versorgungsindex_rural_mean": 70.0,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "kollaps_wahrscheinlichkeit_mean": 8.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 72.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 38.0,
            "gkv_saldo_mean": -12.0,
            "versorgungsindex_rural_mean": 66.0,
            "gesundheitsausgaben_mrd_mean": 620.0,
            "kollaps_wahrscheinlichkeit_mean": 14.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 68.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15

    steps = build_result_reading_path(agg, params)
    combined = " ".join(f"{step['step']} {step['title']} {step['body']}" for step in steps)

    assert len(steps) == 5
    assert "Top-Zusammenfassung" in combined
    assert "Telemedizin" in combined
    assert "KPI-Detailkarte" in combined and "Effektstärke" in combined
    assert "Trend" in combined and "verzögert" in combined
    assert "politische Lesespur" in combined
    assert "Rubrik" in combined and "Vote-Forecast" in combined


def test_simulation_report_structures_policy_briefing_from_existing_explanations():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "gkv_saldo_mean": -5.0,
            "versorgungsindex_rural_mean": 70.0,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "kollaps_wahrscheinlichkeit_mean": 8.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 72.0,
            "chroniker_rate_mean": 42.0,
            "lebenserwartung_mean": 81.0,
            "aerzte_pro_100k_mean": 420.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 38.0,
            "gkv_saldo_mean": -12.0,
            "versorgungsindex_rural_mean": 66.0,
            "gesundheitsausgaben_mrd_mean": 620.0,
            "kollaps_wahrscheinlichkeit_mean": 14.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 68.0,
            "chroniker_rate_mean": 39.0,
            "lebenserwartung_mean": 81.8,
            "aerzte_pro_100k_mean": 405.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15
    params["praeventionsbudget"] = params["praeventionsbudget"] + 0.5

    report = build_simulation_report(agg, params)
    combined = " ".join(
        f"{section['id']} {section['title']} {section['purpose']} {' '.join(section['points'])} {section['caveat']} {section['next_action']}"
        for section in report
    )

    assert [section["id"] for section in report] == [
        "executive_summary",
        "changed_levers",
        "kpi_deep_dive",
        "trend_timing",
        "evidence_assumptions",
        "political_feasibility",
    ]
    assert "Telemedizin" in combined and "Präventionsbudget" in combined
    assert "Effektstärke" in combined and "Nächster Klick" in combined
    assert "Einheiten" in combined and "Trend" in combined
    assert "Evidenzgrad" in combined and "Quellen" in combined and "Caveat" in combined
    assert "Rubrik" in combined and "Vote-Forecast" in combined
    assert "keine gesicherte Realwelt-Kausalität" in combined


def _sample_report_inputs():
    agg = pd.DataFrame([
        {
            "jahr": 2025,
            "wartezeit_fa_mean": 20.0,
            "gkv_saldo_mean": -5.0,
            "versorgungsindex_rural_mean": 70.0,
            "gesundheitsausgaben_mrd_mean": 500.0,
            "kollaps_wahrscheinlichkeit_mean": 8.0,
            "telemedizin_rate_mean": 10.0,
            "zufriedenheit_patienten_mean": 72.0,
            "chroniker_rate_mean": 42.0,
            "lebenserwartung_mean": 81.0,
            "aerzte_pro_100k_mean": 420.0,
        },
        {
            "jahr": 2040,
            "wartezeit_fa_mean": 35.0,
            "gkv_saldo_mean": -14.0,
            "versorgungsindex_rural_mean": 66.0,
            "gesundheitsausgaben_mrd_mean": 630.0,
            "kollaps_wahrscheinlichkeit_mean": 13.0,
            "telemedizin_rate_mean": 18.0,
            "zufriedenheit_patienten_mean": 68.0,
            "chroniker_rate_mean": 39.0,
            "lebenserwartung_mean": 81.8,
            "aerzte_pro_100k_mean": 405.0,
        },
    ])
    params = get_default_params()
    params["telemedizin_rate"] = params["telemedizin_rate"] + 0.15
    params["praeventionsbudget"] = params["praeventionsbudget"] + 0.5

    return agg, params


def test_simulation_report_sections_expose_plain_language_guide_questions():
    agg, params = _sample_report_inputs()
    report = build_simulation_report(agg, params)
    assert all(section.get("guide_questions") for section in report)
    assert all(len(section["guide_questions"]) >= 3 for section in report)

    combined_questions = " ".join(question for section in report for question in section["guide_questions"])
    assert "Was hat sich" in combined_questions
    assert "Modellpfad" in combined_questions
    assert "Effektstärke" in combined_questions
    assert "Evidenzgrade" in combined_questions
    assert "Nächster" in " ".join(section["next_action"] for section in report)
    assert "Vote-Forecast" in combined_questions


def test_report_navigation_index_guides_which_expander_to_open_next():
    agg, params = _sample_report_inputs()
    report = build_simulation_report(agg, params)

    index = build_report_navigation_index(report)
    combined = " ".join(
        [index["instruction"]]
        + [f"{item['title']} {item['open_when']} {item['first_question']} {item['target']}" for item in index["items"]]
    )

    assert len(index["items"]) == 6
    assert [item["section_id"] for item in index["items"]] == [section["id"] for section in report]
    assert "Executive Summary" in combined
    assert "Geänderte Hebel" in combined
    assert "KPI" in combined
    assert "Zeitverlauf" in combined
    assert "Evidenz" in combined
    assert "Politische Umsetzbarkeit" in combined
    assert "Executive Summary zuerst" in combined
    assert "öffne danach den Abschnitt" in combined
    assert all(item["target"].startswith("#policy-briefing-") for item in index["items"])


def test_result_explorer_topics_route_practical_questions_to_existing_explanations():
    agg, params = _sample_report_inputs()
    topics = build_result_explorer_topics(agg, params)
    combined = " ".join(
        f"{topic['topic']} {topic['question']} {topic['answer']} {topic['assumption']} {topic['next_click']}"
        for topic in topics
    )

    assert len(topics) == 5
    assert "Zugang" in combined and "Facharzt" in combined
    assert "Finanzierung" in combined and ("GKV-Saldo" in combined or "GKV-Beitrag" in combined)
    assert "Geänderte Hebel" in combined and "Telemedizin" in combined
    assert "Zeit" in combined and "unterschiedliche Einheiten" in combined
    assert "Politische Umsetzbarkeit" in combined and "Vote-Forecast" in combined
    assert all(topic["next_click"] for topic in topics)
    assert "keine gesicherte Realwelt-Kausalität" not in combined  # no new causality claim; bridge wording remains model-path based here


def test_report_question_shortcuts_route_reader_questions_to_existing_sections():
    agg, params = _sample_report_inputs()
    report = build_simulation_report(agg, params)
    section_ids = {section["id"] for section in report}

    shortcuts = build_report_question_shortcuts(report)
    combined = " ".join(
        f"{item['question']} {item['section_id']} {item['section_title']} {item['why']} {item['target']}"
        for item in shortcuts
    )

    assert len(shortcuts) >= 5
    assert all(item["section_id"] in section_ids for item in shortcuts)
    assert all(item["target"].startswith("#policy-briefing-") for item in shortcuts)
    assert "KPI" in combined and "Effektstärke" in combined
    assert "Zeitverlauf" in combined and "Trendlinien" in combined
    assert "Evidenz" in combined and "Annahmen" in combined
    assert "politische" in combined and "Vote-Forecast" in combined
    assert "Modellpfad" in combined



def test_trend_metric_reading_rows_make_selected_lines_readable_without_hover():
    agg = pd.DataFrame(
        [
            {
                "jahr": 2026,
                "wartezeit_fa_mean": 20.0,
                "gkv_beitragssatz_mean": 16.0,
            },
            {
                "jahr": 2040,
                "wartezeit_fa_mean": 30.0,
                "gkv_beitragssatz_mean": 17.6,
            },
        ]
    )
    choices = {
        "Facharzt-Wartezeit": "wartezeit_fa_mean",
        "GKV-Beitragssatz": "gkv_beitragssatz_mean",
        "Fehlt": "missing_mean",
    }

    rows = build_trend_metric_reading_rows(
        agg,
        ["Facharzt-Wartezeit", "GKV-Beitragssatz", "Fehlt", "Unbekannt"],
        choices,
    )

    assert [row["label"] for row in rows] == ["Facharzt-Wartezeit", "GKV-Beitragssatz"]
    wait_row = rows[0]
    assert wait_row["start"] == 20.0
    assert wait_row["end"] == 30.0
    assert wait_row["abs_delta"] == 10.0
    assert wait_row["pct_delta"] == 50.0
    assert wait_row["effect_strength"] in {"stark", "sehr stark"}
    assert wait_row["direction"] == "verschlechtert"
    assert "Gemischte Einheiten" in wait_row["caveat"]
    assert "KPI-Detailkarte Facharzt-Wartezeit" in wait_row["next_step"]

def test_result_explorer_topics_include_ordered_reading_paths():
    agg, params = _sample_report_inputs()
    topics = build_result_explorer_topics(agg, params)

    assert len(topics) == 5
    for topic in topics:
        path = topic.get("reading_path")
        assert path and [step["step"] for step in path] == [
            "1. Ergebnis-Signal",
            "2. Warum im Modell",
            "3. Annahme/Caveat",
            "4. Nächste Prüfung",
        ]
        combined_path = " ".join(step["text"] for step in path)
        assert topic["answer"] in combined_path
        assert topic["assumption"] in combined_path
        assert topic["next_click"] in combined_path

    combined = " ".join(
        f"{topic['topic']} {' '.join(step['text'] for step in topic['reading_path'])}"
        for topic in topics
    )
    assert "Modellpfad" in combined
    assert "Einheiten" in combined
    assert "Vote-Forecast" in combined
    assert "Lobbying-Empfehlung" in combined

def test_kpi_result_story_answers_core_user_journey_without_new_claims():
    agg, params = _sample_report_inputs()
    item = {item["key"]: item for item in build_kpi_drilldown_items(agg, params)}["wartezeit_fa"]

    story = build_kpi_result_story(item)
    combined = " ".join(story.values())

    assert story["headline"].startswith("Facharzt-Wartezeit")
    assert "Start" in story["what_changed"] and "Ende" in story["what_changed"]
    assert "Warum im Modell" not in story["why_it_changed"]  # value is answer text, not another heading
    assert "Telemedizin" in story["changed_levers"]
    assert "Effektstärke" in story["effect_strength"]
    assert "Annahme" in story["assumption_checkpoint"] or "Caveat" in story["assumption_checkpoint"]
    assert "Nächster Klick" in story["next_inspection"]
    assert "keine amtliche Prognose" in story["scope_caveat"]
    assert "Vote-Forecast" not in combined  # KPI story stays model-result focused, not political forecasting


def test_trend_changed_lever_timing_explains_when_to_inspect_delayed_levers():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    rows = build_trend_changed_lever_timing(agg, params)

    assert [row["label"] for row in rows] == ["Medizinstudienplätze"]
    row = rows[0]
    combined = " ".join(row.values())
    assert "Pipeline" in combined or "Vorlauf" in combined
    assert "2032" in row["inspection_window"]  # 2026 + 6 years
    assert "Facharzt" in row["linked_kpis"] or "Wartezeit" in row["linked_kpis"]
    assert "Kopfzahl" in row["caveat"]
    assert "Zeitverlauf" in row["next_step"]
    assert build_trend_changed_lever_timing(agg, get_default_params()) == []


def test_political_result_checkpoints_link_friction_to_existing_kpi_targets():
    from political_feasibility import assess_political_feasibility

    agg = pd.DataFrame([
        {
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
        },
        {
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    assessment = assess_political_feasibility({"medizinstudienplaetze": params["medizinstudienplaetze"]})
    political_sections = build_political_lever_detail_sections(assessment)
    bridge_items = build_changed_parameter_impact_bridge(agg, params)
    checkpoints = build_political_result_checkpoints(political_sections, bridge_items)

    assert [checkpoint["label"] for checkpoint in checkpoints] == ["Medizinstudienplätze"]
    checkpoint = checkpoints[0]
    combined = " ".join(
        [
            checkpoint["political_friction"],
            checkpoint["implementation_lag"],
            checkpoint["caveat"],
            checkpoint["next_step"],
            " ".join(checkpoint["observed_kpis"]),
            " ".join(target["next_step"] for target in checkpoint["drilldown_targets"]),
        ]
    )

    assert "KPI-Detailkarte" in combined
    assert "Ärztedichte" in combined or "Ärzte" in combined
    assert "Wartezeit Facharzt" in combined or "Facharzt-Wartezeit" in combined
    assert "ländliche Versorgung" in combined or "Versorgungsindex" in combined
    assert "kein Vote-Forecast" in combined
    assert "Annahmen-Checks" in combined
    assert build_political_result_checkpoints([{"label": "Nicht passender Hebel"}], bridge_items) == []



def test_changed_lever_result_audit_trail_links_input_kpi_assumption_timing_and_politics():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    rows = build_changed_lever_result_audit_trail(agg, params)

    assert [row["label"] for row in rows] == ["Medizinstudienplätze"]
    row = rows[0]
    combined = " ".join([
        row["changed"],
        row["model_path"],
        " ".join(row["observed_kpis"]),
        " ".join(target["next_step"] for target in row["drilldown_targets"]),
        row["assumption_check"],
        row["assumption_caveat"],
        row["timing"],
        row["timing_guidance"],
        row["political_supporters"],
        row["political_blockers"],
        row["political_caveat"],
        row["next_step"],
    ])
    assert "KPI-Detailkarte" in combined
    assert "Facharzt" in combined or "Wartezeit" in combined
    assert "Evidenzgrad" in row["assumption_check"]
    assert "2032" in row["timing"]
    assert "Vote-Forecast" in combined
    assert "Eingabe → Ergebnis → Annahme → Umsetzbarkeit" in row["next_step"]
    assert build_changed_lever_result_audit_trail(agg, get_default_params()) == []


def test_changed_lever_question_cards_answer_first_before_audit_details():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    cards = build_changed_lever_question_cards(agg, params)

    assert [card["label"] for card in cards] == ["Medizinstudienplätze"]
    card = cards[0]
    questions = [row["question"] for row in card["question_rows"]]
    combined = " ".join([card["summary"], card["guardrail"]] + [row["answer"] for row in card["question_rows"]])

    assert questions == [
        "Was wurde geändert?",
        "Warum bewegt das Ergebnisse?",
        "Wie stark/wo sichtbar?",
        "Welche Annahme prüfen?",
        "Was vor politischer Bewertung beachten?",
        "Nächster Klick",
    ]
    assert "KPI-Detailkarte" in combined
    assert "Facharzt" in combined or "Wartezeit" in combined
    assert "Evidenzgrad" in combined
    assert "2032" in combined
    assert "Vote-Forecast" in combined
    assert "Lobbying-Empfehlung" in combined
    assert "keine amtliche Prognose" in combined
    assert build_changed_lever_question_cards(agg, get_default_params()) == []

def test_result_decision_checkpoints_prevent_overclaiming_before_kpi_grid():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
            "gkv_saldo_mean": 1.0,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
            "gkv_saldo_mean": -2.0,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    checkpoints = build_result_decision_checkpoints(agg, params)

    assert [row["checkpoint"] for row in checkpoints] == [
        "1 · Ergebnis-Signal",
        "2 · Stärkste KPI zuerst prüfen",
        "3 · Geänderte Hebel zuordnen",
        "4 · Annahmen/Evidenz vor Schlussfolgerung",
        "5 · Timing im Trend prüfen",
        "6 · Politische Bewertung trennen",
        "7 · Sichere Lesart",
    ]
    combined = " ".join(row["answer"] + " " + row["next_step"] for row in checkpoints)
    assert "Effektstärke" in combined
    assert "KPI-Detailkarte" in combined or "Detailkarte" in combined
    assert "Medizinstudienplätze" in combined
    assert "Evidenzgrad" in combined
    assert "2032" in combined
    assert "Vote-Forecast" in combined
    assert "keine amtliche Prognose" in combined
    assert "keinen Wirksamkeitsbeweis" in combined
    assert "Ergebnis → Wirkpfad → Annahme → Zeitverlauf" in combined



def test_kpi_drilldown_navigation_orders_and_contextualizes_detail_cards():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
            "gkv_saldo_mean": 1.0,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
            "gkv_saldo_mean": -2.0,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    rows = build_kpi_drilldown_navigation(agg, params)

    assert rows[0]["rank"] == "1"
    assert rows[0]["title"]
    assert "Effektstärke" in rows[0]["why_open"]
    combined = " ".join(
        " ".join([
            row["title"],
            row["signal"],
            row["why_open"],
            row["matched_levers"],
            row["evidence_status"],
            row["next_click"],
            row["guardrail"],
        ])
        for row in rows
    )
    assert "KPI-Detailkarte" in combined or "Detailkarte" in combined
    assert "Medizinstudienplätze" in combined
    assert "Annahmen-/Evidenzcheck" in combined
    assert "keine amtliche Prognose" in combined or "Modell" in combined


def test_result_storyboard_orders_sections_from_signal_to_politics():
    agg = pd.DataFrame([
        {
            "jahr": 2026,
            "aerzte_pro_100k_mean": 430.0,
            "wartezeit_fa_mean": 35.0,
            "versorgungsindex_rural_mean": 0.72,
            "gkv_saldo_mean": 1.0,
        },
        {
            "jahr": 2040,
            "aerzte_pro_100k_mean": 410.0,
            "wartezeit_fa_mean": 44.0,
            "versorgungsindex_rural_mean": 0.64,
            "gkv_saldo_mean": -2.0,
        },
    ])
    params = get_default_params()
    params["medizinstudienplaetze"] = params["medizinstudienplaetze"] - 1500

    storyboard = build_result_storyboard(agg, params)

    assert [row["stage"] for row in storyboard] == [
        "1 · Orientierung",
        "2 · KPI-Detail",
        "3 · Geänderte Hebel",
        "4 · Annahmen/Evidenz",
        "5 · Timing im Trend",
        "6 · Politische Einordnung",
    ]
    combined = " ".join(
        " ".join([row["user_question"], row["open_section"], row["answer_signal"], row["target"], row["guardrail"]])
        for row in storyboard
    )
    assert "KPI" in combined and "Detail" in combined
    assert "Medizinstudienplätze" in combined
    assert "Evidenzgrad" in combined
    assert "Trend" in combined
    assert "keine offizielle Vorhersage" in combined or "keine amtliche Prognose" in combined
    assert "Vote-Forecast" in combined
    assert "Lobbying-Empfehlung" in combined
    assert "Ergebnis → Wirkpfad → Annahme → Zeitverlauf" in combined
