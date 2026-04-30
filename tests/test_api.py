from fastapi.testclient import TestClient

from api import api
from simulation_core import get_default_params


def test_simulate_embeds_causal_result_packet_for_answer_first_clients():
    client = TestClient(api)
    defaults = get_default_params()
    response = client.post(
        "/simulate",
        json={
            "parameter_changes": {"medizinstudienplaetze": defaults["medizinstudienplaetze"] * 0.5},
            "n_runs": 3,
            "n_years": 15,
            "seed": 42,
        },
    )

    assert response.status_code == 200
    body = response.json()
    packet = body["causal_result_packet"]
    assert packet["title"] == "Ergebnisbericht"
    assert len(packet["relevant_kpis"]) <= 5
    assert "Medizinstudienplätze" in packet["coherent_story"]
    assert "ab etwa Jahr 6" in packet["coherent_story"]
    assert [section["id"] for section in packet["story_sections"]][:3] == [
        "output",
        "changed_inputs",
        "mechanisms",
    ]
    assert "dokumentierten Parametern" in packet["guardrail"]
    assert "random Internet" not in packet["guardrail"]
    assert "Klartext" not in packet["sequential_plain_text"]
    briefing = packet["professional_briefing"]
    assert briefing["title"] == "Ergebnisbericht"
    assert briefing["sequential_text"].startswith("Ergebnisbericht\n\nAusgangslage")
    assert [section["heading"] for section in briefing["sections"]] == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
        "Relevante KPIs",
        "Anpassungsreaktionen",
        "Einordnung und Belastbarkeit",
        "Was daraus folgt",
        "Nächste Prüfentscheidung",
    ]
    assert len(briefing["first_view_kpi_cards"]) <= 4
    assert [card["stage"] for card in packet["first_view_briefing_cards"]][:3] == [
        "Ausgangslage",
        "Eingriff",
        "Berechnete Wirkpfade",
    ]
    assert packet["primary_result_view"]["first_view_briefing_cards"] == packet["first_view_briefing_cards"]
    assert "keine amtliche Prognose" in packet["first_view_briefing_cards"][5]["why_it_matters"]
    assert packet["primary_result_view"]["render_sequence"] == [
        "professional_briefing_text",
        "first_view_kpi_cards",
        "adaptation_and_plausibility",
        "briefing_quality_checks",
        "optional_audit_layers",
    ]
    assert packet["primary_result_view"]["professional_briefing_text"].startswith("Ausgangslage: ")
    assert packet["professional_briefing"]["public_storyline"].startswith("Ergebnisbericht\n\nAusgangslage\n")
    assert packet["public_briefing_text"] == packet["professional_briefing"]["public_storyline"]
    assert "Was daraus folgt\n" in packet["public_briefing_text"]
    assert packet["primary_result_view"]["public_storyline"] == packet["professional_briefing"]["public_storyline"]
    assert "Warum das wichtig ist:" not in packet["professional_briefing"]["public_storyline"]
    assert packet["policy_readiness_summary"]["headline"] == "Was daraus folgt"
    assert "ab Jahr 6" in packet["policy_readiness_summary"]["why"]


def test_api_exposes_data_snapshot_status_guardrail():
    client = TestClient(api)
    response = client.get("/data-snapshots")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_status_not_model_integration"
    assert "Modellparameter ändern sich erst" in body["guardrail"]
    assert isinstance(body["snapshots"], list)
    assert body["snapshot_integrity"]["summary"]["snapshots_seen"] == len(body["snapshots"])
    assert "kein Netzwerkabruf" in body["snapshot_integrity"]["guardrail"]
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
    assert (
        "Snapshot" in passport_population["passport_note"]
        or "Transformationsreview" in passport_population["passport_note"]
    )


def test_api_exposes_focused_snapshot_integrity_without_fetch_or_import():
    client = TestClient(api)
    response = client.get("/data-snapshots/integrity")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_integrity_not_model_integration"
    assert "kein Registry-/Modellimport" in body["guardrail"]
    integrity = body["snapshot_integrity"]
    assert integrity["summary"]["snapshots_seen"] >= 0
    assert {"sha256_match", "sha256_mismatch", "raw_file_missing"} <= set(integrity["summary"])
    assert all("integrity_status" in row for row in integrity["rows"])
    assert "kein Netzwerkabruf" in integrity["guardrail"]
    assert body["integrity_action_plan"]["overall_status"] in {
        "integrity_blocker_before_review",
        "integrity_ok_but_not_reviewed",
        "no_cached_snapshots_yet",
    }
    assert "keine Registry-/Modellmutation" in body["integrity_action_plan"]["guardrail"]
    assert body["integrity_handoff_packet"]["status_route"] == "GET /data-snapshots/integrity"
    assert body["review_start_checklist"]["status"] in {
        "review_start_blocked_by_integrity",
        "review_start_ready_for_manual_check",
        "no_integrity_checked_snapshot_ready",
    }


def test_api_exposes_snapshot_review_start_checklist_without_execution():
    client = TestClient(api)
    response = client.get("/data-snapshots/review-start-checklist")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_review_start_checklist_not_executed"
    assert "keine Review-Erzeugung" in body["guardrail"]
    checklist = body["review_start_checklist"]
    assert checklist["status"] in {
        "review_start_blocked_by_integrity",
        "review_start_ready_for_manual_check",
        "no_integrity_checked_snapshot_ready",
    }
    assert "definition_of_done_before_review_creation" in checklist
    assert "keine Registry-/Modellmutation" in checklist["guardrail"]
    cards = body["review_start_status_cards"]
    assert [card["order"] for card in cards] == [1, 2, 3]
    assert cards[0]["route"] == "GET /data-snapshots/integrity"
    assert "kein Wirkungsbeweis" in cards[-1]["guardrail"]
    packet = body["review_start_handoff_packet"]
    assert packet["checklist_route"] == "GET /data-snapshots/review-start-checklist"
    assert "curl -s" in packet["copyable_status_command"]
    assert "keine Review-Erzeugung" in packet["guardrail"]
    preflight = body["transformation_review_draft_preflight"]
    assert preflight["status"] in {
        "draft_preflight_blocked_by_integrity",
        "draft_preflight_ready_for_manual_review",
        "draft_preflight_no_ready_snapshot",
    }
    assert "keine Review-Erzeugung" in preflight["guardrail"]


def test_api_exposes_transformation_review_draft_preflight_without_recording_review():
    client = TestClient(api)
    response = client.get("/data-snapshots/review-draft-preflight")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_draft_preflight_not_executed"
    assert "keine Review-Erzeugung" in body["guardrail"]
    preflight = body["transformation_review_draft_preflight"]
    assert preflight["status"] in {
        "draft_preflight_blocked_by_integrity",
        "draft_preflight_ready_for_manual_review",
        "draft_preflight_no_ready_snapshot",
    }
    assert "definition_of_done_before_record_review" in preflight
    assert "keine Registry-/Modellmutation" in preflight["guardrail"]
    cards = body["transformation_review_draft_status_cards"]
    assert [card["order"] for card in cards] == [1, 2, 3]
    assert cards[0]["route"] == "GET /data-snapshots/review-draft-preflight"
    assert "keinen Review" in cards[0]["guardrail"]
    packet = body["transformation_review_draft_handoff_packet"]
    assert packet["preflight_route"] == "GET /data-snapshots/review-draft-preflight"
    assert "curl -s" in packet["copyable_preflight_command"]
    assert "keine Review-Erzeugung" in packet["guardrail"]
    example = body["transformation_review_draft_example_payload"]
    assert example["status"] in {
        "draft_example_ready_not_persisted",
        "draft_example_blocked_no_preflight_row",
    }
    assert "example_payload" in example
    assert "review-draft/validate" in example["copyable_validate_command"]
    assert "keine Registry-/Modellmutation" in example["guardrail"]
    validation_packet = body["transformation_review_draft_validation_packet"]
    assert validation_packet["validate_route"] == "POST /data-snapshots/review-draft/validate"
    assert "curl -s" in validation_packet["copyable_validate_command"]
    assert "keine Review-Erzeugung" in validation_packet["guardrail"]
    for row in preflight["rows"]:
        assert row["draft_status"] == "template_ready_not_recorded"
        assert "review_template_route" in row
        assert "output_value" in " ".join(row["required_before_record_review"])


