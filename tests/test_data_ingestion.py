import json

from data_ingestion import (
    build_data_passport_rows,
    build_parameter_snapshot_status,
    cache_source_payload,
    list_cached_snapshots,
    read_snapshot_manifest,
    seed_reference_fixture_snapshots,
    snapshot_payload_hash,
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
