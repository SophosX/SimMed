import json

from data_ingestion import (
    ReviewedTransformation,
    build_connector_execution_workbench,
    build_cached_snapshot_integrity_action_plan,
    build_cached_snapshot_integrity_handoff_packet,
    build_cached_snapshot_integrity_report,
    build_cached_snapshot_review_start_checklist,
    build_cached_snapshot_review_start_handoff_packet,
    build_cached_snapshot_review_start_status_cards,
    build_transformation_review_draft_example_payload,
    build_transformation_review_draft_handoff_packet,
    build_transformation_review_draft_preflight,
    build_transformation_review_draft_status_cards,
    build_transformation_review_draft_validation_packet,
    validate_transformation_review_draft_payload,
    build_connector_snapshot_requests,
    build_data_connector_queue,
    build_data_passport_rows,
    build_data_readiness_backlog,
    build_data_readiness_dashboard_cards,
    build_data_readiness_first_contact_guide,
    build_data_readiness_gate_plan,
    build_data_readiness_integration_preflight,
    build_data_readiness_integration_plan,
    build_data_readiness_integration_pr_brief,
    build_data_readiness_platform_brief,
    build_data_readiness_registry_diff_preview,
    build_data_readiness_registry_integration_decision_record,
    build_data_readiness_registry_integration_command_palette,
    build_data_readiness_registry_integration_decision_template,
    build_data_readiness_registry_integration_handoff_packet,
    build_data_readiness_registry_integration_operator_briefing_cards,
    build_data_readiness_registry_integration_operator_steps,
    build_data_readiness_registry_integration_pr_runbook,
    build_data_readiness_registry_integration_progress_timeline,
    build_data_readiness_registry_integration_safe_start_cards,
    build_data_readiness_registry_integration_safe_start_checklist,
    build_data_readiness_registry_integration_safe_start_packet,
    build_data_readiness_registry_integration_status_board,
    build_data_readiness_registry_integration_status_cards,
    build_data_readiness_registry_integration_decision_audit_checklist,
    build_data_readiness_summary,
    build_next_data_readiness_actions,
    build_parameter_data_workflow_card,
    build_parameter_snapshot_status,
    build_transformation_review_template,
    cache_source_payload,
    execute_connector_snapshot_request,
    fetch_url_payload,
    list_cached_snapshots,
    list_reviewed_transformations,
    read_snapshot_manifest,
    read_transformation_review,
    record_reviewed_transformation,
    seed_reference_fixture_reviewed_transformations,
    seed_reference_fixture_snapshots,
    snapshot_payload_hash,
    verify_cached_snapshot_integrity,
)



def test_cache_source_payload_writes_raw_file_and_manifest(tmp_path):
    payload = b"year,value\n2024,84.4\n"

    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=payload,
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        license_or_terms_note="test fixture only",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw baseline fixture, no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )

    assert snapshot.sha256 == snapshot_payload_hash(payload)
    assert snapshot.output_parameter_keys == ("bevoelkerung_mio",)

    raw_path = tmp_path / "destatis_genesis" / "raw" / "population.csv"
    manifest_path = tmp_path / "destatis_genesis" / "manifests" / "population.manifest.json"
    assert raw_path.read_bytes() == payload
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sha256"] == snapshot.sha256
    assert manifest["transformation_note"] == "raw baseline fixture, no model mutation"

    restored = read_snapshot_manifest(manifest_path)
    assert restored == snapshot


def test_cached_snapshot_integrity_report_recomputes_sha_without_model_import(tmp_path):
    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )

    integrity = verify_cached_snapshot_integrity(snapshot)
    assert integrity["integrity_status"] == "sha256_match"
    assert integrity["expected_sha256"] == snapshot.sha256
    assert integrity["actual_sha256"] == snapshot.sha256
    assert integrity["output_parameter_keys"] == ["bevoelkerung_mio"]
    assert integrity["source_period"] == "2024"
    assert "Registry-/Modellintegration" in integrity["guardrail"]

    report = build_cached_snapshot_integrity_report(cache_root=tmp_path)
    assert report["summary"] == {
        "snapshots_seen": 1,
        "sha256_match": 1,
        "sha256_mismatch": 0,
        "raw_file_missing": 0,
    }
    assert report["rows"][0]["integrity_status"] == "sha256_match"
    assert "kein Netzwerkabruf" in report["guardrail"]

    raw_path = tmp_path / "destatis_genesis" / "raw" / "population.csv"
    raw_path.write_bytes(b"tampered")
    tampered = build_cached_snapshot_integrity_report(cache_root=tmp_path)
    assert tampered["summary"]["sha256_mismatch"] == 1
    assert tampered["rows"][0]["integrity_status"] == "sha256_mismatch"