def test_api_exposes_focused_transformation_review_draft_handoff_without_execution():
    client = TestClient(api)
    response = client.get("/data-snapshots/review-draft-handoff")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_draft_handoff_not_executed"
    assert "kein execute=true" in body["guardrail"]
    assert "keine Review-Erzeugung" in body["guardrail"]
    cards = body["transformation_review_draft_status_cards"]
    assert cards[-1]["route"] == "GET /data-readiness/integration-preflight"
    assert "kein Policy-Wirkungsbeweis" in cards[-1]["guardrail"]
    packet = body["transformation_review_draft_handoff_packet"]
    assert packet["preflight_route"] == "GET /data-snapshots/review-draft-preflight"
    assert packet["copyable_preflight_command"] == "curl -s http://localhost:8000/data-snapshots/review-draft-preflight"
    assert packet["status"] in {
        "draft_blocked_by_integrity",
        "draft_ready_for_manual_completion",
        "no_review_draft_ready",
    }
    assert "keine Registry-/Modellmutation" in packet["guardrail"]


def test_api_exposes_transformation_review_draft_example_payload_without_persisting():
    client = TestClient(api)
    response = client.get("/data-snapshots/review-draft/example-payload")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_draft_example_payload_not_persisted"
    assert "keine Review-Erzeugung" in body["guardrail"]
    example = body["transformation_review_draft_example_payload"]
    assert example["status"] in {
        "draft_example_ready_not_persisted",
        "draft_example_blocked_no_preflight_row",
    }
    assert "parameter_key" in example["example_payload"]
    assert "review-draft/validate" in example["copyable_validate_command"]
    assert "keine Registry-/Modellmutation" in example["guardrail"]

def test_api_exposes_transformation_review_draft_validation_packet_without_persisting():
    client = TestClient(api)
    response = client.get("/data-snapshots/review-draft/validation-packet")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_draft_validation_packet_not_persisted"
    assert "keine Review-Erzeugung" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    packet = body["transformation_review_draft_validation_packet"]
    assert packet["validate_route"] == "POST /data-snapshots/review-draft/validate"
    assert "curl -s" in packet["copyable_validate_command"]
    assert "review-draft/validate" in packet["copyable_validate_command"]
    assert packet["status"] in {
        "draft_validation_incomplete",
        "draft_validation_blocked_no_preflight_row",
        "draft_validation_blocked_by_snapshot_mismatch",
        "draft_validation_ready_for_manual_record_review",
    }
    assert "keine Review-Erzeugung" in packet["guardrail"]
    assert "keine Registry-/Modellmutation" in packet["guardrail"]



