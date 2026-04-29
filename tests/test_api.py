from fastapi.testclient import TestClient

from api import api


def test_api_exposes_data_snapshot_status_guardrail():
    client = TestClient(api)
    response = client.get("/data-snapshots")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_status_not_model_integration"
    assert "Modellparameter ändern sich erst" in body["guardrail"]
    assert isinstance(body["snapshots"], list)
    population = next(row for row in body["parameters"] if row["parameter_key"] == "bevoelkerung_mio")
    assert set(population) == {
        "parameter_key",
        "has_cached_snapshot",
        "snapshot_count",
        "latest_snapshot",
        "status_note",
    }
    assert "Rohdaten-Snapshot" in population["status_note"]
    passport_population = next(row for row in body["data_passport"] if row["parameter_key"] == "bevoelkerung_mio")
    assert passport_population["registry_label"] == "aus Daten"
    assert "cache" in passport_population
    assert "Snapshot" in passport_population["passport_note"]


def test_api_exposes_data_passport_for_registry_and_cache_status():
    client = TestClient(api)
    response = client.get("/data-passport")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "registry_and_raw_cache_passport_not_model_integration"
    assert "Rohdaten-Cache" in body["guardrail"]
    population = next(row for row in body["parameters"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["registry_label"] == "aus Daten"
    assert population["source_version"]
    assert population["cache"]["parameter_key"] == "bevoelkerung_mio"
    assert "Registry" in population["passport_note"]


def test_api_exposes_political_feasibility_endpoint():
    client = TestClient(api)
    response = client.post(
        "/political-feasibility",
        json={"parameter_changes": {"medizinstudienplaetze": 9000}, "n_runs": 1, "n_years": 1, "seed": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "explanation_only_not_validated_forecast"
    assert body["lever_notes"][0]["key"] == "medizinstudienplaetze"


def test_simulate_embeds_political_feasibility_summary():
    client = TestClient(api)
    response = client.post(
        "/simulate",
        json={"parameter_changes": {"telemedizin_rate": 0.12}, "n_runs": 1, "n_years": 1, "seed": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["political_feasibility"]["lever_notes"][0]["key"] == "telemedizin_rate"
