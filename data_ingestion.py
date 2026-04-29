"""Small data-ingestion/cache primitives for SimMed source-backed parameters.

This module is intentionally connector-light: it gives future Destatis/Eurostat/etc.
imports a stable cache manifest shape before any importer is allowed to mutate model
parameters. Cached snapshots are provenance objects, not trusted model facts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

DataStatus = Literal["aus_daten", "annahme"]
CACHE_ROOT = Path("data/cache")


@dataclass(frozen=True)
class CachedSourceSnapshot:
    """Metadata for one raw source snapshot saved in the local cache."""

    source_id: str
    source_url: str
    retrieved_at: str
    raw_path: str
    sha256: str
    source_period: str = ""
    license_or_terms_note: str = ""
    output_parameter_keys: tuple[str, ...] = ()
    transformation_note: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["output_parameter_keys"] = list(self.output_parameter_keys)
        return data


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def snapshot_payload_hash(payload: bytes) -> str:
    """Return the SHA256 hash used for raw cached source files."""

    return sha256(payload).hexdigest()


def cache_source_payload(
    *,
    source_id: str,
    source_url: str,
    payload: bytes,
    filename: str,
    cache_root: Path | str = CACHE_ROOT,
    source_period: str = "",
    license_or_terms_note: str = "",
    output_parameter_keys: tuple[str, ...] = (),
    transformation_note: str = "",
    retrieved_at: str | None = None,
) -> CachedSourceSnapshot:
    """Write raw payload plus a manifest and return the snapshot metadata.

    The function only records provenance. A later reviewed transformation step must
    decide whether any parameter can move from `annahme` to `aus_daten`.
    """

    root = Path(cache_root)
    raw_dir = root / source_id / "raw"
    manifest_dir = root / source_id / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    digest = snapshot_payload_hash(payload)
    safe_name = Path(filename).name
    raw_path = raw_dir / safe_name
    raw_path.write_bytes(payload)

    snapshot = CachedSourceSnapshot(
        source_id=source_id,
        source_url=source_url,
        retrieved_at=retrieved_at or _utc_now_iso(),
        raw_path=str(raw_path),
        sha256=digest,
        source_period=source_period,
        license_or_terms_note=license_or_terms_note,
        output_parameter_keys=output_parameter_keys,
        transformation_note=transformation_note,
    )
    manifest_path = manifest_dir / f"{raw_path.stem}.manifest.json"
    manifest_path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def read_snapshot_manifest(path: Path | str) -> CachedSourceSnapshot:
    """Load a cached source manifest back into the typed metadata object."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["output_parameter_keys"] = tuple(data.get("output_parameter_keys", ()))
    return CachedSourceSnapshot(**data)
