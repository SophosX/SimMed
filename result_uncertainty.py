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
