#!/usr/bin/env python3
"""Liest die von Hand gefaellten Urteile und versucht die Regel dahinter zu finden.

Nicht: auflisten, was sortiert wurde. Sondern: herausarbeiten, woran sich die
Entscheidung festmachen laesst - und wo sie der Automatik widerspricht.

Vier Fragen werden beantwortet:

  1. Wie oft sind Mensch und Automatik einig?     Kreuztabelle je Achse
  2. Woran haengt das menschliche Urteil?         Quelle, Thema, Gewicht
  3. Welche Woerter ziehen in welche Richtung?    Log-Odds gegen den Rest
  4. Wo genau geht es auseinander?                die Faelle einzeln

Zu Punkt 3, damit die Zahlen nicht ueberlesen werden: bei wenigen Dutzend
Urteilen ist jede gefundene "Regel" eine Vermutung, kein Befund. Ein Wort, das
dreimal in "wichtig" auftaucht und nie sonst, kann Zufall sein. Der Lauf nennt
deshalb zu jedem Muster die Fallzahl und schweigt unter fuenf Urteilen je
Klasse ganz.

Rueckgabewerte:
  0  ausgewertet
  1  Datei fehlt oder enthaelt keine Urteile

Aufruf:  python werkzeuge/auswerten.py urteile-2026-09-01.json
         python werkzeuge/auswerten.py            (nimmt urteile.json)
"""

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
KORPUS = WURZEL / "archiv" / "korpus.jsonl"
NACHRICHTEN = WURZEL / "nachrichten.json"

MINDEST = 5          # unter so vielen Urteilen je Klasse wird nichts gedeutet
STOPP = set("""der die das den dem des ein eine einen einem und oder von mit
fuer für the a an of to in on for and is are as at by with from that this it
its be will has have new more than what why how who when where sich auf nach
bei aus im am um zu zur zum ist sind wird werden nicht auch noch nur schon
vs its s t re said says report reports laut ueber über""".split())


def lade_urteile(pfad):
    D = json.loads(Path(pfad).read_text(encoding="utf-8"))
    # Sowohl die Exportdatei (mit Umschlag) als auch urteile.json (flach).
    return D.get("urteile", D)


