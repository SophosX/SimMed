import json

from data_ingestion import cache_source_payload, read_snapshot_manifest, snapshot_payload_hash


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
