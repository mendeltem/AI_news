#!/usr/bin/env python3
"""Schreibt den Tagesstand in den Korpus - archiv/korpus.jsonl.

Warum eine eigene Datei neben den Tagesdateien:

  archiv/JJJJ-MM-TT.json   Momentaufnahme. Beantwortet "wie sah der Feed am
                           12. September aus". Enthaelt jede Meldung so oft,
                           wie sie an Tagen auftauchte - fuer Trainingsdaten
                           also unbrauchbar redundant.

  archiv/korpus.jsonl      Eine Zeile je Meldung, die es je gab, genau einmal.
                           Wird nur angehaengt, nie umgeschrieben. Das ist das
                           Format, das man spaeter einem Modell vorlegt oder
                           mit pandas einliest.

Eine Zeile sieht so aus:

  {"id": "a1b2c3d4e5f6g7h8",      Titel-Hash, stabil ueber alle Laeufe
   "erstgesehen": "2026-08-30",   wann die Meldung zum ersten Mal auftauchte
   "datum": "2026-08-29T14:22:00+00:00",
   "titel": "SK hynix breaks ground ...",     Originalschlagzeile
   "zeile": "SK hynix legt den Grundstein ...",  deutsche Fassung, falls erzeugt
   "quelle": "Tom's Hardware",
   "link": "https://...",
   "bezug": ["SKHYNIX", "HBM"],   welche beobachteten Eintraege vorkommen
   "hashtags": ["#SKHynix", "#HBM"],
   "gewicht": 10.0,
   "rauschen": false}             true = Aktientipp-Quelle oder Kursmeldung

Der Lauf ist idempotent: eine bereits archivierte id wird nicht noch einmal
geschrieben. Ein zweiter Aufruf am selben Tag ergaenzt hoechstens die deutschen
Zeilen, die beim ersten Mal noch fehlten.

Rueckgabewerte:
  0  fertig
  1  nachrichten.json fehlt

Aufruf:  python werkzeuge/archivieren.py [--auch-rauschen]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "nachrichten.json"
ARCHIV = WURZEL / "archiv"
KORPUS = ARCHIV / "korpus.jsonl"
LOG = WURZEL / "lauf.log"

FELDER = ["id", "erstgesehen", "datum", "titel", "zeile", "quelle", "link",
          "bezug", "hashtags", "gewicht", "rauschen",
          "wind", "wind_grund", "wind_quelle"]


def log(msg):
    zeile = "%s  archiv  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(zeile)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass


def vorhandene_ids():
    """Was schon im Korpus steht, samt Zeilennummer - damit wir fehlende
    deutsche Zeilen spaeter nachtragen koennen, ohne zu verdoppeln."""
    if not KORPUS.exists():
        return {}, []
    ids, zeilen = {}, []
    with KORPUS.open(encoding="utf-8") as f:
        for i, z in enumerate(f):
            z = z.strip()
            if not z:
                continue
            try:
                e = json.loads(z)
            except json.JSONDecodeError:
                zeilen.append(z)      # kaputte Zeile unveraendert behalten
                continue
            ids[e.get("id")] = i
            zeilen.append(z)
    return ids, zeilen


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--auch-rauschen", action="store_true",
                   help="abgewertete Meldungen ebenfalls archivieren "
                        "(Vorgabe: ja, sie sind als rauschen=true markiert)")
    p.parse_args()

    if not QUELLE.exists():
        log("nachrichten.json fehlt")
        return 1

    N = json.loads(QUELLE.read_text(encoding="utf-8"))
    tag = N.get("tag") or datetime.now().strftime("%Y-%m-%d")
    ARCHIV.mkdir(exist_ok=True)

    bekannt, zeilen = vorhandene_ids()
    neu, ergaenzt = 0, 0

    for m in N.get("meldungen", []):
        satz = {
            "id": m["id"],
            "erstgesehen": tag,
            "datum": m.get("datum") or None,
            "titel": m["titel"],
            "zeile": m.get("zeile") or None,
            "quelle": m.get("quelle") or None,
            "link": m.get("link"),
            "bezug": m.get("bezug", []),
            "hashtags": m.get("hashtags", []),
            "gewicht": m.get("gewicht"),
            "rauschen": bool(m.get("rauschen")),
            # Richtung samt Begruendung - das eigentliche Lernmaterial.
            # wind_quelle sagt, ob ein Signalwort oder die Redaktion entschied.
            "wind": m.get("wind"),
            "wind_grund": m.get("wind_grund", []),
            "wind_quelle": m.get("wind_quelle"),
        }
        satz = {k: satz[k] for k in FELDER}

        if m["id"] not in bekannt:
            zeilen.append(json.dumps(satz, ensure_ascii=False))
            bekannt[m["id"]] = len(zeilen) - 1
            neu += 1
            continue

        # Schon da: nur nachtragen, was beim ersten Mal fehlte. Erstgesehen
        # bleibt stehen - das ist der Wert, der die Zeitreihe traegt.
        i = bekannt[m["id"]]
        try:
            alt = json.loads(zeilen[i])
        except json.JSONDecodeError:
            continue
        geaendert = False
        if not alt.get("zeile") and satz["zeile"]:
            alt["zeile"] = satz["zeile"]
            geaendert = True
        # Die Richtung wird nachgetragen und aktualisiert: eine
        # Redaktionskorrektur muss den alten Automatikwert ueberschreiben,
        # sonst steht im Datensatz weiter das falsche Etikett.
        if satz["wind"] and (alt.get("wind") != satz["wind"]
                             or satz["wind_quelle"] == "redaktion"):
            alt["wind"] = satz["wind"]
            alt["wind_grund"] = satz["wind_grund"]
            alt["wind_quelle"] = satz["wind_quelle"]
            geaendert = True
        if geaendert:
            zeilen[i] = json.dumps(alt, ensure_ascii=False)
            ergaenzt += 1

    KORPUS.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    log("Korpus: %d Zeilen gesamt, %d neu, %d deutsche Zeilen nachgetragen"
        % (len(zeilen), neu, ergaenzt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
