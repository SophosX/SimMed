import pandas as pd

from app import (
    _changed_policy_lever_notes,
    _direction_word,
    _parameter_control_help,
    _parameter_effect_hint,
    _parameter_evidence_badge,
    _parameter_provenance_help,
    build_kpi_explanations,
    build_political_stakeholder_rows,
    build_result_narrative_summary,
    get_default_params,
    learning_page_next_actions,
    plain_language_workflow_summary,
    sidebar_quick_start_steps,
)


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

    assert badge == "🟢 Evidenz A · hrk_medical_education, destatis_genesis"
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
