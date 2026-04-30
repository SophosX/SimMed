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
from parameter_registry import PARAMETER_REGISTRY

RESULT_CAUSALITY_GUARDRAIL = (
    "Die Berechnung basiert auf dem SimMed-Modelllauf mit dokumentierten Parametern, "
    "Annahmen und Monte-Carlo-Spannweiten; sie ist als Modell-Einordnung zu lesen, "
    "nicht als amtliche Prognose oder Wirksamkeitsnachweis."
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


def _fmt_de(value: Any, *, decimals: int = 2) -> str:
    """Format public German result numbers without exposing Python float noise."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0 or number.is_integer():
        return f"{int(round(number)):,}".replace(",", ".")
    return f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_de_fixed(value: Any, *, decimals: int = 2) -> str:
    """Format German numbers with fixed decimals for KPI rows."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{int(round(number)):,}".replace(",", ".")
    return f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
        label = labels.get(key, key)
        default_text = _fmt_de(defaults[key], decimals=0)
        value_text = _fmt_de(value, decimals=0)
        verb = "wurden" if label == "Medizinstudienplätze" else "wurde"
        changed.append(
            {
                "key": key,
                "label": label,
                "change": f"{label} {verb} {direction}: {default_text} → {value_text}.",
                "default": default_text,
                "value": value_text,
            }
        )
    return changed


def _evidence_assumption_rows(changed_inputs: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    """Expose registry evidence/caveats for changed levers in the causal packet."""

    rows: list[dict[str, Any]] = []
    for item in changed_inputs:
        key = str(item.get("key", ""))
        spec = PARAMETER_REGISTRY.get(key)
        if spec is None:
            continue
        rows.append(
            {
                "parameter_key": key,
                "label": spec.label,
                "evidence_grade": spec.evidence_grade,
                "source_ids": list(spec.source_ids),
                "model_role": spec.model_role,
                "uncertainty": spec.uncertainty,
                "caveat": spec.caveat,
                "interpretation_limit": (
                    f"Evidenzgrad {spec.evidence_grade}: Registry/Quellen stützen den Parameterrahmen, "
                    "aber der konkrete Szenarioeffekt bleibt eine SimMed-Annahme und kein Wirksamkeitsnachweis."
                ),
            }
        )
    return rows


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
        "meaning": (
            f"{spec['why_relevant']}; in diesem Lauf ist die Bewegung "
            f"{'eher entlastend' if good else 'eher belastend'}."
        ),
        "sentence": (
            f"{spec['label']}: {_fmt(start)} → {_fmt(end)} "
            f"({abs_delta:+.2f}; {direction}, {('eher entlastend' if good else 'eher belastend')})."
        ),
        "sort_strength": abs(pct_delta),
    }


def _public_kpi_reading(metric_key: str, direction: str) -> str:
    """Short first-screen reading for a KPI row, without adding new causal claims."""

    if metric_key == "aerzte_pro_100k":
        return "Weniger Kapazität: Zugang und Belastung danach gemeinsam prüfen."
    if metric_key == "wartezeit_fa":
        return "Längere Wartezeit heißt: Zugang wird für Patient:innen schwerer."
    if metric_key == "burnout_rate":
        return "Belastungssignal: passt es zur Kapazitäts- und Wartezeitbewegung?"
    if metric_key == "telemedizin_rate":
        return "Puffer-Signal: kann Druck dämpfen, ersetzt aber keine Kapazitätsprüfung."
    if metric_key == "versorgungsindex_rural":
        return "Regionaler Check: verschlechtert sich Zugang außerhalb der Zentren?"
    if metric_key == "gkv_saldo":
        return "Finanzsignal: zeigt Spielraum oder zusätzlichen politischen Druck."
    return f"{direction.capitalize()}: diese Kennzahl begrenzt die Deutung des Laufs."


def _changed_key_set(params: Mapping[str, Any]) -> set[str]:
    defaults = get_default_params()
    return {key for key, value in params.items() if key in defaults and value != defaults[key]}


def _scenario_kpi_priority(params: Mapping[str, Any]) -> dict[str, int]:
    """Choose the first-view KPI order from the changed lever family.

    The first result view should not always start with the same health-system
    capacity cards. A financing scenario should first show financing pressure;
    a medical-training scenario should first show pipeline/capacity/access; a
    digital scenario should first show the visible adaptation signal. This is a
    presentation rule only — it does not alter the simulation output.
    """

    changed_keys = _changed_key_set(params)
    financing_keys = {
        "gkv_beitragssatz",
        "gkv_zusatzbeitrag",
        "gkv_anteil",
        "pkv_beitrag_durchschnitt",
        "zuzahlungen_gkv",
        "staatliche_subventionen",
    }
    digital_keys = {"telemedizin_rate", "digitalisierung_epa"}
    prevention_keys = {"praeventionsbudget"}
    study_place_keys = {"medizinstudienplaetze"}

    if changed_keys & financing_keys:
        return {
            "gkv_saldo": 0,
            "wartezeit_fa": 1,
            "versorgungsindex_rural": 2,
            "aerzte_pro_100k": 3,
            "burnout_rate": 4,
            "telemedizin_rate": 5,
        }
    if changed_keys & digital_keys:
        return {
            "telemedizin_rate": 0,
            "wartezeit_fa": 1,
            "burnout_rate": 2,
            "versorgungsindex_rural": 3,
            "gkv_saldo": 4,
            "aerzte_pro_100k": 5,
        }
    if changed_keys & prevention_keys:
        return {
            "gkv_saldo": 0,
            "wartezeit_fa": 1,
            "versorgungsindex_rural": 2,
            "burnout_rate": 3,
            "aerzte_pro_100k": 4,
            "telemedizin_rate": 5,
        }
    if changed_keys & study_place_keys:
        return {
            "aerzte_pro_100k": 0,
            "wartezeit_fa": 1,
            "burnout_rate": 2,
            "telemedizin_rate": 3,
            "versorgungsindex_rural": 4,
            "gkv_saldo": 5,
        }
    return {
        "aerzte_pro_100k": 0,
        "wartezeit_fa": 1,
        "burnout_rate": 2,
        "telemedizin_rate": 3,
        "versorgungsindex_rural": 4,
        "gkv_saldo": 5,
    }


def _relevant_kpis(agg: pd.DataFrame, params: Mapping[str, Any], *, max_kpis: int) -> list[dict[str, Any]]:
    rows = [row for key in KPI_SPECS if (row := _metric_movement(agg, key)) is not None]
    priority = _scenario_kpi_priority(params)
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


def _relevant_kpi_summary(
    kpis: Sequence[Mapping[str, Any]],
    changed_inputs: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    """Explain why each selected KPI belongs in the first result view.

    This keeps the first result screen from becoming a KPI wall: every shown KPI
    must state its signal, mechanism link, and next audit step.
    """

    changed_labels = [str(item.get("label", item.get("key", ""))) for item in changed_inputs]
    changed_text = ", ".join(changed_labels) if changed_labels else "dem Standardpfad"
    study_places_changed = any(item.get("key") == "medizinstudienplaetze" for item in changed_inputs)
    mechanism_by_metric = {
        "aerzte_pro_100k": "Ausbildungs-Pipeline und Kapazitätsreserve",
        "wartezeit_fa": "Kapazitätsdruck übersetzt sich in Zugang/Wartezeit",
        "burnout_rate": "Arbeitsdruck/Burnout reagiert auf nicht kompensierten Ärztemangel",
        "telemedizin_rate": "Telemedizin ist ein sichtbarer Dämpfungs-/Anpassungsmechanismus",
        "versorgungsindex_rural": "regionale Verteilung zeigt, ob Druck ländlich stärker ankommt",
        "gkv_saldo": "Finanzierungsdruck zeigt politische Gegenreaktionen",
    }
    rows: list[dict[str, str]] = []
    for row in kpis:
        metric_key = str(row.get("metric_key", ""))
        mechanism = mechanism_by_metric.get(metric_key, "bestehender SimMed-Wirkpfad")
        if study_places_changed and metric_key in {"aerzte_pro_100k", "wartezeit_fa", "burnout_rate", "telemedizin_rate"}:
            why_selected = (
                f"Ausgewählt, weil {changed_text} die Ausbildungs-Pipeline und anschließenden "
                "Kapazitäts-/Wartezeit-/Burnout-Druck direkt prüfen."
            )
        else:
            why_selected = f"Ausgewählt, weil diese Kennzahl die Änderung {changed_text} im Modellpfad sichtbar macht."
        rows.append(
            {
                "metric_key": metric_key,
                "label": str(row.get("label", metric_key)),
                "answer_signal": str(row.get("sentence", "")),
                "why_selected": why_selected,
                "mechanism_link": mechanism,
                "next_check": "Im Ergebnisbericht lesen; anschließend Detailkarte und Trend zur fachlichen Prüfung öffnen.",
            }
        )
    return rows


def _adaptation_signal_trace(kpis: Sequence[Mapping[str, Any]], params: Mapping[str, Any]) -> list[dict[str, str]]:
    """Explain observed adaptation/pressure signals from the selected KPI set."""

    defaults = get_default_params()
    study_places_cut = float(params.get("medizinstudienplaetze", defaults["medizinstudienplaetze"])) < float(defaults["medizinstudienplaetze"])
    if not study_places_cut:
        return []

    trace: list[dict[str, str]] = []
    by_key = {str(row.get("metric_key")): row for row in kpis}
    interpretations = {
        "telemedizin_rate": {
            "if_up": "Telemedizin steigt als dämpfender Mechanismus gegen Wartezeit- und Kapazitätsdruck.",
            "if_down": "Telemedizin sinkt; im Ärztemangel fehlt damit ein sichtbarer digitaler Puffer.",
            "if_flat": "Telemedizin bleibt stabil; sie erklärt dann kaum eine Kompensation des Kapazitätsdrucks.",
            "role": "Anpassung/Puffer",
        },
        "burnout_rate": {
            "if_up": "Burnout steigt als Drucksignal: die Belegschaft trägt einen Teil des Kapazitätsmangels.",
            "if_down": "Burnout sinkt trotz Kapazitätsmangel; das ist nur plausibel, wenn ein Entlastungsmechanismus stark genug sichtbar ist.",
            "if_flat": "Burnout bleibt stabil; prüfen, ob Telemedizin, Delegation oder Nachfrageverzicht den Druck wirklich erklären.",
            "role": "Drucksignal",
        },
    }
    for key, config in interpretations.items():
        row = by_key.get(key)
        if not row:
            continue
        direction = str(row.get("direction", "bleibt stabil"))
        if direction == "steigt":
            interpretation = config["if_up"]
        elif direction == "sinkt":
            interpretation = config["if_down"]
        else:
            interpretation = config["if_flat"]
        trace.append(
            {
                "signal_key": key,
                "label": str(row.get("label", key)),
                "observed_direction": direction,
                "observed_change": str(row.get("sentence", "")),
                "role": config["role"],
                "plain_interpretation": interpretation,
                "guardrail": f"{RESULT_CAUSALITY_GUARDRAIL} Das Signal beschreibt Modellverhalten, nicht eine amtliche Prognose.",
            }
        )
    return trace


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


def _briefing_quality_checks(
    professional_briefing: Mapping[str, Any],
    kpis: Sequence[Mapping[str, Any]],
    adaptation_trace: Sequence[Mapping[str, str]],
    evidence_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Return a compact, read-only quality gate for the first result view.

    The goal is not to score the scenario. It guards the presentation: one
    sequential briefing, a small KPI set, visible adaptation signals, restrained
    human language, and an explicit interpretation boundary.
    """

    sequential_text = str(professional_briefing.get("sequential_text", ""))
    headings = [str(section.get("heading", "")) for section in professional_briefing.get("sections", [])]
    display_headings = ["Wirkpfad" if heading == "Berechnete Wirkpfade" else heading for heading in headings[:3]]
    ordered = " → ".join(display_headings) if len(display_headings) >= 3 else "Sequenz unvollständig"
    adaptation_labels = ", ".join(str(row.get("label", "")) for row in adaptation_trace) or "keine spezifischen Anpassungssignale"
    evidence_grades = ", ".join(
        f"{row.get('label', row.get('parameter_key', 'Parameter'))}: Evidenzgrad {row.get('evidence_grade', '?')}"
        for row in evidence_rows
    ) or "keine geänderte Registry-Zeile"
    banned_terms = (
        "random Internet",
        "Klartext",
        "KPI-Wand",
        "keine freie Web-Recherche",
        "generated",
        "helper",
        "Zahlenwand",
    )
    professional_language_ok = not any(term in sequential_text for term in banned_terms)
    bounded = "keine amtliche Prognose" in sequential_text or "keine amtliche Prognose" in RESULT_CAUSALITY_GUARDRAIL

    return [
        {
            "check": "Ein roter Faden",
            "status": "erfüllt" if headings[:3] == ["Ausgangslage", "Eingriff", "Berechnete Wirkpfade"] else "prüfen",
            "evidence": f"{ordered} ist die erste Lesespur.",
            "why_it_matters": "Der Bericht beginnt mit einer nachvollziehbaren Kette statt mit lose verteilten Kennzahlen.",
        },
        {
            "check": "Wenige relevante KPIs",
            "status": "erfüllt" if 0 < len(kpis) <= 5 else "prüfen",
            "evidence": f"{len(kpis)} relevante Kennzahlen stehen vor den Detailkarten.",
            "why_it_matters": "Die erste Ansicht zeigt nur Signale, die den Wirkpfad erklären; der Rest bleibt als Audit-Layer verfügbar.",
        },
        {
            "check": "Anpassung sichtbar",
            "status": "erfüllt" if adaptation_trace else "prüfen",
            "evidence": f"Beobachtete Anpassungs-/Drucksignale: {adaptation_labels}.",
            "why_it_matters": "Bei Kapazitätsdruck müssen Puffer wie Telemedizin und Drucksignale wie Burnout gemeinsam gelesen werden.",
        },
        {
            "check": "Professionelle Sprache",
            "status": "erfüllt" if professional_language_ok else "prüfen",
            "evidence": "Der erste Ergebnistext vermeidet interne Prozessfloskeln und bleibt bei fachlicher Sprache.",
            "why_it_matters": "Der Bericht soll wie eine ernsthafte Simulationseinordnung wirken, nicht wie zusammengeklebte Systemnotizen.",
        },
        {
            "check": "Belastbarkeit begrenzt",
            "status": "erfüllt" if bounded else "prüfen",
            "evidence": f"{evidence_grades}; keine amtliche Prognose oder Wirksamkeitsnachweis.",
            "why_it_matters": "Evidenz und Annahmen bleiben sichtbar, ohne die erste Ergebnisansicht mit Quellenprosa zu überladen.",
        },
    ]


def _timeline_windows(params: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return human-readable timing checkpoints for delayed policy effects."""
    defaults = get_default_params()
    study_places_cut = float(params.get("medizinstudienplaetze", defaults["medizinstudienplaetze"])) < float(defaults["medizinstudienplaetze"])
    if not study_places_cut:
        return []
    guardrail = f"{RESULT_CAUSALITY_GUARDRAIL} Zeitfenster sind SimMed-Annahmen und Prüfpunkte, nicht amtliche Prognosen."
    return [
        {
            "window": "Jahr 0–5",
            "expected_signal": "kein unmittelbarer Kapazitäts-Crash: weniger Studienplätze sind noch überwiegend in der Ausbildungspipeline gebunden",
            "adaptation_to_check": "kurzfristig eher Mehrarbeit, Terminsteuerung, Telemedizin- und Delegationsausbau prüfen",
            "pressure_check": "Wartezeit/Burnout dürfen nicht als endgültige Entwarnung gelesen werden, weil der Hauptlag noch nicht angekommen ist",
            "guardrail": guardrail,
        },
        {
            "window": "Jahr 6–10",
            "expected_signal": "weniger Absolvent:innen erreichen den Arbeitsmarkt; Kapazitätsreserve und Wartezeit sollten sichtbar unter Druck geraten",
            "adaptation_to_check": "Telemedizin, Delegation, Zuwanderung und Produktivität müssen als dämpfende Mechanismen sichtbar benannt werden",
            "pressure_check": "Burnout oder Arbeitsdruck sollten ohne klare Entlastung nicht still fallen",
            "guardrail": guardrail,
        },
        {
            "window": "Jahr 11–15",
            "expected_signal": "Facharzt- und Versorgungskapazität geraten stärker unter Druck, wenn frühere Kohortenlücken nicht kompensiert wurden",
            "adaptation_to_check": "dauerhafte Substitution/Delegation, regionale Umverteilung und internationale Rekrutierung als mögliche, aber begrenzte Puffer prüfen",
            "pressure_check": "Burnout, Wartezeit und ländliche Versorgung sind die zentralen Crash-/Kompensationssignale",
            "guardrail": guardrail,
        },
    ]


def build_causal_result_layout(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Describe the answer-first result layout for UI/API clients.

    This keeps the old dense KPI cards available as an audit/detail layer, but
    explicitly prevents them from being the first interpretation surface.
    """

    return {
        "first_view": str(packet.get("title", "Ergebnisbericht")),
        "primary_sequence": [
            "Ergebnis",
            "Eingriff",
            "Warum es passiert",
            "Relevante Kennzahlen",
            "Anpassungen",
            "Einordnung",
            "Nächster Prüfschritt",
        ],
        "dense_kpi_wall": {
            "label": "Weitere Kennzahlen nach dem Ergebnisbericht",
            "mode": "collapsed_after_result_briefing",
            "default_expanded": False,
            "reason": (
                "Die vollständigen Kennzahlen bleiben verfügbar, stehen aber unter der ersten Lesefassung: "
                "zuerst Ergebnis, Eingriff, Wirkpfad, Anpassung und Einordnung; danach die Detailprüfung."
            ),
        },
        "optional_interpretation_layers": {
            "label": "Weitere Prüfung: Zeitverlauf, Unsicherheit und Detailbegründung",
            "mode": "collapsed_after_result_briefing",
            "default_expanded": False,
            "sections": [
                "Narrative Zusammenfassung",
                "Entscheidungs-Checkpoints",
                "Storyboard",
                "Unsicherheitsband",
            ],
            "reason": (
                "Diese Abschnitte vertiefen den Ergebnisbericht. Sie bleiben geschlossen, damit der Einstieg "
                "als ein lesbarer Bericht beginnt und nicht als mehrere konkurrierende Erklärblöcke."
            ),
        },
        "secondary_detail_layers": {
            "label": "Detailprüfung nach dem Ergebnisbericht",
            "mode": "single_collapsed_detail_area",
            "default_expanded": False,
            "sections": [
                "KPI-Details",
                "Trend und Timing",
                "Policy-Briefing",
                "politische Einordnung",
            ],
            "reason": (
                "Alles nach dem ersten Ergebnisbriefing ist bewusst Prüfung: einzelne Kennzahlen, "
                "Zeitverlauf, Annahmen und politische Einordnung werden geöffnet, wenn die erste Antwort verstanden ist."
            ),
        },
        "optional_details_after": packet.get("primary_result_view", {}).get(
            "optional_details_after",
            [
                "Kennzahlen im Detail",
                "Zeitverlauf",
                "Bericht mit Annahmen und Quellen",
                "politische Einordnung",
            ],
        ),
        "guardrail": packet.get("guardrail", RESULT_CAUSALITY_GUARDRAIL),
    }


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
    evidence_rows = _evidence_assumption_rows(changed)
    kpis = _relevant_kpis(agg, params, max_kpis=max_kpis)
    kpi_summary = _relevant_kpi_summary(kpis, changed)
    mechanisms = _adaptation_mechanisms(params, kpis)
    adaptation_trace = _adaptation_signal_trace(kpis, params)
    timeline_windows = _timeline_windows(params)
    counter = _counterintuitive_findings(kpis, params)
    changed_text = " ".join(item["change"] for item in changed) or "Keine zentrale Stellschraube wurde gegenüber dem Standardpfad verändert."
    study_places_changed = any(item.get("key") == "medizinstudienplaetze" for item in changed)
    kpi_text = " ".join(item["sentence"] for item in kpis) or "Keine priorisierten KPI-Bewegungen verfügbar."
    mechanism_text = " ".join(
        f"{item['mechanism']}: {item['expected_effect']} Timing: {item['timing']}." for item in mechanisms
    ) or "Keine spezifischen Anpassungsmechanismen wurden aus den geänderten Haupthebeln abgeleitet."
    adaptation_trace_text = " ".join(
        f"{item['label']} {item['observed_direction']}: {item['plain_interpretation']}" for item in adaptation_trace
    ) or "Keine beobachteten Anpassungs-/Drucksignale im kompakten KPI-Set."
    timeline_text = " ".join(
        f"{item['window']}: {item['expected_signal']} ({item['pressure_check']})." for item in timeline_windows
    ) or "Kein spezifisches verzögertes Zeitfenster aus den geänderten Haupthebeln abgeleitet."
    counter_text = " ".join(item["finding"] + " " + item["operator_action"] for item in counter) or "Keine harte Gegenintuition im kompakten KPI-Set erkannt."
    evidence_text = " ".join(
        f"{row['label']} ({row['parameter_key']}): Evidenzgrad {row['evidence_grade']}; {row['interpretation_limit']}"
        for row in evidence_rows
    ) or "Keine geänderte Stellschraube mit Registry-Evidenzzeile im aktuellen Lauf."

    if study_places_changed:
        mechanism_block_text = (
            "SimMed verbindet Eingriffe über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
            "Bei Medizinstudienplätzen ist der zentrale Mechanismus die Ausbildungs-Pipeline: "
            "ab etwa Jahr 6 kommen weniger Absolvent:innen an, danach steigt der Facharzt-/Kapazitätsdruck. "
            f"Zeitfenster: {timeline_text}"
        )
    elif changed:
        mechanism_block_text = (
            "SimMed verbindet die geänderten Stellschrauben mit den dazu passenden Modellpfaden: Finanzierung, Nachfrage, Versorgungskapazität, regionale Verteilung und Zeitverzug. "
            "Für diesen Lauf wird kein spezieller Ausbildungs-Lag behauptet; der Bericht bleibt bei den tatsächlich veränderten Hebeln und ihren beobachteten Kennzahlen. "
            f"Zeitfenster: {timeline_text}"
        )
    else:
        mechanism_block_text = (
            "SimMed liest hier den Referenzpfad ohne zusätzlichen Eingriff: Welche Kennzahlen bewegen sich im Modelllauf, "
            "welche Mechanismen könnten dahinterliegen, und welche davon sind vor einer fachlichen Deutung prüfpflichtig?"
        )

    free_text_blocks = [
        {
            "step": "1. Ergebnis",
            "text": f"Der Lauf wird zuerst über wenige relevante Kennzahlen gelesen: {kpi_text}",
        },
        {
            "step": "2. Änderung",
            "text": changed_text,
        },
        {
            "step": "3. Wirkmechanismus",
            "text": mechanism_block_text,
        },
        {
            "step": "4. Anpassung",
            "text": f"{mechanism_text} Beobachtete Signale: {adaptation_trace_text}",
        },
        {
            "step": "5. Plausibilitätsprüfung",
            "text": counter_text,
        },
        {
            "step": "6. Einordnung und Belastbarkeit",
            "text": (
                f"Datenlage und Belastbarkeit: {evidence_text} {RESULT_CAUSALITY_GUARDRAIL} "
                "Evidenzgrade, Registry-Caveats und Modellannahmen begrenzen die Interpretation."
            ),
        },
    ]

    legacy_numbered_story = "\n\n".join(
        ["Ergebnisbericht"]
        + [f"{block['step']}\n{block['text']}" for block in free_text_blocks]
    )

    cleartext_reading_cards = [
        {
            "stage": "Ergebnis",
            "answer_first": free_text_blocks[0]["text"],
            "audit_focus": "nur die priorisierten relevanten KPIs lesen",
            "next_step": "Danach Änderung und Wirkpfad öffnen; Detailkarten erst anschließend nutzen.",
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        {
            "stage": "Änderung",
            "answer_first": free_text_blocks[1]["text"],
            "audit_focus": "geänderte Hebel gegen Standardpfad prüfen",
            "next_step": "Für jeden geänderten Hebel Evidenzgrad und Caveat prüfen.",
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        {
            "stage": "Wirkmechanismus",
            "answer_first": free_text_blocks[2]["text"],
            "audit_focus": "Zeitfenster 0–5 / 6–10 / 11–15 prüfen",
            "next_step": "Bei Ausbildungshebeln besonders auf verzögerte Kapazität und Facharzt-Effekt achten.",
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        {
            "stage": "Anpassung",
            "answer_first": free_text_blocks[3]["text"],
            "audit_focus": "Telemedizin, Delegation, Zuwanderung oder Arbeitsdruck als sichtbare Puffer/Drucksignale prüfen",
            "next_step": "Wenn ein Drucksignal fällt, muss ein Entlastungsmechanismus sichtbar benannt sein.",
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        {
            "stage": "Gegencheck",
            "answer_first": free_text_blocks[4]["text"],
            "audit_focus": "gegenintuitive Bewegungen vor politischer Deutung markieren",
            "next_step": "Bei ungeklärter Gegenintuition Modellkopplung oder Annahme prüfen, nicht überinterpretieren.",
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        {
            "stage": "Evidenzgrenze",
            "answer_first": free_text_blocks[5]["text"],
            "audit_focus": "Evidenzgrade, Quellen und SimMed-Annahmen trennen",
            "next_step": "Erst nach dieser Grenze Detailkarten, Trend und Policy-Briefing als Audit-Layer öffnen.",
            "guardrail": f"{RESULT_CAUSALITY_GUARDRAIL} Nicht als amtliche Prognose oder Policy-Wirksamkeitsnachweis zu lesen.",
        },
    ]

    story_sections = [
        {
            "id": "output",
            "heading": "Was ist der Output?",
            "text": free_text_blocks[0]["text"],
        },
        {
            "id": "changed_inputs",
            "heading": "Was wurde geändert?",
            "text": free_text_blocks[1]["text"],
        },
        {
            "id": "mechanisms",
            "heading": "Warum verändert sich das Ergebnis?",
            "text": free_text_blocks[2]["text"],
        },
        {
            "id": "adaptation",
            "heading": "Welche Anpassungen werden sichtbar?",
            "text": free_text_blocks[3]["text"],
        },
        {
            "id": "counterintuitive_checks",
            "heading": "Was ist gegenintuitiv oder prüfpflichtig?",
            "text": free_text_blocks[4]["text"],
        },
        {
            "id": "evidence_assumptions",
            "heading": "Welche Einordnung und Belastbarkeit gilt?",
            "text": free_text_blocks[5]["text"],
        },
    ]

    first_view_kpi_cards = [
        {
            "label": str(row.get("label", "")),
            "movement": str(row.get("sentence", "")),
            "value_line": f"{row.get('start', '–')} → {row.get('end', '–')} ({row.get('direction', 'stabil')})",
            "interpretation_tone": str(row.get("interpretation", "prüfen")),
            "why_it_matters": str(summary.get("mechanism_link", row.get("why_relevant", ""))),
            "what_to_check_next": (
                "Zeitverlauf und Annahmen prüfen, bevor diese Kennzahl politisch interpretiert wird."
            ),
        }
        for row, summary in zip(kpis, kpi_summary, strict=False)
    ]

    if study_places_changed:
        pathway_body = (
            "Der Eingriff läuft im Modell über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
            "Bei weniger Medizinstudienplätzen ist der entscheidende Punkt die Ausbildungs-Pipeline: "
            "in Jahr 0–5 passiert noch wenig an der ärztlichen Versorgung, ab Jahr 6 erreicht die kleinere Kohorte den Arbeitsmarkt, "
            "und Richtung Jahr 11–15 wird der Facharzt- und Kapazitätseffekt deutlich prüfpflichtig. "
            f"{timeline_text}"
        )
    elif changed:
        pathway_body = (
            "Der Eingriff läuft im Modell über die jeweils dokumentierten SimMed-Pfade — Kapazität, Nachfrage, Finanzierung, regionale Verteilung und Zeitverzug. "
            "Der Bericht bleibt bei den tatsächlich veränderten Hebeln und den dazu passenden Kennzahlen; zusätzliche Pipeline-Mechanismen werden nicht hineingelesen. "
            f"{timeline_text}"
        )
    else:
        pathway_body = (
            "Es wurde keine zentrale Stellschraube verändert. Der Bericht liest deshalb den Referenzpfad selbst: Welche Kennzahlen bewegen sich im Modelllauf, "
            "obwohl kein zusätzlicher Eingriff gesetzt wurde, und welche davon sollten vor einer fachlichen Deutung genauer geprüft werden?"
        )

    policy_readiness_summary = {
        "headline": "Was daraus folgt",
        "current_read": "prüfpflichtig" if study_places_changed or counter else "belastbar innerhalb der Modellannahmen",
        "why": (
            "Medizinstudienplätze wirken in diesem Lauf nicht sofort, sondern über die Ausbildungs-Pipeline: "
            "ab Jahr 6 wird die kleinere Kohorte arbeitsmarktnäher, Richtung Jahr 11–15 wird der Facharzt-/Kapazitätspfad entscheidend."
            if study_places_changed
            else "Der Lauf sollte entlang der veränderten Stellschrauben, der relevanten Kennzahlen und der dokumentierten Annahmen gelesen werden."
        ),
        "before_decision": (
            "Vor einer politischen Bewertung zuerst prüfen: passen Telemedizin, Delegation oder Zuwanderung als Puffer zum beobachteten Wartezeit- und Burnout-Signal?"
            if study_places_changed
            else "Vor einer politischen Bewertung zuerst prüfen, ob die gezeigten Kennzahlen zum dokumentierten Modellpfad und zu den Registry-Caveats passen."
        ),
        "recommended_next_step": (
            "Zuerst die Zeitfenster 6–10 und 11–15, die relevanten KPI-Detailkarten und die Evidenz-/Annahmegrenzen öffnen; erst danach die politische Einordnung lesen."
        ),
        "guardrail": f"{RESULT_CAUSALITY_GUARDRAIL} Kurz: keine amtliche Prognose, kein Wirksamkeitsnachweis.",
    }

    professional_sections = [
        {
            "heading": "Ausgangslage",
            "body": (
                "SimMed liest diesen Lauf als Deutschland-Referenzpfad mit veränderten Stellschrauben. "
                "Die erste Ansicht zeigt bewusst nur die Kennzahlen, die den zentralen Wirkpfad erklären."
            ),
        },
        {
            "heading": "Eingriff",
            "body": changed_text,
        },
        {
            "heading": "Berechnete Wirkpfade",
            "body": pathway_body,
        },
        {
            "heading": "Relevante Kennzahlen",
            "body": kpi_text,
        },
        {
            "heading": "Anpassungsreaktionen",
            "body": (
                f"{mechanism_text} Beobachtete Signale: {adaptation_trace_text} "
                "Wichtig: Wenn unter Ärztemangel Burnout oder Wartezeit überraschend sinken, braucht der Bericht einen sichtbaren Puffer — etwa Telemedizin, Delegation, Zuwanderung oder Nachfrageverzicht. Sonst ist das kein stiller Triumph, sondern ein Prüfhinweis."
            ),
        },
        {
            "heading": "Einordnung und Belastbarkeit",
            "body": (
                f"{evidence_text} Die Berechnung basiert auf dem SimMed-Modelllauf mit dokumentierten Parametern, Annahmen und Monte-Carlo-Spannweiten. "
                "Sie ist eine belastbare Modell-Einordnung innerhalb dieser Annahmen, aber keine amtliche Prognose und kein Nachweis, dass eine politische Maßnahme real so wirkt."
            ),
        },
        {
            "heading": "Was daraus folgt",
            "body": (
                "Der Bericht liefert damit keine einzelne Siegerzahl, sondern eine prüfbare Linie: Eingriff → Wirkpfad → beobachtete Kennzahlen → Anpassungsreaktionen → Belastbarkeitsgrenze. "
                + (
                    "Für diesen Lauf heißt das: Kapazitätsdruck darf erst dann politisch interpretiert werden, wenn die sichtbaren Puffer und Drucksignale gemeinsam zu prüfen sind."
                    if study_places_changed
                    else "Für diesen Lauf heißt das: Die politische Deutung sollte beim tatsächlich veränderten Hebel beginnen und erst danach die nachgeordneten Versorgungs-, Finanzierungs- und Annahmenprüfungen öffnen."
                )
            ),
        },
        {
            "heading": "Nächste Prüfentscheidung",
            "body": (
                "Als nächste fachliche Prüfung sollte zuerst geklärt werden, ob die Anpassungsreaktionen den Kapazitätsdruck plausibel erklären: "
                "Telemedizin/Delegation/Zuwanderung als Puffer, Burnout als Drucksignal und Wartezeit als Patient:innen-Signal. "
                "Kurz: erst fachlich prüfen, dann politisch bewerten; sonst wäre die Zahl präzise, aber die Entscheidung zu früh."
            ),
        },
    ]
    lead_paragraph = (
        "Dieser Lauf wird als Wirkungskette gelesen. "
        "Die erste Ansicht konzentriert sich auf wenige relevante Kennzahlen, erklärt die gesetzte Änderung, "
        "ordnet den berechneten Wirkpfad ein und zeigt, welche Anpassungsreaktionen vor einer politischen Deutung geprüft werden müssen."
    )
    if study_places_changed:
        lead_paragraph += (
            " Bei weniger Medizinstudienplätzen ist der kritische Punkt nicht das Startjahr, "
            "sondern die Pipeline: erst ab Jahr 6 kommt die kleinere Kohorte spürbar am Arbeitsmarkt an."
        )
    first_view_briefing_cards = [
        {
            "stage": section["heading"],
            "answer": section["body"][:360],
            "why_it_matters": why,
            "next_step": next_step,
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        }
        for section, why, next_step in zip(
            professional_sections,
            [
                "Setzt den Kontext, bevor Zahlen interpretiert werden.",
                "Macht sichtbar, welche Stellschraube den Lauf vom Standardpfad trennt.",
                "Erklärt die berechnete Kette zwischen Eingriff, Zeitverzug und Ergebnis.",
                "Reduziert die erste Ansicht auf die Kennzahlen, die den Wirkpfad tragen.",
                "Prüft, ob Puffer wie Telemedizin oder Drucksignale wie Burnout zur Bewegung passen.",
                "Hält Evidenz, Annahmen und Grenzen zusammen: keine amtliche Prognose, kein Wirksamkeitsnachweis.",
                "Übersetzt den Bericht in eine prüfbare Lesereihenfolge statt in eine einzelne Siegerzahl.",
                "Sagt, welche fachliche Prüfung vor der politischen Deutung kommen sollte.",
            ],
            [
                "Danach den Eingriff lesen.",
                "Danach den berechneten Wirkpfad und die Zeitfenster prüfen.",
                "Danach nur die relevanten KPI-Signale lesen; die vollständigen Detailkarten kommen erst danach.",
                "Danach Anpassungsreaktionen und Gegenintuitionen prüfen.",
                "Danach Belastbarkeit und Registry-Caveats prüfen.",
                "Danach Detailkarten, Trend und Policy-Briefing als vertiefende Prüfung öffnen.",
                "Danach die nächste fachliche Prüfentscheidung bewusst setzen.",
                "Danach entscheiden, ob weitere Modell-/Annahmenprüfung nötig ist.",
            ],
            strict=False,
        )
    ]
    section_flow = [
        "Ausgangslage",
        "Eingriff",
        "berechneter Wirkpfad",
        "relevante Kennzahlen",
        "Anpassungsreaktionen",
        "Einordnung",
        "nächste Prüfentscheidung",
    ]
    narrative_hints = {
        "Ausgangslage": "Warum das wichtig ist: Der Kontext verhindert, dass einzelne Endwerte wie eine Rangliste gelesen werden.",
        "Eingriff": "Warum das wichtig ist: Nur sichtbare Änderungen gegenüber dem Standardpfad dürfen als mögliche Auslöser gelesen werden.",
        "Berechnete Wirkpfade": "Warum das wichtig ist: Der Wirkpfad zeigt, wann eine Maßnahme überhaupt im Modell ankommen kann.",
        "Relevante Kennzahlen": "Warum das wichtig ist: Die erste Ansicht soll die tragenden Signale zeigen, nicht jede verfügbare Zahl.",
        "Anpassungsreaktionen": "Warum das wichtig ist: Systeme puffern Druck oft erst ab; genau diese Puffer müssen vor der Deutung sichtbar werden.",
        "Einordnung und Belastbarkeit": "Warum das wichtig ist: Evidenzgrad, Registry-Caveat und Monte-Carlo-Spannweite begrenzen die Aussagekraft.",
        "Was daraus folgt": "Warum das wichtig ist: SimMed liefert eine prüfbare Wirkungslinie, keine einzelne Siegerzahl.",
        "Nächste Prüfentscheidung": "Warum das wichtig ist: Erst fachlich prüfen, dann politisch bewerten — in dieser Reihenfolge bleibt der Bericht ehrlich.",
    }
    narrative_blocks = [
        {
            "heading": section["heading"],
            "body": section["body"],
            "reader_hint": narrative_hints.get(
                section["heading"],
                "Warum das wichtig ist: Diese Passage ordnet den Modelllauf vor der Detailprüfung ein.",
            ),
        }
        for section in professional_sections
    ]
    public_stage_labels = {
        "Berechnete Wirkpfade": "Wirkpfad der Simulation",
        "Relevante Kennzahlen": "Relevante Kennzahlen",
        "Einordnung und Belastbarkeit": "Einordnung",
    }
    public_briefing_sequence = [
        {
            "stage": public_stage_labels.get(block["heading"], block["heading"]),
            "body": block["body"],
            "reader_hint": block["reader_hint"],
        }
        for block in narrative_blocks
    ]
    public_briefing_text = "\n\n".join(
        ["Ergebnisbericht"]
        + [
            f"{step['stage']}\n{step['body']}"
            for step in public_briefing_sequence
        ]
    )
    # Backward-compatible alias for older UI/API callers; the new name is more
    # explicit that this is public reader-facing prose, not an internal packet dump.
    public_storyline = public_briefing_text
    reader_brief = "\n\n".join(
        f"{block['heading']}: {block['body']}\n{block['reader_hint']}" for block in narrative_blocks
    )
    reader_summary = (
        f"{lead_paragraph} "
        f"{policy_readiness_summary['why']} "
        "Die Lesart bleibt bewusst nüchtern: keine amtliche Prognose, kein Wirksamkeitsnachweis, "
        "sondern ein nachvollziehbarer SimMed-Wirkpfad mit Annahmen, Gegenchecks und nächster Prüfentscheidung."
    )
    professional_briefing = {
        "title": "Ergebnisbericht",
        "lead_paragraph": lead_paragraph,
        "reader_summary": reader_summary,
        "section_flow": section_flow,
        "sections": professional_sections,
        "narrative_blocks": narrative_blocks,
        "public_storyline": public_storyline,
        "reader_brief": reader_brief,
        "first_view_kpi_cards": first_view_kpi_cards,
        "sequential_text": "\n\n".join(
            ["Ergebnisbericht"]
            + [f"{block['heading']}\n{block['body']}\n{block['reader_hint']}" for block in narrative_blocks]
        ),
        "guardrail": RESULT_CAUSALITY_GUARDRAIL,
    }
    briefing_quality_checks = _briefing_quality_checks(
        professional_briefing,
        kpis,
        adaptation_trace,
        evidence_rows,
    )
    sequential_plain_text = professional_briefing["sequential_text"]

    if study_places_changed:
        coherent_story = (
            f"Ausgangspunkt: {changed_text} Ergebnis: {kpi_text} "
            f"Warum: Die Simulation liest Änderungen nicht als Einzelzahl, sondern als Wirkpfad über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
            f"Bei Medizinstudienplätzen ist der zentrale Punkt der Ausbildungs-Lag: ab etwa Jahr 6 kommen weniger Absolvent:innen an; "
            f"im 15-Jahres-Horizont sollte sich das in Ärzte pro 100k, Wartezeit und Burnout zeigen, sofern Anpassungsmechanismen es nicht sichtbar dämpfen. "
            f"Zeitverlauf: {timeline_text} "
            f"Anpassungsmechanismen: {mechanism_text} Beobachtete Signale: {adaptation_trace_text} Gegencheck: {counter_text}"
        )
    elif changed:
        coherent_story = (
            f"Ausgangspunkt: {changed_text} Ergebnis: {kpi_text} "
            "Warum: Die Simulation liest die Änderung nicht als Einzelzahl, sondern als Wirkpfad über den tatsächlich veränderten Hebel, die passenden Kennzahlen und dokumentierte Annahmen. "
            "Für diesen Lauf bleibt die erste Prüfung bei Finanzierung, Versorgungssignal und Belastbarkeitsgrenze; zusätzliche Zeitverzugsmechanismen werden nicht hineingelesen. "
            f"Zeitverlauf: {timeline_text} "
            f"Anpassungsmechanismen: {mechanism_text} Beobachtete Signale: {adaptation_trace_text} Gegencheck: {counter_text}"
        )
    else:
        coherent_story = (
            f"Ausgangspunkt: {changed_text} Ergebnis: {kpi_text} "
            "Warum: Die Simulation liest den Referenzpfad als Wirkpfad über Kapazität, Nachfrage, Finanzierung und Zeitverzug, ohne einen zusätzlichen Szenariohebel zu erfinden. "
            f"Zeitverlauf: {timeline_text} "
            f"Anpassungsmechanismen: {mechanism_text} Beobachtete Signale: {adaptation_trace_text} Gegencheck: {counter_text}"
        )

    result_headline = (
        "Weniger Medizinstudienplätze: der relevante Druck kommt verzögert"
        if study_places_changed
        else "Ergebnis: die wichtigsten Veränderungen im Modelllauf"
    )
    top_kpi_sentences = "; ".join(
        f"{item['label']} {item['direction']} ({str(item['start']).replace('.', ',')} → {str(item['end']).replace('.', ',')})"
        for item in kpis[:2]
    ) or "keine priorisierten Kennzahlen verfügbar"
    if study_places_changed:
        short_answer = (
            f"Rausgekommen ist: Weniger Medizinstudienplätze erzeugen verzögerten Kapazitätsdruck; wichtigste Signale: {top_kpi_sentences}. "
            "Warum? Über die Ausbildungs-Pipeline: ab etwa Jahr 6 kommt weniger Nachwuchs an, Richtung Jahr 11–15 wird der Facharztpfad wichtig. "
            "Was bedeutet das? Das bedeutet: als Nächstes Wartezeit, Belastung und Puffer prüfen, dann politisch bewerten."
        )
    elif changed:
        short_answer = (
            f"Geändert wurde: {changed_text} Relevant sind vor allem: {top_kpi_sentences}. "
            "Die Bewegung läuft über die dokumentierten SimMed-Pfade für Kapazität, Nachfrage, Finanzierung und regionale Verteilung. "
            "Als Nächstes sollten die stärkste Kennzahl und ihre Annahmengrenze geprüft werden."
        )
    else:
        short_answer = (
            f"Es wurde kein zusätzlicher Hebel verändert; relevant sind vor allem: {top_kpi_sentences}. "
            "Der Lauf zeigt den Referenzpfad selbst; als Nächstes sollten die stärkste Kennzahl und ihre Annahmengrenze geprüft werden."
        )

    relevant_kpis_public = [
        {
            **row,
            "start": _fmt_de_fixed(row.get("start"), decimals=2),
            "end": _fmt_de_fixed(row.get("end"), decimals=2),
            "abs_delta": _fmt_de_fixed(row.get("abs_delta"), decimals=2),
            "pct_delta": _fmt_de_fixed(row.get("pct_delta"), decimals=2),
            "direction": "stabil" if row.get("direction") == "bleibt stabil" else row.get("direction", "stabil"),
            "plain_change": (
                f"{_fmt_de_fixed(row.get('start'), decimals=2)} auf {_fmt_de_fixed(row.get('end'), decimals=2)}"
                f" ({'+' if str(row.get('abs_delta', '')).replace(',', '.').strip().startswith('-') is False else ''}{_fmt_de_fixed(row.get('abs_delta'), decimals=2)})"
            ),
            "display_value": f"{_fmt_de_fixed(row.get('start'), decimals=2)} → {_fmt_de_fixed(row.get('end'), decimals=2)}",
            "reading": _public_kpi_reading(
                str(row.get("metric_key", "")),
                "stabil" if row.get("direction") == "bleibt stabil" else str(row.get("direction", "stabil")),
            ),
            "meaning": row.get("meaning") or row.get("why_relevant", "Diese Kennzahl ordnet den Modelllauf ein."),
        }
        for row in kpis
    ]
    kpi_items = [
        f"{row['label']}: {row['start']} → {row['end']} ({row['direction']})"
        for row in relevant_kpis_public[:4]
    ]
    kpi_body = "; ".join(kpi_items) + "." if kpi_items else "Keine priorisierten Kennzahlen verfügbar."
    if study_places_changed:
        result_body = (
            "Heraus kommt ein späterer Kapazitätsdruck. Anfangs bleibt die Versorgung fast unverändert; später werden weniger Ärzt:innen, längere Wartezeiten und höhere Belastung relevant."
        )
    elif changed:
        result_body = (
            "Das Ergebnis zeigt die wichtigste Bewegung des Szenarios, ohne daraus schon eine politische Entscheidung zu machen."
        )
    else:
        result_body = "Das Ergebnis beschreibt den Referenzpfad ohne zusätzlichen Eingriff."
    if study_places_changed:
        why_body = (
            "Der Eingriff wirkt verzögert: In Jahr 0–5 ändert sich wenig; Ab etwa Jahr 6 kommt weniger Nachwuchs an, Richtung Jahr 11–15 zählt der Facharztpfad."
        )
    else:
        why_body = pathway_body[:180]

    observed_signals = []
    for signal in adaptation_trace[:2]:
        label = str(signal.get("label", "Signal"))
        direction = str(signal.get("observed_direction", "ändert sich"))
        observed_signals.append(f"{label} {direction}")
    observed_text = "; ".join(observed_signals) or "kein starkes Puffersignal sichtbar"
    adaptation_body = (
        f"Das Modell prüft Puffer wie Telemedizin; beobachtet: {observed_text}. "
        "Fällt Belastung trotz Mangel, braucht es einen klaren Puffer, sonst ist es ein Plausibilitätscheck."
    )
    result_sections = [
        {"heading": "Ergebnis", "body": result_body},
        {"heading": "Eingriff", "body": changed_text},
        {"heading": "Warum es passiert", "body": why_body},
        {"heading": "Relevante Kennzahlen", "body": kpi_body},
        {"heading": "Anpassungen", "body": adaptation_body},
        {
            "heading": "Einordnung",
            "body": (
                "Das bedeutet: einen prüfbaren SimMed-Wirkpfad, keine fertige politische Entscheidung; "
                "keine amtliche Prognose, kein Wirksamkeitsnachweis."
            ),
        },
        {
            "heading": "Nächster Prüfschritt",
            "body": "Zuerst Zeitfenster, relevante Kennzahlen und Evidenzgrenzen prüfen; danach politisch bewerten.",
        }
    ]
    follow_up_question = (
        "Nächster Check: Passen die sichtbaren Puffer im Modell zur späteren Kapazitätslücke — oder muss der Ausbildungs-/Facharztpfad nachgeschärft werden?"
        if study_places_changed
        else "Welche Annahme begrenzt die wichtigste beobachtete Kennzahl am stärksten?"
    )

    first_screen_blocks = []
    for section in result_sections:
        block = {
            "heading": section["heading"],
            "body": section["body"][:240],
            "display": "kpi_rows" if section["heading"] == "Relevante Kennzahlen" else "text",
            "primary_answer": section["heading"] == "Ergebnis",
        }
        if section["heading"] == "Relevante Kennzahlen":
            block["kpi_refs"] = [str(row.get("metric_key", "")) for row in relevant_kpis_public]
        first_screen_blocks.append(block)

    audit_sections = [
        {
            "id": "mechanism_audit",
            "title": "Wirkpfad und Plausibilität prüfen",
            "contains": "Zeitfenster, Anpassungsreaktionen und gegenintuitive Signale",
            "default_expanded": False,
        },
        {
            "id": "evidence_audit",
            "title": "Evidenz und Annahmen prüfen",
            "contains": "Evidenzgrade, Quellen, Unsicherheit und Registry-Caveats",
            "default_expanded": False,
        },
        {
            "id": "legacy_details",
            "title": "Weitere Detailansichten öffnen",
            "contains": "vollständige Kennzahlen, Trend, Policy-Briefing und politische Einordnung",
            "default_expanded": False,
        },
    ]

    executive_brief_blocks = []
    for section in result_sections:
        block = {
            "heading": section["heading"],
            "body": section["body"],
            "kind": "compact_kpi_rows" if section["heading"] == "Relevante Kennzahlen" else "text",
        }
        if section["heading"] == "Relevante Kennzahlen":
            block["component"] = "readable_metric_cards"
            block["rows"] = relevant_kpis_public[:4]
        executive_brief_blocks.append(block)
    executive_brief = {
        "title": result_headline,
        "lead": short_answer,
        "blocks": executive_brief_blocks,
        "audit_hint": "Details bleiben darunter geschlossen: Zeitfenster, Evidenz, vollständige Kennzahlen und politische Einordnung.",
    }

    kpi_lines = "\n".join(
        f"- **{row.get('label', 'Kennzahl')}**: {row.get('start', '–')} → {row.get('end', '–')} "
        f"({row.get('direction', 'stabil')}). {row.get('meaning') or row.get('why_relevant', '')}"
        for row in relevant_kpis_public[:4]
    ) or "- Keine priorisierten Kennzahlen verfügbar."
    briefing_parts = [f"### {result_headline}", short_answer]
    for section in result_sections:
        briefing_parts.append(f"#### {section['heading']}")
        if section["heading"] == "Relevante Kennzahlen":
            briefing_parts.append(kpi_lines)
        else:
            briefing_parts.append(section["body"])
    briefing_markdown = "\n\n".join(briefing_parts)

    public_result_view = {
        "briefing_style": "single_readable_briefing",
        "first_screen_policy": "one_briefing_then_collapsed_audit",
        "render_order": [
            "result_headline",
            "short_answer",
            "result_sections",
            "relevant_kpis",
            "follow_up_question",
            "collapsed_audit_sections",
        ],
        "headline": result_headline,
        "short_answer": short_answer,
        "briefing_markdown": briefing_markdown,
        "executive_brief": executive_brief,
        "result_sections": result_sections,
        "first_screen_blocks": first_screen_blocks,
        "primary_blocks": first_screen_blocks,
        "relevant_kpis": relevant_kpis_public,
        "follow_up_question": follow_up_question,
        "render_follow_up_after_sections": False,
        "audit_sections": audit_sections,
        "deeper_review_default_expanded": False,
        "legacy_detail_default_expanded": False,
        "dense_kpi_default_expanded": False,
        "audit_expanders": [
            "Zeitfenster, Annahmen und Plausibilität",
            "vollständige Kennzahlen und Einzelprüfungen",
            "Trend, Policy-Briefing und politische Einordnung",
        ],
        "guardrail": RESULT_CAUSALITY_GUARDRAIL,
    }

    return {
        "title": "Ergebnisbericht",
        "result_headline": result_headline,
        "short_answer": short_answer,
        "result_sections": result_sections,
        "executive_brief": executive_brief,
        "follow_up_question": follow_up_question,
        "audit_sections": audit_sections,
        "public_result_view": public_result_view,
        "subtitle": "Relevante Kennzahlen und ein zusammenhängender Wirkpfad von Ausgangslage bis Einordnung.",
        "reading_order": [
            "1 · geänderte Eingriffe",
            "2 · relevante KPIs",
            "3 · Wirkpfad und Timing",
            "4 · Anpassungsmechanismen",
            "5 · Gegencheck/Caveat",
        ],
        "changed_inputs": changed,
        "evidence_assumption_rows": evidence_rows,
        "relevant_kpis": relevant_kpis_public,
        "relevant_kpi_summary": kpi_summary,
        "adaptation_mechanisms": mechanisms,
        "adaptation_signal_trace": adaptation_trace,
        "timeline_windows": timeline_windows,
        "counterintuitive_findings": counter,
        "free_text_blocks": free_text_blocks,
        "primary_result_view": {
            "briefing_style": "single_readable_briefing",
            "headline": result_headline,
            "short_answer": short_answer,
            "result_sections": result_sections,
            "executive_brief": executive_brief,
            "first_screen_blocks": first_screen_blocks,
            "primary_blocks": first_screen_blocks,
            "relevant_kpis": relevant_kpis_public,
            "follow_up_question": follow_up_question,
            "audit_sections": audit_sections,
            "deeper_review_default_expanded": False,
            "render_sequence": [
                "headline",
                "short_answer",
                "result_sections",
                "relevant_kpis",
                "follow_up_question",
                "collapsed_detailprüfung",
            ],
            # Legacy/diagnostic fields stay available for collapsed review surfaces and older callers.
            "main_blocks": free_text_blocks,
            "legacy_numbered_story": legacy_numbered_story,
            "sequential_plain_text": sequential_plain_text,
            "professional_briefing": professional_briefing,
            "professional_briefing_text": reader_brief,
            "public_storyline": public_storyline,
            "lead_paragraph": lead_paragraph,
            "section_flow": section_flow,
            "public_briefing_sequence": public_briefing_sequence,
            "first_view_briefing_cards": first_view_briefing_cards,
            "first_view_kpi_cards": first_view_kpi_cards,
            "policy_readiness_summary": policy_readiness_summary,
            "next_check": {
                "label": "Nächster Prüfschritt",
                "text": follow_up_question,
            },
            "optional_audit_layers": {
                "expanded_by_default": False,
                "reason": (
                    "Detailprüfungen bleiben verfügbar, stehen aber unter dem kurzen Ergebnisbericht. "
                    "So bleibt die erste Ansicht lesbar: erst Ergebnis, dann Prüfung."
                ),
            },
            "cleartext_reading_cards": cleartext_reading_cards,
            "relevant_kpi_summary": kpi_summary,
            "adaptation_mechanisms": mechanisms,
            "adaptation_signal_trace": adaptation_trace,
            "timeline_windows": timeline_windows,
            "evidence_assumption_rows": evidence_rows,
            "briefing_quality_checks": briefing_quality_checks,
            "optional_details_after": [
                "Kennzahlen im Detail",
                "Zeitverlauf",
                "Bericht mit Annahmen und Quellen",
                "politische Einordnung",
            ],
            "guardrail": RESULT_CAUSALITY_GUARDRAIL,
        },
        "story_sections": story_sections,
        "professional_briefing": professional_briefing,
        "public_briefing_sequence": public_briefing_sequence,
        "public_briefing_text": public_briefing_text,
        "first_view_briefing_cards": first_view_briefing_cards,
        "policy_readiness_summary": policy_readiness_summary,
        "briefing_quality_checks": briefing_quality_checks,
        "legacy_numbered_story": legacy_numbered_story,
        "sequential_plain_text": sequential_plain_text,
        "coherent_story": coherent_story,
        "method_note": RESULT_CAUSALITY_GUARDRAIL,
        "guardrail": RESULT_CAUSALITY_GUARDRAIL,
    }
