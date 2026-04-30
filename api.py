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
    build_data_readiness_action_packet,
    build_data_readiness_backlog,
    build_data_readiness_dashboard_cards,
    build_data_readiness_first_contact_guide,
    build_data_readiness_integration_preflight,
    build_data_readiness_integration_plan,
    build_data_readiness_integration_pr_brief,
    build_data_readiness_operator_handoff,
    build_data_readiness_registry_diff_preview,
    build_data_readiness_platform_brief,
    build_data_readiness_registry_integration_decision_record,
    build_data_readiness_registry_integration_handoff_packet,
    build_data_readiness_gate_plan,
    build_data_readiness_summary,
    build_next_data_readiness_actions,
    build_parameter_data_workflow_card,
    build_parameter_snapshot_status,
    build_transformation_review_template,
    execute_connector_snapshot_request,
    list_cached_snapshots,
    list_reviewed_transformations,
    seed_reference_fixture_reviewed_transformations,
    seed_reference_fixture_snapshots,
)
from data_sources import list_sources
from parameter_registry import list_parameters
from political_feasibility import assess_political_feasibility
from scenario_gallery import build_scenario_gallery_guided_apply_plan
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


@api.get("/data-readiness/next-actions")
def get_next_data_readiness_actions(limit: int = 3) -> dict:
    """Return the next concrete platform data-foundation actions.

    This endpoint is operator/agent guidance only: it points to dry-run/status
    APIs and parameter workflow cards, but does not execute connectors, cache
    payloads, review transformations, or integrate model values.
    """

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_next_actions_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Datenaktion wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    actions = build_next_data_readiness_actions(items, limit=limit)
    return {
        "status": "data_readiness_next_actions_not_executed",
        "guardrail": "Nächste Aktionen sind Dry-run-/Workflow-Hinweise: kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "actions": actions,
        "action_packet": build_data_readiness_action_packet(actions),
        "operator_handoff": build_data_readiness_operator_handoff(actions),
        "platform_brief": build_data_readiness_platform_brief(actions),
    }


@api.get("/data-readiness/operator-handoff")
def get_data_readiness_operator_handoff(limit: int = 3) -> dict:
    """Return a focused safe handoff for the next platform data cycle."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_operator_handoff_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Datenaktion wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    actions = build_next_data_readiness_actions(items, limit=limit)
    return {
        "status": "data_readiness_operator_handoff_not_executed",
        "guardrail": "Operator-Handoff ist Status/Dry-run-only: kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "actions": actions,
        "operator_handoff": build_data_readiness_operator_handoff(actions),
        "platform_brief": build_data_readiness_platform_brief(actions),
    }


@api.get("/data-readiness/platform-brief")
def get_data_readiness_platform_brief(limit: int = 3) -> dict:
    """Return the next safe core-platform data brief for cron/operators."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_platform_brief_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Datenaktion wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    actions = build_next_data_readiness_actions(items, limit=limit)
    summary = build_data_readiness_summary(items)
    return {
        "status": "data_readiness_platform_brief_not_executed",
        "guardrail": "Plattform-Brief ist read-only: kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": summary,
        "dashboard_cards": build_data_readiness_dashboard_cards(summary, actions),
        "first_contact_guide": build_data_readiness_first_contact_guide(summary, actions),
        "platform_brief": build_data_readiness_platform_brief(actions),
    }


@api.get("/data-readiness/integration-preflight")
def get_data_readiness_integration_preflight(limit: int = 5) -> dict:
    """Return the safe preflight before any data-backed model integration PR."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_integration_preflight_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Datenaktion wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    return {
        "status": "data_readiness_integration_preflight_not_executed",
        "guardrail": "Integrations-Preflight ist Status/Planung-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "integration_preflight": (preflight := build_data_readiness_integration_preflight(items, passport_rows, limit=limit)),
        "integration_plan": (plan := build_data_readiness_integration_plan(preflight)),
        "registry_diff_preview": (preview := build_data_readiness_registry_diff_preview(plan, parameters)),
        "integration_pr_brief": (brief := build_data_readiness_integration_pr_brief(plan)),
        "registry_integration_decision_record": build_data_readiness_registry_integration_decision_record(preview, brief),
    }


@api.get("/data-readiness/integration-plan")
def get_data_readiness_integration_plan(limit: int = 3) -> dict:
    """Return read-only parameter-specific integration plans for preflight-ready rows."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_integration_plan_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Integration wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    preflight = build_data_readiness_integration_preflight(items, passport_rows, limit=10)
    return {
        "status": "data_readiness_integration_plan_not_executed",
        "guardrail": "Integrationspläne sind read-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreiben, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "integration_preflight": preflight,
        "integration_plan": (plan := build_data_readiness_integration_plan(preflight, limit=limit)),
        "registry_diff_preview": (preview := build_data_readiness_registry_diff_preview(plan, parameters)),
        "integration_pr_brief": (brief := build_data_readiness_integration_pr_brief(plan)),
        "registry_integration_decision_record": build_data_readiness_registry_integration_decision_record(preview, brief),
    }


