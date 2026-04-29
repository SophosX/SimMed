"""Baseline/reference projection metadata for SimMed.

This module separates current measurements, external projection inputs and
SimMed assumptions. It does not change simulation math; it creates structured
explanation data for UI/reporting.
"""

from typing import Dict, List


def _item(label: str, value: str, layer: str, evidence_grade: str, source: str, caveat: str) -> Dict[str, str]:
    return {
        "label": label,
        "value": value,
        "layer": layer,
        "evidence_grade": evidence_grade,
        "source": source,
        "caveat": caveat,
    }


def build_baseline_projection() -> Dict[str, object]:
    """Return the structured Germany baseline + reference projection description."""
    sections: List[Dict[str, object]] = [
        {
            "id": "demography",
            "title": "Demografie",
            "items": [
                _item("Aktuelle Bevölkerung", "ca. 84 Mio.", "current_measurement", "A", "Destatis/GENESIS", "Aktueller Messwert; Quelle und Jahr müssen im Datenlayer präzisiert werden."),
                _item("Bevölkerungsentwicklung bis 2040", "Referenzpfad", "external_projection", "A", "Destatis koordinierte Bevölkerungsvorausberechnung", "Externe Projektion, keine sichere Vorhersage."),
            ],
        },
        {
            "id": "financing",
            "title": "Finanzierung und Ausgaben",
            "items": [
                _item("Gesundheitsausgaben/GKV-Druck", "heutiger Ausgangswert + Trend", "current_measurement", "B", "BMG, BAS, GKV-Spitzenverband, Destatis", "Aktuelle Finanzdaten sind messbar; künftige Beitragssatzreaktionen sind Modellannahmen."),
                _item("Politische Finanzierungsreaktion", "regelbasierte Reaktion", "simmed_assumption", "E", "SimMed Modellannahme", "Beiträge, Zuschüsse oder Leistungskürzungen werden vereinfacht modelliert."),
            ],
        },
        {
            "id": "workforce_access",
            "title": "Personal, Kapazität und Zugang",
            "items": [
                _item("Ärztebestand und Arztdichte", "heutiger Ausgangswert", "current_measurement", "B", "Bundesärztekammer, KBV/Zi", "Kopfzahl ist nicht gleich Kapazität; Arbeitszeit, Fachrichtung und Region fehlen teilweise."),
                _item("Ärzte-Pipeline bis 2040", "verzögerter Referenzpfad", "simmed_assumption", "D", "HRK/Destatis + SimMed Pipeline", "Studienplätze wirken erst nach Ausbildung und Weiterbildung deutlich."),
            ],
        },
        {
            "id": "digital_prevention",
            "title": "Digitalisierung und Prävention",
            "items": [
                _item("Telemedizin/ePA-Ausgangslage", "aktueller Adoptionsstand", "current_measurement", "C", "gematik, BMG, KBV, BfArM", "Datenlage je nach Indikator uneinheitlich; Wirkung nicht automatisch kostensenkend."),
                _item("Präventionswirkung", "verzögerter Modellpfad", "simmed_assumption", "D", "RKI/GBE + SimMed Annahme", "Prävention wirkt langfristig und krankheitsspezifisch; kurzfristige Einsparungen sind unsicher."),
            ],
        },
    ]
    return {
        "name": "Deutschland-Baseline + Referenzprojektion bis 2040",
        "short_name": "Deutschland-Baseline",
        "projection_label": "Referenzprojektion",
        "plain_language_summary": (
            "SimMed startet mit der aktuellen Deutschland-Baseline und simuliert daraus einen "
            "Referenzpfad bis 2040. Das ist keine amtliche Prognose, sondern ein transparenter "
            "Vergleichsstandard: aktuelle Messwerte, externe Projektionen und SimMed-Annahmen "
            "werden getrennt ausgewiesen."
        ),
        "sections": sections,
    }
