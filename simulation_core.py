"""Simulation core for SimMed Deutschland 2040.

This module contains the non-UI model: baseline parameters, Monte-Carlo
state transitions, KPI extraction and aggregation.  Keep Streamlit-specific
code in app.py and agent/API wrappers in api.py so the model can be tested,
versioned and called by external agents independently of the UI.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from joblib import Parallel, delayed
    HAS_JOBLIB = True
except ImportError:  # pragma: no cover - optional acceleration
    HAS_JOBLIB = False

MODEL_VERSION = "simmed-core-v0.2"
BASE_YEAR = 2026

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
    # Use thread backend by default for local Streamlit stability. Process-based
    # loky can SIGSEGV on some macOS/Python builds; override via env if needed.
    n_cores = min(max(1, multiprocessing.cpu_count() - 1), int(os.getenv("SIMMED_MAX_WORKERS", "4")))
    joblib_backend = os.getenv("SIMMED_JOBLIB_BACKEND", "threading")
    batch_size = max(1, n_runs // 10)

    all_kpis: List[np.ndarray] = []
    all_regional: List[np.ndarray] = []

    for batch_start in range(0, n_runs, batch_size):
        batch_end = min(batch_start + batch_size, n_runs)
        seeds = list(range(base_seed + batch_start, base_seed + batch_end))

        if HAS_JOBLIB and len(seeds) > 1:
            try:
                batch = Parallel(n_jobs=n_cores, backend=joblib_backend)(
                    delayed(_run_single_sim)(params, s, n_years) for s in seeds
                )
            except Exception as exc:
                if progress_callback:
                    progress_callback(min(1.0, batch_start / n_runs))
                warnings.warn(
                    f"Joblib backend '{joblib_backend}' failed ({type(exc).__name__}); "
                    "falling back to sequential simulation for stability.",
                    RuntimeWarning,
                )
                batch = [_run_single_sim(params, s, n_years) for s in seeds]
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


def _validate_scenario_inputs(parameter_changes: dict[str, Any], n_runs: int, n_years: int) -> dict[str, Any]:
    """Return default parameters after validating agent-supplied scenario inputs."""
    params = get_default_params()
    unknown = sorted(set(parameter_changes) - set(params))
    if unknown:
        raise ValueError(f"unknown parameters: {unknown}")
    if not 1 <= n_runs <= 1000:
        raise ValueError("n_runs must be between 1 and 1000 for the agent API")
    if not 1 <= n_years <= 30:
        raise ValueError("n_years must be between 1 and 30 for the agent API")
    return params


def build_scenario_manifest(
    parameter_changes: Optional[dict[str, Any]] = None,
    *,
    n_runs: int = 100,
    n_years: int = 15,
    seed: int = 42,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a reproducible scenario manifest without executing the simulation.

    The manifest is intentionally deterministic except for ``generated_at`` so
    agents can submit, archive and compare scenarios before running them.  It
    documents the model version, seed, bounded run configuration, changed
    parameters, parameter provenance available in the registry, and core caveats.
    """
    from parameter_registry import PARAMETER_REGISTRY

    parameter_changes = parameter_changes or {}
    defaults = _validate_scenario_inputs(parameter_changes, n_runs, n_years)
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed_parameters = []
    for key in sorted(parameter_changes):
        spec = PARAMETER_REGISTRY.get(key)
        changed_parameters.append({
            "key": key,
            "default": defaults[key],
            "value": parameter_changes[key],
            "registered": spec is not None,
            "unit": spec.unit if spec else "undocumented",
            "source_ids": list(spec.source_ids) if spec else [],
            "evidence_grade": spec.evidence_grade if spec else "E",
            "uncertainty": spec.uncertainty if spec else "not yet documented in parameter registry",
            "caveat": spec.caveat if spec else "Parameter exists in model defaults but lacks registry provenance coverage.",
        })
    canonical = {
        "model_version": MODEL_VERSION,
        "base_year": BASE_YEAR,
        "years": n_years,
        "runs": n_runs,
        "seed": seed,
        "parameter_changes": {k: parameter_changes[k] for k in sorted(parameter_changes)},
    }
    scenario_id = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": "simmed-scenario-manifest-v1",
        "scenario_id": scenario_id,
        "generated_at": generated_at,
        **canonical,
        "changed_parameters": changed_parameters,
        "reproducibility": {
            "simulation_entrypoint": "simulation_core.run_scenario",
            "api_endpoint": "POST /simulate",
            "manifest_endpoint": "POST /scenario-manifest",
            "random_seed_policy": "Monte-Carlo run seeds are base seed + run index.",
        },
        "model_caveats": [
            "Medical study-place effects enter physician supply only after roughly 6+ years; specialist effects after roughly 11-13+ years.",
            "Physician headcount is not capacity; FTE, specialty, age, region and productivity must be interpreted separately.",
            "Hospital beds are not usable capacity without staffing and occupancy constraints.",
            "Prevention and digitalization effects are delayed and uncertain, not immediate flat cost savings.",
            "Separate latent demand, realized utilization and unmet need when interpreting access KPIs.",
        ],
    }


def run_scenario(parameter_changes: Optional[dict[str, Any]] = None, *, n_runs: int = 100, n_years: int = 15, seed: int = 42) -> dict[str, Any]:
    """Run a bounded scenario and return agent-friendly summary data.

    Raises:
        ValueError: if unknown parameter keys are supplied.
    """
    parameter_changes = parameter_changes or {}
    params = _validate_scenario_inputs(parameter_changes, n_runs, n_years)
    params.update(parameter_changes)
    manifest = build_scenario_manifest(parameter_changes, n_runs=n_runs, n_years=n_years, seed=seed)
    df, df_reg = run_simulation(params, n_runs=n_runs, n_years=n_years, base_seed=seed)
    agg = aggregate_kpis(df)
    last = agg.iloc[-1].to_dict()
    return {
        "model_version": MODEL_VERSION,
        "scenario_id": manifest["scenario_id"],
        "manifest": manifest,
        "years": n_years,
        "runs": n_runs,
        "seed": seed,
        "parameter_changes": parameter_changes,
        "final_year_summary": {k: float(v) for k, v in last.items() if isinstance(v, (int, float, np.number))},
        "regional_rows": int(len(df_reg)),
    }
