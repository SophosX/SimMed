"""Minimal agent-facing API for SimMed.

This wraps the existing simulation functions without changing the Streamlit app.
Agents can inspect provenance and run bounded scenarios.  In production this
should add auth, rate limits, persistent scenario manifests and model-versioning.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

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


@api.get("/sources")
def get_sources() -> list[dict]:
    return list_sources()


@api.get("/parameters")
def get_parameters() -> list[dict]:
    return list_parameters()


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
