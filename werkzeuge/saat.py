#!/usr/bin/env python3
"""Erzeugt themen.json - die Beobachtungsliste, aus der der taegliche Lauf sucht.

Die Liste wird nicht von Hand gepflegt, sondern aus den beiden Bestandsseiten
gezogen, damit sie nicht auseinanderlaeuft:

  nvidia-oekosystem.html   66 boersennotierte Firmen, Schicht und Rolle
  ai_use_cases_overview    15 Cluster, 91 Anwendungen, genannte Firmen

Dazu kommen die privaten KI-Labore, die auf keiner Kachel stehen, aber die
Nachfrage erzeugen - die Oekosystem-Seite sagt das selbst.

Aufruf:  python werkzeuge/saat.py [--quelle-firmen PFAD] [--quelle-cases PFAD]

Ohne Pfade wird von GitHub geladen. Ergebnis: themen.json im Repo-Wurzelordner.
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "themen.json"

ROH_FIRMEN = "https://raw.githubusercontent.com/mendeltem/AI_Companys/main/nvidia-oekosystem.html"
ROH_CASES = "https://raw.githubusercontent.com/mendeltem/ai_use_cases_overview/main/index.html"

# Die Schichten in der Reihenfolge, in der die Oekosystem-Seite sie fuehrt.
# Die Firmen-JSON traegt die Schicht nicht mit, die Reihenfolge aber schon.
SCHICHTEN = [
    ("Chip-Entwurf", 5), ("Fertigung", 4), ("Fertigungsanlagen", 4),
    ("Speicher", 5), ("Packaging und Test", 2), ("Netzwerk und Optik", 4),
    ("Systeme", 3), ("Strom und Kuehlung", 3), ("Cloud und Betrieb", 7),
    ("Licht und Detektor", 5), ("LiDAR-Systeme", 5), ("Edge-Gehirn", 3),
    ("Aktoren und Roboter", 2), ("Endgeraete", 1), ("Wirkstoffsuche", 6),
    ("Anwendung und Erloes", 6), ("Systeme (weitere)", 1),
]

# Privat, keine Quartalszahlen, trotzdem der Grund fuer die Nachfrage.
LABORE = [
    ("OpenAI", "KI-Labor", "GPT, groesster Einzelabnehmer von Rechenzeit"),
    ("Anthropic", "KI-Labor", "Claude, Coding-Agenten"),
    ("xAI", "KI-Labor", "Grok, eigenes Rechenzentrum Colossus"),
    ("Mistral AI", "KI-Labor", "offene Modelle, Europa"),
    ("Safe Superintelligence", "KI-Labor", "Forschung, kein Produkt"),
    ("DeepSeek", "KI-Labor", "offene Modelle, China"),
    ("Isomorphic Labs", "KI-Labor", "Wirkstoffsuche, gehoert Alphabet"),
]

# Themen ohne Firmenbezug, die den Kern der Frage beruehren: was kostet der
# Speicher, was kostet der Strom, wie schnell kommt die naechste Architektur.
#
# Zwei getrennte Listen, und die Trennung ist der Punkt:
#   suchen      was in die Suchmaschine geht - darf weit sein
#   stichworte  was im Titel stehen muss, damit die Meldung das Thema wirklich
#               betrifft - muss eng sein
# Frueher wurde das Stichwort aus dem ersten Wort des Suchbegriffs abgeleitet.
# Aus "Advanced Packaging" wurde "Advanced", aus "semiconductor export
# restriction" wurde "semiconductor" - und damit trug jede zweite Chipmeldung
# den Hashtag #CoWoS oder #Exportkontrolle.
THEMEN = [
    ("HBM", "Speicher",
     ["HBM4", "HBM Preis", "HBM Kapazitaet", "HBM4E"],
     ["HBM", "HBM3", "HBM3E", "HBM4", "HBM4E", "NVHBM", "High Bandwidth Memory"]),

    ("DRAM", "Speicher",
     ["DRAM Preis", "DRAM Kontraktpreis", "DDR5 Preis", "DRAM contract price"],
     ["DRAM", "DDR4", "DDR5", "DDR3", "LPDDR", "Arbeitsspeicher", "RAM-Preis",
      "RAM-Preise", "Speicherpreis", "Speicherpreise"]),

    ("NAND", "Speicher",
     ["NAND Preis", "NAND Flash Nachfrage", "eSSD Nachfrage", "NAND fab"],
     ["NAND", "SSD-Preis", "SSD-Preise", "eSSD", "3D NAND", "Flash-Speicher",
      "NAND flash"]),

    ("CoWoS", "Packaging",
     ["CoWoS", "CoWoS Kapazitaet", "CoWoS capacity TSMC",
      "TSMC advanced packaging capacity", "SoIC TSMC", "Amkor advanced packaging",
      "ASE advanced packaging", "panel level packaging"],
     ["CoWoS", "CoWoS-L", "CoWoS-S", "CoWoS-R", "SoIC", "InFO",
      "Chip-on-Wafer", "advanced packaging", "Advanced Packaging",
      "Fan-Out", "fan-out", "Panel Level Packaging", "panel-level",
      "2.5D packaging", "3D-Stacking", "Interposer", "interposer"]),

    ("Rechenzentrum-Strom", "Energie",
     ["Rechenzentrum Netzanschluss", "data center power constraint",
      "data center grid connection", "Rechenzentrum Stromversorgung"],
     ["Netzanschluss", "Rechenzentrum", "Rechenzentren", "Stromnetz",
      "data center power", "grid connection", "power constraint", "Gigawatt",
      "Umspannwerk", "Netzkapazitaet", "Netzkapazität"]),

    ("NVIDIA-Architektur", "Silizium",
     ["Rubin GPU", "Vera Rubin", "Blackwell Ultra", "Feynman GPU", "Rubin CPX"],
     ["Rubin", "Vera Rubin", "Blackwell", "Feynman", "Grace Hopper", "GB200",
      "GB300", "VR200", "NVL72", "NVL576", "Kyber", "NVLink"]),

    ("Exportkontrolle", "Politik",
     ["Chip Exportkontrolle China", "semiconductor export restriction",
      "chip export ban", "Entity List semiconductor"],
     ["Exportkontrolle", "Exportbeschraenkung", "Exportbeschränkung",
      "export control", "export restriction", "export ban", "Entity List",
      "Sanktion", "Sanktionen", "sanctions", "Ausfuhrbeschraenkung",
      "tariff", "Zoelle", "Zölle"]),
]


def lade(pfad_oder_none, url):
    if pfad_oder_none:
        return Path(pfad_oder_none).read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def firmen_aus_oekosystem(h):
    """Der JSON-Block id="daten" traegt alle 66 Firmen samt Rolle und CIK."""
    i = h.index('id="daten"')
    s = h.index(">", i) + 1
    e = h.index("</script>", s)
    D = json.loads(h[s:e])
    F = D["firmen"]

    # Schicht aus der Reihenfolge zuordnen.
    schicht_je_index = []
    for name, n in SCHICHTEN:
        schicht_je_index += [name] * n

    raus = []
    for i, (tic, v) in enumerate(F.items()):
        raus.append({
            "id": tic,
            "name": v.get("name", tic),
            "rolle": v.get("rolle", ""),
            "schicht": schicht_je_index[i] if i < len(schicht_je_index) else "?",
            "cik": v.get("cik") or None,
            "boerse": v.get("boerse"),
            "stufe": 1,
            "art": "boersennotiert",
        })
    return raus, D.get("stand")


def cluster_und_firmen_aus_cases(h):
    """CLUSTERS liefert die 15 Cluster, UC die Anwendungen samt Firmennennungen."""
    cl = []
    for m in re.finditer(
            r'\{n:(\d+),\s*cat:"(\w+)".*?title:\{en:"(.*?)",de:"(.*?)"\}', h, re.S):
        cl.append({"n": int(m.group(1)), "kategorie": m.group(2),
                   "titel_de": m.group(4), "titel_en": m.group(3)})

    # Firmennennungen je Cluster: U(<cluster>, "<firmen>", "<reife>", ...
    nennung = {}
    for m in re.finditer(r'U\(\s*(\d+)\s*,\s*"(.*?)"\s*,\s*"(\w+)"', h):
        n, firmen, reife = int(m.group(1)), m.group(2), m.group(3)
        for f in firmen.split(","):
            f = f.strip().rstrip(")").strip()
            if not f or len(f) < 2:
                continue
            e = nennung.setdefault(f, {"cluster": set(), "reife": set()})
            e["cluster"].add(n)
            e["reife"].add(reife)
    return cl, nennung


def hashtag(s):
    """Stabiler Hashtag aus einem Namen - deterministisch, damit er sich
    zwischen zwei Laeufen nicht aendert."""
    t = (s.replace("&", " und ").replace("ä", "ae").replace("ö", "oe")
          .replace("ü", "ue").replace("ß", "ss"))
    t = re.sub(r"[^0-9A-Za-z]+", " ", t).strip()
    teile = [w.capitalize() if w.islower() else w for w in t.split()]
    return "#" + "".join(teile)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quelle-firmen")
    p.add_argument("--quelle-cases")
    p.add_argument("--stufe2-max", type=int, default=45,
                   help="wie viele Anwendungsfirmen aufgenommen werden")
    a = p.parse_args()

    firmen, stand = firmen_aus_oekosystem(lade(a.quelle_firmen, ROH_FIRMEN))
    cluster, nennung = cluster_und_firmen_aus_cases(lade(a.quelle_cases, ROH_CASES))

    bekannt = {f["name"].lower() for f in firmen} | {f["id"].lower() for f in firmen}

    # Anwendungsfirmen: die am haeufigsten genannten, die nicht schon
    # boersennotiert erfasst sind. Haeufig genannt heisst hier: taucht in
    # mehreren Anwendungen auf, ist also kein Einzelfall.
    kandidaten = []
    for name, e in nennung.items():
        if name.lower() in bekannt:
            continue
        if re.search(r"^(AI|the |a )|assisted|program$|^\d", name, re.I):
            continue
        kandidaten.append((len(e["cluster"]), name, sorted(e["cluster"]),
                           sorted(e["reife"])))
    kandidaten.sort(key=lambda x: (-x[0], x[1]))

    anwendung = []
    for _, name, cl, reife in kandidaten[:a.stufe2_max]:
        anwendung.append({
            "id": re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").upper()[:24],
            "name": name, "rolle": "", "schicht": "Anwendung",
            "cluster": cl, "reife": reife, "stufe": 2, "art": "anwendung",
        })

    labore = [{"id": re.sub(r"[^0-9A-Za-z]+", "_", n).upper(), "name": n,
               "rolle": r, "schicht": s, "stufe": 1, "art": "privat"}
              for n, s, r in LABORE]

    eintraege = firmen + labore + anwendung
    for e in eintraege:
        e["hashtag"] = hashtag(e["name"])

    themen = [{"id": re.sub(r"[^0-9A-Za-z]+", "_", n).upper(), "name": n,
               "schicht": s, "suchen": q, "stichworte": w, "stufe": 1,
               "art": "thema", "hashtag": hashtag(n)} for n, s, q, w in THEMEN]

    aus = {
        "erzeugt": date.today().isoformat(),
        "quellen": {
            "firmen": "mendeltem/AI_Companys - nvidia-oekosystem.html",
            "firmen_stand": stand,
            "anwendungen": "mendeltem/ai_use_cases_overview - index.html",
        },
        "cluster": cluster,
        "beobachtet": eintraege + themen,
    }
    ZIEL.write_text(json.dumps(aus, ensure_ascii=False, indent=1), encoding="utf-8")

    n1 = sum(1 for e in aus["beobachtet"] if e["stufe"] == 1)
    print("themen.json geschrieben: %d Eintraege (%d Kern, %d Anwendung), %d Cluster"
          % (len(aus["beobachtet"]), n1, len(aus["beobachtet"]) - n1, len(cluster)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