def test_api_validates_transformation_review_draft_without_persisting():
    client = TestClient(api)
    response = client.post(
        "/data-snapshots/review-draft/validate",
        json={
            "parameter_key": "bevoelkerung_mio",
            "source_snapshot_sha256": "wrong-sha",
            "reviewer": "Evidence Agent",
            "method_note": "Manual table/year/denominator check",
            "output_value": 84.4,
            "output_unit": "Mio. Personen",
            "caveat": "Fixture/status validation only; no model integration.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_draft_validation_not_persisted"
    validation = body["transformation_review_draft_validation"]
    assert validation["parameter_key"] == "bevoelkerung_mio"
    validation_packet = body["transformation_review_draft_validation_packet"]
    assert validation_packet["parameter_key"] == "bevoelkerung_mio"
    assert validation_packet["validate_route"] == "POST /data-snapshots/review-draft/validate"
    assert validation["status"] in {
        "draft_validation_blocked_by_snapshot_mismatch",
        "draft_validation_blocked_no_preflight_row",
    }
    assert "keine Review-Erzeugung" in validation["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]


def test_api_exposes_focused_snapshot_integrity_handoff_without_execution():
    client = TestClient(api)
    response = client.get("/data-snapshots/integrity-handoff")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_integrity_handoff_not_model_integration"
    packet = body["integrity_handoff_packet"]
    assert packet["action_plan_route"] == "GET /data-snapshots/integrity-action-plan"
    assert "curl -s" in packet["copyable_status_command"]
    assert "kein execute=true" in packet["guardrail"]
    assert "keine Registry-/Modellmutation" in packet["guardrail"]


def test_api_exposes_focused_snapshot_integrity_action_plan_without_execution():
    client = TestClient(api)
    response = client.get("/data-snapshots/integrity-action-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "raw_snapshot_integrity_action_plan_not_model_integration"
    assert "kein Netzwerkabruf" in body["guardrail"]
    plan = body["integrity_action_plan"]
    assert "first_safe_action" in plan
    assert "definition_of_done_before_review" in plan
    assert all("operator_action" in row for row in plan["rows"])
    assert "keine Registry-/Modellmutation" in plan["guardrail"]


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
    assert body["connector_execution_workbench"]["summary"]["planned_request_count"] >= 1
    first_workbench_row = body["connector_execution_workbench"]["rows"][0]
    assert first_workbench_row["source_label"] == "Destatis/GENESIS"
    assert first_workbench_row["next_safe_gate"]["gate"] in {"raw_snapshot_cache", "transformation_review", "explicit_model_integration"}
    assert "keine Registry- oder Modellmutation" in first_workbench_row["guardrail"]
    first_connector = body["connector_queue"][0]
    assert {"source_id", "source_label", "open_parameter_count", "connector_next_action", "guardrail"} <= set(first_connector)
    assert "keine automatische" in first_connector["guardrail"]

    assert "snapshot_needed" in body["summary"]["counts_by_gate"]
    assert "kein Live-Import" in body["summary"]["plain_language_note"]
    first = body["items"][0]
    assert {"parameter_key", "next_gate", "next_action", "guardrail"} <= set(first)
    assert "Modelländerung" in first["guardrail"]


def test_api_exposes_next_data_readiness_actions_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/next-actions?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_next_actions_not_executed"
    assert "kein Netzwerkabruf" in body["guardrail"]
    assert len(body["actions"]) == 2
    packet = body["action_packet"]
    assert "Status/Dry-run-only" in packet["plain_language_note"]
    assert len(packet["rows"]) == 2
    assert "execute=true" in packet["guardrail"] or "kein Live-Fetch" in packet["guardrail"]
    handoff = body["operator_handoff"]
    assert "Status/Dry-run-only" in handoff["plain_language_note"]
    assert "Transformation mit Review-Template" in " ".join(handoff["sequence"])
    assert len(handoff["rows"]) == 2
    first_handoff_row = handoff["rows"][0]
    assert first_handoff_row["review_template_route"].startswith("GET /data-connectors/transformation-review-template/")
    assert "kein execute=true" in first_handoff_row["guardrail"]
    assert "Registry-/Modelländerung" in " ".join(first_handoff_row["definition_of_done_before_model_integration"])
    platform_brief = body["platform_brief"]
    assert "Plattform-Brief" in platform_brief["title"]
    assert len(platform_brief["rows"]) == 2
    assert "kein execute=true" in platform_brief["guardrail"]
    assert platform_brief["rows"][0]["verification"].startswith("Status prüfen")
    first_packet_row = packet["rows"][0]
    assert first_packet_row["copyable_api_command"].startswith("curl")
    assert first_packet_row["next_review_route"].startswith("GET /data-connectors/transformation-review-template/")
    assert "Registry/Modell" in " ".join(first_packet_row["operator_checklist"])
    assert "keine Registry-/Modellmutation" in first_packet_row["guardrail"]
    first = body["actions"][0]
    assert first["rank"] == 1
    assert first["workflow_api"].startswith("GET /data-readiness/")
    assert first["next_gate_label"]
    assert "keine Registry-/Modellmutation" in first["guardrail"]
    if first["planned_connector_request"]:
        assert first["primary_api"] == "POST /data-connectors/execute-planned-snapshot"
        assert first["dry_run_payload"] == {"parameter_key": first["parameter_key"], "execute": False}
    else:
        assert first["primary_api"] == first["workflow_api"]
        assert first["dry_run_payload"] is None



def test_api_exposes_platform_brief_as_core_platform_status_endpoint():
    client = TestClient(api)
    response = client.get("/data-readiness/platform-brief?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_platform_brief_not_executed"
    assert "kein Netzwerkabruf" in body["guardrail"]
    brief = body["platform_brief"]
    assert brief["title"].startswith("Plattform-Brief")
    assert len(brief["rows"]) == 2
    assert "Status/Dry-run" in brief["sequence"][0]
    first = brief["rows"][0]
    assert first["verification"].startswith("Status prüfen")
    assert "Review-Template" in first["verification"]
    assert "Registry-/Modelländerung" in first["definition_of_done"]
    assert "kein execute=true" in first["guardrail"]
    cockpit = body["dashboard_cards"]
    assert cockpit["cards"]
    assert cockpit["first_safe_action"]
    assert "kein execute=true" in cockpit["guardrail"]
    guide = body["first_contact_guide"]
    assert guide["title"].startswith("So liest du")
    assert guide["steps"][1]["open"].startswith("GET /data-readiness/")
    assert "kein execute=true" in guide["guardrail"]


def test_api_exposes_integration_preflight_without_model_mutation():
    client = TestClient(api)
    response = client.get("/data-readiness/integration-preflight?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_integration_preflight_not_executed"
    assert "kein execute=true" in body["guardrail"]
    preflight = body["integration_preflight"]
    assert preflight["title"].startswith("Integrations-Preflight")
    assert preflight["rows"]
    assert preflight["summary"]["shown_rows"] <= 3
    row = preflight["rows"][0]
    assert row["workflow_api"].startswith("GET /data-readiness/")
    assert row["review_template_api"].startswith("GET /data-connectors/transformation-review-template/")
    assert "Registry-/Modelländerung" in " ".join(row["definition_of_done"])
    assert "keine Registry-/Modellmutation" in row["guardrail"]
    assert body["integration_plan"]["title"].startswith("Parameter-spezifischer Integrationsplan")
    assert "keine Registry-/Modellmutation" in body["integration_plan"]["guardrail"]


def test_api_exposes_data_readiness_dashboard_cards_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/dashboard-cards?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_dashboard_cards_not_executed"
    assert "kein execute=true" in body["guardrail"]
    cockpit = body["dashboard_cards"]
    assert cockpit["title"].startswith("Daten-Reife Cockpit")
    assert len(cockpit["cards"]) == 4
    assert {"overall_progress", "snapshot_needed", "transformation_review_needed", "explicit_model_integration_needed"} == {
        card["id"] for card in cockpit["cards"]
    }
    assert cockpit["first_safe_action"]["workflow_api"].startswith("GET /data-readiness/")
    assert "keine Modellintegration" in cockpit["guardrail"]
    guide = body["first_contact_guide"]
    assert [step["order"] for step in guide["steps"]] == [1, 2, 3]
    assert "Status verstehen" in guide["plain_language_note"]
    assert "keine Registry-/Modellmutation" in guide["guardrail"]


def test_api_exposes_operator_handoff_as_focused_data_platform_work_order():
    client = TestClient(api)
    response = client.get("/data-readiness/operator-handoff?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_operator_handoff_not_executed"
    assert "kein Netzwerkabruf" in body["guardrail"]
    handoff = body["operator_handoff"]
    assert handoff["title"].startswith("Operator-Handoff")
    assert handoff["rows"]
    assert len(handoff["rows"]) == 2
    row = handoff["rows"][0]
    assert row["workflow_route"].startswith("GET /data-readiness/")
    assert row["review_template_route"].startswith("GET /data-connectors/transformation-review-template/")
    assert row["copyable_status_command"].startswith("curl")
    assert "Transformation ist separat reviewed" in " ".join(row["definition_of_done_before_model_integration"])
    assert "keine Registry-/Modellmutation" in row["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in handoff["guardrail"]


def test_api_rejects_next_data_readiness_actions_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/next-actions?limit=0")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_data_readiness_next_actions_limit"
    assert "keine Datenaktion" in detail["guardrail"]



def test_api_exposes_single_parameter_data_readiness_workflow_without_execution():
    client = TestClient(api)
    backlog = client.get("/data-readiness-backlog").json()
    request = backlog["connector_snapshot_requests"][0]
    parameter_key = request["output_parameter_keys"][0]

    response = client.get(f"/data-readiness/{parameter_key}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "parameter_data_workflow_not_model_integration"
    assert body["parameter_key"] == parameter_key
    assert body["passport"]["parameter_key"] == parameter_key
    assert body["backlog_item"]["parameter_key"] == parameter_key
    assert body["planned_connector_request"]["output_parameter_keys"] == [parameter_key]
    assert body["next_safe_gate"]["gate"] in {"raw_snapshot_cache", "transformation_review", "explicit_model_integration"}
    assert body["transformation_review_template"]["parameter_key"] == parameter_key
    assert "kein Netzwerkabruf" in body["guardrail"]
    assert "keine Registry- oder Modellmutation" in body["guardrail"]


def test_api_rejects_single_parameter_data_readiness_for_unknown_parameter():
    client = TestClient(api)
    response = client.get("/data-readiness/not_a_parameter")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["status"] == "unknown_parameter_data_workflow"
    assert "kein Netzwerkabruf" in detail["guardrail"]


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
    assert (
        "geprüfte Transformation" in population["passport_note"]
        or "Transformationsreview" in population["passport_note"]
    )


def test_api_exposes_single_transformation_review_template_without_model_integration():
    client = TestClient(api)
    backlog = client.get("/data-readiness-backlog").json()
    request = backlog["connector_snapshot_requests"][0]
    parameter_key = request["output_parameter_keys"][0]

    response = client.get(f"/data-connectors/transformation-review-template/{parameter_key}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transformation_review_template_not_model_integration"
    assert "kein Netzwerkabruf" in body["guardrail"]
    assert "keine Registry- oder Modellmutation" in body["guardrail"]
    assert body["request"]["output_parameter_keys"] == [parameter_key]
    template = body["template"]
    assert template["parameter_key"] == parameter_key
    assert "source_snapshot_sha256" in template["required_review_fields"]
    assert "ReviewedTransformation" in template["next_safe_action"]
    assert "keinen Datenwert im Modell" in template["guardrail"]
    passport_row = next(row for row in body["data_passport"] if row["parameter_key"] == parameter_key)
    assert passport_row["parameter_key"] == parameter_key


def test_api_rejects_transformation_review_template_without_supported_request():
    client = TestClient(api)
    response = client.get("/data-connectors/transformation-review-template/telemedizin_rate")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["status"] == "no_planned_transformation_review_template"
    assert "keine Modellintegration" in detail["guardrail"]


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


def test_api_exposes_scenario_gallery_guided_apply_plans_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/guided-apply-plans?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_guided_apply_plans_not_executed"
    assert "kein automatischer Apply-Button" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert body["plans"]
    training = next(plan for plan in body["plans"] if plan["card_id"] == "medical_training_pipeline")
    assert training["api_payload"] == {
        "parameter_changes": {"medizinstudienplaetze": 9000},
        "n_runs": 100,
        "n_years": 15,
        "seed": 42,
    }
    assert training["scenario_id"]
    assert training["manual_sidebar_steps"][0]["parameter_key"] == "medizinstudienplaetze"
    assert "Annahmen" in training["reading_order"][3]
    assert "keine amtliche Prognose" in training["guardrail"]
    assert "keine Lobbying-Empfehlung" in training["guardrail"]


def test_api_rejects_scenario_gallery_guided_apply_plan_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/guided-apply-plans?n_runs=1001")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_plan_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_scenario_gallery_run_readiness_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-readiness?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_run_readiness_not_executed"
    assert body["scenario_count"] >= 3
    assert body["evidence_check_count"] >= body["scenario_count"]
    assert body["ready_cards"]
    assert body["operator_route"] == "GET /scenario-gallery/operator-run-packets"
    assert body["handoff_route"] == "GET /scenario-gallery/run-handoff-sheet"
    assert "nichts wird automatisch angewendet" in body["first_safe_step"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in body["guardrail"]


def test_api_rejects_scenario_gallery_run_readiness_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-readiness?n_runs=0")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_run_readiness_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_scenario_gallery_run_handoff_sheet_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-handoff-sheet?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_run_handoff_not_executed"
    assert body["starter_rows"]
    assert body["routes_to_open_before_run"] == [
        "GET /scenario-gallery/run-readiness",
        "GET /scenario-gallery/operator-status-cards",
        "GET /scenario-gallery/operator-run-packets",
    ]
    assert "nichts wird automatisch angewendet" in body["first_safe_step"]
    assert "Ergebnis-Storyboard" in " ".join(body["post_run_reading_order"])
    assert body["starter_rows"][0]["copyable_payload_route"] == "POST /simulate"
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in body["guardrail"]


def test_api_rejects_scenario_gallery_run_handoff_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-handoff-sheet?n_runs=1001")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_run_handoff_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_focused_scenario_gallery_operator_status_cards_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/operator-status-cards?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_operator_status_cards_not_executed"
    assert "kein automatischer Apply-Button" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    assert "packets" not in body
    cards = body["status_cards"]
    assert cards
    medical_status = next(card for card in cards if card["card_id"] == "medical_training_pipeline")
    assert medical_status["status_label"] == "Bereit zur bewussten Prüfung, nicht ausgeführt"
    assert medical_status["primary_action"] == "Payload prüfen: POST /simulate"
    assert "Medizinstudienplätze" in medical_status["changed_parameters_plain"]
    assert "nichts wird automatisch angewendet" in medical_status["first_safe_check"]
    assert "Ergebnis-Storyboard" in medical_status["post_run_first_read"]
    assert "keine Registry-/Modellmutation" in medical_status["guardrail"]
    assert "Wirkungsbeweis" in medical_status["stop_rule_short"]


def test_api_rejects_scenario_gallery_operator_status_card_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/operator-status-cards?seed=1000000")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_status_card_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_scenario_gallery_pre_run_audit_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/pre-run-audit?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_pre_run_audit_not_executed"
    assert "kein Apply-Button" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    assert "keine amtliche Prognose" in body["guardrail"]
    rows = body["rows"]
    assert rows
    medical_row = next(row for row in rows if row["card_id"] == "medical_training_pipeline")
    assert medical_row["audit_status"] == "bereit_zur_manuellen_pruefung_nicht_ausgefuehrt"
    assert medical_row["payload_route"] == "POST /simulate"
    assert medical_row["manifest_route"] == "POST /scenario-manifest"
    assert medical_row["evidence_checks_required"] == 1
    assert "Medizinstudienplätze" in medical_row["changed_parameters_plain"]
    assert any("nichts wird automatisch angewendet" in item for item in medical_row["must_confirm_before_run"])
    assert any("keine amtliche Prognose" in item for item in medical_row["must_confirm_before_run"])
    assert any("Ergebnis-Storyboard" in item for item in medical_row["after_run_first_three_clicks"])
    assert "Wirksamkeitsnachweis" in medical_row["stop_rule"]


def test_api_rejects_scenario_gallery_pre_run_audit_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/pre-run-audit?n_runs=1001")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_pre_run_audit_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]



def test_api_exposes_scenario_gallery_run_decision_brief_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-decision-brief?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_run_decision_brief_not_executed"
    assert body["recommended_default"].startswith("Hold")
    assert "keine Entscheidungsspeicherung" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    rows = body["rows"]
    medical_row = next(row for row in rows if row["card_id"] == "medical_training_pipeline")
    assert medical_row["allowed_decisions"] == ["Run", "Hold", "Reject/Rework"]
    assert "evidence_caveat_acknowledged" in medical_row["decision_fields_to_fill"]
    assert medical_row["copyable_payload_route_if_run"] == "POST /simulate"
    assert medical_row["copyable_manifest_route_if_run"] == "POST /scenario-manifest"
    assert any("keine amtliche Prognose" in item for item in medical_row["minimum_checks_before_run"])
    assert "Wirksamkeitsnachweis" in medical_row["stop_rule"]



def test_api_rejects_scenario_gallery_run_decision_brief_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-decision-brief?seed=1000000")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_run_decision_brief_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_scenario_gallery_run_confirmation_template_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-confirmation-template?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_run_confirmation_template_not_executed"
    assert body["recommended_default"].startswith("Hold")
    assert "keine Entscheidungsspeicherung" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    medical_row = next(row for row in body["rows"] if row["card_id"] == "medical_training_pipeline")
    fields = medical_row["fields_to_fill_before_run"]
    assert fields[0]["field"] == "decision"
    assert fields[0]["allowed_values"] == ["Run", "Hold", "Reject/Rework"]
    assert fields[0]["recommended_default"] == "Hold"
    assert medical_row["copyable_payload_route_if_run"] == "POST /simulate"
    assert "Wirksamkeitsnachweis" in medical_row["stop_rule"]


def test_api_rejects_scenario_gallery_run_confirmation_template_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/run-confirmation-template?n_runs=1001")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_run_confirmation_template_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


def test_api_exposes_scenario_gallery_operator_run_packets_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/operator-run-packets?n_runs=100&n_years=15&seed=42")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scenario_gallery_operator_run_packets_not_executed"
    assert "kein automatischer Apply-Button" in body["guardrail"]
    assert "kein Simulationslauf" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    packets = body["packets"]
    status_cards = body["status_cards"]
    assert status_cards
    medical_status = next(card for card in status_cards if card["card_id"] == "medical_training_pipeline")
    assert medical_status["status_label"] == "Bereit zur bewussten Prüfung, nicht ausgeführt"
    assert medical_status["primary_action"] == "Payload prüfen: POST /simulate"
    assert medical_status["evidence_check_count"] == 1
    assert "kein Simulationslauf" in medical_status["guardrail"]
    assert "keine Registry-/Modellmutation" in medical_status["guardrail"]
    assert "Wirkungsbeweis" in medical_status["stop_rule_short"]
    assert "Ergebnis-Storyboard" in medical_status["post_run_first_read"]
    assert "Medizinstudienplätze" in medical_status["changed_parameters_plain"]
    assert "nichts wird automatisch angewendet" in medical_status["first_safe_check"]
    assert len(status_cards) == len(packets)
    assert packets
    medical_packet = next(packet for packet in packets if packet["card_id"] == "medical_training_pipeline")
    assert medical_packet["status"] == "run_packet_ready_but_not_executed"
    assert medical_packet["copyable_api_route"] == "POST /simulate"
    assert medical_packet["manifest_route"] == "POST /scenario-manifest"
    assert medical_packet["copyable_api_payload"]["parameter_changes"] == {"medizinstudienplaetze": 9000}
    assert "STOP:" in medical_packet["operator_stop_rule"]
    assert "Wirksamkeitsnachweis" in medical_packet["operator_stop_rule"]


def test_api_rejects_scenario_gallery_operator_run_packet_out_of_bounds_without_execution():
    client = TestClient(api)
    response = client.get("/scenario-gallery/operator-run-packets?n_years=31")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "invalid_scenario_gallery_run_packet_bounds"
    assert "kein Simulationslauf" in detail["guardrail"]


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


def test_api_exposes_focused_integration_plan_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/integration-plan?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_integration_plan_not_executed"
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    plan = body["integration_plan"]
    assert plan["title"].startswith("Parameter-spezifischer Integrationsplan")
    assert plan["summary"]["shown_plans"] <= 2
    assert "keine Registry-/Modellmutation" in plan["guardrail"]
    for item in plan["plans"]:
        assert item["workflow_api"].startswith("GET /data-readiness/")
        assert "parameter_registry.py" in item["proposed_files"]
        assert "Data Passport" in " ".join(item["definition_of_done"])
    assert body["integration_pr_brief"]["summary"]["shown_pr_briefs"] == plan["summary"]["shown_plans"]
    assert "keine Registry-/Modellmutation" in body["integration_pr_brief"]["guardrail"]


def test_api_seeds_reference_review_demo_for_green_integration_path_without_model_import():
    client = TestClient(api)
    response = client.post("/data-fixtures/seed-reference-review-demo")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reference_fixture_review_demo_seeded_not_model_integration"
    assert "kein Live-Destatis-Import" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    assert body["seeded_reviews"][0]["status"] == "reviewed_model_ready"
    population = next(row for row in body["data_passport"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["transformation_review"]["status"] == "reviewed_model_ready"
    assert body["integration_preflight"]["summary"]["ready_for_integration_plan"] >= 1
    brief = next(
        item for item in body["integration_pr_brief"]["briefs"] if item["parameter_key"] == "bevoelkerung_mio"
    )
    assert brief["branch_name"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert "kein Branch wird erstellt" in brief["guardrail"]



def test_api_exposes_focused_integration_pr_brief_without_branch_or_mutation():
    client = TestClient(api)
    response = client.get("/data-readiness/integration-pr-brief?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_integration_pr_brief_not_executed"
    assert "kein Branch" in body["guardrail"]
    brief = body["integration_pr_brief"]
    assert brief["title"].startswith("Integrations-PR-Brief")
    assert brief["summary"]["shown_pr_briefs"] <= 2
    assert "keine Registry-/Modellmutation" in brief["guardrail"]
    for item in brief["briefs"]:
        assert item["branch_name"].startswith("feat/integrate-reviewed-")
        assert item["status"] == "pr_brief_bereit_aber_nicht_ausgefuehrt"
        assert "ReviewedTransformation" in " ".join(item["review_checklist"])
        assert "keine amtliche Prognose" in item["guardrail"]


def test_api_exposes_registry_diff_preview_for_reviewed_values_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-diff-preview?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_diff_preview_not_applied"
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    preview = body["registry_diff_preview"]
    assert preview["title"].startswith("Registry-Diff-Preview")
    assert "kein Registry-Write" in preview["guardrail"]
    population = next(row for row in preview["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["status"] == "diff_preview_only_not_applied"
    assert population["current_registry_default"] == 84.4
    assert population["reviewed_output_value"] == 84.5
    assert population["unit_check"]["unit_matches"] is True
    assert population["plausibility_check"]["within_registry_bounds"] is True
    assert "darf ein separater PR den Default ändern" in population["required_human_decision"]
    assert "keine Registry-/Modellmutation" in population["guardrail"]



def test_api_exposes_registry_integration_decision_record_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-decision-record?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_decision_record_not_applied"
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    decision = body["registry_integration_decision_record"]
    assert decision["title"].startswith("Registry-Integrationsentscheidung")
    assert decision["summary"]["decision_rows"] <= 3
    population = next(row for row in decision["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["status"] == "human_go_no_go_required_before_pr"
    assert population["checks"]["reviewed_value_present"] is True
    assert population["checks"]["source_snapshot_sha256_present"] is True
    assert population["checks"]["unit_matches_registry"] is True
    assert population["checks"]["within_registry_bounds"] is True
    assert population["checks"]["pr_brief_available"] is True
    assert population["branch_name_if_go"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert any(option.startswith("Hold:") for option in population["safe_options"])
    assert "kein Branch" in population["guardrail"]
    template = body["registry_integration_decision_template"]
    assert template["title"].startswith("Ausfüllvorlage")
    template_population = next(row for row in template["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert template_population["allowed_decisions"] == ["Go", "Hold", "Reject"]
    assert "decision_rationale" in " ".join(template_population["decision_fields_to_fill"])
    assert "keine Registry-/Modellmutation" in template_population["guardrail"]
    audit = body["registry_integration_decision_audit_checklist"]
    assert audit["title"].startswith("Audit-Checkliste")
    audit_population = next(row for row in audit["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert audit_population["missing_technical_checks_before_go"] == []
    assert "GET /data-readiness/bevoelkerung_mio" in audit_population["evidence_routes_to_reopen"]
    assert any("audit_ok" in option for option in audit_population["audit_outcome_options"])
    assert "keine Entscheidungsspeicherung" in audit_population["guardrail"]
    handoff = body["registry_integration_handoff_packet"]
    assert handoff["title"].startswith("Registry-Integrations-Handoff")
    handoff_population = next(row for row in handoff["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert handoff_population["copyable_status_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert handoff_population["missing_checks_before_go"] == []
    assert "Go/Hold/Reject" in handoff_population["definition_of_done_before_branch"][0]
    assert "kein Branch" in handoff["guardrail"]
    assert "keine Registry-/Modellmutation" in decision["guardrail"]



def test_api_exposes_focused_registry_integration_decision_template_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-decision-template?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_decision_template_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    template = body["registry_integration_decision_template"]
    assert template["title"].startswith("Ausfüllvorlage")
    population = next(row for row in template["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["allowed_decisions"] == ["Go", "Hold", "Reject"]
    assert population["branch_name_if_go"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert "GET /data-readiness/bevoelkerung_mio" in population["evidence_routes_to_open"]
    assert "decision_rationale" in " ".join(population["decision_fields_to_fill"])
    assert "keine Entscheidungsspeicherung" in population["guardrail"]


def test_api_exposes_focused_registry_integration_decision_audit_checklist_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-decision-audit-checklist?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_decision_audit_checklist_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    audit = body["registry_integration_decision_audit_checklist"]
    assert audit["title"].startswith("Audit-Checkliste")
    population = next(row for row in audit["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["current_status"] == "human_go_no_go_required_before_pr"
    assert population["missing_technical_checks_before_go"] == []
    assert "GET /data-readiness/bevoelkerung_mio" in population["evidence_routes_to_reopen"]
    assert any("Hold" in question for question in population["audit_questions"])
    assert "execute=true" in audit["guardrail"]



def test_api_exposes_focused_registry_integration_handoff_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-handoff?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_handoff_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    handoff = body["registry_integration_handoff_packet"]
    assert handoff["title"].startswith("Registry-Integrations-Handoff")
    population = next(row for row in handoff["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["copyable_status_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert population["branch_name_if_go"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert population["missing_checks_before_go"] == []
    assert any("separat" in item.lower() for item in population["definition_of_done_before_branch"])
    assert "kein Branch" in handoff["guardrail"]
    assert "execute=true" in handoff["guardrail"]


def test_api_exposes_focused_registry_integration_pr_runbook_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-pr-runbook?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_pr_runbook_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    runbook = body["registry_integration_pr_runbook"]
    assert runbook["title"].startswith("Registry-Integrations-PR-Runbook")
    population = next(row for row in runbook["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["pr_runbook_status"] == "pr_runbook_waits_for_audited_go"
    assert population["branch_name_if_go"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert "GET /data-readiness/bevoelkerung_mio" in population["copyable_evidence_routes"]
    assert any("parameter_registry.py" in step for step in population["implementation_sequence_if_go"])
    assert any("Data-Passport" in item for item in population["definition_of_done_for_pr"])
    assert "kein Branch" in runbook["guardrail"]
    assert "execute=true" in runbook["guardrail"]


def test_api_exposes_focused_registry_integration_status_board_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-status-board?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_status_board_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    board = body["registry_integration_status_board"]
    assert board["title"].startswith("Registry-Integrations-Statusboard")
    population = next(row for row in board["rows"] if row["parameter_key"] == "bevoelkerung_mio")
    assert population["board_status"] == "bereit_fuer_menschliches_go_audit"
    assert population["status_route"] == "GET /data-readiness/bevoelkerung_mio"
    assert population["audit_route"] == "GET /data-readiness/registry-integration-decision-audit-checklist"
    assert population["runbook_route"] == "GET /data-readiness/registry-integration-pr-runbook"
    cards = body["registry_integration_status_cards"]
    assert cards["title"].startswith("Registry-Integrationskarten")
    assert cards["cards"][0]["id"] == "overall_registry_gate"
    assert cards["cards"][2]["id"] == "ready_for_human_audit"
    assert "kein execute=true" in cards["guardrail"]
    assert "keine Registry-/Modellmutation" in cards["cards"][0]["guardrail"]
    assert "kein Branch" in board["guardrail"]
    assert "execute=true" in board["guardrail"]


def test_api_exposes_focused_registry_integration_status_cards_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-status-cards?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_status_cards_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    cards = body["registry_integration_status_cards"]
    assert [card["id"] for card in cards["cards"]] == [
        "overall_registry_gate",
        "waiting_or_hold",
        "ready_for_human_audit",
        "first_safe_route",
    ]
    assert any(card["next_click"] == "GET /data-readiness/bevoelkerung_mio" for card in cards["cards"])
    assert "kein execute=true" in cards["guardrail"]


def test_api_exposes_registry_integration_operator_steps_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-operator-steps?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_operator_steps_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "kein execute=true" in body["guardrail"]
    steps = body["registry_integration_operator_steps"]
    assert steps["title"].startswith("Registry-Integrations-Operatorfolge")
    assert steps["primary_parameter_key"] == "bevoelkerung_mio"
    safe_start = steps["safe_start"]
    assert safe_start["first_command"] == "GET /data-readiness/registry-integration-status-board"
    assert safe_start["then_open"] == "GET /data-readiness/bevoelkerung_mio"
    assert "Hold" in safe_start["human_decision_default"]
    assert any("kein execute=true" in item for item in safe_start["do_not_do"])
    assert "Policy-Wirkungsbeweis" in safe_start["why_this_matters"]
    assert [step["rank"] for step in steps["steps"]] == [1, 2, 3, 4]
    commands = [step["copyable_status_command"] for step in steps["steps"]]
    assert commands[0] == "GET /data-readiness/registry-integration-status-board"
    assert "GET /data-readiness/bevoelkerung_mio" in commands
    assert not any("execute=true" in command for command in commands)
    assert any("separatem getestetem PR" in item for item in steps["definition_of_done_before_branch"])
    assert "keine Registry-/Modellmutation" in steps["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in steps["guardrail"]
    packet = body["registry_integration_safe_start_packet"]
    assert packet["primary_parameter_key"] == "bevoelkerung_mio"
    assert packet["first_safe_command"] == "GET /data-readiness/registry-integration-status-board"
    assert packet["inspect_next_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert not any("execute=true" in command for command in packet["copyable_read_only_sequence"])
    assert "keine Registry-/Modellmutation" in packet["guardrail"]


def test_api_exposes_focused_registry_integration_safe_start_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-safe-start?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_safe_start_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "kein execute=true" in body["guardrail"]
    packet = body["registry_integration_safe_start_packet"]
    assert packet["title"].startswith("Registry-Integration: sicherer Start")
    assert packet["primary_parameter_key"] == "bevoelkerung_mio"
    assert packet["human_decision_default"].startswith("Hold")
    assert packet["first_safe_command"] == "GET /data-readiness/registry-integration-status-board"
    assert packet["inspect_next_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert packet["audit_command"] == "GET /data-readiness/registry-integration-decision-audit-checklist"
    assert packet["blocked_or_waiting_count"] >= 0
    assert packet["copyable_read_only_sequence"] == [
        "GET /data-readiness/registry-integration-status-board",
        "GET /data-readiness/bevoelkerung_mio",
        "GET /data-readiness/registry-integration-decision-audit-checklist",
    ]
    assert any("keinen Registry-/Modell-PR" in item for item in packet["do_not_do"])
    assert any("separatem getestetem PR" in item for item in packet["definition_of_done_before_branch"])
    assert "keine amtliche Prognose" in packet["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in packet["guardrail"]
    checklist = body["registry_integration_safe_start_checklist"]
    assert checklist["title"].startswith("Safe-start-Checkliste")
    assert checklist["primary_parameter_key"] == "bevoelkerung_mio"
    assert [row["rank"] for row in checklist["rows"]] == [1, 2, 3, 4]
    assert checklist["rows"][0]["copyable_read_only_command"] == "GET /data-readiness/registry-integration-status-board"
    assert checklist["rows"][1]["copyable_read_only_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert "Stoppschild" in checklist["rows"][3]["check"]
    assert not any("execute=true" in row["copyable_read_only_command"] for row in checklist["rows"])
    assert "keine Registry-/Modellmutation" in checklist["guardrail"]
    cards = body["registry_integration_safe_start_cards"]
    assert cards["title"].startswith("Safe-start-Karten")
    assert cards["primary_parameter_key"] == "bevoelkerung_mio"
    assert [card["rank"] for card in cards["cards"]] == [1, 2, 3, 4]
    assert cards["cards"][0]["primary_action"] == "GET /data-readiness/registry-integration-status-board"
    assert cards["cards"][1]["primary_action"] == "GET /data-readiness/bevoelkerung_mio"
    assert cards["cards"][3]["is_stop_gate"] is True
    assert not any("execute=true" in card["primary_action"] for card in cards["cards"])
    assert "keine Registry-/Modellmutation" in cards["guardrail"]


def test_api_exposes_focused_registry_integration_safe_start_checklist_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-safe-start-checklist?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_safe_start_checklist_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "kein execute=true" in body["guardrail"]
    checklist = body["registry_integration_safe_start_checklist"]
    assert checklist["primary_parameter_key"] == "bevoelkerung_mio"
    assert [row["rank"] for row in checklist["rows"]] == [1, 2, 3, 4]
    assert checklist["rows"][0]["copyable_read_only_command"] == "GET /data-readiness/registry-integration-status-board"
    assert checklist["rows"][1]["copyable_read_only_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert "Stoppschild" in checklist["rows"][3]["check"]
    commands = [row["copyable_read_only_command"] for row in checklist["rows"]]
    assert not any("execute=true" in command for command in commands)
    assert "keine Registry-/Modellmutation" in checklist["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in checklist["guardrail"]
    cards = body["registry_integration_safe_start_cards"]
    assert cards["cards"][0]["primary_action"] == checklist["rows"][0]["copyable_read_only_command"]
    assert cards["cards"][3]["is_stop_gate"] is True
    assert "kein execute=true" in cards["guardrail"]

    invalid = client.get("/data-readiness/registry-integration-safe-start-checklist?limit=0")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["status"] == "invalid_data_readiness_registry_integration_safe_start_checklist_limit"


def test_api_exposes_focused_registry_integration_safe_start_cards_without_apply():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-safe-start-cards?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_safe_start_cards_not_applied"
    assert "kein Branch" in body["guardrail"]
    assert "kein execute=true" in body["guardrail"]
    cards = body["registry_integration_safe_start_cards"]
    assert cards["title"].startswith("Safe-start-Karten")
    assert cards["primary_parameter_key"] == "bevoelkerung_mio"
    assert cards["primary_label"]
    assert [card["rank"] for card in cards["cards"]] == [1, 2, 3, 4]
    assert cards["cards"][0]["primary_action"] == "GET /data-readiness/registry-integration-status-board"
    assert cards["cards"][1]["primary_action"] == "GET /data-readiness/bevoelkerung_mio"
    assert cards["cards"][3]["is_stop_gate"] is True
    assert not any("execute=true" in card["primary_action"] for card in cards["cards"])
    assert "keine Registry-/Modellmutation" in cards["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in cards["guardrail"]

    invalid = client.get("/data-readiness/registry-integration-safe-start-cards?limit=0")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["status"] == "invalid_data_readiness_registry_integration_safe_start_cards_limit"


def test_api_exposes_registry_integration_progress_timeline_without_actions():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-progress-timeline?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_progress_timeline_not_applied"
    assert "kein execute=true" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    timeline = body["registry_integration_progress_timeline"]
    assert timeline["primary_parameter_key"] == "bevoelkerung_mio"
    assert timeline["summary"]["timeline_phases"] == 4
    assert [phase["phase"] for phase in timeline["phases"]] == [
        "Orientieren",
        "Parameter einzeln prüfen",
        "Menschliche Entscheidung vorbereiten",
        "Vor Codearbeit stoppen",
    ]
    assert timeline["phases"][1]["what_to_open"] == "GET /data-readiness/bevoelkerung_mio"
    assert not any("execute=true" in phase["what_to_open"] for phase in timeline["phases"])
    assert "kein Policy-Wirkungsbeweis" in timeline["phases"][3]["guardrail"]

    invalid = client.get("/data-readiness/registry-integration-progress-timeline?limit=0")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["status"] == "invalid_data_readiness_registry_integration_progress_timeline_limit"


def test_api_exposes_registry_integration_command_palette_without_actions():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-command-palette?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_command_palette_not_applied"
    assert "kein execute=true" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    palette = body["registry_integration_command_palette"]
    assert palette["primary_parameter_key"] == "bevoelkerung_mio"
    assert palette["commands"][1]["copyable_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert palette["commands"][-1]["mode"] == "stop_no_command"
    assert palette["commands"][-1]["copyable_command"].startswith("STOP:")
    assert not any("execute=true" in command["copyable_command"] for command in palette["commands"])
    assert "kein Branch" in palette["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in palette["guardrail"]

    invalid = client.get("/data-readiness/registry-integration-command-palette?limit=0")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["status"] == "invalid_data_readiness_registry_integration_command_palette_limit"


def test_api_exposes_registry_integration_operator_briefing_without_actions():
    client = TestClient(api)
    seed_response = client.post("/data-fixtures/seed-reference-review-demo")
    assert seed_response.status_code == 200

    response = client.get("/data-readiness/registry-integration-operator-briefing?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_readiness_registry_integration_operator_briefing_not_applied"
    assert "kein execute=true" in body["guardrail"]
    assert "keine Registry-/Modellmutation" in body["guardrail"]
    briefing = body["registry_integration_operator_briefing"]
    assert briefing["primary_parameter_key"] == "bevoelkerung_mio"
    assert briefing["first_safe_command"] == "GET /data-readiness/registry-integration-status-board"
    assert briefing["next_parameter_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert briefing["human_decision_command"] == "GET /data-readiness/registry-integration-decision-audit-checklist"
    assert briefing["stop_before_code"].startswith("STOP:")
    assert any("Go/Hold/Reject" in question for question in briefing["operator_questions"])
    assert not any("execute=true" in briefing[key] for key in ["first_safe_command", "next_parameter_command", "human_decision_command", "stop_before_code"])
    assert "kein Branch" in briefing["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in briefing["guardrail"]
    cards = body["registry_integration_operator_briefing_cards"]
    assert cards["cards"][0]["copyable_command"] == briefing["first_safe_command"]
    assert cards["cards"][-1]["is_stop_gate"] is True
    assert "kein execute=true" in cards["guardrail"]

    cards_response = client.get("/data-readiness/registry-integration-operator-briefing-cards?limit=3")
    assert cards_response.status_code == 200
    cards_body = cards_response.json()
    assert cards_body["status"] == "data_readiness_registry_integration_operator_briefing_cards_not_applied"
    assert cards_body["registry_integration_operator_briefing_cards"]["cards"][1]["copyable_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert "keine Registry-/Modellmutation" in cards_body["guardrail"]

    sheet = body["registry_integration_operator_briefing_handoff_sheet"]
    assert sheet["rows"][-1]["is_stop_gate"] is True
    assert "Go/Hold/Reject" in sheet["operator_definition_of_done"][2]
    assert "kein Branch" in sheet["guardrail"]

    sheet_response = client.get("/data-readiness/registry-integration-operator-briefing-handoff-sheet?limit=3")
    assert sheet_response.status_code == 200
    sheet_body = sheet_response.json()
    assert sheet_body["status"] == "data_readiness_registry_integration_operator_briefing_handoff_sheet_not_applied"
    assert sheet_body["registry_integration_operator_briefing_handoff_sheet"]["rows"][1]["copyable_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert "kein execute=true" in sheet_body["guardrail"]

    export_packet = body["registry_integration_operator_export_packet"]
    assert export_packet["primary_parameter_key"] == "bevoelkerung_mio"
    assert "GET /data-readiness/bevoelkerung_mio" in export_packet["safe_routes_to_open"]
    assert export_packet["copyable_summary"].startswith("Status lesen")
    assert "Go/Hold/Reject" in export_packet["copyable_summary"]
    assert export_packet["cards_available"] == 4
    assert "kein execute=true" in export_packet["guardrail"]
    assert "keine Registry-/Modellmutation" in export_packet["guardrail"]
    assert not any("execute=true" in route for route in export_packet["safe_routes_to_open"])
    export_audit = body["registry_integration_operator_export_audit"]
    assert export_audit["copy_safe"] is True
    assert export_audit["all_routes_are_get"] is True
    assert export_audit["safe_route_count"] == len(export_packet["safe_routes_to_open"])
    assert len(export_audit["packet_sha256"]) == 64
    assert export_audit["unsafe_findings"] == []
    assert export_audit["verdict_label"] == "copy-safe_status_only"
    assert "Go/Hold/Reject" in export_audit["operator_next_step"]
    assert all(row["passed"] is True for row in export_audit["audit_checklist"])
    assert "Stop-Gate" in export_audit["audit_checklist"][-1]["check"]
    assert "kein execute=true" in export_audit["guardrail"]
    export_digest = body["registry_integration_operator_export_digest"]
    assert export_digest["copy_safe"] is True
    assert export_digest["packet_sha256"] == export_audit["packet_sha256"]
    assert export_digest["safe_route_count"] == export_audit["safe_route_count"]
    assert "GET /data-readiness/bevoelkerung_mio" in export_digest["markdown"]
    assert "Packet-SHA256" in export_digest["markdown"]
    assert "Stop-Gate" in export_digest["markdown"]
    assert "execute=true" not in export_digest["markdown"]
    assert export_digest["unsafe_findings"] == []
    assert "keine Registry-/Modellmutation" in export_digest["guardrail"]
    share_cards = body["registry_integration_operator_export_share_cards"]
    assert share_cards["copy_safe"] is True
    assert share_cards["cards"][0]["value"] == "copy-safe_status_only"
    assert "GET /data-readiness/bevoelkerung_mio" in share_cards["cards"][1]["body"]
    assert share_cards["cards"][2]["is_stop_gate"] is True
    assert "kein execute=true" in share_cards["guardrail"]
    share_brief = body["registry_integration_operator_export_share_brief"]
    assert share_brief["copy_safe"] is True
    assert "GET /data-readiness/bevoelkerung_mio" in share_brief["markdown"]
    assert "STOP:" in share_brief["markdown"]
    assert "execute=true" not in share_brief["markdown"]
    status_card = body["registry_integration_operator_export_status_card"]
    assert status_card["title"] == "Registry-Export-Statuskarte"
    assert status_card["traffic_light"] == "gruen_status_teilbar"
    assert status_card["first_safe_route"].startswith("GET ")
    assert "STOP:" in status_card["stop_condition"]
    assert "execute=true" not in " ".join(status_card["safe_routes_to_open"])
    final_gate = body["registry_integration_final_gate_summary"]
    assert final_gate["can_start_code_work_from_this_surface"] is False
    assert final_gate["status_shareable"] is True
    assert final_gate["first_safe_route"].startswith("GET ")
    assert any("Go/Hold/Reject" in item for item in final_gate["required_external_go_before_branch"])
    assert "STOP" in final_gate["operator_answer"]
    assert "kein Branch" in final_gate["guardrail"]

    final_gate_response = client.get("/data-readiness/registry-integration-final-gate-summary?limit=3")
    assert final_gate_response.status_code == 200
    final_gate_body = final_gate_response.json()
    assert final_gate_body["status"] == "data_readiness_registry_integration_final_gate_summary_not_applied"
    assert final_gate_body["registry_integration_final_gate_summary"]["can_start_code_work_from_this_surface"] is False
    assert "kein execute=true" in final_gate_body["guardrail"]

    export_response = client.get("/data-readiness/registry-integration-operator-export-packet?limit=3")
    assert export_response.status_code == 200
    export_body = export_response.json()
    assert export_body["status"] == "data_readiness_registry_integration_operator_export_packet_not_applied"
    assert export_body["registry_integration_operator_export_packet"]["safe_routes_to_open"][1] == "GET /data-readiness/bevoelkerung_mio"
    assert "kein Branch" in export_body["guardrail"]

    audit_response = client.get("/data-readiness/registry-integration-operator-export-audit?limit=3")
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["status"] == "data_readiness_registry_integration_operator_export_audit_not_applied"
    assert audit_body["registry_integration_operator_export_audit"]["copy_safe"] is True
    assert "kein execute=true" in audit_body["guardrail"]

    digest_response = client.get("/data-readiness/registry-integration-operator-export-digest?limit=3")
    assert digest_response.status_code == 200
    digest_body = digest_response.json()
    assert digest_body["status"] == "data_readiness_registry_integration_operator_export_digest_not_applied"
    assert digest_body["registry_integration_operator_export_digest"]["copy_safe"] is True
    assert "GET /data-readiness/bevoelkerung_mio" in digest_body["registry_integration_operator_export_digest"]["markdown"]
    assert "kein execute=true" in digest_body["guardrail"]

    share_cards_response = client.get("/data-readiness/registry-integration-operator-export-share-cards?limit=3")
    assert share_cards_response.status_code == 200
    share_cards_body = share_cards_response.json()
    assert share_cards_body["status"] == "data_readiness_registry_integration_operator_export_share_cards_not_applied"
    assert share_cards_body["registry_integration_operator_export_share_cards"]["copy_safe"] is True
    assert share_cards_body["registry_integration_operator_export_share_cards"]["cards"][2]["is_stop_gate"] is True
    assert "kein execute=true" in share_cards_body["guardrail"]

    bundle = body["registry_integration_operator_export_bundle"]
    assert bundle["title"] == "Registry-Operator-Export-Bundle"
    assert bundle["copy_safe"] is True
    assert bundle["packet_sha256"] == export_audit["packet_sha256"]
    assert "GET /data-readiness/registry-integration-operator-export-digest" in bundle["focused_status_routes"]
    assert "Branch/PR stoppen" in " ".join(bundle["bundle_steps"])
    assert "kein execute=true" in bundle["guardrail"]

    bundle_response = client.get("/data-readiness/registry-integration-operator-export-bundle?limit=3")
    assert bundle_response.status_code == 200
    bundle_body = bundle_response.json()
    assert bundle_body["status"] == "data_readiness_registry_integration_operator_export_bundle_not_applied"
    assert bundle_body["registry_integration_operator_export_bundle"]["copy_safe"] is True
    assert bundle_body["registry_integration_operator_export_bundle"]["focused_status_routes"][0].startswith("GET ")
    assert "kein execute=true" in bundle_body["guardrail"]

    walkthrough = body["registry_integration_operator_export_bundle_walkthrough"]
    assert walkthrough["copy_safe"] is True
    assert walkthrough["steps"][0]["label"] == "Copy-Safety prüfen"
    assert walkthrough["steps"][-1]["safe_route"] == "GET /data-readiness/registry-integration-decision-template"
    assert "execute=true" not in " ".join(step["safe_route"] for step in walkthrough["steps"])
    assert "keine Registry-/Modellmutation" in walkthrough["guardrail"]

    walkthrough_response = client.get("/data-readiness/registry-integration-operator-export-bundle-walkthrough?limit=3")
    assert walkthrough_response.status_code == 200
    walkthrough_body = walkthrough_response.json()
    assert walkthrough_body["status"] == "data_readiness_registry_integration_operator_export_bundle_walkthrough_not_applied"
    assert len(walkthrough_body["registry_integration_operator_export_bundle_walkthrough"]["steps"]) == 4
    assert "kein execute=true" in walkthrough_body["guardrail"]

    next_review = body["registry_integration_operator_export_next_review"]
    assert next_review["next_safe_action"] == "Copy-Safety prüfen"
    assert next_review["copyable_status_route"] == "GET /data-readiness/registry-integration-operator-export-audit"
    assert next_review["then_open_parameter_route"].startswith("GET /data-readiness/")
    assert any("Decision-Template" in check for check in next_review["operator_checks"])
    assert "keine Registry-/Modellmutation" in next_review["guardrail"]

    next_review_response = client.get("/data-readiness/registry-integration-operator-export-next-review?limit=3")
    assert next_review_response.status_code == 200
    next_review_body = next_review_response.json()
    assert next_review_body["status"] == "data_readiness_registry_integration_operator_export_next_review_not_applied"
    assert next_review_body["registry_integration_operator_export_next_review"]["next_safe_action"] == "Copy-Safety prüfen"
    assert "kein execute=true" in next_review_body["guardrail"]

    invalid = client.get("/data-readiness/registry-integration-operator-briefing?limit=0")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["status"] == "invalid_data_readiness_registry_integration_operator_briefing_limit"


def test_api_exposes_registry_operator_export_review_stoplight_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-operator-export-review-stoplight")

    assert response.status_code == 200
    payload = response.json()
    stoplight = payload["registry_integration_operator_export_review_stoplight"]
    assert payload["status"] == "data_readiness_registry_integration_operator_export_review_stoplight_not_applied"
    assert stoplight["title"] == "Registry-Export-Review-Stoplight"
    assert stoplight["routes_to_open_in_order"]
    assert all(route.startswith("GET ") for route in stoplight["routes_to_open_in_order"])
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in stoplight["guardrail"]


def test_api_exposes_registry_operator_export_review_checklist_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-operator-export-review-checklist")

    assert response.status_code == 200
    payload = response.json()
    checklist = payload["registry_integration_operator_export_review_checklist"]
    assert payload["status"] == "data_readiness_registry_integration_operator_export_review_checklist_not_applied"
    assert checklist["title"] == "Registry-Export-Review-Checkliste"
    assert checklist["checklist_items"]
    assert all(route.startswith("GET ") for route in checklist["safe_routes_to_open"])
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in checklist["guardrail"]


def test_api_exposes_registry_operator_export_share_brief_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-operator-export-share-brief")

    assert response.status_code == 200
    payload = response.json()
    share_brief = payload["registry_integration_operator_export_share_brief"]
    assert payload["status"] == "data_readiness_registry_integration_operator_export_share_brief_not_applied"
    assert share_brief["title"] == "Registry-Export-Share-Brief"
    assert share_brief["copy_safe"] is True
    assert all(route.startswith("GET ") for route in share_brief["safe_routes_to_open"])
    assert "STOP:" in share_brief["markdown"]
    assert "execute=true" not in share_brief["markdown"]
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in share_brief["guardrail"]


def test_api_exposes_registry_operator_export_status_card_without_execution():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-operator-export-status-card")

    assert response.status_code == 200
    payload = response.json()
    status_card = payload["registry_integration_operator_export_status_card"]
    assert payload["status"] == "data_readiness_registry_integration_operator_export_status_card_not_applied"
    assert status_card["title"] == "Registry-Export-Statuskarte"
    assert status_card["copy_safe"] is True
    assert status_card["traffic_light"] == "gruen_status_teilbar"
    assert status_card["first_safe_route"].startswith("GET ")
    assert all(route.startswith("GET ") for route in status_card["safe_routes_to_open"])
    assert "STOP:" in status_card["stop_condition"]
    assert "execute=true" not in " ".join(status_card["safe_routes_to_open"])
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in status_card["guardrail"]


def test_api_exposes_registry_final_gate_summary_without_code_work():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-final-gate-summary")

    assert response.status_code == 200
    payload = response.json()
    summary = payload["registry_integration_final_gate_summary"]
    assert payload["status"] == "data_readiness_registry_integration_final_gate_summary_not_applied"
    assert summary["title"] == "Letztes Gate vor Registry-/Modell-PR"
    assert summary["can_start_code_work_from_this_surface"] is False
    assert summary["status_shareable"] is True
    assert summary["first_safe_route"].startswith("GET ")
    assert any("Go/Hold/Reject" in item for item in summary["required_external_go_before_branch"])
    assert "STOP" in summary["operator_answer"]
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in summary["guardrail"]
    stub = payload["registry_integration_final_gate_issue_stub"]
    assert stub["copy_safe"] is True
    assert stub["status_route"].startswith("GET ")
    assert "Codearbeit startet nicht" in stub["markdown"]
    assert "execute=true" not in stub["markdown"]


def test_api_exposes_registry_final_gate_issue_stub_without_code_work():
    client = TestClient(api)
    response = client.get("/data-readiness/registry-integration-final-gate-issue-stub")

    assert response.status_code == 200
    payload = response.json()
    stub = payload["registry_integration_final_gate_issue_stub"]
    assert payload["status"] == "data_readiness_registry_integration_final_gate_issue_stub_not_applied"
    assert stub["title"] == "Registry-Final-Gate Issue-Stub"
    assert stub["copy_safe"] is True
    assert stub["unsafe_findings"] == []
    assert "STOP:" in stub["markdown"]
    assert "git commit" not in stub["markdown"]
    assert "kein execute=true" in payload["guardrail"]
    assert "keine Registry-/Modellmutation" in stub["guardrail"]


def test_simulate_exposes_uncertainty_band_summary_for_agents():
    client = TestClient(api)
    response = client.post(
        "/simulate",
        json={"parameter_changes": {"medizinstudienplaetze": 9000}, "n_runs": 5, "n_years": 2, "seed": 7},
    )

    assert response.status_code == 200
    body = response.json()
    rows = body["uncertainty_band_summary"]
    assert rows
    assert {"metric_key", "mean", "p5", "p95", "signal", "guardrail"} <= set(rows[0])
    first_contact_cards = body["uncertainty_first_contact_cards"]
    assert first_contact_cards
    assert {"step", "title", "answer_first", "what_to_open_next", "guardrail"} <= set(first_contact_cards[0])
    assert "KPI-Detailkarte" in first_contact_cards[0]["what_to_open_next"]
    assert "keine amtliche Prognose" in first_contact_cards[0]["guardrail"]
    questions = body["uncertainty_result_questions"]
    assert questions
    assert {"question", "answer_first", "what_to_open_next", "safe_reading", "guardrail"} <= set(questions[0])
    assert "KPI-Detailkarte" in questions[0]["what_to_open_next"]
    checklist = body["uncertainty_decision_checklist"]
    assert checklist
    assert {"decision_status", "required_check_before_decision", "what_to_open_next", "guardrail"} <= set(checklist[0])
    assert "KPI-Detailkarte" in checklist[0]["what_to_open_next"]
    assert "keine amtliche Prognose" in checklist[0]["guardrail"]
    storyboard = body["uncertainty_reading_storyboard"]
    assert [step["stage"] for step in storyboard] == [
        "Orientieren",
        "Robustheit prüfen",
        "Wirkpfad gegenlesen",
        "Entscheidung bremsen",
    ]
    assert "P5/P95" in storyboard[0]["answer_first"]
    assert "KPI-Detailkarte" in storyboard[0]["open_next"]
    assert "keine amtliche Prognose" in storyboard[-1]["answer_first"]
    assert "kein Wirksamkeitsnachweis" in storyboard[-1]["guardrail"]
    packet = body["uncertainty_interpretation_packet"]
    assert packet["mode"] == "read_only_uncertainty_interpretation"
    assert "P5/P95-Kennzahlen" in packet["summary"]
    assert packet["first_contact_cards"] == first_contact_cards[: len(packet["first_contact_cards"])]
    assert packet["reading_storyboard"] == storyboard[: len(packet["reading_storyboard"])]
    assert "Annahmen-/Evidenzcheck" in " ".join(packet["definition_of_done_before_decision"])
    assert "execute=true" not in str(packet)
    assert "keine amtliche Prognose" in body["uncertainty_guardrail"]
    assert all("kein Wirksamkeitsnachweis" in row["guardrail"] for row in rows)
    assert body["final_year_summary"]["jahr"] == 2028.0
