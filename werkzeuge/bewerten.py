#!/usr/bin/env python3
"""Ordnet jeder Meldung eine Richtung zu: Rueckenwind, Gegenwind oder neutral.

Der Standpunkt ist festgelegt und steht auch so auf der Seite:

    Erleichtert diese Meldung den Ausbau von KI-Rechenzentren, oder erschwert
    sie ihn?

Ohne festen Standpunkt ist "gut" und "schlecht" bedeutungslos. Steigende
DRAM-Preise sind gut fuer Micron, schlecht fuer Nvidias Stueckkosten und
schlecht fuer den PC-Kaeufer. Erst der Standpunkt macht das Etikett pruefbar -
und nur ein pruefbares Etikett taugt spaeter als Lernmaterial.

WARUM KEIN SPRACHMODELL

Der naheliegende Weg waere, das lokale Modell klassifizieren zu lassen.
Gemessen am 30.08.2026 auf dieser Maschine:

    27 bis 65 Sekunden je Meldung (Decode 0,3-0,8 t/s statt 19)
    und als Ergebnis "neutral" fuer einen Streik, fuer eine
    31-Milliarden-Investition und fuer 50 Prozent Preisanstieg

Ein Streik ist kein neutrales Ereignis. Bewerten heisst urteilen, und genau
davon raet die Anleitung zum lokalen Modell ab. Deshalb entscheidet hier eine
Liste von Signalwoertern.

Das ist kein Notbehelf, sondern fuer diese Aufgabe die bessere Loesung:

    nachvollziehbar   das gefundene Signalwort IST die Begruendung
    reproduzierbar    zweimal derselbe Titel, zweimal dasselbe Etikett
    korrigierbar      ein falsches Signalwort sieht man und aendert es
    schnell           Millisekunden statt einer halben Minute

Was kein Signalwort trifft, bleibt "unbestimmt". Raten waere schlechter als
zugeben, dass es unklar ist.

LERNEN

Jede Bewertung speichert, welches Signalwort sie ausgeloest hat. Zusammen mit
korrekturen.json - dort ueberschreibt die Redaktion einzelne Etiketten samt
Grund - entsteht ein Datensatz aus Titel, Etikett und Begruendung. Das ist das
Material, aus dem sich spaeter lernen laesst, warum etwas Rueckenwind ist.

Rueckgabewerte:
  0  bewertet
  1  nachrichten.json fehlt

Aufruf:  python werkzeuge/bewerten.py [--zeige-unbestimmt]
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "nachrichten.json"
KORREKTUREN = WURZEL / "korrekturen.json"
LOG = WURZEL / "lauf.log"

# (Muster, Richtung, was das Signal bedeutet)
#
# Reihenfolge zaehlt nicht - es werden alle Treffer gesammelt und am Ende
# gegeneinander gestellt. Ein Titel mit Signalen in beide Richtungen wird
# "gemischt" und nicht kuenstlich aufgeloest.
SIGNALE = [
    # ---------------- Gegenwind: etwas fehlt, stockt oder bricht ----------
    (r"\b(engpass|bottleneck|knappheit|shortage|mangel)\b", "gegen",
     "Engpass gemeldet"),
    (r"\b(ausverkauft|sold out|fully booked|ausgebucht|stretched|constrain\w*)\b",
     "gegen", "Kapazitaet ausgebucht"),
    (r"\b(lieferzeit|lead time|wartezeit|backlog)\b", "gegen",
     "lange Lieferzeit"),
    (r"\b(verzoeger\w*|verzöger\w*|delay\w*|postpone\w*|verschiebt|pushed back|"
     r"slips?)\b", "gegen", "Verzoegerung"),
    (r"\b(streik|strike|walkout|arbeitskampf|gewerkschaft|union)\b", "gegen",
     "Arbeitskampf"),
    (r"\b(exportverbot|export ban|export control|export restriction|"
     r"exportkontrolle|exportbeschr\w*|sanktion\w*|sanction\w*|entity list|"
     r"ausfuhrbeschr\w*)\b", "gegen", "Handelsbeschraenkung"),
    (r"\b(zoll|zoelle|zölle|tariff\w*)\b", "gegen", "Zoelle"),
    (r"\b(rueckruf|rückruf|recall|defekt|defect|fehler\w*|flaw|bug)\b", "gegen",
     "Qualitaetsproblem"),
    # "brand" ist deutsch Feuer und englisch Marke - nur eindeutige Formen.
    (r"\b(ausfall|outage|downtime|stoerung|störung|grossbrand|großbrand|"
     r"fabrikbrand|feuer|erdbeben|earthquake|flooding|ueberschwemmung)\b",
     "gegen", "Stoerung oder Unglueck"),
    (r"\b(entlass\w*|layoff\w*|stellenabbau|job cuts|kuerz\w*|kürz\w*|cuts?)\b",
     "gegen", "Kuerzung"),
    (r"\b(klage|lawsuit|sues?|untersuchung|probe|investigation|kartell|"
     r"antitrust|bussgeld|bußgeld|fine)\b", "gegen", "Rechtsstreit oder Aufsicht"),
    (r"\b(scheiter\w*|fails?|failed|abgesagt|cancel\w*|aufgegeben|scrapp\w*|"
     r"eingestellt)\b", "gegen", "gescheitert oder abgesagt"),
    (r"\b(teurer|preisanstieg|preise steigen|price (increase|hike|surge)|"
     r"verteuert|kostenanstieg)\b", "gegen", "steigende Kosten"),
    (r"\b(ueberhitz\w*|überhitz\w*|thermal (issue|problem)|kuehlungsproblem)\b",
     "gegen", "thermisches Problem"),
    (r"\b(netzanschluss|grid (constraint|connection)|stromknappheit|"
     r"power (shortage|constraint)|moratorium)\b", "gegen", "Stromversorgung stockt"),

    # ---------------- Rueckenwind: etwas entsteht oder gelingt ------------
    (r"\b(grundstein|breaks? ground|groundbreaking|spatenstich|baubeginn)\b",
     "rueckenwind", "Baubeginn"),
    (r"\b(ausbau|expansion|erweitert|expands?|aufstockung|scales? up|"
     r"hochlauf|ramp\w*)\b", "rueckenwind", "Kapazitaetsausbau"),
    (r"\b(serienproduktion|mass production|volume production|in produktion|"
     r"produktionsstart|in betrieb genommen|geht in betrieb|now shipping|"
     r"verfuegbar ab|generally available)\b", "rueckenwind", "Produktionsstart"),
    (r"\b(rekord|record|bestwert|all-time high|hoechststand|höchststand)\b",
     "rueckenwind", "Rekordwert"),
    # invest\w* verschluckte "investigation" - deshalb die Formen einzeln.
    (r"\b(investiert|investier\w+|investment|investments|invests|investing|"
     r"milliarden (fuer|in)|billion (for|into)|finanzierung|funding|"
     r"kapitalerhoehung)\b", "rueckenwind", "Investition"),
    (r"\b(vereinbarung|agreement|partnership|kooperation|deal|vertrag|"
     r"abkommen|allianz|alliance)\b", "rueckenwind", "Vereinbarung"),
    (r"\b(auftrag|auftraege|aufträge|order[sn]?\b|bestellung\w*|gebucht|books?)\b",
     "rueckenwind", "Auftragseingang"),
    (r"\b(uebertrifft|übertrifft|beats?|exceeds?|besser als erwartet|"
     r"outperform\w*|schlaegt|schlägt)\b", "rueckenwind", "uebertrifft Erwartung"),
    (r"\b(durchbruch|breakthrough|erstmals|world'?s first|weltweit erste[rns]?|"
     r"first ever)\b", "rueckenwind", "erstmals gelungen"),
    (r"\b(ausbeute|yield)\b.{0,24}\b(steigt|verbessert|improve\w*|rises?|"
     r"\d{2}\s*(prozent|percent|%))", "rueckenwind", "Ausbeute verbessert"),
    (r"\b(guenstiger|günstiger|billiger|lower cost|cost reduction|senkt (die )?"
     r"kosten|cheaper|spart)\b", "rueckenwind", "Kosten sinken"),
    (r"\b(zulassung|approval|genehmigt|approved|zertifiziert|certified|"
     r"freigabe)\b", "rueckenwind", "Genehmigung erteilt"),
    # accelerat\w* traf das Substantiv "AI Accelerators" - nur Verben.
    (r"\b(schneller als|faster than|beschleunigt|accelerates|speeds up|"
     r"\d+(,\d+)?\s*(x|mal|fach) (schneller|faster))\b", "rueckenwind",
     "Leistungssprung"),
    (r"\b(neue[rns]? (fabrik|werk|fab|standort)|new (fab|plant|factory)|"
     r"kapazitaet (erhoeht|steigt)|raises? capacity|capacity (boost|increase))\b",
     "rueckenwind", "neue Kapazitaet"),
]

VORAB = [(re.compile(p, re.I), r, g) for p, r, g in SIGNALE]

# Ein Dementi kehrt die Aussage um: "SK hynix dementiert Intel-Deal" ist kein
# Rueckenwind, nur weil das Wort "Deal" darin vorkommt. Solche Titel werden
# nicht umgedreht, sondern unbestimmt - was verneint wurde, ist kein Ereignis,
# ueber dessen Richtung man etwas wuesste.
DEMENTI = re.compile(
    r"\b(dementiert|dementi|weist .{0,20}zurueck|widerspricht|denies|denied|"
    r"refutes?|rejects?|abgelehnt|nicht bestaetigt|no plans|"
    r"keine? (plaene|plan|deal|vereinbarung))\b", re.I)


def log(msg):
    zeile = "%s  bewerten  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(zeile)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass


def bewerte(titel, zeile=None):
    """Gibt (richtung, gruende) zurueck.

    Geprueft wird Originaltitel und deutsche Zeile - die Signalwoerter stehen
    mal in der einen, mal in der anderen Fassung."""
    text = titel + (" " + zeile if zeile and zeile != titel else "")
    if DEMENTI.search(text):
        return "unbestimmt", []
    treffer, gruende = Counter(), []
    gesehen = set()
    for muster, richtung, grund in VORAB:
        m = muster.search(text)
        if not m:
            continue
        treffer[richtung] += 1
        if grund not in gesehen:
            gesehen.add(grund)
            gruende.append({"grund": grund, "richtung": richtung,
                            "fundstelle": m.group(0)})
    if not treffer:
        return "unbestimmt", []
    g, r = treffer.get("gegen", 0), treffer.get("rueckenwind", 0)
    if g and r:
        return "gemischt", gruende
    return ("gegenwind" if g else "rueckenwind"), gruende


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zeige-unbestimmt", action="store_true",
                   help="listet Meldungen auf, die kein Signalwort trifft - "
                        "die Vorlage zum Erweitern der Liste")
    a = p.parse_args()

    if not QUELLE.exists():
        log("nachrichten.json fehlt")
        return 1
    N = json.loads(QUELLE.read_text(encoding="utf-8"))

    # Redaktionskorrekturen haben Vorrang und sind der Kern des Lernteils:
    # {"<meldungs-id>": {"richtung": "gegenwind", "grund": "warum"}}
    korr = {}
    if KORREKTUREN.exists():
        try:
            korr = json.loads(KORREKTUREN.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("korrekturen.json unlesbar - wird ignoriert")

    zaehler = Counter()
    for m in N.get("meldungen", []):
        richtung, gruende = bewerte(m["titel"], m.get("zeile"))
        quelle = "signalwort"
        if m["id"] in korr:
            k = korr[m["id"]]
            richtung = k.get("richtung", richtung)
            gruende = [{"grund": k.get("grund", "von der Redaktion gesetzt"),
                        "richtung": richtung, "fundstelle": None}]
            quelle = "redaktion"
        m["wind"] = richtung
        m["wind_grund"] = gruende
        m["wind_quelle"] = quelle
        zaehler[richtung] += 1

    # Der Zeiger: nur die eindeutigen Faelle zaehlen. Gemischt und unbestimmt
    # gehen nicht als halber Ausschlag ein, sie stehen als eigene Zahl daneben.
    r, g = zaehler["rueckenwind"], zaehler["gegenwind"]
    stand = round((r - g) / (r + g), 3) if (r + g) else 0.0

    N["wind"] = {
        "standpunkt": "Erleichtert die Meldung den Ausbau von KI-Rechenzentren "
                      "oder erschwert sie ihn?",
        "verfahren": "Signalwoerter im Titel, keine Modellbewertung",
        "stand": stand,
        "rueckenwind": r,
        "gegenwind": g,
        "gemischt": zaehler["gemischt"],
        "unbestimmt": zaehler["unbestimmt"],
        "korrigiert": sum(1 for m in N.get("meldungen", [])
                          if m.get("wind_quelle") == "redaktion"),
    }
    QUELLE.write_text(json.dumps(N, ensure_ascii=False, indent=1), encoding="utf-8")

    log("Rueckenwind %d, Gegenwind %d, gemischt %d, unbestimmt %d, Zeiger %+.2f"
        % (r, g, zaehler["gemischt"], zaehler["unbestimmt"], stand))

    if a.zeige_unbestimmt:
        offen = [m for m in N["meldungen"]
                 if m["wind"] == "unbestimmt" and not m.get("rauschen")][:25]
        print("\nOhne Signalwort (Vorlage zum Erweitern der Liste):")
        for m in offen:
            print("   " + (m.get("zeile") or m["titel"])[:88])
    return 0


if __name__ == "__main__":
    sys.exit(main())