@api.get("/data-readiness/integration-pr-brief")
def get_data_readiness_integration_pr_brief(limit: int = 3) -> dict:
    """Return a read-only PR handoff for reviewed data integration candidates."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_integration_pr_brief_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; kein PR/Branch und keine Integration wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    preflight = build_data_readiness_integration_preflight(items, passport_rows, limit=10)
    plan = build_data_readiness_integration_plan(preflight, limit=limit)
    return {
        "status": "data_readiness_integration_pr_brief_not_executed",
        "guardrail": "PR-Brief ist read-only: kein Branch, kein execute=true, kein Netzwerkabruf, keine Cache-/Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "integration_plan": plan,
        "integration_pr_brief": build_data_readiness_integration_pr_brief(plan),
    }


@api.get("/data-readiness/registry-diff-preview")
def get_data_readiness_registry_diff_preview(limit: int = 3) -> dict:
    """Return a read-only diff preview between reviewed values and current Registry defaults."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_registry_diff_preview_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Registry-/Modelländerung wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    preflight = build_data_readiness_integration_preflight(items, passport_rows, limit=10)
    plan = build_data_readiness_integration_plan(preflight, limit=limit)
    return {
        "status": "data_readiness_registry_diff_preview_not_applied",
        "guardrail": "Registry-Diff-Preview ist read-only: kein Branch, kein execute=true, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "integration_plan": plan,
        "registry_diff_preview": (preview := build_data_readiness_registry_diff_preview(plan, parameters)),
        "integration_pr_brief": (brief := build_data_readiness_integration_pr_brief(plan)),
        "registry_integration_decision_record": build_data_readiness_registry_integration_decision_record(preview, brief),
    }


@api.get("/data-readiness/dashboard-cards")
def get_data_readiness_dashboard_cards(limit: int = 3) -> dict:
    """Return mobile-safe data-readiness cockpit cards without executing work."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_dashboard_cards_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Datenaktion wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    actions = build_next_data_readiness_actions(items, limit=limit)
    summary = build_data_readiness_summary(items)
    return {
        "status": "data_readiness_dashboard_cards_not_executed",
        "guardrail": "Daten-Reife-Cockpit ist Status/Navigation-only: kein execute=true, kein Netzwerkabruf, kein Cache-Schreibvorgang, keine Review-Erzeugung, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": summary,
        "dashboard_cards": build_data_readiness_dashboard_cards(summary, actions),
        "first_contact_guide": build_data_readiness_first_contact_guide(summary, actions),
    }


@api.get("/data-readiness/registry-integration-decision-record")
def get_data_readiness_registry_integration_decision_record(limit: int = 3) -> dict:
    """Return the final read-only Go/Hold/Reject decision sheet before a Registry PR."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_registry_integration_decision_record_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; keine Registry-/Modelländerung wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    preflight = build_data_readiness_integration_preflight(items, passport_rows, limit=10)
    plan = build_data_readiness_integration_plan(preflight, limit=limit)
    preview = build_data_readiness_registry_diff_preview(plan, parameters)
    brief = build_data_readiness_integration_pr_brief(plan)
    decision_record = build_data_readiness_registry_integration_decision_record(preview, brief)
    return {
        "status": "data_readiness_registry_integration_decision_record_not_applied",
        "guardrail": "Decision-Record ist read-only: kein Branch, kein execute=true, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "registry_diff_preview": preview,
        "integration_pr_brief": brief,
        "registry_integration_decision_record": decision_record,
        "registry_integration_handoff_packet": build_data_readiness_registry_integration_handoff_packet(decision_record),
    }


