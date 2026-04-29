from pathlib import Path

from provenance import append_ingest_log, make_ingest_record, sha256_file


def test_make_ingest_record_hashes_raw_file(tmp_path):
    raw = tmp_path / "sample.csv"
    raw.write_text("a,b\n1,2\n", encoding="utf-8")
    record = make_ingest_record(
        source_id="destatis_genesis",
        url_or_path="https://example.test/table",
        raw_path=raw,
        source_period="2025",
        output_keys=["bevoelkerung_mio"],
    )
    assert record.source_id == "destatis_genesis"
    assert record.content_hash_sha256 == sha256_file(raw)
    assert record.retrieved_at


def test_append_ingest_log_writes_jsonl(tmp_path):
    record = make_ingest_record(
        source_id="baek",
        url_or_path="https://example.test/baek",
        output_keys=["aerzte_gesamt"],
    )
    log = append_ingest_log(record, tmp_path / "ingest_log.jsonl")
    content = Path(log).read_text(encoding="utf-8")
    assert "baek" in content
    assert "aerzte_gesamt" in content