def test_cached_snapshot_integrity_action_plan_blocks_bad_cache_before_review(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    report = build_cached_snapshot_integrity_report(cache_root=tmp_path)
    ok_plan = build_cached_snapshot_integrity_action_plan(report)
    assert ok_plan["overall_status"] == "integrity_ok_but_not_reviewed"
    assert ok_plan["summary"]["ready_for_transformation_review_only"] == 1
    assert ok_plan["rows"][0]["may_start_transformation_review"] is True
    assert "nicht Modellintegration" in ok_plan["rows"][0]["guardrail"]

    (tmp_path / "destatis_genesis" / "raw" / "population.csv").write_bytes(b"tampered")
    bad_report = build_cached_snapshot_integrity_report(cache_root=tmp_path)
    bad_plan = build_cached_snapshot_integrity_action_plan(bad_report)
    assert bad_plan["overall_status"] == "integrity_blocker_before_review"
    assert bad_plan["summary"]["integrity_blockers"] == 1
    assert bad_plan["rows"][0]["may_start_transformation_review"] is False
    assert "blockiert Review" in bad_plan["rows"][0]["guardrail"]
    assert "kein Netzwerkabruf" in bad_plan["guardrail"]


def test_cached_snapshot_integrity_handoff_packet_is_copyable_and_read_only(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    report = build_cached_snapshot_integrity_report(cache_root=tmp_path)

    handoff = build_cached_snapshot_integrity_handoff_packet(report)

    assert handoff["status"] == "integrity_ok_but_not_reviewed"
    assert handoff["status_route"] == "GET /data-snapshots/integrity"
    assert "curl -s" in handoff["copyable_status_command"]
    assert "Transformation-Review" in handoff["first_safe_step"]
    assert "Registry-/Modellintegration separat" in " ".join(handoff["operator_sequence"])
    assert "kein execute=true" in handoff["guardrail"]
    assert "keine Registry-/Modellmutation" in handoff["guardrail"]



def test_cached_snapshot_review_start_checklist_routes_only_sha_matched_snapshots(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    report = build_cached_snapshot_integrity_report(cache_root=tmp_path)

    checklist = build_cached_snapshot_review_start_checklist(report)

    assert checklist["status"] == "review_start_ready_for_manual_check"
    assert checklist["ready_snapshot_count"] == 1
    row = checklist["rows"][0]
    assert row["source_snapshot_sha256"] == report["rows"][0]["actual_sha256"]
    assert row["review_template_routes"] == ["GET /data-connectors/transformation-review-template/bevoelkerung_mio"]
    assert "Denominator" in " ".join(row["first_review_questions"])
    assert row["may_create_review_after_manual_check"] is True
    assert "keine Registry-/Modellmutation" in checklist["guardrail"]

    (tmp_path / "destatis_genesis" / "raw" / "population.csv").write_bytes(b"tampered")
    blocked = build_cached_snapshot_review_start_checklist(build_cached_snapshot_integrity_report(cache_root=tmp_path))
    assert blocked["status"] == "review_start_blocked_by_integrity"
    assert blocked["blocked_snapshot_count"] == 1
    assert blocked["rows"] == []


def test_cached_snapshot_review_start_status_cards_make_pre_review_gate_mobile_safe(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )

    cards = build_cached_snapshot_review_start_status_cards(checklist)

    assert [card["order"] for card in cards] == [1, 2, 3]
    assert cards[0]["route"] == "GET /data-snapshots/integrity"
    assert "1 SHA256-passende Snapshots" in cards[0]["signal"]
    assert cards[1]["status"] == "bereit für manuelle Prüfung"
    assert "Review-Vorlage öffnen" in cards[1]["first_action"]
    assert cards[2]["route"] == "GET /data-readiness/integration-preflight"
    assert "kein automatischer Import" in cards[2]["guardrail"]
    assert "kein Wirkungsbeweis" in cards[2]["guardrail"]


def test_cached_snapshot_review_start_handoff_packet_points_to_review_templates_without_creating_reviews(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )

    handoff = build_cached_snapshot_review_start_handoff_packet(checklist)

    assert handoff["status"] == "manual_review_template_ready"
    assert handoff["checklist_route"] == "GET /data-snapshots/review-start-checklist"
    assert handoff["first_review_template_route"] == "GET /data-connectors/transformation-review-template/bevoelkerung_mio"
    assert "curl -s" in handoff["copyable_status_command"]
    assert "Registry-/Modellintegration erst in separatem getesteten PR" in " ".join(handoff["operator_sequence"])
    assert "keine Review-Erzeugung" in handoff["guardrail"]
    assert "keine Registry-/Modellmutation" in handoff["guardrail"]


def test_transformation_review_draft_handoff_packet_turns_preflight_into_copyable_draft_steps(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )
    preflight = build_transformation_review_draft_preflight(checklist)

    packet = build_transformation_review_draft_handoff_packet(preflight)

    assert packet["status"] == "draft_ready_for_manual_completion"
    assert packet["preflight_route"] == "GET /data-snapshots/review-draft-preflight"
    assert packet["first_parameter_key"] == "bevoelkerung_mio"
    assert packet["first_review_template_route"] == "GET /data-connectors/transformation-review-template/bevoelkerung_mio"
    assert "curl -s" in packet["copyable_preflight_command"]
    assert "ReviewedTransformation erst nach manueller Prüfung erfassen" in packet["operator_sequence"]
    assert "keine Review-Erzeugung" in packet["guardrail"]
    assert "keine Registry-/Modellmutation" in packet["guardrail"]


def test_transformation_review_draft_example_payload_is_copyable_but_not_persisted(tmp_path):
    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )
    preflight = build_transformation_review_draft_preflight(checklist)

    example = build_transformation_review_draft_example_payload(preflight)

    assert example["status"] == "draft_example_ready_not_persisted"
    assert example["example_payload"]["parameter_key"] == "bevoelkerung_mio"
    assert example["example_payload"]["source_snapshot_sha256"] == snapshot.sha256
    assert "review-draft/validate" in example["copyable_validate_command"]
    assert "Rohdatei und SHA256-Manifest" in " ".join(example["required_manual_replacements"])
    assert "keine Review-Erzeugung" in example["guardrail"]
    assert "keine Registry-/Modellmutation" in example["guardrail"]



def test_transformation_review_draft_preflight_lists_required_fields_without_recording_review(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )

    preflight = build_transformation_review_draft_preflight(checklist)

    assert preflight["status"] == "draft_preflight_ready_for_manual_review"
    assert preflight["ready_draft_count"] == 1
    assert "noch nichts persistieren" in preflight["first_safe_step"]
    row = preflight["rows"][0]
    assert row["parameter_key"] == "bevoelkerung_mio"
    assert row["review_template_route"] == "GET /data-connectors/transformation-review-template/bevoelkerung_mio"
    assert row["draft_status"] == "template_ready_not_recorded"
    required = " ".join(row["required_before_record_review"])
    assert "reviewer identity" in required
    assert "method_note" in required
    assert "output_value" in required
    assert "source_snapshot_sha256" in required
    assert "keine Review-Erzeugung" in row["guardrail"]
    assert "keine Registry-/Modellmutation" in preflight["guardrail"]


def test_transformation_review_draft_status_cards_explain_manual_gate_without_writes(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )
    preflight = build_transformation_review_draft_preflight(checklist)

    cards = build_transformation_review_draft_status_cards(preflight)

    assert [card["order"] for card in cards] == [1, 2, 3]
    assert cards[0]["route"] == "GET /data-snapshots/review-draft-preflight"
    assert "1 vorbereitete Draft-Zeilen" in cards[0]["signal"]
    assert "Reviewer" in cards[0]["first_action"]
    assert cards[1]["status"] == "bereit für manuelle Draft-Prüfung"
    assert cards[1]["route"] == "GET /data-snapshots/review-draft-handoff"
    assert "keine Review-Erzeugung" in cards[1]["guardrail"]
    assert "separater Integrationspfad" == cards[2]["status"]
    assert "keine automatische Modellmutation" in cards[2]["guardrail"]


def test_transformation_review_draft_payload_validation_is_read_only_gate(tmp_path):
    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )
    preflight = build_transformation_review_draft_preflight(checklist)

    incomplete = validate_transformation_review_draft_payload(
        preflight,
        {
            "parameter_key": "bevoelkerung_mio",
            "source_snapshot_sha256": snapshot.sha256,
            "reviewer": "",
            "method_note": "GENESIS fixture row 2024 checked manually",
            "output_value": 84.4,
            "output_unit": "Mio. Personen",
            "caveat": "Fixture-only; no live import and no model integration.",
        },
    )
    assert incomplete["status"] == "draft_validation_incomplete"
    assert incomplete["matched_preflight_row"] is True
    assert "reviewer" in incomplete["missing_fields"]
    assert "keine Review-Erzeugung" in incomplete["guardrail"]

    ready = validate_transformation_review_draft_payload(
        preflight,
        {
            "parameter_key": "bevoelkerung_mio",
            "source_snapshot_sha256": snapshot.sha256,
            "reviewer": "Evidence Agent",
            "method_note": "GENESIS fixture row 2024 checked manually",
            "output_value": 84.4,
            "output_unit": "Mio. Personen",
            "caveat": "Fixture-only; no live import and no model integration.",
        },
    )
    assert ready["status"] == "draft_validation_ready_for_manual_record_review"
    assert ready["missing_fields"] == []
    assert ready["matched_review_template_route"] == "GET /data-connectors/transformation-review-template/bevoelkerung_mio"
    assert "separat erfasst" in ready["next_safe_step"]
    assert "keine Registry-/Modellmutation" in ready["guardrail"]

    mismatch = validate_transformation_review_draft_payload(
        preflight,
        {
            "parameter_key": "bevoelkerung_mio",
            "source_snapshot_sha256": "wrong-sha",
            "reviewer": "Evidence Agent",
            "method_note": "checked",
            "output_value": 84.4,
            "output_unit": "Mio. Personen",
            "caveat": "Fixture-only.",
        },
    )
    assert mismatch["status"] == "draft_validation_blocked_by_snapshot_mismatch"
    assert mismatch["matched_preflight_row"] is False



def test_transformation_review_draft_validation_packet_guides_copyable_read_only_validation(tmp_path):
    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    checklist = build_cached_snapshot_review_start_checklist(
        build_cached_snapshot_integrity_report(cache_root=tmp_path)
    )
    preflight = build_transformation_review_draft_preflight(checklist)
    validation = validate_transformation_review_draft_payload(
        preflight,
        {
            "parameter_key": "bevoelkerung_mio",
            "source_snapshot_sha256": snapshot.sha256,
            "reviewer": "",
            "method_note": "GENESIS fixture row 2024 checked manually",
            "output_value": 84.4,
            "output_unit": "Mio. Personen",
            "caveat": "Fixture-only; no live import and no model integration.",
        },
    )

    packet = build_transformation_review_draft_validation_packet(preflight, validation)

    assert packet["status"] == "draft_validation_incomplete"
    assert packet["parameter_key"] == "bevoelkerung_mio"
    assert packet["missing_fields"] == ["reviewer"]
    assert packet["validate_route"] == "POST /data-snapshots/review-draft/validate"
    assert "reviewer" in packet["first_safe_step"]
    assert "review-draft/validate" in packet["copyable_validate_command"]
    assert "bevoelkerung_mio" in packet["copyable_validate_command"]
    assert "Payload nur gegen den Validierungsendpoint" in " ".join(packet["operator_sequence"])
    assert "keine Review-Erzeugung" in packet["guardrail"]
    assert "keine Registry-/Modellmutation" in packet["guardrail"]


def test_snapshot_status_is_read_only_and_conservative(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2024,84.4\n",
        filename="population-old.csv",
        cache_root=tmp_path,
        source_period="2024",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="fixture only; no model mutation",
        retrieved_at="2026-04-29T19:00:00+00:00",
    )
    latest = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2025,84.5\n",
        filename="population-new.csv",
        cache_root=tmp_path,
        source_period="2025",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="newer fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )

    snapshots = list_cached_snapshots(tmp_path)
    assert [s.source_period for s in snapshots] == ["2025", "2024"]

    rows = build_parameter_snapshot_status(("bevoelkerung_mio", "geburtenrate"), cache_root=tmp_path)
    population = rows[0]
    fertility = rows[1]

    assert population["parameter_key"] == "bevoelkerung_mio"
    assert population["has_cached_snapshot"] is True
    assert population["snapshot_count"] == 2
    assert population["latest_snapshot"]["sha256"] == latest.sha256
    assert "Modellwert bleibt" in population["status_note"]

    assert fertility == {
        "parameter_key": "geburtenrate",
        "has_cached_snapshot": False,
        "snapshot_count": 0,
        "latest_snapshot": None,
        "status_note": "Noch kein Rohdaten-Snapshot im lokalen Cache verknüpft.",
    }


def test_data_passport_separates_registry_status_from_raw_cache(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2025,84.5\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2025",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
            "source_version": "Destatis referenced baseline; automated snapshot pending",
            "data_lineage": "Registry baseline; reviewed import pending.",
        },
        {
            "key": "telemedizin_rate",
            "label": "Telemedizin-Nutzung",
            "unit": "share",
            "evidence_grade": "E",
            "source_ids": ["expert_assumption"],
            "data_status": "annahme",
            "source_version": "",
            "data_lineage": "Scenario assumption.",
        },
    ]

    rows = build_data_passport_rows(parameters, cache_root=tmp_path)

    population = rows[0]
    assert population["registry_label"] == "aus Daten"
    assert population["cache"]["has_cached_snapshot"] is True
    assert "geprüfte Transformation separat" in population["passport_note"]

    telemedicine = rows[1]
    assert telemedicine["registry_label"] == "Annahme, nicht aus Daten"
    assert telemedicine["cache"]["has_cached_snapshot"] is False
    assert "nicht als gemessenen Datenwert" in telemedicine["passport_note"]


