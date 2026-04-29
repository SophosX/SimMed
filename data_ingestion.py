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
from typing import Callable, Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DataStatus = Literal["aus_daten", "annahme"]
TransformationStatus = Literal["not_reviewed", "reviewed_no_model_import", "reviewed_model_ready"]
CACHE_ROOT = Path("data/cache")
FIXTURE_ROOT = Path("data/fixtures")


@dataclass(frozen=True)
class ConnectorSnapshotRequest:
    """Read-only connector plan for fetching/caching one authoritative source payload.

    The request describes the exact endpoint/table/output parameters a connector
    should use before calling `cache_source_payload`. It is intentionally not a
    model-import object: executing it may create a raw cache artifact, but registry
    defaults still require transformation review and explicit integration.
    """

    source_id: str
    source_label: str
    endpoint_url: str
    table_code: str
    output_parameter_keys: tuple[str, ...]
    source_period: str
    suggested_filename: str
    license_or_terms_note: str
    transformation_note: str
    guardrail: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["output_parameter_keys"] = list(self.output_parameter_keys)
        return data


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


DESTATIS_GENESIS_TABLES = {
    "bevoelkerung_mio": {
        "table_code": "12411-0001",
        "source_period": "latest available year",
        "suggested_filename": "destatis_genesis_12411_0001_population.csv",
        "content": "population baseline by age/sex/status dimensions; transformation must document denominator and aggregation before model use",
    },
    "krankenhaeuser": {
        "table_code": "23111-0001",
        "source_period": "latest available year",
        "suggested_filename": "destatis_genesis_23111_0001_hospitals.csv",
        "content": "hospital statistics table candidate; connector execution must verify dimensions and whether the row represents facilities, beds or other hospital-care measures",
    },
    "krankenhausbetten": {
        "table_code": "23111-0001",
        "source_period": "latest available year",
        "suggested_filename": "destatis_genesis_23111_0001_hospital_beds.csv",
        "content": "hospital statistics table candidate; transformation must verify bed denominator, staffing caveat and reporting-year alignment before model use",
    },
}


def build_destatis_genesis_snapshot_request(parameter_key: str) -> ConnectorSnapshotRequest:
    """Return the first safe GENESIS download/cache request for a registry parameter.

    This builds the connector contract for live/download work without performing a
    network call. The endpoint is the Destatis GENESIS table download route; callers
    still need credentials/terms handling and must cache the raw payload unchanged.
    """

    if parameter_key not in DESTATIS_GENESIS_TABLES:
        raise ValueError(f"No Destatis/GENESIS connector mapping for parameter '{parameter_key}'")
    table = DESTATIS_GENESIS_TABLES[parameter_key]
    table_code = table["table_code"]
    endpoint = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
    query = urlencode({"name": table_code, "area": "all", "format": "csv"})
    return ConnectorSnapshotRequest(
        source_id="destatis_genesis",
        source_label="Destatis/GENESIS",
        endpoint_url=f"{endpoint}?{query}",
        table_code=table_code,
        output_parameter_keys=(parameter_key,),
        source_period=table["source_period"],
        suggested_filename=table["suggested_filename"],
        license_or_terms_note="Destatis/GENESIS live/download source; verify API credentials, terms and redistribution before publishing raw data.",
        transformation_note=(
            f"Raw GENESIS table {table_code} is cache/provenance input for {parameter_key}; "
            f"{table['content']}. No automatic registry or model mutation."
        ),
        guardrail="Connector request is not a model import, official forecast, or policy-effect proof; transformation review and explicit integration remain required.",
    )


def build_connector_snapshot_requests(backlog_items: list[dict], *, per_source_limit: int = 2) -> list[dict]:
    """Create concrete read-only connector requests for supported snapshot-needed backlog items."""

    requests: list[dict] = []
    per_source_counts: dict[str, int] = {}
    for item in backlog_items:
        if item.get("next_gate") != "snapshot_needed":
            continue
        source_ids = item.get("source_ids", [])
        if "destatis_genesis" not in source_ids:
            continue
        if per_source_counts.get("destatis_genesis", 0) >= per_source_limit:
            continue
        try:
            request = build_destatis_genesis_snapshot_request(item["parameter_key"])
        except ValueError:
            continue
        data = request.to_dict()
        data["parameter_label"] = item.get("label", item["parameter_key"])
        data["next_safe_action"] = "Payload über endpoint_url holen, unverändert mit cache_source_payload cachen, danach Transformationsreview schreiben."
        requests.append(data)
        per_source_counts["destatis_genesis"] = per_source_counts.get("destatis_genesis", 0) + 1
    return requests


