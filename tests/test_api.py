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


def test_api_exposes_data_readiness_backlog_without_model_integration():
    client = TestClient(api)
    response = client.get("/data-readiness-backlog")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_backlog_not_model_integration"
    assert body["summary"]["counts_by_gate"]["snapshot_needed"] >= 1
    assert [gate["gate"] for gate in body["gate_plan"]] == [
        "snapshot_needed",
        "transformation_review_needed",
        "explicit_model_integration_needed",
        "monitor_only",
    ]
    assert "keine Modellmutation" in " ".join(gate["guardrail"] for gate in body["gate_plan"])
    assert body["items"]
    assert body["connector_queue"]
    assert "connector_snapshot_requests" in body
    assert body["connector_snapshot_requests"]
    first_request = body["connector_snapshot_requests"][0]
    assert first_request["source_id"] == "destatis_genesis"
    assert first_request["table_code"] in {"12411-0001", "23111-0001"}
    assert "endpoint_url" in first_request
    assert "not a model import" in first_request["guardrail"]
    first_connector = body["connector_queue"][0]
    assert {"source_id", "source_label", "open_parameter_count", "connector_next_action", "guardrail"} <= set(first_connector)
    assert "keine automatische" in first_connector["guardrail"]

    assert "snapshot_needed" in body["summary"]["counts_by_gate"]
    assert "kein Live-Import" in body["summary"]["plain_language_note"]
    first = body["items"][0]
    assert {"parameter_key", "next_gate", "next_action", "guardrail"} <= set(first)
    assert "Modelländerung" in first["guardrail"]


def test_api_can_seed_reference_fixture_snapshots_without_model_import():
    client = TestClient(api)
    response = client.post("/data-fixtures/seed-reference-snapshots")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reference_fixtures_seeded_not_model_integration"
    assert "kein Live-Destatis-Import" in body["guardrail"]
    assert body["seeded_snapshots"]
    seeded = body["seeded_snapshots"][0]
    assert seeded["source_id"] == "destatis_genesis"
    assert seeded["output_parameter_keys"] == ["bevoelkerung_mio"]
    population = next(row for row in body["data_passport"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["cache"]["has_cached_snapshot"] is True
    assert "geprüfte Transformation" in population["passport_note"]


def test_api_plans_connector_snapshot_execution_as_dry_run_by_default():
    client = TestClient(api)
    backlog = client.get("/data-readiness-backlog").json()
    request = backlog["connector_snapshot_requests"][0]
    parameter_key = request["output_parameter_keys"][0]

    response = client.post("/data-connectors/execute-planned-snapshot", json={"parameter_key": parameter_key})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned_snapshot_request_not_executed"
    assert "kein Netzwerkabruf" in body["guardrail"]
    assert body["request"]["source_id"] == "destatis_genesis"
    assert body["request"]["output_parameter_keys"] == [parameter_key]
    assert "cache_source_payload" in body["next_safe_action"]
    assert [step["gate"] for step in body["execution_plan"]] == [
        "dry_run",
        "raw_snapshot_cache",
        "transformation_review",
        "explicit_model_integration",
    ]
    assert "kein netzwerkabruf" in body["execution_plan"][0]["guardrail"].lower()
    assert "kein Wirkungsbeweis" in body["execution_plan"][1]["guardrail"]
    assert "nicht automatisch" in body["execution_plan"][2]["guardrail"]
    assert "Keine offizielle Prognose" in body["execution_plan"][3]["guardrail"]
    assert body["data_passport"]
    passport_row = next(row for row in body["data_passport"] if row["parameter_key"] == parameter_key)
    assert passport_row["parameter_key"] == parameter_key


def test_api_rejects_connector_execution_without_supported_request():
    client = TestClient(api)
    response = client.post("/data-connectors/execute-planned-snapshot", json={"parameter_key": "telemedizin_rate"})

    assert response.status_code == 404
    assert response.json()["detail"]["status"] == "no_planned_connector_snapshot_request"


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
