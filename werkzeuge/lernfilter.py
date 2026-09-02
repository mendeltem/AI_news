#!/usr/bin/env python3
"""Lernt aus den von Hand sortierten Urteilen, was wichtig ist - und sagt
ehrlich, ob er dafuer schon gut genug ist.

Verfahren: Naive Bayes ueber Titelwoerter, Quelle und ein paar Zaehlmerkmale.
Kein Fremdpaket noetig, und vor allem: jede Entscheidung laesst sich in ihre
Bestandteile zerlegen. Das ist hier keine Bescheidenheit, sondern Bedingung -
ein Filter, der nicht sagen kann, warum er etwas wegwirft, ist nicht
korrigierbar.

DIE WICHTIGSTE ZAHL IST NICHT DIE TREFFERQUOTE

Ein Modell, das auf seinen eigenen Trainingsdaten geprueft wird, hat immer
recht. Deshalb misst dieser Lauf mit Kreuzvalidierung: das Modell sieht beim
Pruefen nur Beispiele, die es nicht kannte. Und es vergleicht sich gegen zwei
Messlatten:

  Mehrheitsrater   sagt immer die haeufigere Klasse. Wer die nicht schlaegt,
                   hat nichts gelernt.
  Regelfilter      die handgeschriebenen Muster aus sammeln.py.

Liegt das Modell nicht ueber beiden, sagt der Lauf das - und empfiehlt, es
nicht einzusetzen. Ein Filter, der falsch aussortiert, kostet mehr als einer,
den es nicht gibt.

ENTHALTUNG STATT RATEN

Angewandt wird nur oberhalb einer Sicherheitsschwelle. Was darunter liegt,
bleibt unbewertet und wandert in den Sortierstapel - genau die Faelle, deren
Beurteilung dem Modell am meisten beibringt.

Aufrufe:
  python werkzeuge/lernfilter.py pruefen     Kreuzvalidierung, nichts wird geschrieben
  python werkzeuge/lernfilter.py trainieren  modell.json aus allen Urteilen
  python werkzeuge/lernfilter.py anwenden    nachrichten.json bewerten
  python werkzeuge/lernfilter.py erklaeren "Schlagzeile"

Rueckgabewerte:
  0  fertig
  1  zu wenige Urteile oder Datei fehlt
  2  geprueft, aber nicht besser als die Messlatten - nicht einsetzen
"""

import argparse
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
URTEILE = WURZEL / "urteile.json"
KORPUS = WURZEL / "archiv" / "korpus.jsonl"
NACHRICHTEN = WURZEL / "nachrichten.json"
MODELL = WURZEL / "modell.json"
LOG = WURZEL / "lauf.log"

MINDEST_JE_KLASSE = 25    # darunter wird gar nicht erst trainiert
SCHWELLE = 0.80           # ab welcher Sicherheit ueberhaupt entschieden wird
FALTEN = 5

STOPP = set("""der die das den dem des ein eine einen einem und oder von mit
fuer für the a an of to in on for and is are as at by with from that this it
its be will has have new more than what why how who when where sich auf nach
bei aus im am um zu zur zum ist sind wird werden nicht auch noch nur schon
vs said says laut ueber über nach""".split())