def test_reference_fixture_seeds_population_cache_without_model_import(tmp_path):
    snapshots = seed_reference_fixture_snapshots(cache_root=tmp_path)

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.source_id == "destatis_genesis"
    assert snapshot.output_parameter_keys == ("bevoelkerung_mio",)
    assert "Fixture mirrors the registry default only" in snapshot.transformation_note
    assert "replace with a live reviewed GENESIS snapshot" in snapshot.license_or_terms_note

    rows = build_parameter_snapshot_status(("bevoelkerung_mio", "geburtenrate"), cache_root=tmp_path)
    assert rows[0]["has_cached_snapshot"] is True
    assert rows[0]["latest_snapshot"]["source_period"] == "registry-baseline fixture"
    assert "Modellwert bleibt" in rows[0]["status_note"]
    assert rows[1]["has_cached_snapshot"] is False


def test_reference_fixture_review_can_create_green_integration_pr_path_without_model_import(tmp_path):
    reviews = seed_reference_fixture_reviewed_transformations(cache_root=tmp_path)

    assert len(reviews) == 1
    review = reviews[0]
    assert review.parameter_key == "bevoelkerung_mio"
    assert review.status == "reviewed_model_ready"
    assert "not a live GENESIS download" in review.caveat

    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
            "source_version": "fixture only; live GENESIS import pending",
            "data_lineage": "Static fixture review for workflow demonstration only.",
        }
    ]
    passport = build_data_passport_rows(parameters, cache_root=tmp_path)
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    preflight = build_data_readiness_integration_preflight(backlog, passport)
    plan = build_data_readiness_integration_plan(preflight)
    pr_brief = build_data_readiness_integration_pr_brief(plan)

    assert passport[0]["cache"]["has_cached_snapshot"] is True
    assert passport[0]["transformation_review"]["status"] == "reviewed_model_ready"
    assert backlog[0]["next_gate"] == "explicit_model_integration_needed"
    assert preflight["summary"]["ready_for_integration_plan"] == 1
    assert plan["plans"][0]["status"] == "planbar_aber_nicht_ausgefuehrt"
    assert pr_brief["briefs"][0]["branch_name"] == "feat/integrate-reviewed-bevoelkerung_mio"
    combined_guardrails = " ".join(
        [passport[0]["passport_note"], preflight["guardrail"], plan["guardrail"], pr_brief["guardrail"]]
    )
    assert "keine Registry-/Modellmutation" in combined_guardrails
    assert "keine amtliche Prognose" in combined_guardrails
    assert "kein Wirkungsbeweis" in combined_guardrails



