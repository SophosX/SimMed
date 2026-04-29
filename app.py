"""
SimMed Deutschland 2040
=======================
Hochinteraktive Monte-Carlo-Simulationsplattform für das deutsche Gesundheitssystem.
Simuliert GKV + PKV mit dynamischen Feedback-Loops, Ausweichmechanismen und
stochastischen Schocks über 5–30 Jahre.

Starten: streamlit run app.py

Autor: Generiert mit Claude | Datenquellen: Destatis, BÄK, KBV, BMG 2025/2026
"""

import streamlit as st
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import multiprocessing
import os
import time
import io
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Any
import warnings

from political_feasibility import assess_political_feasibility
from expert_council import plain_language_workflow_summary
from parameter_registry import PARAMETER_REGISTRY

warnings.filterwarnings("ignore")

try:
    from joblib import Parallel, delayed
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False


# ═══════════════════════════════════════════════════════════════════════════════
# KONSTANTEN & REFERENZDATEN (Quellen: Destatis, BÄK, KBV, BMG 2025/2026)
# ═══════════════════════════════════════════════════════════════════════════════

BUNDESLAENDER = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
]

BL_KURZ = [
    "BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV",
    "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH",
]

# Bevölkerung in Millionen (ca. 2025, Destatis)
BL_BEVOELKERUNG = np.array([
    11.2, 13.4, 3.7, 2.6, 0.7, 1.9, 6.4, 1.6,
    8.1, 18.1, 4.1, 1.0, 4.1, 2.2, 2.9, 2.1,
], dtype=np.float64)

# Koordinaten (Lat, Lon) der Bundesland-Zentroide
BL_COORDS_LAT = np.array([
    48.66, 48.79, 52.52, 52.41, 53.08, 53.55, 50.65, 53.61,
    52.64, 51.43, 50.12, 49.40, 51.10, 51.95, 54.22, 50.93,
])
BL_COORDS_LON = np.array([
    9.00, 11.50, 13.40, 13.06, 8.80, 10.00, 9.16, 12.43,
    9.85, 7.66, 7.31, 6.96, 13.20, 11.69, 9.90, 11.02,
])

# Urbanisierungsgrad pro Bundesland (0–1)
BL_URBAN_SHARE = np.array([
    0.72, 0.68, 0.96, 0.52, 0.97, 0.99, 0.75, 0.48,
    0.63, 0.80, 0.62, 0.76, 0.65, 0.52, 0.60, 0.55,
], dtype=np.float64)

# 18 Alterskohorten (5-Jahres-Gruppen: 0–4 bis 85+)
ALTERSGRUPPEN = [
    "0–4", "5–9", "10–14", "15–19", "20–24", "25–29",
    "30–34", "35–39", "40–44", "45–49", "50–54", "55–59",
    "60–64", "65–69", "70–74", "75–79", "80–84", "85+",
]

# Baseline-Altersverteilung (Destatis 2025, normalisiert)
ALTERS_VERTEILUNG_RAW = np.array([
    3.90, 3.80, 3.90, 4.00, 4.50, 5.00, 5.30, 5.10,
    4.80, 5.00, 5.80, 6.40, 5.90, 5.10, 4.20, 3.50, 2.80, 2.40,
], dtype=np.float64)
ALTERS_VERTEILUNG = ALTERS_VERTEILUNG_RAW / ALTERS_VERTEILUNG_RAW.sum()

# Altersspezifische Mortalitätsrate pro Jahr (Destatis 2024)
MORTALITAET_BASIS = np.array([
    0.40, 0.10, 0.10, 0.20, 0.40, 0.40, 0.50, 0.60,
    1.00, 1.50, 2.50, 4.00, 7.00, 12.0, 20.0, 40.0, 80.0, 160.0,
], dtype=np.float64) / 1000.0

# Altersspezifischer Nachfrage-Multiplikator (relativ zu Durchschnitt)
NACHFRAGE_FAKTOR = np.array([
    1.20, 0.60, 0.50, 0.50, 0.60, 0.70, 0.80, 0.90,
    1.00, 1.10, 1.30, 1.50, 1.70, 2.00, 2.50, 3.00, 3.50, 4.00,
], dtype=np.float64)

# Zuwanderungs-Altersprofil (jung gewichtet, BAMF 2024)
ZUWANDERUNG_PROFIL_RAW = np.array([
    0.03, 0.05, 0.08, 0.10, 0.14, 0.15, 0.12, 0.10,
    0.07, 0.05, 0.04, 0.03, 0.02, 0.01, 0.005, 0.003, 0.002, 0.001,
], dtype=np.float64)
ZUWANDERUNG_PROFIL = ZUWANDERUNG_PROFIL_RAW / ZUWANDERUNG_PROFIL_RAW.sum()

# Arzt-Fachrichtungen
FACHRICHTUNGEN = [
    "Allgemeinmedizin", "Innere Medizin", "Chirurgie",
    "Psychiatrie/Psychotherapie", "Sonstige Fachärzte",
]
FACH_VERTEILUNG = np.array([0.25, 0.20, 0.12, 0.08, 0.35], dtype=np.float64)

# KPI-Namen für vektorisierte Extraktion (29 KPIs)
KPI_NAMES = [
    "jahr", "bevoelkerung_mio", "aerzte_gesamt", "aerzte_pro_100k",
    "chroniker_rate", "lebenserwartung", "qaly_index",
    "wartezeit_ha", "wartezeit_fa",
    "gkv_einnahmen", "gkv_ausgaben", "gkv_saldo",
    "gesundheitsausgaben_mrd", "bip_anteil",
    "gkv_anteil", "pkv_anteil", "gkv_beitragssatz",
    "burnout_rate", "zufriedenheit_aerzte", "zufriedenheit_patienten",
    "telemedizin_rate", "digitalisierung",
    "versorgungsindex_rural", "fahrzeit_praxis",
    "vermeidbare_mortalitaet", "gini_versorgung",
    "kollaps_wahrscheinlichkeit", "urban_anteil",
    "praevention_kumuliert",
]

# Deutsche Labels für KPIs
KPI_LABELS = {
    "gesundheitsausgaben_mrd": "Gesundheitsausgaben (Mrd. €)",
    "bip_anteil": "BIP-Anteil (%)",
    "gkv_beitragssatz": "GKV-Beitragssatz eff. (%)",
    "gkv_saldo": "GKV-Saldo (Mrd. €)",
    "gkv_einnahmen": "GKV-Einnahmen (Mrd. €)",
    "gkv_ausgaben": "GKV-Ausgaben (Mrd. €)",
    "lebenserwartung": "Lebenserwartung (Jahre)",
    "vermeidbare_mortalitaet": "Vermeidbare Mortalität (/100k)",
    "chroniker_rate": "Chroniker-Rate (%)",
    "qaly_index": "QALY-Index (0–1)",
    "bevoelkerung_mio": "Bevölkerung (Mio.)",
    "aerzte_gesamt": "Ärzte gesamt",
    "aerzte_pro_100k": "Ärzte pro 100.000",
    "wartezeit_ha": "Wartezeit Hausarzt (Tage)",
    "wartezeit_fa": "Wartezeit Facharzt (Tage)",
    "burnout_rate": "Burnout-Rate Ärzte (%)",
    "zufriedenheit_aerzte": "Ärztezufriedenheit (0–100)",
    "zufriedenheit_patienten": "Patientenzufriedenheit (0–100)",
    "telemedizin_rate": "Telemedizin-Rate (%)",
    "digitalisierung": "Digitalisierung (%)",
    "versorgungsindex_rural": "Versorgungsindex ländlich (0–100)",
    "fahrzeit_praxis": "Fahrzeit zur Praxis (Min.)",
    "gini_versorgung": "Gini-Koeffizient Versorgung",
    "kollaps_wahrscheinlichkeit": "Kollaps-Wahrscheinlichkeit (%)",
    "urban_anteil": "Urbanisierungsgrad (%)",
    "gkv_anteil": "GKV-Anteil (%)",
    "pkv_anteil": "PKV-Anteil (%)",
    "praevention_kumuliert": "Prävention kumuliert",
}


