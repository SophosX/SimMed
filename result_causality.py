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
                "next_check": "Als Teil der Klartext-Geschichte lesen, nicht als KPI-Wand; danach Detailkarte/Trend öffnen.",
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
                "guardrail": f"{RESULT_CAUSALITY_GUARDRAIL} Das Signal beschreibt Modellverhalten, keine amtliche Prognose.",
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


def _timeline_windows(params: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return human-readable timing checkpoints for delayed policy effects."""
    defaults = get_default_params()
    study_places_cut = float(params.get("medizinstudienplaetze", defaults["medizinstudienplaetze"])) < float(defaults["medizinstudienplaetze"])
    if not study_places_cut:
        return []
    guardrail = f"{RESULT_CAUSALITY_GUARDRAIL} Zeitfenster sind SimMed-Annahmen/Prüfpunkte, keine amtliche Prognose."
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
        "first_view": str(packet.get("title", "Simulationsergebnis in Klartext")),
        "primary_sequence": [
            "coherent_free_text",
            "relevant_kpis",
            "adaptation_mechanisms",
            "counterintuitive_checks",
            "evidence_assumptions",
        ],
        "dense_kpi_wall": {
            "label": "Optionale KPI-Wand / Detailkarten erst nach dem Klartext",
            "mode": "optional_expander_after_causal_story",
            "default_expanded": False,
            "reason": (
                "Die KPI-Wand ist nicht die erste Ansicht, weil Alex zuerst Output, Änderung, "
                "Wirkpfad, Anpassung und Caveat als zusammenhängende Geschichte lesen soll."
            ),
        },
        "optional_interpretation_layers": {
            "label": "Optionale Vertiefungen erst nach dem Klartext",
            "mode": "collapsed_after_primary_causal_packet",
            "default_expanded": False,
            "sections": [
                "Narrative Zusammenfassung",
                "Entscheidungs-Checkpoints",
                "Storyboard",
                "Unsicherheitsband",
            ],
            "reason": (
                "Diese bestehenden Hilfen bleiben als Audit-Layer erhalten, sind aber keine zweite erste Ergebnisansicht; "
                "die primäre Interpretation kommt aus dem causal_result_packet."
            ),
        },
        "optional_details_after": packet.get("primary_result_view", {}).get(
            "optional_details_after",
            ["KPI-Drilldowns", "Trend", "Policy-Briefing", "Politik/Stakeholder"],
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
    kpis = _relevant_kpis(agg, max_kpis=max_kpis)
    kpi_summary = _relevant_kpi_summary(kpis, changed)
    mechanisms = _adaptation_mechanisms(params, kpis)
    adaptation_trace = _adaptation_signal_trace(kpis, params)
    timeline_windows = _timeline_windows(params)
    counter = _counterintuitive_findings(kpis, params)
    changed_text = " ".join(item["change"] for item in changed) or "Keine zentrale Stellschraube wurde gegenüber dem Standardpfad verändert."
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

    free_text_blocks = [
        {
            "step": "1. Ergebnis",
            "text": f"Der Lauf wird zuerst über wenige relevante KPIs gelesen: {kpi_text}",
        },
        {
            "step": "2. Änderung",
            "text": changed_text,
        },
        {
            "step": "3. Wirkmechanismus",
            "text": (
                "SimMed verbindet Eingriffe über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
                "Bei Medizinstudienplätzen ist der zentrale Mechanismus die Ausbildungs-Pipeline: "
                "ab etwa Jahr 6 kommen weniger Absolvent:innen an, danach steigt der Facharzt-/Kapazitätsdruck. "
                f"Zeitfenster: {timeline_text}"
            ),
        },
        {
            "step": "4. Anpassung",
            "text": f"{mechanism_text} Beobachtete Signale: {adaptation_trace_text}",
        },
        {
            "step": "5. Gegencheck",
            "text": counter_text,
        },
        {
            "step": "6. Evidenzgrenze",
            "text": (
                f"{evidence_text} {RESULT_CAUSALITY_GUARDRAIL} Evidenzgrade und Registry-Caveats begrenzen die Interpretation; "
                "diese Erklärung ist ein lokaler Modelllauf, keine freie Web-Recherche und keine automatische Parameterintegration."
            ),
        },
    ]

    sequential_plain_text = "\n\n".join(
        ["Simulationsergebnis in Klartext"]
        + [f"{block['step']}\n{block['text']}" for block in free_text_blocks]
    )

    cleartext_reading_cards = [
        {
            "stage": "Ergebnis",
            "answer_first": free_text_blocks[0]["text"],
            "audit_focus": "nur die priorisierten relevanten KPIs lesen",
            "next_step": "Danach Änderung und Wirkpfad öffnen, nicht die KPI-Wand zuerst.",
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
            "guardrail": f"{RESULT_CAUSALITY_GUARDRAIL} Keine amtliche Prognose und kein Policy-Wirksamkeitsnachweis.",
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
            "heading": "Welche Evidenz-/Annahmegrenze gilt?",
            "text": free_text_blocks[5]["text"],
        },
    ]

    coherent_story = (
        f"Ausgangspunkt: {changed_text} Ergebnis: {kpi_text} "
        f"Warum: Die Simulation liest Änderungen nicht als Einzelzahl, sondern als Wirkpfad über Kapazität, Nachfrage, Finanzierung und Zeitverzug. "
        f"Bei Medizinstudienplätzen ist der zentrale Punkt der Ausbildungs-Lag: ab etwa Jahr 6 kommen weniger Absolvent:innen an; "
        f"im 15-Jahres-Horizont sollte sich das in Ärzte pro 100k, Wartezeit und Burnout zeigen, sofern Anpassungsmechanismen es nicht sichtbar dämpfen. "
        f"Zeitverlauf: {timeline_text} "
        f"Anpassungsmechanismen: {mechanism_text} Beobachtete Signale: {adaptation_trace_text} Gegencheck: {counter_text}"
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
        "evidence_assumption_rows": evidence_rows,
        "relevant_kpis": kpis,
        "relevant_kpi_summary": kpi_summary,
        "adaptation_mechanisms": mechanisms,
        "adaptation_signal_trace": adaptation_trace,
        "timeline_windows": timeline_windows,
        "counterintuitive_findings": counter,
        "free_text_blocks": free_text_blocks,
        "primary_result_view": {
            "headline": "Erst Klartext, dann Details",
            "main_blocks": free_text_blocks,
            "sequential_plain_text": sequential_plain_text,
            "cleartext_reading_cards": cleartext_reading_cards,
            "relevant_kpis": kpis,
            "relevant_kpi_summary": kpi_summary,
            "adaptation_mechanisms": mechanisms,
            "adaptation_signal_trace": adaptation_trace,
            "timeline_windows": timeline_windows,
            "evidence_assumption_rows": evidence_rows,
            "optional_details_after": ["KPI-Drilldowns", "Trend", "Policy-Briefing", "Politik/Stakeholder"],
        },
        "story_sections": story_sections,
        "sequential_plain_text": sequential_plain_text,
        "coherent_story": coherent_story,
        "method_note": RESULT_CAUSALITY_GUARDRAIL,
        "guardrail": RESULT_CAUSALITY_GUARDRAIL,
    }
