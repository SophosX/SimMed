"""Minimal agent-facing API for SimMed.

This wraps the existing simulation functions without changing the Streamlit app.
Agents can inspect provenance and run bounded scenarios.  In production this
should add auth, rate limits, persistent scenario manifests and model-versioning.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from data_ingestion import (
    build_connector_execution_plan,
    build_connector_execution_workbench,
    build_connector_snapshot_requests,
    build_data_connector_queue,
    build_data_passport_rows,
    build_data_readiness_backlog,
    build_data_readiness_gate_plan,
    build_data_readiness_summary,
    build_parameter_snapshot_status,
    build_transformation_review_template,
    execute_connector_snapshot_request,
    list_cached_snapshots,
    list_reviewed_transformations,
    seed_reference_fixture_snapshots,
)
from data_sources import list_sources
from parameter_registry import list_parameters
from political_feasibility import assess_political_feasibility
from simulation_core import MODEL_VERSION, build_scenario_manifest, get_default_params, run_scenario

api = FastAPI(title="SimMed Deutschland 2040 API", version="0.2.0")


class ScenarioRequest(BaseModel):
    parameter_changes: dict[str, Any] = Field(default_factory=dict)
    n_runs: int = Field(default=100, ge=1, le=1000)
    n_years: int = Field(default=15, ge=1, le=30)
    seed: int = Field(default=42, ge=0, le=999999)


class ConnectorExecutionRequest(BaseModel):
    parameter_key: str = Field(description="Registry parameter key with a planned connector request")
    execute: bool = Field(
        default=False,
        description="False returns the safe planned request only; True fetches and caches raw bytes without model integration.",
    )


@api.get("/sources")
def get_sources() -> list[dict]:
    return list_sources()


@api.get("/parameters")
def get_parameters() -> list[dict]:
    return list_parameters()


@api.get("/data-snapshots")
def get_data_snapshots() -> dict:
    """Expose raw-source cache status without treating snapshots as model truth."""

    parameters = list_parameters()
    parameter_keys = [p["key"] for p in parameters]
    return {
        "status": "raw_snapshot_status_not_model_integration",
        "guardrail": "Rohdaten-Snapshots zeigen Cache/Provenienz; Modellparameter ändern sich erst nach geprüfter Transformation.",
        "snapshots": [snapshot.to_dict() for snapshot in list_cached_snapshots()],
        "transformation_reviews": [review.to_dict() for review in list_reviewed_transformations()],
        "parameters": build_parameter_snapshot_status(parameter_keys),
        "data_passport": build_data_passport_rows(parameters),
    }


@api.get("/data-passport")
def get_data_passport() -> dict:
    """Expose registry status plus raw-cache status as a user-facing data passport."""

    parameters = list_parameters()
    return {
        "status": "registry_and_raw_cache_passport_not_model_integration",
        "guardrail": "'aus Daten' beschreibt den Registry-/Quellenstatus; Rohdaten-Cache und geprüfte Transformation bleiben getrennt sichtbar.",
        "parameters": build_data_passport_rows(parameters),
    }


@api.get("/data-readiness-backlog")
def get_data_readiness_backlog() -> dict:
    """Expose safe next data-foundation gates without mutating model values."""

    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    return {
        "status": "data_readiness_backlog_not_model_integration",
        "guardrail": "Diese Liste priorisiert Cache-/Review-/Integrationsarbeit; sie importiert keine Werte und beweist keine Policy-Wirkung.",
        "summary": build_data_readiness_summary(items),
        "gate_plan": build_data_readiness_gate_plan(items),
        "connector_queue": build_data_connector_queue(items),
        "connector_snapshot_requests": build_connector_snapshot_requests(items),
        "connector_execution_workbench": build_connector_execution_workbench(
            build_connector_snapshot_requests(items),
            build_data_passport_rows(parameters),
        ),
        "items": items,
    }


@api.post("/data-fixtures/seed-reference-snapshots")
def seed_data_fixture_snapshots() -> dict:
    """Seed local reference fixtures for data-passport demos without mutating model parameters.

    This is a deliberate development/onboarding action: it makes the raw-cache
    passport path visible through the API while preserving the guardrail that
    fixtures, raw snapshots and transformation reviews are not model imports.
    """

    snapshots = seed_reference_fixture_snapshots()
    parameters = list_parameters()
    return {
        "status": "reference_fixtures_seeded_not_model_integration",
        "guardrail": "Fixture-Snapshots dienen nur Cache/Provenienz- und UI-Tests; sie ändern keine SimMed-Modellparameter und sind kein Live-Destatis-Import.",
        "seeded_snapshots": [snapshot.to_dict() for snapshot in snapshots],
        "data_passport": build_data_passport_rows(parameters),
    }


@api.get("/data-connectors/transformation-review-template/{parameter_key}")
def get_transformation_review_template(parameter_key: str) -> dict:
    """Return the pre-model-integration review checklist for one planned connector.

    This endpoint is intentionally read-only. It lets agents/UI prepare a
    ReviewedTransformation entry after raw cache exists, but does not fetch,
    parse, review, or integrate any model value.
    """

    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    requests = build_connector_snapshot_requests(items, per_source_limit=100)
    planned = next(
        (item for item in requests if parameter_key in item.get("output_parameter_keys", [])),
        None,
    )
    if planned is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "no_planned_transformation_review_template",
                "parameter_key": parameter_key,
                "guardrail": "Review-Templates gibt es nur für unterstützte geplante Connector-Snapshot-Requests; keine Modellintegration wird vorbereitet.",
            },
        )

    passport_rows = build_data_passport_rows(parameters)
    passport_by_key = {row["parameter_key"]: row for row in passport_rows}
    return {
        "status": "transformation_review_template_not_model_integration",
        "guardrail": "Dieses Template ist nur eine Prüf-Checkliste: kein Netzwerkabruf, kein Datenwert, keine Registry- oder Modellmutation und kein Policy-Wirkungsbeweis.",
        "request": planned,
        "template": build_transformation_review_template(planned, passport_by_key.get(parameter_key)),
        "data_passport": passport_rows,
    }


@api.post("/data-connectors/execute-planned-snapshot")
def execute_planned_connector_snapshot(req: ConnectorExecutionRequest) -> dict:
    """Plan or execute one safe raw-snapshot cache action without model mutation.

    Default `execute=False` is a dry-run/status response for agents and UI: it
    identifies the exact request and next safe gate but performs no network call.
    Setting `execute=True` fetches the configured connector URL and caches raw
    bytes unchanged; parsing, transformation review and registry/model changes
    remain explicit later steps.
    """

    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    requests = build_connector_snapshot_requests(items, per_source_limit=100)
    planned = next(
        (item for item in requests if req.parameter_key in item.get("output_parameter_keys", [])),
        None,
    )
    if planned is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "no_planned_connector_snapshot_request",
                "parameter_key": req.parameter_key,
                "guardrail": "Nur unterstützte Snapshot-needed-Parameter mit expliziter Connector-Zuordnung können ausgeführt werden.",
            },
        )

    if not req.execute:
        passport_rows = build_data_passport_rows(parameters)
        passport_by_key = {row["parameter_key"]: row for row in passport_rows}
        parameter_key = planned["output_parameter_keys"][0]
        return {
            "status": "planned_snapshot_request_not_executed",
            "guardrail": "Dry-run: kein Netzwerkabruf, kein Rohdaten-Cache, keine Registry- oder Modellmutation.",
            "request": planned,
            "execution_plan": build_connector_execution_plan(planned, passport_by_key.get(parameter_key)),
            "next_safe_action": planned["next_safe_action"],
            "data_passport": passport_rows,
        }

    result = execute_connector_snapshot_request(planned)
    updated_parameters = list_parameters()
    return {
        **result,
        "request": planned,
        "data_passport": build_data_passport_rows(updated_parameters),
    }


@api.post("/scenario-manifest")
def scenario_manifest(req: ScenarioRequest) -> dict:
    try:
        return build_scenario_manifest(
            req.parameter_changes,
            n_runs=req.n_runs,
            n_years=req.n_years,
            seed=req.seed,
        )
    except ValueError as exc:
        unknown = sorted(set(req.parameter_changes) - set(get_default_params()))
        return {"error": "invalid_scenario", "unknown": unknown, "detail": str(exc)}


@api.post("/political-feasibility")
def political_feasibility(req: ScenarioRequest) -> dict:
    """Explain likely political implementation friction for changed levers."""
    return assess_political_feasibility(req.parameter_changes)


@api.post("/simulate")
def simulate(req: ScenarioRequest) -> dict:
    try:
        result = run_scenario(
            req.parameter_changes,
            n_runs=req.n_runs,
            n_years=req.n_years,
            seed=req.seed,
        )
    except ValueError as exc:
        unknown = sorted(set(req.parameter_changes) - set(get_default_params()))
        return {"error": "unknown_parameter", "unknown": unknown, "detail": str(exc)}
    result["model"] = MODEL_VERSION
    result["political_feasibility"] = assess_political_feasibility(req.parameter_changes)
    return result
