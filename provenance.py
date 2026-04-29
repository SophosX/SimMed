"""Utilities for recording external data ingests.

This is intentionally lightweight for now.  The future production version should
write to SQLite/Postgres and keep immutable raw files.  The current helper gives
agents and scripts a standard JSONL format so every source pull is traceable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

from data_sources import DATA_SOURCES


@dataclass(frozen=True)
class IngestRecord:
    source_id: str
    url_or_path: str
    retrieved_at: str
    source_period: str | None
    raw_path: str | None
    content_hash_sha256: str | None
    output_keys: list[str]
    notes: str = ""
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_ingest_record(
    *,
    source_id: str,
    url_or_path: str,
    raw_path: str | Path | None = None,
    source_period: str | None = None,
    output_keys: list[str] | None = None,
    notes: str = "",
    warnings: list[str] | None = None,
) -> IngestRecord:
    if source_id not in DATA_SOURCES:
        raise KeyError(f"Unknown source_id: {source_id}")
    raw_str = str(raw_path) if raw_path is not None else None
    digest = sha256_file(raw_path) if raw_path is not None and Path(raw_path).exists() else None
    return IngestRecord(
        source_id=source_id,
        url_or_path=url_or_path,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_period=source_period,
        raw_path=raw_str,
        content_hash_sha256=digest,
        output_keys=output_keys or [],
        notes=notes,
        warnings=warnings,
    )


def append_ingest_log(record: IngestRecord, log_path: str | Path = "data/ingest_log.jsonl") -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return path