def test_reviewed_transformation_is_separate_passport_layer(tmp_path):
    snapshot = cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2025,84.5\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2025",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    review = ReviewedTransformation(
        parameter_key="bevoelkerung_mio",
        source_snapshot_sha256=snapshot.sha256,
        status="reviewed_no_model_import",
        reviewed_at="2026-04-29T21:00:00+00:00",
        reviewer="SimMed Integrator",
        method_note="Compared fixture value to registry default for plumbing only.",
        caveat="Fixture is not a live GENESIS import and must not mutate the model.",
        output_value=84.5,
        output_unit="million people",
    )

    review_path = record_reviewed_transformation(review, cache_root=tmp_path)

    assert read_transformation_review(review_path) == review
    assert list_reviewed_transformations(tmp_path) == [review]

    rows = build_data_passport_rows(
        [
            {
                "key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "unit": "million people",
                "evidence_grade": "A",
                "source_ids": ["destatis_genesis"],
                "data_status": "aus_daten",
                "source_version": "Destatis referenced baseline; automated snapshot pending",
                "data_lineage": "Registry baseline; reviewed import pending.",
            }
        ],
        cache_root=tmp_path,
    )

    passport = rows[0]
    assert passport["cache"]["has_cached_snapshot"] is True
    assert passport["transformation_review"]["status"] == "reviewed_no_model_import"
    assert "nicht ins Modell übernommen" in passport["transformation_review"]["label"]
    assert "bewusst nicht als Modellwert übernommen" in passport["passport_note"]
    assert "must not mutate" in passport["transformation_review"]["review"]["caveat"]


def test_data_passport_shows_missing_transformation_review(tmp_path):
    rows = build_data_passport_rows(
        [
            {
                "key": "telemedizin_rate",
                "label": "Telemedizin-Nutzung",
                "unit": "share",
                "evidence_grade": "E",
                "source_ids": ["expert_assumption"],
                "data_status": "annahme",
            }
        ],
        cache_root=tmp_path,
    )

    assert rows[0]["transformation_review"] == {
        "status": "not_reviewed",
        "label": "Keine geprüfte Transformation",
        "review": None,
        "status_note": "Rohdaten wurden noch nicht nachvollziehbar in einen Modellwert übersetzt.",
    }
    assert "Annahme ohne verknüpften Rohdaten-Snapshot" in rows[0]["passport_note"]


def test_data_readiness_summary_counts_gates_without_model_import(tmp_path):
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2025,84.5\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2025",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
        {
            "key": "telemedizin_rate",
            "label": "Telemedizin-Nutzung",
            "unit": "share",
            "evidence_grade": "E",
            "source_ids": ["expert_assumption"],
            "data_status": "annahme",
        },
    ]

    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    summary = build_data_readiness_summary(backlog)

    assert summary["total_items"] == 2
    assert summary["counts_by_gate"]["snapshot_needed"] == 1
    assert summary["counts_by_gate"]["transformation_review_needed"] == 1
    assert summary["primary_focus"]["parameter"] == "Telemedizin-Nutzung"
    assert "kein Live-Import" in summary["plain_language_note"]
    assert "kein Wirkungsbeweis" in summary["plain_language_note"]

    gate_plan = build_data_readiness_gate_plan(backlog)
    assert [gate["gate"] for gate in gate_plan] == [
        "snapshot_needed",
        "transformation_review_needed",
        "explicit_model_integration_needed",
        "monitor_only",
    ]
    snapshot_gate = gate_plan[0]
    review_gate = gate_plan[1]
    assert snapshot_gate["open_count"] == 1
    assert snapshot_gate["example_parameters"] == ["Telemedizin-Nutzung"]
    assert "Manifest" in snapshot_gate["why_this_gate"]
    assert review_gate["open_count"] == 1
    assert review_gate["example_parameters"] == ["Bevölkerung"]
    combined = " ".join(str(value) for gate in gate_plan for value in gate.values())
    assert "keine Live-Datenübernahme" in combined
    assert "keine Modellmutation" in combined
    assert "kein Wirkungsbeweis" in combined


def test_data_connector_queue_groups_snapshot_work_by_authoritative_source(tmp_path):
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
        {
            "key": "fertilitaetsrate",
            "label": "Fertilität",
            "unit": "births per woman",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
        {
            "key": "telemedizin_rate",
            "label": "Telemedizin-Nutzung",
            "unit": "share",
            "evidence_grade": "E",
            "source_ids": ["expert_assumption"],
            "data_status": "annahme",
        },
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)

    queue = build_data_connector_queue(backlog)

    assert len(queue) == 1
    assert queue[0]["source_id"] == "destatis_genesis"
    assert queue[0]["source_label"] == "Destatis/GENESIS"
    assert queue[0]["open_parameter_count"] == 2
    assert queue[0]["example_parameters"] == ["Bevölkerung", "Fertilität"]
    assert "SHA256-Manifest" in queue[0]["connector_next_action"]
    assert "keine automatische Registry- oder Modellmutation" in queue[0]["guardrail"]
    assert "Telemedizin-Nutzung" not in queue[0]["example_parameters"]


def test_connector_snapshot_requests_expose_first_safe_destatis_cache_contract(tmp_path):
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
        {
            "key": "unknown_destatis_parameter",
            "label": "Noch nicht gemappt",
            "unit": "",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)

    requests = build_connector_snapshot_requests(backlog)

    assert len(requests) == 1
    request = requests[0]
    assert request["source_id"] == "destatis_genesis"
    assert request["parameter_label"] == "Bevölkerung"
    assert request["table_code"] == "12411-0001"
    assert "genesisWS/rest/2020/data/tablefile" in request["endpoint_url"]
    assert "format=csv" in request["endpoint_url"]
    assert request["output_parameter_keys"] == ["bevoelkerung_mio"]
    assert "cache_source_payload" in request["next_safe_action"]
    assert "No automatic registry or model mutation" in request["transformation_note"]
    assert "not a model import" in request["guardrail"]


