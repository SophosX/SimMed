from result_uncertainty import build_uncertainty_band_summary_from_final


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
