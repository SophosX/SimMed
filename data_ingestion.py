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
TransformationStatus = Literal["not_reviewed", "reviewed_no_model_import", "reviewed_model_ready"]
CACHE_ROOT = Path("data/cache")
FIXTURE_ROOT = Path("data/fixtures")


@dataclass(frozen=True)
class ReviewedTransformation:
    """Review metadata for a raw snapshot-to-parameter transformation.

    This is the missing middle layer between a raw cache artifact and a model
    parameter. A record can document that a transformation was reviewed without
    silently mutating simulation defaults.
    """

    parameter_key: str
    source_snapshot_sha256: str
    status: TransformationStatus
    reviewed_at: str
    reviewer: str
    method_note: str
    caveat: str
    output_value: float | int | str | None = None
    output_unit: str = ""

    def to_dict(self) -> dict:
        return asdict(self)



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


def record_reviewed_transformation(
    transformation: ReviewedTransformation,
    *,
    cache_root: Path | str = CACHE_ROOT,
) -> Path:
    """Persist a reviewed transformation record without changing model defaults."""

    if not transformation.parameter_key:
        raise ValueError("parameter_key is required")
    if not transformation.source_snapshot_sha256:
        raise ValueError("source_snapshot_sha256 is required")
    if not transformation.reviewer or not transformation.method_note or not transformation.caveat:
        raise ValueError("reviewer, method_note and caveat are required for transformation review")

    review_dir = Path(cache_root) / "transformations" / transformation.parameter_key
    review_dir.mkdir(parents=True, exist_ok=True)
    safe_digest = transformation.source_snapshot_sha256[:16]
    review_path = review_dir / f"{safe_digest}.review.json"
    review_path.write_text(json.dumps(transformation.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return review_path


def read_transformation_review(path: Path | str) -> ReviewedTransformation:
    """Load a reviewed transformation record."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReviewedTransformation(**data)


def list_reviewed_transformations(cache_root: Path | str = CACHE_ROOT) -> list[ReviewedTransformation]:
    """Return reviewed transformation records newest-first.

    These records document review status only. Even `reviewed_model_ready` remains
    a staging signal until an explicit registry/model change is made in code.
    """

    root = Path(cache_root) / "transformations"
    if not root.exists():
        return []
    reviews = [read_transformation_review(path) for path in root.glob("*/*.review.json")]
    return sorted(reviews, key=lambda item: item.reviewed_at, reverse=True)


def seed_reference_fixture_snapshots(
    *,
    cache_root: Path | str = CACHE_ROOT,
    fixture_root: Path | str = FIXTURE_ROOT,
) -> list[CachedSourceSnapshot]:
    """Seed reviewed raw-cache *fixtures* that exercise the data passport plumbing.

    Fixtures are deliberately not model imports. They make the provenance/cache
    path visible in API/UI development while keeping the current parameter value
    separate from any automated GENESIS transformation or policy claim.
    """

    fixture_dir = Path(fixture_root)
    population_fixture = fixture_dir / "destatis_genesis_population_baseline_fixture.csv"
    if not population_fixture.exists():
        return []

    return [
        cache_source_payload(
            source_id="destatis_genesis",
            source_url="https://www-genesis.destatis.de/genesis/online",
            payload=population_fixture.read_bytes(),
            filename=population_fixture.name,
            cache_root=cache_root,
            source_period="registry-baseline fixture",
            license_or_terms_note="Static SimMed fixture for cache/provenance plumbing; replace with a live reviewed GENESIS snapshot before model integration.",
            output_parameter_keys=("bevoelkerung_mio",),
            transformation_note="Fixture mirrors the registry default only; no checked transformation and no mutation of simulation parameters.",
            retrieved_at="2026-04-29T21:00:00+00:00",
        )
    ]


def list_cached_snapshots(cache_root: Path | str = CACHE_ROOT) -> list[CachedSourceSnapshot]:
    """Return all cache manifests sorted newest-first by retrieval timestamp.

    This is a read-only status helper for API/UI data passports. It deliberately
    does not infer that a parameter default is trustworthy just because a raw
    snapshot exists; reviewed transformations remain a separate step.
    """

    root = Path(cache_root)
    if not root.exists():
        return []
    snapshots: list[CachedSourceSnapshot] = []
    for manifest_path in root.glob("*/manifests/*.manifest.json"):
        snapshots.append(read_snapshot_manifest(manifest_path))
    return sorted(snapshots, key=lambda item: item.retrieved_at, reverse=True)


def build_parameter_snapshot_status(
    parameter_keys: list[str] | tuple[str, ...],
    *,
    cache_root: Path | str = CACHE_ROOT,
) -> list[dict]:
    """Summarize whether each parameter has a cached raw-source snapshot.

    The output is intentionally conservative: `has_cached_snapshot` means only
    that raw source material is present in the local cache. It is not evidence
    that the value has been reviewed, transformed, or integrated into the model.
    """

    snapshots = list_cached_snapshots(cache_root)
    rows: list[dict] = []
    for key in parameter_keys:
        matching = [s for s in snapshots if key in s.output_parameter_keys]
        latest = matching[0] if matching else None
        rows.append(_snapshot_status_row(key, matching, latest))
    return rows


def _snapshot_status_row(
    parameter_key: str,
    matching_snapshots: list[CachedSourceSnapshot],
    latest: CachedSourceSnapshot | None,
) -> dict:
    return {
        "parameter_key": parameter_key,
        "has_cached_snapshot": latest is not None,
        "snapshot_count": len(matching_snapshots),
        "latest_snapshot": latest.to_dict() if latest else None,
        "status_note": (
            "Rohdaten-Snapshot vorhanden; Modellwert bleibt bis zur geprüften Transformation getrennt."
            if latest
            else "Noch kein Rohdaten-Snapshot im lokalen Cache verknüpft."
        ),
    }


def build_data_passport_rows(
    parameters: list[dict],
    *,
    cache_root: Path | str = CACHE_ROOT,
) -> list[dict]:
    """Combine registry provenance with raw-cache and transformation-review status for UI/API data passports.

    A passport row answers three separate questions that users often conflate:
    1. Is the current model default source-referenced or still an assumption?
    2. Is there already a raw cached snapshot connected to that parameter?
    3. Has a human/agent review documented a transformation from raw source to model-ready value?

    It never marks a parameter as imported just because the registry cites a source
    or a raw snapshot exists. Reviewed transformations remain outside this read-only helper.
    """

    snapshot_by_key = {
        row["parameter_key"]: row
        for row in build_parameter_snapshot_status([p["key"] for p in parameters], cache_root=cache_root)
    }
    transformation_by_key = _latest_transformation_by_parameter(cache_root)
    rows: list[dict] = []
    for parameter in parameters:
        key = parameter["key"]
        data_status = parameter.get("data_status", "annahme")
        cache_status = snapshot_by_key[key]
        transformation = transformation_by_key.get(key)
        rows.append(
            {
                "parameter_key": key,
                "label": parameter.get("label", key),
                "unit": parameter.get("unit", ""),
                "evidence_grade": parameter.get("evidence_grade", "E"),
                "source_ids": parameter.get("source_ids", []),
                "registry_data_status": data_status,
                "registry_label": "aus Daten" if data_status == "aus_daten" else "Annahme, nicht aus Daten",
                "source_version": parameter.get("source_version", ""),
                "data_lineage": parameter.get("data_lineage", ""),
                "cache": cache_status,
                "transformation_review": _transformation_review_status(transformation),
                "passport_note": _data_passport_note(
                    data_status,
                    cache_status["has_cached_snapshot"],
                    transformation.status if transformation else "not_reviewed",
                ),
            }
        )
    return rows



def build_data_readiness_summary(backlog_items: list[dict]) -> dict:
    """Summarize data-readiness gates for API/UI status cards.

    This turns the operational backlog into a first-time-user readable progress
    signal without changing any model value. Counts are about provenance gates,
    not about policy truth or import success.
    """

    gate_labels = {
        "snapshot_needed": "Rohdaten-Snapshot fehlt",
        "transformation_review_needed": "Transformationsreview fehlt",
        "explicit_model_integration_needed": "explizite Modellintegration offen",
        "monitor_only": "nur beobachten",
    }
    counts = {gate: 0 for gate in gate_labels}
    for item in backlog_items:
        gate = item.get("next_gate", "")
        if gate in counts:
            counts[gate] += 1

    first_action = backlog_items[0]["next_action"] if backlog_items else "Keine offenen Daten-Gates im aktuellen Register."
    first_parameter = backlog_items[0]["label"] if backlog_items else "—"
    return {
        "total_items": len(backlog_items),
        "counts_by_gate": counts,
        "labels_by_gate": gate_labels,
        "primary_focus": {
            "parameter": first_parameter,
            "next_action": first_action,
        },
        "plain_language_note": (
            "Diese Übersicht zählt offene Provenienz-Gates: erst Rohdaten cachen, dann Transformation prüfen, "
            "danach erst explizit Modell/Registry ändern. Sie ist kein Live-Import und kein Wirkungsbeweis."
        ),
    }


def build_data_readiness_backlog(
    parameters: list[dict],
    *,
    cache_root: Path | str = CACHE_ROOT,
    limit: int | None = None,
) -> list[dict]:
    """Return the next safe data-foundation tasks per parameter.

    The backlog is intentionally operational, not a model-import mechanism. It
    tells users/agents what is missing before a registry value could be treated
    as a reviewed data-derived model input: raw snapshot, checked transformation,
    and explicit model/registry integration remain separate gates.
    """

    priority = {
        "snapshot_needed": 0,
        "transformation_review_needed": 1,
        "explicit_model_integration_needed": 2,
        "monitor_only": 3,
    }
    rows: list[dict] = []
    for row in build_data_passport_rows(parameters, cache_root=cache_root):
        has_snapshot = row["cache"]["has_cached_snapshot"]
        review_status = row["transformation_review"]["status"]
        if not has_snapshot:
            next_gate = "snapshot_needed"
            next_action = "Rohdaten-Snapshot aus der dokumentierten Quelle holen und mit SHA256-Manifest cachen."
        elif review_status == "not_reviewed":
            next_gate = "transformation_review_needed"
            next_action = "Transformation von Rohdaten zu Modellgröße prüfen, dokumentieren und bewusst noch nicht automatisch importieren."
        elif review_status == "reviewed_model_ready":
            next_gate = "explicit_model_integration_needed"
            next_action = "Nur nach fachlicher Freigabe Registry/Modellcode explizit ändern; Snapshot allein reicht nicht."
        else:
            next_gate = "monitor_only"
            next_action = "Derzeit kein Modellimport: Review/Caveat beobachten und bei neuer Quelle erneut prüfen."

        rows.append({
            "parameter_key": row["parameter_key"],
            "label": row["label"],
            "evidence_grade": row["evidence_grade"],
            "registry_label": row["registry_label"],
            "has_cached_snapshot": has_snapshot,
            "transformation_status": review_status,
            "next_gate": next_gate,
            "next_action": next_action,
            "guardrail": "Keine Modelländerung durch diese Backlog-Aufgabe; Daten werden erst nach Review und expliziter Integration wirksam.",
        })
    rows.sort(key=lambda item: (priority.get(item["next_gate"], 99), item["evidence_grade"], item["label"]))
    return rows if limit is None else rows[:limit]

def _latest_transformation_by_parameter(cache_root: Path | str) -> dict[str, ReviewedTransformation]:
    latest: dict[str, ReviewedTransformation] = {}
    for review in list_reviewed_transformations(cache_root):
        latest.setdefault(review.parameter_key, review)
    return latest


def _transformation_review_status(transformation: ReviewedTransformation | None) -> dict:
    if transformation is None:
        return {
            "status": "not_reviewed",
            "label": "Keine geprüfte Transformation",
            "review": None,
            "status_note": "Rohdaten wurden noch nicht nachvollziehbar in einen Modellwert übersetzt.",
        }
    return {
        "status": transformation.status,
        "label": _transformation_status_label(transformation.status),
        "review": transformation.to_dict(),
        "status_note": "Transformation ist dokumentiert; Modelländerung braucht weiterhin explizite Registry-/Code-Integration.",
    }


def _transformation_status_label(status: str) -> str:
    labels = {
        "not_reviewed": "Keine geprüfte Transformation",
        "reviewed_no_model_import": "Geprüft, aber nicht ins Modell übernommen",
        "reviewed_model_ready": "Geprüft und bereit für explizite Modellintegration",
    }
    return labels.get(status, "Unbekannter Transformationsstatus")


def _data_passport_note(data_status: str, has_cached_snapshot: bool, transformation_status: str = "not_reviewed") -> str:
    if transformation_status == "reviewed_model_ready":
        return "Registry, Rohdaten und Transformationsreview sind vorhanden; Modellintegration braucht trotzdem einen expliziten Code-/Registry-Schritt."
    if transformation_status == "reviewed_no_model_import":
        return "Transformation wurde geprüft, aber bewusst nicht als Modellwert übernommen; Caveat/Review lesen."
    if data_status == "aus_daten" and has_cached_snapshot:
        return "Registry ist source-backed und ein Rohdaten-Snapshot ist vorhanden; geprüfte Transformation separat prüfen."
    if data_status == "aus_daten":
        return "Registry ist source-backed, aber der automatisierte Rohdaten-Snapshot fehlt noch."
    if has_cached_snapshot:
        return "Rohdaten-Snapshot vorhanden, aber Registry markiert den Modellwert weiter als Annahme bis zur Review."
    return "Annahme ohne verknüpften Rohdaten-Snapshot; nicht als gemessenen Datenwert lesen."
