"""Structured policy-briefing report builder for SimMed results."""

from typing import Dict, List, Any

import pandas as pd

from baseline_projection import build_baseline_projection
from international_reforms import list_international_reforms


def _default_params() -> Dict[str, Any]:
    # Local import avoids circular import at module import time.
    from app import get_default_params

    return get_default_params()


_PARAM_LABELS = {
    "telemedizin_rate": "Telemedizin",
    "digitalisierung_epa": "ePA/Digitalisierung",
    "praeventionsbudget": "Präventionsbudget",
    "medizinstudienplaetze": "Medizinstudienplätze",
    "bevoelkerung_mio": "Bevölkerung",
    "netto_zuwanderung": "Nettozuwanderung",
    "gkv_beitragssatz_basis": "GKV-Beitragssatz Basis",
}


def _changed_levers(params: Dict[str, Any]) -> List[Dict[str, str]]:
    defaults = _default_params()
    changes: List[Dict[str, str]] = []
    for key, value in params.items():
        if key not in defaults or defaults[key] == value:
            continue
        base = defaults[key]
        changes.append({
            "key": key,
            "label": _PARAM_LABELS.get(key, key.replace("_", " ").title()),
            "baseline": str(base),
            "scenario": str(value),
            "summary": f"{_PARAM_LABELS.get(key, key)} wurde von {base} auf {value} geändert.",
        })
    return changes


def _kpi_movements(agg: pd.DataFrame) -> List[Dict[str, str]]:
    labels = {
        "gesundheitsausgaben_mrd": "Gesundheitsausgaben",
        "gkv_saldo": "GKV-Saldo",
        "wartezeit_fa": "Facharzt-Wartezeit",
        "aerzte_pro_100k": "Ärzte / 100k",
        "lebenserwartung": "Lebenserwartung",
        "kollaps_wahrscheinlichkeit": "Kollaps-Risiko",
        "zufriedenheit_patienten": "Patientenzufriedenheit",
    }
    first, last = agg.iloc[0], agg.iloc[-1]
    out: List[Dict[str, str]] = []
    for key, label in labels.items():
        col = f"{key}_mean"
        if col not in agg.columns:
            continue
        start = float(first[col])
        end = float(last[col])
        delta = end - start
        out.append({
            "key": key,
            "label": label,
            "start": f"{start:.2f}",
            "end": f"{end:.2f}",
            "delta": f"{delta:+.2f}",
            "summary": f"{label}: {start:.2f} → {end:.2f} ({delta:+.2f}).",
        })
    return sorted(out, key=lambda item: abs(float(item["delta"])), reverse=True)


def build_simulation_report(agg: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """Build a structured, mobile-friendly policy briefing from a simulation."""
    baseline = build_baseline_projection()
    changes = _changed_levers(params)
    movements = _kpi_movements(agg)
    change_text = ", ".join(item["label"] for item in changes) if changes else "keine Parameter gegenüber dem Referenzpfad"
    top_movements = "; ".join(item["summary"] for item in movements[:3]) if movements else "Noch keine KPI-Bewegungen verfügbar."
    reforms = list_international_reforms()[:3]

    sections = [
        {
            "id": "executive_summary",
            "title": "Executive Summary",
            "summary": (
                f"Dieses Policy-Briefing erklärt die Simulation ausgehend von der Deutschland-Baseline. "
                f"Geändert wurden: {change_text}. Wichtigste beobachtete Bewegungen: {top_movements}"
            ),
            "detail_items": ["Dashboard zuerst lesen, danach die größten KPI-Bewegungen und kausalen Pfade prüfen."],
            "caveats": ["Die Simulation ist ein transparenter Modellpfad, keine amtliche Prognose."],
        },
        {
            "id": "baseline",
            "title": "Deutschland-Baseline und Referenzprojektion",
            "summary": baseline["plain_language_summary"],
            "detail_items": [f"{section['title']}: " + "; ".join(item["label"] for item in section["items"]) for section in baseline["sections"]],
            "caveats": ["Aktuelle Messwerte, externe Projektionen und SimMed-Annahmen müssen sichtbar getrennt bleiben."],
        },
        {
            "id": "scenario_changes",
            "title": "Deine Änderungen gegenüber dem Referenzpfad",
            "summary": f"SimMed vergleicht dein Szenario mit der Deutschland-Baseline. Geändert: {change_text}.",
            "detail_items": [item["summary"] for item in changes] or ["Keine geänderten Hebel; dies ist der Referenzpfad."],
            "caveats": ["Parameteränderungen sind Szenarioannahmen und noch keine politische Umsetzung."],
        },
        {
            "id": "causal_pathways",
            "title": "Kausale Pfade: Warum bewegt sich etwas?",
            "summary": "Geänderte Hebel wirken über Nachfrage, Kapazität, Zugang, Finanzierung, Digitalisierung und politische Umsetzbarkeit.",
            "detail_items": [
                "Telemedizin/Digitalisierung wirken vor allem auf Zugang, Koordination und teilweise Wartezeiten — nicht automatisch auf Gesamtkosten.",
                "Ärzte- und Studienplatzänderungen wirken verzögert über Ausbildung, Weiterbildung und regionale Verteilung.",
                "Finanzierungshebel verändern GKV-Druck, Akzeptanz und politische Konflikte.",
            ],
            "caveats": ["Direkte und indirekte Effekte müssen getrennt gelesen werden."],
        },
        {
            "id": "kpi_deep_dives",
            "title": "KPI Deep Dives",
            "summary": "Die wichtigsten Kennzahlen werden nach Bewegungsstärke sortiert und mit Start, Ende und Lesart erklärt.",
            "detail_items": [item["summary"] for item in movements],
            "related_kpis": [item["label"] for item in movements[:5]],
        },
        {
            "id": "international_comparison",
            "title": "Was machen andere Länder?",
            "summary": "Internationale Reformen dienen als Lern- und Vergleichsfälle, nicht als 1:1-Vorhersage für Deutschland.",
            "detail_items": [f"{r['country']}: {r['policy_name']} — Vergleichbarkeit: {r['comparability_to_germany']}" for r in reforms],
            "caveats": ["Ausländische Effekte müssen vor der deutschen Simulation übersetzt und mit Caveats versehen werden."],
        },
        {
            "id": "political_feasibility",
            "title": "Politische und praktische Umsetzbarkeit",
            "summary": "Reformen brauchen Unterstützer, institutionelle Zuständigkeiten, Umsetzungszeit und Akzeptanz. Diese Einordnung ist qualitativ, keine Prognose.",
            "detail_items": ["Prüfe betroffene Akteure, Umsetzungslag, Bundes-/Länderzuständigkeiten und Selbstverwaltung."],
            "caveats": ["Keine Wahlprognose, kein Lobby-Ranking, keine rechtliche Beratung."],
        },
        {
            "id": "sources_evidence_assumptions",
            "title": "Quellen, Evidenz und Annahmen",
            "summary": "Jede wichtige Aussage soll als aktuelle Messung, externe Projektion oder SimMed-Annahme erkennbar sein.",
            "detail_items": ["Evidenzgrade A-E sichtbar machen.", "Schwache oder fehlende Daten nicht verstecken, sondern als Platzhalter markieren."],
            "evidence_refs": [item["source"] for section in baseline["sections"] for item in section["items"]],
        },
    ]
    return {"title": "Policy-Briefing", "sections": sections}