@api.get("/data-readiness/registry-integration-handoff")
def get_data_readiness_registry_integration_handoff(limit: int = 3) -> dict:
    """Return the focused read-only handoff packet before any Registry branch work."""

    if limit < 1 or limit > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_data_readiness_registry_integration_handoff_limit",
                "limit": limit,
                "guardrail": "Limit muss zwischen 1 und 10 liegen; kein Branch und keine Registry-/Modelländerung wurde ausgeführt.",
            },
        )
    parameters = list_parameters()
    items = build_data_readiness_backlog(parameters)
    passport_rows = build_data_passport_rows(parameters)
    preflight = build_data_readiness_integration_preflight(items, passport_rows, limit=10)
    plan = build_data_readiness_integration_plan(preflight, limit=limit)
    preview = build_data_readiness_registry_diff_preview(plan, parameters)
    brief = build_data_readiness_integration_pr_brief(plan)
    decision_record = build_data_readiness_registry_integration_decision_record(preview, brief)
    return {
        "status": "data_readiness_registry_integration_handoff_not_applied",
        "guardrail": "Handoff ist read-only/status-only: kein Branch, kein execute=true, kein Netzwerkabruf, kein Cache-/Review-Schreiben, keine Registry-/Modellmutation und kein Wirkungsbeweis.",
        "summary": build_data_readiness_summary(items),
        "registry_integration_handoff_packet": build_data_readiness_registry_integration_handoff_packet(decision_record),
    }


@api.get("/data-readiness/{parameter_key}")
def get_parameter_data_readiness(parameter_key: str) -> dict:
    """Return the complete safe data workflow for one parameter.

    This parameter-level endpoint helps UI/agents answer: registry or assumption,
    raw cache status, next backlog gate, dry-run connector plan if available, and
    review checklist. It remains read-only and performs no network/cache/model work.
    """

    parameters = list_parameters()
    try:
        return build_parameter_data_workflow_card(parameter_key, parameters)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unknown_parameter_data_workflow",
                "parameter_key": parameter_key,
                "guardrail": "Unbekannter Parameter: kein Datenworkflow, kein Netzwerkabruf und keine Modellintegration.",
            },
        )


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


@api.post("/data-fixtures/seed-reference-review-demo")
def seed_data_fixture_review_demo() -> dict:
    """Seed a reviewed-model-ready fixture so the integration planning chain has a green demo row.

    This is still a fixture/dev action: it writes a ReviewedTransformation record
    tied to the static population fixture only. It does not fetch live data, change
    Registry/model defaults, create a branch/PR, or prove a policy effect.
    """

    reviews = seed_reference_fixture_reviewed_transformations()
    parameters = list_parameters()
    passport = build_data_passport_rows(parameters)
    backlog = build_data_readiness_backlog(parameters)
    preflight = build_data_readiness_integration_preflight(backlog, passport)
    integration_plan = build_data_readiness_integration_plan(preflight)
    return {
        "status": "reference_fixture_review_demo_seeded_not_model_integration",
        "guardrail": "Demo-Review ist nur ein Fixture für Preflight/Integrationsplan/PR-Brief: kein Live-Destatis-Import, keine Registry-/Modellmutation, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        "seeded_reviews": [review.to_dict() for review in reviews],
        "data_passport": passport,
        "integration_preflight": preflight,
        "integration_plan": integration_plan,
        "integration_pr_brief": build_data_readiness_integration_pr_brief(integration_plan),
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


@api.get("/scenario-gallery/guided-apply-plans")
def get_scenario_gallery_guided_apply_plans(
    n_runs: int = 100,
    n_years: int = 15,
    seed: int = 42,
) -> dict:
    """Expose read-only starter scenario plans for agents/UI without applying them."""

    if not 1 <= n_runs <= 1000 or not 1 <= n_years <= 30 or not 0 <= seed <= 999999:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "invalid_scenario_gallery_plan_bounds",
                "guardrail": "Nur bounded Manifest-/Payload-Vorschauen; kein Apply, kein Simulationslauf und keine Modellmutation.",
            },
        )
    plans = build_scenario_gallery_guided_apply_plan(n_runs=n_runs, n_years=n_years, seed=seed)
    return {
        "status": "scenario_gallery_guided_apply_plans_not_executed",
        "guardrail": "Read-only: kein automatischer Apply-Button, keine Session-State-Mutation, kein Simulationslauf, keine amtliche Prognose und kein Policy-Wirkungsbeweis.",
        "plans": plans,
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
