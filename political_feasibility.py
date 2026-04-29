"""Plain-language political feasibility rubric for SimMed scenarios.

This module is intentionally separate from ``simulation_core.py``: it does not
change numeric simulation outputs. It turns selected policy levers into a
transparent, auditable explanation of implementation realism, likely supporters,
likely blockers and the assumptions that should later be source-backed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


RUBRIC_VERSION = "simmed-feasibility-rubric-v0.1"


@dataclass(frozen=True)
class LeverFeasibilityRule:
    """Qualitative rule for one policy lever.

    The score is a rough explanation aid, not a validated political forecast.
    Positive values mean easier implementation; negative values mean more
    friction. Keep this plain-language and cite/source rules before making them
    consequential for scoring or leaderboards.
    """

    key: str
    label: str
    plain_language_effect: str
    likely_supporters: tuple[str, ...]
    likely_blockers: tuple[str, ...]
    implementation_lag: str
    political_friction: str
    score_delta: int
    caveat: str


LEVER_RULES: Dict[str, LeverFeasibilityRule] = {
    "telemedizin_rate": LeverFeasibilityRule(
        key="telemedizin_rate",
        label="Telemedizin ausbauen",
        plain_language_effect=(
            "Mehr digitale Kontakte können Wege und einfache Praxisbesuche sparen. "
            "Der Nutzen kommt aber nur, wenn Praxen, Patient:innen und Vergütung mitziehen."
        ),
        likely_supporters=("Patient:innen mit langen Wegen", "digitale Anbieter", "Teile der Krankenkassen"),
        likely_blockers=("Praxen mit Umstellungsaufwand", "Datenschutz-/Sicherheitsbedenken", "Gruppen mit geringer digitaler Teilhabe"),
        implementation_lag="kurz bis mittel: Technik geht schneller als Alltagsnutzung und Vergütungsregeln",
        political_friction="mittel",
        score_delta=1,
        caveat="Digitalisierung ist kein automatischer Kostensenker; es gibt Anlaufkosten und ungleiche Nutzung.",
    ),
    "digitalisierung_epa": LeverFeasibilityRule(
        key="digitalisierung_epa",
        label="ePA/Digitalisierung stärken",
        plain_language_effect=(
            "Bessere digitale Daten können Doppelarbeit verringern und Behandlungsabläufe verständlicher machen. "
            "Der Effekt hängt stark von Akzeptanz, Datenschutz, Schnittstellen und Schulung ab."
        ),
        likely_supporters=("gematik/BfArM-nahe Digitalakteure", "Teile der Krankenkassen", "Versorgungsforscher:innen"),
        likely_blockers=("Datenschutzbedenken", "IT-belastete Leistungserbringer", "Akteure mit schlechten Schnittstellen"),
        implementation_lag="mittel: Infrastruktur plus Verhaltensänderung",
        political_friction="mittel",
        score_delta=0,
        caveat="Produktivitätsgewinne müssen belegt werden und treten nicht überall gleichzeitig auf.",
    ),
    "praeventionsbudget": LeverFeasibilityRule(
        key="praeventionsbudget",
        label="Prävention finanzieren",
        plain_language_effect=(
            "Mehr Prävention kann Krankheit später vermeiden. Kurzfristig kostet sie aber Geld, "
            "und Einsparungen zeigen sich oft erst nach Jahren."
        ),
        likely_supporters=("Public-Health-Akteure", "Patientengruppen", "Kommunen mit Präventionsprogrammen"),
        likely_blockers=("kurzfristige Budgethüter", "Akteure mit unklarer Zuständigkeit", "Skeptiker bei schwer messbarer Wirkung"),
        implementation_lag="lang: Gesundheitswirkungen entstehen verzögert",
        political_friction="mittel",
        score_delta=0,
        caveat="Nicht jede Prävention spart sofort Geld; manche Programme erhöhen zunächst Ausgaben.",
    ),
    "medizinstudienplaetze": LeverFeasibilityRule(
        key="medizinstudienplaetze",
        label="Medizinstudienplätze verändern",
        plain_language_effect=(
            "Mehr oder weniger Studienplätze verändern die Arztzahl nicht sofort. Erst nach Studium und Weiterbildung "
            "wird der Effekt in der Versorgung spürbar."
        ),
        likely_supporters=("Länder und Hochschulen bei Ausbaufinanzierung", "BÄK/ärztliche Verbände bei Nachwuchssicherung", "ländliche Regionen"),
        likely_blockers=("Finanzministerien wegen Ausbildungskosten", "Universitäten mit Kapazitätsgrenzen", "Akteure, die kurzfristige Effekte erwarten"),
        implementation_lag="lang: etwa 6+ Jahre bis Absolvent:innen, 11–13+ Jahre bis Fachärzt:innen",
        political_friction="hoch",
        score_delta=-1,
        caveat="Der Modellkern bildet die Verzögerung ab; politische Kommunikation muss erklären, dass kurzfristig kaum Angebotseffekt entsteht.",
    ),
    "pflegepersonal_schluessel": LeverFeasibilityRule(
        key="pflegepersonal_schluessel",
        label="Pflegepersonal-Schlüssel verbessern",
        plain_language_effect=(
            "Bessere Personalschlüssel können Qualität und Arbeitsbedingungen verbessern. "
            "Sie brauchen aber reale Fachkräfte und verlässliche Finanzierung."
        ),
        likely_supporters=("Pflegekräfte", "Patientenschutz", "Qualitätsakteure"),
        likely_blockers=("Krankenhausträger unter Kostendruck", "Budgetakteure", "Einrichtungen mit Personalmangel"),
        implementation_lag="mittel bis lang: Regel kann schnell kommen, Personalaufbau dauert",
        political_friction="hoch",
        score_delta=-1,
        caveat="Betten oder Regeln schaffen keine Kapazität, wenn Personal fehlt.",
    ),
}


def _changed_keys(parameter_changes: Dict[str, Any]) -> Iterable[str]:
    for key, value in parameter_changes.items():
        if value is not None:
            yield key


def assess_political_feasibility(parameter_changes: Dict[str, Any]) -> Dict[str, Any]:
    """Return a transparent feasibility explanation for changed scenario levers.

    The result is deterministic and suitable for API/UI display. It is not a
    partisan recommendation and not yet a validated score.
    """

    matched_rules: List[LeverFeasibilityRule] = [
        LEVER_RULES[key] for key in _changed_keys(parameter_changes) if key in LEVER_RULES
    ]
    raw_score = sum(rule.score_delta for rule in matched_rules)
    if not matched_rules:
        category = "noch nicht bewertet"
        summary = "Für diese Parameter gibt es noch keine politische Umsetzbarkeitsregel."
    elif raw_score >= 1:
        category = "eher gut umsetzbar"
        summary = "Die gewählten Hebel wirken politisch vergleichsweise anschlussfähig, haben aber weiterhin Umsetzungsbedingungen."
    elif raw_score <= -1:
        category = "politisch anspruchsvoll"
        summary = "Die gewählten Hebel berühren starke Zuständigkeiten, Budgets oder Berufsgruppen und brauchen klare Umsetzungsschritte."
    else:
        category = "mittel"
        summary = "Die Reform ist erklärbar, aber es gibt relevante Reibung bei Finanzierung, Akzeptanz oder Zuständigkeit."

    return {
        "rubric_version": RUBRIC_VERSION,
        "status": "explanation_only_not_validated_forecast",
        "category": category,
        "summary": summary,
        "score_hint": raw_score,
        "score_explanation": "Positiv = weniger Reibung, negativ = mehr Reibung; noch kein offizieller Wettbewerbs-Score.",
        "lever_notes": [
            {
                "key": rule.key,
                "label": rule.label,
                "why_it_matters": rule.plain_language_effect,
                "likely_supporters": list(rule.likely_supporters),
                "likely_blockers": list(rule.likely_blockers),
                "implementation_lag": rule.implementation_lag,
                "political_friction": rule.political_friction,
                "caveat": rule.caveat,
            }
            for rule in matched_rules
        ],
        "next_strategy_mode_step": (
            "Später kann Strategie-Modus daraus Reihenfolge, Bündnisse, Vetospieler, Framing, "
            "Kompromisspakete und Gesetzgebungsfenster ableiten."
        ),
    }