def lade_meldungen():
    """Volle Angaben je Meldung - erst aus dem Korpus, dann aus dem Tagesstand."""
    M = {}
    if KORPUS.exists():
        with KORPUS.open(encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if not z:
                    continue
                try:
                    e = json.loads(z)
                except json.JSONDecodeError:
                    continue
                M[e.get("id")] = e
    if NACHRICHTEN.exists():
        try:
            for m in json.loads(NACHRICHTEN.read_text(encoding="utf-8"))["meldungen"]:
                M.setdefault(m["id"], m)
        except Exception:
            pass
    return M


def kreuztabelle(paare, titel):
    """Mensch gegen Automatik."""
    if not paare:
        return
    zeilen = sorted({m for m, _ in paare})
    spalten = sorted({a for _, a in paare})
    zaehler = Counter(paare)
    breite = max(11, max(len(s) for s in spalten) + 2)
    print("\n%s  (%d Urteile)" % (titel, len(paare)))
    print("  %-14s" % "du \\ Automatik" + "".join("%*s" % (breite, s) for s in spalten))
    for z in zeilen:
        print("  %-14s" % z + "".join("%*d" % (breite, zaehler[(z, s)]) for s in spalten))
    einig = sum(n for (m, a), n in zaehler.items() if m == a)
    strittig = sum(n for (m, a), n in zaehler.items()
                   if m != a and a not in ("unbestimmt", "egal"))
    ohne = sum(n for (m, a), n in zaehler.items() if a in ("unbestimmt", "egal"))
    print("  einig %d, uneinig %d, Automatik hatte nichts %d" % (einig, strittig, ohne))


def verteilung(gruppen, schluessel, titel, mindest=2, oben=8):
    """Welcher Wert kommt in welcher Klasse wie oft vor."""
    tab = defaultdict(Counter)
    for klasse, meldungen in gruppen.items():
        for m in meldungen:
            for w in schluessel(m):
                tab[w][klasse] += 1
    interessant = [(w, c) for w, c in tab.items() if sum(c.values()) >= mindest]
    if not interessant:
        return
    interessant.sort(key=lambda wc: -sum(wc[1].values()))
    klassen = sorted(gruppen)
    print("\n%s" % titel)
    print("  %-34s" % "" + "".join("%12s" % k for k in klassen))
    for w, c in interessant[:oben]:
        print("  %-34s" % str(w)[:34] + "".join("%12d" % c[k] for k in klassen))


def worte(text, quelle=None):
    """Woerter des Titels ohne den angehaengten Quellennamen.

    Google News schreibt "... - Tom's Hardware" in den Titel. Ohne diesen
    Schnitt landen "tom", "hardware", "golem", "cnbc" in der Wortanalyse und
    sehen aus wie Begruendungen, obwohl sie nur sagen, wer es gedruckt hat."""
    t = text or ""
    if quelle:
        t = re.sub(r"\s*[-–|]\s*" + re.escape(quelle) + r"\s*$", "", t, flags=re.I)
    # Rest-Suffixe wie " - Reuters". Leerzeichen auf beiden Seiten sind Pflicht:
    # ohne sie frisst das Muster den Bindestrich in "KI-Gesichter" und alles
    # dahinter.
    t = re.sub(r"\s+[-–]\s+[A-Z][\w.'& ]{2,28}$", "", t)
    t = re.sub(r"[^0-9A-Za-zÄÖÜäöüß\- ]+", " ", t.lower())
    raus = []
    quellworte = set(worte_roh(quelle)) if quelle else set()
    for w in t.split():
        if len(w) > 2 and w not in STOPP and w not in quellworte:
            raus.append(w)
    return raus


def worte_roh(s):
    return re.sub(r"[^0-9A-Za-zÄÖÜäöüß ]+", " ", (s or "").lower()).split()


def log_odds(gruppen, oben=10):
    """Welche Woerter ziehen in welche Richtung - mit Gegenprobe auf Fallzahl."""
    klassen = [k for k, v in gruppen.items() if len(v) >= MINDEST]
    if len(klassen) < 2:
        print("\n  (zu wenige Urteile fuer eine Wortanalyse - mindestens %d je "
              "Klasse noetig)" % MINDEST)
        return
    zaehler = {k: Counter(w for m in gruppen[k]
                          for w in set(worte(m.get("titel", ""), m.get("quelle"))))
               for k in klassen}
    gesamt = {k: sum(zaehler[k].values()) or 1 for k in klassen}
    alle = set().union(*[set(z) for z in zaehler.values()])
    for k in klassen:
        andere = [x for x in klassen if x != k]
        werte = []
        for w in alle:
            n = zaehler[k][w]
            if n < 2:
                continue
            m = sum(zaehler[o][w] for o in andere)
            p1 = (n + .5) / (gesamt[k] + .5)
            p0 = (m + .5) / (sum(gesamt[o] for o in andere) + .5)
            werte.append((math.log(p1 / p0), w, n, m))
        werte.sort(reverse=True)
        if not werte:
            continue
        print("\n  typisch fuer %s:" % k)
        for s, w, n, m in werte[:oben]:
            print("    %-24s %dx hier, %dx sonst" % (w, n, m))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("datei", nargs="?", default=str(WURZEL / "urteile.json"))
    a = p.parse_args()

    pfad = Path(a.datei)
    if not pfad.exists():
        print("Datei nicht gefunden: %s" % pfad)
        print("\nAuf sortieren.html unten auf 'herunterladen' klicken, dann:")
        print("  python werkzeuge/auswerten.py <heruntergeladene-datei>")
        return 1

    U = lade_urteile(pfad)
    if not U:
        print("Keine Urteile in der Datei.")
        return 1
    M = lade_meldungen()

    fehlend = sum(1 for mid in U if mid not in M)
    print("=" * 72)
    print("%d Urteile, davon %d im Bestand wiedergefunden" % (len(U), len(U) - fehlend))
    if fehlend:
        print("(%d Meldungen sind aus dem Zeitfenster gefallen - fuer die gibt es "
              "nur Titel und Etikett)" % fehlend)

    for feld, name, autofeld in (("urteil", "RICHTUNG", "urteil_automatik"),
                                 ("wichtig", "WICHTIGKEIT", "wichtig_automatik")):
        beurteilt = {mid: u for mid, u in U.items() if u.get(feld)}
        if not beurteilt:
            continue
        print("\n" + "=" * 72)
        print("%s  -  %d Urteile" % (name, len(beurteilt)))
        print("=" * 72)

        kreuztabelle([(u[feld], u.get(autofeld) or "unbestimmt")
                      for u in beurteilt.values()],
                     "Kreuztabelle")

        gruppen = defaultdict(list)
        for mid, u in beurteilt.items():
            m = dict(M.get(mid) or {})
            m.setdefault("titel", u.get("titel"))
            gruppen[u[feld]].append(m)

        verteilung(gruppen, lambda m: [m.get("quelle") or "?"],
                   "Nach Quelle", mindest=2)
        verteilung(gruppen, lambda m: m.get("hashtags") or [],
                   "Nach Thema", mindest=2)
        verteilung(gruppen,
                   lambda m: ["Gewicht %s" % ("hoch (>=8)" if (m.get("gewicht") or 0) >= 8
                              else "mittel (4-7)" if (m.get("gewicht") or 0) >= 4
                              else "niedrig (<4)")],
                   "Nach Gewicht des Sammellaufs", mindest=1)
        if feld == "urteil":
            verteilung(gruppen,
                       lambda m: [g["grund"] for g in (m.get("wind_grund") or [])]
                                 or ["(kein Signalwort)"],
                       "Nach Signalwort der Automatik", mindest=1)

        print("\nWortgebrauch:")
        log_odds(gruppen)

        strittig = [(mid, u) for mid, u in beurteilt.items()
                    if u.get(autofeld) and u[autofeld] not in ("unbestimmt", "egal")
                    and u[feld] != u[autofeld]]
        if strittig:
            print("\nWo du der Automatik widersprichst (%d):" % len(strittig))
            for mid, u in strittig[:25]:
                m = M.get(mid) or {}
                gr = ", ".join(g["grund"] for g in (m.get("wind_grund") or []))
                print("  du %-11s / Automatik %-11s %s"
                      % (u[feld], u[autofeld], (u.get("titel") or "")[:60]))
                if gr:
                    print("      Automatik stuetzte sich auf: %s" % gr)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