def test_execute_connector_snapshot_request_caches_raw_payload_without_model_import(tmp_path):
    request = build_connector_snapshot_requests(
        build_data_readiness_backlog(
            [
                {
                    "key": "bevoelkerung_mio",
                    "label": "Bevölkerung",
                    "unit": "million people",
                    "evidence_grade": "A",
                    "source_ids": ["destatis_genesis"],
                    "data_status": "aus_daten",
                }
            ],
            cache_root=tmp_path,
        )
    )[0]
    seen_urls = []

    def fake_fetcher(url):
        seen_urls.append(url)
        return b"GENESIS raw csv bytes;year;value\n2025;84.5\n"

    result = execute_connector_snapshot_request(
        request,
        cache_root=tmp_path,
        payload_fetcher=fake_fetcher,
        retrieved_at="2026-04-29T22:10:00+00:00",
    )

    assert seen_urls == [request["endpoint_url"]]
    assert result["status"] == "raw_snapshot_cached_not_model_integration"
    assert "not a model import" in result["guardrail"]
    assert "ReviewedTransformation" in result["next_safe_action"]

    snapshot = result["snapshot"]
    assert snapshot["source_id"] == "destatis_genesis"
    assert snapshot["output_parameter_keys"] == ["bevoelkerung_mio"]
    assert snapshot["raw_path"].endswith("destatis_genesis_12411_0001_population.csv")
    assert snapshot["sha256"] == snapshot_payload_hash(b"GENESIS raw csv bytes;year;value\n2025;84.5\n")
    assert "No automatic registry or model mutation" in snapshot["transformation_note"]

    rows = build_data_passport_rows(
        [
            {
                "key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "unit": "million people",
                "evidence_grade": "A",
                "source_ids": ["destatis_genesis"],
                "data_status": "aus_daten",
            }
        ],
        cache_root=tmp_path,
    )
    assert rows[0]["cache"]["has_cached_snapshot"] is True
    assert rows[0]["transformation_review"]["status"] == "not_reviewed"
    assert "geprüfte Transformation separat" in rows[0]["passport_note"]


