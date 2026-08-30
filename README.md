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
| `werkzeuge/saat.py` | erzeugt `themen.json` neu aus den Schwesterseiten |
| `werkzeuge/sammeln.py` | der Sammellauf |
| `werkzeuge/schreiben.py` | der Modell-Lauf |
| `werkzeuge/taeglich.cmd` | was die Aufgabenplanung startet |

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
