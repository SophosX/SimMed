"""Read-only uncertainty summaries for SimMed result outputs.

These helpers translate already-computed Monte-Carlo aggregate columns into
agent/UI friendly rows. They do not run simulations, change parameters, or turn
model spread into official forecast intervals.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

DEFAULT_UNCERTAINTY_METRICS = [
    "gkv_saldo",
    "wartezeit_fa",
    "versorgungsindex_rural",
    "gesundheitsausgaben_mrd",
    "aerzte_pro_100k",
    "kollaps_wahrscheinlichkeit",
]

UNCERTAINTY_GUARDRAIL = (
    "Monte-Carlo-Spannweite im SimMed-Modell; keine amtliche Prognose, "
    "kein Wirksamkeitsnachweis und keine Konfidenzgarantie."
)


def _classify_band(relative_width: float) -> tuple[str, str]:
    if relative_width >= 0.50:
        return "breites Band", "Ergebnis stark als Spannweite lesen; erst Annahmen und Treiber prüfen."
    if relative_width >= 0.20:
        return "mittleres Band", "Mittelwert nur zusammen mit P5/P95 lesen; mehrere plausible Modellläufe unterscheiden sich sichtbar."
    return "enges Band", "Mittelwert wirkt in den Modellläufen relativ stabil, bleibt aber Szenario- und Annahmen-getrieben."


def build_uncertainty_result_questions(
    band_rows: Sequence[Mapping[str, str]],
    *,
    limit: int = 3,
) -> list[dict[str, str]]:
    """Turn uncertainty bands into question-first reading prompts.

    This is a UX/API helper only: it reuses precomputed band rows and never runs
    a simulation or changes model/data state.
    """

    questions: list[dict[str, str]] = []
    for row in list(band_rows)[:limit]:
        label = row.get("label") or row.get("metric_key") or "Kennzahl"
        signal = row.get("signal", "Spannweite prüfen")
        p5 = row.get("p5", "?")
        p95 = row.get("p95", "?")
        mean = row.get("mean", "?")
        questions.append(
            {
                "metric_key": row.get("metric_key", ""),
                "question": f"Wie sicher ist das Signal bei {label}?",
                "answer_first": f"{label}: Mittelwert {mean}, plausible Modell-Spannweite P5–P95 {p5}–{p95} ({signal}).",
                "what_to_open_next": f"KPI-Detailkarte für {label} öffnen und P5/P95 zusammen mit Wirkpfad, Annahmen und Trend-Timing lesen.",
                "safe_reading": "Breite Bänder als Unsicherheit/Robustheitsfrage lesen, nicht als eindeutige Punktprognose.",
                "guardrail": UNCERTAINTY_GUARDRAIL,
            }
        )
    return questions


def build_uncertainty_decision_checklist(
    band_rows: Sequence[Mapping[str, str]],
    *,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Build a decision-hygiene checklist from existing uncertainty bands.

    The checklist answers what a first-time user should do before treating a
    Monte-Carlo result as decision-ready. It is read-only: no simulations,
    sensitivity runs, connector calls, or model mutations happen here.
    """

    checklist: list[dict[str, str]] = []
    for index, row in enumerate(list(band_rows)[:limit], start=1):
        label = row.get("label") or row.get("metric_key") or "Kennzahl"
        signal = row.get("signal", "Spannweite prüfen")
        if signal == "breites Band":
            decision_status = "erst Robustheit prüfen"
            required_check = "Parameterannahmen, geänderte Hebel und P5/P95-Band vor jeder Entscheidung prüfen."
        elif signal == "mittleres Band":
            decision_status = "mit Vorsicht nutzbar"
            required_check = "Mittelwert nur zusammen mit P5/P95, Trend-Timing und KPI-Detailkarte lesen."
        else:
            decision_status = "relativ stabil im Modell"
            required_check = "Trotz engem Band Evidenzgrad, Wirkpfad und politische Umsetzbarkeit gegenprüfen."
        checklist.append(
            {
                "rank": str(index),
                "metric_key": row.get("metric_key", ""),
                "label": label,
                "uncertainty_signal": signal,
                "decision_status": decision_status,
                "required_check_before_decision": required_check,
                "what_to_open_next": f"KPI-Detailkarte und Annahmen-Check für {label} öffnen; danach Trend-Timing lesen.",
                "guardrail": UNCERTAINTY_GUARDRAIL,
            }
        )
    return checklist



def build_uncertainty_band_summary_from_final(
    final_year_summary: Mapping[str, Any],
    *,
    metric_labels: Mapping[str, str] | None = None,
    metric_keys: Sequence[str] | None = None,
    limit: int = 5,
) -> list[dict[str, str]]:
    """Summarize P5/P95 bands from a final-year aggregate mapping.

    Expected keys follow ``<metric>_mean``, ``<metric>_p5`` and ``<metric>_p95``.
    Missing metrics are skipped so API/UI callers can use the same helper across
    model versions without brittle assumptions.
    """

    labels = metric_labels or {}
    rows: list[dict[str, str]] = []
    for key in metric_keys or DEFAULT_UNCERTAINTY_METRICS:
        mean_key = f"{key}_mean"
        p5_key = f"{key}_p5"
        p95_key = f"{key}_p95"
        if mean_key not in final_year_summary or p5_key not in final_year_summary or p95_key not in final_year_summary:
            continue
        mean = float(final_year_summary[mean_key])
        p5 = float(final_year_summary[p5_key])
        p95 = float(final_year_summary[p95_key])
        width = p95 - p5
        relative_width = abs(width / mean) if mean else abs(width)
        signal, interpretation = _classify_band(relative_width)
        rows.append(
            {
                "metric_key": key,
                "label": labels.get(key, key),
                "end_year": str(int(final_year_summary["jahr"])),
                "mean": f"{mean:.2f}",
                "p5": f"{p5:.2f}",
                "p95": f"{p95:.2f}",
                "band_width": f"{width:.2f}",
                "signal": signal,
                "interpretation": interpretation,
                "guardrail": UNCERTAINTY_GUARDRAIL,
            }
        )
    return sorted(rows, key=lambda row: float(row["band_width"]), reverse=True)[:limit]