def test_platform_brief_turns_next_actions_into_verified_read_only_work(tmp_path):
    parameters = [
        {
            "key": "krankenhausbetten",
            "label": "Krankenhausbetten",
            "unit": "beds",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        }
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    actions = build_next_data_readiness_actions(backlog, limit=1)

    brief = build_data_readiness_platform_brief(actions)

    assert brief["title"].startswith("Plattform-Brief")
    assert "kein execute=true" in brief["guardrail"]
    assert "Status/Dry-run" in brief["sequence"][0]
    row = brief["rows"][0]
    assert row["parameter_key"] == "krankenhausbetten"
    assert "POST /data-connectors/execute-planned-snapshot" in row["verification"]
    assert "GET /data-readiness/krankenhausbetten" in row["verification"]
    assert "GET /data-connectors/transformation-review-template/krankenhausbetten" in row["verification"]
    assert "Registry-/Modelländerung" in row["definition_of_done"]
    assert "kein execute=true" in row["guardrail"]


def test_data_readiness_dashboard_cards_summarize_status_without_execution(tmp_path):
    parameters = [
        {
            "key": "krankenhausbetten",
            "label": "Krankenhausbetten",
            "unit": "beds",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        }
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    summary = build_data_readiness_summary(backlog)
    actions = build_next_data_readiness_actions(backlog, limit=1)

    cockpit = build_data_readiness_dashboard_cards(summary, actions)

    assert cockpit["title"].startswith("Daten-Reife Cockpit")
    assert len(cockpit["cards"]) == 4
    assert cockpit["cards"][0]["id"] == "overall_progress"
    assert cockpit["cards"][0]["value"] == "1"
    snapshot_card = next(card for card in cockpit["cards"] if card["id"] == "snapshot_needed")
    assert snapshot_card["value"] == "1"
    assert snapshot_card["next_click"] == "GET /data-readiness/next-actions"
    assert "kein Netzwerkabruf" in snapshot_card["guardrail"]
    assert cockpit["first_safe_action"]["parameter_key"] == "krankenhausbetten"
    assert cockpit["first_safe_action"]["primary_api"] == "POST /data-connectors/execute-planned-snapshot"
    assert "kein execute=true" in cockpit["guardrail"]
    assert "keine Modellintegration" in cockpit["guardrail"]


def test_first_contact_guide_explains_data_readiness_before_backlog_tables(tmp_path):
    parameters = [
        {
            "key": "krankenhausbetten",
            "label": "Krankenhausbetten",
            "unit": "beds",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        }
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    summary = build_data_readiness_summary(backlog)
    actions = build_next_data_readiness_actions(backlog, limit=1)

    guide = build_data_readiness_first_contact_guide(summary, actions)

    assert guide["title"].startswith("So liest du")
    assert len(guide["steps"]) == 3
    assert guide["steps"][0]["question"] == "Welche Datenarbeit ist insgesamt noch offen?"
    assert "1 Parameter" in guide["steps"][0]["answer"]
    assert guide["steps"][1]["open"] == "GET /data-readiness/krankenhausbetten"
    assert "Snapshot fehlt: 1" in guide["steps"][2]["answer"]
    assert "Registry-Quelle, Rohdaten-Cache, Transformationsreview und Modellintegration" in guide["steps"][2]["guardrail"]
    assert "kein execute=true" in guide["guardrail"]
    assert "keine Registry-/Modellmutation" in guide["guardrail"]


def test_connector_execution_workbench_turns_requests_into_next_safe_actions(tmp_path):
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        }
    ]
    backlog = build_data_readiness_backlog(parameters, cache_root=tmp_path)
    requests = build_connector_snapshot_requests(backlog)
    passport = build_data_passport_rows(parameters, cache_root=tmp_path)

    workbench = build_connector_execution_workbench(requests, passport)

    assert workbench["summary"]["planned_request_count"] == 1
    assert "Modellintegration bleibt" in workbench["summary"]["guardrail"]
    row = workbench["rows"][0]
    assert row["parameter_key"] == "bevoelkerung_mio"
    assert row["table_code"] == "12411-0001"
    assert row["next_safe_gate"]["gate"] == "raw_snapshot_cache"
    assert "kein Netzwerkabruf" in row["guardrail"]
    assert [step["gate"] for step in row["execution_plan"]] == [
        "dry_run",
        "raw_snapshot_cache",
        "transformation_review",
        "explicit_model_integration",
    ]
    template = row["transformation_review_template"]
    assert template["parameter_key"] == "bevoelkerung_mio"
    assert "source_snapshot_sha256" in template["required_review_fields"]
    assert any("Nenner" in item for item in template["checklist"])
    assert "keine offizielle Prognose" in template["guardrail"]


def test_parameter_data_workflow_card_combines_passport_backlog_and_review_next_step(tmp_path):
    parameters = [
        {
            "key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "unit": "million people",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
            "source_version": "Destatis referenced baseline; automated snapshot pending",
            "data_lineage": "Registry baseline; reviewed import pending.",
        },
    ]
    cache_source_payload(
        source_id="destatis_genesis",
        source_url="https://www-genesis.destatis.de/genesis/online",
        payload=b"year,value\n2025,84.5\n",
        filename="population.csv",
        cache_root=tmp_path,
        source_period="2025",
        output_parameter_keys=("bevoelkerung_mio",),
        transformation_note="raw fixture only; no model mutation",
        retrieved_at="2026-04-29T20:00:00+00:00",
    )

    card = build_parameter_data_workflow_card("bevoelkerung_mio", parameters, cache_root=tmp_path)

    assert card["status"] == "parameter_data_workflow_not_model_integration"
    assert card["parameter_key"] == "bevoelkerung_mio"
    assert card["passport"]["registry_label"] == "aus Daten"
    assert card["backlog_item"]["next_gate"] == "transformation_review_needed"
    assert card["next_safe_gate"]["gate"] == "transformation_review"
    assert card["planned_connector_request"] is None
    assert card["transformation_review_template"]["parameter_key"] == "bevoelkerung_mio"
    assert "Rohdatei" in card["transformation_review_template"]["checklist"][0]
    assert "keine Registry- oder Modellmutation" in card["guardrail"]


def test_parameter_data_workflow_card_exposes_connector_plan_for_snapshot_needed_parameter(tmp_path):
    parameters = [
        {
            "key": "krankenhausbetten",
            "label": "Krankenhausbetten",
            "unit": "beds",
            "evidence_grade": "A",
            "source_ids": ["destatis_genesis"],
            "data_status": "aus_daten",
        },
    ]

    card = build_parameter_data_workflow_card("krankenhausbetten", parameters, cache_root=tmp_path)

    assert card["backlog_item"]["next_gate"] == "snapshot_needed"
    assert card["planned_connector_request"]["table_code"] == "23111-0001"
    assert card["next_safe_gate"]["gate"] == "raw_snapshot_cache"
    assert card["connector_execution_workbench"]["parameter_key"] == "krankenhausbetten"
    assert card["transformation_review_template"]["required_review_fields"]
    assert "kein Netzwerkabruf" in card["guardrail"]


def test_transformation_review_template_is_pre_model_integration_guidance(tmp_path):
    request = build_connector_snapshot_requests(
        build_data_readiness_backlog(
            [
                {
                    "key": "krankenhausbetten",
                    "label": "Krankenhausbetten",
                    "unit": "beds",
                    "evidence_grade": "A",
                    "source_ids": ["destatis_genesis"],
                    "data_status": "aus_daten",
                }
            ],
            cache_root=tmp_path,
        )
    )[0]
    passport = build_data_passport_rows(
        [
            {
                "key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "unit": "beds",
                "evidence_grade": "A",
                "source_ids": ["destatis_genesis"],
                "data_status": "aus_daten",
            }
        ],
        cache_root=tmp_path,
    )[0]

    template = build_transformation_review_template(request, passport)

    assert template["table_code"] == "23111-0001"
    assert template["suggested_status_flow"] == ["not_reviewed", "reviewed_no_model_import", "reviewed_model_ready"]
    assert "Rohsnapshot" in template["raw_snapshot_status"]
    assert "ReviewedTransformation" in template["next_safe_action"]
    assert "keinen Datenwert im Modell" in template["guardrail"]


def test_data_readiness_integration_preflight_blocks_until_review_and_separate_pr():
    backlog_items = [
        {
            "parameter_key": "bevoelkerung_mio",
            "label": "Bevölkerung",
            "next_gate": "explicit_model_integration_needed",
            "next_action": "separate integration",
            "guardrail": "no mutation",
        },
        {
            "parameter_key": "krankenhausbetten",
            "label": "Krankenhausbetten",
            "next_gate": "transformation_review_needed",
            "next_action": "review",
            "guardrail": "no mutation",
        },
        {
            "parameter_key": "krankenhaeuser",
            "label": "Krankenhäuser",
            "next_gate": "snapshot_needed",
            "next_action": "snapshot",
            "guardrail": "no mutation",
        },
    ]
    passport_rows = [
        {
            "parameter_key": "bevoelkerung_mio",
            "cache": {"label": "Rohsnapshot im Cache vorhanden"},
            "transformation_review": {"label": "reviewed_model_ready"},
        },
        {
            "parameter_key": "krankenhausbetten",
            "cache": {"label": "Rohsnapshot im Cache vorhanden"},
            "transformation_review": {"label": "Transformation nicht geprüft"},
        },
        {
            "parameter_key": "krankenhaeuser",
            "cache": {"label": "Rohsnapshot noch nicht im Cache"},
            "transformation_review": {"label": "Transformation nicht geprüft"},
        },
    ]

    preflight = build_data_readiness_integration_preflight(backlog_items, passport_rows, limit=3)

    assert preflight["summary"] == {
        "ready_for_integration_plan": 1,
        "blocked_before_integration": 2,
        "shown_rows": 3,
    }
    ready = preflight["rows"][0]
    assert ready["parameter_key"] == "bevoelkerung_mio"
    assert ready["preflight_status"] == "bereit_fuer_separaten_integrationsplan"
    assert "separaten Registry-/Modell-PR" in ready["first_blocker"]
    assert "Tests und Smoke-Test" in " ".join(ready["definition_of_done"])
    blocked = {row["parameter_key"]: row["preflight_status"] for row in preflight["rows"][1:]}
    assert blocked == {
        "krankenhausbetten": "blockiert_bis_transformation_review",
        "krankenhaeuser": "blockiert_bis_rohsnapshot",
    }
    assert "keine Registry-/Modellmutation" in preflight["guardrail"]


def test_integration_plan_only_includes_preflight_ready_rows():
    preflight = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "preflight_status": "bereit_fuer_separaten_integrationsplan",
                "definition_of_done": ["Registry-/Modelländerung als eigener PR"],
                "workflow_api": "GET /data-readiness/bevoelkerung_mio",
                "review_template_api": "GET /data-connectors/transformation-review-template/bevoelkerung_mio",
            },
            {
                "parameter_key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "preflight_status": "blockiert_bis_transformation_review",
            },
        ]
    }

    plan = build_data_readiness_integration_plan(preflight)

    assert plan["summary"] == {"ready_rows_in_preflight": 1, "shown_plans": 1, "blocked_rows_seen": 1}
    item = plan["plans"][0]
    assert item["parameter_key"] == "bevoelkerung_mio"
    assert item["status"] == "planbar_aber_nicht_ausgefuehrt"
    assert "parameter_registry.py" in item["proposed_files"]
    assert "tests/test_data_ingestion.py tests/test_api.py" in item["test_plan"][1]
    assert "Data Passport" in " ".join(item["definition_of_done"])
    assert "keine Registry-/Modellmutation" in item["guardrail"]
    assert "krankenhausbetten" not in str(plan["plans"])


