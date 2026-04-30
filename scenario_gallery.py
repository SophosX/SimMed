"""Scenario-gallery starter workflows for SimMed.

The gallery is a safe, read-only bridge from newcomer-friendly example cards to
reproducible scenario manifests and API payloads. It must never mutate Streamlit
session state, run a simulation, change registry/model values, or present a card
as an official forecast or proof of policy effectiveness.
"""

from __future__ import annotations

from typing import Any

from parameter_registry import PARAMETER_REGISTRY
from simulation_core import build_scenario_manifest


SCENARIO_GALLERY_WORKFLOW = [
    "Ausgangslage verstehen",
    "Reform auswählen",
    "Annahmen prüfen",
    "Simulation laufen lassen",
    "Policy-Briefing lesen",
]


def build_scenario_gallery_cards() -> list[dict[str, Any]]:
    """Return evidence-guarded starter scenarios for a guided first run."""

    return [
        {
            "id": "medical_training_pipeline",
            "title": "Medizinstudienplätze: verzögerte Pipeline testen",
            "question": "Was passiert, wenn heute weniger oder mehr Studienplätze beschlossen werden?",
            "parameter_changes": {"medizinstudienplaetze": {"suggested_value": 9000, "direction": "senken"}},
            "why_this_matters": "Der Effekt darf nicht sofort als Facharztkapazität erscheinen; wichtig ist das 6+/11–13-Jahre-Zeitfenster.",
            "workflow": SCENARIO_GALLERY_WORKFLOW,
            "guardrail": "Starterkarte, keine amtliche Prognose und nicht automatisch ein Nachweis für Versorgungseffekte.",
            "next_click": "Nach der Simulation: Ergebnis-Storyboard → KPI-Detail Ärzte/Facharzt-Wartezeit → Annahmen-Check.",
        },
        {
            "id": "digital_access_relief",
            "title": "Telemedizin: Zugang entlasten, Evidenz prüfen",
            "question": "Kann ein höherer Telemedizin-Anteil Wartezeiten senken, ohne ländliche Versorgung zu überschätzen?",
            "parameter_changes": {"telemedizin_rate": {"suggested_value": 0.25, "direction": "erhöhen"}},
            "why_this_matters": "Digitalisierung ist im Modell ein Szenariohebel mit Adoptions- und Umsetzungsunsicherheit, kein pauschaler Kostensenker.",
            "workflow": SCENARIO_GALLERY_WORKFLOW,
            "guardrail": "Starterkarte, keine amtliche Prognose; Telemedizin-Effekte sind nicht automatisch Patientennutzen oder Einsparungen.",
            "next_click": "Nach der Simulation: geänderte Hebel als Fragen lesen → Facharzt-Wartezeit → Evidenz/Annahmen.",
        },
        {
            "id": "prevention_finance_tradeoff",
            "title": "Prävention: spätere Wirkung gegen kurzfristige Kosten abwägen",
            "question": "Wie verändert mehr Präventionsbudget den Zielkonflikt zwischen Gesundheit und GKV-Finanzen?",
            "parameter_changes": {"praeventionsbudget": {"suggested_value": 10.0, "direction": "erhöhen"}},
            "why_this_matters": "Prävention kann verzögert wirken und kurzfristig Ausgaben erhöhen; die Karte erzwingt deshalb Ergebnis- und Annahmenprüfung.",
            "workflow": SCENARIO_GALLERY_WORKFLOW,
            "guardrail": "Starterkarte, keine amtliche Prognose und kein Beweis für sofortige Einsparungen.",
            "next_click": "Nach der Simulation: GKV-Saldo/BIP-Anteil → Trend-Timing → Annahmen-Check.",
        },
    ]


