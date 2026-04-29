"""International reform examples and Germany-transfer helpers.

International evidence is treated as scenario input, never as a direct prediction
for Germany.
"""

from typing import Dict, List

_REFORMS: List[Dict[str, object]] = [
    {
        "id": "dk_digital_primary_access",
        "country": "Dänemark",
        "policy_name": "Digitale Zugangswege und starke Primärversorgung",
        "policy_area": "Digitalisierung / Primärversorgung",
        "target_problem": "Zugang steuern, unnötige Kontakte reduzieren und Versorgung koordinieren.",
        "reported_outcomes": [
            "höhere digitale Kontakt- und Koordinationsfähigkeit",
            "bessere Orientierung im Versorgungspfad",
        ],
        "evidence_grade": "C",
        "comparability_to_germany": "mittel",
        "transfer_caveat": "Dänemark ist kleiner und institutionell anders organisiert; Effekte sind nicht 1:1 auf Deutschland übertragbar.",
        "suggested_parameter_changes": {"telemedizin_rate": "+5 bis +15 Prozentpunkte", "digitalisierung_epa": "+10 bis +25 Prozentpunkte"},
        "confidence": "explorativ",
        "sources": ["OECD/European Observatory country profiles", "WHO Europe", "nationale Digital-Health-Berichte"],
    },
    {
        "id": "nl_gatekeeping_primary_care",
        "country": "Niederlande",
        "policy_name": "Starke Hausarztsteuerung / Gatekeeping",
        "policy_area": "Primärversorgung / Zugang",
        "target_problem": "Facharztzugang koordinieren und Nachfrage in die passende Versorgungsebene lenken.",
        "reported_outcomes": [
            "klarere Patientenpfade",
            "potenzielle Entlastung fachärztlicher Versorgung bei stärkerer Primärversorgung",
        ],
        "evidence_grade": "C",
        "comparability_to_germany": "mittel",
        "transfer_caveat": "Deutschlands freie Arztwahl, KVen-Struktur und Facharztlandschaft unterscheiden sich stark; Effekte sind nicht 1:1 auf Deutschland übertragbar.",
        "suggested_parameter_changes": {"hausarztpraxen": "+Kapazitäts-/Koordinationsannahme", "wartezeit_fa": "indirekter Entlastungspfad"},
        "confidence": "explorativ",
        "sources": ["OECD Health System Reviews", "European Observatory HiT reports"],
    },
    {
        "id": "se_waiting_time_guarantee",
        "country": "Schweden",
        "policy_name": "Wartezeitgarantien",
        "policy_area": "Zugang / Wartezeiten",
        "target_problem": "Politisch sichtbare maximale Wartezeiten und Priorisierung von Zugang.",
        "reported_outcomes": [
            "stärkerer Fokus auf Wartezeiten",
            "mögliche Zielkonflikte bei Priorisierung und Kapazität",
        ],
        "evidence_grade": "C",
        "comparability_to_germany": "niedrig",
        "transfer_caveat": "Ohne zusätzliche Kapazität kann eine Garantie in Deutschland nur begrenzt wirken; Effekte sind nicht 1:1 auf Deutschland übertragbar.",
        "suggested_parameter_changes": {"wartezeit_fa": "Zielwert-/Priorisierungspfad", "patienten_pro_quartal": "Kapazitätsannahme prüfen"},
        "confidence": "explorativ",
        "sources": ["OECD", "European Observatory", "nationale Evaluationsberichte"],
    },
]


def list_international_reforms() -> List[Dict[str, object]]:
    """Return curated reform examples for the international comparison layer."""
    return [dict(item) for item in _REFORMS]


def transfer_reform_to_germany(reform_id: str) -> Dict[str, object]:
    """Return a cautious Germany-transfer proposal for a reform example."""
    reform = next((item for item in _REFORMS if item["id"] == reform_id), None)
    if reform is None:
        raise KeyError(f"Unknown reform_id: {reform_id}")
    return {
        "reform_id": reform["id"],
        "title": f"{reform['policy_name']} auf Deutschland übertragen",
        "suggested_parameter_changes": reform["suggested_parameter_changes"],
        "comparability_to_germany": reform["comparability_to_germany"],
        "confidence": reform["confidence"],
        "transfer_caveat": reform["transfer_caveat"],
        "plain_language_summary": (
            f"{reform['country']} liefert ein interessantes Beispiel für {reform['policy_area']}. "
            "SimMed behandelt das als vorsichtige Szenarioübersetzung, nicht als sichere Wirkung für Deutschland."
        ),
    }