def test_integration_pr_brief_turns_green_plans_into_safe_handoff():
    integration_plan = {
        "plans": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "workflow_api": "GET /data-readiness/bevoelkerung_mio",
                "review_template_api": "GET /data-connectors/transformation-review-template/bevoelkerung_mio",
                "definition_of_done": ["Data Passport trennt Cache, Review und Modelleffekt"],
            }
        ]
    }

    brief = build_data_readiness_integration_pr_brief(integration_plan)

    assert brief["summary"] == {"plan_rows_seen": 1, "shown_pr_briefs": 1}
    item = brief["briefs"][0]
    assert item["status"] == "pr_brief_bereit_aber_nicht_ausgefuehrt"
    assert item["branch_name"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert "ReviewedTransformation" in " ".join(item["review_checklist"])
    assert "GET /data-readiness/bevoelkerung_mio" in " ".join(item["copyable_pr_body_outline"])
    assert "kein Branch" in item["guardrail"]
    assert "keine Registry-/Modellmutation" in brief["guardrail"]


def test_registry_integration_decision_record_requires_human_go_hold_reject():
    preview = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "reviewed_output_value": 84.5,
                "source_snapshot_sha256": "abc123",
                "unit_check": {"unit_matches": True},
                "plausibility_check": {"within_registry_bounds": True},
                "required_human_decision": "separater PR erforderlich",
            },
            {
                "parameter_key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "reviewed_output_value": None,
                "source_snapshot_sha256": None,
                "unit_check": {"unit_matches": False},
                "plausibility_check": {"within_registry_bounds": None},
            },
        ]
    }
    pr_brief = {
        "briefs": [
            {
                "parameter_key": "bevoelkerung_mio",
                "branch_name": "feat/integrate-reviewed-bevoelkerung_mio",
            }
        ]
    }

    decision = build_data_readiness_registry_integration_decision_record(preview, pr_brief)

    assert decision["title"].startswith("Registry-Integrationsentscheidung")
    assert decision["summary"] == {"diff_rows_seen": 2, "decision_rows": 2, "ready_for_human_go_no_go": 1}
    ready = decision["rows"][0]
    assert ready["status"] == "human_go_no_go_required_before_pr"
    assert ready["checks"] == {
        "reviewed_value_present": True,
        "source_snapshot_sha256_present": True,
        "unit_matches_registry": True,
        "within_registry_bounds": True,
        "pr_brief_available": True,
    }
    assert ready["branch_name_if_go"] == "feat/integrate-reviewed-bevoelkerung_mio"
    assert "Go:" in ready["safe_options"][0]
    assert "Hold" in ready["recommended_default"]
    blocked = decision["rows"][1]
    assert blocked["status"] == "blocked_before_human_go_no_go"
    assert blocked["checks"]["pr_brief_available"] is False
    assert "keine Registry-/Modellmutation" in decision["guardrail"]


def test_registry_integration_decision_template_is_auditable_and_read_only():
    decision_record = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "status": "human_go_no_go_required_before_pr",
                "checks": {
                    "reviewed_value_present": True,
                    "source_snapshot_sha256_present": True,
                    "unit_matches_registry": True,
                    "within_registry_bounds": True,
                    "pr_brief_available": True,
                },
                "branch_name_if_go": "feat/integrate-reviewed-bevoelkerung_mio",
                "recommended_default": "Hold, falls irgendein Check fehlt; Go nur vollständig.",
                "safe_options": ["Go", "Hold", "Reject"],
            }
        ]
    }

    template = build_data_readiness_registry_integration_decision_template(decision_record)

    assert template["title"].startswith("Ausfüllvorlage")
    assert template["summary"] == {"decision_rows_seen": 1, "template_rows": 1, "go_eligible_rows": 1}
    row = template["rows"][0]
    assert row["parameter_key"] == "bevoelkerung_mio"
    assert row["allowed_decisions"] == ["Go", "Hold", "Reject"]
    assert row["recommended_default"].startswith("Hold")
    assert row["decision_fields_to_fill"] == [
        "decision: Go | Hold | Reject",
        "decision_rationale: konkrete Begründung mit Quelle/Methode/Unsicherheit",
        "decided_by: Name/Rolle der verantwortlichen Person",
        "decided_at: ISO-Datum/Zeit",
        "follow_up: nächster sicherer Schritt",
    ]
    assert "GET /data-readiness/bevoelkerung_mio" in row["evidence_routes_to_open"]
    assert "kein Branch" in template["guardrail"]
    assert "keine Registry-/Modellmutation" in row["guardrail"]


def test_registry_integration_handoff_packet_is_copy_safe_and_read_only():
    decision_record = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "status": "human_go_no_go_required_before_pr",
                "checks": {
                    "reviewed_value_present": True,
                    "source_snapshot_sha256_present": True,
                    "unit_matches_registry": True,
                    "within_registry_bounds": True,
                    "pr_brief_available": True,
                },
                "branch_name_if_go": "feat/integrate-reviewed-bevoelkerung_mio",
                "recommended_default": "Hold, falls irgendein Check fehlt; Go nur vollständig.",
                "safe_options": ["Go", "Hold", "Reject"],
            },
            {
                "parameter_key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "status": "blocked_before_human_go_no_go",
                "checks": {
                    "reviewed_value_present": False,
                    "source_snapshot_sha256_present": False,
                    "unit_matches_registry": False,
                    "within_registry_bounds": None,
                    "pr_brief_available": False,
                },
            },
        ]
    }

    packet = build_data_readiness_registry_integration_handoff_packet(decision_record)

    assert packet["title"].startswith("Registry-Integrations-Handoff")
    assert packet["summary"] == {"decision_rows_seen": 2, "handoff_rows": 2, "blocked_or_hold_default": 1}
    ready = packet["rows"][0]
    assert ready["copyable_status_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert ready["missing_checks_before_go"] == []
    assert "Go/Hold/Reject" in ready["definition_of_done_before_branch"][0]
    blocked = packet["rows"][1]
    assert "Review-Wert fehlt" in blocked["missing_checks_before_go"]
    assert "PR-Brief fehlt" in blocked["missing_checks_before_go"]
    assert "kein Branch" in packet["guardrail"]
    assert "keine Registry-/Modellmutation" in ready["guardrail"]


def test_registry_integration_status_board_compacts_final_gates_without_actions():
    decision_record = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "status": "human_go_no_go_required_before_pr",
                "checks": {
                    "reviewed_value_present": True,
                    "source_snapshot_sha256_present": True,
                    "unit_matches_registry": True,
                    "within_registry_bounds": True,
                    "pr_brief_available": True,
                },
                "branch_name_if_go": "feat/integrate-reviewed-bevoelkerung_mio",
            },
            {
                "parameter_key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "status": "blocked_before_human_go_no_go",
                "checks": {
                    "reviewed_value_present": False,
                    "source_snapshot_sha256_present": False,
                    "unit_matches_registry": False,
                    "within_registry_bounds": None,
                    "pr_brief_available": False,
                },
            },
        ]
    }
    audit = build_data_readiness_registry_integration_decision_audit_checklist(decision_record)
    runbook = build_data_readiness_registry_integration_pr_runbook(decision_record)

    board = build_data_readiness_registry_integration_status_board(decision_record, audit, runbook)

    assert board["title"].startswith("Registry-Integrations-Statusboard")
    assert board["summary"] == {"decision_rows_seen": 2, "board_rows": 2, "rows_waiting_or_hold": 1}
    ready = board["rows"][0]
    assert ready["board_status"] == "bereit_fuer_menschliches_go_audit"
    assert ready["green_check_count"] == 5
    assert ready["status_route"] == "GET /data-readiness/bevoelkerung_mio"
    assert ready["runbook_route"] == "GET /data-readiness/registry-integration-pr-runbook"
    blocked = board["rows"][1]
    assert blocked["board_status"] == "hold_bis_technical_checks_gruen"
    assert "reviewed_value_present" in blocked["missing_checks_before_go"]

    cards = build_data_readiness_registry_integration_status_cards(board)
    assert cards["title"].startswith("Registry-Integrationskarten")
    assert [card["id"] for card in cards["cards"]] == [
        "overall_registry_gate",
        "waiting_or_hold",
        "ready_for_human_audit",
        "first_safe_route",
    ]
    assert cards["cards"][0]["value"] == "2"
    assert cards["cards"][1]["value"] == "1"
    assert "Fehlende technische Checks" in cards["cards"][1]["answer"]
    assert cards["cards"][2]["value"] == "1"
    assert cards["cards"][3]["next_click"] == "GET /data-readiness/bevoelkerung_mio"
    assert "kein execute=true" in cards["guardrail"]
    assert "keine Registry-/Modellmutation" in cards["cards"][0]["guardrail"]
    assert "kein Branch" in board["guardrail"]
    assert "keine Registry-/Modellmutation" in ready["guardrail"]