def build_scenario_gallery_manifest_previews(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> list[dict[str, Any]]:
    """Attach reproducible manifest previews to starter cards without applying them."""

    previews: list[dict[str, Any]] = []
    for card in build_scenario_gallery_cards():
        parameter_changes = {
            key: change["suggested_value"]
            for key, change in card["parameter_changes"].items()
        }
        manifest = build_scenario_manifest(
            parameter_changes,
            n_runs=n_runs,
            n_years=n_years,
            seed=seed,
            generated_at="preview-not-executed",
        )
        previews.append({
            "card_id": card["id"],
            "title": card["title"],
            "scenario_id": manifest["scenario_id"],
            "parameter_changes": manifest["parameter_changes"],
            "changed_parameters": manifest["changed_parameters"],
            "api_endpoint": manifest["reproducibility"]["manifest_endpoint"],
            "simulate_endpoint": manifest["reproducibility"]["api_endpoint"],
            "guardrail": (
                "Manifest-Vorschau: reproduzierbar und API-fähig, aber noch kein Apply-Button, "
                "kein Simulationslauf, keine amtliche Prognose und kein Wirksamkeitsnachweis."
            ),
        })
    return previews


def build_scenario_gallery_guided_apply_plan(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> list[dict[str, Any]]:
    """Return copy-ready, read-only next steps from starter card to manual scenario."""

    previews = {
        item["card_id"]: item
        for item in build_scenario_gallery_manifest_previews(n_runs=n_runs, n_years=n_years, seed=seed)
    }
    plans: list[dict[str, Any]] = []
    for card in build_scenario_gallery_cards():
        preview = previews[card["id"]]
        sidebar_steps = []
        for parameter in preview["changed_parameters"]:
            spec = PARAMETER_REGISTRY.get(parameter["key"])
            label = parameter.get("label") or (spec.label if spec else parameter["key"])
            direction = card["parameter_changes"][parameter["key"]].get("direction", "setzen")
            sidebar_steps.append({
                "parameter_key": parameter["key"],
                "label": label,
                "target_value": parameter["value"],
                "instruction": f"Sidebar-Regler '{label}' auf {parameter['value']} {direction}.",
                "evidence_grade": parameter.get("evidence_grade", "E"),
                "caveat": parameter.get("caveat") or (spec.caveat if spec else "Registry-Caveat prüfen."),
            })

        api_payload = {
            "parameter_changes": preview["parameter_changes"],
            "n_runs": n_runs,
            "n_years": n_years,
            "seed": seed,
        }
        plans.append({
            "card_id": card["id"],
            "title": card["title"],
            "scenario_id": preview["scenario_id"],
            "manual_sidebar_steps": sidebar_steps,
            "api_payload": api_payload,
            "copy_hint": "Werte manuell in der Sidebar setzen oder Payload an POST /simulate senden.",
            "reading_order": [
                "Simulation starten",
                "Ergebnis-Storyboard öffnen",
                "Geänderte Hebel als Fragen lesen",
                "KPI-Detailkarte und Annahmen-Check prüfen",
                "Policy-Briefing und politische Rubrik lesen",
            ],
            "guardrail": (
                "Guided-Apply-Plan: kein automatischer Apply-Button, keine Session-State-Mutation, "
                "kein Simulationslauf, keine amtliche Prognose, kein Wirksamkeitsnachweis und keine Lobbying-Empfehlung."
            ),
        })
    return plans


def build_scenario_gallery_operator_run_packets(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> list[dict[str, Any]]:
    """Return copy-safe run packets that bridge guided cards to deliberate execution.

    A packet is more concrete than a guided plan, but still read-only: it bundles
    the exact payload, pre-run checks, and post-run reading path for an operator or
    agent. It deliberately does not run the simulation, mutate Streamlit state, or
    claim official forecasts/effects.
    """

    packets: list[dict[str, Any]] = []
    for plan in build_scenario_gallery_guided_apply_plan(n_runs=n_runs, n_years=n_years, seed=seed):
        changed_labels = [step["label"] for step in plan["manual_sidebar_steps"]]
        evidence_checks = [
            {
                "parameter_key": step["parameter_key"],
                "label": step["label"],
                "evidence_grade": step["evidence_grade"],
                "check": "Registry-Evidenzgrad und Caveat vor dem Lauf lesen; Ergebnis nicht als Wirkungsbeweis behandeln.",
                "caveat": step["caveat"],
            }
            for step in plan["manual_sidebar_steps"]
        ]
        packets.append({
            "card_id": plan["card_id"],
            "title": plan["title"],
            "scenario_id": plan["scenario_id"],
            "status": "run_packet_ready_but_not_executed",
            "changed_parameters_plain": ", ".join(changed_labels),
            "pre_run_checklist": [
                "Parameteränderungen bewusst prüfen; nichts wird automatisch angewendet.",
                "Evidenzgrad/Caveat je geändertem Parameter lesen.",
                "n_runs/n_years/seed als Reproduzierbarkeitsangaben notieren.",
                "Nach dem Lauf zuerst Storyboard, KPI-Details, Annahmen-Check und Policy-Briefing lesen.",
            ],
            "evidence_checks": evidence_checks,
            "copyable_api_payload": plan["api_payload"],
            "copyable_api_route": "POST /simulate",
            "manifest_route": "POST /scenario-manifest",
            "post_run_reading_order": plan["reading_order"],
            "operator_stop_rule": "STOP: kein Ergebnis als amtliche Prognose, Wirksamkeitsnachweis, Lobbying-Empfehlung oder automatische Modellentscheidung verwenden.",
            "guardrail": (
                "Operator-Run-Packet: read-only Vorbereitung; kein automatischer Apply-Button, "
                "keine Session-State-Mutation, kein Simulationslauf, keine Registry-/Modellmutation, "
                "keine amtliche Prognose, kein Wirksamkeitsnachweis und keine Lobbying-Empfehlung."
            ),
        })
    return packets
