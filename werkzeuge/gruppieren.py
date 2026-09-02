#!/usr/bin/env python3
"""Fasst Meldungen, die dieselbe Geschichte erzaehlen, zu einer zusammen.

Das bisherige Entdoppeln verglich normalisierte Titel und traf damit nur
woertliche Wiederholungen. Ueber Redaktions- und Sprachgrenzen hinweg versagt
das vollstaendig. Beispiel vom 02.09.2026 - achtmal dieselbe Nachricht:

  [News] SK hynix Reportedly Weighs Intel for HBM4E Base Dies amid TSMC ...
  Intel statt TSMC?: SK Hynix will angeblich Intel fuer HBM-Base-Dies nutzen
  SK Hynix Weighs Intel Foundry for HBM4E Base Die, Reducing TSMC Dependence
  SK Hynix Reportedly Taps Intel Foundry for HBM Base Dies, Threatening ...
  SK Hynix prueft Intel als Partner fuer HBM4E-Basis-Chips
  SK Hynix explores Intel as second source for HBM base dies
  ...

Kein Wort davon ist identisch. Gemeinsam sind die Eigennamen und Fachbegriffe:
hynix, intel, hbm4e, tsmc, foundry.

VERFAHREN

Nicht Jaccard ueber alle Woerter - das ergibt fuer das Beispiel oben 0,25 und
damit keine Gruppe. Sondern Ueberlappung der *seltenen* Woerter, gewichtet mit
ihrer Seltenheit und bezogen auf die kuerzere der beiden Schlagzeilen:

    aehnlichkeit = summe(idf der gemeinsamen) / min(summe(idf) je Titel)

Haeufige Woerter wie "news" oder "chip" tragen dadurch kaum bei, ein Wort wie
"hbm4e" sehr viel. Zusaetzlich muss mindestens ein beobachteter Eintrag geteilt
sein - sonst gruppiert es Meldungen, die zufaellig Fachvokabular teilen.

Verglichen wird nur, was mindestens zwei seltene Woerter teilt; dafuer gibt es
einen Wortindex. Ohne den waeren es bei 6000 Meldungen 18 Millionen Vergleiche.

ERGEBNIS

Jede Meldung bekommt:
    geschichte    Kennung ihrer Gruppe
    vertreter     true bei genau einer je Gruppe
    weitere       Zahl der uebrigen Meldungen der Gruppe (nur beim Vertreter)

Geloescht wird nichts. Die Seite zeigt den Vertreter und blendet die uebrigen
auf Klick ein - wer wissen will, wer sonst noch berichtet hat, kommt heran.

Vertreter wird, was am meisten hergibt: gute Quelle vor schwacher, kein
Rauschen vor Rauschen, hohes Gewicht vor niedrigem, deutsche Zeile vorhanden.

Rueckgabewerte:
  0  gruppiert
  1  nachrichten.json fehlt

Aufruf:  python werkzeuge/gruppieren.py [--schwelle 0.45] [--zeige]
"""

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "nachrichten.json"
LOG = WURZEL / "lauf.log"

SCHWELLE = 0.38
MINDEST_GETEILT = 2      # so viele seltene Woerter muessen sich ueberhaupt treffen

STOPP = set("""der die das den dem des ein eine einen einem und oder von mit fuer
für the a an of to in on for and is are as at by with from that this it its be
will has have new more than what why how who when where sich auf nach bei aus im
am um zu zur zum ist sind wird werden nicht auch noch nur schon vs said says
laut ueber über news bericht report reports angeblich reportedly could would may
about into over amid its it's soll will sein seine ihre ihren""".split())

UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                        "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def log(msg):
    z = "%s  gruppieren  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(z)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass


def worte(titel, quelle=None):
    t = titel or ""
    if quelle:
        t = re.sub(r"\s*[-–|]\s*" + re.escape(quelle) + r"\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+[-–]\s+[A-Z][\w.'& ]{2,28}$", "", t)
    t = t.translate(UMLAUT).lower()
    # Bindestriche trennen: "hbm4e-basisdies" -> "hbm4e", "basisdies"
    t = re.sub(r"[^0-9a-z]+", " ", t)
    return {w for w in t.split() if len(w) >= 3 and w not in STOPP}


