"""Causal, answer-first result narration for SimMed outputs.

This module turns already aggregated simulation outputs into a small set of
relevant KPIs plus one coherent German explanation. It is intentionally
read-only: no simulation run, web lookup, data fetch, or model mutation happens
here.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from simulation_core import get_default_params

RESULT_CAUSALITY_GUARDRAIL = (
    "Klartext-Erklärung eines SimMed-Modelllaufs: keine random Internet-Suche, "
    "keine amtliche Prognose und kein Wirksamkeitsnachweis."
)

KPI_SPECS: dict[str, dict[str, Any]] = {
    "aerzte_pro_100k": {
        "label": "Ärzte pro 100k",
        "higher_is_better": True,
        "why_relevant": "zeigt die verfügbare ärztliche Kapazität relativ zur Bevölkerung",
    },
    "wartezeit_fa": {
        "label": "Facharzt-Wartezeit",
        "higher_is_better": False,
        "why_relevant": "übersetzt Kapazitätsdruck in Zugang für Patient:innen",
    },
    "burnout_rate": {
        "label": "Burnout",
        "higher_is_better": False,
        "why_relevant": "zeigt, ob Kapazitätsdruck auf die Belegschaft zurückschlägt",
    },
    "telemedizin_rate": {
        "label": "Telemedizin",
        "higher_is_better": True,
        "why_relevant": "ist ein plausibler Anpassungsmechanismus bei Wartezeit- oder Ärztemangel",
    },
    "versorgungsindex_rural": {
        "label": "ländliche Versorgung",
        "higher_is_better": True,
        "why_relevant": "zeigt, ob Druck regional ungleich verteilt wird",
    },
    "gkv_saldo": {
        "label": "GKV-Saldo",
        "higher_is_better": True,
        "why_relevant": "zeigt Finanzierungsspielraum und politischen Reaktionsdruck",
    },
}


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def _changed_inputs(params: Mapping[str, Any]) -> list[dict[str, str]]:
    defaults = get_default_params()
    changed: list[dict[str, str]] = []
    labels = {
        "medizinstudienplaetze": "Medizinstudienplätze",
        "telemedizin_rate": "Telemedizin",
        "digitalisierung_epa": "ePA/Digitalisierung",
        "praeventionsbudget": "Präventionsbudget",
        "pflegepersonal_schluessel": "Pflegepersonalschlüssel",
        "drg_niveau": "Fallpauschalen-/DRG-Niveau",
        "wartezeit_grenze_tage": "Wartezeit-Zielgrenze",
    }
    for key, value in params.items():
        if key not in defaults or value == defaults[key]:
            continue
        try:
            delta = float(value) - float(defaults[key])
            direction = "erhöht" if delta > 0 else "gesenkt"
        except (TypeError, ValueError):
            direction = "geändert"
        changed.append(
            {
                "key": key,
                "label": labels.get(key, key),
                "change": f"{labels.get(key, key)} wurde {direction}: {defaults[key]} → {value}.",
                "default": str(defaults[key]),
                "value": str(value),
            }
        )
    return changed


def _metric_movement(agg: pd.DataFrame, key: str) -> dict[str, Any] | None:
    col = f"{key}_mean"
    if col not in agg.columns or agg.empty:
        return None
    spec = KPI_SPECS[key]
    start = float(agg.iloc[0][col])
    end = float(agg.iloc[-1][col])
    abs_delta = end - start
    pct_delta = abs_delta / abs(start) * 100 if start else 0.0
    good = abs_delta >= 0 if spec["higher_is_better"] else abs_delta <= 0
    direction = "steigt" if abs_delta > 0 else "sinkt" if abs_delta < 0 else "bleibt stabil"
    return {
        "metric_key": key,
        "label": spec["label"],
        "start": _fmt(start),
        "end": _fmt(end),
        "abs_delta": _fmt(abs_delta),
        "pct_delta": _fmt(pct_delta),
        "direction": direction,
        "interpretation": "eher entlastend" if good else "eher belastend",
        "why_relevant": spec["why_relevant"],
        "sentence": (
            f"{spec['label']}: {_fmt(start)} → {_fmt(end)} "
            f"({abs_delta:+.2f}; {direction}, {('eher entlastend' if good else 'eher belastend')})."
        ),
        "sort_strength": abs(pct_delta),
    }


def _relevant_kpis(agg: pd.DataFrame, *, max_kpis: int) -> list[dict[str, Any]]:
    rows = [row for key in KPI_SPECS if (row := _metric_movement(agg, key)) is not None]
    priority = {"aerzte_pro_100k": 0, "wartezeit_fa": 1, "burnout_rate": 2, "telemedizin_rate": 3}
    rows.sort(key=lambda row: (priority.get(row["metric_key"], 9), -row["sort_strength"]))
    return [
        {key: value for key, value in row.items() if key != "sort_strength"}
        for row in rows[:max_kpis]
    ]


def _adaptation_mechanisms(params: Mapping[str, Any], kpis: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    defaults = get_default_params()
    mechanisms: list[dict[str, str]] = []
    if float(params.get("medizinstudienplaetze", defaults["medizinstudienplaetze"])) < float(defaults["medizinstudienplaetze"]):
        mechanisms.extend(
            [
                {
                    "mechanism": "Ausbildungs-Pipeline",
                    "trigger": "weniger Studienplätze",
                    "timing": "ab etwa Jahr 6; Facharzt-/Kapazitätseffekt stärker Richtung Jahr 11–15",
                    "expected_effect": "weniger neue Ärzt:innen, sinkende Kapazitätsreserve, steigende Wartezeiten und Burnout-Druck",
                    "caveat": "Kopfzahl ist nicht FTE; Migration, Delegation und Telemedizin können dämpfen, müssen aber sichtbar erklärt werden.",
                },
                {
                    "mechanism": "Anpassungsmechanismen bei Ärztemangel",
                    "trigger": "sinkende ärztliche Kapazität oder steigende Wartezeit",
                    "timing": "kurzfristig Telemedizin/Mehrarbeit/Import; mittelfristig Delegation; langfristig neue Ausbildungskohorten",
                    "expected_effect": "Telemedizin kann steigen, Arbeitsdruck/Burnout sollte ohne starke Entlastung nicht einfach fallen",
                    "caveat": "Wenn Entlastung den Crash überkompensiert, muss der Output genau benennen, welcher Mechanismus das verursacht.",
                },
            ]
        )
    if any(row.get("metric_key") == "gkv_saldo" and str(row.get("direction")) == "sinkt" for row in kpis):
        mechanisms.append(
            {
                "mechanism": "Finanzielle Gegenreaktion",
                "trigger": "GKV-Saldo verschlechtert sich",
                "timing": "politisch verzögert, nicht automatisch im selben Jahr",
                "expected_effect": "Beitrag, Zuschuss, Leistungskatalog oder Vergütung geraten unter Druck",
                "caveat": "Das ist eine Modell-/Politiklogik, keine Prognose eines konkreten Gesetzes.",
            }
        )
    return mechanisms


def _counterintuitive_findings(kpis: Sequence[Mapping[str, Any]], params: Mapping[str, Any]) -> list[dict[str, str]]:
    defaults = get_default_params()
    by_key = {row["metric_key"]: row for row in kpis}
    findings: list[dict[str, str]] = []
    study_places_cut = float(params.get("medizinstudienplaetze", defaults["medizinstudienplaetze"])) < float(defaults["medizinstudienplaetze"])
    doctors_down = by_key.get("aerzte_pro_100k", {}).get("direction") == "sinkt"
    burnout_down = by_key.get("burnout_rate", {}).get("direction") == "sinkt"
    if study_places_cut and doctors_down and burnout_down:
        findings.append(
            {
                "finding": "Burnout sinkt trotz sinkender Arztkapazität.",
                "possible_model_explanation": "Das kann nur plausibel sein, wenn Telemedizin, Delegation, Arbeitszeitentlastung oder Nachfrageverzicht stark genug kompensieren.",
                "operator_action": "Mechanismus prüfen: Wenn kein starker Entlastungsmechanismus sichtbar ist, ist dieser Output als Modellfehler/zu schwache Burnout-Kopplung zu behandeln.",
            }
        )
    return findings


def build_causal_result_packet(
    agg: pd.DataFrame,
    params: Mapping[str, Any],
    *,
    max_kpis: int = 5,
) -> dict[str, Any]:
    """Build a coherent result story with only the most relevant KPIs.

    The packet is designed to replace a scattered KPI wall: show few KPIs, then
    explain the run as one auditable chain from input to output.
    """

    changed = _changed_inputs(params)
    kpis = _relevant_kpis(agg, max_kpis=max_kpis)
    mechanisms = _adaptation_mechanisms(params, kpis)
    counter = _counterintuitive_findings(kpis, params)
    changed_text = " ".join(item["change"] for item in changed) or "Keine zentrale Stellschraube wurde gegenüber dem Standardpfad verändert."
    kpi_text = " ".join(item["sentence"] for item in kpis) or "Keine priorisierten KPI-Bewegungen verfügbar."
    mechanism_text = " ".join(
        f"{item['mechanism']}: {item['expected_effect']} Timing: {item['timing']}." for item in mechanisms
    ) or "Keine spezifischen Anpassungsmechanismen wurden aus den geänderten Haupthebeln abgeleitet."
    counter_text = " ".join(item["finding"] + " " + item["operator_action"] for item in counter) or "Keine harte Gegenintuition im kompakten KPI-Set erkannt."

    story_sections = [
        {
            "id": "output",
            "heading": "Was ist der Output?",
            "text": f"Die erste Leseschicht zeigt wenige relevante KPIs statt einer KPI-Wand: {kpi_text}",
        },
        {
            "id": "changed_inputs",
            "heading": "Was wurde geändert?",
            "text": changed_text,
        },
        {
            "id": "mechanisms",
            "heading": "Warum verändert sich das Ergebnis?",
            "text": (
                "SimMed verbindet Eingriffe über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
                "Bei Medizinstudienplätzen ist der zentrale Mechanismus die Ausbildungs-Pipeline: "
                "ab etwa Jahr 6 kommen weniger Absolvent:innen an, danach steigt der Facharzt-/Kapazitätsdruck."
            ),
        },
        {
            "id": "adaptation",
            "heading": "Welche Anpassungen werden sichtbar?",
            "text": mechanism_text,
        },
        {
            "id": "counterintuitive_checks",
            "heading": "Was ist gegenintuitiv oder prüfpflichtig?",
            "text": counter_text,
        },
        {
            "id": "evidence_assumptions",
            "heading": "Welche Evidenz-/Annahmegrenze gilt?",
            "text": (
                f"{RESULT_CAUSALITY_GUARDRAIL} Evidenzgrade und Registry-Caveats begrenzen die Interpretation; "
                "diese Erklärung ist ein lokaler Modelllauf, keine freie Web-Recherche und keine automatische Parameterintegration."
            ),
        },
    ]

    coherent_story = (
        f"Ausgangspunkt: {changed_text} Ergebnis: {kpi_text} "
        f"Warum: Die Simulation liest Änderungen nicht als Einzelzahl, sondern als Wirkpfad über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
        f"Bei Medizinstudienplätzen ist der zentrale Punkt der Ausbildungs-Lag: ab etwa Jahr 6 kommen weniger Absolvent:innen an; "
        f"im 15-Jahres-Horizont sollte sich das in Ärzte pro 100k, Wartezeit und Burnout zeigen, sofern Anpassungsmechanismen es nicht sichtbar dämpfen. "
        f"Anpassungsmechanismen: {mechanism_text} Gegencheck: {counter_text}"
    )

    return {
        "title": "Simulationsergebnis in Klartext",
        "subtitle": "Wenige relevante KPIs plus ein zusammenhängender Wirkpfad von Eingabe zu Output.",
        "reading_order": [
            "1 · geänderte Eingriffe",
            "2 · relevante KPIs",
            "3 · Wirkpfad und Timing",
            "4 · Anpassungsmechanismen",
            "5 · Gegencheck/Caveat",
        ],
        "changed_inputs": changed,
        "relevant_kpis": kpis,
        "adaptation_mechanisms": mechanisms,
        "counterintuitive_findings": counter,
        "story_sections": story_sections,
        "coherent_story": coherent_story,
        "method_note": RESULT_CAUSALITY_GUARDRAIL,
        "guardrail": RESULT_CAUSALITY_GUARDRAIL,
    }
