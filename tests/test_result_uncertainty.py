from result_uncertainty import (
    build_uncertainty_band_summary_from_final,
    build_uncertainty_decision_checklist,
    build_uncertainty_first_contact_cards,
    build_uncertainty_interpretation_packet,
    build_uncertainty_reading_storyboard,
    build_uncertainty_result_questions,
)


def test_uncertainty_summary_from_final_is_api_safe_and_guarded():
    final = {
        "jahr": 2040,
        "gkv_saldo_mean": 10.0,
        "gkv_saldo_p5": -5.0,
        "gkv_saldo_p95": 25.0,
        "wartezeit_fa_mean": 40.0,
        "wartezeit_fa_p5": 37.0,
        "wartezeit_fa_p95": 43.0,
    }

    rows = build_uncertainty_band_summary_from_final(
        final,
        metric_labels={"gkv_saldo": "GKV-Saldo", "wartezeit_fa": "Facharzt-Wartezeit"},
        metric_keys=["gkv_saldo", "wartezeit_fa", "missing_metric"],
        limit=5,
    )

    assert [row["metric_key"] for row in rows] == ["gkv_saldo", "wartezeit_fa"]
    assert rows[0]["label"] == "GKV-Saldo"
    assert rows[0]["signal"] == "breites Band"
    assert rows[0]["end_year"] == "2040"
    assert "keine amtliche Prognose" in rows[0]["guardrail"]
    assert "kein Wirksamkeitsnachweis" in rows[0]["guardrail"]
    assert rows[1]["signal"] == "enges Band"


def test_uncertainty_result_questions_make_p5_p95_actionable_without_overclaiming():
    rows = [
        {
            "metric_key": "gkv_saldo",
            "label": "GKV-Saldo",
            "mean": "10.00",
            "p5": "-5.00",
            "p95": "25.00",
            "signal": "breites Band",
            "guardrail": "keine amtliche Prognose",
        }
    ]

    questions = build_uncertainty_result_questions(rows)

    assert questions[0]["question"] == "Wie sicher ist das Signal bei GKV-Saldo?"
    assert "P5–P95 -5.00–25.00" in questions[0]["answer_first"]
    assert "KPI-Detailkarte" in questions[0]["what_to_open_next"]
    assert "nicht als eindeutige Punktprognose" in questions[0]["safe_reading"]
    assert "keine amtliche Prognose" in questions[0]["guardrail"]
    assert "kein Wirksamkeitsnachweis" in questions[0]["guardrail"]


def test_uncertainty_decision_checklist_prevents_decision_overclaiming():
    rows = [
        {
            "metric_key": "gkv_saldo",
            "label": "GKV-Saldo",
            "signal": "breites Band",
        },
        {
            "metric_key": "wartezeit_fa",
            "label": "Facharzt-Wartezeit",
            "signal": "enges Band",
        },
    ]

    checklist = build_uncertainty_decision_checklist(rows)

    assert checklist[0]["rank"] == "1"
    assert checklist[0]["decision_status"] == "erst Robustheit prüfen"
    assert "P5/P95-Band" in checklist[0]["required_check_before_decision"]
    assert "KPI-Detailkarte" in checklist[0]["what_to_open_next"]
    assert checklist[1]["decision_status"] == "relativ stabil im Modell"
    assert "Evidenzgrad" in checklist[1]["required_check_before_decision"]
    assert "keine amtliche Prognose" in checklist[0]["guardrail"]
    assert "kein Wirksamkeitsnachweis" in checklist[0]["guardrail"]


def test_uncertainty_first_contact_cards_create_mobile_reading_path():
    rows = [
        {"metric_key": "gkv_saldo", "label": "GKV-Saldo", "signal": "breites Band"},
        {"metric_key": "wartezeit_fa", "label": "Facharzt-Wartezeit", "signal": "mittleres Band"},
        {"metric_key": "aerzte_pro_100k", "label": "Ärzte pro 100k", "signal": "enges Band"},
    ]

    cards = build_uncertainty_first_contact_cards(rows)

    assert [card["step"] for card in cards] == ["1", "2", "3"]
    assert "3 Kennzahlen" in cards[0]["answer_first"]
    assert "1 breit, 1 mittel, 1 eng" in cards[0]["answer_first"]
    assert "Starte mit GKV-Saldo" in cards[0]["answer_first"]
    assert "KPI-Detailkarte" in cards[0]["what_to_open_next"]
    assert "Robustheitsfrage" in cards[1]["title"]
    assert "nicht sofort eine Entscheidung" in cards[1]["answer_first"]
    assert "Modellannahmen" in cards[2]["title"]
    assert "keine amtliche Prognose" in cards[0]["guardrail"]
    assert "kein Wirksamkeitsnachweis" in cards[0]["guardrail"]


def test_uncertainty_reading_storyboard_orders_safe_result_interpretation():
    rows = [
        {
            "metric_key": "gkv_saldo",
            "label": "GKV-Saldo",
            "mean": "10.00",
            "p5": "-5.00",
            "p95": "25.00",
            "signal": "breites Band",
        },
        {"metric_key": "wartezeit_fa", "label": "Facharzt-Wartezeit", "signal": "enges Band"},
    ]

    storyboard = build_uncertainty_reading_storyboard(rows)

    assert [step["rank"] for step in storyboard] == ["1", "2", "3", "4"]
    assert [step["stage"] for step in storyboard] == [
        "Orientieren",
        "Robustheit prüfen",
        "Wirkpfad gegenlesen",
        "Entscheidung bremsen",
    ]
    assert "GKV-Saldo" in storyboard[0]["answer_first"]
    assert "P5/P95 -5.00–25.00" in storyboard[0]["answer_first"]
    assert "breite Bänder" in storyboard[1]["answer_first"]
    assert "Annahmen-/Evidenzcheck" in storyboard[2]["answer_first"]
    assert "keine amtliche Prognose" in storyboard[3]["answer_first"]
    assert "kein Wirksamkeitsnachweis" in storyboard[3]["guardrail"]
    assert all("execute=true" not in step.get("open_next", "") for step in storyboard)


def test_uncertainty_interpretation_packet_bundles_safe_reading_path():
    rows = [
        {
            "metric_key": "gkv_saldo",
            "label": "GKV-Saldo",
            "mean": "10.00",
            "p5": "-5.00",
            "p95": "25.00",
            "signal": "breites Band",
        },
        {"metric_key": "wartezeit_fa", "label": "Facharzt-Wartezeit", "signal": "enges Band"},
    ]

    packet = build_uncertainty_interpretation_packet(rows)

    assert packet["mode"] == "read_only_uncertainty_interpretation"
    assert "2 P5/P95-Kennzahlen" in packet["summary"]
    assert "1 davon mit breitem Band" in packet["summary"]
    assert packet["first_contact_cards"][0]["title"] == "Erst Spannweite, dann Mittelwert"
    assert packet["result_questions"][0]["question"] == "Wie sicher ist das Signal bei GKV-Saldo?"
    assert packet["decision_checklist"][0]["decision_status"] == "erst Robustheit prüfen"
    assert [step["stage"] for step in packet["reading_storyboard"]] == [
        "Orientieren",
        "Robustheit prüfen",
        "Wirkpfad gegenlesen",
        "Entscheidung bremsen",
    ]
    assert "Annahmen-/Evidenzcheck" in " ".join(packet["definition_of_done_before_decision"])
    assert "keine amtliche Prognose" in packet["guardrail"]
    assert "kein Wirksamkeitsnachweis" in packet["guardrail"]
    assert "execute=true" not in str(packet)
