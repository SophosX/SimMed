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


def verify_cached_snapshot_integrity(snapshot: CachedSourceSnapshot | dict) -> dict:
    """Recompute the raw file SHA256 for a cached snapshot manifest.

    This is a provenance safety check only. A matching hash proves that the cached
    raw bytes still match the manifest; it does not validate source semantics,
    transformation correctness, Registry integration, or policy effects.
    """

    snapshot_data = snapshot.to_dict() if isinstance(snapshot, CachedSourceSnapshot) else dict(snapshot)
    raw_path = Path(snapshot_data.get("raw_path", ""))
    expected_sha = snapshot_data.get("sha256", "")
    if not raw_path.exists() or not raw_path.is_file():
        return {
            "source_id": snapshot_data.get("source_id", ""),
            "raw_path": str(raw_path),
            "output_parameter_keys": list(snapshot_data.get("output_parameter_keys", [])),
            "source_period": snapshot_data.get("source_period", ""),
            "expected_sha256": expected_sha,
            "actual_sha256": None,
            "integrity_status": "raw_file_missing",
            "guardrail": "Integrity-Check ist read-only: fehlende oder passende Rohdateien sind keine Transformation, keine Registry-/Modellintegration und kein Wirkungsbeweis.",
        }

    actual_sha = snapshot_payload_hash(raw_path.read_bytes())
    return {
        "source_id": snapshot_data.get("source_id", ""),
        "raw_path": str(raw_path),
        "output_parameter_keys": list(snapshot_data.get("output_parameter_keys", [])),
        "source_period": snapshot_data.get("source_period", ""),
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "integrity_status": "sha256_match" if expected_sha == actual_sha else "sha256_mismatch",
        "guardrail": "Integrity-Check ist read-only: SHA256-Abgleich beweist nur Cache-Unverändertheit, nicht Transformation, Registry-/Modellintegration oder Policy-Wirkung.",
    }


