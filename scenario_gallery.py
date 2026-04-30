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


def build_scenario_gallery_operator_status_cards(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> list[dict[str, Any]]:
    """Summarize scenario-gallery run packets as mobile-safe status cards.

    These cards make the deliberate-run bridge easier to scan on the landing
    page/API before any execution. They intentionally stay read-only and only
    point to existing payload/checklist/reading-path objects.
    """

    cards: list[dict[str, Any]] = []
    for packet in build_scenario_gallery_operator_run_packets(n_runs=n_runs, n_years=n_years, seed=seed):
        cards.append({
            "card_id": packet["card_id"],
            "title": packet["title"],
            "status_label": "Bereit zur bewussten Prüfung, nicht ausgeführt",
            "primary_action": f"Payload prüfen: {packet['copyable_api_route']}",
            "changed_parameters_plain": packet["changed_parameters_plain"],
            "first_safe_check": packet["pre_run_checklist"][0],
            "evidence_check_count": len(packet["evidence_checks"]),
            "post_run_first_read": packet["post_run_reading_order"][1],
            "stop_rule_short": "Kein Ergebnis als Prognose, Wirkungsbeweis, Lobbying-Empfehlung oder automatische Modellentscheidung verwenden.",
            "guardrail": (
                "Statuskarte ist read-only: kein Apply-Button, keine Session-State-Mutation, "
                "kein Simulationslauf, keine Registry-/Modellmutation und keine amtliche Prognose."
            ),
        })
    return cards


def build_scenario_gallery_run_readiness_summary(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> dict[str, Any]:
    """Return a first-contact readiness summary before any scenario-gallery run.

    This is the top-level safety layer for newcomers and agents: it explains
    what is ready, what still needs manual checking, and where to go next,
    without executing a simulation or mutating any parameter state.
    """

    status_cards = build_scenario_gallery_operator_status_cards(n_runs=n_runs, n_years=n_years, seed=seed)
    packets = build_scenario_gallery_operator_run_packets(n_runs=n_runs, n_years=n_years, seed=seed)
    evidence_checks = sum(len(packet["evidence_checks"]) for packet in packets)
    return {
        "status": "scenario_gallery_run_readiness_not_executed",
        "scenario_count": len(status_cards),
        "evidence_check_count": evidence_checks,
        "first_safe_step": "Starterkarte wählen und die Parameter-/Evidenzchecks lesen; nichts wird automatisch angewendet.",
        "operator_route": "GET /scenario-gallery/operator-run-packets",
        "status_card_route": "GET /scenario-gallery/operator-status-cards",
        "handoff_route": "GET /scenario-gallery/run-handoff-sheet",
        "ready_cards": [
            {
                "card_id": card["card_id"],
                "title": card["title"],
                "primary_action": card["primary_action"],
                "changed_parameters_plain": card["changed_parameters_plain"],
                "first_safe_check": card["first_safe_check"],
                "post_run_first_read": card["post_run_first_read"],
            }
            for card in status_cards
        ],
        "definition_of_done_before_run": [
            "Parameteränderungen wurden bewusst geprüft; kein automatischer Apply-Button wurde verwendet.",
            "Registry-Evidenzgrad und Caveat je geändertem Parameter wurden gelesen.",
            "n_runs, n_years und seed sind als Reproduzierbarkeitsangaben bekannt.",
            "Die Lesereihenfolge nach dem Lauf ist klar: Storyboard → KPI-Details → Annahmen-Check → Policy-Briefing.",
        ],
        "guardrail": (
            "Readiness-Summary ist read-only: kein Apply-Button, keine Session-State-Mutation, "
            "kein Simulationslauf, keine Registry-/Modellmutation, keine amtliche Prognose, "
            "kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung."
        ),
    }


def build_scenario_gallery_run_handoff_sheet(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> dict[str, Any]:
    """Return a compact operator handoff for deliberate starter-scenario runs.

    The handoff is designed for mobile/API consumers that need one copy-safe
    overview: what can be started, which status routes to open, which checks must
    happen before running, and where to read results afterwards. It remains
    planning-only and does not execute or apply scenario parameters.
    """

    readiness = build_scenario_gallery_run_readiness_summary(n_runs=n_runs, n_years=n_years, seed=seed)
    packets = build_scenario_gallery_operator_run_packets(n_runs=n_runs, n_years=n_years, seed=seed)
    starter_rows = [
        {
            "rank": index,
            "card_id": packet["card_id"],
            "title": packet["title"],
            "status": packet["status"],
            "changed_parameters_plain": packet["changed_parameters_plain"],
            "first_check": packet["pre_run_checklist"][0],
            "copyable_status_route": "GET /scenario-gallery/run-readiness",
            "copyable_payload_route": packet["copyable_api_route"],
            "post_run_first_read": packet["post_run_reading_order"][1],
            "stop_rule": packet["operator_stop_rule"],
        }
        for index, packet in enumerate(packets, start=1)
    ]
    return {
        "status": "scenario_gallery_run_handoff_not_executed",
        "title": "Scenario-Gallery Run-Handoff: bewusst starten, danach richtig lesen",
        "first_safe_step": readiness["first_safe_step"],
        "routes_to_open_before_run": [
            "GET /scenario-gallery/run-readiness",
            "GET /scenario-gallery/operator-status-cards",
            "GET /scenario-gallery/operator-run-packets",
        ],
        "starter_rows": starter_rows,
        "definition_of_done_before_run": readiness["definition_of_done_before_run"],
        "post_run_reading_order": [
            "Ergebnis-Storyboard öffnen",
            "KPI-Detailkarte für den stärksten Ausschlag lesen",
            "Geänderte Hebel als Fragen lesen",
            "Annahmen-/Evidenzcheck prüfen",
            "Policy-Briefing und politische Rubrik als qualitative Einordnung lesen",
        ],
        "guardrail": (
            "Run-Handoff ist read-only/status-only: kein Apply-Button, keine Session-State-Mutation, "
            "kein Simulationslauf, keine Registry-/Modellmutation, keine amtliche Prognose, "
            "kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung."
        ),
    }


def build_scenario_gallery_pre_run_audit(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> dict[str, Any]:
    """Return a final read-only audit before a starter scenario is executed.

    This is the last safe checkpoint between a newcomer-friendly gallery card and
    a deliberate simulation/API call. It makes hidden overclaim risks explicit,
    but still does not apply parameters, run the model, persist state, or create
    a forecast/effect claim.
    """

    handoff = build_scenario_gallery_run_handoff_sheet(n_runs=n_runs, n_years=n_years, seed=seed)
    packets = build_scenario_gallery_operator_run_packets(n_runs=n_runs, n_years=n_years, seed=seed)
    rows: list[dict[str, Any]] = []
    for packet in packets:
        rows.append({
            "card_id": packet["card_id"],
            "title": packet["title"],
            "audit_status": "bereit_zur_manuellen_pruefung_nicht_ausgefuehrt",
            "payload_route": packet["copyable_api_route"],
            "manifest_route": packet["manifest_route"],
            "changed_parameters_plain": packet["changed_parameters_plain"],
            "evidence_checks_required": len(packet["evidence_checks"]),
            "must_confirm_before_run": [
                packet["pre_run_checklist"][0],
                packet["pre_run_checklist"][1],
                "Ergebnis danach nur als SimMed-Szenario lesen: keine amtliche Prognose, kein Wirkungsbeweis.",
            ],
            "after_run_first_three_clicks": packet["post_run_reading_order"][:3],
            "stop_rule": packet["operator_stop_rule"],
        })
    return {
        "status": "scenario_gallery_pre_run_audit_not_executed",
        "title": "Scenario-Gallery Pre-Run-Audit: erst prüfen, dann bewusst simulieren",
        "first_safe_step": handoff["first_safe_step"],
        "rows": rows,
        "definition_of_done_before_run": handoff["definition_of_done_before_run"],
        "guardrail": (
            "Pre-Run-Audit ist read-only/status-only: kein Apply-Button, keine Session-State-Mutation, "
            "kein Simulationslauf, keine Registry-/Modellmutation, keine amtliche Prognose, "
            "kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung."
        ),
    }



def build_scenario_gallery_run_decision_brief(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> dict[str, Any]:
    """Return a copy-safe human decision brief before any gallery run.

    This is intentionally one step more explicit than the pre-run audit: it tells
    an operator what a safe "Run now" decision must mean, which evidence checks
    remain manual, and what must *not* be inferred after the simulation. It does
    not store a decision, execute a run, apply parameters, or mutate model state.
    """

    audit = build_scenario_gallery_pre_run_audit(n_runs=n_runs, n_years=n_years, seed=seed)
    rows: list[dict[str, Any]] = []
    for row in audit["rows"]:
        rows.append({
            "card_id": row["card_id"],
            "title": row["title"],
            "recommended_default": "Hold bis Parameter/Evidenz bewusst geprüft wurden",
            "allowed_decisions": ["Run", "Hold", "Reject/Rework"],
            "decision_fields_to_fill": [
                "decision",
                "decided_by",
                "decided_at",
                "why_this_scenario_now",
                "evidence_caveat_acknowledged",
                "post_run_reading_owner",
            ],
            "minimum_checks_before_run": row["must_confirm_before_run"],
            "copyable_payload_route_if_run": row["payload_route"],
            "copyable_manifest_route_if_run": row["manifest_route"],
            "post_run_first_three_clicks": row["after_run_first_three_clicks"],
            "stop_rule": row["stop_rule"],
        })
    return {
        "status": "scenario_gallery_run_decision_brief_not_executed",
        "title": "Scenario-Gallery Run-Entscheidung: Run/Hold/Reject vor dem Start dokumentieren",
        "recommended_default": "Hold, solange Evidenz-/Caveat-Checks nicht bewusst gelesen sind",
        "rows": rows,
        "definition_of_done_before_run": audit["definition_of_done_before_run"] + [
            "Eine menschliche Run/Hold/Reject-Entscheidung ist außerhalb des Systems dokumentiert.",
            "Der erste Lesepfad nach dem Lauf ist zugewiesen; Resultate werden nicht als Prognose oder Wirksamkeitsbeweis gelesen.",
        ],
        "guardrail": (
            "Run-Decision-Brief ist read-only/status-only: keine Entscheidungsspeicherung, "
            "kein Apply-Button, keine Session-State-Mutation, kein Simulationslauf, "
            "keine Registry-/Modellmutation, keine amtliche Prognose, kein Policy-Wirkungsbeweis "
            "und keine Lobbying-Empfehlung."
        ),
    }



def build_scenario_gallery_run_confirmation_template(
    *, n_runs: int = 100, n_years: int = 15, seed: int = 42
) -> dict[str, Any]:
    """Return an auditable confirmation template before a gallery run.

    This converts the decision brief into fillable, copy-safe records for a
    human/operator. It intentionally does not persist the confirmation, execute
    a simulation, apply parameters, or create evidence/model claims.
    """

    decision_brief = build_scenario_gallery_run_decision_brief(n_runs=n_runs, n_years=n_years, seed=seed)
    rows: list[dict[str, Any]] = []
    for row in decision_brief["rows"]:
        rows.append({
            "card_id": row["card_id"],
            "title": row["title"],
            "recommended_default": row["recommended_default"],
            "confirmation_status": "template_only_not_persisted_not_executed",
            "fields_to_fill_before_run": [
                {"field": "decision", "allowed_values": row["allowed_decisions"], "recommended_default": "Hold"},
                {"field": "decided_by", "prompt": "Name/Rolle der verantwortlichen Person oder Agentenrolle eintragen."},
                {"field": "decided_at", "prompt": "Zeitpunkt der Entscheidung eintragen."},
                {"field": "why_this_scenario_now", "prompt": "Kurz begründen, warum diese Starterkarte jetzt geprüft wird."},
                {"field": "evidence_caveat_acknowledged", "prompt": "Bestätigen, dass Evidenzgrad/Caveat je Parameter gelesen wurden."},
                {"field": "post_run_reading_owner", "prompt": "Festlegen, wer Storyboard, KPI-Details, Annahmen-Check und Policy-Briefing liest."},
            ],
            "minimum_checks_before_run": row["minimum_checks_before_run"],
            "copyable_payload_route_if_run": row["copyable_payload_route_if_run"],
            "copyable_manifest_route_if_run": row["copyable_manifest_route_if_run"],
            "post_run_first_three_clicks": row["post_run_first_three_clicks"],
            "stop_rule": row["stop_rule"],
            "guardrail": (
                "Confirmation-Template ist read-only: keine Entscheidungsspeicherung, kein Apply-Button, "
                "keine Session-State-Mutation, kein Simulationslauf, keine Registry-/Modellmutation, "
                "keine amtliche Prognose, kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung."
            ),
        })
    return {
        "status": "scenario_gallery_run_confirmation_template_not_executed",
        "title": "Scenario-Gallery Run-Confirmation: erst Hold/Run dokumentieren, dann bewusst ausführen",
        "recommended_default": decision_brief["recommended_default"],
        "rows": rows,
        "definition_of_done_before_run": decision_brief["definition_of_done_before_run"] + [
            "Die Confirmation-Felder wurden außerhalb dieses read-only Endpunkts ausgefüllt.",
            "Falls die Entscheidung Run lautet, wird nur der copyable Payload bewusst an POST /simulate übergeben.",
        ],
        "guardrail": (
            "Run-Confirmation-Template ist read-only/status-only: keine Entscheidungsspeicherung, "
            "kein Apply-Button, keine Session-State-Mutation, kein Simulationslauf, keine Registry-/Modellmutation, "
            "keine amtliche Prognose, kein Policy-Wirkungsbeweis und keine Lobbying-Empfehlung."
        ),
    }


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
