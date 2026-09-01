#!/usr/bin/env python3
"""Selbsttest fuer die Zuordnung von Meldungen zu beobachteten Eintraegen.

Der Anlass: Die Stichwortpruefung war zweimal hintereinander falsch, und beide
Male sah das Ergebnis auf den ersten Blick richtig aus - der Feed war voll,
die Hashtags standen dran, nur bezogen sie sich auf nichts. Aufgefallen ist es
erst beim Nachzaehlen. Deshalb steht hier jetzt ein Testfall je Fehler, den es
schon gab.

Der Kern des Problems, damit er nicht wiederkommt: Der Suchbegriff sagt, wonach
gesucht wird. Er sagt nicht, wovon die gefundene Meldung handelt. Aus
"TSMC advanced packaging capacity" darf kein Beleg fuer CoWoS werden.

Aufruf:  python werkzeuge/pruefen.py
Rueckgabewerte:  0 alles bestanden, 1 mindestens ein Fall gescheitert
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sammeln import treffer, schluessel, RAUSCHMUSTER, SCHWACHE_QUELLEN  # noqa: E402
from bewerten import bewerte  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent

# (Eintrag, Schlagzeile, soll zugeordnet werden)
FAELLE = [
    # --- der Fehler vom 30.08.2026: erstes Wort des Suchbegriffs als Beleg ---
    ("COWOS", "M6-Chip: Apple startet TSMC-Validierung mit 2-Nanometer-Prozess", False),
    ("COWOS", "What Is Amkor Technology (AMKR) Telling Investors About Advanced "
              "Chip Packaging?", False),
    ("COWOS", "Inside TSMC's 238-page sustainability report", False),
    ("EXPORTKONTROLLE", "AI Orders Surge: TSMC Commands 73% Q2 Market Share", False),
    ("RECHENZENTRUM_STROM", "TSMC will invest an additional $100 billion into "
                            "Arizona operations", False),

    # --- was sehr wohl zugeordnet gehoert ---
    ("COWOS", "TSMC raises CoWoS capacity targets for 2026-2027", True),
    ("COWOS", "TSMC pushes CoPoS panel level packaging exclusivity", True),
    ("COWOS", "Rubin combines CoWoS-L with SoIC stacking", True),
    ("COWOS", "ASE ramps advanced packaging capacity", True),
    ("EXPORTKONTROLLE", "Trump Chip Tariff Phase 2 Targets Servers", True),
    ("EXPORTKONTROLLE", "US adds chipmaker to Entity List", True),
    ("RECHENZENTRUM_STROM", "PJM sees 30 GW of new data center power demand", True),
    ("HBM", "SK hynix breaks ground on first HBM plant in the US", True),
    ("HBM", "Nvidia kuendigt NVHBM an", True),
    ("NAND", "Kioxia and SanDisk plan $31 billion for Japan NAND fabs", True),
    ("DRAM", "DDR4-Preise steigen um ueber 50 Prozent", True),
    ("NVDA", "Nvidia baut eigenen KI-Speicher", True),
    ("NVIDIA_ARCHITEKTUR", "Vera Rubin NVL72 enters volume production", True),

    # --- Ticker, die auch normale Woerter sind, duerfen nicht anschlagen ---
    ("ON", "Samsung turns on new fab", False),
    ("NOW", "AI chips are in demand now", False),
    ("ARM", "Robot arm assembles servers", False),
]

# (Schlagzeile, erwartete Richtung) - Standpunkt: erleichtert oder erschwert
# die Meldung den Ausbau von KI-Rechenzentren?
WIND_FAELLE = [
    # eindeutig, in beide Richtungen
    ("Micron-Angestellte in Taiwan stimmen fuer Streik", "gegenwind"),
    ("TSMC CoWoS capacity fully booked, lead times 78 weeks", "gegenwind"),
    ("US adds chipmaker to Entity List", "gegenwind"),
    ("SK hynix breaks ground on first HBM plant in the US", "rueckenwind"),
    ("Kioxia und SanDisk investieren 31 Milliarden in NAND-Fabriken", "rueckenwind"),
    ("Powertech startet Serienproduktion", "rueckenwind"),

    # --- Kollisionen, die es schon gab ---
    # invest\w* verschluckte "investigation"
    ("Nvidia supplier Unimicron under investigation over relabeling", "gegenwind"),
    # "brand" ist deutsch Feuer, englisch Marke
    ("VMware nutzt die von Nvidia bevorzugte AI Factory brand", "unbestimmt"),
    # accelerat\w* traf das Substantiv
    ("Solving the CoWoS Bottleneck for Next-Gen AI Accelerators", "gegenwind"),
    # ein Dementi ist kein Ereignis
    ("SK Hynix dementiert Intel-Foundry-Deal fuer HBM4E-Chips", "unbestimmt"),
    ("Nvidia denies plans for new fab", "unbestimmt"),
]

RAUSCH_FAELLE = [
    ("Nvidia Aktie News: Nvidia tendiert am Mittag schwaecher", True),
    ("Which Semiconductor Giant Is the Better Stock Buy?", True),
    ("ARK Invest schichtet um: Cathie Wood trennt sich von AMD", True),
    ("SK hynix breaks ground on first HBM plant in the US", False),
    ("Kioxia and SanDisk Plan Over $31 Billion for Japan NAND Fabs", False),
    ("Tiefstpreis geortet: Apple AirTag im 4er-Pack nie guenstiger", True),
]


def main():
    pfad = WURZEL / "themen.json"
    if not pfad.exists():
        print("themen.json fehlt - erst werkzeuge/saat.py laufen lassen")
        return 1
    E = {e["id"]: e for e in json.loads(pfad.read_text(encoding="utf-8"))["beobachtet"]}

    fehler = 0

    print("Zuordnung:")
    for tid, titel, soll in FAELLE:
        if tid not in E:
            print("  UEBERSPRUNGEN  %s steht nicht in themen.json" % tid)
            continue
        ist = treffer(titel, E[tid])
        if ist != soll:
            fehler += 1
            print("  FEHLGESCHLAGEN %-20s soll=%-5s ist=%-5s  %s"
                  % (tid, soll, ist, titel[:56]))

    print("Rauschfilter:")
    for titel, soll in RAUSCH_FAELLE:
        ist = bool(RAUSCHMUSTER.search(titel))
        if ist != soll:
            fehler += 1
            print("  FEHLGESCHLAGEN soll=%-5s ist=%-5s  %s" % (soll, ist, titel[:56]))

    print("Richtung:")
    for titel, soll in WIND_FAELLE:
        ist, _ = bewerte(titel)
        if ist != soll:
            fehler += 1
            print("  FEHLGESCHLAGEN soll=%-12s ist=%-12s  %s"
                  % (soll, ist, titel[:52]))

    print("Entdoppeln:")
    # Dieselbe Meldung bei zwei Haeusern muss denselben Schluessel ergeben.
    a = schluessel("SK hynix breaks ground on the first HBM plant in the US")
    b = schluessel("SK hynix breaks ground on first HBM plant in US")
    if a != b:
        fehler += 1
        print("  FEHLGESCHLAGEN Varianten derselben Meldung ergeben "
              "verschiedene Schluessel")
    c = schluessel("Micron workers vote to strike in Taiwan")
    if a == c:
        fehler += 1
        print("  FEHLGESCHLAGEN verschiedene Meldungen ergeben denselben Schluessel")

    gesamt = len(FAELLE) + len(RAUSCH_FAELLE) + len(WIND_FAELLE) + 2
    if fehler:
        print("\n%d von %d Faellen gescheitert" % (fehler, gesamt))
        return 1
    print("\nalle %d Faelle bestanden" % gesamt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
