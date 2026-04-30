from result_uncertainty import build_uncertainty_band_summary_from_final, build_uncertainty_result_questions


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