def build_cached_snapshot_integrity_report(cache_root: Path | str = CACHE_ROOT) -> dict:
    """Return a read-only integrity report for all cached raw snapshot manifests."""

    snapshots = list_cached_snapshots(cache_root=cache_root)
    rows = [verify_cached_snapshot_integrity(snapshot) for snapshot in snapshots]
    return {
        "title": "Rohdaten-Cache-Integrität vor Transformation",
        "plain_language_note": (
            "Dieser Check vergleicht jedes Rohdaten-Artefakt erneut mit dem SHA256 im Manifest. "
            "Er beantwortet nur: Ist der Cache unverändert? Er beantwortet nicht: Ist der Wert schon modellreif?"
        ),
        "summary": {
            "snapshots_seen": len(rows),
            "sha256_match": sum(1 for row in rows if row["integrity_status"] == "sha256_match"),
            "sha256_mismatch": sum(1 for row in rows if row["integrity_status"] == "sha256_mismatch"),
            "raw_file_missing": sum(1 for row in rows if row["integrity_status"] == "raw_file_missing"),
        },
        "rows": rows,
        "guardrail": "Read-only/Integrität-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Transformation, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }


def build_cached_snapshot_review_start_checklist(integrity_report: dict, limit: int = 5) -> dict:
    """Return the safe pre-review checklist for raw snapshots whose SHA256 matches.

    This bridges raw-cache integrity to the separate transformation-review template
    without creating a review, fetching data, or mutating model/registry values.
    """

    ready_rows = [
        row for row in integrity_report.get("rows", [])
        if row.get("integrity_status") == "sha256_match"
    ]
    blocked_rows = [
        row for row in integrity_report.get("rows", [])
        if row.get("integrity_status") in {"sha256_mismatch", "raw_file_missing"}
    ]
    rows = []
    for row in ready_rows[:limit]:
        parameter_keys = list(row.get("output_parameter_keys") or [])
        rows.append({
            "source_id": row.get("source_id", ""),
            "raw_path": row.get("raw_path", ""),
            "source_period": row.get("source_period", ""),
            "output_parameter_keys": parameter_keys,
            "source_snapshot_sha256": row.get("actual_sha256", ""),
            "review_template_routes": [
                f"GET /data-connectors/transformation-review-template/{key}"
                for key in parameter_keys
            ],
            "first_review_questions": [
                "Passt die Rohdatei exakt zum Manifest-SHA256?",
                "Sind Jahr/Filter/Tabelle/Denominator nachvollziehbar dokumentiert?",
                "Ist der Zielwert mit Einheit und Plausibilitätsgrenzen vereinbar?",
                "Welche Caveats verhindern noch Registry-/Modellintegration?",
            ],
            "may_create_review_after_manual_check": True,
            "guardrail": "Start-Checkliste ist read-only: SHA256 ok erlaubt nur manuelle Transformation-Review, nicht Modellintegration, amtliche Prognose oder Wirkungsbeweis.",
        })
    return {
        "title": "Rohsnapshot → Transformation-Review: Start-Checkliste",
        "status": "review_start_blocked_by_integrity" if blocked_rows else ("review_start_ready_for_manual_check" if rows else "no_integrity_checked_snapshot_ready"),
        "blocked_snapshot_count": len(blocked_rows),
        "ready_snapshot_count": len(ready_rows),
        "rows": rows,
        "definition_of_done_before_review_creation": [
            "SHA256-Match in der Integritätsprüfung",
            "Rohdatei und Manifest manuell geöffnet",
            "Tabelle/Filter/Jahr/Einheit/Denominator geprüft",
            "Review-Template je Parameter ausgefüllt; Modellintegration bleibt separater PR",
        ],
        "guardrail": "Read-only/Pre-review-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_cached_snapshot_review_start_status_cards(review_start_checklist: dict) -> list[dict]:
    """Return mobile-safe status cards for the raw-snapshot -> review-start gate.

    The cards are intentionally read-only UX guidance. They translate the
    checklist into a first-contact sequence without creating reviews or making
    model/registry claims.
    """

    rows = review_start_checklist.get("rows", [])
    blocked_count = review_start_checklist.get("blocked_snapshot_count", 0)
    ready_count = review_start_checklist.get("ready_snapshot_count", len(rows))
    if blocked_count:
        first_action = "Integritätsblocker klären; kein Review starten."
        review_gate_status = "blockiert"
    elif rows:
        first_action = "Erste Review-Vorlage öffnen und Rohdatei/Manifest manuell prüfen."
        review_gate_status = "bereit für manuelle Prüfung"
    else:
        first_action = "Erst Rohsnapshot-Integrität oder Connector-Dry-run prüfen."
        review_gate_status = "noch nicht bereit"

    return [
        {
            "order": 1,
            "title": "1. Rohcache-Integrität",
            "status": review_start_checklist.get("status", "unknown"),
            "signal": f"{ready_count} SHA256-passende Snapshots, {blocked_count} Blocker",
            "first_action": "Nur Snapshots mit SHA256-Match dürfen in die manuelle Review-Vorbereitung.",
            "route": "GET /data-snapshots/integrity",
            "guardrail": "Integrität ist noch keine Transformation, kein Modellwert und kein Wirkungsbeweis.",
        },
        {
            "order": 2,
            "title": "2. Transformation-Review vorbereiten",
            "status": review_gate_status,
            "signal": f"{len(rows)} Review-Start-Zeilen werden angezeigt",
            "first_action": first_action,
            "route": "GET /data-snapshots/review-start-checklist",
            "guardrail": "Vorbereitung ist read-only: keine Review-Erzeugung und keine Registry-/Modellmutation.",
        },
        {
            "order": 3,
            "title": "3. Modellintegration getrennt halten",
            "status": "immer separater PR",
            "signal": "Review-Template kann Evidenz ordnen, setzt aber keinen Defaultwert.",
            "first_action": "Erst nach ausgefülltem Review, Entscheidung und Tests einen separaten Registry-/Modell-PR planen.",
            "route": "GET /data-readiness/integration-preflight",
            "guardrail": "Keine amtliche Prognose, kein automatischer Import und kein Wirkungsbeweis.",
        },
    ]


def build_transformation_review_draft_preflight(review_start_checklist: dict) -> dict:
    """Return a read-only preflight before creating persisted transformation reviews.

    The preflight turns the review-start checklist into explicit required fields
    for a future ReviewedTransformation. It does not create a review, write
    files, fetch data, or change registry/model values.
    """

    rows = []
    for row in review_start_checklist.get("rows", []):
        for parameter_key, route in zip(
            row.get("output_parameter_keys", []),
            row.get("review_template_routes", []),
            strict=False,
        ):
            rows.append({
                "parameter_key": parameter_key,
                "source_id": row.get("source_id", ""),
                "raw_path": row.get("raw_path", ""),
                "source_period": row.get("source_period", ""),
                "source_snapshot_sha256": row.get("source_snapshot_sha256", ""),
                "review_template_route": route,
                "required_before_record_review": [
                    "reviewer identity/role",
                    "method_note with table/filter/year/denominator",
                    "output_value and output_unit checked against registry bounds",
                    "caveat explaining remaining uncertainty and non-integration status",
                    "source_snapshot_sha256 matched to manifest",
                ],
                "draft_status": "template_ready_not_recorded",
                "guardrail": "Preflight ist read-only: keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
            })

    blocked_count = review_start_checklist.get("blocked_snapshot_count", 0)
    if blocked_count:
        status = "draft_preflight_blocked_by_integrity"
        first_safe_step = "Integritätsblocker klären; keine Review-Daten erfassen."
    elif rows:
        status = "draft_preflight_ready_for_manual_review"
        first_safe_step = "Review-Template je Parameter öffnen und Pflichtfelder manuell prüfen; noch nichts persistieren."
    else:
        status = "draft_preflight_no_ready_snapshot"
        first_safe_step = "Erst Rohsnapshot-Integrität oder Connector-Dry-run prüfen."

    return {
        "title": "Transformation-Review-Draft: Preflight vor Persistenz",
        "status": status,
        "first_safe_step": first_safe_step,
        "ready_draft_count": len(rows),
        "blocked_snapshot_count": blocked_count,
        "rows": rows,
        "definition_of_done_before_record_review": [
            "SHA256-Match ist dokumentiert",
            "Rohdatei/Manifest wurden manuell geöffnet",
            "Transformation, Einheit, Jahr/Denominator und Plausibilitätsgrenzen sind nachvollziehbar",
            "Reviewer/Rolle und Caveat sind ausgefüllt",
            "Registry-/Modellintegration bleibt ein separater getesteter PR",
        ],
        "guardrail": "Read-only/Draft-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_transformation_review_draft_example_payload(draft_preflight: dict) -> dict:
    """Return a copyable example payload for draft validation without persisting it.

    This helps operators move from preflight status to a concrete manual review
    draft while keeping the step read-only. Placeholder values must be replaced
    after opening the raw file, manifest, and review template.
    """

    rows = draft_preflight.get("rows", [])
    first_row = rows[0] if rows else {}
    example_payload = {
        "parameter_key": first_row.get("parameter_key", "<parameter_key_from_preflight>"),
        "source_snapshot_sha256": first_row.get("source_snapshot_sha256", "<sha256_from_manifest>"),
        "reviewer": "<Name/Rolle der manuellen Reviewer:in>",
        "method_note": "<Tabelle, Filter, Berichtsjahr, Nenner, Einheit und Transformationsweg dokumentieren>",
        "output_value": "<manuell geprüfter Zahlenwert>",
        "output_unit": "<geprüfte Einheit passend zum Registry-Parameter>",
        "caveat": "<Unsicherheit/Caveat; ausdrücklich keine Registry-/Modellintegration>",
    }
    return {
        "title": "Transformation-Review-Draft: Beispielpayload für Validierung",
        "status": "draft_example_ready_not_persisted" if rows else "draft_example_blocked_no_preflight_row",
        "example_payload": example_payload,
        "copyable_validate_command": "curl -s -X POST http://localhost:8000/data-snapshots/review-draft/validate -H 'Content-Type: application/json' -d '<payload>'",
        "review_template_route": first_row.get("review_template_route", ""),
        "required_manual_replacements": [
            "Reviewer-Identität/Rolle eintragen",
            "Rohdatei und SHA256-Manifest öffnen und Hash/Quelle/Periode prüfen",
            "Methode mit Tabelle, Filtern, Jahr, Einheit und Denominator dokumentieren",
            "Output-Wert gegen Registry-Plausibilitätsgrenzen prüfen",
            "Caveat ausfüllen und Nicht-Integration ausdrücklich festhalten",
        ],
        "next_safe_step": (
            "Payload manuell ausfüllen und nur gegen /data-snapshots/review-draft/validate prüfen; Persistenz/Modellintegration separat."
            if rows
            else "Erst Rohsnapshot-Integrität und Draft-Preflight herstellen; kein Payload aus Platzhaltern speichern."
        ),
        "guardrail": "Beispielpayload ist read-only: keine Review-Erzeugung, kein Cache-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def validate_transformation_review_draft_payload(draft_preflight: dict, payload: dict) -> dict:
    """Validate a manual ReviewedTransformation draft without persisting it.

    This is the last read-only guard before an operator records a
    ReviewedTransformation. It checks required fields and whether the submitted
    parameter/SHA256 pair matches the current draft preflight rows, but it never
    writes a review file or mutates registry/model values.
    """

    required_fields = [
        "parameter_key",
        "source_snapshot_sha256",
        "reviewer",
        "method_note",
        "output_value",
        "output_unit",
        "caveat",
    ]
    missing_fields = [field for field in required_fields if payload.get(field) in (None, "", [])]

    rows = draft_preflight.get("rows", [])
    matching_row = next(
        (
            row
            for row in rows
            if row.get("parameter_key") == payload.get("parameter_key")
            and row.get("source_snapshot_sha256") == payload.get("source_snapshot_sha256")
        ),
        None,
    )
    if not rows:
        status = "draft_validation_blocked_no_preflight_row"
    elif matching_row is None:
        status = "draft_validation_blocked_by_snapshot_mismatch"
    elif missing_fields:
        status = "draft_validation_incomplete"
    else:
        status = "draft_validation_ready_for_manual_record_review"

    return {
        "status": status,
        "parameter_key": payload.get("parameter_key", ""),
        "matched_preflight_row": matching_row is not None,
        "missing_fields": missing_fields,
        "matched_review_template_route": (matching_row or {}).get("review_template_route", ""),
        "required_fields": required_fields,
        "next_safe_step": (
            "Erst fehlende Felder und SHA256-/Parameter-Match klären."
            if status != "draft_validation_ready_for_manual_record_review"
            else "Manuelle ReviewedTransformation kann separat erfasst werden; Registry-/Modellintegration bleibt danach ein eigener getesteter PR."
        ),
        "guardrail": "Validierung ist read-only: keine Review-Erzeugung, kein Cache-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_transformation_review_draft_validation_packet(draft_preflight: dict, validation: dict | None = None) -> dict:
    """Package draft validation results into a copyable, read-only operator step.

    The packet turns the raw validation object into a concrete next action for
    humans/agents: which fields are missing, which route to use, and what remains
    forbidden. It deliberately does not persist a ReviewedTransformation or mutate
    registry/model values.
    """

    rows = draft_preflight.get("rows", [])
    first_row = rows[0] if rows else {}
    if validation is None:
        validation = validate_transformation_review_draft_payload(
            draft_preflight,
            {
                "parameter_key": first_row.get("parameter_key", ""),
                "source_snapshot_sha256": first_row.get("source_snapshot_sha256", ""),
                "reviewer": "",
                "method_note": "",
                "output_value": None,
                "output_unit": "",
                "caveat": "",
            },
        )

    status = validation.get("status", "draft_validation_unknown")
    missing_fields = validation.get("missing_fields", [])
    if status == "draft_validation_ready_for_manual_record_review":
        first_safe_step = "Draft ist formal vollständig; Review-Erfassung bleibt ein separater manueller Schritt vor jeder Registry-/Modellintegration."
    elif status == "draft_validation_blocked_by_snapshot_mismatch":
        first_safe_step = "Parameter/SHA256 passt nicht zum Preflight; Rohdatei und Manifest erneut prüfen, nichts erfassen."
    elif missing_fields:
        first_safe_step = f"Fehlende Pflichtfelder ergänzen: {', '.join(missing_fields)}; danach erneut nur validieren."
    else:
        first_safe_step = "Erst Draft-Preflight herstellen; keine Platzhalter als Review erfassen."

    example_payload = build_transformation_review_draft_example_payload(draft_preflight)["example_payload"]
    return {
        "title": "Transformation-Review-Draft: Validierungspaket",
        "status": status,
        "parameter_key": validation.get("parameter_key") or first_row.get("parameter_key", ""),
        "matched_preflight_row": validation.get("matched_preflight_row", False),
        "missing_fields": missing_fields,
        "first_safe_step": first_safe_step,
        "validate_route": "POST /data-snapshots/review-draft/validate",
        "review_template_route": validation.get("matched_review_template_route") or first_row.get("review_template_route", ""),
        "copyable_validate_command": (
            "curl -s -X POST http://localhost:8000/data-snapshots/review-draft/validate "
            "-H 'Content-Type: application/json' -d '"
            + json.dumps(example_payload, ensure_ascii=False)
            + "'"
        ),
        "operator_sequence": [
            "Draft-Preflight und Rohcache-Integrität lesen",
            "Payload-Felder mit Rohdatei, Manifest, SHA256 und Review-Template ausfüllen",
            "Payload nur gegen den Validierungsendpoint prüfen",
            "ReviewedTransformation separat erfassen; danach Integration separat planen und testen",
        ],
        "guardrail": "Validierungspaket ist read-only: keine Review-Erzeugung, kein Cache-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_transformation_review_draft_status_cards(draft_preflight: dict) -> list[dict]:
    """Return mobile-safe cards for the manual transformation-review draft gate.

    These cards make the preflight understandable before an operator fills a
    ReviewedTransformation. They are deliberately read-only and do not create
    reviews, write files, or change Registry/model values.
    """

    rows = draft_preflight.get("rows", [])
    blocked_count = draft_preflight.get("blocked_snapshot_count", 0)
    ready_count = draft_preflight.get("ready_draft_count", len(rows))
    if blocked_count:
        draft_gate_status = "blockiert"
        first_action = "Integritätsblocker klären; keine Draft-Felder ausfüllen."
    elif rows:
        draft_gate_status = "bereit für manuelle Draft-Prüfung"
        first_action = "Review-Template öffnen und Pflichtfelder mit Rohdatei/Manifest abgleichen."
    else:
        draft_gate_status = "noch kein Draft bereit"
        first_action = "Erst Rohsnapshot-Integrität oder Review-Start-Checkliste prüfen."

    return [
        {
            "order": 1,
            "title": "1. Pflichtfelder vor Review",
            "status": draft_preflight.get("status", "unknown"),
            "signal": f"{ready_count} vorbereitete Draft-Zeilen, {blocked_count} Blocker",
            "first_action": "Reviewer, Methode, Einheit, Jahr/Denominator, Output-Wert und Caveat müssen vor Persistenz geprüft sein.",
            "route": "GET /data-snapshots/review-draft-preflight",
            "guardrail": "Pflichtfelder ordnen nur die manuelle Prüfung; sie erzeugen keinen Review und keinen Modellwert.",
        },
        {
            "order": 2,
            "title": "2. Manuelles Review-Template",
            "status": draft_gate_status,
            "signal": f"{len(rows)} Template-Routen sind verknüpft",
            "first_action": first_action,
            "route": "GET /data-snapshots/review-draft-handoff",
            "guardrail": "Handoff bleibt read-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung.",
        },
        {
            "order": 3,
            "title": "3. Nach Review separat entscheiden",
            "status": "separater Integrationspfad",
            "signal": "Auch ein ausgefüllter Review ist noch keine Registry-/Modellintegration.",
            "first_action": "Nach manueller Review erst Integrations-Preflight, Decision-Template und separaten getesteten PR nutzen.",
            "route": "GET /data-readiness/integration-preflight",
            "guardrail": "Keine amtliche Prognose, keine automatische Modellmutation und kein Policy-Wirkungsbeweis.",
        },
    ]


def build_transformation_review_draft_handoff_packet(draft_preflight: dict) -> dict:
    """Create a copyable handoff for manually completing review drafts.

    This is the final read-only operator packet before a human records a
    ReviewedTransformation. It points to preflight/template routes and required
    fields, but it never creates a review or mutates registry/model values.
    """

    rows = draft_preflight.get("rows", [])
    blocked_count = draft_preflight.get("blocked_snapshot_count", 0)
    if blocked_count:
        status = "draft_blocked_by_integrity"
        first_safe_step = "Integritätsblocker klären; keine Draft-Felder ausfüllen."
    elif rows:
        status = "draft_ready_for_manual_completion"
        first_safe_step = "Erstes Review-Template öffnen, Pflichtfelder aus dem Preflight manuell ausfüllen und noch nichts ins Modell übernehmen."
    else:
        status = "no_review_draft_ready"
        first_safe_step = "Erst Rohsnapshot-Integrität, Review-Start-Checkliste oder Connector-Dry-run prüfen."

    first_row = rows[0] if rows else {}
    return {
        "title": "Transformation-Review-Draft: Operator-Handoff",
        "status": status,
        "ready_draft_count": draft_preflight.get("ready_draft_count", len(rows)),
        "blocked_snapshot_count": blocked_count,
        "first_safe_step": first_safe_step,
        "preflight_route": "GET /data-snapshots/review-draft-preflight",
        "first_parameter_key": first_row.get("parameter_key", ""),
        "first_review_template_route": first_row.get("review_template_route", ""),
        "copyable_preflight_command": "curl -s http://localhost:8000/data-snapshots/review-draft-preflight",
        "operator_sequence": [
            "Draft-Preflight lesen",
            "Rohdatei/Manifest und SHA256 erneut gegenprüfen",
            "Review-Template je Parameter öffnen",
            "ReviewedTransformation erst nach manueller Prüfung erfassen",
            "Registry-/Modellintegration danach separat planen, testen und dokumentieren",
        ],
        "definition_of_done_before_record_review": draft_preflight.get("definition_of_done_before_record_review", []),
        "rows": rows,
        "guardrail": "Handoff ist draft-only/read-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_cached_snapshot_review_start_handoff_packet(review_start_checklist: dict) -> dict:
    """Create a copyable handoff for starting manual transformation reviews.

    This comes after raw-cache SHA256 integrity is OK and before any persisted
    ReviewedTransformation. It gives operators concrete review-template routes,
    but stays read-only: it never creates a review or mutates model values.
    """

    rows = review_start_checklist.get("rows", [])
    blocked_count = review_start_checklist.get("blocked_snapshot_count", 0)
    ready_count = review_start_checklist.get("ready_snapshot_count", len(rows))
    if blocked_count:
        first_safe_step = "Integritätsblocker zuerst beheben; keine Review-Vorlage ausfüllen."
        status = "review_start_blocked_by_integrity"
    elif rows:
        first_safe_step = "Erste Review-Vorlage öffnen und Rohdatei/Manifest manuell gegenprüfen; noch nichts ins Modell übernehmen."
        status = "manual_review_template_ready"
    else:
        first_safe_step = "Noch keinen Review starten; erst Rohsnapshot-Integrität oder Connector-Dry-run prüfen."
        status = "no_manual_review_template_ready"

    first_route = ""
    for row in rows:
        routes = row.get("review_template_routes") or []
        if routes:
            first_route = routes[0]
            break

    return {
        "title": "Transformation-Review starten: Operator-Handoff",
        "status": status,
        "ready_snapshot_count": ready_count,
        "blocked_snapshot_count": blocked_count,
        "first_safe_step": first_safe_step,
        "checklist_route": "GET /data-snapshots/review-start-checklist",
        "first_review_template_route": first_route,
        "copyable_status_command": "curl -s http://localhost:8000/data-snapshots/review-start-checklist",
        "operator_sequence": [
            "Pre-Review-Checkliste lesen",
            "Rohdatei und Manifest/SHA256 öffnen",
            "Passende Transformation-Review-Vorlage je Parameter öffnen",
            "Reviewer, Methode, Einheit, Jahr/Denominator und Caveat dokumentieren",
            "Registry-/Modellintegration erst in separatem getesteten PR entscheiden",
        ],
        "definition_of_done_before_review_creation": review_start_checklist.get("definition_of_done_before_review_creation", []),
        "rows": rows,
        "guardrail": "Handoff ist pre-review/read-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_cached_snapshot_integrity_handoff_packet(integrity_report: dict) -> dict:
    """Create a copyable, read-only handoff for raw-cache integrity follow-up.

    The packet translates the integrity report into operator-safe routes and a
    definition of done before any transformation review. It deliberately avoids
    network fetches, cache writes, review creation, registry/model mutation, or
    policy-effect claims.
    """

    action_plan = build_cached_snapshot_integrity_action_plan(integrity_report)
    status = action_plan["overall_status"]
    if status == "integrity_blocker_before_review":
        first_safe_step = "Integritätsblocker zuerst manuell klären; keine Transformation-Review starten."
    elif status == "integrity_ok_but_not_reviewed":
        first_safe_step = "Nur die passende Transformation-Review-Vorlage öffnen; noch keinen Modellwert ändern."
    else:
        first_safe_step = "Erst Connector-Planung/Dry-run prüfen; kein Live-Fetch aus diesem Handoff."

    return {
        "title": "Rohcache-Integrität: Operator-Handoff",
        "status": status,
        "first_safe_step": first_safe_step,
        "status_route": "GET /data-snapshots/integrity",
        "action_plan_route": "GET /data-snapshots/integrity-action-plan",
        "copyable_status_command": "curl -s http://localhost:8000/data-snapshots/integrity-action-plan",
        "operator_sequence": [
            "Integritätsstatus lesen",
            "Bei Mismatch/fehlender Rohdatei Review pausieren und Manifest/Rohdatei prüfen",
            "Bei SHA256 ok nur Transformation-Review-Template öffnen",
            "Registry-/Modellintegration separat planen, testen und dokumentieren",
        ],
        "definition_of_done_before_transformation_review": action_plan["definition_of_done_before_review"],
        "rows": action_plan["rows"],
        "guardrail": "Handoff ist read-only/status-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_cached_snapshot_integrity_action_plan(integrity_report: dict) -> dict:
    """Turn raw-cache integrity status into safe operator next actions.

    This is intentionally before transformation review and model integration: a
    mismatch or missing raw file must block downstream review; a matching hash only
    permits opening the separate transformation-review checklist.
    """

    summary = integrity_report.get("summary", {})
    rows = integrity_report.get("rows", [])
    problem_rows = [row for row in rows if row.get("integrity_status") in {"sha256_mismatch", "raw_file_missing"}]
    ready_rows = [row for row in rows if row.get("integrity_status") == "sha256_match"]
    if problem_rows:
        overall_status = "integrity_blocker_before_review"
        first_safe_action = "Rohdatei/Manifest manuell prüfen; Transformation-Review und Modellintegration pausieren."
    elif ready_rows:
        overall_status = "integrity_ok_but_not_reviewed"
        first_safe_action = "Passende Roh-Snapshots dürfen nur in den separaten Transformation-Review geführt werden."
    else:
        overall_status = "no_cached_snapshots_yet"
        first_safe_action = "Erst geplante Connector-Snapshot-Requests im Dry-run prüfen; kein Live-Fetch aus diesem Plan."

    action_rows = []
    for row in problem_rows[:5]:
        status = row.get("integrity_status", "unknown")
        action_rows.append({
            "source_id": row.get("source_id", ""),
            "raw_path": row.get("raw_path", ""),
            "integrity_status": status,
            "operator_action": "Cache-Artefakt stoppen und Quelle/Manifest neu prüfen" if status == "sha256_mismatch" else "Fehlende Rohdatei vor jeder Review rekonstruieren oder Snapshot neu planen",
            "may_start_transformation_review": False,
            "guardrail": "Integritätsproblem blockiert Review/Registry-/Modellintegration; kein execute=true und keine Policy-Wirkung ableiten.",
        })
    for row in ready_rows[: max(0, 5 - len(action_rows))]:
        action_rows.append({
            "source_id": row.get("source_id", ""),
            "raw_path": row.get("raw_path", ""),
            "integrity_status": row.get("integrity_status", "unknown"),
            "operator_action": "Nur Transformation-Review-Template öffnen; Wert/Einheit/Denominator separat prüfen",
            "may_start_transformation_review": True,
            "guardrail": "SHA256 ok heißt nur unveränderter Cache, nicht geprüfter Datenwert, nicht Modellintegration, nicht amtliche Prognose.",
        })

    return {
        "title": "Rohcache-Integrität: sichere nächste Aktionen",
        "overall_status": overall_status,
        "first_safe_action": first_safe_action,
        "summary": {
            "snapshots_seen": summary.get("snapshots_seen", 0),
            "integrity_blockers": len(problem_rows),
            "ready_for_transformation_review_only": len(ready_rows),
        },
        "rows": action_rows,
        "definition_of_done_before_review": [
            "SHA256 passt zum Manifest und Rohdatei existiert",
            "Quelle/Periode/Lizenzhinweis im Manifest gelesen",
            "Transformation-Review prüft Tabelle, Filter, Jahr, Einheit, Denominator und Plausibilität separat",
        ],
        "guardrail": "Read-only/Action-plan-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


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


def seed_reference_fixture_reviewed_transformations(
    *,
    cache_root: Path | str = CACHE_ROOT,
    fixture_root: Path | str = FIXTURE_ROOT,
) -> list[ReviewedTransformation]:
    """Seed a reviewed-model-ready *fixture* without integrating it into the model.

    This creates the first green demo path for Preflight → Integrationsplan → PR-Brief.
    It deliberately references the static population fixture and writes only a
    ReviewedTransformation record. It does not fetch live GENESIS data, update the
    Registry, change simulation defaults, or prove a policy effect.
    """

    snapshots = seed_reference_fixture_snapshots(cache_root=cache_root, fixture_root=fixture_root)
    population_snapshot = next(
        (snapshot for snapshot in snapshots if "bevoelkerung_mio" in snapshot.output_parameter_keys),
        None,
    )
    if population_snapshot is None:
        return []

    review = ReviewedTransformation(
        parameter_key="bevoelkerung_mio",
        source_snapshot_sha256=population_snapshot.sha256,
        status="reviewed_model_ready",
        reviewed_at="2026-04-29T21:30:00+00:00",
        reviewer="SimMed fixture review / not a live Destatis import",
        method_note=(
            "Static fixture review for platform workflow only: inspect CSV fixture, "
            "confirm it mirrors the current registry default unit (million people), "
            "and keep live GENESIS import plus registry/model PR separate."
        ),
        caveat=(
            "Demo fixture only: not a live GENESIS download, not an official forecast, "
            "not automatic Registry/model integration, and not policy-effect proof."
        ),
        output_value=84.5,
        output_unit="million people",
    )
    record_reviewed_transformation(review, cache_root=cache_root)
    return [review]


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



def build_data_readiness_first_contact_guide(summary: dict, actions: list[dict]) -> dict:
    """Return a plain-language first-contact guide for the data-readiness cockpit.

    This explains what a newcomer should do with the cockpit before they see the
    denser backlog tables. It is intentionally read-only and only references
    status/Dry-run routes; it never includes execute=true or implies that a data
    source, cached snapshot, or review has already changed model values.
    """

    counts = summary.get("counts_by_gate", {})
    first_action = actions[0] if actions else None
    steps = [
        {
            "order": 1,
            "question": "Welche Datenarbeit ist insgesamt noch offen?",
            "answer": f"{summary.get('total_items', 0)} Parameter haben noch ein Daten-Reife-Gate offen.",
            "open": "GET /data-readiness/dashboard-cards",
            "guardrail": "Das ist ein Arbeitsstatus, kein importierter Modellwert.",
        },
        {
            "order": 2,
            "question": "Wo starte ich sicher, ohne etwas zu verändern?",
            "answer": (
                f"Öffne zuerst {first_action['label']} und prüfe {first_action['next_gate_label']}."
                if first_action else
                "Es gibt aktuell keine priorisierte Aktion; prüfe den Datenpass."
            ),
            "open": first_action["workflow_api"] if first_action else "GET /data-passport",
            "guardrail": "Workflow-/Statusroute ist read-only: kein Netzwerkabruf, kein Cache-Schreiben, keine Modellintegration.",
        },
        {
            "order": 3,
            "question": "Warum ist ein Quellenhinweis noch kein Modelleffekt?",
            "answer": (
                f"Snapshot fehlt: {counts.get('snapshot_needed', 0)} · Review fehlt: {counts.get('transformation_review_needed', 0)} · "
                f"explizite Integration fehlt: {counts.get('explicit_model_integration_needed', 0)}."
            ),
            "open": "GET /data-readiness-backlog",
            "guardrail": "Registry-Quelle, Rohdaten-Cache, Transformationsreview und Modellintegration bleiben vier getrennte Prüfungen.",
        },
    ]
    return {
        "title": "So liest du die Daten-Reife in 60 Sekunden",
        "plain_language_note": "Erst Status verstehen, dann Dry-run/Workflow öffnen, erst später bewusst Rohdaten cachen oder Modellintegration planen.",
        "steps": steps,
        "guardrail": "First-contact-Guide ist Status/Navigation-only: kein execute=true, kein Live-Fetch, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
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



def build_data_readiness_integration_preflight(
    backlog_items: list[dict],
    passport_rows: list[dict],
    *,
    limit: int = 5,
) -> dict:
    """Return a preflight checklist before any reviewed data can enter the model.

    This is the last safety rail after raw snapshots and transformation reviews: it
    tells operators whether a parameter is actually ready for an explicit, tested
    Registry/model integration slice. It performs no integration and treats
    missing snapshots/reviews as blockers, not as failures to hide.
    """

    passport_by_key = {row.get("parameter_key"): row for row in passport_rows}
    integration_ready = [
        item for item in backlog_items if item.get("next_gate") == "explicit_model_integration_needed"
    ]
    blockers = [
        item for item in backlog_items if item.get("next_gate") in {"snapshot_needed", "transformation_review_needed"}
    ]
    selected = (integration_ready + blockers)[:limit]
    rows: list[dict] = []
    for item in selected:
        parameter_key = item["parameter_key"]
        passport = passport_by_key.get(parameter_key, {})
        cache = passport.get("cache") or passport.get("raw_snapshot", {})
        review = passport.get("transformation_review", {})
        next_gate = item.get("next_gate")
        ready = next_gate == "explicit_model_integration_needed"
        if ready:
            preflight_status = "bereit_fuer_separaten_integrationsplan"
            first_blocker = "kein Blocker im Daten-Gate; jetzt separaten Registry-/Modell-PR planen"
            required_next_step = "Integrationsplan mit Registry-Default, Tests, Modell-Smoke und Provenienz-Diff schreiben; erst danach Code ändern."
        elif next_gate == "transformation_review_needed":
            preflight_status = "blockiert_bis_transformation_review"
            first_blocker = "Rohdaten existieren, aber die Transformation ist noch nicht reviewed."
            required_next_step = "Review-Template ausfüllen und ReviewedTransformation dokumentieren, bevor Integration diskutiert wird."
        else:
            preflight_status = "blockiert_bis_rohsnapshot"
            first_blocker = "Rohdaten-Snapshot/Manifest fehlt noch."
            required_next_step = "Status/Dry-run prüfen und Rohpayload nur bewusst unverändert cachen; danach Transformation reviewen."
        rows.append({
            "parameter_key": parameter_key,
            "label": item["label"],
            "next_gate": next_gate,
            "preflight_status": preflight_status,
            "raw_cache": cache.get("label", "Rohsnapshot nicht geprüft"),
            "transformation_review": review.get("label", "Transformation nicht geprüft"),
            "first_blocker": first_blocker,
            "required_next_step": required_next_step,
            "workflow_api": f"GET /data-readiness/{parameter_key}",
            "review_template_api": f"GET /data-connectors/transformation-review-template/{parameter_key}",
            "definition_of_done": [
                "geprüfter Rohsnapshot mit SHA256/Manifest nachvollziehbar",
                "Transformation mit Methode, Einheit, Nenner, Berichtsjahr und Caveat reviewed",
                "Registry-/Modelländerung als eigener PR mit Tests und Smoke-Test umgesetzt",
                "UI/API beschriften weiterhin Quelle, Review und Modelleffekt getrennt",
            ],
            "guardrail": "Preflight ist Status/Planung: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Integrations-Preflight: erst Daten-Gates, dann Modell-PR",
        "plain_language_note": (
            "Diese Prüfung verhindert, dass ein Quellenhinweis oder ein Rohdaten-Cache versehentlich als Modellwert gilt. "
            "Nur Parameter mit geprüftem Transformationsreview dürfen in einem separaten, getesteten Integrationsplan weitergehen."
        ),
        "summary": {
            "ready_for_integration_plan": len(integration_ready),
            "blocked_before_integration": len(blockers),
            "shown_rows": len(rows),
        },
        "rows": rows,
        "guardrail": "Integrations-Preflight ist read-only/status-only: kein execute=true, kein Live-Fetch, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Wirkungsbeweis.",
    }



def build_data_readiness_integration_plan(
    preflight: dict,
    *,
    limit: int = 3,
) -> dict:
    """Return read-only implementation-plan skeletons for integration-ready rows.

    The plan is deliberately not executable automation. It translates a green
    preflight row into the files, tests, and verification commands an integrator
    should prepare in a separate PR before any reviewed value can become a model
    default. Blocked parameters are excluded so operators do not confuse missing
    raw/review gates with integration work.
    """

    ready_rows = [
        row for row in preflight.get("rows", [])
        if row.get("preflight_status") == "bereit_fuer_separaten_integrationsplan"
    ][:limit]
    plans: list[dict] = []
    for row in ready_rows:
        parameter_key = row["parameter_key"]
        plans.append({
            "parameter_key": parameter_key,
            "label": row["label"],
            "status": "planbar_aber_nicht_ausgefuehrt",
            "goal": "Geprüften Transformationswert nur in einem separaten, getesteten Registry-/Modell-PR integrieren.",
            "required_inputs": [
                "Rohsnapshot-Pfad und SHA256 aus Manifest prüfen",
                "ReviewedTransformation mit Methode, Einheit, Nenner, Berichtsjahr und Caveat lesen",
                "bisherigen Registry-Default, plausible Grenzen, source_ids und uncertainty_treatment vergleichen",
                "UI/API-Labels vorab definieren: Quelle, Review und Modelleffekt getrennt sichtbar halten",
            ],
            "proposed_files": [
                "parameter_registry.py",
                "simulation_core.py falls der Modellpfad den Wert direkt nutzt",
                "tests/test_registries.py",
                "tests/test_simulation_core.py oder ein fokussierter neuer Regressionstest",
                "docs/SOURCE_PROVENANCE_POLICY.md oder docs/AGENT_COUNCIL_LOG.md für die Integrationsentscheidung",
            ],
            "test_plan": [
                f"python3 -m pytest -q tests/test_registries.py -k {parameter_key}",
                "python3 -m pytest -q tests/test_data_ingestion.py tests/test_api.py",
                "python3 -m py_compile app.py data_sources.py parameter_registry.py provenance.py api.py simulation_core.py",
                "kleiner run_simulation-Smoke-Test nach jeder Modellpfad-Änderung",
            ],
            "definition_of_done": row.get("definition_of_done", []) + [
                "Data Passport zeigt nach Integration weiterhin Rohcache, Review und Modelleffekt getrennt",
                "Commit/PR benennt Quelle, Transformationsreview und verbleibende Caveats ausdrücklich",
            ],
            "workflow_api": row.get("workflow_api"),
            "review_template_api": row.get("review_template_api"),
            "guardrail": "Integrationsplan ist read-only: keine Registry-/Modellmutation, kein execute=true, kein Cache-Schreiben, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Parameter-spezifischer Integrationsplan (nur nach grünem Preflight)",
        "plain_language_note": (
            "Diese Pläne sagen, wie ein geprüfter Datenwert später sauber in Registry/Modell gelangen könnte. "
            "Sie führen nichts aus und zeigen geblockte Parameter bewusst nicht als integrationsbereit."
        ),
        "summary": {
            "ready_rows_in_preflight": len([
                row for row in preflight.get("rows", [])
                if row.get("preflight_status") == "bereit_fuer_separaten_integrationsplan"
            ]),
            "shown_plans": len(plans),
            "blocked_rows_seen": len([
                row for row in preflight.get("rows", [])
                if row.get("preflight_status") != "bereit_fuer_separaten_integrationsplan"
            ]),
        },
        "plans": plans,
        "guardrail": "Read-only/Planung-only: keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Wirkungsbeweis.",
    }

def build_data_readiness_registry_diff_preview(
    integration_plan: dict,
    parameters: list[dict],
    *,
    cache_root: Path | str = CACHE_ROOT,
) -> dict:
    """Preview reviewed-value vs. current Registry default before any code change.

    This is the last read-only sanity check before a future integration PR: it
    shows what would have to be compared by a human/integrator, but it does not
    edit ``parameter_registry.py`` or simulation defaults.
    """

    parameter_by_key = {parameter["key"]: parameter for parameter in parameters}
    transformation_by_key = _latest_transformation_by_parameter(cache_root)
    rows: list[dict] = []
    for plan in integration_plan.get("plans", []):
        parameter_key = plan["parameter_key"]
        parameter = parameter_by_key.get(parameter_key, {})
        transformation = transformation_by_key.get(parameter_key)
        reviewed_value = transformation.output_value if transformation else None
        current_default = parameter.get("default")
        plausible_min = parameter.get("plausible_min")
        plausible_max = parameter.get("plausible_max")
        within_bounds = None
        if isinstance(reviewed_value, (int, float)) and plausible_min is not None and plausible_max is not None:
            within_bounds = plausible_min <= reviewed_value <= plausible_max
        numeric_delta = None
        if isinstance(reviewed_value, (int, float)) and isinstance(current_default, (int, float)):
            numeric_delta = reviewed_value - current_default
        rows.append({
            "parameter_key": parameter_key,
            "label": plan.get("label", parameter.get("label", parameter_key)),
            "status": "diff_preview_only_not_applied",
            "current_registry_default": current_default,
            "reviewed_output_value": reviewed_value,
            "unit_check": {
                "registry_unit": parameter.get("unit", ""),
                "reviewed_output_unit": transformation.output_unit if transformation else "",
                "unit_matches": bool(transformation and transformation.output_unit == parameter.get("unit", "")),
            },
            "numeric_delta_from_registry_default": numeric_delta,
            "plausibility_check": {
                "plausible_min": plausible_min,
                "plausible_max": plausible_max,
                "within_registry_bounds": within_bounds,
            },
            "source_snapshot_sha256": transformation.source_snapshot_sha256 if transformation else None,
            "review_status": transformation.status if transformation else "not_reviewed",
            "required_human_decision": (
                "Nur wenn Einheit, SHA256/Manifest, Methode, Berichtsjahr, Caveat und Registry-Grenzen geprüft sind, "
                "darf ein separater PR den Default ändern."
            ),
            "guardrail": "Diff-Preview ist read-only: keine Registry-/Modellmutation, keine Datenaktion, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Registry-Diff-Preview vor Datenintegration",
        "plain_language_note": (
            "Diese Vorschau zeigt, was ein geprüfter Transformationswert gegenüber dem aktuellen Registry-Default bedeuten würde. "
            "Sie ist kein Apply-Schritt und ändert keine Modellwerte."
        ),
        "summary": {
            "plan_rows_seen": len(integration_plan.get("plans", [])),
            "shown_diff_previews": len(rows),
        },
        "rows": rows,
        "guardrail": "Read-only/Planung-only: kein Registry-Write, keine Simulationseffekt-Änderung, kein execute=true und kein Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_decision_template(decision_record: dict) -> dict:
    """Return an auditable, copy-safe template for the human Go/Hold/Reject step.

    The decision record says what must be decided. This template says exactly which
    fields a human/integrator should fill before any separate Registry integration
    branch exists. It deliberately stores no decision and performs no side effect.
    """

    rows: list[dict] = []
    for idx, row in enumerate(decision_record.get("rows", []), start=1):
        parameter_key = row["parameter_key"]
        rows.append({
            "rank": idx,
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "current_status": row.get("status", "blocked_before_human_go_no_go"),
            "allowed_decisions": ["Go", "Hold", "Reject"],
            "recommended_default": row.get("recommended_default", "Hold, bis alle Checks vollständig sind."),
            "decision_fields_to_fill": [
                "decision: Go | Hold | Reject",
                "decision_rationale: konkrete Begründung mit Quelle/Methode/Unsicherheit",
                "decided_by: Name/Rolle der verantwortlichen Person",
                "decided_at: ISO-Datum/Zeit",
                "follow_up: nächster sicherer Schritt",
            ],
            "evidence_routes_to_open": [
                f"GET /data-readiness/{parameter_key}",
                "GET /data-readiness/registry-diff-preview",
                "GET /data-readiness/integration-pr-brief",
            ],
            "branch_name_if_go": row.get("branch_name_if_go"),
            "go_only_if_all_checks_true": row.get("checks", {}),
            "safe_options": row.get("safe_options", []),
            "guardrail": "Ausfüllvorlage ist read-only: keine Entscheidungsspeicherung, kein Branch, kein execute=true, keine Cache-/Review-Aktion, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return {
        "title": "Ausfüllvorlage für Registry-Integrationsentscheidung",
        "plain_language_note": (
            "Diese Vorlage verhindert stille Modelländerungen: Eine verantwortliche Person muss Go, "
            "Hold oder Reject plus Begründung dokumentieren, bevor ein separater PR beginnt."
        ),
        "summary": {
            "decision_rows_seen": len(decision_record.get("rows", [])),
            "template_rows": len(rows),
            "go_eligible_rows": sum(1 for row in rows if row["current_status"] == "human_go_no_go_required_before_pr"),
        },
        "rows": rows,
        "guardrail": "Read-only/Template-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_decision_audit_checklist(decision_record: dict) -> dict:
    """Return a read-only audit checklist for reviewing a filled Go/Hold/Reject decision.

    The decision template tells humans what to fill. This checklist tells a reviewer
    how to audit that filled record before any implementation branch exists. It is
    intentionally status-only: it stores no decision, validates no private payload,
    and performs no Registry/model mutation.
    """

    rows: list[dict] = []
    for idx, row in enumerate(decision_record.get("rows", []), start=1):
        parameter_key = row["parameter_key"]
        checks = row.get("checks", {})
        required_checks = [
            "reviewed_value_present",
            "source_snapshot_sha256_present",
            "unit_matches_registry",
            "within_registry_bounds",
            "pr_brief_available",
        ]
        missing_technical_checks = [key for key in required_checks if checks.get(key) is not True]
        rows.append({
            "rank": idx,
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "current_status": row.get("status", "blocked_before_human_go_no_go"),
            "recommended_default": row.get("recommended_default", "Hold, bis alle Checks vollständig sind."),
            "audit_questions": [
                "Ist die Entscheidung ausdrücklich Go, Hold oder Reject?",
                "Nennt die Begründung Quelle, Methode, Unsicherheit und konkrete Folge?",
                "Sind decided_by, decided_at und follow_up ausgefüllt?",
                "Wurden Diff-Preview, PR-Brief und Parameter-Workflow geöffnet?",
                "Wird bei fehlenden Checks Hold statt Go empfohlen?",
            ],
            "technical_checks_to_reconfirm": checks,
            "missing_technical_checks_before_go": missing_technical_checks,
            "evidence_routes_to_reopen": [
                f"GET /data-readiness/{parameter_key}",
                "GET /data-readiness/registry-integration-decision-record",
                "GET /data-readiness/registry-diff-preview",
                "GET /data-readiness/integration-pr-brief",
            ],
            "audit_outcome_options": [
                "audit_ok_for_separate_pr: nur wenn Decision=Go und alle technischen Checks true sind",
                "audit_hold_required: wenn Begründung/Felder/Checks fehlen oder Unsicherheit offen ist",
                "audit_reject_or_rework: wenn Reviewwert, Einheit, Methode oder Quelle nicht plausibel ist",
            ],
            "guardrail": "Audit-Checkliste ist read-only: keine Entscheidungsspeicherung, kein Branch, kein execute=true, keine Cache-/Review-Aktion, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return {
        "title": "Audit-Checkliste für ausgefüllte Registry-Entscheidungen",
        "plain_language_note": (
            "Diese Checkliste prüft die menschliche Go/Hold/Reject-Dokumentation, bevor ein separater PR beginnt. "
            "Sie macht unvollständige Entscheidungen sichtbar, speichert aber selbst nichts."
        ),
        "summary": {
            "decision_rows_seen": len(decision_record.get("rows", [])),
            "audit_rows": len(rows),
            "rows_requiring_hold_by_checks": sum(1 for row in rows if row["missing_technical_checks_before_go"]),
        },
        "rows": rows,
        "guardrail": "Read-only/Audit-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_pr_runbook(decision_record: dict) -> dict:
    """Return a conservative PR runbook after an audited Go decision.

    The handoff packet says what must be decided. This runbook says how a future
    integrator should execute a *separate* Registry/model PR if and only if the
    audited decision is Go. It remains read-only: it does not create a branch,
    write files, run connectors, persist decisions, or change model values.
    """

    rows: list[dict] = []
    for idx, row in enumerate(decision_record.get("rows", []), start=1):
        parameter_key = row["parameter_key"]
        checks = row.get("checks", {})
        all_checks_green = all(
            checks.get(key) is True
            for key in [
                "reviewed_value_present",
                "source_snapshot_sha256_present",
                "unit_matches_registry",
                "within_registry_bounds",
                "pr_brief_available",
            ]
        )
        rows.append({
            "rank": idx,
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "pr_runbook_status": "pr_runbook_waits_for_audited_go" if all_checks_green else "blocked_keep_hold",
            "allowed_start_condition": "Nur nach dokumentierter Decision=Go und bestandenem Audit; sonst Hold.",
            "branch_name_if_go": row.get("branch_name_if_go"),
            "copyable_evidence_routes": [
                f"GET /data-readiness/{parameter_key}",
                "GET /data-readiness/registry-integration-decision-record",
                "GET /data-readiness/registry-integration-decision-audit-checklist",
                "GET /data-readiness/registry-diff-preview",
                "GET /data-readiness/integration-pr-brief",
            ],
            "implementation_sequence_if_go": [
                "1. Separaten Branch aus aktuellem main erstellen; keine Connectoren ausführen.",
                "2. Registry-Diff-Preview, ReviewedTransformation und SHA256-Manifest in der PR-Beschreibung zitieren.",
                "3. parameter_registry.py nur für den auditierten Parameter und mit Quelle/Version/Caveat aktualisieren.",
                "4. simulation_core.py nur ändern, wenn der Parameter dort explizit aus dem Registry-Default übernommen werden muss.",
                "5. API/UI-Labels prüfen: aus Daten, Rohcache, Transformationsreview und Modellintegration bleiben getrennt.",
                "6. Fokussierte Registry/API/UI-Tests, py_compile und einen kleinen Simulation-Smoke ausführen.",
            ],
            "files_to_consider": [
                "parameter_registry.py",
                "simulation_core.py (nur falls Modell-Default tatsächlich betroffen ist)",
                "tests/test_registries.py",
                "tests/test_api.py",
                "tests/test_app_explanations.py",
                "docs/AGENT_COUNCIL_LOG.md",
            ],
            "definition_of_done_for_pr": [
                "Nur ein auditiert freigegebener Parameter wurde integriert",
                "Registry/default, Quelle, Version, Datenlinie und Caveat sind konsistent",
                "Data-Passport/Readiness-Labels zeigen Modellintegration separat von Cache/Review",
                "Tests und Smoke laufen; PR-Text enthält Guardrails und keine Wirkungsbehauptung",
            ],
            "guardrail": "PR-Runbook ist read-only: kein Branch, kein execute=true, kein Netzwerkabruf, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Registry-Integrations-PR-Runbook nach Audit-Go",
        "plain_language_note": (
            "Dieses Runbook ist die letzte Status-Schiene vor echter Codearbeit: Es erklärt, wie ein separater PR "
            "aussehen müsste, startet ihn aber nicht. Ohne auditiertes Go bleibt der sichere Default Hold."
        ),
        "summary": {
            "decision_rows_seen": len(decision_record.get("rows", [])),
            "runbook_rows": len(rows),
            "rows_blocked_or_waiting_for_go": sum(1 for row in rows if row["pr_runbook_status"] != "pr_runbook_waits_for_audited_go"),
        },
        "rows": rows,
        "guardrail": "Read-only/Runbook-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_status_board(
    decision_record: dict,
    audit_checklist: dict,
    pr_runbook: dict,
) -> dict:
    """Return a compact read-only board for the last Registry integration gates.

    The Decision-Record, Audit-Checklist and PR-Runbook are intentionally detailed.
    This board compresses them into one newcomer/operator view: what is the current
    state, which gate blocks a Registry/model PR, and which status route should be
    opened next. It never persists decisions, starts branches, executes connectors,
    writes reviews, or mutates Registry/model defaults.
    """

    audit_by_key = {row["parameter_key"]: row for row in audit_checklist.get("rows", [])}
    runbook_by_key = {row["parameter_key"]: row for row in pr_runbook.get("rows", [])}
    rows: list[dict] = []
    for idx, row in enumerate(decision_record.get("rows", []), start=1):
        parameter_key = row["parameter_key"]
        audit_row = audit_by_key.get(parameter_key, {})
        runbook_row = runbook_by_key.get(parameter_key, {})
        checks = row.get("checks", {})
        missing_checks = audit_row.get("missing_technical_checks_before_go", [])
        if missing_checks:
            board_status = "hold_bis_technical_checks_gruen"
            next_gate = "Fehlende technische Checks schließen und Decision=Hold dokumentieren"
        elif row.get("status") != "human_go_no_go_required_before_pr":
            board_status = "hold_bis_decision_record_vollstaendig"
            next_gate = "Go/Hold/Reject-Entscheidung vollständig ausfüllen"
        else:
            board_status = "bereit_fuer_menschliches_go_audit"
            next_gate = "Menschliches Go/Hold/Reject auditieren; PR erst danach"
        rows.append({
            "rank": idx,
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "board_status": board_status,
            "green_check_count": sum(1 for ok in checks.values() if ok is True),
            "missing_checks_before_go": missing_checks,
            "next_gate": next_gate,
            "status_route": f"GET /data-readiness/{parameter_key}",
            "decision_route": "GET /data-readiness/registry-integration-decision-record",
            "audit_route": "GET /data-readiness/registry-integration-decision-audit-checklist",
            "runbook_route": "GET /data-readiness/registry-integration-pr-runbook",
            "branch_name_if_go": runbook_row.get("branch_name_if_go"),
            "guardrail": "Status-Board ist read-only: keine Entscheidungsspeicherung, kein Branch, kein execute=true, kein Netzwerkabruf, keine Cache-/Review-Aktion, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        })
    return {
        "title": "Registry-Integrations-Statusboard vor jedem PR",
        "plain_language_note": (
            "Dieses Board ist die kompakte Ampel vor echter Registry-/Modellarbeit: erst Status und Decision-Record lesen, "
            "dann Audit prüfen, und nur nach dokumentiertem Go einen separaten PR planen."
        ),
        "summary": {
            "decision_rows_seen": len(decision_record.get("rows", [])),
            "board_rows": len(rows),
            "rows_waiting_or_hold": sum(1 for row in rows if row["board_status"] != "bereit_fuer_menschliches_go_audit"),
        },
        "rows": rows,
        "guardrail": "Read-only/Statusboard-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_status_cards(status_board: dict) -> dict:
    """Return touch-friendly summary cards for the final Registry integration board.

    The status board is accurate but table-heavy. These cards give first-time users
    and mobile operators a short answer-first view before they inspect the detailed
    Decision-Record/Audit/Runbook layers. They remain read-only and never turn a
    green status into an automatic branch or Registry/model mutation.
    """

    rows = status_board.get("rows", [])
    waiting_rows = [row for row in rows if row.get("board_status") != "bereit_fuer_menschliches_go_audit"]
    ready_rows = [row for row in rows if row.get("board_status") == "bereit_fuer_menschliches_go_audit"]
    first_row = rows[0] if rows else {}
    first_waiting = waiting_rows[0] if waiting_rows else None
    first_ready = ready_rows[0] if ready_rows else None
    cards = [
        {
            "id": "overall_registry_gate",
            "title": "Wie viele Registry-Integrationszeilen stehen an?",
            "value": str(len(rows)),
            "answer": "Das sind Kandidaten nach Preflight/Diff/Decision-Record; noch keine Modelländerungen.",
            "next_click": "GET /data-readiness/registry-integration-status-board",
            "guardrail": "Statuskarte ist read-only: kein Branch, kein execute=true, keine Registry-/Modellmutation.",
        },
        {
            "id": "waiting_or_hold",
            "title": "Was blockiert vor einem Go?",
            "value": str(len(waiting_rows)),
            "answer": first_waiting.get("next_gate", "Keine blockierende Zeile im aktuellen Statusboard.") if first_waiting else "Keine blockierende Zeile im aktuellen Statusboard.",
            "next_click": "GET /data-readiness/registry-integration-decision-audit-checklist",
            "guardrail": "Fehlende Checks bedeuten Hold: erst Audit/Review klären, keine automatische Integration.",
        },
        {
            "id": "ready_for_human_audit",
            "title": "Was ist nur menschlich entscheidungsreif?",
            "value": str(len(ready_rows)),
            "answer": first_ready.get("label", "Keine Zeile ist aktuell menschlich Go/Hold/Reject-reif.") if first_ready else "Keine Zeile ist aktuell menschlich Go/Hold/Reject-reif.",
            "next_click": "GET /data-readiness/registry-integration-decision-template",
            "guardrail": "Auch grün heißt nur: Menschliches Go/Hold/Reject auditieren; kein Wirkungsbeweis und kein PR-Start.",
        },
        {
            "id": "first_safe_route",
            "title": "Wo fange ich sicher an?",
            "value": first_row.get("label", "keine Zeile"),
            "answer": first_row.get("next_gate", "Erst Statusboard öffnen und prüfen, ob ein Decision-Record existiert."),
            "next_click": first_row.get("status_route", "GET /data-readiness/registry-integration-status-board"),
            "guardrail": "Der nächste Klick ist Status/Lesen, nicht Ausführen, nicht Cachen, nicht Modellintegration.",
        },
    ]
    return {
        "title": "Registry-Integrationskarten: zuerst verstehen, dann entscheiden",
        "plain_language_note": (
            "Diese Karten übersetzen das letzte Statusboard in eine mobile Erstansicht: "
            "Wie viel ist offen, was blockiert, was ist nur menschlich entscheidungsreif, und welche Statusroute ist der sichere Start?"
        ),
        "cards": cards,
        "guardrail": "Read-only/Karten-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_operator_steps(
    status_board: dict,
    status_cards: dict | None = None,
) -> dict:
    """Return a copy-safe operator sequence for the final Registry gates.

    Status cards answer what is open; this sequence answers what to do first,
    second and third without turning any step into execution. It is deliberately
    status/read-only and keeps a human Go/Hold/Reject decision separate from
    branch/PR work and Registry/model mutation.
    """

    rows = status_board.get("rows", [])
    cards = (status_cards or {}).get("cards", [])
    card_by_id = {card.get("id"): card for card in cards}
    first_row = rows[0] if rows else {}
    first_waiting = next((row for row in rows if row.get("board_status") != "bereit_fuer_menschliches_go_audit"), None)
    first_ready = next((row for row in rows if row.get("board_status") == "bereit_fuer_menschliches_go_audit"), None)
    primary_row = first_waiting or first_ready or first_row

    steps = [
        {
            "rank": 1,
            "title": "Status zuerst lesen",
            "why": card_by_id.get("overall_registry_gate", {}).get(
                "answer",
                "Kandidaten nach Preflight/Diff/Decision-Record ansehen; noch keine Modelländerungen.",
            ),
            "copyable_status_command": "GET /data-readiness/registry-integration-status-board",
            "expected_result": "Board zeigt Board-Status, fehlende Checks und sichere nächste Route pro Parameter.",
            "guardrail": "Nur Status lesen: kein execute=true, kein Netzwerkabruf, kein Branch und keine Registry-/Modellmutation.",
        },
        {
            "rank": 2,
            "title": "Blocker oder menschliches Go/Hold/Reject prüfen",
            "why": (primary_row or {}).get("next_gate", "Erst prüfen, ob technische Checks fehlen oder nur eine menschliche Entscheidung offen ist."),
            "copyable_status_command": (primary_row or {}).get(
                "audit_route",
                "GET /data-readiness/registry-integration-decision-audit-checklist",
            ),
            "expected_result": "Audit zeigt missing checks; sicherer Default bleibt Hold, bis alle Pflichtfelder und Checks nachvollziehbar sind.",
            "guardrail": "Decision-Prüfung speichert keine Entscheidung und startet keinen PR; grün ist kein Wirkungsbeweis.",
        },
        {
            "rank": 3,
            "title": "Parameter-Workflow öffnen, bevor ein PR geplant wird",
            "why": (primary_row or {}).get("label", "Ersten Parameter aus dem Statusboard einzeln prüfen."),
            "copyable_status_command": (primary_row or {}).get("status_route", "GET /data-readiness/{parameter_key}"),
            "expected_result": "Workflow zeigt Data-Passport, Cache, Transformation-Review, Preflight, Diff und Guardrails für genau einen Parameter.",
            "guardrail": "Workflow ist read-only: keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und keine amtliche Prognose.",
        },
        {
            "rank": 4,
            "title": "PR-Runbook erst nach auditiertem Go lesen",
            "why": card_by_id.get("ready_for_human_audit", {}).get(
                "answer",
                "Nur falls alle Checks grün und menschlich auditiert sind, wird ein separater PR geplant.",
            ),
            "copyable_status_command": (primary_row or {}).get(
                "runbook_route",
                "GET /data-readiness/registry-integration-pr-runbook",
            ),
            "expected_result": "Runbook nennt Branchnamen nur als falls-Go-Hinweis; echte Codearbeit bleibt separater getesteter PR.",
            "guardrail": "Kein Branch aus diesem Paket: keine automatische Integration, kein official forecast, kein Policy-Wirkungsbeweis.",
        },
    ]
    safe_start = {
        "title": "Sicherer Start für den nächsten Integrator",
        "first_command": steps[0]["copyable_status_command"],
        "then_open": steps[2]["copyable_status_command"],
        "human_decision_default": "Hold, bis Audit-Checklist und Go/Hold/Reject-Begründung vollständig sind.",
        "do_not_do": [
            "kein execute=true aus dieser Folge ableiten",
            "keinen Branch oder PR starten, bevor ein auditiertes Go dokumentiert ist",
            "Raw-Cache, Review und Registry-/Modellintegration nicht vermischen",
        ],
        "why_this_matters": (
            "So kann ein Operator weiterarbeiten, ohne aus einem grünen Status versehentlich "
            "eine Modellintegration, amtliche Prognose oder einen Policy-Wirkungsbeweis zu machen."
        ),
    }
    return {
        "title": "Registry-Integrations-Operatorfolge: lesen → auditieren → einzeln prüfen → PR separat",
        "plain_language_note": (
            "Diese Folge macht aus Statusboard und Karten eine kopierbare Arbeitsreihenfolge für Operatoren. "
            "Alle Befehle sind Status-/Lesewege; sie enthalten bewusst kein execute=true und starten keinen Branch."
        ),
        "primary_parameter_key": primary_row.get("parameter_key") if primary_row else None,
        "safe_start": safe_start,
        "steps": steps,
        "definition_of_done_before_branch": [
            "Statusboard gelesen und Parameter einzeln geöffnet",
            "Audit-Checklist ohne fehlende technische Checks",
            "Go/Hold/Reject-Entscheidung mit Rationale, Person und Zeitpunkt außerhalb dieses read-only Pakets dokumentiert",
            "PR-Runbook nur nach auditiertem Go genutzt; Registry-/Modelländerung in separatem getestetem PR",
        ],
        "guardrail": "Read-only/Operatorfolge-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_safe_start_packet(
    operator_steps: dict,
    status_board: dict,
) -> dict:
    """Return a one-screen safe-start packet for the final Registry gates.

    The operator sequence is useful but still detailed. This packet is the shortest
    possible handoff for a sleeping/next-shift integrator: which read-only command to
    open first, which parameter to inspect next, what default decision to keep, and
    what must not be inferred. It intentionally contains no execution command, branch
    creation instruction, or model-integration action.
    """

    safe_start = operator_steps.get("safe_start", {})
    rows = status_board.get("rows", [])
    primary_key = operator_steps.get("primary_parameter_key")
    primary_row = next((row for row in rows if row.get("parameter_key") == primary_key), rows[0] if rows else {})
    next_commands = [
        operator_steps.get("safe_start", {}).get("first_command", "GET /data-readiness/registry-integration-status-board"),
        operator_steps.get("safe_start", {}).get("then_open", primary_row.get("status_route", "GET /data-readiness/{parameter_key}")),
        primary_row.get("audit_route", "GET /data-readiness/registry-integration-decision-audit-checklist"),
    ]
    next_commands = [command for command in next_commands if "execute=true" not in command]
    return {
        "title": "Registry-Integration: sicherer Start in einem Bildschirm",
        "plain_language_note": (
            "Dieses Paket ist der kürzeste Einstieg für den nächsten Integrator: erst lesen, "
            "dann einen Parameter einzeln prüfen, Default Hold behalten und keine Modelländerung ableiten."
        ),
        "primary_parameter_key": primary_row.get("parameter_key"),
        "primary_label": primary_row.get("label", "kein Parameter"),
        "current_status": primary_row.get("board_status", "kein_statusboard"),
        "first_safe_command": safe_start.get("first_command", next_commands[0]),
        "inspect_next_command": safe_start.get("then_open", next_commands[1] if len(next_commands) > 1 else "GET /data-readiness/{parameter_key}"),
        "audit_command": primary_row.get("audit_route", "GET /data-readiness/registry-integration-decision-audit-checklist"),
        "human_decision_default": safe_start.get("human_decision_default", "Hold, bis Decision/Audit vollständig sind."),
        "blocked_or_waiting_count": status_board.get("summary", {}).get("rows_waiting_or_hold", 0),
        "copyable_read_only_sequence": next_commands,
        "do_not_do": safe_start.get("do_not_do", []) + [
            "aus einem Statuspaket keinen Registry-/Modell-PR ableiten",
            "keine amtliche Prognose oder keinen Policy-Wirkungsbeweis behaupten",
        ],
        "definition_of_done_before_branch": operator_steps.get("definition_of_done_before_branch", []),
        "guardrail": "Read-only/Safe-start-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_safe_start_checklist(safe_start_packet: dict) -> dict:
    """Turn the one-screen safe-start packet into a tiny no-mutation checklist.

    The safe-start packet tells operators where to begin. This checklist makes the
    order auditable for a mobile UI/API client without adding any execution, branch,
    cache, review, or model-integration step.
    """

    primary_label = safe_start_packet.get("primary_label", "kein Parameter")
    primary_key = safe_start_packet.get("primary_parameter_key") or "{parameter_key}"
    rows = [
        {
            "rank": 1,
            "check": "Statusboard öffnen",
            "copyable_read_only_command": safe_start_packet.get(
                "first_safe_command",
                "GET /data-readiness/registry-integration-status-board",
            ),
            "expected_evidence": "Board-Status, offene Checks und nächste sichere Routen sichtbar machen.",
            "operator_decision": "Nur lesen; noch kein Go/Hold/Reject ausfüllen.",
            "guardrail": "kein execute=true, kein Netzwerkabruf, keine Daten-/Review-Aktion und kein Branch",
        },
        {
            "rank": 2,
            "check": f"Parameter einzeln prüfen: {primary_label}",
            "copyable_read_only_command": safe_start_packet.get(
                "inspect_next_command",
                f"GET /data-readiness/{primary_key}",
            ),
            "expected_evidence": "Data-Passport, Cache, Review, Preflight, Diff und Status für genau diesen Parameter sehen.",
            "operator_decision": safe_start_packet.get("human_decision_default", "Hold bis Audit vollständig ist."),
            "guardrail": "Workflow lesen ist keine Registry-/Modellmutation und kein Wirkungsbeweis",
        },
        {
            "rank": 3,
            "check": "Audit-Checkliste öffnen",
            "copyable_read_only_command": safe_start_packet.get(
                "audit_command",
                "GET /data-readiness/registry-integration-decision-audit-checklist",
            ),
            "expected_evidence": "Fehlende technische Checks und Pflichtfelder vor einem möglichen menschlichen Go sehen.",
            "operator_decision": "Default bleibt Hold, wenn ein Check fehlt oder die Begründung nicht auditierbar ist.",
            "guardrail": "Checkliste speichert keine Entscheidung und startet keinen PR",
        },
        {
            "rank": 4,
            "check": "Stoppschild vor Codearbeit",
            "copyable_read_only_command": "kein Befehl: erst menschliches Go/Hold/Reject außerhalb dieses Pakets dokumentieren",
            "expected_evidence": "Definition of done vor Branch muss erfüllt sein.",
            "operator_decision": "Branch/PR nur in separatem, getestetem Integrations-PR nach auditiertem Go.",
            "guardrail": "keine amtliche Prognose, kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung",
        },
    ]
    return {
        "title": "Safe-start-Checkliste: lesen, prüfen, auditieren, stoppen",
        "plain_language_note": (
            "Diese Checkliste macht den kürzesten Registry-Integrationsstart als vier sichtbare, "
            "mobile Schritte auditierbar. Alle Schritte sind Lese-/Statusschritte; der letzte Schritt ist bewusst ein Stoppschild."
        ),
        "primary_parameter_key": safe_start_packet.get("primary_parameter_key"),
        "primary_label": primary_label,
        "rows": rows,
        "definition_of_done_before_branch": safe_start_packet.get("definition_of_done_before_branch", []),
        "guardrail": "Read-only/Checklist-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_safe_start_cards(safe_start_checklist: dict) -> dict:
    """Return compact mobile cards for the safe-start checklist.

    The checklist table is audit-friendly but dense on phones. These cards preserve
    the same read-only commands and stop/hold guardrails as short first-contact cards
    so an operator can see the next click without interpreting a wide dataframe.
    """

    cards = []
    for row in safe_start_checklist.get("rows", []):
        command = row.get("copyable_read_only_command", "")
        decision = row.get("operator_decision", "")
        cards.append(
            {
                "rank": row.get("rank"),
                "title": row.get("check"),
                "primary_action": command,
                "decision_hint": decision,
                "expected_evidence": row.get("expected_evidence"),
                "is_stop_gate": "kein Befehl" in command.lower() or "branch" in decision.lower(),
                "guardrail": row.get("guardrail"),
            }
        )
    return {
        "title": "Safe-start-Karten: nächster Klick ohne Tabellenbreite",
        "plain_language_note": (
            "Dies sind dieselben vier Safe-start-Schritte als mobile Karten: Status lesen, "
            "einen Parameter prüfen, Audit öffnen, dann bewusst stoppen."
        ),
        "primary_parameter_key": safe_start_checklist.get("primary_parameter_key"),
        "primary_label": safe_start_checklist.get("primary_label"),
        "cards": cards,
        "guardrail": "Read-only/Card-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_progress_timeline(
    safe_start_cards: dict,
    status_board: dict,
) -> dict:
    """Return a plain-language progress timeline for the final Registry gates.

    Safe-start cards answer the next click; the status board answers technical state.
    This timeline joins both into a first-contact/mobile reading path so operators see
    where they are in the sequence without mistaking a green card for model import.
    It remains status-only and never creates decisions, branches, reviews, or model changes.
    """

    board_rows = status_board.get("rows", [])
    waiting = status_board.get("summary", {}).get("rows_waiting_or_hold", 0)
    ready = status_board.get("summary", {}).get(
        "ready_for_human_audit",
        sum(1 for row in board_rows if row.get("board_status") == "bereit_fuer_menschliches_go_audit"),
    )
    primary_key = safe_start_cards.get("primary_parameter_key")
    primary_label = safe_start_cards.get("primary_label") or "kein Parameter"
    first_card = next((card for card in safe_start_cards.get("cards", []) if not card.get("is_stop_gate")), {})
    stop_card = next((card for card in safe_start_cards.get("cards", []) if card.get("is_stop_gate")), {})
    phases = [
        {
            "rank": 1,
            "phase": "Orientieren",
            "status": "read_only_start",
            "what_to_open": first_card.get("primary_action", "GET /data-readiness/registry-integration-status-board"),
            "plain_language_result": "Statusboard und sichere Karten zeigen, welcher Parameter zuerst geprüft wird.",
            "guardrail": "Nur lesen: kein execute=true, kein Branch und keine Registry-/Modellmutation.",
        },
        {
            "rank": 2,
            "phase": "Parameter einzeln prüfen",
            "status": "primary_parameter_selected" if primary_key else "no_parameter_selected",
            "what_to_open": f"GET /data-readiness/{primary_key or '{parameter_key}'}",
            "plain_language_result": f"{primary_label}: Data-Passport, Cache, Review, Diff und Caveats zusammen ansehen.",
            "guardrail": "Ein Workflow-Status ist noch keine Datenintegration, Prognose oder Wirkungsaussage.",
        },
        {
            "rank": 3,
            "phase": "Menschliche Entscheidung vorbereiten",
            "status": "human_audit_possible" if ready else "hold_or_blocker_expected",
            "what_to_open": "GET /data-readiness/registry-integration-decision-audit-checklist",
            "plain_language_result": (
                f"{ready} Kandidat(en) auditierbar; {waiting} Kandidat(en) bleiben Hold/blockiert, bis Pflichtchecks vollständig sind."
            ),
            "guardrail": "Audit-Vorbereitung speichert kein Go/Hold/Reject und startet keinen PR.",
        },
        {
            "rank": 4,
            "phase": "Vor Codearbeit stoppen",
            "status": "stop_before_branch",
            "what_to_open": stop_card.get("primary_action", "kein Befehl: erst menschliches Go dokumentieren"),
            "plain_language_result": "Branch/PR bleibt ein separater, getesteter Integrationsschritt nach dokumentiertem Go.",
            "guardrail": "Kein Modellwert, keine amtliche Prognose, kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung.",
        },
    ]
    return {
        "title": "Registry-Integrationsfortschritt: wo stehen wir?",
        "plain_language_note": (
            "Diese Timeline übersetzt Safe-start-Karten und Statusboard in eine kurze Lesereihenfolge: "
            "orientieren, Parameter prüfen, Entscheidung auditieren, vor Codearbeit stoppen."
        ),
        "primary_parameter_key": primary_key,
        "primary_label": primary_label,
        "summary": {
            "status_rows_seen": len(board_rows),
            "ready_for_human_audit": ready,
            "waiting_or_hold": waiting,
            "timeline_phases": len(phases),
        },
        "phases": phases,
        "guardrail": "Read-only/Timeline-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_command_palette(progress_timeline: dict) -> dict:
    """Return copy-safe status commands from the Registry integration timeline.

    The progress timeline is readable, but operators often need the exact next API
    calls. This palette extracts only read-only/status commands and adds an explicit
    stop row before any branch or Registry/model integration work. It must never
    include execute=true or a branch/PR creation command.
    """

    commands: list[dict] = []
    for phase in progress_timeline.get("phases", []):
        command = phase.get("what_to_open", "")
        is_read_command = command.startswith("GET ")
        commands.append(
            {
                "rank": phase.get("rank"),
                "phase": phase.get("phase"),
                "copyable_command": command if is_read_command else "STOP: erst menschliches Go außerhalb dieses Pakets dokumentieren",
                "mode": "read_only_status" if is_read_command else "stop_no_command",
                "expected_result": phase.get("plain_language_result"),
                "guardrail": phase.get("guardrail"),
            }
        )
    return {
        "title": "Registry-Integration: Copy-Palette ohne Ausführung",
        "plain_language_note": (
            "Diese Palette macht die Timeline als kopierbare Statusbefehle nutzbar. "
            "Sie ist bewusst nur Lesen/Status und enthält keinen execute=true-, Branch- oder PR-Befehl."
        ),
        "primary_parameter_key": progress_timeline.get("primary_parameter_key"),
        "primary_label": progress_timeline.get("primary_label"),
        "commands": commands,
        "definition_of_done_before_branch": [
            "Statusbefehle gelesen und Parameter-Workflow geöffnet",
            "Audit-Checkliste ohne fehlende technische Checks nachvollzogen",
            "Go/Hold/Reject-Entscheidung mit Rationale, Entscheider und Zeitpunkt separat dokumentiert",
            "erst danach separaten, getesteten Registry-/Modell-PR planen",
        ],
        "guardrail": "Read-only/Command-palette-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_operator_briefing(
    progress_timeline: dict,
    command_palette: dict,
) -> dict:
    """Return a one-screen read-only briefing for the final Registry gates.

    The command palette is useful for operators, but first-time users need an
    answer-first summary before they copy routes. This briefing turns the same
    timeline/palette data into a mobile-safe overview: where to start, what to
    open next, where to stop, and what must never be inferred from the status.
    It is deliberately status-only and must not contain execute=true or branch
    creation commands.
    """

    commands = command_palette.get("commands", [])
    read_commands = [command for command in commands if command.get("mode") == "read_only_status"]
    stop_command = next((command for command in commands if command.get("mode") == "stop_no_command"), {})
    primary_key = progress_timeline.get("primary_parameter_key")
    primary_label = progress_timeline.get("primary_label") or "kein Parameter"
    next_read_command = next(
        (
            command.get("copyable_command")
            for command in read_commands
            if command.get("copyable_command", "").startswith(f"GET /data-readiness/{primary_key}")
        ),
        f"GET /data-readiness/{primary_key or '{parameter_key}'}",
    )
    return {
        "title": "Registry-Integration: Operator-Briefing vor Codearbeit",
        "plain_language_summary": (
            f"Start mit Status lesen, dann {primary_label} einzeln prüfen, danach menschliche Go/Hold/Reject-"
            "Entscheidung auditieren. Vor Branch/PR bewusst stoppen."
        ),
        "primary_parameter_key": primary_key,
        "primary_label": primary_label,
        "first_safe_command": read_commands[0].get("copyable_command") if read_commands else "GET /data-readiness/registry-integration-status-board",
        "next_parameter_command": next_read_command,
        "human_decision_command": next(
            (
                command.get("copyable_command")
                for command in read_commands
                if "decision-audit-checklist" in command.get("copyable_command", "")
            ),
            "GET /data-readiness/registry-integration-decision-audit-checklist",
        ),
        "stop_before_code": stop_command.get(
            "copyable_command",
            "STOP: erst menschliches Go außerhalb dieses Pakets dokumentieren",
        ),
        "operator_questions": [
            "Welcher Parameter ist zuerst auditierbar?",
            "Sind Raw-Cache, Transformationsreview, Einheit, Grenzen und PR-Brief nachvollziehbar?",
            "Ist die Entscheidung Go/Hold/Reject mit Rationale, Entscheider und Zeitpunkt dokumentiert?",
            "Wurde vor Branch/PR klar gestoppt?",
        ],
        "definition_of_done_before_branch": command_palette.get("definition_of_done_before_branch", []),
        "guardrail": "Read-only/Operator-briefing-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_operator_briefing_cards(operator_briefing: dict) -> dict:
    """Turn the operator briefing into tap-friendly action cards.

    The one-screen briefing is compact, but mobile users still need clear cards for
    the safe route sequence. These cards repeat only existing read-only commands and
    insert an explicit stop card before any branch/PR or Registry/model mutation.
    """

    card_specs = [
        (
            "start_status",
            "1. Status lesen",
            operator_briefing.get("first_safe_command", "GET /data-readiness/registry-integration-status-board"),
            "Welche Kandidaten sind überhaupt auditierbar?",
            "Nur Status lesen; kein execute=true und keine Datenaktion.",
        ),
        (
            "parameter_workflow",
            "2. Parameter einzeln öffnen",
            operator_briefing.get("next_parameter_command", "GET /data-readiness/{parameter_key}"),
            "Data-Passport, Cache, Review, Diff und Caveats für den ersten Parameter prüfen.",
            "Ein Workflow-Status ist noch keine Registry-/Modellintegration.",
        ),
        (
            "human_decision",
            "3. Entscheidung auditieren",
            operator_briefing.get("human_decision_command", "GET /data-readiness/registry-integration-decision-audit-checklist"),
            "Go/Hold/Reject nur mit Rationale, Entscheider und Zeitpunkt vorbereiten.",
            "Audit-Vorbereitung speichert keine Entscheidung und startet keinen PR.",
        ),
        (
            "stop_before_code",
            "4. Vor Codearbeit stoppen",
            operator_briefing.get("stop_before_code", "STOP: erst menschliches Go außerhalb dieses Pakets dokumentieren"),
            "Branch/PR erst nach separatem dokumentiertem Go planen.",
            "Stop-Karte: kein Branch, keine Modellmutation, keine Prognose und kein Wirkungsbeweis.",
        ),
    ]
    cards = [
        {
            "id": card_id,
            "title": title,
            "copyable_command": command,
            "operator_question": question,
            "is_stop_gate": command.startswith("STOP"),
            "guardrail": guardrail,
        }
        for card_id, title, command, question, guardrail in card_specs
    ]
    return {
        "title": "Operator-Briefing als mobile Aktionskarten",
        "plain_language_note": (
            "Dieselbe sichere Route als vier Karten: Status lesen, Parameter prüfen, "
            "Entscheidung auditieren, dann vor Codearbeit stoppen."
        ),
        "primary_parameter_key": operator_briefing.get("primary_parameter_key"),
        "primary_label": operator_briefing.get("primary_label"),
        "cards": cards,
        "definition_of_done_before_branch": operator_briefing.get("definition_of_done_before_branch", []),
        "guardrail": "Read-only/Action-cards-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_operator_briefing_handoff_sheet(briefing_cards: dict) -> dict:
    """Return a one-page handoff sheet for the mobile operator briefing cards.

    The card deck is touch-friendly, but a future human/operator also needs a
    compact audit sheet that states the exact safe order, what evidence to have
    open, and where the workflow must stop. This remains read-only/status-only
    and deliberately never creates a branch, review, cache write, or model
    change.
    """

    rows: list[dict] = []
    for index, card in enumerate(briefing_cards.get("cards", []), start=1):
        command = card.get("copyable_command", "")
        rows.append(
            {
                "rank": index,
                "card_id": card.get("id"),
                "title": card.get("title"),
                "copyable_command": command,
                "operator_question": card.get("operator_question"),
                "handoff_note": (
                    "STOP-Gate: erst dokumentiertes menschliches Go außerhalb dieses Sheets, dann separaten PR planen."
                    if card.get("is_stop_gate")
                    else "Status/Evidenz öffnen und Ergebnis in der Entscheidungsvorlage referenzieren; keine Ausführung."
                ),
                "is_stop_gate": bool(card.get("is_stop_gate")),
                "guardrail": card.get("guardrail"),
            }
        )

    return {
        "title": "Registry-Operator-Handoff-Sheet",
        "plain_language_note": (
            "Ein kopierbares Übergabeblatt für die letzten Registry-Gates: erst Status lesen, "
            "dann Parameter prüfen, Entscheidung auditieren und vor Codearbeit stoppen."
        ),
        "primary_parameter_key": briefing_cards.get("primary_parameter_key"),
        "primary_label": briefing_cards.get("primary_label"),
        "rows": rows,
        "operator_definition_of_done": [
            "Alle Statusrouten aus dem Sheet wurden gelesen",
            "Parameter-Workflow, Diff-Preview, PR-Brief und Entscheidungs-Template sind referenziert",
            "Go/Hold/Reject ist außerhalb dieses read-only Sheets mit Rationale, Entscheider und Zeitpunkt dokumentiert",
            "Branch/PR erst in einem separaten, getesteten Integrationsschritt nach dokumentiertem Go",
        ],
        "guardrail": "Read-only/Handoff-sheet-only: kein Branch, kein execute=true, kein Netzwerkabruf, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }



def _stable_read_only_packet_hash(packet: dict) -> str:
    """Return a deterministic SHA256 for read-only operator handoff packets."""

    canonical = json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256(canonical).hexdigest()


def build_data_readiness_registry_integration_operator_export_packet(
    operator_briefing: dict,
    briefing_cards: dict,
    handoff_sheet: dict,
) -> dict:
    """Return a copy-safe export packet for the final Registry operator workflow.

    The briefing, cards, and handoff sheet are useful in different UI/API contexts;
    this packet bundles their read-only routes and stop conditions so a future
    operator can copy one structured object into an issue, PR description draft, or
    handoff note without accidentally executing connectors or changing Registry
    defaults. It deliberately contains no execute=true, branch, PR, cache-write, or
    model-mutation command.
    """

    evidence_routes = [
        row.get("copyable_command", "")
        for row in handoff_sheet.get("rows", [])
        if row.get("copyable_command", "").startswith("GET ")
    ]
    stop_rows = [row for row in handoff_sheet.get("rows", []) if row.get("is_stop_gate")]
    return {
        "title": "Registry-Operator-Exportpaket ohne Ausführung",
        "plain_language_note": (
            "Ein kompaktes Paket zum Weitergeben: Startbefehl, Parameterroute, "
            "Entscheidungsroute, Stop-Gate und Definition of Done. Es ist nur ein "
            "Status-/Handoff-Paket und führt nichts aus."
        ),
        "primary_parameter_key": operator_briefing.get("primary_parameter_key"),
        "primary_label": operator_briefing.get("primary_label"),
        "copyable_summary": (
            f"Status lesen → {operator_briefing.get('primary_label') or 'Parameter'} prüfen → "
            "Go/Hold/Reject auditieren → vor Branch/PR stoppen."
        ),
        "safe_routes_to_open": evidence_routes,
        "stop_condition": stop_rows[0].get("handoff_note") if stop_rows else "STOP: erst dokumentiertes menschliches Go außerhalb dieses Pakets.",
        "operator_questions": operator_briefing.get("operator_questions", []),
        "cards_available": len(briefing_cards.get("cards", [])),
        "definition_of_done_before_branch": handoff_sheet.get("operator_definition_of_done", []),
        "guardrail": "Read-only/Export-packet-only: kein Branch, kein execute=true, kein Netzwerkabruf, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_operator_export_audit(export_packet: dict) -> dict:
    """Audit an operator export packet for copy-safety before handoff.

    This is a deterministic, read-only verification layer for future operators and
    agents: it records a stable packet hash, counts copied routes, and flags unsafe
    command fragments. It does not execute routes, create branches, or write any
    model/Registry state.
    """

    routes = list(export_packet.get("safe_routes_to_open", []))
    text_fragments = [
        export_packet.get("copyable_summary", ""),
        export_packet.get("stop_condition", ""),
        *routes,
    ]
    unsafe_tokens = ["execute=true", "POST ", "git checkout -b", "git commit", "git push"]
    unsafe_findings = [
        token
        for token in unsafe_tokens
        if any(token in fragment for fragment in text_fragments)
    ]
    return {
        "title": "Registry-Operator-Export-Audit",
        "plain_language_note": (
            "Dieses Audit macht das Exportpaket prüfbar: stabiler SHA256, Anzahl "
            "der reinen Statusrouten, Stop-Gate und Warnung, falls ein Ausführungs-"
            " oder Git-Befehl im Paket auftaucht."
        ),
        "packet_sha256": _stable_read_only_packet_hash(export_packet),
        "safe_route_count": len(routes),
        "all_routes_are_get": all(route.startswith("GET ") for route in routes),
        "unsafe_findings": unsafe_findings,
        "copy_safe": bool(routes) and all(route.startswith("GET ") for route in routes) and not unsafe_findings,
        "stop_condition": export_packet.get("stop_condition", ""),
        "definition_of_done_before_branch": export_packet.get("definition_of_done_before_branch", []),
        "guardrail": "Read-only/Export-Audit-only: kein Branch, kein execute=true, kein Netzwerkabruf, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
    }


def build_data_readiness_registry_integration_handoff_packet(decision_record: dict) -> dict:
    """Create a copy-safe operator handoff from the Go/Hold/Reject decision record.

    This is still deliberately read-only: it tells a human/integrator what to open,
    what decision options exist, and what must be true before a separate PR starts.
    It never creates a branch, writes reviews, fetches data, or mutates Registry/model
    defaults.
    """

    rows: list[dict] = []
    for idx, row in enumerate(decision_record.get("rows", []), start=1):
        parameter_key = row["parameter_key"]
        checks = row.get("checks", {})
        missing_checks = [
            label
            for key, label in [
                ("reviewed_value_present", "Review-Wert fehlt"),
                ("source_snapshot_sha256_present", "SHA256/Manifest fehlt"),
                ("unit_matches_registry", "Einheit passt nicht/ungeprüft"),
                ("within_registry_bounds", "Registry-Grenzen nicht erfüllt/ungeprüft"),
                ("pr_brief_available", "PR-Brief fehlt"),
            ]
            if checks.get(key) is not True
        ]
        rows.append({
            "rank": idx,
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "status": row.get("status", "blocked_before_human_go_no_go"),
            "first_safe_step": "Decision-Record lesen und Go/Hold/Reject dokumentieren",
            "copyable_status_command": f"GET /data-readiness/{parameter_key}",
            "copyable_decision_route": "GET /data-readiness/registry-integration-decision-record",
            "branch_name_if_go": row.get("branch_name_if_go"),
            "missing_checks_before_go": missing_checks,
            "recommended_default": row.get("recommended_default", "Hold, bis alle Checks vollständig sind."),
            "safe_options": row.get("safe_options", []),
            "definition_of_done_before_branch": [
                "Go/Hold/Reject wurde mit Begründung festgehalten",
                "Raw-Snapshot-SHA256/Manifest und Transformationsreview sind nachvollziehbar",
                "Einheit, Berichtsjahr, Nenner/Methode und Registry-Grenzen wurden geprüft",
                "Separater PR enthält Tests, UI/API-Labelchecks und Guardrails",
            ],
            "guardrail": "Handoff-Packet ist read-only: kein Branch, kein execute=true, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Registry-Integrations-Handoff für Go/Hold/Reject",
        "plain_language_note": (
            "Dieses Packet macht den letzten menschlichen Entscheidungsschritt copybar: Status öffnen, "
            "Go/Hold/Reject begründen, und erst danach ggf. einen separaten PR beginnen."
        ),
        "summary": {
            "decision_rows_seen": len(decision_record.get("rows", [])),
            "handoff_rows": len(rows),
            "blocked_or_hold_default": sum(1 for row in rows if row["missing_checks_before_go"]),
        },
        "rows": rows,
        "guardrail": "Read-only/Handoff-only: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }



def build_data_readiness_registry_integration_decision_record(
    registry_diff_preview: dict,
    integration_pr_brief: dict,
) -> dict:
    """Summarize the final human go/no-go decision before any Registry PR.

    The diff preview and PR brief already contain the detailed technical checks.
    This helper turns them into a short, auditable decision record so operators
    and future agents know exactly what must be decided before code is touched.
    It remains read-only and never changes Registry/model values.
    """

    briefs_by_key = {
        brief["parameter_key"]: brief
        for brief in integration_pr_brief.get("briefs", [])
    }
    rows: list[dict] = []
    for row in registry_diff_preview.get("rows", []):
        parameter_key = row["parameter_key"]
        brief = briefs_by_key.get(parameter_key, {})
        unit_matches = row.get("unit_check", {}).get("unit_matches") is True
        within_bounds = row.get("plausibility_check", {}).get("within_registry_bounds") is True
        has_reviewed_value = row.get("reviewed_output_value") is not None
        has_sha = bool(row.get("source_snapshot_sha256"))
        ready_for_human_go_no_go = all([unit_matches, within_bounds, has_reviewed_value, has_sha, brief])
        rows.append({
            "parameter_key": parameter_key,
            "label": row.get("label", parameter_key),
            "status": "human_go_no_go_required_before_pr" if ready_for_human_go_no_go else "blocked_before_human_go_no_go",
            "decision_question": "Soll dieser geprüfte Transformationswert in einem separaten Registry-/Modell-PR vorbereitet werden?",
            "checks": {
                "reviewed_value_present": has_reviewed_value,
                "source_snapshot_sha256_present": has_sha,
                "unit_matches_registry": unit_matches,
                "within_registry_bounds": within_bounds,
                "pr_brief_available": bool(brief),
            },
            "safe_options": [
                "Go: separaten PR gemäß PR-Brief vorbereiten, Tests/Smoke ausführen, Guardrails im PR-Text behalten",
                "Hold: zusätzliche Quellen-/Methodenprüfung verlangen, kein PR und keine Wertänderung",
                "Reject: Review als nicht integrationsreif markieren und neues Transformationsreview planen",
            ],
            "recommended_default": "Hold, falls irgendein Check fehlt; Go nur bei vollständigem Review, SHA256/Manifest, Einheit, Grenzen und PR-Brief.",
            "branch_name_if_go": brief.get("branch_name"),
            "required_human_decision": row.get("required_human_decision"),
            "guardrail": "Decision-Record ist read-only: kein Branch, kein execute=true, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Registry-Integrationsentscheidung (Go/Hold/Reject)",
        "plain_language_note": (
            "Diese Liste ist der letzte Entscheidungszettel vor einem separaten PR. "
            "Sie sagt, ob Go/Hold/Reject fachlich geklärt werden muss, ändert aber nichts im Modell."
        ),
        "summary": {
            "diff_rows_seen": len(registry_diff_preview.get("rows", [])),
            "decision_rows": len(rows),
            "ready_for_human_go_no_go": sum(1 for row in rows if row["status"] == "human_go_no_go_required_before_pr"),
        },
        "rows": rows,
        "guardrail": "Read-only/Entscheidungsvorbereitung: kein Branch, kein execute=true, keine Datenaktion, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }



def build_data_readiness_integration_pr_brief(integration_plan: dict) -> dict:
    """Turn read-only integration plans into a conservative PR handoff.

    This is the final planning layer before a human/integrator opens a real code
    change. It deliberately uses only already-green integration-plan rows, keeps
    the action as branch/PR preparation, and repeats the separation between
    reviewed data, Registry/model defaults, and policy-effect interpretation.
    """

    plans = integration_plan.get("plans", [])
    briefs: list[dict] = []
    for plan in plans:
        parameter_key = plan["parameter_key"]
        briefs.append({
            "parameter_key": parameter_key,
            "label": plan["label"],
            "status": "pr_brief_bereit_aber_nicht_ausgefuehrt",
            "branch_name": f"feat/integrate-reviewed-{parameter_key}",
            "pr_title": f"Integrate reviewed data value for {plan['label']}",
            "first_commit_scope": [
                "Registry-Default/Metadaten nur mit ReviewedTransformation und SHA256-Bezug ändern",
                "UI/API-Labels prüfen: Rohdaten-Cache, Review und Modelleffekt bleiben getrennt",
                "keine Simulationseffekte ändern, außer der dokumentierte Modellpfad nutzt den Parameter bereits explizit",
            ],
            "review_checklist": [
                "Quelle/Manifest/SHA256 im PR-Text verlinken",
                "Reviewer, Methode, Einheit, Nenner, Berichtsjahr und Caveat aus ReviewedTransformation zitieren",
                "alte vs. neue Registry-Grenzen/Defaults und Unsicherheit begründen",
                "Tests für Registry, Data Passport, API/UI-Labeltrennung und ggf. Simulation-Smoke ausführen",
                "klar sagen: integrierter Datenwert ist keine amtliche Prognose und kein Policy-Wirkungsbeweis",
            ],
            "copyable_pr_body_outline": [
                f"Parameter: {plan['label']} ({parameter_key})",
                f"Workflow: {plan.get('workflow_api')}",
                f"Review-Template: {plan.get('review_template_api')}",
                "Geprüfte Inputs: Rohsnapshot-SHA256, ReviewedTransformation, Einheit/Nenner/Jahr, Caveat",
                "Tests: Registry/Data-Passport/API/UI-Labeltrennung + Simulation-Smoke falls Modellpfad betroffen",
                "Guardrail: keine automatische Datenaktion, keine amtliche Prognose, kein Wirkungsbeweis",
            ],
            "definition_of_done_before_merge": plan.get("definition_of_done", []) + [
                "PR beschreibt verbleibende Annahmen/Caveats in Alltagssprache",
                "Git-Historie trennt Datenintegration klar von späteren Policy-/Szenarioeffekten",
            ],
            "guardrail": "PR-Brief ist Planung-only: kein Branch wird erstellt, kein Code geändert, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        })
    return {
        "title": "Integrations-PR-Brief (nur für grüne Preflight-Pläne)",
        "plain_language_note": (
            "Dieser Handoff sagt, wie ein separater Datenintegrations-PR aussehen soll. "
            "Er startet keinen Branch und ändert keine Werte."
        ),
        "summary": {
            "plan_rows_seen": len(plans),
            "shown_pr_briefs": len(briefs),
        },
        "briefs": briefs,
        "guardrail": "Read-only/Planung-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
    }



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