#  Warum kein Union-Find:
#
#  Der erste Anlauf verband alles, was paarweise aehnlich war, und schloss
#  transitiv ab. Ergebnis waren 123 Meldungen in einer Gruppe mit mindestens
#  fuenf verschiedenen Geschichten darin - NVHBM, ein Cloud-Vertrag von
#  Anthropic, eine MediaTek-Beteiligung, ein Grossauftrag aus Indien. Sie
#  hingen ueber Zwischenglieder aneinander: A gleicht B, B gleicht C, also
#  landen A und C zusammen, obwohl sie nichts gemeinsam haben.
#
#  Stattdessen Leader-Clustering: die gewichtigste noch freie Meldung wird
#  Vertreter, und aufgenommen wird nur, wer *ihr selbst* aehnlich genug ist.
#  Keine Ketten, dafuer gelegentlich zwei Gruppen fuer eine Geschichte - der
#  harmlosere der beiden Fehler.


def guete(m):
    """Wie gut taugt diese Meldung als Vertreter ihrer Gruppe?"""
    return (0 if m.get("rauschen") else 1,
            1 if m.get("zeile") else 0,
            m.get("gewicht") or 0,
            -len(m.get("titel") or ""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--schwelle", type=float, default=SCHWELLE)
    p.add_argument("--zeige", action="store_true",
                   help="die groessten Gruppen auflisten")
    a = p.parse_args()

    if not QUELLE.exists():
        log("nachrichten.json fehlt")
        return 1
    N = json.loads(QUELLE.read_text(encoding="utf-8"))
    M = N.get("meldungen", [])
    if not M:
        log("keine Meldungen")
        return 0

    # Wortmengen und Seltenheit
    mengen = [worte(m["titel"], m.get("quelle")) for m in M]
    haeufig = Counter()
    for s in mengen:
        haeufig.update(s)
    n = len(M)
    idf = {w: math.log(n / (1 + c)) for w, c in haeufig.items()}
    gewichtssumme = [sum(idf.get(w, 0) for w in s) or 1e-9 for s in mengen]

    # Wortindex: nur seltene Woerter, sonst wird jede Meldung mit jeder verglichen
    index = defaultdict(list)
    for i, s in enumerate(mengen):
        for w in s:
            if haeufig[w] <= max(3, n // 40):
                index[w].append(i)

    bezuege = [set(m.get("bezug") or []) for m in M]
    selten = lambda w: haeufig[w] <= max(3, n // 40)   # noqa: E731

    def aehnlichkeit(i, j):
        if not (bezuege[i] & bezuege[j]):
            return 0.0
        gemeinsam = sum(idf.get(w, 0) for w in mengen[i] & mengen[j])
        return gemeinsam / min(gewichtssumme[i], gewichtssumme[j])

    # Der gewichtigste Kandidat zuerst - er wird Vertreter seiner Gruppe.
    reihenfolge = sorted(range(n), key=lambda i: guete(M[i]), reverse=True)
    zugeteilt = [False] * n
    gruppen, paare = [], 0

    for i in reihenfolge:
        if zugeteilt[i]:
            continue
        zugeteilt[i] = True
        gruppe = [i]
        kandidaten = Counter()
        for w in mengen[i]:
            if selten(w):
                for j in index[w]:
                    if not zugeteilt[j]:
                        kandidaten[j] += 1
        for j, geteilt in kandidaten.items():
            if geteilt < MINDEST_GETEILT or zugeteilt[j]:
                continue
            paare += 1
            if aehnlichkeit(i, j) >= a.schwelle:
                zugeteilt[j] = True
                gruppe.append(j)
        gruppen.append(gruppe)

    for glieder in gruppen:
        bester = glieder[0]          # der Anfuehrer, nach guete ausgewaehlt
        kennung = M[bester]["id"]
        for i in glieder:
            M[i]["geschichte"] = kennung
            M[i]["vertreter"] = (i == bester)
            M[i].pop("weitere", None)
        M[bester]["weitere"] = len(glieder) - 1

    mehrfach = [g for g in gruppen if len(g) > 1]
    zusammengefasst = sum(len(g) - 1 for g in mehrfach)
    N["gruppen"] = {
        "verfahren": "idf-gewichtete Ueberlappung seltener Woerter, "
                     "mindestens ein geteilter beobachteter Eintrag",
        "schwelle": a.schwelle,
        "gruppen": len(gruppen),
        "mehrfach_besetzt": len(mehrfach),
        "zusammengefasst": zusammengefasst,
    }
    QUELLE.write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")
    log("%d Meldungen -> %d Geschichten, %d Wiederholungen zusammengefasst "
        "(%d Paare geprueft)" % (n, len(gruppen), zusammengefasst, paare))

    if a.zeige:
        mehrfach.sort(key=len, reverse=True)
        for g in mehrfach[:8]:
            bester = g[0]
            print("\n--- %d Meldungen ---" % len(g))
            for i in g:
                print("  %s %-18s %s" % ("*" if i == bester else " ",
                                         (M[i].get("quelle") or "?")[:18],
                                         M[i]["titel"][:76]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
