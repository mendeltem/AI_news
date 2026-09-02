#!/usr/bin/env python3
"""Holt die Nachrichten des Tages zu allem, was in themen.json steht.

Quelle ist der RSS-Ausgang von Google News - kein Schluessel, kein Konto, kein
Anbieter dazwischen, der wegfallen kann. Je Eintrag der Beobachtungsliste eine
Abfrage, danach zusammenlegen und entdoppeln.

Der Lauf merkt sich in archiv/gesehen.json, was er schon hatte. Ein zweiter
Aufruf am selben Tag holt also nur Neues und schreibt nichts doppelt.

Rueckgabewerte:
  0  fertig (auch wenn nichts Neues da war)
  1  keine einzige Abfrage kam durch - vermutlich kein Netz

Aufruf:  python werkzeuge/sammeln.py [--tage 2] [--limit N] [--nur NVDA,HBM]
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
THEMEN = WURZEL / "themen.json"
ARCHIV = WURZEL / "archiv"
GESEHEN = ARCHIV / "gesehen.json"
LOG = WURZEL / "lauf.log"

KOPF = {"User-Agent": "Mozilla/5.0 (compatible; AI-news-sammler/1.0; "
                      "+https://github.com/mendeltem/AI_news)"}
PAUSE = 0.35          # Sekunden zwischen zwei Abfragen
ZEITFENSTER_TAGE = 2    # Firmen: aelteres interessiert im Tagesfeed nicht
ZEITFENSTER_THEMEN = 8  # Themen bewegen sich im Wochentakt, nicht taeglich

# Quellen, deren Meldungen erfahrungsgemaess Substanz haben. Kein Filter -
# nur ein Bonus bei der Sortierung, damit oben nicht die Aggregatoren stehen.
GUTE_QUELLEN = {
    "reuters", "bloomberg", "financial times", "wall street journal", "nikkei",
    "the information", "tom's hardware", "anandtech", "servethehome",
    "semianalysis", "trendforce", "digitimes", "heise", "golem", "the register",
    "ieee spectrum", "techcrunch", "ars technica", "cnbc", "handelsblatt",
    "korea herald", "businesskorea", "the elec", "nikkei asia", "eetimes",
}

# Aktientipp-Muehlen. Die schreiben taeglich ueber dieselben Ticker, ohne dass
# etwas passiert ist - genau das Rauschen, das den Feed unbrauchbar macht.
# Kein harter Ausschluss, aber sie sollen nicht oben stehen.
SCHWACHE_QUELLEN = {
    "der aktionär", "der aktionaer", "ntg24", "investing.com", "sharewise",
    "finanznachrichten", "wallstreet-online", "wallstreet online", "motley fool",
    "the motley fool", "zacks", "benzinga", "tipranks", "simply wall st",
    "simplywall", "insider monkey", "24/7 wall st", "aktiencheck", "boerse",
    "börse", "marketbeat", "stocktwits", "invezz", "barchart", "gurufocus",
    "finanzen.ch", "finanzen.net", "finanztrends", "tradingkey", "fool.de",
    "aktien-global", "onvista", "boersennews", "4investors", "stock3",
    "investing.com deutsch", "sharedeals", "boersen-zeitung",
}

# Schlagzeilenmuster ohne Nachricht: Kauf-oder-Verkauf-Vergleiche, Kursziele,
# Depotumschichtungen. Erkennt man am Titel, nicht an der Quelle.
RAUSCHMUSTER = re.compile(
    r"(better (stock|buy)|which .* (stock|giant)|should you buy|buy or sell|"
    r"kursziel|aktie kaufen|jetzt einsteigen|prognose \d{4}|"
    r"\bmillionär|reich werden|these \d+ stocks|top \d+ stocks|"
    r"schichtet um|depot|dividende|\bpennystock|"
    r"aktie news|tendiert|b[uü]sst|gewinnt am|verliert am|zeigt sich|"
    r"aktienkursprognose|kursanalyse|charttechnik|analysten|kaufempfehlung|"
    r"so viel .* w[aä]re|h[aä]tten sie|w[aä]re ihr investment|"
    r"tiefstpreis|bestpreis|nie g[uü]nstiger|deal des tages|"
    r"schn[aä]ppchen|jetzt reduziert|prime day|black friday)", re.I)

# Videokanal-Auswurf. Faellt beim Sortieren von Hand sofort auf: Titel wie
# "10 AKTIEN Alphabet Microsoft Amazon ... Real Betis Vs Elche (u2FAu6pMjM)"
# reihen Firmennamen aneinander und haengen eine Video-Kennung an. Sie treffen
# damit ein Dutzend beobachteter Eintraege auf einmal und stehen ohne diesen
# Filter weit oben.
# Marktgeplauder. Abgeleitet aus 109 von Hand sortierten Meldungen vom
# 02.09.2026: von den Meldungen, die den bisherigen Filter passiert hatten,
# wurden 36 Prozent als wertlos aussortiert - fast durchweg Kursberichte,
# Quartalsvorschauen und Wer-gewinnt-Spekulation.
#
# Aufgenommen sind nur die mechanisch eindeutigen Faelle. Grenzfaelle wie
# "TSMC packaging shift could boost AMD CoWoS share" wurden zwar ebenfalls
# aussortiert, sind aber inhaltlich Lieferkettenmeldungen - die bleiben drin.
MARKTGEPLAUDER = re.compile(
    # Indexstaende, Futures, Vorboersliches
    r"(pre-?market|nachboerslich|vorboerslich|"
    r"\b(nasdaq|dow jones|s&p ?500|dax|nikkei)\b.*\b(futures?|schliesst|starten|"
    r"hold|slide|rise)|"
    # b[oö] traf "börsen" und "borsen", nicht aber die oe-Umschrift, die in
    # deutschen Titeln genauso vorkommt.
    r"b(oe|ö|o)rsen-?ticker|markets? live|us[- ]markt|marktbericht|"
    # Kursbewegung als Nachricht
    r"\bstocks?\b.{0,24}\b(rally|slide|soar|plunge|see-?saw|jump|tumble|dip)|"
    r"\b(shares?|aktien?)\b.{0,20}\b(steigen|fallen|springen|rutschen|verlieren)|"
    r"chip[- ]aktien|semiconductor stocks|memory stocks|"
    # Quartalsvorschau und Analystenrunden
    r"ahead of (its |their )?earnings|vor den quartalszahlen|"
    r"analyst (research calls?|blog)|zacks|options market statistics|"
    r"draw[s]? focus|in focus after|"
    # Wer-gewinnt-Spekulation
    r"biggest (ai )?(winner|loser)|winner or loser|which stock|"
    r"^not (nvidia|amd|intel)\b|better than nvidia|"
    # Makro ohne Chipbezug
    r"rate pressure|bond selloff|lifts yields|amid .* yields|"
    # Angebote
    r"save \$\d+|now just \$|\bdeal[s]? of the day)", re.I)

SPAM = [
    # Emoji im Titel - serioese Nachrichtenhaeuser setzen keine.
    re.compile(r"[\U0001F300-\U0001FAFF☀-➿️]"),
    # elfstellige Videokennung in Klammern, wie sie YouTube vergibt
    re.compile(r"\([A-Za-z0-9_-]{11}\)"),
    # Aufzaehlungs-Clickbait
    re.compile(r"^\s*\d{1,2}\s+(aktien|stocks|shares)\b", re.I),
]


def log(msg):
    zeile = "%s  sammeln  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(zeile)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass


def rss_url(suche, sprache="de", tage=7):
    """Beide Sprachen, absichtlich: die deutsche Presse bringt Golem und heise,
    die Substanz zu Speicherpreisen und Fertigung steht bei TrendForce,
    DigiTimes und Reuters und erscheint nur englisch.

    tage steuert das Fenster der Anfrage. Es muss mindestens so breit sein wie
    das Fenster, nach dem spaeter gefiltert wird - sonst filtert man Material,
    das gar nicht erst geholt wurde."""
    q = urllib.parse.quote(suche)
    if sprache == "en":
        return ("https://news.google.com/rss/search?q=%s+when:%dd"
                "&hl=en-US&gl=US&ceid=US:en" % (q, tage))
    return ("https://news.google.com/rss/search?q=%s+when:%dd"
            "&hl=de&gl=DE&ceid=DE:de" % (q, tage))


def hole(url, versuche=2):
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers=KOPF)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if i + 1 == versuche:
                return None
            time.sleep(1.5)
    return None


def parse_rss(roh):
    """Gibt (titel, link, quelle, datum_iso) je Eintrag zurueck."""
    try:
        wurzel = ET.fromstring(roh)
    except ET.ParseError:
        return []
    raus = []
    for item in wurzel.iter("item"):
        t = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not t or not link:
            continue
        quelle = ""
        src = item.find("source")
        if src is not None and src.text:
            quelle = src.text.strip()
        # Google haengt " - Quelle" an den Titel; das trennen wir ab.
        if not quelle and " - " in t:
            t, _, quelle = t.rpartition(" - ")
        dat = item.findtext("pubDate") or ""
        iso = ""
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                iso = datetime.strptime(dat, fmt).replace(
                    tzinfo=timezone.utc).isoformat()
                break
            except ValueError:
                continue
        raus.append((t.strip(), link, quelle.strip(), iso))
    return raus


def schluessel(titel):
    """Erkennt dieselbe Meldung bei verschiedenen Haeusern am normalisierten
    Titel - Satzzeichen und Fuellwoerter raus, dann Hash."""
    t = titel.lower()
    t = re.sub(r"[^\wäöüß ]+", " ", t)
    t = re.sub(r"\b(der|die|das|den|dem|des|ein|eine|einen|und|oder|von|mit|"
               r"fuer|für|the|a|an|of|to|in|on|for|and|is|says|said)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:16]


def treffer(text, eintrag):
    """Kommt dieser beobachtete Eintrag im Text vor?"""
    name = eintrag["name"]
    if len(name) >= 4 and re.search(r"\b%s\b" % re.escape(name), text, re.I):
        return True
    # Ticker nur, wenn er nicht zufaellig ein Wort ist (ON, ARM, NOW ...)
    tic = eintrag.get("id", "")
    if (eintrag.get("art") == "boersennotiert" and 3 <= len(tic) <= 8
            and tic.isupper() and tic not in {"ON", "ARM", "NOW", "ALL"}):
        if re.search(r"\b%s\b" % re.escape(tic), text):
            return True
    # Stichworte sind der Relevanzbeweis und werden als ganze Wendung geprueft.
    #
    # Hier stand frueher eine Ableitung aus den Suchbegriffen: kern =
    # s.split()[0]. Aus "TSMC advanced packaging capacity" wurde damit "TSMC",
    # aus "semiconductor export restriction" wurde "semiconductor" - und jede
    # TSMC-Meldung trug #CoWoS. Der Suchbegriff sagt, wonach gesucht wird; er
    # sagt nicht, wovon die gefundene Meldung handelt.
    for w in eintrag.get("stichworte", []):
        muster = r"\b%s\b" % re.escape(w) if re.match(r"\w", w) else re.escape(w)
        if re.search(muster, text, re.I):
            return True
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tage", type=int, default=ZEITFENSTER_TAGE,
                   help="Zeitfenster fuer Firmen (Vorgabe 2)")
    p.add_argument("--tage-themen", type=int, default=ZEITFENSTER_THEMEN,
                   help="Zeitfenster fuer Querschnittsthemen (Vorgabe 8)")
    p.add_argument("--limit", type=int, help="nur die ersten N Eintraege abfragen")
    p.add_argument("--nur", help="Kommaliste von IDs, sonst alles")
    a = p.parse_args()

    if not THEMEN.exists():
        log("themen.json fehlt - erst werkzeuge/saat.py laufen lassen")
        return 1
    T = json.loads(THEMEN.read_text(encoding="utf-8"))
    beob = T["beobachtet"]
    if a.nur:
        will = {x.strip().upper() for x in a.nur.split(",")}
        beob = [e for e in beob if e["id"].upper() in will]
    if a.limit:
        beob = beob[:a.limit]

    ARCHIV.mkdir(exist_ok=True)
    gesehen = {}
    if GESEHEN.exists():
        try:
            gesehen = json.loads(GESEHEN.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("gesehen.json unlesbar - wird neu angelegt")

    # Zwei Zeitfenster, und der Unterschied ist beabsichtigt: Firmennachrichten
    # sind Tagesgeschaeft, Querschnittsthemen wie CoWoS oder NAND-Preise
    # bewegen sich im Wochentakt. Mit einem gemeinsamen 2-Tage-Fenster sehen
    # genau die strukturellen Themen leer aus, wegen derer die Seite existiert.
    grenze_firma = datetime.now(timezone.utc) - timedelta(days=a.tage)
    grenze_thema = datetime.now(timezone.utc) - timedelta(days=a.tage_themen)
    meldungen = {}
    ok = 0

    for i, e in enumerate(beob, 1):
        suchen = e.get("suchen") or [e["name"]]
        # Kern-Eintraege in beiden Sprachen, Anwendungsfirmen nur englisch -
        # ueber die schreibt die deutsche Presse ohnehin kaum.
        sprachen = ("de", "en") if e.get("stufe") == 1 else ("en",)
        ist_thema = e.get("art") == "thema"
        fenster = (a.tage_themen if ist_thema else a.tage) + 2
        for s in suchen:
            for spr in sprachen:
                roh = hole(rss_url(s, spr, fenster))
                time.sleep(PAUSE)
                if roh is None:
                    continue
                ok += 1
                grenze = grenze_thema if ist_thema else grenze_firma
                for titel, link, quelle, iso in parse_rss(roh):
                    if iso:
                        try:
                            if datetime.fromisoformat(iso) < grenze:
                                continue
                        except ValueError:
                            pass
                    k = schluessel(titel)
                    m = meldungen.setdefault(k, {
                        "id": k, "titel": titel, "link": link,
                        "quelle": quelle, "datum": iso,
                        "gefunden_ueber": [], "bezug": [],
                    })
                    if e["id"] not in m["gefunden_ueber"]:
                        m["gefunden_ueber"].append(e["id"])
        if i % 25 == 0:
            log("%d/%d abgefragt, %d Meldungen" % (i, len(beob), len(meldungen)))

    if ok == 0:
        log("keine einzige Abfrage kam durch")
        return 1

    # Bezug bestimmen: welcher beobachtete Eintrag steht wirklich im Titel.
    #
    # Frueher wurde hier zusaetzlich uebernommen, worueber die Meldung
    # *gefunden* wurde. Das war der eigentliche Grund fuer die falschen
    # Hashtags: die Suchanfrage "TSMC advanced packaging capacity" liefert
    # allgemeine TSMC-Meldungen, und die trugen dann alle #CoWoS. Gefunden
    # zu werden ist kein Beleg fuer Relevanz - es steht deshalb nur noch in
    # gefunden_ueber und wird nicht mehr zum Hashtag.
    alle = {e["id"]: e for e in T["beobachtet"]}
    for m in meldungen.values():
        text = m["titel"]
        m["bezug"] = [eid for eid, e in alle.items() if treffer(text, e)][:6]
        m["hashtags"] = [alle[b]["hashtag"] for b in m["bezug"] if b in alle]
        m["neu"] = m["id"] not in gesehen

        q = (m["quelle"] or "").lower()
        gut = any(g in q for g in GUTE_QUELLEN)
        schwach = any(g in q for g in SCHWACHE_QUELLEN)
        rausch = (bool(RAUSCHMUSTER.search(m["titel"]))
                  or bool(MARKTGEPLAUDER.search(m["titel"]))
                  or any(p.search(m["titel"]) for p in SPAM))
        kern = sum(1 for b in m["bezug"] if alle.get(b, {}).get("stufe") == 1)
        m["rauschen"] = schwach or rausch
        m["gewicht"] = round(kern * 2 + (3 if gut else 0)
                             + (2 if m["neu"] else 0)
                             + min(len(m["gefunden_ueber"]), 4)
                             - (6 if schwach else 0)
                             - (5 if rausch else 0), 1)

    sortiert = sorted(meldungen.values(),
                      key=lambda m: (-m["gewicht"], m.get("datum") or ""))

    heute = datetime.now().strftime("%Y-%m-%d")
    aus = {
        "stand": datetime.now().isoformat(timespec="seconds"),
        "tag": heute,
        "abgefragt": len(beob),
        "meldungen_gesamt": len(sortiert),
        "meldungen_neu": sum(1 for m in sortiert if m["neu"]),
        "meldungen": sortiert,
    }
    (WURZEL / "nachrichten.json").write_text(
        json.dumps(aus, ensure_ascii=False, indent=1), encoding="utf-8")
    (ARCHIV / ("%s.json" % heute)).write_text(
        json.dumps(aus, ensure_ascii=False, indent=1), encoding="utf-8")

    for m in sortiert:
        gesehen[m["id"]] = heute
    # Aelteres als 60 Tage brauchen wir zum Entdoppeln nicht mehr.
    schwelle = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    gesehen = {k: v for k, v in gesehen.items() if v >= schwelle}
    GESEHEN.write_text(json.dumps(gesehen, ensure_ascii=False), encoding="utf-8")

    log("%d Meldungen (%d neu) aus %d Abfragen"
        % (len(sortiert), aus["meldungen_neu"], ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
