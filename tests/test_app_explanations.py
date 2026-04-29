import pandas as pd

from app import _direction_word, build_kpi_explanations


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
