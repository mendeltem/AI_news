#!/usr/bin/env python3
"""Pflegt die auf sortieren.html gefaellten Urteile in korrekturen.json ein.

Warum ueber eine Datei und nicht direkt: sortieren.html liegt auf GitHub Pages
und ist statisch. Eine Seite dort kann nicht ins Repo zurueckschreiben, und ein
Zugangstoken im Quelltext waere die falsche Loesung fuer das richtige Problem.
Also: im Browser urteilen, herunterladen, hier einpflegen.

Zwei Achsen, beide beantworten eine feste Frage:

  Richtung      Erleichtert die Meldung den Ausbau von KI-Rechenzentren
                oder erschwert sie ihn?
  Wichtigkeit   Wuerdest du das jemandem weitererzaehlen, der die Kette
                verfolgt?

Nur die Richtung wirkt auf die Anzeige zurueck - sie landet in korrekturen.json
und ueberschreibt ab dem naechsten Lauf das automatische Etikett. Die
Wichtigkeit wird gesammelt, aber nicht angewandt: dafuer bräuchte es erst genug
Urteile, um zu pruefen, ob sich daraus eine Regel ableiten laesst.

Der Ertrag steht in den Abweichungen. Wo Mensch und Automatik dasselbe sagen,
lernt man nichts. Deshalb zaehlt und listet dieser Lauf sie eigens auf.

Rueckgabewerte:
  0  eingepflegt
  1  Datei fehlt oder ist unlesbar

Aufruf:  python werkzeuge/einpflegen.py urteile-2026-09-01.json [--trocken]
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
KORREKTUREN = WURZEL / "korrekturen.json"
URTEILE = WURZEL / "urteile.json"
LOG = WURZEL / "lauf.log"


def log(msg):
    zeile = "%s  einpflegen  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(zeile)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("datei", help="die auf sortieren.html heruntergeladene Datei")
    p.add_argument("--trocken", action="store_true",
                   help="nur zeigen, was passieren wuerde")
    a = p.parse_args()

    pfad = Path(a.datei)
    if not pfad.exists():
        log("Datei nicht gefunden: %s" % pfad)
        return 1
    try:
        D = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("Datei unlesbar: %s" % e)
        return 1

    neu = D.get("urteile") or {}
    if not neu:
        log("keine Urteile in der Datei")
        return 1

    korr = {}
    if KORREKTUREN.exists():
        try:
            korr = json.loads(KORREKTUREN.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("korrekturen.json unlesbar - wird neu aufgebaut")
    # Die Erklaerzeilen bleiben stehen, sie fangen mit _ an.
    behalten = {k: v for k, v in korr.items() if k.startswith("_")}

    alle = {k: v for k, v in korr.items() if not k.startswith("_")}
    zaehler = Counter()
    abweichungen = []

    for mid, u in neu.items():
        richtung = u.get("urteil")
        if richtung and richtung != "unbestimmt":
            vorher = alle.get(mid, {}).get("richtung")
            alle[mid] = {
                "richtung": richtung,
                "grund": "von Hand sortiert am %s" % (u.get("zeit") or "")[:10],
                "titel": u.get("titel"),
            }
            zaehler["geaendert" if vorher and vorher != richtung else "gesetzt"] += 1

        # Abweichungen sammeln - das ist der Lernstoff.
        for feld, achse in (("urteil", "Richtung"), ("wichtig", "Wichtigkeit")):
            mensch, auto = u.get(feld), u.get(feld + "_automatik")
            if mensch and auto and auto != "unbestimmt" and mensch != auto:
                abweichungen.append((achse, mensch, auto, u.get("titel") or mid))
                zaehler["abweichung"] += 1

    zaehler["wichtigkeit"] = sum(1 for u in neu.values() if u.get("wichtig"))

    print("\nEingelesen: %d Urteile" % len(neu))
    print("  Richtung gesetzt:    %d" % zaehler["gesetzt"])
    print("  Richtung geaendert:  %d" % zaehler["geaendert"])
    print("  Wichtigkeit erfasst: %d  (wird noch nicht angewandt)"
          % zaehler["wichtigkeit"])
    print("  Abweichungen:        %d" % zaehler["abweichung"])

    if abweichungen:
        print("\nWo du und die Automatik auseinandergehen:")
        for achse, mensch, auto, titel in abweichungen[:20]:
            print("  [%s] du %s / Automatik %s" % (achse, mensch, auto))
            print("      %s" % str(titel)[:84])
        if len(abweichungen) > 20:
            print("  ... und %d weitere" % (len(abweichungen) - 20))

    if a.trocken:
        print("\nTrockenlauf - nichts geschrieben.")
        return 0

    behalten.update(alle)
    KORREKTUREN.write_text(json.dumps(behalten, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    # Die vollstaendigen Urteile beider Achsen getrennt aufheben - sie sind der
    # Datensatz, korrekturen.json ist nur der wirksame Teil davon.
    bestand = {}
    if URTEILE.exists():
        try:
            bestand = json.loads(URTEILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    bestand.update(neu)
    URTEILE.write_text(json.dumps(bestand, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    log("korrekturen.json: %d Eintraege, urteile.json: %d Eintraege"
        % (len(alle), len(bestand)))
    print("\nGeschrieben. Der naechste Lauf wendet die Richtungen an:")
    print("  python werkzeuge/bewerten.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
