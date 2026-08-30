# AI_news — KI-Lagemeldung

Täglicher Nachrichtenstand entlang der KI-Lieferkette.
**[Zur Seite →](https://mendeltem.github.io/AI_news/AI_new.html)**

Beobachtet werden **125 Einträge**: die 66 börsennotierten Firmen der
Nvidia-Kette, sieben private KI-Labore, 45 Anwendungsfirmen aus den Use-Cases
und sieben Querschnittsthemen (HBM, DRAM, NAND, CoWoS, Rechenzentrumsstrom,
Nvidia-Architektur, Exportkontrolle).

## Wie sie funktioniert

Derselbe Aufbau wie [wetter](https://github.com/mendeltem/wetter): die Daten
stehen als JSON im Repo, die Seite holt sie sich beim Aufruf selbst. Fällt ein
Lauf aus, weil der Rechner aus war, bleibt der letzte Stand stehen und die Seite
bleibt benutzbar.

Um **6:00** startet die Aufgabenplanung `werkzeuge/taeglich.cmd`:

1. **`sammeln.py`** fragt für jeden beobachteten Eintrag den RSS-Ausgang von
   Google News ab — Kernthemen auf Deutsch *und* Englisch, weil die Substanz zu
   Speicherpreisen bei TrendForce, DigiTimes und Reuters liegt und nie auf
   Deutsch erscheint. Doppelmeldungen werden am normalisierten Titel
   zusammengelegt, jede Meldung bekommt Hashtags aus den Einträgen, die
   tatsächlich in ihr vorkommen.
2. **`schreiben.py`** lässt das lokale Modell die englischen Schlagzeilen
   eindeutschen und die Lage schreiben.
3. Committen und pushen.

Der Lauf merkt sich in `archiv/gesehen.json`, was er schon hatte — ein zweiter
Aufruf am selben Tag holt nur Neues.

## Die Arbeitsteilung, und warum es sie gibt

| | schreibt | erkennbar an |
|---|---|---|
| lokales Modell | Übersetzungen, Tageslage | Kürzel **Modell** |
| Redaktion | Einordnung: was das für Nvidia, DRAM und NAND heißt | Kürzel **Redaktion** |

Das ist keine Kosmetik. Lieferketteneffekte herzuleiten — was ein
kundenspezifischer HBM-Base-Die für die Verhandlungsmacht von SK hynix bedeutet
— ist genau die Aufgabe, bei der ein kleines Modell *plausibel falsch* liegt:
die Antwort liest sich richtig und muss teurer nachgeprüft werden, als sie
gekostet hat. Deshalb steht der Analyseteil in `analyse/` und entsteht in einem
eigenen Lauf, nicht um 6 Uhr.

## Rauschfilter

Der wertvollste Teil des Sammlers ist, was er **nicht** nach oben lässt.
Aktientipp-Mühlen und Kursmeldungen ohne Nachricht („Aktie News: X tendiert
schwächer") machen bei den großen Tickern die Mehrheit der Treffer aus. Sie
werden nicht entfernt, aber abgewertet und als *abgewertet* markiert — typisch
sind das 40 % der Rohtreffer.

## Dateien

| | |
|---|---|
| `AI_new.html` | die Seite — eigenständig, holt die JSON-Dateien selbst |
| `themen.json` | die Beobachtungsliste, erzeugt aus den Schwesterseiten |
| `nachrichten.json` | der aktuelle Stand |
| `archiv/JJJJ-MM-TT.json` | jeder Tag einzeln, plus `gesehen.json` fürs Entdoppeln |
| `analyse/` | die Redaktionsartikel, `index.json` listet sie |
| `archiv/korpus.jsonl` | **der Datensatz** — eine Zeile je Meldung, genau einmal |
| `werkzeuge/saat.py` | erzeugt `themen.json` neu aus den Schwesterseiten |
| `werkzeuge/pruefen.py` | Selbsttest der Zuordnung — Torwächter des Laufs |
| `werkzeuge/sammeln.py` | der Sammellauf |
| `werkzeuge/schreiben.py` | der Modell-Lauf |
| `werkzeuge/archivieren.py` | schreibt den Korpus fort |
| `werkzeuge/taeglich.cmd` | was die Aufgabenplanung startet |

`lauf.log` steht bewusst **nicht** im Repo — es wird nach dem Commit
weitergeschrieben und hielte den Arbeitsbaum sonst dauerhaft schmutzig.

Rückgabewerte von `taeglich.cmd`: `0` fertig und gepusht · `1` Sammeln
fehlgeschlagen, alter Stand bleibt · `2` Modell war aus, gepusht ohne deutsche
Zeilen · `3` Push nach drei Versuchen fehlgeschlagen, der Commit liegt lokal und
der nächste Lauf schiebt ihn mit · `4` Selbsttest gescheitert, nichts angefasst.

## Der Selbsttest, und warum es ihn gibt

`werkzeuge/pruefen.py` läuft als **Torwächter** vor jedem Lauf. Schlägt er an,
bricht der Lauf ab und veröffentlicht nichts — ein falsch etikettierter Feed ist
schlimmer als ein alter.

Anlass war ein Fehler, der zweimal hintereinander ausgeliefert wurde und beide
Male richtig aussah. Die Relevanzprüfung leitete ihr Stichwort aus dem
*Suchbegriff* ab, indem sie dessen erstes Wort nahm:

```python
kern = s.split()[0]     # "TSMC advanced packaging capacity"  ->  "TSMC"
```

Damit trug jede TSMC-Meldung `#CoWoS` und jede mit „Chip" `#Exportkontrolle`.
Der Feed war voll, die Hashtags standen dran, sie bezogen sich nur auf nichts.
Aufgefallen ist es erst beim Nachzählen: 23 Meldungen mit `#CoWoS`, davon 0
über CoWoS.

**Der Merksatz:** Der Suchbegriff sagt, wonach gesucht wird. Er sagt nicht,
wovon die gefundene Meldung handelt. `suchen` darf weit sein, `stichworte` muss
eng sein.

Der Test deckt 28 Fälle ab — einen je Fehler, den es schon gab, dazu die Ticker,
die auch normale Wörter sind (`ON`, `NOW`, `ARM`), den Rauschfilter und das
Entdoppeln.

## Zwei Zeitfenster

Firmennachrichten sind Tagesgeschäft, Querschnittsthemen nicht. CoWoS,
NAND-Preise oder Exportregeln bewegen sich im Wochentakt — mit einem gemeinsamen
2-Tage-Fenster sehen genau die strukturellen Themen leer aus, wegen derer die
Seite existiert.

| | Fenster |
|---|---|
| Firmen | 2 Tage |
| Themen | 8 Tage |

Nach der Korrektur der Etiketten hatte CoWoS zunächst **eine** Meldung. Mit dem
breiteren Fenster sind es 21, alle echt.

## Selbst laufen lassen

```bash
python werkzeuge/sammeln.py --nur NVDA,HBM,DRAM,NAND
```

Ohne `--nur` werden alle 125 Einträge abgefragt; das dauert ein paar Minuten.
`--limit N` begrenzt auf die ersten N Einträge, `--tage N` das Zeitfenster.

```bash
python werkzeuge/schreiben.py --max 40
```

Braucht den lokalen `llama-server`. Läuft er nicht, endet der Lauf mit Code 2
und lässt den Feed ohne deutsche Zeilen stehen — die Meldungen selbst brauchen
das Modell nicht. Der lokale Teil stammt aus
[local_models](https://github.com/mendeltem/local_models).

Die Beobachtungsliste neu aus den Schwesterseiten ziehen:

```bash
python werkzeuge/saat.py
```

## Schwesterseiten

- [Nvidia-Ökosystem](https://mendeltem.github.io/AI_Companys/nvidia-oekosystem.html) — 66 Firmen, Quartalszahlen, Bewertung. Liefert die Beobachtungsliste.
- [KI-Use-Cases](https://mendeltem.github.io/ai_use_cases_overview/) — 91 Anwendungen in 15 Clustern. Die Nachfrageseite.
- [Silizium-Roadmap](https://mendeltem.github.io/nvidia-roadmap/) — Ampere bis Feynman.

## Grenzen

Schlagzeilen sind keine Belege. Was hier steht, ist der Stand der
Berichterstattung, nicht der Stand der Dinge. Zahlen aus
Unternehmensmitteilungen sind ungeprüft, und die Google-News-Auswahl ist eine
Blackbox — Vollständigkeit ist nicht behauptet.