def fetch_url_payload(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch a connector payload as bytes without interpreting or transforming it.

    The helper deliberately returns raw bytes only. Parsing, table-shape checks and
    parameter changes belong to a later reviewed transformation step.
    """

    request = Request(url, headers={"User-Agent": "SimMed-data-provenance-bot/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - configured connector URL only
        return response.read()


def build_connector_execution_plan(request: ConnectorSnapshotRequest | dict, passport_row: dict | None = None) -> list[dict]:
    """Return the safe human/agent execution ladder for one connector request.

    The plan is deliberately operational, not evidentiary: it tells users and
    agents which gate to perform next while keeping raw cache, transformation
    review and explicit model integration separate.
    """

    data = request.to_dict() if isinstance(request, ConnectorSnapshotRequest) else dict(request)
    passport = passport_row or {}
    raw_snapshot = passport.get("cache") or passport.get("raw_snapshot", {}) if isinstance(passport, dict) else {}
    transformation_review = passport.get("transformation_review", {}) if isinstance(passport, dict) else {}
    if raw_snapshot.get("has_cached_snapshot"):
        cache_label = "Rohsnapshot im Cache vorhanden"
    else:
        cache_label = raw_snapshot.get("label", "Rohsnapshot noch nicht im Cache")
    review_label = transformation_review.get("label", "Transformation noch nicht geprüft")
    parameter_label = data.get("parameter_label") or ", ".join(data.get("output_parameter_keys", []))
    return [
        {
            "order": 1,
            "gate": "dry_run",
            "label": "Dry-run prüfen",
            "status": "geplant, nicht ausgeführt",
            "instruction": f"Request für {parameter_label} lesen: Quelle {data.get('source_label')} Tabelle {data.get('table_code')}.",
            "guardrail": "Kein Netzwerkabruf, kein Rohdaten-Cache, keine Registry- oder Modelländerung.",
        },
        {
            "order": 2,
            "gate": "raw_snapshot_cache",
            "label": "Rohdaten unverändert cachen",
            "status": cache_label,
            "instruction": "Nur bei bewusster Ausführung endpoint_url laden und exakt als Rohpayload mit SHA256-Manifest speichern.",
            "guardrail": "Ein Cache-Artefakt ist noch kein Datenwert im Modell und kein Wirkungsbeweis.",
        },
        {
            "order": 3,
            "gate": "transformation_review",
            "label": "Transformation reviewen",
            "status": review_label,
            "instruction": "Tabellenform, Nenner, Einheit, Berichtsjahr und Ableitung in ReviewedTransformation dokumentieren.",
            "guardrail": "Auch ein Review mutiert den Registry-Default nicht automatisch.",
        },
        {
            "order": 4,
            "gate": "explicit_model_integration",
            "label": "Explizite Modellintegration entscheiden",
            "status": "wartet auf geprüften Review und bewussten Code/Registry-Change",
            "instruction": "Erst nach Review ParameterSpec/Modelllogik gezielt ändern, Tests ergänzen und Caveats sichtbar halten.",
            "guardrail": "Keine offizielle Prognose, keine automatische Policy-Wirkung und keine stille Parameteränderung.",
        },
    ]



def build_transformation_review_template(request: ConnectorSnapshotRequest | dict, passport_row: dict | None = None) -> dict:
    """Return a structured checklist for the review after a raw snapshot is cached.

    The template is intentionally pre-integration guidance. It tells humans/agents
    what evidence must be written into a ReviewedTransformation record before any
    registry default or model path can change.
    """

    data = request.to_dict() if isinstance(request, ConnectorSnapshotRequest) else dict(request)
    passport = passport_row or {}
    raw_snapshot = passport.get("cache") or passport.get("raw_snapshot", {}) if isinstance(passport, dict) else {}
    parameter_keys = data.get("output_parameter_keys", [])
    parameter_key = parameter_keys[0] if parameter_keys else ""
    return {
        "parameter_key": parameter_key,
        "parameter_label": data.get("parameter_label", parameter_key),
        "source_id": data.get("source_id", ""),
        "source_label": data.get("source_label", ""),
        "table_code": data.get("table_code", ""),
        "source_period": data.get("source_period", ""),
        "raw_snapshot_status": raw_snapshot.get("label", "Rohsnapshot noch nicht im Cache"),
        "required_review_fields": [
            "source_snapshot_sha256",
            "reviewer",
            "method_note",
            "output_value",
            "output_unit",
            "caveat",
            "status",
        ],
        "checklist": [
            "Rohdatei und SHA256-Manifest öffnen; keine Werte aus UI-Anzeigen abschreiben.",
            "Tabellendimensionen, Filter, Berichtsjahr und Nenner dokumentieren.",
            "Einheit und Aggregationsweg vom Rohwert zum Parameterwert beschreiben.",
            "Plausibilitätscheck gegen Registry-Min/Max und Modellrolle durchführen.",
            "Caveat notieren: Review ist noch keine Registry- oder Modellintegration.",
        ],
        "suggested_status_flow": ["not_reviewed", "reviewed_no_model_import", "reviewed_model_ready"],
        "next_safe_action": "Nach Rohsnapshot-Cache einen ReviewedTransformation-Datensatz schreiben; erst danach eine explizite Modellintegration entscheiden.",
        "guardrail": "Review-Template erzeugt keinen Datenwert im Modell, keine offizielle Prognose und keinen Policy-Wirkungsbeweis.",
    }



def build_connector_execution_workbench(
    requests: list[dict],
    passport_rows: list[dict],
    *,
    limit: int | None = None,
) -> dict:
    """Summarize planned connector work as an actionable, read-only workbench.

    This is the UI/API bridge from "a list of requests" to "what should an
    integrator do next?". It intentionally reuses Data Passport rows and the
    connector execution ladder, so it cannot infer model integration from raw
    cache or review status.
    """

    passport_by_key = {row.get("parameter_key"): row for row in passport_rows}
    rows: list[dict] = []
    ordered_requests = requests[: limit or None]
    for request in ordered_requests:
        parameter_keys = request.get("output_parameter_keys", [])
        parameter_key = parameter_keys[0] if parameter_keys else ""
        passport = passport_by_key.get(parameter_key, {})
        plan = build_connector_execution_plan(request, passport)
        raw_step = next(step for step in plan if step["gate"] == "raw_snapshot_cache")
        review_step = next(step for step in plan if step["gate"] == "transformation_review")
        rows.append(
            {
                "parameter_key": parameter_key,
                "parameter_label": request.get("parameter_label", parameter_key),
                "source_label": request.get("source_label", ""),
                "table_code": request.get("table_code", ""),
                "raw_snapshot_status": raw_step["status"],
                "transformation_review_status": review_step["status"],
                "next_safe_gate": _next_connector_safe_gate(plan),
                "execution_plan": plan,
                "transformation_review_template": build_transformation_review_template(request, passport),
                "guardrail": "Workbench ist nur Planung/Status: kein Netzwerkabruf, keine Registry- oder Modellmutation, kein Wirkungsbeweis.",
            }
        )
    return {
        "summary": {
            "planned_request_count": len(requests),
            "shown_request_count": len(rows),
            "guardrail": "Connector-Workbench plant sichere Rohdaten-Schritte; Modellintegration bleibt ein späterer expliziter Code-/Registry-Entscheid.",
        },
        "rows": rows,
    }


def _next_connector_safe_gate(plan: list[dict]) -> dict:
    """Pick the first incomplete connector gate after dry-run for concise UI/API display."""

    for step in plan:
        if step["gate"] == "dry_run":
            continue
        status = str(step.get("status", "")).lower()
        if "noch nicht" in status or "wartet" in status or "not_reviewed" in status:
            return {
                "gate": step["gate"],
                "label": step["label"],
                "status": step["status"],
                "instruction": step["instruction"],
                "guardrail": step["guardrail"],
            }
    final_step = plan[-1]
    return {
        "gate": final_step["gate"],
        "label": final_step["label"],
        "status": final_step["status"],
        "instruction": final_step["instruction"],
        "guardrail": final_step["guardrail"],
    }



def build_parameter_data_workflow_card(
    parameter_key: str,
    parameters: list[dict],
    *,
    cache_root: Path | str = CACHE_ROOT,
) -> dict:
    """Build one parameter-level data workflow card for UI/API agents.

    The card joins the Data Passport, readiness backlog, connector dry-run plan,
    and transformation-review checklist for a single parameter. It is deliberately
    read-only: it does not fetch data, write cache files, create reviews, or mutate
    registry/model values.
    """

    parameter = next((item for item in parameters if item.get("key") == parameter_key), None)
    if parameter is None:
        raise KeyError(parameter_key)

    passport_rows = build_data_passport_rows(parameters, cache_root=cache_root)
    passport = next(row for row in passport_rows if row["parameter_key"] == parameter_key)
    backlog_items = build_data_readiness_backlog(parameters, cache_root=cache_root)
    backlog_item = next(row for row in backlog_items if row["parameter_key"] == parameter_key)
    requests = build_connector_snapshot_requests(backlog_items, per_source_limit=100)
    planned_request = next(
        (request for request in requests if parameter_key in request.get("output_parameter_keys", [])),
        None,
    )

    if planned_request is None:
        review_request = {
            "parameter_label": passport.get("label", parameter_key),
            "output_parameter_keys": [parameter_key],
            "source_id": passport.get("source_ids", [""])[0] if passport.get("source_ids") else "",
            "source_label": ", ".join(passport.get("source_ids", [])),
            "table_code": "",
            "source_period": passport.get("source_version", ""),
        }
        execution_plan = [
            {
                "order": 1,
                "gate": "transformation_review",
                "label": "Transformation reviewen",
                "status": passport.get("transformation_review", {}).get("status", "not_reviewed"),
                "instruction": "Rohdaten prüfen, SHA256-Manifest und Ableitung in ReviewedTransformation dokumentieren.",
                "guardrail": "Review ist keine Registry- oder Modellmutation.",
            },
            {
                "order": 2,
                "gate": "explicit_model_integration",
                "label": "Explizite Modellintegration entscheiden",
                "status": "wartet auf geprüften Review und bewussten Code/Registry-Change",
                "instruction": "Erst nach Review ParameterSpec/Modelllogik gezielt ändern und Tests ergänzen.",
                "guardrail": "Keine offizielle Prognose, keine automatische Policy-Wirkung und keine stille Parameteränderung.",
            },
        ]
        workbench_row = None
    else:
        review_request = planned_request
        execution_plan = build_connector_execution_plan(planned_request, passport)
        workbench_row = build_connector_execution_workbench([planned_request], passport_rows)["rows"][0]

    return {
        "status": "parameter_data_workflow_not_model_integration",
        "parameter_key": parameter_key,
        "parameter_label": passport.get("label", parameter_key),
        "passport": passport,
        "backlog_item": backlog_item,
        "planned_connector_request": planned_request,
        "connector_execution_workbench": workbench_row,
        "execution_plan": execution_plan,
        "next_safe_gate": _next_connector_safe_gate(execution_plan),
        "transformation_review_template": build_transformation_review_template(review_request, passport),
        "guardrail": "Parameter-Workflow ist nur Status/Planung: kein Netzwerkabruf, kein Rohdaten-Cache, keine Registry- oder Modellmutation und kein Policy-Wirkungsbeweis.",
    }


def execute_connector_snapshot_request(
    request: ConnectorSnapshotRequest | dict,
    *,
    cache_root: Path | str = CACHE_ROOT,
    payload_fetcher: Callable[[str], bytes] | None = None,
    retrieved_at: str | None = None,
) -> dict:
    """Fetch/cache one planned connector snapshot without mutating model parameters.

    This is the first executable bridge after `ConnectorSnapshotRequest`: it
    consumes the read-only request contract, obtains the raw payload unchanged,
    writes the standard SHA256 manifest via `cache_source_payload`, and returns a
    Data-Passport-ready status object. It never parses values, updates the
    registry, or claims a policy/model effect.
    """

    data = request.to_dict() if isinstance(request, ConnectorSnapshotRequest) else dict(request)
    fetcher = payload_fetcher or fetch_url_payload
    payload = fetcher(data["endpoint_url"])
    snapshot = cache_source_payload(
        source_id=data["source_id"],
        source_url=data["endpoint_url"],
        payload=payload,
        filename=data["suggested_filename"],
        cache_root=cache_root,
        source_period=data.get("source_period", ""),
        license_or_terms_note=data.get("license_or_terms_note", ""),
        output_parameter_keys=tuple(data.get("output_parameter_keys", ())),
        transformation_note=data.get("transformation_note", ""),
        retrieved_at=retrieved_at,
    )
    return {
        "status": "raw_snapshot_cached_not_model_integration",
        "snapshot": snapshot.to_dict(),
        "guardrail": data.get("guardrail")
        or "Rohdaten-Snapshot gecacht; keine Registry- oder Modellmutation ohne Transformationsreview.",
        "next_safe_action": "Rohdatenstruktur prüfen und ein ReviewedTransformation-Review dokumentieren; erst danach explizite Modellintegration erwägen.",
    }


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



DATA_READINESS_GATE_LABELS = {
    "snapshot_needed": "Rohdaten-Snapshot fehlt",
    "transformation_review_needed": "Transformationsreview fehlt",
    "explicit_model_integration_needed": "explizite Modellintegration offen",
    "monitor_only": "nur beobachten",
}


def build_data_readiness_summary(backlog_items: list[dict]) -> dict:
    """Summarize data-readiness gates for API/UI status cards.

    This turns the operational backlog into a first-time-user readable progress
    signal without changing any model value. Counts are about provenance gates,
    not about policy truth or import success.
    """

    counts = {gate: 0 for gate in DATA_READINESS_GATE_LABELS}
    for item in backlog_items:
        gate = item.get("next_gate", "")
        if gate in counts:
            counts[gate] += 1

    first_action = backlog_items[0]["next_action"] if backlog_items else "Keine offenen Daten-Gates im aktuellen Register."
    first_parameter = backlog_items[0]["label"] if backlog_items else "—"
    return {
        "total_items": len(backlog_items),
        "counts_by_gate": counts,
        "labels_by_gate": DATA_READINESS_GATE_LABELS,
        "primary_focus": {
            "parameter": first_parameter,
            "next_action": first_action,
        },
        "plain_language_note": (
            "Diese Übersicht zählt offene Provenienz-Gates: erst Rohdaten cachen, dann Transformation prüfen, "
            "danach erst explizit Modell/Registry ändern. Sie ist kein Live-Import und kein Wirkungsbeweis."
        ),
    }


def build_next_data_readiness_actions(backlog_items: list[dict], *, limit: int = 3) -> list[dict]:
    """Return the next concrete, safe data-foundation actions for agents/UI.

    This is a small orchestration layer over the backlog: it answers "what should
    the platform team do next?" with exact API/status routes and dry-run guidance.
    It does not fetch data, write cache files, review transformations, or mutate
    registry/model values.
    """

    planned_requests = build_connector_snapshot_requests(backlog_items, per_source_limit=max(limit, 1))
    request_by_parameter = {
        key: request
        for request in planned_requests
        for key in request.get("output_parameter_keys", [])
    }
    actions: list[dict] = []
    for rank, item in enumerate(backlog_items[:limit], start=1):
        parameter_key = item["parameter_key"]
        request = request_by_parameter.get(parameter_key)
        if request is not None:
            dry_run_payload = {"parameter_key": parameter_key, "execute": False}
            primary_api = "POST /data-connectors/execute-planned-snapshot"
            operator_hint = "Dry-run ausführen, Request/Cache-Status prüfen; erst danach bewusst execute=true für Rohdaten-Cache."
        else:
            dry_run_payload = None
            primary_api = f"GET /data-readiness/{parameter_key}"
            operator_hint = "Parameter-Workflow öffnen und das nächste Gate manuell vorbereiten; kein Live-Abruf verfügbar."

        actions.append({
            "rank": rank,
            "parameter_key": parameter_key,
            "label": item["label"],
            "next_gate": item["next_gate"],
            "next_gate_label": DATA_READINESS_GATE_LABELS.get(item["next_gate"], item["next_gate"]),
            "next_action": item["next_action"],
            "primary_api": primary_api,
            "dry_run_payload": dry_run_payload,
            "workflow_api": f"GET /data-readiness/{parameter_key}",
            "planned_connector_request": request,
            "operator_hint": operator_hint,
            "guardrail": "Nächste-Aktion-Planung: kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return actions


def build_data_readiness_action_packet(actions: list[dict]) -> dict:
    """Package next actions into a copyable operator handoff for API/UI.

    The packet makes the platform backlog operational for humans and agents while
    staying read-only: commands are dry-run/status calls only, never execute=true
    connector calls and never registry/model mutation instructions.
    """

    rows: list[dict] = []
    for action in actions:
        payload = action.get("dry_run_payload")
        if payload:
            api_command = (
                "curl -X POST /data-connectors/execute-planned-snapshot "
                f"-d '{{\"parameter_key\": \"{payload['parameter_key']}\", \"execute\": false}}'"
            )
            mode = "dry_run_status"
        else:
            api_command = f"curl {action['workflow_api'].replace('GET ', '')}"
            mode = "workflow_status"
        rows.append({
            "rank": action["rank"],
            "parameter_key": action["parameter_key"],
            "label": action["label"],
            "mode": mode,
            "copyable_api_command": api_command,
            "operator_checklist": [
                "Workflow-/Dry-run-Status lesen",
                "Rohdaten-Cache-Status und SHA256/Manifest prüfen",
                "Transformation separat reviewen, bevor Registry/Modell geändert wird",
            ],
            "next_review_route": f"GET /data-connectors/transformation-review-template/{action['parameter_key']}",
            "guardrail": "Copy-Paste-Paket ist Status/Dry-run-only: kein execute=true, kein Netzwerkabruf durch diese Planung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return {
        "title": "Copy-Paste Arbeitsauftrag für nächste Daten-Gates",
        "plain_language_note": (
            "Dieses Paket übersetzt die nächsten Daten-Backlog-Zeilen in sichere API-Schritte. "
            "Es ist für Operatoren/Agents gedacht und bleibt ausdrücklich Status/Dry-run-only."
        ),
        "rows": rows,
        "guardrail": "Action-Packet führt nichts aus: kein Live-Fetch, kein Cache-Schreibvorgang, keine Modellintegration, keine amtliche Prognose und kein Wirkungsbeweis.",
    }


def build_data_readiness_operator_handoff(actions: list[dict]) -> dict:
    """Return a focused, safe handoff for the next human/agent platform cycle.

    Unlike the raw action packet, this adds a plain-language execution order and
    per-action verification route so a future operator can move from status to
    reviewed transformation without guessing. It still performs no data action.
    """

    packet = build_data_readiness_action_packet(actions)
    rows: list[dict] = []
    for action, packet_row in zip(actions, packet["rows"]):
        if action.get("planned_connector_request"):
            first_step = "Dry-run-Status prüfen; erst ein späterer bewusster Schritt darf Rohdaten cachen."
            verification_route = action["primary_api"]
        else:
            first_step = "Parameter-Workflow öffnen und fehlendes Gate manuell vorbereiten."
            verification_route = action["workflow_api"]
        rows.append({
            "rank": action["rank"],
            "parameter_key": action["parameter_key"],
            "label": action["label"],
            "first_safe_step": first_step,
            "status_or_dry_run_route": verification_route,
            "workflow_route": action["workflow_api"],
            "review_template_route": packet_row["next_review_route"],
            "copyable_status_command": packet_row["copyable_api_command"],
            "definition_of_done_before_model_integration": [
                "Rohdaten-Snapshot mit Manifest/SHA256 ist sichtbar",
                "Transformation ist separat reviewed und caveat-dokumentiert",
                "Registry-/Modelländerung ist als eigener, getesteter Integrationsschritt entschieden",
            ],
            "guardrail": "Operator-Handoff ist nur Arbeitsreihenfolge und Status/Dry-run: kein execute=true, kein Live-Fetch, kein Cache-Schreiben, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return {
        "title": "Operator-Handoff: nächste Daten-Gates sicher abarbeiten",
        "plain_language_note": (
            "Diese Übergabe sagt nicht nur, welche API aufgerufen wird, sondern wann ein Datenpunkt wirklich bereit für eine spätere Modellintegration wäre. "
            "Sie bleibt Status/Dry-run-only und trennt Rohdaten, Review und explizite Integration."
        ),
        "sequence": [
            "1. Status/Dry-run lesen",
            "2. Rohdaten-Cache nur bewusst und getrennt ausführen",
            "3. Transformation mit Review-Template prüfen",
            "4. Modellintegration separat planen, testen und dokumentieren",
        ],
        "rows": rows,
        "guardrail": "Handoff führt nichts aus: kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Modellintegration, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_platform_brief(actions: list[dict]) -> dict:
    """Create a compact platform-work brief from the next safe data actions.

    This is the cron/operator-facing wrapper around the existing handoff. It
    answers: what is the next platform slice, how is it verified, and what must
    still *not* be inferred? It stays read-only/status-only and deliberately
    contains no execute=true commands.
    """

    handoff = build_data_readiness_operator_handoff(actions)
    rows: list[dict] = []
    for handoff_row in handoff["rows"]:
        rows.append({
            "rank": handoff_row["rank"],
            "parameter_key": handoff_row["parameter_key"],
            "label": handoff_row["label"],
            "platform_slice": handoff_row["first_safe_step"],
            "verification": (
                f"Status prüfen über {handoff_row['status_or_dry_run_route']} und Workflow prüfen über "
                f"{handoff_row['workflow_route']}; Review-Template: {handoff_row['review_template_route']}."
            ),
            "definition_of_done": " · ".join(handoff_row["definition_of_done_before_model_integration"]),
            "guardrail": handoff_row["guardrail"],
        })
    return {
        "title": "Plattform-Brief: nächste Datenarbeit ohne Modellmutation",
        "plain_language_note": (
            "Dieser Brief ist für kurze Plattform-Zyklen: erst Status/Dry-run, dann bewusstes Rohdaten-Caching, "
            "dann Review, danach separate Modellintegration. Er ist kein Importknopf."
        ),
        "sequence": handoff["sequence"],
        "rows": rows,
        "guardrail": "Plattform-Brief ist read-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_dashboard_cards(summary: dict, actions: list[dict]) -> dict:
    """Return mobile-safe status cards for the data-readiness platform dashboard.

    The cards translate the backlog summary into an opening UI/API view: what is
    still missing, what should be opened first, and what must not be inferred.
    They intentionally reuse existing summary/action structures and perform no
    connector execution, cache write, review creation, or model integration.
    """

    counts = summary.get("counts_by_gate", {})
    labels = summary.get("labels_by_gate", DATA_READINESS_GATE_LABELS)
    cards = [
        {
            "id": "overall_progress",
            "title": "Daten-Reife insgesamt",
            "value": str(summary.get("total_items", 0)),
            "caption": "offene Registry-/Provenienz-Gates",
            "next_click": "GET /data-readiness-backlog",
            "guardrail": "Zählt Arbeitsgates, nicht importierte Modellwerte oder Policy-Wirkungsbeweise.",
        }
    ]
    for gate in ("snapshot_needed", "transformation_review_needed", "explicit_model_integration_needed"):
        cards.append({
            "id": gate,
            "title": labels.get(gate, gate),
            "value": str(counts.get(gate, 0)),
            "caption": _dashboard_gate_caption(gate),
            "next_click": "GET /data-readiness/next-actions" if counts.get(gate, 0) else "GET /data-passport",
            "guardrail": "Statuskarte ist read-only: kein Netzwerkabruf, kein Cache-Schreiben und keine Registry-/Modellmutation.",
        })

    first_action = actions[0] if actions else None
    return {
        "title": "Daten-Reife Cockpit: erst verstehen, dann bewusst ausführen",
        "plain_language_note": (
            "Diese Karten sind der erste Blick auf die Datenbasis: Registry-Status, Rohdaten-Cache, Review und spätere Modellintegration bleiben getrennt."
        ),
        "cards": cards,
        "first_safe_action": {
            "parameter_key": first_action["parameter_key"],
            "label": first_action["label"],
            "next_gate_label": first_action["next_gate_label"],
            "primary_api": first_action["primary_api"],
            "workflow_api": first_action["workflow_api"],
            "operator_hint": first_action["operator_hint"],
            "guardrail": first_action["guardrail"],
        } if first_action else None,
        "guardrail": "Cockpit ist Status/Navigation-only: kein execute=true, kein Live-Fetch, kein Cache-Schreiben, keine Review-Erzeugung, keine Modellintegration und kein Wirkungsbeweis.",
    }



def _dashboard_gate_caption(gate: str) -> str:
    captions = {
        "snapshot_needed": "Rohdaten fehlen noch im Cache/Manifest.",
        "transformation_review_needed": "Rohdaten existieren, aber die Transformation ist noch nicht geprüft.",
        "explicit_model_integration_needed": "Review liegt vor; eine getestete Registry-/Modelländerung ist separat zu entscheiden.",
    }
    return captions.get(gate, "Daten-Gate prüfen.")



def build_data_connector_queue(backlog_items: list[dict], *, per_source_limit: int = 4) -> list[dict]:
    """Group snapshot-needed parameters by source so connector work can start safely.

    This is the bridge from a passive data-readiness backlog to concrete connector
    implementation slices. It still does not fetch live data or mutate model values;
    it only tells agents which source connector would unlock which source-backed
    parameters first. Assumption-only parameters remain outside this connector
    queue unless they cite a real source id in the registry.
    """

    source_labels = {
        "destatis_genesis": "Destatis/GENESIS",
        "eurostat": "Eurostat",
        "bmg_gbe": "BMG/GBE",
        "bundesaerztekammer": "Bundesärztekammer",
        "kbv_zi": "KBV/Zi",
        "gematik_bfarm": "gematik/BfArM",
        "gkv_spitzenverband": "GKV-Spitzenverband",
        "bas_bundesamt_soziale_sicherung": "BAS",
        "hrk_destatis_hochschulstatistik": "HRK/Destatis Hochschulstatistik",
    }
    blocked_source_ids = {"expert_assumption"}
    grouped: dict[str, list[dict]] = {}
    for item in backlog_items:
        if item.get("next_gate") != "snapshot_needed":
            continue
        for source_id in item.get("source_ids", []):
            if source_id in blocked_source_ids:
                continue
            grouped.setdefault(source_id, []).append(item)

    queue: list[dict] = []
    for source_id, items in grouped.items():
        examples = items[:per_source_limit]
        queue.append({
            "source_id": source_id,
            "source_label": source_labels.get(source_id, source_id),
            "open_parameter_count": len(items),
            "example_parameters": [item["label"] for item in examples],
            "parameter_keys": [item["parameter_key"] for item in examples],
            "connector_next_action": (
                f"Live/Download-Connector für {source_labels.get(source_id, source_id)} bauen oder prüfen, "
                "Payload unverändert cachen, SHA256-Manifest schreiben und noch keine Modellwerte ändern."
            ),
            "guardrail": "Connector-Queue ist Arbeitsplanung: Rohdaten holen/cachen, aber keine automatische Registry- oder Modellmutation.",
        })
    return sorted(queue, key=lambda item: (-item["open_parameter_count"], item["source_label"]))


def build_data_readiness_gate_plan(backlog_items: list[dict], *, per_gate_limit: int = 3) -> list[dict]:
    """Group the data-readiness backlog into a sequential, safe implementation plan.

    This is intentionally a planning/readability layer for API and Learning Page:
    it does not import data, does not mark a parameter as model-ready, and does
    not change registry defaults. It helps agents/users see the order of work:
    snapshot -> transformation review -> explicit integration -> monitoring.
    """

    gate_explanations = {
        "snapshot_needed": "Zuerst Rohdaten aus der dokumentierten Quelle speichern und mit Manifest/Hash nachvollziehbar machen.",
        "transformation_review_needed": "Danach prüfen, wie Rohdaten in genau diese Modellgröße übersetzt würden.",
        "explicit_model_integration_needed": "Erst nach Review bewusst Registry/Modellcode ändern; kein automatischer Import.",
        "monitor_only": "Bereits geprüfte oder bewusst nicht integrierte Daten beobachten und bei neuen Quellen erneut prüfen.",
    }
    plan: list[dict] = []
    for order, gate in enumerate(DATA_READINESS_GATE_LABELS, start=1):
        items = [item for item in backlog_items if item.get("next_gate") == gate]
        plan.append(
            {
                "order": order,
                "gate": gate,
                "label": DATA_READINESS_GATE_LABELS[gate],
                "open_count": len(items),
                "why_this_gate": gate_explanations[gate],
                "example_parameters": [item["label"] for item in items[:per_gate_limit]],
                "next_actions": [item["next_action"] for item in items[:per_gate_limit]],
                "guardrail": "Planungsstatus nur für Provenienzarbeit: keine Live-Datenübernahme, keine Modellmutation, kein Wirkungsbeweis.",
            }
        )
    return plan


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
            "source_ids": row["source_ids"],
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