def test_registry_integration_progress_timeline_shows_safe_sequence_without_actions():
    decision_record = {
        "rows": [
            {
                "parameter_key": "bevoelkerung_mio",
                "label": "Bevölkerung",
                "status": "human_go_no_go_required_before_pr",
                "checks": {
                    "reviewed_value_present": True,
                    "source_snapshot_sha256_present": True,
                    "unit_matches_registry": True,
                    "within_registry_bounds": True,
                    "pr_brief_available": True,
                },
                "branch_name_if_go": "feat/integrate-reviewed-bevoelkerung_mio",
            },
            {
                "parameter_key": "krankenhausbetten",
                "label": "Krankenhausbetten",
                "status": "blocked_before_human_go_no_go",
                "checks": {
                    "reviewed_value_present": False,
                    "source_snapshot_sha256_present": False,
                    "unit_matches_registry": False,
                    "within_registry_bounds": None,
                    "pr_brief_available": False,
                },
            },
        ]
    }
    audit = build_data_readiness_registry_integration_decision_audit_checklist(decision_record)
    runbook = build_data_readiness_registry_integration_pr_runbook(decision_record)
    board = build_data_readiness_registry_integration_status_board(decision_record, audit, runbook)
    status_cards = build_data_readiness_registry_integration_status_cards(board)
    operator_steps = build_data_readiness_registry_integration_operator_steps(board, status_cards)
    packet = build_data_readiness_registry_integration_safe_start_packet(operator_steps, board)
    checklist = build_data_readiness_registry_integration_safe_start_checklist(packet)
    safe_cards = build_data_readiness_registry_integration_safe_start_cards(checklist)

    timeline = build_data_readiness_registry_integration_progress_timeline(safe_cards, board)

    assert timeline["title"].startswith("Registry-Integrationsfortschritt")
    assert timeline["summary"]["ready_for_human_audit"] == 1
    assert timeline["summary"]["waiting_or_hold"] == 1
    assert [phase["phase"] for phase in timeline["phases"]] == [
        "Orientieren",
        "Parameter einzeln prüfen",
        "Menschliche Entscheidung vorbereiten",
        "Vor Codearbeit stoppen",
    ]
    assert timeline["phases"][1]["what_to_open"].startswith("GET /data-readiness/")
    assert timeline["phases"][2]["status"] == "human_audit_possible"
    assert "kein execute=true" in timeline["phases"][0]["guardrail"]
    assert "keine Registry-/Modellmutation" in timeline["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in timeline["phases"][3]["guardrail"]

    palette = build_data_readiness_registry_integration_command_palette(timeline)

    assert palette["title"].startswith("Registry-Integration: Copy-Palette")
    assert palette["primary_parameter_key"] == timeline["primary_parameter_key"]
    assert [command["mode"] for command in palette["commands"]] == [
        "read_only_status",
        "read_only_status",
        "read_only_status",
        "stop_no_command",
    ]
    assert palette["commands"][1]["copyable_command"] == timeline["phases"][1]["what_to_open"]
    assert palette["commands"][3]["copyable_command"].startswith("STOP:")
    assert not any("execute=true" in command["copyable_command"] for command in palette["commands"])
    assert "kein Branch" in palette["guardrail"]
    assert "keine Registry-/Modellmutation" in palette["guardrail"]
    assert "kein Policy-Wirkungsbeweis" in palette["guardrail"]


def test_registry_operator_briefing_cards_make_safe_route_touch_friendly():
    operator_briefing = {
        "primary_parameter_key": "bevoelkerung_mio",
        "primary_label": "Bevölkerung",
        "first_safe_command": "GET /data-readiness/registry-integration-status-board",
        "next_parameter_command": "GET /data-readiness/bevoelkerung_mio",
        "human_decision_command": "GET /data-readiness/registry-integration-decision-audit-checklist",
        "stop_before_code": "STOP: erst menschliches Go außerhalb dieses Pakets dokumentieren",
        "definition_of_done_before_branch": ["Go/Hold/Reject dokumentiert"],
    }

    cards = build_data_readiness_registry_integration_operator_briefing_cards(operator_briefing)

    assert cards["title"].startswith("Operator-Briefing als mobile")
    assert cards["primary_parameter_key"] == "bevoelkerung_mio"
    assert [card["id"] for card in cards["cards"]] == [
        "start_status",
        "parameter_workflow",
        "human_decision",
        "stop_before_code",
    ]
    assert cards["cards"][1]["copyable_command"] == "GET /data-readiness/bevoelkerung_mio"
    assert cards["cards"][-1]["is_stop_gate"] is True
    assert "kein Branch" in cards["guardrail"]
    assert "kein execute=true" in cards["guardrail"]
    assert "keine Registry-/Modellmutation" in cards["guardrail"]
