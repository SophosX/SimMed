import pandas as pd

from app import (
    _changed_policy_lever_notes,
    _direction_word,
    _parameter_evidence_badge,
    _parameter_provenance_help,
    build_kpi_explanations,
    get_default_params,
    plain_language_workflow_summary,
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


def test_parameter_evidence_badge_is_short_and_registry_based():
    badge = _parameter_evidence_badge("medizinstudienplaetze")

    assert badge == "🟢 Evidenz A · hrk_medical_education, destatis_genesis"
    assert _parameter_evidence_badge("unregistriert") == "⚪ Evidenz offen · Register fehlt"


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


def test_learning_page_reuses_expert_council_plain_language_workflow():
    steps = plain_language_workflow_summary()
    combined = " ".join(steps)

    assert len(steps) >= 4
    assert "Vorschläge" in combined
    assert "nicht direkt" in combined
    assert "Quellen" in combined
    assert "Git-Historie" in combined