# ═══════════════════════════════════════════════════════════════════════════════
# CSS & UI-HILFSFUNKTIONEN
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 18px 20px; border-radius: 14px; color: white;
        margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        min-height: 120px;
    }
    .mc-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 18px 20px; border-radius: 14px; color: white;
        margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        min-height: 120px;
    }
    .mc-red {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        padding: 18px 20px; border-radius: 14px; color: white;
        margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        min-height: 120px;
    }
    .mc-blue {
        background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
        padding: 18px 20px; border-radius: 14px; color: white;
        margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        min-height: 120px;
    }
    .mc-orange {
        background: linear-gradient(135deg, #f2994a 0%, #f2c94c 100%);
        padding: 18px 20px; border-radius: 14px; color: white;
        margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        min-height: 120px;
    }
    .mv { font-size: 2em; font-weight: 700; margin: 4px 0; }
    .ml { font-size: 0.88em; opacity: 0.92; }
    .md { font-size: 0.82em; margin-top: 6px; }
</style>
"""


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Konvertiert Hex-Farbe (#RRGGBB) in rgba()-String."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def metric_card(
    label: str,
    value: str,
    delta: Optional[float] = None,
    delta_good: bool = True,
    css_class: str = "metric-card",
) -> str:
    """Erzeugt HTML für eine Dashboard-Metrik-Karte."""
    delta_html = ""
    if delta is not None:
        if delta > 0.05:
            arrow, sign = "\u2191", "+"
        elif delta < -0.05:
            arrow, sign = "\u2193", ""
        else:
            arrow, sign = "\u2192", ""
        good = (delta > 0) == delta_good
        color = "#c8ffc8" if good else "#ffc8c8" if abs(delta) > 0.05 else "#ffffff"
        delta_html = (
            f'<div class="md" style="color:{color}">'
            f"{arrow} {sign}{delta:.1f} %</div>"
        )
    return (
        f'<div class="{css_class}">'
        f'<div class="ml">{label}</div>'
        f'<div class="mv">{value}</div>'
        f"{delta_html}</div>"
    )


def _params_hash(params: dict) -> str:
    """Erzeugt einen Hash der Parameter für Änderungserkennung."""
    serializable = {k: (v if not isinstance(v, np.ndarray) else v.tolist()) for k, v in params.items()}
    return hashlib.md5(json.dumps(serializable, sort_keys=True, default=str).encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT-PARAMETER (alle mit Quellen-Referenz 2025/2026)
# ═══════════════════════════════════════════════════════════════════════════════

def get_default_params() -> Dict[str, Any]:
    """Liefert alle Simulationsparameter mit realistischen Standardwerten."""
    return {
        # ── Demografie & Bevölkerung ──
        "bevoelkerung_mio": 84.4,          # Destatis 2025
        "geburtenrate": 1.35,              # TFR, Destatis 2024
        "netto_zuwanderung": 300_000,      # BAMF 2024
        "alterungsfaktor": 1.0,            # 1.0 = Baseline
        "urban_anteil": 0.77,              # Destatis 2025
        "einkommen_durchschnitt": 45_000,  # Destatis 2025, brutto/Jahr
        "einkommens_wachstum": 0.02,       # 2% nominal p.a.
        "pkv_schwelle": 69_300,            # JAEG 2025
        # ── Versorgungsstruktur ──
        "aerzte_gesamt": 421_000,          # BÄK 2025
        "aerzte_pro_100k_urban": 280,      # KBV 2025
        "aerzte_pro_100k_rural": 160,      # KBV 2025
        "hausarztpraxen": 54_000,          # KBV 2025
        "fachpraxen": 48_000,
        "mvz_anzahl": 4_800,               # KBV 2025
        "krankenhaeuser": 1_900,           # Destatis 2025
        "krankenhausbetten": 480_000,      # Destatis 2025
        "patienten_pro_quartal": 850,
        "arbeitszeit_stunden": 52,         # MB-Monitor 2024
        # ── Ärzte-Pipeline ──
        "medizinstudienplaetze": 11_000,   # HRK 2025
        "ausbildungsdauer_jahre": 6.5,
        "facharzt_weiterbildung": 5.5,
        "abwanderungsquote": 0.03,         # 3%
        "einwanderung_aerzte": 3_500,      # BÄK 2025
        "ruhestandsquote": 0.025,          # 2.5% p.a.
        # ── Versicherung & Finanzierung ──
        "gkv_beitragssatz": 14.6,          # BMG 2025
        "gkv_zusatzbeitrag": 1.7,          # BMG 2025 Durchschnitt
        "gkv_anteil": 0.88,               # ~88% GKV
        "pkv_beitrag_durchschnitt": 450,   # EUR/Monat
        "pkv_selbstbehalt": 600,           # EUR/Jahr
        "zuzahlungen_gkv": 2.0,           # Mrd EUR/Jahr
        "morbi_rsa_staerke": 1.0,
        "staatliche_subventionen": 14.5,   # Mrd EUR, BMG 2025
        "praeventionsbudget": 8.0,         # Mrd EUR
        # ── Politische Hebel ──
        "telemedizin_rate": 0.05,          # 5% der Kontakte
        "digitalisierung_epa": 0.15,       # 15% ePA-Nutzung, gematik 2025
        "praevention_effektivitaet": 0.5,  # 0–1
        "amnog_preisreduktion": 0.10,      # 10%
        "drg_niveau": 1.0,
        "pflegepersonal_schluessel": 1.0,
        "wartezeit_grenze_tage": 25,       # TSG § 75 Abs. 1a SGB V
        "igel_rate": 0.08,                 # 8%
        # ── Simulation ──
        "sim_jahre": 15,
        "n_runs": 1_000,
        "basis_seed": 42,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATIONSKERN
# ═══════════════════════════════════════════════════════════════════════════════

def _initialize_state(p: dict, rng: np.random.Generator) -> dict:
    """Erstellt den vollständigen Systemzustand aus Parametern."""
    bev = p["bevoelkerung_mio"] * 1e6
    bl_frac = BL_BEVOELKERUNG / BL_BEVOELKERUNG.sum()

    # Ärzte regional: gewichtet nach Bevölkerung × Urbanisierung
    aerzte_weight = bl_frac * (0.65 + 0.35 * BL_URBAN_SHARE)
    aerzte_weight /= aerzte_weight.sum()

    s: Dict[str, Any] = {
        # Demografie
        "jahr": 2026,
        "bevoelkerung": bev,
        "pop_alter": ALTERS_VERTEILUNG * bev,
        "pop_regional": bl_frac * bev,
        "urban_anteil": p["urban_anteil"],
        # Versorgung
        "aerzte_gesamt": float(p["aerzte_gesamt"]),
        "aerzte_regional": aerzte_weight * p["aerzte_gesamt"],
        "aerzte_fach": FACH_VERTEILUNG * p["aerzte_gesamt"],
        "krankenhausbetten": float(p["krankenhausbetten"]),
        "pipeline_buffer": np.full(12, p["medizinstudienplaetze"] * 0.82),
        # Gesundheit
        "chroniker_rate": 0.38,
        "morbiditaet_index": 1.0,
        "lebenserwartung": 80.6,
        "qaly_index": 0.82,
        # Zugang
        "wartezeit_ha": 3.0,
        "wartezeit_fa": 25.0,
        "versorgungsindex_rural": 72.0,
        "fahrzeit_praxis_min": 12.0,
        # Finanzen (werden sofort berechnet)
        "gkv_einnahmen": 0.0,
        "gkv_ausgaben": 0.0,
        "gkv_saldo": 0.0,
        "gesundheitsausgaben_gesamt": 474.0,
        "bip": 4100.0,
        "bip_anteil": 11.6,
        # Versicherung
        "gkv_anteil": p["gkv_anteil"],
        "pkv_anteil": 1.0 - p["gkv_anteil"],
        "gkv_beitragssatz_eff": p["gkv_beitragssatz"] + p["gkv_zusatzbeitrag"],
        # Telemedizin & Digital
        "telemedizin_rate": p["telemedizin_rate"],
        "digitalisierung": p["digitalisierung_epa"],
        # Arbeitszufriedenheit
        "burnout_rate": 0.12,
        "zufriedenheit_aerzte": 65.0,
        "zufriedenheit_patienten": 72.0,
        # Prävention
        "praevention_kumuliert": 0.0,
        # Verteilungsgerechtigkeit
        "gini_versorgung": 0.18,
        # Mortalität
        "vermeidbare_mortalitaet": 110.0,
        # Systemstabilität
        "kollaps_wahrscheinlichkeit": 0.02,
    }

    # GKV-Finanzen initial berechnen
    gkv_vers = s["bevoelkerung"] * s["gkv_anteil"]
    s["gkv_einnahmen"] = (
        gkv_vers * p["einkommen_durchschnitt"] * (s["gkv_beitragssatz_eff"] / 100) / 2
    ) / 1e9 + p["staatliche_subventionen"]
    s["gkv_ausgaben"] = s["gkv_einnahmen"] * 0.98
    s["gkv_saldo"] = s["gkv_einnahmen"] - s["gkv_ausgaben"]

    return s


def _simulate_year(s: dict, p: dict, rng: np.random.Generator) -> dict:
    """Simuliert einen vollständigen Jahresschritt mit allen Feedback-Loops."""
    # Arbeitskopie aller Zustandsvariablen
    s = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in s.items()}
    s["jahr"] += 1

    # Stochastisches Rauschen (skaliert)
    def noise(scale: float = 0.02) -> float:
        return 1.0 + rng.normal(0, scale)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1 – DEMOGRAFIE
    # ═══════════════════════════════════════════════════════════════
    pop = s["pop_alter"]

    # 1a) Mortalität
    deaths = pop * MORTALITAET_BASIS * noise(0.03) * s["morbiditaet_index"]
    pop = pop - deaths

    # 1b) Kohortenalterung (20 % jeder 5-Jahres-Gruppe rücken pro Jahr auf)
    shift_frac = 0.2 * p["alterungsfaktor"]
    shift = pop * np.clip(shift_frac, 0, 0.25)
    pop = pop - shift
    pop[1:] += shift[:-1]

    # 1c) Geburten
    # Frauen im gebärfähigen Alter: Kohorten 15-19 bis 40-44 (Index 3–8)
    frauen_15_44 = s["pop_alter"][3:9].sum() * 0.5  # ca. 50% weiblich
    geburten = frauen_15_44 * (p["geburtenrate"] / 5.0) * noise(0.05)
    pop[0] += max(0, geburten)

    # 1d) Netto-Zuwanderung
    netto_zuw = max(0, p["netto_zuwanderung"] * noise(0.15))
    pop += ZUWANDERUNG_PROFIL * netto_zuw

    pop = np.maximum(pop, 0)
    s["pop_alter"] = pop
    s["bevoelkerung"] = pop.sum()

    # 1e) Regionale Bevölkerung (proportional + leichter Trend)
    bl_frac = BL_BEVOELKERUNG / BL_BEVOELKERUNG.sum()
    s["pop_regional"] = bl_frac * s["bevoelkerung"]
    s["urban_anteil"] = min(0.92, s["urban_anteil"] + 0.0008 * noise(0.4))

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2 – ÄRZTE-PIPELINE
    # ═══════════════════════════════════════════════════════════════
    # Absolventen aus Pipeline (Ende der Ausbildung)
    absolventen = s["pipeline_buffer"][-1] * (1.0 - p["abwanderungsquote"]) * noise(0.05)

    # Pipeline vorrücken
    s["pipeline_buffer"] = np.roll(s["pipeline_buffer"], 1)
    s["pipeline_buffer"][0] = p["medizinstudienplaetze"] * noise(0.03)

    # Einwanderung ausländischer Ärzte
    einwanderung = max(0, p["einwanderung_aerzte"] * noise(0.15))

    # Ruhestand
    ruhestand = s["aerzte_gesamt"] * p["ruhestandsquote"] * noise(0.05)

    # Burnout-bedingter Abgang (2% der Burnout-Betroffenen verlassen Beruf)
    burnout_abgang = s["aerzte_gesamt"] * s["burnout_rate"] * 0.02

    # Nettoänderung
    s["aerzte_gesamt"] += absolventen + einwanderung - ruhestand - burnout_abgang
    s["aerzte_gesamt"] = max(s["aerzte_gesamt"], 100_000)

    # Regionale Verteilung
    aerzte_w = bl_frac * (0.65 + 0.35 * BL_URBAN_SHARE)
    aerzte_w /= aerzte_w.sum()
    s["aerzte_regional"] = aerzte_w * s["aerzte_gesamt"]

    # Fachrichtungen
    s["aerzte_fach"] = FACH_VERTEILUNG * s["aerzte_gesamt"]

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3 – NACHFRAGE-BERECHNUNG
    # ═══════════════════════════════════════════════════════════════
    # Altersgewichtete Nachfrage
    alter_nachfrage = (s["pop_alter"] * NACHFRAGE_FAKTOR).sum() / max(s["bevoelkerung"], 1)

    # Chroniker-Multiplikator
    chroniker_mult = 1.0 + 0.5 * (s["chroniker_rate"] - 0.38)

    # Telemedizin-Entlastung (reduziert Vor-Ort-Bedarf um bis zu 15%)
    tele_entlastung = 1.0 - 0.15 * s["telemedizin_rate"]

    # Digitalisierungs-Effizienz (bis zu 8% Effizienzgewinn)
    digi_effizienz = 1.0 - 0.08 * s["digitalisierung"]

    nachfrage_index = alter_nachfrage * chroniker_mult * tele_entlastung * digi_effizienz * noise(0.02)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 4 – ANGEBOT-NACHFRAGE-BALANCE
    # ═══════════════════════════════════════════════════════════════
    aerzte_pro_100k = s["aerzte_gesamt"] / max(s["bevoelkerung"] / 100_000, 1)
    baseline_bedarf = 250.0  # Ärzte/100k Baseline-Bedarf
    angebot_nachfrage = aerzte_pro_100k / (baseline_bedarf * nachfrage_index)

    # Wartezeiten: inverse Funktion des Angebot-Nachfrage-Verhältnisses
    wz_faktor = 1.0 / max(angebot_nachfrage, 0.3)
    s["wartezeit_ha"] = max(1.0, 3.0 * wz_faktor * noise(0.08))
    s["wartezeit_fa"] = max(3.0, 25.0 * wz_faktor * noise(0.10))

    # ═══════════════════════════════════════════════════════════════
    # PHASE 5 – FINANZMODELL
    # ═══════════════════════════════════════════════════════════════
    # BIP-Wachstum (real ~1.2% + Inflation ~2%)
    s["bip"] *= 1.0 + 0.015 * noise(0.5)

    # Einkommen (wächst über Zeit)
    jahre_seit_start = s["jahr"] - 2026
    einkommen = p["einkommen_durchschnitt"] * (1.0 + p["einkommens_wachstum"]) ** jahre_seit_start

    # GKV-Einnahmen
    gkv_vers = s["bevoelkerung"] * s["gkv_anteil"]
    beitrag_eff = s["gkv_beitragssatz_eff"]
    s["gkv_einnahmen"] = (
        (gkv_vers * einkommen * (beitrag_eff / 100.0) / 2.0) / 1e9
        + p["staatliche_subventionen"]
    )

    # GKV-Ausgaben (wachsen mit Nachfrage, Morbidität, DRG-Niveau)
    kosten_steigerung = nachfrage_index * p["drg_niveau"] * (1.0 + 0.02 * noise(0.3))
    pflegekosten_faktor = 1.0 + 0.05 * max(0, p["pflegepersonal_schluessel"] - 1.0)
    amnog_ersparnis = 1.0 - p["amnog_preisreduktion"] * 0.15  # AMNOG spart bei Arzneimitteln
    s["gkv_ausgaben"] = (
        s["gkv_einnahmen"] * 0.95
        * kosten_steigerung
        * pflegekosten_faktor
        * amnog_ersparnis
        * noise(0.02)
    )
    s["gkv_saldo"] = s["gkv_einnahmen"] - s["gkv_ausgaben"]

    # Gesamtausgaben (GKV + PKV + Privat + Prävention)
    pkv_ausgaben = s["bevoelkerung"] * s["pkv_anteil"] * p["pkv_beitrag_durchschnitt"] * 12 / 1e9
    privat_ausgaben = s["bevoelkerung"] * p["igel_rate"] * 200 / 1e9  # ~200€/Kopf IGeL
    s["gesundheitsausgaben_gesamt"] = (
        s["gkv_ausgaben"] + pkv_ausgaben + privat_ausgaben + p["praeventionsbudget"]
    )
    s["bip_anteil"] = s["gesundheitsausgaben_gesamt"] / max(s["bip"], 1) * 100

    # ═══════════════════════════════════════════════════════════════
    # PHASE 6 – FEEDBACK-LOOPS
    # ═══════════════════════════════════════════════════════════════

    # --- Loop A: Ärztemangel → Gehaltsanreize → Pipeline-Anpassung ---
    if angebot_nachfrage < 0.9:
        mangel = (0.9 - angebot_nachfrage) * 2.0
        # Mehr Studienplätze (wirkt erst nach Ausbildungszeit)
        s["pipeline_buffer"][0] *= 1.0 + 0.04 * mangel
        # Stärkere Immigration
        s["aerzte_gesamt"] += p["einwanderung_aerzte"] * 0.12 * mangel
        # Teilzeit-Reduktion (Ärzte arbeiten mehr bei Mangel)
        s["aerzte_gesamt"] *= 1.0 + 0.005 * mangel

    # --- Loop B: Wartezeiten → Patientenverhalten ---
    wz_ratio = s["wartezeit_fa"] / max(p["wartezeit_grenze_tage"], 1)
    if wz_ratio > 1.2:
        ueberlast = wz_ratio - 1.2
        # Patienten wechseln zur PKV
        s["pkv_anteil"] = min(0.25, s["pkv_anteil"] + 0.002 * ueberlast)
        s["gkv_anteil"] = 1.0 - s["pkv_anteil"]
        # Telemedizin-Adoption beschleunigt
        s["telemedizin_rate"] = min(0.60, s["telemedizin_rate"] + 0.012 * ueberlast)
        # Behandlungsverzicht → höhere Mortalität
        s["vermeidbare_mortalitaet"] *= 1.0 + 0.015 * ueberlast
        # Auslandsbehandlung (kleiner Effekt, entlastet System leicht)
        s["wartezeit_fa"] *= 1.0 - 0.005 * ueberlast
        # Patientenzufriedenheit sinkt
        s["zufriedenheit_patienten"] = max(15, s["zufriedenheit_patienten"] - 2.5 * ueberlast)

    # --- Loop C: Ländliche Versorgungslücken → Mortalität ---
    rural_pop_share = 1.0 - s["urban_anteil"]
    rural_aerzte_share = np.sum(s["aerzte_regional"] * (1 - BL_URBAN_SHARE)) / max(s["aerzte_gesamt"], 1)
    rural_ratio = (rural_aerzte_share / max(rural_pop_share, 0.01))
    rural_gap = max(0, 1.0 - rural_ratio / 0.85)  # Gap wenn Ratio < 85% des Ideals

    s["versorgungsindex_rural"] = max(15, 72.0 * (1.0 - 0.8 * rural_gap))
    s["fahrzeit_praxis_min"] = 12.0 * (1.0 + 0.6 * rural_gap)

    if rural_gap > 0.10:
        # Zeitkritische Erkrankungen: höhere Mortalität bei schlechter Versorgung
        s["vermeidbare_mortalitaet"] *= 1.0 + 0.04 * rural_gap

    # --- Loop D: PKV-Wachstum → Rosinenpickerei → GKV-Belastung ---
    pkv_excess = max(0, s["pkv_anteil"] - 0.12)
    if pkv_excess > 0:
        cream_skim = pkv_excess * 5.0
        # GKV bekommt kränkere Population
        s["morbiditaet_index"] *= 1.0 + 0.02 * cream_skim
        # Morbi-RSA wird teurer
        s["gkv_ausgaben"] *= 1.0 + 0.008 * cream_skim * p["morbi_rsa_staerke"]

    # --- Loop E: Kostenexplosion → Politik reagiert ---
    if s["gkv_saldo"] < -5.0:  # > 5 Mrd. Defizit
        defizit_ratio = abs(s["gkv_saldo"]) / max(s["gkv_einnahmen"], 1)
        if defizit_ratio > 0.03:
            # Beitragserhöhung (stochastische Politikverzögerung)
            if rng.random() < 0.4:
                s["gkv_beitragssatz_eff"] = min(22.0, s["gkv_beitragssatz_eff"] + 0.2)
            # Leistungskürzung bei schwerem Defizit
            if defizit_ratio > 0.06 and rng.random() < 0.3:
                s["gkv_ausgaben"] *= 0.97
            # Staatlicher Sonderzuschuss
            if defizit_ratio > 0.08 and rng.random() < 0.5:
                s["gkv_einnahmen"] += 2.0  # 2 Mrd. Sonderzuschuss

    # --- Loop F: Prävention → langfristige Gesundheitsverbesserung ---
    praev_effekt = p["praeventionsbudget"] * p["praevention_effektivitaet"] / 100.0
    s["praevention_kumuliert"] += praev_effekt
    # Chroniker-Rate sinkt langsam mit kumulierter Prävention
    s["chroniker_rate"] = max(0.12, s["chroniker_rate"] * (1.0 - 0.003 * praev_effekt))
    # Morbiditätsindex verbessert sich
    s["morbiditaet_index"] = max(0.7, s["morbiditaet_index"] - 0.001 * praev_effekt)

    # --- Loop G: Burnout → Versorgungsreduktion ---
    workload = nachfrage_index / max(angebot_nachfrage, 0.3)
    arbeitszeit_faktor = p["arbeitszeit_stunden"] / 52.0  # Norm: 52h
    s["burnout_rate"] = np.clip(
        0.10 + 0.10 * max(0, workload - 1.0) + 0.05 * max(0, arbeitszeit_faktor - 1.0),
        0.05, 0.50,
    )
    s["zufriedenheit_aerzte"] = max(10, 65.0 - 80.0 * (s["burnout_rate"] - 0.10))

    # --- Digitalisierung wächst organisch ---
    s["digitalisierung"] = min(0.95, s["digitalisierung"] + 0.025 * noise(0.3))
    s["telemedizin_rate"] = min(0.60, s["telemedizin_rate"] + 0.004 * s["digitalisierung"])

    # --- Demografischer Chroniker-Drift (Alterung → mehr Chroniker) ---
    anteil_65plus = s["pop_alter"][13:].sum() / max(s["bevoelkerung"], 1)
    s["chroniker_rate"] += 0.003 * max(0, anteil_65plus - 0.22)  # Anstieg wenn > 22% über 65

    # ═══════════════════════════════════════════════════════════════
    # PHASE 7 – ZUFALLSSCHOCKS
    # ═══════════════════════════════════════════════════════════════

    # Pandemie (~3% pro Jahr)
    if rng.random() < 0.03:
        staerke = rng.uniform(0.15, 0.40)
        s["gkv_ausgaben"] *= 1.0 + staerke
        s["burnout_rate"] = min(0.50, s["burnout_rate"] + 0.08)
        s["vermeidbare_mortalitaet"] *= 1.0 + 0.12 * staerke
        s["zufriedenheit_patienten"] = max(15, s["zufriedenheit_patienten"] - 8)

    # Cyberangriff auf Krankenhaus-IT (~2%)
    if rng.random() < 0.02:
        s["krankenhausbetten"] *= 0.88
        s["wartezeit_fa"] *= 1.25
        s["zufriedenheit_patienten"] = max(15, s["zufriedenheit_patienten"] - 5)

    # Ärztestreik (~2%)
    if rng.random() < 0.02:
        s["wartezeit_ha"] *= 1.6
        s["wartezeit_fa"] *= 1.5
        s["zufriedenheit_patienten"] = max(15, s["zufriedenheit_patienten"] - 10)
        s["zufriedenheit_aerzte"] += 5  # Kurzfristig solidarisierend

    # Wirtschaftskrise (~4%)
    if rng.random() < 0.04:
        s["bip"] *= 0.97
        s["gkv_einnahmen"] *= 0.95
        # Mehr GKV-Versicherte (Arbeitslose → GKV)
        s["gkv_anteil"] = min(0.95, s["gkv_anteil"] + 0.005)
        s["pkv_anteil"] = 1.0 - s["gkv_anteil"]

    # ═══════════════════════════════════════════════════════════════
    # PHASE 8 – ABGELEITETE KPIs
    # ═══════════════════════════════════════════════════════════════

    # Lebenserwartung
    gesundheit = (1.0 - 0.2 * (s["morbiditaet_index"] - 1.0)) * (
        1.0 + 0.05 * min(s["praevention_kumuliert"] / 10.0, 1.0)
    )
    versorgung = 1.0 - 0.03 * max(0, 1.0 - angebot_nachfrage)
    s["lebenserwartung"] = np.clip(80.6 * gesundheit * versorgung * noise(0.002), 72, 92)

    # QALY-Index
    s["qaly_index"] = np.clip(
        0.82 * gesundheit * (1.0 - 0.08 * s["burnout_rate"]) * versorgung, 0.45, 0.96
    )

    # Gini-Koeffizient der regionalen Versorgungsdichte
    a_per_cap = s["aerzte_regional"] / np.maximum(s["pop_regional"], 1)
    sorted_v = np.sort(a_per_cap)
    n = len(sorted_v)
    idx = np.arange(1, n + 1)
    s["gini_versorgung"] = np.clip(
        (2.0 * (idx * sorted_v).sum()) / (n * sorted_v.sum()) - (n + 1) / n,
        0.0, 0.65,
    )

    # Kollaps-Wahrscheinlichkeit (>20% Wartezeit-Steigerung + >5% Mortalitätsanstieg)
    wz_anstieg = max(0, (s["wartezeit_fa"] - 25.0) / 25.0)
    mort_anstieg = max(0, (s["vermeidbare_mortalitaet"] - 110.0) / 110.0)
    finanz_stress = max(0, -s["gkv_saldo"] / max(s["gkv_einnahmen"], 1))
    s["kollaps_wahrscheinlichkeit"] = np.clip(
        0.02 + 0.35 * wz_anstieg + 0.35 * mort_anstieg + 0.15 * finanz_stress,
        0.0, 0.95,
    )

    # Betten-Recovery nach Cyberangriff
    s["krankenhausbetten"] = max(s["krankenhausbetten"], p["krankenhausbetten"] * 0.80)
    s["krankenhausbetten"] += (p["krankenhausbetten"] - s["krankenhausbetten"]) * 0.5

    # Vermeidbare Mortalität: leichte natürliche Regression zum Mittelwert
    s["vermeidbare_mortalitaet"] += (110.0 - s["vermeidbare_mortalitaet"]) * 0.02

    return s


def _extract_kpi_array(state: dict) -> np.ndarray:
    """Extrahiert die 29 KPIs als kompakten float32-Vektor."""
    return np.array([
        state["jahr"],
        state["bevoelkerung"] / 1e6,
        state["aerzte_gesamt"],
        state["aerzte_gesamt"] / max(state["bevoelkerung"] / 100_000, 1),
        state["chroniker_rate"] * 100,
        state["lebenserwartung"],
        state["qaly_index"],
        state["wartezeit_ha"],
        state["wartezeit_fa"],
        state["gkv_einnahmen"],
        state["gkv_ausgaben"],
        state["gkv_saldo"],
        state["gesundheitsausgaben_gesamt"],
        state["bip_anteil"],
        state["gkv_anteil"] * 100,
        state["pkv_anteil"] * 100,
        state["gkv_beitragssatz_eff"],
        state["burnout_rate"] * 100,
        state["zufriedenheit_aerzte"],
        state["zufriedenheit_patienten"],
        state["telemedizin_rate"] * 100,
        state["digitalisierung"] * 100,
        state["versorgungsindex_rural"],
        state["fahrzeit_praxis_min"],
        state["vermeidbare_mortalitaet"],
        state["gini_versorgung"],
        state["kollaps_wahrscheinlichkeit"] * 100,
        state["urban_anteil"] * 100,
        state["praevention_kumuliert"],
    ], dtype=np.float32)


def _run_single_sim(params_dict: dict, seed: int, n_years: int) -> Tuple[np.ndarray, np.ndarray]:
    """Führt eine einzelne Monte-Carlo-Simulation durch.

    Returns:
        (kpi_history, regional_final): KPIs als (n_years+1, 29) Array,
        regionale Daten als (16, 2) Array [aerzte, population].
    """
    rng = np.random.default_rng(seed)
    state = _initialize_state(params_dict, rng)

    n_kpis = len(KPI_NAMES)
    history = np.zeros((n_years + 1, n_kpis), dtype=np.float32)
    history[0] = _extract_kpi_array(state)

    for yr in range(n_years):
        state = _simulate_year(state, params_dict, rng)
        history[yr + 1] = _extract_kpi_array(state)

    regional = np.column_stack([state["aerzte_regional"], state["pop_regional"]])
    return history, regional


# ═══════════════════════════════════════════════════════════════════════════════
# MONTE-CARLO-ENGINE & AGGREGATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_simulation(
    params: dict,
    n_runs: int,
    n_years: int,
    base_seed: int,
    progress_callback=None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Führt die parallele Monte-Carlo-Simulation aus.

    Returns:
        (df_kpis, df_regional): KPI-DataFrame (run_id × jahr × kpis),
        Regional-DataFrame (run_id × bundesland × ärzte/pop).
    """
    n_cores = max(1, multiprocessing.cpu_count() - 1)
    batch_size = max(1, n_runs // 10)

    all_kpis: List[np.ndarray] = []
    all_regional: List[np.ndarray] = []

    for batch_start in range(0, n_runs, batch_size):
        batch_end = min(batch_start + batch_size, n_runs)
        seeds = list(range(base_seed + batch_start, base_seed + batch_end))

        if HAS_JOBLIB and len(seeds) > 1:
            batch = Parallel(n_jobs=n_cores, backend="loky")(
                delayed(_run_single_sim)(params, s, n_years) for s in seeds
            )
        else:
            batch = [_run_single_sim(params, s, n_years) for s in seeds]

        for kpi_arr, reg_arr in batch:
            all_kpis.append(kpi_arr)
            all_regional.append(reg_arr)

        if progress_callback:
            progress_callback(min(1.0, batch_end / n_runs))

    # KPI-DataFrame aufbauen
    n_steps = n_years + 1
    n_actual = len(all_kpis)
    data_3d = np.stack(all_kpis)  # (n_runs, n_steps, n_kpis)
    flat = data_3d.reshape(-1, len(KPI_NAMES))
    df = pd.DataFrame(flat, columns=KPI_NAMES)
    df["run_id"] = np.repeat(np.arange(n_actual), n_steps)

    # Regional-DataFrame (nur Endjahr-Daten)
    rows = []
    for run_id, reg in enumerate(all_regional):
        for i, bl in enumerate(BUNDESLAENDER):
            rows.append({
                "run_id": run_id,
                "bundesland": bl,
                "bl_kurz": BL_KURZ[i],
                "aerzte": reg[i, 0],
                "bevoelkerung": reg[i, 1],
                "aerzte_pro_100k": reg[i, 0] / max(reg[i, 1], 1) * 100_000,
            })
    df_reg = pd.DataFrame(rows)

    return df, df_reg


def aggregate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Berechnet Mittelwert, Std, Median, P5, P95 pro Jahr über alle Runs."""
    numeric_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in ("run_id", "jahr")
    ]

    grouped = df.groupby("jahr")[numeric_cols]
    agg_mean = grouped.mean().add_suffix("_mean")
    agg_std = grouped.std().add_suffix("_std")
    agg_median = grouped.median().add_suffix("_median")
    agg_p5 = grouped.quantile(0.05).add_suffix("_p5")
    agg_p95 = grouped.quantile(0.95).add_suffix("_p95")

    result = pd.concat([agg_mean, agg_std, agg_median, agg_p5, agg_p95], axis=1)
    return result.reset_index()


# ═══════════════════════════════════════════════════════════════════════════════
# UI: SIDEBAR – PARAMETER-PANEL
# ═══════════════════════════════════════════════════════════════════════════════

def _parameter_evidence_badge(key: str) -> str:
    """Short evidence badge for visual, low-friction provenance cues."""
    spec = PARAMETER_REGISTRY.get(key)
    if spec is None:
        return "⚪ Evidenz offen · Register fehlt"

    grade_icon = {
        "A": "🟢",
        "B": "🟢",
        "C": "🟡",
        "D": "🟠",
        "E": "🔴",
    }.get(spec.evidence_grade, "⚪")
    sources = ", ".join(spec.source_ids)
    return f"{grade_icon} Evidenz {spec.evidence_grade} · {sources}"


def _parameter_provenance_help(key: str, plain_hint: str | None = None) -> str:
    """Builds plain-language sidebar help from the parameter registry.

    The UI may add a short, concrete hint, but source grade, uncertainty and
    caveat come from `parameter_registry.py` so provenance stays auditable.
    """
    spec = PARAMETER_REGISTRY.get(key)
    if spec is None:
        return plain_hint or "Noch nicht im Parameter-Register dokumentiert."

    parts = [
        f"Register: {spec.label}; Evidenzgrad {spec.evidence_grade}; Quellen: {', '.join(spec.source_ids)}.",
        f"Rolle im Modell: {spec.model_role}.",
        f"Unsicherheit: {spec.uncertainty}.",
    ]
    if spec.caveat:
        parts.append(f"Wichtig: {spec.caveat}")
    if plain_hint:
        parts.append(plain_hint)
    return " ".join(parts)


def render_sidebar() -> dict:
    """Rendert das vollständige Parameter-Panel in der Sidebar."""
    st.sidebar.markdown("## \u2695\ufe0f SimMed 2040")
    st.sidebar.caption("Simulationsplattform Gesundheitssystem")

    params = get_default_params()
    if "user_params" in st.session_state:
        params.update(st.session_state["user_params"])

    if st.sidebar.button("\U0001f504 Reset auf 2026-Realität", use_container_width=True):
        st.session_state["user_params"] = get_default_params()
        st.rerun()

    st.sidebar.divider()

    # ── Simulationseinstellungen ──
    with st.sidebar.expander("\U0001f3af Simulationseinstellungen", expanded=True):
        params["sim_jahre"] = st.slider(
            "Simulationshorizont (Jahre)", 5, 30, params["sim_jahre"],
            help="Simulationsdauer ab Basisjahr 2026",
        )
        modus = st.radio(
            "Modus",
            ["Schnell (100)", "Standard (1.000)", "Präzise (5.000)", "Ultra (10.000)"],
            index=1,
            help="Anzahl Monte-Carlo-Runs (mehr = genauer, langsamer)",
        )
        params["n_runs"] = {
            "Schnell (100)": 100,
            "Standard (1.000)": 1_000,
            "Präzise (5.000)": 5_000,
            "Ultra (10.000)": 10_000,
        }[modus]
        params["basis_seed"] = st.number_input(
            "Basis-Seed", 0, 99999, params["basis_seed"],
            help="Für reproduzierbare Ergebnisse",
        )

    # ── Demografie ──
    with st.sidebar.expander("👥 Demografie & Bevölkerung"):
        st.caption(_parameter_evidence_badge("bevoelkerung_mio"))
        params["bevoelkerung_mio"] = st.slider(
            "Bevölkerung (Mio.)", 70.0, 95.0, params["bevoelkerung_mio"], 0.1,
            help=_parameter_provenance_help("bevoelkerung_mio", "Standardwert im Prototyp: 84,4 Mio."),
        )
        params["geburtenrate"] = st.slider(
            "Geburtenrate (TFR)", 0.80, 2.50, params["geburtenrate"], 0.05,
            help=_parameter_provenance_help("geburtenrate", "TFR = durchschnittliche Kinderzahl je Frau."),
        )
        params["netto_zuwanderung"] = st.slider(
            "Netto-Zuwanderung/Jahr", 0, 800_000, params["netto_zuwanderung"], 10_000,
            help=_parameter_provenance_help("netto_zuwanderung", "Wirkt im Modell als Bevölkerungszufluss und grober Arbeitskräfte-Proxy."),
        )
        params["alterungsfaktor"] = st.slider(
            "Alterungsfaktor", 0.5, 2.0, params["alterungsfaktor"], 0.1,
            help="1.0 = Baseline-Alterung, >1 = beschleunigte Alterung",
        )
        params["urban_anteil"] = st.slider(
            "Urbanisierungsgrad", 0.50, 0.95, params["urban_anteil"], 0.01,
            help="Quelle: Destatis 2025 – 77 %",
        )
        params["einkommen_durchschnitt"] = st.slider(
            "\u00d8 Bruttoeinkommen (\u20ac/Jahr)", 25_000, 80_000,
            params["einkommen_durchschnitt"], 500,
            help="Quelle: Destatis 2025 – ca. 45.000 \u20ac",
        )
        params["einkommens_wachstum"] = st.slider(
            "Einkommenswachstum (%/Jahr)", 0.0, 0.06,
            params["einkommens_wachstum"], 0.005,
            help="Nominales jährliches Wachstum",
        )
        params["pkv_schwelle"] = st.slider(
            "Versicherungspflichtgrenze (\u20ac)", 50_000, 90_000,
            params["pkv_schwelle"], 500,
            help="JAEG 2025: 69.300 \u20ac",
        )

    # ── Versorgungsstruktur ──
    with st.sidebar.expander("\U0001f3e5 Versorgungsstruktur"):
        params["aerzte_gesamt"] = st.slider(
            "Ärzte gesamt", 200_000, 600_000, params["aerzte_gesamt"], 1_000,
            help=_parameter_provenance_help("aerzte_gesamt", "Kopfzahl erklärt noch nicht, wie viele Sprechstunden tatsächlich verfügbar sind."),
        )
        params["aerzte_pro_100k_urban"] = st.slider(
            "Ärzte/100k (urban)", 150, 500, params["aerzte_pro_100k_urban"], 5,
            help="Quelle: KBV 2025 – ca. 280",
        )
        params["aerzte_pro_100k_rural"] = st.slider(
            "Ärzte/100k (ländlich)", 80, 300, params["aerzte_pro_100k_rural"], 5,
            help="Quelle: KBV 2025 – ca. 160",
        )
        params["hausarztpraxen"] = st.slider(
            "Hausarztpraxen", 30_000, 80_000, params["hausarztpraxen"], 500,
            help="Quelle: KBV 2025 – ca. 54.000",
        )
        params["fachpraxen"] = st.slider(
            "Fachpraxen", 20_000, 80_000, params["fachpraxen"], 500,
        )
        params["mvz_anzahl"] = st.slider(
            "MVZ-Anzahl", 1_000, 15_000, params["mvz_anzahl"], 100,
            help="Quelle: KBV 2025 – ca. 4.800",
        )
        params["krankenhaeuser"] = st.slider(
            "Krankenhäuser", 800, 3_000, params["krankenhaeuser"], 10,
            help="Quelle: Destatis 2025 – ca. 1.900",
        )
        params["krankenhausbetten"] = st.slider(
            "Krankenhausbetten", 200_000, 700_000, params["krankenhausbetten"], 5_000,
            help="Quelle: Destatis 2025 – ca. 480.000",
        )
        params["patienten_pro_quartal"] = st.slider(
            "Patienten/Arzt/Quartal", 400, 1_500, params["patienten_pro_quartal"], 10,
        )
        params["arbeitszeit_stunden"] = st.slider(
            "Arbeitszeit (h/Woche)", 35, 70, params["arbeitszeit_stunden"],
            help="Quelle: MB-Monitor 2024 – ca. 52 h",
        )

    # ── Ärzte-Pipeline ──
    with st.sidebar.expander("🎓 Ärzte-Pipeline"):
        st.caption(_parameter_evidence_badge("medizinstudienplaetze"))
        params["medizinstudienplaetze"] = st.slider(
            "Studienplätze/Jahr", 5_000, 25_000, params["medizinstudienplaetze"], 100,
            help=_parameter_provenance_help("medizinstudienplaetze", "Wichtig für Szenarien: Effekte kommen erst nach Studium und Weiterbildung an."),
        )
        params["ausbildungsdauer_jahre"] = st.slider(
            "Studiumsdauer (Jahre)", 5.0, 8.0, params["ausbildungsdauer_jahre"], 0.5,
        )
        params["abwanderungsquote"] = st.slider(
            "Abwanderungsquote", 0.00, 0.15, params["abwanderungsquote"], 0.005,
            help="Anteil neuer Ärzt:innen, die ins Ausland gehen",
        )
        params["einwanderung_aerzte"] = st.slider(
            "Ärzte-Einwanderung/Jahr", 0, 15_000, params["einwanderung_aerzte"], 100,
            help="Quelle: BÄK 2025 – ca. 3.500",
        )
        params["ruhestandsquote"] = st.slider(
            "Ruhestandsquote/Jahr", 0.010, 0.060, params["ruhestandsquote"], 0.005,
        )

    # ── Versicherung & Finanzierung ──
    with st.sidebar.expander("💰 Versicherung & Finanzierung"):
        st.caption(_parameter_evidence_badge("gkv_beitragssatz"))
        params["gkv_beitragssatz"] = st.slider(
            "GKV-Beitragssatz (%)", 12.0, 18.0, params["gkv_beitragssatz"], 0.1,
            help=_parameter_provenance_help("gkv_beitragssatz", "Das ist ein politisch gesetzter Einnahmehebel, keine automatische Modellprognose."),
        )
        params["gkv_zusatzbeitrag"] = st.slider(
            "GKV-Zusatzbeitrag (%)", 0.0, 4.0, params["gkv_zusatzbeitrag"], 0.1,
            help=_parameter_provenance_help("gkv_zusatzbeitrag", "Zusatzbeitrag steht für Finanzierungsdruck und politische Reaktion."),
        )
        params["gkv_anteil"] = st.slider(
            "GKV-Versichertenanteil", 0.70, 0.95, params["gkv_anteil"], 0.01,
            help="Quelle: BMG 2025 – ca. 88 %",
        )
        params["zuzahlungen_gkv"] = st.slider(
            "GKV-Zuzahlungen (Mrd. \u20ac)", 0.0, 10.0, params["zuzahlungen_gkv"], 0.5,
        )
        params["morbi_rsa_staerke"] = st.slider(
            "Morbi-RSA Intensität", 0.0, 2.0, params["morbi_rsa_staerke"], 0.1,
            help="1.0 = aktueller Stand",
        )
        params["staatliche_subventionen"] = st.slider(
            "Bundeszuschuss (Mrd. \u20ac)", 0.0, 30.0,
            params["staatliche_subventionen"], 0.5,
            help="Quelle: BMG 2025 – 14,5 Mrd. \u20ac",
        )
        params["praeventionsbudget"] = st.slider(
            "Präventionsbudget (Mrd. \u20ac)", 0.0, 30.0,
            params["praeventionsbudget"], 0.5,
            help=_parameter_provenance_help("praeventionsbudget", "Prävention kostet kurzfristig Geld; Nutzen entsteht meist verzögert."),
        )

    # ── Politische Hebel ──
    with st.sidebar.expander("\u2696\ufe0f Politische Hebel"):
        params["telemedizin_rate"] = st.slider(
            "Telemedizin-Startrate", 0.0, 0.60, params["telemedizin_rate"], 0.01,
            help=_parameter_provenance_help("telemedizin_rate", "Telemedizin kann Wege sparen, ersetzt aber nicht jede Untersuchung."),
        )
        params["digitalisierung_epa"] = st.slider(
            "ePA-Nutzungsrate (Start)", 0.0, 1.0, params["digitalisierung_epa"], 0.05,
            help="Quelle: gematik 2025 – ca. 15 %",
        )
        params["praevention_effektivitaet"] = st.slider(
            "Präventions-Effektivität", 0.0, 1.0,
            params["praevention_effektivitaet"], 0.05,
            help="0 = keine Wirkung, 1 = maximale Wirkung",
        )
        params["amnog_preisreduktion"] = st.slider(
            "AMNOG-Preisreduktion", 0.0, 0.30, params["amnog_preisreduktion"], 0.01,
        )
        params["drg_niveau"] = st.slider(
            "DRG-Fallpauschalen-Niveau", 0.70, 1.50, params["drg_niveau"], 0.05,
            help="1.0 = aktuelles Niveau",
        )
        params["pflegepersonal_schluessel"] = st.slider(
            "Pflegepersonal-Schlüssel", 0.5, 2.0,
            params["pflegepersonal_schluessel"], 0.05,
            help="1.0 = aktuell, >1 = mehr Personal",
        )
        params["wartezeit_grenze_tage"] = st.slider(
            "Wartezeit-Grenze FA (Tage)", 7, 60,
            params["wartezeit_grenze_tage"],
            help="Gesetzliche Maximal-Wartezeit (TSG)",
        )
        params["igel_rate"] = st.slider(
            "IGeL/Selbstzahler-Rate", 0.0, 0.25, params["igel_rate"], 0.01,
        )

    st.session_state["user_params"] = params
    return params


# ═══════════════════════════════════════════════════════════════════════════════
# UI: DASHBOARD TAB
# ═══════════════════════════════════════════════════════════════════════════════

def _direction_word(delta: float, higher_is_better: bool) -> str:
    """Beschreibt eine KPI-Bewegung in einfacher Sprache."""
    if abs(delta) < 0.05:
        return "kaum verändert"
    if higher_is_better:
        return "verbessert" if delta > 0 else "verschlechtert"
    return "verschlechtert" if delta > 0 else "verbessert"


def _changed_policy_lever_notes(params: dict) -> List[str]:
    """Beschreibt veränderte Szenario-Hebel in Klartext.

    Diese Hinweise sind bewusst qualitativ. Sie helfen Nutzer:innen zu sehen,
    welche von ihnen geänderten Stellschrauben die Ergebnis-Erklärungen besonders
    relevant machen, ohne neue Modellzahlen zu erfinden.
    """
    defaults = get_default_params()
    notes: List[str] = []

    def changed(key: str, tolerance: float = 1e-9) -> bool:
        if key not in params or key not in defaults:
            return False
        try:
            return abs(float(params[key]) - float(defaults[key])) > tolerance
        except (TypeError, ValueError):
            return params[key] != defaults[key]

    if changed("telemedizin_rate"):
        direction = "mehr" if params["telemedizin_rate"] > defaults["telemedizin_rate"] else "weniger"
        notes.append(
            f"Telemedizin wurde auf {direction} digitale Kontakte gestellt. Das beeinflusst vor allem Wege, einfache Kontakte und Praxisentlastung — nicht jede fachärztliche Leistung."
        )
    if changed("digitalisierung_epa"):
        direction = "stärker" if params["digitalisierung_epa"] > defaults["digitalisierung_epa"] else "schwächer"
        notes.append(
            f"ePA/Digitalisierung wurde {direction} gesetzt. Der Effekt hängt davon ab, ob Daten wirklich genutzt werden und ob Praxen dadurch weniger Doppelarbeit haben."
        )
    if changed("praeventionsbudget"):
        direction = "erhöht" if params["praeventionsbudget"] > defaults["praeventionsbudget"] else "gesenkt"
        notes.append(
            f"Das Präventionsbudget wurde {direction}. Prävention kann spätere Krankheitslast senken, kostet aber kurzfristig Geld und wirkt verzögert."
        )
    if changed("medizinstudienplaetze"):
        direction = "mehr" if params["medizinstudienplaetze"] > defaults["medizinstudienplaetze"] else "weniger"
        notes.append(
            f"Es wurden {direction} Medizinstudienplätze eingestellt. Das verändert die Versorgung kaum sofort, sondern erst nach Ausbildung und Weiterbildung."
        )
    if changed("pflegepersonal_schluessel"):
        direction = "verbessert" if params["pflegepersonal_schluessel"] > defaults["pflegepersonal_schluessel"] else "verschlechtert"
        notes.append(
            f"Der Pflegepersonalschlüssel wurde {direction}. Das kann Qualität und Belastung verändern, braucht aber echte verfügbare Fachkräfte."
        )
    return notes


def build_kpi_explanations(agg: pd.DataFrame, params: dict) -> List[Dict[str, str]]:
    """Erzeugt kurze Klartext-Erklärungen für zentrale Live-Ergebnisse.

    Die Texte sind bewusst keine zusätzliche Modelllogik. Sie übersetzen die
    bereits simulierten KPI-Trends in eine nachvollziehbare Ursache-Wirkungs-
    Lesart und nennen die wichtigsten Annahmen, die Nutzer prüfen sollten.
    """
    first = agg.iloc[0]
    last = agg.iloc[-1]
    lever_notes = _changed_policy_lever_notes(params)
    scenario_focus = "\n".join(f"- {note}" for note in lever_notes) if lever_notes else "Keine der aktuell erklärten Haupt-Stellschrauben wurde gegenüber dem Startwert verändert."

    def delta(col: str) -> float:
        return float(last[f"{col}_mean"] - first[f"{col}_mean"])

    explanations = [
        {
            "title": "Warum verändert sich die Facharzt-Wartezeit?",
            "status": _direction_word(delta("wartezeit_fa"), higher_is_better=False),
            "body": (
                "SimMed vergleicht die erwartete Nachfrage mit der verfügbaren Behandlungskapazität. "
                "Steigen Alterung, chronische Erkrankungen oder Nachfrage schneller als Ärzt:innen, Arbeitszeit "
                "und digitale Entlastung, werden Wartezeiten länger. Mehr Telemedizin kann einfache Kontakte "
                "abfedern, ersetzt aber nicht jede fachärztliche Behandlung."
            ),
            "assumption": (
                "Wichtige Annahmen: Ärzt:innen-Kopfzahl ist nicht automatisch Kapazität; Arbeitszeit, regionale "
                "Verteilung und digitale Nutzung bestimmen, wie viel Versorgung wirklich ankommt."
            ),
        },
        {
            "title": "Warum verändert sich der GKV-Saldo?",
            "status": _direction_word(delta("gkv_saldo"), higher_is_better=True),
            "body": (
                "Der Saldo wird besser, wenn Einnahmen, Zusatzbeiträge oder Bundeszuschuss stärker wachsen als "
                "Ausgaben. Er wird schlechter, wenn Alterung, Morbidität, Preise oder zusätzliche Programme die "
                "Kosten schneller erhöhen. Prävention und Digitalisierung können später helfen, kosten aber oft zuerst Geld."
            ),
            "assumption": (
                "Wichtige Annahmen: Beitragssatz, Einkommen, GKV-Anteil, Bundeszuschuss und Ausgabenwachstum wirken zusammen; "
                "kurzfristige Einsparungen sind nicht garantiert."
            ),
        },
        {
            "title": "Warum verändert sich die ländliche Versorgung?",
            "status": _direction_word(delta("versorgungsindex_rural"), higher_is_better=True),
            "body": (
                "Der Index reagiert darauf, ob genug Versorgungskapazität außerhalb großer Städte verfügbar bleibt. "
                "Mehr Studienplätze helfen erst verzögert: nach etwa sechs Jahren bei Absolvent:innen und oft erst "
                "nach 11–13 Jahren bei Fachärzt:innen. Telemedizin kann Wege reduzieren, löst aber keine Personalengpässe allein."
            ),
            "assumption": (
                "Wichtige Annahmen: regionale Verteilung, Ruhestand, Einwanderung von Ärzt:innen und Studienplatz-Pipeline "
                "sind entscheidend für den langfristigen Zugang."
            ),
        },
    ]
    for explanation in explanations:
        explanation["scenario_focus"] = scenario_focus
    return explanations


def render_kpi_explanation_card(agg: pd.DataFrame, params: dict):
    """Zeigt eine Live-Erklärung: Warum haben sich zentrale Ergebnisse bewegt?"""
    st.markdown("---")
    st.markdown("### Warum verändern sich die Ergebnisse?")
    st.caption(
        "Diese Erklärungen übersetzen die simulierten Trends in Klartext. Sie sind keine zusätzliche Prognose, "
        "sondern zeigen, welche Modellannahmen die Richtung treiben."
    )
    for explanation in build_kpi_explanations(agg, params):
        with st.expander(f"{explanation['title']} — {explanation['status']}", expanded=False):
            st.write(explanation["body"])
            if explanation.get("scenario_focus"):
                st.markdown("**Was in diesem Szenario besonders zählt:**")
                st.markdown(explanation["scenario_focus"])
            st.info(explanation["assumption"])


def render_dashboard(agg: pd.DataFrame, params: dict):
    """Zeigt Dashboard-Karten mit Trend-Pfeilen."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    first = agg.iloc[0]
    last = agg.iloc[-1]
    endjahr = int(last["jahr"])

    st.markdown(f"### Kernkennzahlen {endjahr} (Mittelwerte über alle Runs)")

    def delta_pct(col: str) -> float:
        v0, v1 = first[f"{col}_mean"], last[f"{col}_mean"]
        return ((v1 / v0) - 1) * 100 if v0 != 0 else 0

    # Zeile 1: Kosten & Finanzen
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v = last["gesundheitsausgaben_mrd_mean"]
        st.markdown(metric_card("Gesundheitsausgaben", f"{v:.0f} Mrd. \u20ac",
            delta_pct("gesundheitsausgaben_mrd"), False, "metric-card"), unsafe_allow_html=True)
    with c2:
        v = last["bip_anteil_mean"]
        d = v - first["bip_anteil_mean"]
        st.markdown(metric_card("BIP-Anteil Gesundheit", f"{v:.1f} %",
            d * 8, False, "mc-orange"), unsafe_allow_html=True)
    with c3:
        v = last["gkv_beitragssatz_mean"]
        d = v - first["gkv_beitragssatz_mean"]
        st.markdown(metric_card("GKV-Beitragssatz (eff.)", f"{v:.1f} %",
            d * 5, False, "mc-red"), unsafe_allow_html=True)
    with c4:
        v = last["gkv_saldo_mean"]
        cls = "mc-green" if v >= 0 else "mc-red"
        st.markdown(metric_card("GKV-Saldo", f"{v:+.1f} Mrd. \u20ac",
            css_class=cls), unsafe_allow_html=True)

    # Zeile 2: Gesundheit
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v = last["lebenserwartung_mean"]
        d = v - first["lebenserwartung_mean"]
        st.markdown(metric_card("Lebenserwartung", f"{v:.1f} J.",
            d * 8, True, "mc-green"), unsafe_allow_html=True)
    with c2:
        v = last["vermeidbare_mortalitaet_mean"]
        st.markdown(metric_card("Vermeidb. Mortalität", f"{v:.0f} /100k",
            delta_pct("vermeidbare_mortalitaet"), False, "mc-red"), unsafe_allow_html=True)
    with c3:
        v = last["chroniker_rate_mean"]
        d = v - first["chroniker_rate_mean"]
        st.markdown(metric_card("Chroniker-Rate", f"{v:.1f} %",
            d * 2, False, "mc-orange"), unsafe_allow_html=True)
    with c4:
        v = last["bevoelkerung_mio_mean"]
        st.markdown(metric_card("Bevölkerung", f"{v:.1f} Mio.",
            delta_pct("bevoelkerung_mio"), css_class="mc-blue"), unsafe_allow_html=True)

    # Zeile 3: Versorgung
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v = last["aerzte_pro_100k_mean"]
        st.markdown(metric_card("Ärzte / 100k", f"{v:.0f}",
            delta_pct("aerzte_pro_100k"), True, "mc-blue"), unsafe_allow_html=True)
    with c2:
        v = last["wartezeit_fa_mean"]
        st.markdown(metric_card("Wartezeit FA", f"{v:.0f} Tage",
            delta_pct("wartezeit_fa"), False, "mc-orange"), unsafe_allow_html=True)
    with c3:
        v = last["versorgungsindex_rural_mean"]
        d = v - first["versorgungsindex_rural_mean"]
        st.markdown(metric_card("Versorgung Land", f"{v:.0f} / 100",
            d * 1.5, True, "mc-green"), unsafe_allow_html=True)
    with c4:
        v = last["gini_versorgung_mean"]
        st.markdown(metric_card("Gini Versorgung", f"{v:.3f}",
            delta_pct("gini_versorgung"), False, "metric-card"), unsafe_allow_html=True)

    # Zeile 4: System & Personal
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v = last["burnout_rate_mean"]
        d = v - first["burnout_rate_mean"]
        st.markdown(metric_card("Burnout Ärzte", f"{v:.1f} %",
            d * 3, False, "mc-red"), unsafe_allow_html=True)
    with c2:
        v = last["telemedizin_rate_mean"]
        st.markdown(metric_card("Telemedizin", f"{v:.0f} %",
            css_class="mc-blue"), unsafe_allow_html=True)
    with c3:
        v = last["kollaps_wahrscheinlichkeit_mean"]
        cls = "mc-red" if v > 15 else "mc-green"
        st.markdown(metric_card("Kollaps-Risiko", f"{v:.1f} %",
            css_class=cls), unsafe_allow_html=True)
    with c4:
        v = last["zufriedenheit_patienten_mean"]
        d = v - first["zufriedenheit_patienten_mean"]
        cls = "mc-green" if v > 60 else "mc-orange"
        st.markdown(metric_card("Patientenzufr.", f"{v:.0f} / 100",
            d, True, cls), unsafe_allow_html=True)

    # Schnell-Überblick: Trend-Sparklines
    st.markdown("---")
    st.markdown("### Trendübersicht")
    key_kpis = [
        ("gesundheitsausgaben_mrd", "#667eea"),
        ("lebenserwartung", "#11998e"),
        ("wartezeit_fa", "#eb3349"),
        ("gkv_beitragssatz", "#f2994a"),
    ]
    cols = st.columns(len(key_kpis))
    for col, (kpi, color) in zip(cols, key_kpis):
        with col:
            mean_col = f"{kpi}_mean"
            if mean_col in agg.columns:
                fig = go.Figure(go.Scatter(
                    x=agg["jahr"], y=agg[mean_col],
                    mode="lines", fill="tozeroy",
                    line=dict(color=color, width=2),
                    fillcolor=_hex_to_rgba(color, 0.15),
                ))
                fig.update_layout(
                    height=120, margin=dict(l=5, r=5, t=25, b=5),
                    title=dict(text=KPI_LABELS.get(kpi, kpi), font=dict(size=11)),
                    xaxis=dict(visible=False), yaxis=dict(visible=False),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

    render_kpi_explanation_card(agg, params)

    render_political_stakeholder_card(params)


def render_political_stakeholder_card(params: dict):
    """Zeigt die qualitative Stakeholder-Orientierung direkt im Dashboard."""
    feasibility = assess_political_feasibility(params)
    overview = feasibility.get("stakeholder_overview", {})
    lever_notes = feasibility.get("lever_notes", [])

    st.markdown("---")
    st.markdown("### Wer unterstützt? Wer bremst? Warum?")
    st.caption(
        "Diese Karte ist eine qualitative Orientierung zur politischen Umsetzbarkeit — "
        "keine Wahlprognose, kein Lobby-Ranking und kein validierter Score."
    )

    st.info(feasibility.get("summary", "Noch keine politische Einordnung vorhanden."))

    col_support, col_block, col_why = st.columns(3)
    with col_support:
        st.markdown("**Mögliche Unterstützer**")
        supporters = overview.get("likely_supporters") or ["Noch keine Unterstützer-Regel hinterlegt."]
        for item in supporters[:6]:
            st.markdown(f"- {item}")
    with col_block:
        st.markdown("**Mögliche Bremser**")
        blockers = overview.get("likely_blockers") or ["Noch keine Bremser-Regel hinterlegt."]
        for item in blockers[:6]:
            st.markdown(f"- {item}")
    with col_why:
        st.markdown("**Warum ist das wichtig?**")
        st.write(overview.get("plain_summary", "SimMed erklärt neben Modellwerten auch Zuständigkeiten, Budgets und Akzeptanz."))
        st.write(f"**Umsetzbarkeit:** {feasibility.get('category', 'noch nicht bewertet')}")

    if lever_notes:
        with st.expander("Hebel im Klartext anzeigen", expanded=False):
            for note in lever_notes:
                st.markdown(f"**{note['label']}**")
                st.write(note["why_it_matters"])
                st.caption(f"Verzögerung: {note['implementation_lag']} · Reibung: {note['political_friction']}")
                st.caption(f"Achtung: {note['caveat']}")


# ═══════════════════════════════════════════════════════════════════════════════
# UI: STATISTIKEN TAB
# ═══════════════════════════════════════════════════════════════════════════════

def render_statistics(df: pd.DataFrame, agg: pd.DataFrame):
    """Tabellen, Histogramme, Boxplots, Korrelations-Heatmap."""

    last_year = int(df["jahr"].max())
    df_last = df[df["jahr"] == last_year].copy()

    # ── Zusammenfassungstabelle ──
    st.markdown(f"### Statistische Übersicht – Endjahr {last_year}")

    display_kpis = [
        "gesundheitsausgaben_mrd", "bip_anteil", "gkv_beitragssatz",
        "lebenserwartung", "vermeidbare_mortalitaet", "chroniker_rate",
        "aerzte_pro_100k", "wartezeit_fa", "wartezeit_ha",
        "burnout_rate", "zufriedenheit_patienten", "versorgungsindex_rural",
        "gini_versorgung", "kollaps_wahrscheinlichkeit", "telemedizin_rate",
        "bevoelkerung_mio",
    ]

    table_rows = []
    for col in display_kpis:
        if col in df_last.columns:
            vals = df_last[col].dropna()
            table_rows.append({
                "Kennzahl": KPI_LABELS.get(col, col),
                "Mittelwert": f"{vals.mean():.2f}",
                "Std.-Abw.": f"{vals.std():.2f}",
                "Median": f"{vals.median():.2f}",
                "P5": f"{vals.quantile(0.05):.2f}",
                "P95": f"{vals.quantile(0.95):.2f}",
            })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # ── Histogramme ──
    st.markdown("### Verteilungen (Endjahr)")
    sel_hist = st.multiselect(
        "KPIs auswählen",
        display_kpis,
        default=["gesundheitsausgaben_mrd", "lebenserwartung", "wartezeit_fa", "burnout_rate"],
        format_func=lambda x: KPI_LABELS.get(x, x),
        key="hist_select",
    )
    if sel_hist:
        cols = st.columns(min(len(sel_hist), 2))
        for i, kpi in enumerate(sel_hist):
            with cols[i % 2]:
                fig = px.histogram(
                    df_last, x=kpi, nbins=50,
                    title=KPI_LABELS.get(kpi, kpi),
                    color_discrete_sequence=["#667eea"],
                )
                fig.update_layout(
                    showlegend=False, height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                    xaxis_title="", yaxis_title="Häufigkeit",
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Boxplots über Zeit ──
    st.markdown("### Boxplots im Zeitverlauf")
    sel_box = st.selectbox(
        "KPI für Boxplot",
        display_kpis,
        format_func=lambda x: KPI_LABELS.get(x, x),
        key="box_select",
    )
    if sel_box:
        years = sorted(df["jahr"].unique())
        step = max(1, len(years) // 8)
        sampled = years[::step]
        if years[-1] not in sampled:
            sampled.append(years[-1])
        df_box = df[df["jahr"].isin(sampled)]

        fig = px.box(
            df_box, x="jahr", y=sel_box,
            labels={"jahr": "Jahr", sel_box: KPI_LABELS.get(sel_box, sel_box)},
            color_discrete_sequence=["#667eea"],
        )
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # ── Korrelations-Heatmap ──
    st.markdown("### Korrelations-Heatmap (Endjahr)")
    corr_kpis = [
        "gesundheitsausgaben_mrd", "lebenserwartung", "wartezeit_fa",
        "aerzte_pro_100k", "burnout_rate", "chroniker_rate",
        "gkv_beitragssatz", "kollaps_wahrscheinlichkeit",
    ]
    corr_kpis = [c for c in corr_kpis if c in df_last.columns]
    corr_matrix = df_last[corr_kpis].corr()

    labels = [KPI_LABELS.get(c, c)[:20] for c in corr_kpis]
    fig = go.Figure(go.Heatmap(
        z=corr_matrix.values,
        x=labels, y=labels,
        colorscale="RdBu_r", zmid=0,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=10),
    ))
    fig.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI: ZEITREIHEN TAB
# ═══════════════════════════════════════════════════════════════════════════════

def render_timeseries(agg: pd.DataFrame):
    """Interaktive Zeitreihen mit 90%-Konfidenzintervallen."""

    st.markdown("### Zeitreihen mit Konfidenzintervallen (P5–P95)")

    kpi_groups = {
        "Kosten & Finanzen": [
            ("gesundheitsausgaben_mrd", "#667eea"),
            ("bip_anteil", "#f2994a"),
            ("gkv_beitragssatz", "#eb3349"),
            ("gkv_saldo", "#11998e"),
        ],
        "Gesundheit & Mortalität": [
            ("lebenserwartung", "#11998e"),
            ("vermeidbare_mortalitaet", "#eb3349"),
            ("chroniker_rate", "#f2994a"),
            ("qaly_index", "#667eea"),
        ],
        "Versorgung & Zugang": [
            ("aerzte_pro_100k", "#2193b0"),
            ("wartezeit_fa", "#eb3349"),
            ("versorgungsindex_rural", "#11998e"),
            ("gini_versorgung", "#f2994a"),
        ],
        "System & Personal": [
            ("burnout_rate", "#eb3349"),
            ("zufriedenheit_aerzte", "#667eea"),
            ("zufriedenheit_patienten", "#11998e"),
            ("kollaps_wahrscheinlichkeit", "#f45c43"),
        ],
        "Digitalisierung & Prävention": [
            ("telemedizin_rate", "#2193b0"),
            ("digitalisierung", "#667eea"),
            ("praevention_kumuliert", "#11998e"),
        ],
        "Demografie": [
            ("bevoelkerung_mio", "#667eea"),
            ("urban_anteil", "#2193b0"),
            ("gkv_anteil", "#11998e"),
            ("pkv_anteil", "#f2994a"),
        ],
    }

    group_name = st.selectbox("KPI-Gruppe", list(kpi_groups.keys()))
    group = kpi_groups[group_name]

    fig = make_subplots(
        rows=len(group), cols=1,
        subplot_titles=[KPI_LABELS.get(k, k) for k, _ in group],
        vertical_spacing=0.08,
    )

    years = agg["jahr"].values

    for idx, (kpi, color) in enumerate(group, 1):
        mean_col = f"{kpi}_mean"
        p5_col = f"{kpi}_p5"
        p95_col = f"{kpi}_p95"

        if mean_col not in agg.columns:
            continue

        # Konfidenzband (P5–P95)
        if p5_col in agg.columns and p95_col in agg.columns:
            upper = agg[p95_col].values
            lower = agg[p5_col].values
            fig.add_trace(go.Scatter(
                x=np.concatenate([years, years[::-1]]),
                y=np.concatenate([upper, lower[::-1]]),
                fill="toself",
                fillcolor=_hex_to_rgba(color, 0.15),
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ), row=idx, col=1)

        # Mittelwert-Linie
        fig.add_trace(go.Scatter(
            x=years, y=agg[mean_col].values,
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=3),
            name=KPI_LABELS.get(kpi, kpi),
            showlegend=False,
        ), row=idx, col=1)

    fig.update_layout(
        height=280 * len(group),
        margin=dict(l=30, r=20, t=35, b=20),
    )
    fig.update_xaxes(title_text="Jahr", row=len(group), col=1)
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI: REGIONALE KARTE TAB
# ═══════════════════════════════════════════════════════════════════════════════

def render_regional_map(df_reg: pd.DataFrame):
    """Deutschland-Karte als Bubble-Map mit Bundesland-Details."""

    st.markdown("### Regionale Verteilung (Endjahr-Mittelwerte)")

    agg_reg = df_reg.groupby("bundesland").agg(
        aerzte=("aerzte", "mean"),
        bevoelkerung=("bevoelkerung", "mean"),
        aerzte_pro_100k=("aerzte_pro_100k", "mean"),
    ).reset_index()

    # Koordinaten und Kürzel
    agg_reg["lat"] = agg_reg["bundesland"].map(dict(zip(BUNDESLAENDER, BL_COORDS_LAT)))
    agg_reg["lon"] = agg_reg["bundesland"].map(dict(zip(BUNDESLAENDER, BL_COORDS_LON)))
    agg_reg["bl_kurz"] = agg_reg["bundesland"].map(dict(zip(BUNDESLAENDER, BL_KURZ)))

    kpi_choice = st.selectbox(
        "Dargestellte Kennzahl",
        ["aerzte_pro_100k", "aerzte", "bevoelkerung"],
        format_func=lambda x: {
            "aerzte_pro_100k": "Ärzte pro 100.000",
            "aerzte": "Ärzte (absolut)",
            "bevoelkerung": "Bevölkerung",
        }[x],
        key="map_kpi",
    )

    # Bubble Map
    hover_text = agg_reg.apply(
        lambda r: (
            f"<b>{r['bundesland']}</b><br>"
            f"Ärzte/100k: {r['aerzte_pro_100k']:.0f}<br>"
            f"Ärzte: {r['aerzte']:,.0f}<br>"
            f"Bevölkerung: {r['bevoelkerung']/1e6:.2f} Mio."
        ),
        axis=1,
    )

    size_vals = agg_reg[kpi_choice]
    size_norm = (size_vals / size_vals.max() * 35 + 8).values

    fig = go.Figure()
    fig.add_trace(go.Scattergeo(
        lat=agg_reg["lat"], lon=agg_reg["lon"],
        text=hover_text,
        hoverinfo="text",
        marker=dict(
            size=size_norm,
            color=agg_reg["aerzte_pro_100k"],
            colorscale="RdYlGn",
            colorbar=dict(title="Ärzte/100k"),
            line=dict(width=1, color="white"),
            sizemode="diameter",
        ),
    ))
    # Labels
    fig.add_trace(go.Scattergeo(
        lat=agg_reg["lat"], lon=agg_reg["lon"],
        text=agg_reg["bl_kurz"],
        mode="text",
        textfont=dict(size=9, color="black"),
        hoverinfo="skip",
    ))

    fig.update_geos(
        scope="europe",
        center=dict(lat=51.2, lon=10.4),
        projection_scale=9,
        showland=True, landcolor="rgb(243,243,243)",
        showocean=True, oceancolor="rgb(210,230,255)",
        showcountries=True, countrycolor="rgb(200,200,200)",
        showlakes=False,
        lataxis_range=[47.0, 55.5],
        lonaxis_range=[5.5, 15.5],
    )
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Tile-Grid-Heatmap (alternative Darstellung)
    st.markdown("### Tile-Grid-Karte")
    # Positionen für Tile-Grid (col, row)
    tile_pos = {
        "SH": (2, 0), "MV": (3, 0),
        "HH": (2, 1), "HB": (1, 1), "NI": (1, 2), "BE": (4, 1), "BB": (3, 1),
        "ST": (3, 2), "NW": (0, 2),
        "TH": (3, 3), "SN": (4, 3), "HE": (2, 3),
        "RP": (1, 4), "SL": (0, 4),
        "BW": (2, 5), "BY": (3, 5),
    }

    grid = np.full((6, 5), np.nan)
    text_grid = np.full((6, 5), "", dtype=object)
    bl_kurz_map = dict(zip(BL_KURZ, range(len(BL_KURZ))))

    for bl_k, (c, r) in tile_pos.items():
        idx = bl_kurz_map.get(bl_k)
        if idx is not None:
            row_data = agg_reg[agg_reg["bl_kurz"] == bl_k]
            if not row_data.empty:
                val = row_data["aerzte_pro_100k"].values[0]
                grid[r, c] = val
                text_grid[r, c] = f"{bl_k}<br>{val:.0f}"

    fig2 = go.Figure(go.Heatmap(
        z=grid, text=text_grid, texttemplate="%{text}",
        colorscale="RdYlGn", showscale=True,
        colorbar=dict(title="Ärzte/100k"),
        hoverinfo="text",
        xgap=3, ygap=3,
    ))
    fig2.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False, autorange="reversed"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Detailtabelle
    st.markdown("### Bundesland-Details")
    table = agg_reg[["bundesland", "bevoelkerung", "aerzte", "aerzte_pro_100k"]].copy()
    table.columns = ["Bundesland", "Bevölkerung", "Ärzte", "Ärzte/100k"]
    table["Bevölkerung"] = table["Bevölkerung"].apply(lambda x: f"{x/1e6:.2f} Mio.")
    table["Ärzte"] = table["Ärzte"].apply(lambda x: f"{x:,.0f}")
    table["Ärzte/100k"] = table["Ärzte/100k"].apply(lambda x: f"{x:.0f}")
    table = table.sort_values("Bundesland")
    st.dataframe(table, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI: SZENARIEN-VERGLEICH TAB
# ═══════════════════════════════════════════════════════════════════════════════

def render_scenarios():
    """Vergleicht bis zu 4 gespeicherte Szenarien nebeneinander."""

    st.markdown("### Szenarien-Vergleich")

    if "szenarien" not in st.session_state:
        st.session_state["szenarien"] = {}

    szenarien = st.session_state["szenarien"]
    n = len(szenarien)

    if n == 0:
        st.info(
            "Noch keine Szenarien gespeichert. Aktivieren Sie "
            "'Als Szenario speichern' in der Seitenleiste und starten Sie eine Simulation."
        )
        return

    st.write(f"**{n} Szenario(s) gespeichert** (max. 4)")

    selected = st.multiselect(
        "Szenarien auswählen",
        list(szenarien.keys()),
        default=list(szenarien.keys())[:4],
        key="scenario_select",
    )
    if not selected:
        return

    compare_kpis = [
        "gesundheitsausgaben_mrd", "lebenserwartung", "wartezeit_fa",
        "aerzte_pro_100k", "burnout_rate", "kollaps_wahrscheinlichkeit",
        "gkv_beitragssatz", "vermeidbare_mortalitaet", "zufriedenheit_patienten",
    ]
    compare_kpi = st.selectbox(
        "Vergleichs-KPI",
        compare_kpis,
        format_func=lambda x: KPI_LABELS.get(x, x),
        key="scenario_kpi",
    )

    colors = ["#667eea", "#eb3349", "#11998e", "#f2994a"]
    fig = go.Figure()
    for i, name in enumerate(selected[:4]):
        a = szenarien[name]["agg"]
        mc = f"{compare_kpi}_mean"
        if mc in a.columns:
            fig.add_trace(go.Scatter(
                x=a["jahr"], y=a[mc],
                mode="lines+markers",
                name=name,
                line=dict(color=colors[i % 4], width=2.5),
                marker=dict(size=4),
            ))
    fig.update_layout(
        height=480, margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(x=0, y=1),
        xaxis_title="Jahr",
        yaxis_title=KPI_LABELS.get(compare_kpi, compare_kpi),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Vergleichstabelle
    st.markdown("### Vergleich der Endwerte")
    rows = []
    for name in selected[:4]:
        a = szenarien[name]["agg"]
        last = a.iloc[-1]
        rows.append({
            "Szenario": name,
            "Ausgaben (Mrd.)": f"{last.get('gesundheitsausgaben_mrd_mean', 0):.0f}",
            "Lebenserwart.": f"{last.get('lebenserwartung_mean', 0):.1f}",
            "Wartezeit FA": f"{last.get('wartezeit_fa_mean', 0):.0f} T.",
            "Beitragssatz": f"{last.get('gkv_beitragssatz_mean', 0):.1f} %",
            "Burnout": f"{last.get('burnout_rate_mean', 0):.1f} %",
            "Kollaps": f"{last.get('kollaps_wahrscheinlichkeit_mean', 0):.1f} %",
            "Zufriedenheit": f"{last.get('zufriedenheit_patienten_mean', 0):.0f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Radar-Chart
    st.markdown("### Radar-Vergleich (normalisiert)")
    radar_kpis = [
        "lebenserwartung", "zufriedenheit_patienten", "versorgungsindex_rural",
        "aerzte_pro_100k", "qaly_index",
    ]
    radar_labels = [KPI_LABELS.get(k, k)[:18] for k in radar_kpis]

    fig_radar = go.Figure()
    for i, name in enumerate(selected[:4]):
        a = szenarien[name]["agg"]
        last = a.iloc[-1]
        values = []
        for k in radar_kpis:
            mc = f"{k}_mean"
            values.append(last.get(mc, 0))
        # Normalisierung auf 0–100
        vmin = [70, 15, 15, 150, 0.45]
        vmax = [90, 100, 100, 600, 0.96]
        normed = [max(0, min(100, (v - mn) / (mx - mn) * 100))
                  for v, mn, mx in zip(values, vmin, vmax)]
        normed.append(normed[0])  # Schließen
        fig_radar.add_trace(go.Scatterpolar(
            r=normed,
            theta=radar_labels + [radar_labels[0]],
            name=name,
            line=dict(color=colors[i % 4]),
            fill="toself",
            fillcolor=_hex_to_rgba(colors[i % 4], 0.1),
        ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=450, margin=dict(l=40, r=40, t=20, b=20),
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Löschen
    st.markdown("---")
    to_del = st.selectbox("Szenario löschen", ["(keins)"] + list(szenarien.keys()), key="del_sc")
    if to_del != "(keins)" and st.button(f"'{to_del}' entfernen"):
        del st.session_state["szenarien"][to_del]
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# UI: EXPORT TAB
# ═══════════════════════════════════════════════════════════════════════════════

def render_export(df: pd.DataFrame, agg: pd.DataFrame, df_reg: pd.DataFrame, params: dict):
    """CSV-, Excel-Export und Parameterübersicht."""

    st.markdown("### Daten-Export")

    c1, c2, c3 = st.columns(3)
    with c1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Rohdaten (CSV)",
            csv, "simmed_rohdaten.csv", "text/csv",
            use_container_width=True,
            help="Alle Einzelruns × Jahre × KPIs",
        )
    with c2:
        csv_agg = agg.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Aggregiert (CSV)",
            csv_agg, "simmed_aggregiert.csv", "text/csv",
            use_container_width=True,
        )
    with c3:
        csv_reg = df_reg.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Regional (CSV)",
            csv_reg, "simmed_regional.csv", "text/csv",
            use_container_width=True,
        )

    # Excel
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            agg.to_excel(w, sheet_name="Aggregiert", index=False)
            df_reg.groupby("bundesland").mean(numeric_only=True).to_excel(
                w, sheet_name="Regional"
            )
            # Parameter-Sheet
            pd.DataFrame([
                {"Parameter": k, "Wert": str(v)} for k, v in params.items()
            ]).to_excel(w, sheet_name="Parameter", index=False)

        st.download_button(
            "Vollständiger Report (Excel)",
            buf.getvalue(), "simmed_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except ImportError:
        st.warning("Für Excel-Export: `pip install openpyxl`")

    # Parameter-Übersicht
    st.markdown("### Aktuelle Simulationsparameter")
    param_rows = []
    categories = {
        "Demografie": [
            "bevoelkerung_mio", "geburtenrate", "netto_zuwanderung",
            "alterungsfaktor", "urban_anteil", "einkommen_durchschnitt",
            "einkommens_wachstum", "pkv_schwelle",
        ],
        "Versorgung": [
            "aerzte_gesamt", "aerzte_pro_100k_urban", "aerzte_pro_100k_rural",
            "hausarztpraxen", "fachpraxen", "mvz_anzahl", "krankenhaeuser",
            "krankenhausbetten", "patienten_pro_quartal", "arbeitszeit_stunden",
        ],
        "Pipeline": [
            "medizinstudienplaetze", "ausbildungsdauer_jahre",
            "abwanderungsquote", "einwanderung_aerzte", "ruhestandsquote",
        ],
        "Finanzen": [
            "gkv_beitragssatz", "gkv_zusatzbeitrag", "gkv_anteil",
            "zuzahlungen_gkv", "morbi_rsa_staerke",
            "staatliche_subventionen", "praeventionsbudget",
        ],
        "Politik": [
            "telemedizin_rate", "digitalisierung_epa",
            "praevention_effektivitaet", "amnog_preisreduktion",
            "drg_niveau", "pflegepersonal_schluessel",
            "wartezeit_grenze_tage", "igel_rate",
        ],
    }
    for cat, keys in categories.items():
        for k in keys:
            if k in params:
                param_rows.append({"Kategorie": cat, "Parameter": k, "Wert": params[k]})
    st.dataframe(pd.DataFrame(param_rows), use_container_width=True, hide_index=True)



# ═══════════════════════════════════════════════════════════════════════════════
# UI: LEARNING PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_learning_page():
    """Erklärt SimMed als übersichtliche, schön strukturierte Lernseite."""
    st.markdown("""
<style>
.learn-hero {
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 28px;
  padding: 34px 36px;
  margin: 8px 0 24px 0;
  background: radial-gradient(circle at 15% 10%, rgba(24,226,153,0.22), transparent 28%),
              linear-gradient(135deg, #ffffff 0%, #f7fffb 55%, #ffffff 100%);
  box-shadow: 0 8px 30px rgba(0,0,0,0.045);
}
.learn-kicker {
  display: inline-block;
  padding: 5px 12px;
  border-radius: 999px;
  background: #d4fae8;
  color: #0f7d55;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  margin-bottom: 14px;
}
.learn-hero h2 { font-size: 42px; line-height: 1.08; letter-spacing: -0.9px; margin: 0 0 12px 0; color: #0d0d0d; }
.learn-hero p { font-size: 18px; line-height: 1.55; color: #3f3f46; max-width: 920px; margin: 0; }
.learn-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 18px 0 26px 0; }
.learn-card { border: 1px solid rgba(0,0,0,0.06); border-radius: 20px; background: #fff; padding: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); min-height: 172px; }
.learn-card h3 { font-size: 20px; letter-spacing: -0.2px; margin: 0 0 8px 0; color: #0d0d0d; }
.learn-card p, .learn-card li { color: #52525b; line-height: 1.5; font-size: 15px; }
.learn-card ul { margin: 8px 0 0 18px; padding: 0; }
.learn-step { display: flex; gap: 14px; padding: 16px 0; border-bottom: 1px solid rgba(0,0,0,0.06); }
.learn-step:last-child { border-bottom: 0; }
.learn-num { flex: 0 0 auto; width: 34px; height: 34px; border-radius: 999px; display: grid; place-items: center; background: #0d0d0d; color: white; font-weight: 700; }
.learn-step h4 { margin: 0 0 4px 0; font-size: 17px; color: #0d0d0d; }
.learn-step p { margin: 0; color: #52525b; line-height: 1.48; }
.learn-pill { display: inline-block; border: 1px solid rgba(0,0,0,0.08); border-radius: 999px; padding: 6px 11px; margin: 4px 5px 4px 0; background: #fafafa; font-size: 13px; color: #333; }
.learn-callout { border-left: 5px solid #18E299; background: #f4fffa; border-radius: 16px; padding: 18px 20px; margin: 18px 0; color: #2f3a35; }
@media (max-width: 900px) { .learn-grid { grid-template-columns: 1fr; } .learn-hero h2 { font-size: 32px; } }
</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="learn-hero">
  <div class="learn-kicker">Lernseite</div>
  <h2>SimMed verständlich erklärt</h2>
  <p>
    SimMed ist ein Simulator für das deutsche Gesundheitssystem. Die Plattform soll nicht nur Zahlen ausgeben,
    sondern erklären, warum ein Ergebnis entsteht, welche Annahmen dahinterliegen und ob eine Reform politisch
    realistisch umsetzbar wäre.
  </p>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 1. Wofür ist SimMed gedacht?")
    st.markdown("""
<div class="learn-grid">
  <div class="learn-card">
    <h3>Politik besser verstehen</h3>
    <p>SimMed zeigt, was passieren könnte, wenn man Stellschrauben wie Studienplätze, Prävention, Digitalisierung oder GKV-Beiträge verändert.</p>
  </div>
  <div class="learn-card">
    <h3>Nicht nur Zahlen</h3>
    <p>Die App soll erklären: Warum steigt eine Wartezeit? Warum wirkt eine Maßnahme erst später? Wer könnte politisch blockieren?</p>
  </div>
  <div class="learn-card">
    <h3>Kein Orakel</h3>
    <p>SimMed ist kein fertiges Prognosemodell. Es ist ein transparenter Denk- und Lernraum mit sichtbaren Annahmen und Unsicherheiten.</p>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 2. Wie funktioniert die Simulation?")
    st.markdown("""
<div class="learn-card">
  <div class="learn-step"><div class="learn-num">1</div><div><h4>Du veränderst eine Stellschraube</h4><p>Zum Beispiel: weniger Medizinstudienplätze, mehr Telemedizin oder höheres Präventionsbudget.</p></div></div>
  <div class="learn-step"><div class="learn-num">2</div><div><h4>Das Modell berechnet viele mögliche Zukünfte</h4><p>Monte-Carlo bedeutet: Die App simuliert nicht nur eine Zukunft, sondern viele Varianten mit Zufallsschwankungen.</p></div></div>
  <div class="learn-step"><div class="learn-num">3</div><div><h4>Die Effekte laufen über Wirkungsketten</h4><p>Beispiel: weniger Studienplätze → nach Jahren weniger Absolventen → später weniger Fachärzte → mehr Wartezeit.</p></div></div>
  <div class="learn-step"><div class="learn-num">4</div><div><h4>SimMed erklärt Ergebnis und Unsicherheit</h4><p>Wichtig ist nicht nur der Wert, sondern warum er entsteht und welche Annahmen unsicher sind.</p></div></div>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 3. Die wichtigsten Bereiche")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
<div class="learn-card">
  <h3>Versorgung</h3>
  <p>Ärzte, Praxen, Krankenhäuser, ländliche Versorgung, Wartezeiten.</p>
  <span class="learn-pill">Ärzte pro 100k</span><span class="learn-pill">Wartezeit</span><span class="learn-pill">Landversorgung</span>
</div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="learn-card">
  <h3>Finanzierung</h3>
  <p>GKV-Einnahmen, Ausgaben, Beitragssatz, Bundeszuschuss und Kostenentwicklung.</p>
  <span class="learn-pill">GKV-Saldo</span><span class="learn-pill">BIP-Anteil</span><span class="learn-pill">Ausgaben</span>
</div>
""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div class="learn-card">
  <h3>Gesundheit</h3>
  <p>Chronische Erkrankungen, vermeidbare Mortalität, QALY-Index und Lebenserwartung als Modellindikatoren.</p>
  <span class="learn-pill">Chroniker</span><span class="learn-pill">Mortalität</span><span class="learn-pill">QALY</span>
</div>
""", unsafe_allow_html=True)
        st.markdown("""
<div class="learn-card">
  <h3>Politische Umsetzbarkeit</h3>
  <p>SimMed soll zeigen, ob eine Reform nicht nur rechnerisch wirkt, sondern politisch realistisch durchsetzbar ist.</p>
  <span class="learn-pill">Gewinner</span><span class="learn-pill">Blockierer</span><span class="learn-pill">Machbarkeit</span>
</div>
""", unsafe_allow_html=True)

    st.markdown("### 4. Beispiel: weniger Medizinstudienplätze")
    st.markdown("""
<div class="learn-callout">
  <b>Einfach erklärt:</b> Wenn heute weniger Menschen Medizin studieren, gibt es nicht sofort weniger Ärztinnen und Ärzte.
  Der Effekt kommt verzögert, weil Studium und Weiterbildung viele Jahre dauern. Kurzfristig ändern sich Wartezeiten kaum.
  Nach einigen Jahren kann aber der Nachwuchs fehlen – besonders bei Fachärzten und in Regionen, die ohnehin unterversorgt sind.
</div>
""", unsafe_allow_html=True)

    st.markdown("### 5. Wie kommen neue Beiträge ins Modell?")
    workflow_steps = plain_language_workflow_summary()
    st.markdown("""
<div class="learn-callout">
  <b>Wichtig:</b> Externe KI- oder Menschenbeiträge sind zuerst Vorschläge – keine Modellfakten.
  Sie verändern die Simulation nicht automatisch. Erst nach Prüfung, Begründung und Integration mit Provenienz
  dürfen sie ins Modell einfließen.
</div>
""", unsafe_allow_html=True)
    for idx, step in enumerate(workflow_steps, start=1):
        st.markdown(
            f"""
<div class="learn-step">
  <div class="learn-num">{idx}</div>
  <div><h4>Schritt {idx}</h4><p>{step}</p></div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### 6. Was kommt als Nächstes?")
    st.markdown("""
<div class="learn-grid">
  <div class="learn-card"><h3>Entscheidungsrubrik</h3><p>Zu jedem Szenario: Was passiert, warum passiert es, wer gewinnt/verliert, wer blockiert?</p></div>
  <div class="learn-card"><h3>Expertenrat</h3><p>Als Nächstes soll diese Prüfkette in API und UI sichtbar werden, ohne dass Einsendungen direkt Parameter verändern.</p></div>
  <div class="learn-card"><h3>Strategie-Modus</h3><p>Später: Wie könnte man eine Reform politisch wirklich durchsetzen – mit Reihenfolge, Bündnissen und Kompromissen?</p></div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="SimMed Deutschland 2040",
        page_icon="\u2695\ufe0f",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Parameter-Sidebar
    params = render_sidebar()

    st.sidebar.divider()

    # Szenario-Speicherung
    szenario_name = st.sidebar.text_input(
        "Szenario-Name",
        value=f"Szenario {len(st.session_state.get('szenarien', {})) + 1}",
    )
    save_scenario = st.sidebar.checkbox("Als Szenario speichern", value=False)

    run_btn = st.sidebar.button(
        "\U0001f52c Simulation starten",
        type="primary",
        use_container_width=True,
    )

    # Header
    st.title("\u2695\ufe0f SimMed Deutschland 2040")
    st.caption(
        "Monte-Carlo-Simulationsplattform für das deutsche Gesundheitssystem \u2013 "
        f"{params['n_runs']:,} Runs \u00d7 {params['sim_jahre']} Jahre"
    )

    # Warnung bei geänderten Parametern
    if "last_params_hash" in st.session_state and "agg" in st.session_state:
        current_hash = _params_hash(params)
        if current_hash != st.session_state["last_params_hash"]:
            st.warning(
                "Parameter wurden seit der letzten Simulation geändert. "
                "Klicken Sie auf **'Simulation starten'** für aktualisierte Ergebnisse."
            )

    # ── Simulation ausführen ──
    if run_btn:
        progress_bar = st.progress(0, text="Monte-Carlo-Simulation läuft ...")
        t0 = time.time()

        def on_progress(p: float):
            n_done = int(p * params["n_runs"])
            progress_bar.progress(
                p,
                text=f"Simulation: {p*100:.0f} % ({n_done:,} / {params['n_runs']:,} Runs)",
            )

        df, df_reg = run_simulation(
            params,
            n_runs=params["n_runs"],
            n_years=params["sim_jahre"],
            base_seed=params["basis_seed"],
            progress_callback=on_progress,
        )
        elapsed = time.time() - t0
        progress_bar.progress(1.0, text=f"Fertig! {params['n_runs']:,} Runs in {elapsed:.1f} s")

        agg = aggregate_kpis(df)

        st.session_state["df"] = df
        st.session_state["df_reg"] = df_reg
        st.session_state["agg"] = agg
        st.session_state["last_params_hash"] = _params_hash(params)

        # Szenario speichern
        if save_scenario and szenario_name:
            if "szenarien" not in st.session_state:
                st.session_state["szenarien"] = {}
            # Max 4 Szenarien
            if len(st.session_state["szenarien"]) >= 4:
                oldest = list(st.session_state["szenarien"].keys())[0]
                del st.session_state["szenarien"][oldest]
            st.session_state["szenarien"][szenario_name] = {
                "agg": agg.copy(),
                "params": params.copy(),
            }

    # ── Tabs ──
    if "agg" in st.session_state:
        tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "Lernen",
            "Dashboard",
            "Statistiken & Verteilungen",
            "Zeitreihen",
            "Regionale Karte",
            "Szenarien-Vergleich",
            "Export & Einstellungen",
        ])

        with tab0:
            render_learning_page()
        with tab1:
            render_dashboard(st.session_state["agg"], params)
        with tab2:
            render_statistics(st.session_state["df"], st.session_state["agg"])
        with tab3:
            render_timeseries(st.session_state["agg"])
        with tab4:
            render_regional_map(st.session_state["df_reg"])
        with tab5:
            render_scenarios()
        with tab6:
            render_export(
                st.session_state["df"], st.session_state["agg"],
                st.session_state["df_reg"], params,
            )
    else:
        # Startseite
        render_learning_page()
        st.info("Konfigurieren Sie Parameter in der Seitenleiste und klicken Sie auf **'Simulation starten'**.")

        with st.expander("Über SimMed Deutschland 2040", expanded=False):
            st.markdown("""
**SimMed Deutschland 2040** simuliert das gesamte deutsche Gesundheitssystem
(GKV + PKV) über 5–30 Jahre mittels Monte-Carlo-Verfahren.

**Kernmerkmale:**
- 100 – 10.000 parallele Monte-Carlo-Simulationen (joblib-parallelisiert)
- 7 dynamische Feedback-Loops mit Ausweichmechanismen
- 4 stochastische Schocks (Pandemie, Cyberangriff, Streik, Rezession)
- 29 Ziel-KPIs mit Konfidenzintervallen
- Regionale Analyse nach 16 Bundesländern
- Szenarien-Vergleich (bis zu 4 parallel)
- Export als CSV / Excel

**Feedback-Mechanismen:**
1. **Ärztemangel** \u2192 Gehaltsanreize \u2192 mehr Studienplätze + Immigration
2. **Wartezeiten** \u2192 PKV-Wechsel / Telemedizin / Behandlungsverzicht / Auslandsbehandlung
3. **Ländliche Lücken** \u2192 längere Fahrtwege \u2192 höhere Mortalität (Herzinfarkt, Schlaganfall)
4. **PKV-Wachstum** \u2192 Rosinenpickerei \u2192 GKV-Belastung durch Morbi-RSA
5. **Kostenexplosion** \u2192 Politik reagiert (Beitragserhöhung, Leistungskürzung, Sonderzuschüsse)
6. **Prävention** \u2192 langfristige Reduktion der Chroniker-Rate
7. **Burnout** \u2192 Ärzte-Abwanderung \u2192 Versorgungslücken

**Datenquellen:** Destatis, BÄK, KBV, BMG, gematik, BAMF, HRK (Stand 2025/2026)
""")


if __name__ == "__main__":
    main()
