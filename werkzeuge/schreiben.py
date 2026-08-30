#!/usr/bin/env python3
"""Laesst das lokale Modell aus den gesammelten Meldungen den Tagesstand
schreiben: je Meldung eine deutsche Zeile, dazu eine kurze Lage.

Bewusste Arbeitsteilung, und sie steht so auch auf der Seite:

  Das kleine Modell  uebersetzt, fasst zusammen, ordnet ein Cluster zu.
                     Das kann es, und es kostet nichts.
  Der Analyseteil    - was eine Meldung fuer Nvidia, DRAM und NAND bedeutet -
                     wird nicht hier erzeugt. Lieferketteneffekte herzuleiten
                     ist genau das, wobei ein kleines Modell plausibel falsch
                     liegt. Dieser Teil kommt aus einem eigenen Lauf und traegt
                     auf der Seite ein anderes Autorenkuerzel.

Faellt das Modell aus, bleibt der Feed trotzdem stehen: dann zeigt die Seite
die Originalschlagzeilen. Das ist derselbe Gedanke wie bei wetter.

Rueckgabewerte:
  0  geschrieben
  2  lokales Modell nicht erreichbar - Feed bleibt ohne deutsche Zeilen
  1  nachrichten.json fehlt

Aufruf:  python werkzeuge/schreiben.py [--max 40]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "nachrichten.json"
THEMEN = WURZEL / "themen.json"
ARTIKEL = WURZEL / "artikel"
LOG = WURZEL / "lauf.log"

LOK = Path(r"C:\Users\Mendel\Projects\lok\lok.cmd")
LOK_PY = Path(r"C:\Users\Mendel\Projects\local_models\tools\lok.py")


def log(msg):
    zeile = "%s  schreiben  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(zeile)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass


def lok_befehl():
    if LOK.exists():
        return [str(LOK)]
    if LOK_PY.exists():
        return [sys.executable, str(LOK_PY)]
    return None


def lok(aufgabe, text, zusatz=None, zeitlimit=180):
    """Ruft das lokale Modell. Gibt (text, code) zurueck.

    Code 2 heisst eskaliert und ist kein Fehler - dann steht die Aufgabe dem
    grossen Modell zu und wir lassen das Feld hier einfach leer."""
    b = lok_befehl()
    if b is None:
        return None, 3
    args = b + [aufgabe, "-q"]
    if zusatz:
        args += ["-c", zusatz]
    try:
        p = subprocess.run(args, input=text, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=zeitlimit)
    except subprocess.TimeoutExpired:
        return None, 4
    return (p.stdout or "").strip(), p.returncode


def erreichbar():
    b = lok_befehl()
    if b is None:
        return False
    try:
        p = subprocess.run(b + ["ping"], capture_output=True, text=True, timeout=30)
        return p.returncode == 0
    except Exception:
        return False


def deutsch(titel):
    """Englische Schlagzeile eindeutschen; deutsche bleiben, wie sie sind."""
    if not re.search(r"[a-z]", titel):
        return titel, 0
    deutsche_marker = re.search(
        r"\b(der|die|das|und|für|fuer|mit|von|bei|auf|nach|über|ueber|"
        r"Prozent|Milliarden|Millionen|steigen|senkt|baut)\b", titel)
    if deutsche_marker:
        return titel, 0
    aus, code = lok("de", titel)
    if code != 0 or not aus:
        return titel, code
    # Das Modell haengt gelegentlich eine Erklaerung an - nur die erste Zeile.
    return aus.splitlines()[0].strip().strip('"'), 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=40,
                   help="wie viele Meldungen eine deutsche Zeile bekommen")
    a = p.parse_args()

    if not QUELLE.exists():
        log("nachrichten.json fehlt - erst werkzeuge/sammeln.py laufen lassen")
        return 1

    N = json.loads(QUELLE.read_text(encoding="utf-8"))
    T = json.loads(THEMEN.read_text(encoding="utf-8"))
    namen = {e["id"]: e for e in T["beobachtet"]}

    if not erreichbar():
        log("lokales Modell nicht erreichbar - Feed bleibt ohne deutsche Zeilen")
        N["modell"] = {"stand": None, "hinweis": "Modell war beim Lauf aus"}
        QUELLE.write_text(json.dumps(N, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        return 2

    kandidaten = [m for m in N["meldungen"] if not m.get("rauschen")][:a.max]

    # Was schon einmal uebersetzt wurde, steht im Korpus. Das Zeitfenster ist
    # zwei Tage breit, die meisten Schlagzeilen kommen also mehrfach vor - ohne
    # dieses Nachschlagen uebersetzt der Lauf jeden Morgen dieselben Zeilen neu,
    # bei rund 40 Sekunden je Zeile.
    bekannt = {}
    korpus = WURZEL / "archiv" / "korpus.jsonl"
    if korpus.exists():
        with korpus.open(encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if not z:
                    continue
                try:
                    e = json.loads(z)
                except json.JSONDecodeError:
                    continue
                if e.get("zeile"):
                    bekannt[e.get("id")] = e["zeile"]

    offen = [m for m in kandidaten if m["id"] not in bekannt]
    log("%d Meldungen: %d aus dem Korpus, %d neu zu uebersetzen"
        % (len(kandidaten), len(kandidaten) - len(offen), len(offen)))

    eskaliert = 0
    for m in kandidaten:
        if m["id"] in bekannt:
            m["zeile"] = bekannt[m["id"]]
    for i, m in enumerate(offen, 1):
        zeile, code = deutsch(m["titel"])
        m["zeile"] = zeile
        if code == 2:
            eskaliert += 1
        if i % 10 == 0:
            log("%d/%d" % (i, len(offen)))

    # Tageslage aus den obersten Schlagzeilen. Bewusst knapp gehalten - ein
    # laengerer Prompt kostet bei diesem Modell vor allem Wartezeit.
    oben = kandidaten[:15]
    eingabe = "\n".join("- " + (m.get("zeile") or m["titel"]) for m in oben)
    lage, code = lok("tldr", eingabe, zeitlimit=300)
    if code != 0 or not lage:
        lage = None
        log("Tageslage eskaliert oder leer (Code %d)" % code)

    # Straenge: worueber heute mehrfach NEU berichtet wurde.
    #
    # Zwei Zuschnitte waren hier falsch. Erst wurden sie nur aus den 40
    # uebersetzten Meldungen gebildet - das ist eine willkuerliche Stichprobe.
    # Ueber alle Meldungen gerechnet ist die Schwelle "mehr als eine" dagegen
    # bedeutungslos: bei 3000 Meldungen im Fenster hat jedes Thema mehr als
    # eine. Was den Tag beschreibt, sind die neu hinzugekommenen Meldungen.
    neue = [m for m in N["meldungen"] if m.get("neu") and not m.get("rauschen")]
    straenge = {}
    for m in neue:
        for h in m.get("hashtags", []):
            straenge.setdefault(h, []).append(m["id"])
    # Schwelle zwei, nicht drei: gemessen wird ueber die neuen Meldungen, und
    # an ruhigen Tagen sind das wenige Dutzend. Bei drei bliebe das Brett dann
    # leer, obwohl sich sehr wohl etwas bewegt hat.
    straenge = {h: v for h, v in sorted(straenge.items(),
                                        key=lambda kv: -len(kv[1]))[:14]
                if len(v) >= 2}

    heute = N.get("tag") or datetime.now().strftime("%Y-%m-%d")
    N["modell"] = {
        "stand": datetime.now().isoformat(timespec="seconds"),
        "name": "Qwen3.6-35B-A3B lokal",
        "eingedeutscht": len(kandidaten),
        "eskaliert": eskaliert,
    }
    N["lage"] = lage
    N["straenge"] = straenge
    QUELLE.write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")

    ARTIKEL.mkdir(exist_ok=True)
    (ARTIKEL / ("%s.json" % heute)).write_text(
        json.dumps({"tag": heute, "lage": lage, "straenge": straenge,
                    "modell": N["modell"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    log("fertig: %d Zeilen, %d eskaliert, %d Straenge"
        % (len(kandidaten), eskaliert, len(straenge)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