def log(msg):
    z = "%s  lernfilter  %s" % (__import__("datetime").datetime.now()
                                .strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(z)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(z + "\n")
    except Exception:
        pass


def merkmale(titel, quelle=None, gewicht=None, bezug=None):
    """Alles, woran das Modell eine Meldung erkennen darf.

    Der Quellenname wird aus dem Titel geschnitten und als eigenes Merkmal
    gefuehrt - sonst lernt das Modell "hardware" als Sachwort, obwohl es nur
    'Tom's Hardware' hiess."""
    t = titel or ""
    if quelle:
        t = re.sub(r"\s*[-–|]\s*" + re.escape(quelle) + r"\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+[-–]\s+[A-Z][\w.'& ]{2,28}$", "", t)
    worte = re.sub(r"[^0-9A-Za-zÄÖÜäöüß\- ]+", " ", t.lower()).split()
    qw = set(re.sub(r"[^a-z ]+", " ", (quelle or "").lower()).split())

    m = ["w:" + w for w in worte if len(w) > 2 and w not in STOPP and w not in qw]
    if quelle:
        m.append("q:" + quelle.lower())
    n = len(bezug or [])
    m.append("bezuege:" + ("viele" if n >= 4 else "einige" if n >= 2 else "wenige"))
    g = gewicht or 0
    m.append("gewicht:" + ("hoch" if g >= 8 else "mittel" if g >= 4 else "niedrig"))
    m.append("laenge:" + ("lang" if len(worte) > 14 else "kurz"))
    return m


def lade_beispiele():
    """(Merkmale, Klasse, Titel) je Urteil, angereichert aus dem Korpus."""
    if not URTEILE.exists():
        return []
    U = json.loads(URTEILE.read_text(encoding="utf-8"))
    K = {}
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
                K[e.get("id")] = e
    raus = []
    for mid, u in U.items():
        k = u.get("wichtig")
        if k not in ("wichtig", "unwichtig"):
            continue
        e = K.get(mid) or {}
        titel = u.get("titel") or e.get("titel") or ""
        raus.append((merkmale(titel, e.get("quelle"), e.get("gewicht"),
                              e.get("bezug")), k, titel))
    return raus


class Bayes:
    """Naive Bayes mit Laplace-Glaettung. Bewusst schlicht gehalten."""

    def __init__(self, alpha=0.4):
        self.alpha = alpha
        self.zaehler = defaultdict(Counter)
        self.gesamt = Counter()
        self.dokumente = Counter()
        self.wortschatz = set()

    def lernen(self, beispiele):
        for m, k, _ in beispiele:
            self.dokumente[k] += 1
            for f in set(m):
                self.zaehler[k][f] += 1
                self.gesamt[k] += 1
                self.wortschatz.add(f)
        return self

    def punkte(self, m):
        """Log-Wahrscheinlichkeit je Klasse, plus Beitrag je Merkmal."""
        n = len(self.wortschatz) or 1
        docs = sum(self.dokumente.values()) or 1
        raus, beitrag = {}, defaultdict(dict)
        for k in self.dokumente:
            s = math.log(self.dokumente[k] / docs)
            for f in set(m):
                p = ((self.zaehler[k][f] + self.alpha)
                     / (self.gesamt[k] + self.alpha * n))
                s += math.log(p)
                beitrag[k][f] = math.log(p)
            raus[k] = s
        return raus, beitrag

    def vorhersage(self, m):
        p, beitrag = self.punkte(m)
        if not p:
            return None, 0.0, {}
        hoechst = max(p, key=p.get)
        # Log-Punkte in eine Wahrscheinlichkeit umrechnen
        mx = max(p.values())
        summe = sum(math.exp(v - mx) for v in p.values())
        sicher = math.exp(p[hoechst] - mx) / summe
        return hoechst, sicher, beitrag[hoechst]


def kreuzvalidierung(beispiele, falten=FALTEN, schwelle=SCHWELLE, saat=11):
    r = random.Random(saat)
    daten = list(beispiele)
    r.shuffle(daten)
    teile = [daten[i::falten] for i in range(falten)]
    treffer = entschieden = gesamt = 0
    matrix = Counter()
    for i in range(falten):
        test = teile[i]
        train = [x for j, t in enumerate(teile) if j != i for x in t]
        if not train or not test:
            continue
        b = Bayes().lernen(train)
        for m, k, _ in test:
            gesamt += 1
            vor, sicher, _ = b.vorhersage(m)
            if vor is None or sicher < schwelle:
                continue
            entschieden += 1
            treffer += (vor == k)
            matrix[(k, vor)] += 1
    return treffer, entschieden, gesamt, matrix


def messlatten(beispiele):
    """Womit sich das Modell messen lassen muss."""
    klassen = Counter(k for _, k, _ in beispiele)
    mehrheit = klassen.most_common(1)[0]
    basis = mehrheit[1] / sum(klassen.values())

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sammeln import RAUSCHMUSTER, SPAM, MARKTGEPLAUDER  # noqa: E402
    def regel(t):
        return (bool(RAUSCHMUSTER.search(t)) or bool(MARKTGEPLAUDER.search(t))
                or any(p.search(t) for p in SPAM))
    richtig = sum(1 for _, k, t in beispiele
                  if (regel(t) and k == "unwichtig") or (not regel(t) and k == "wichtig"))
    return basis, mehrheit[0], richtig / len(beispiele)


def bericht(beispiele, schwelle=SCHWELLE):
    klassen = Counter(k for _, k, _ in beispiele)
    print("=" * 68)
    print("%d Urteile: %s" % (len(beispiele),
                              ", ".join("%s %d" % (k, n) for k, n in klassen.items())))
    zu_wenig = [k for k, n in klassen.items() if n < MINDEST_JE_KLASSE]
    if len(klassen) < 2 or zu_wenig:
        print("\nZu wenige Beispiele (mindestens %d je Klasse). Erst weiter "
              "sortieren." % MINDEST_JE_KLASSE)
        return 1

    treffer, entschieden, gesamt, matrix = kreuzvalidierung(beispiele, schwelle=schwelle)
    basis, mklasse, regelquote = messlatten(beispiele)
    genau = treffer / entschieden if entschieden else 0
    deckung = entschieden / gesamt if gesamt else 0

    print("\nKreuzvalidierung ueber %d Falten, Schwelle %.0f%%:" % (FALTEN, schwelle*100))
    print("  entscheidet bei   %d von %d  (%.0f%% Deckung)" % (entschieden, gesamt, deckung*100))
    print("  davon richtig     %d  (%.0f%% Genauigkeit)" % (treffer, genau*100))
    if matrix:
        print("\n  %-14s%12s%12s" % ("echt \\ Modell", "unwichtig", "wichtig"))
        for k in ("unwichtig", "wichtig"):
            print("  %-14s%12d%12d" % (k, matrix[(k, "unwichtig")], matrix[(k, "wichtig")]))

    print("\nMesslatten:")
    print("  immer \"%s\" raten      %.0f%%" % (mklasse, basis*100))
    print("  handgeschriebene Regeln  %.0f%%" % (regelquote*100))
    print("  dieses Modell            %.0f%%  (auf %.0f%% der Faelle)"
          % (genau*100, deckung*100))

    if genau <= max(basis, regelquote) + 0.02:
        print("\nURTEIL: nicht besser als die Messlatten. Nicht einsetzen.")
        print("Ein Filter, der falsch aussortiert, kostet mehr als keiner.")
        return 2
    if deckung < 0.25:
        print("\nURTEIL: genau genug, aber es entscheidet nur bei %.0f%% der "
              "Faelle. Als Vorsortierung brauchbar, nicht als Filter." % (deckung*100))
        return 0
    print("\nURTEIL: besser als beide Messlatten. Einsatz vertretbar - weiter "
          "sortieren macht es besser.")
    return 0


def lernkurve(beispiele, saaten=6):
    """Bringt mehr Sortieren ueberhaupt noch etwas?

    Eine flache Kurve heisst: nicht die Menge der Urteile ist der Engpass,
    sondern das, woran das Modell eine Meldung erkennen darf. Dann hilft kein
    weiteres Sortieren derselben Art, sondern anderes Material - und das sind
    die Faelle, bei denen das Modell unsicher ist."""
    print("\nLernkurve - hilft mehr Sortieren?")
    print("  %-12s %-13s %s" % ("Beispiele", "Genauigkeit", "Deckung"))
    werte = []
    for n in (40, 60, 80, len(beispiele)):
        if n > len(beispiele):
            continue
        proben = []
        for saat in range(saaten):
            r = random.Random(saat)
            d = list(beispiele)
            r.shuffle(d)
            t, e, g, _ = kreuzvalidierung(d[:n], saat=saat)
            if e:
                proben.append((t / e, e / g))
        if proben:
            a = sum(x for x, _ in proben) / len(proben)
            c = sum(y for _, y in proben) / len(proben)
            werte.append(a)
            print("  %-12d %-13s %s" % (n, "%.0f%%" % (a * 100), "%.0f%%" % (c * 100)))
    if len(werte) >= 2 and werte[-1] - werte[0] < 0.03:
        print("\n  Die Kurve ist flach. Mehr Urteile derselben Art bringen "
              "nichts -")
        print("  sortiere stattdessen, wo das Modell unsicher ist:")
        print("    python werkzeuge/lernfilter.py anwenden")
        print("    dann auf sortieren.html die Auswahl 'wo das Modell unsicher ist'")


def erklaeren(b, titel, oben=8):
    m = merkmale(titel)
    vor, sicher, beitrag = b.vorhersage(m)
    print("\n%s" % titel[:88])
    print("  -> %s  (Sicherheit %.0f%%)" % (vor, sicher*100))
    gegen = [k for k in b.dokumente if k != vor]
    if not gegen:
        return
    g = gegen[0]
    _, alle = b.punkte(m)
    diff = sorted(((alle[vor][f] - alle[g][f], f) for f in set(m)), reverse=True)
    print("  spricht dafuer:")
    for d, f in diff[:oben]:
        if d <= 0:
            break
        print("    %-28s %+.2f" % (f, d))
    print("  spricht dagegen:")
    for d, f in diff[-oben:]:
        if d >= 0:
            continue
        print("    %-28s %+.2f" % (f, d))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("befehl", choices=["pruefen", "trainieren", "anwenden", "erklaeren"])
    p.add_argument("text", nargs="?")
    p.add_argument("--schwelle", type=float, default=SCHWELLE)
    p.add_argument("--kurve", action="store_true",
                   help="zeigt, ob mehr Urteile ueberhaupt noch helfen")
    a = p.parse_args()

    beispiele = lade_beispiele()
    if not beispiele:
        print("Keine Urteile gefunden. Erst auf sortieren.html sortieren, "
              "herunterladen und mit werkzeuge/einpflegen.py einpflegen.")
        return 1

    if a.befehl == "pruefen":
        code = bericht(beispiele, a.schwelle)
        if a.kurve:
            lernkurve(beispiele)
        return code

    b = Bayes().lernen(beispiele)

    if a.befehl == "trainieren":
        MODELL.write_text(json.dumps({
            "stand": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "beispiele": len(beispiele),
            "klassen": dict(b.dokumente),
            "schwelle": a.schwelle,
            "zaehler": {k: dict(v) for k, v in b.zaehler.items()},
            "gesamt": dict(b.gesamt),
        }, ensure_ascii=False), encoding="utf-8")
        log("modell.json geschrieben, %d Beispiele" % len(beispiele))
        return 0

    if a.befehl == "erklaeren":
        if not a.text:
            print("Bitte eine Schlagzeile mitgeben.")
            return 1
        erklaeren(b, a.text)
        return 0

    # anwenden
    if not NACHRICHTEN.exists():
        print("nachrichten.json fehlt")
        return 1
    N = json.loads(NACHRICHTEN.read_text(encoding="utf-8"))
    z = Counter()
    for m in N["meldungen"]:
        vor, sicher, beitrag = b.vorhersage(
            merkmale(m["titel"], m.get("quelle"), m.get("gewicht"), m.get("bezug")))
        if vor is None or sicher < a.schwelle:
            m["relevanz"] = None
            z["enthalten"] += 1
            continue
        m["relevanz"] = vor
        m["relevanz_sicher"] = round(sicher, 3)
        m["relevanz_grund"] = [f for f, _ in
                               sorted(beitrag.items(), key=lambda kv: -kv[1])[:5]]
        z[vor] += 1
    N["lernfilter"] = {"beispiele": len(beispiele), "schwelle": a.schwelle,
                       "verteilung": dict(z)}
    NACHRICHTEN.write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")
    log("angewandt: %s" % dict(z))
    return 0


if __name__ == "__main__":
    sys.exit(main())
