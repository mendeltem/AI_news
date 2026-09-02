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
| `werkzeuge/bewerten.py` | Richtung je Meldung, per Signalwort |
| `sortieren.html` | Meldungen selbst wischen, zwei Achsen |
| `werkzeuge/einpflegen.py` | pflegt die gewischten Urteile ein |
| `werkzeuge/lernfilter.py` | lernt aus den Urteilen, läuft im Schattenbetrieb |
| `werkzeuge/auswerten.py` | sucht die Regel hinter den Handurteilen |
| `urteile.json` | alle Urteile beider Achsen, der Datensatz |
| `korrekturen.json` | Redaktionskorrekturen der Richtung — der Lernteil |
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

## Rückenwind oder Gegenwind

Oben auf der Seite steht ein Zeiger zwischen **Gegenwind** und **Rückenwind**.
Der Standpunkt ist festgelegt und steht daneben:

> Erleichtert die Meldung den Ausbau von KI-Rechenzentren oder erschwert sie ihn?

Ohne festen Standpunkt ist „gut" und „schlecht" bedeutungslos. Steigende
DRAM-Preise sind gut für Micron, schlecht für Nvidias Stückkosten und schlecht
für den PC-Käufer. Erst der Standpunkt macht das Etikett prüfbar — und nur ein
prüfbares Etikett taugt später als Lernmaterial.

### Warum kein Sprachmodell

Der naheliegende Weg wäre, das lokale Modell klassifizieren zu lassen. Gemessen
am 30.08.2026 auf dieser Maschine:

| | |
|---|---|
| Geschwindigkeit | 27–65 s je Meldung, Decode 0,3–0,8 t/s statt 19 |
| Ergebnis | „neutral" für einen Streik, für 31 Mrd. Investition, für +50 % Preise |

Ein Streik ist kein neutrales Ereignis. Bewerten heißt urteilen, und genau davon
rät die Anleitung zum lokalen Modell ab. Deshalb entscheidet eine Liste von
Signalwörtern — und das ist hier nicht der Notbehelf, sondern die bessere
Lösung:

- **nachvollziehbar** — das gefundene Signalwort *ist* die Begründung, sie steht
  unter jeder Meldung
- **reproduzierbar** — zweimal derselbe Titel, zweimal dasselbe Etikett
- **korrigierbar** — ein falsches Signalwort sieht man und ändert es
- **schnell** — Millisekunden statt einer halben Minute

Was kein Signalwort trifft, bleibt **unbestimmt**. Raten wäre schlechter als
zugeben, dass es unklar ist — derzeit sind rund 80 % unbestimmt. Die Liste
wächst mit:

```bash
python werkzeuge/bewerten.py --zeige-unbestimmt
```

Ein Dementi kippt die Aussage nicht um, sondern auf unbestimmt: „SK hynix
dementiert Intel-Deal" ist kein Rückenwind, nur weil „Deal" darin vorkommt.

### Der Lernteil

Jede Bewertung speichert, welches Signalwort sie ausgelöst hat. In
`korrekturen.json` überschreibt die Redaktion einzelne Etiketten samt Grund:

```json
{"a1b2c3d4e5f6g7h8": {"richtung": "gegenwind",
                      "grund": "Rekordauftrag ist hier Folge der Knappheit"}}
```

Beides landet im Korpus (`wind`, `wind_grund`, `wind_quelle`). Daraus entsteht
ein Datensatz aus Titel, Etikett, Begründung und der Angabe, wer entschieden
hat — das Material, aus dem sich später lernen lässt, *warum* etwas Rückenwind
ist. Redaktionskorrekturen sind dabei die wertvollen Zeilen: sie markieren genau
die Fälle, in denen die Regel danebenlag.

## Selbst sortieren

**[sortieren.html](https://mendeltem.github.io/AI_news/sortieren.html)** legt die
Meldungen einzeln als Karte vor: nach links wischen, nach rechts, oder
Pfeiltasten. Zwei Achsen, umschaltbar:

| Achse | ← links | → rechts | ↓ unten |
|---|---|---|---|
| Richtung | Gegenwind | Rückenwind | unbestimmt |
| Wichtigkeit | unwichtig | wichtig | unklar |

Nach jedem Urteil erscheint, **was die Automatik gesagt hätte** — und ob ihr
auseinandergeht. Beide Achsen haben eine Automatik zum Vergleich: die Richtung
aus den Signalwörtern, die Wichtigkeit aus Gewicht und Rauschmarke.

Die Abweichungen sind der Ertrag. Wo Mensch und Regel dasselbe sagen, lernt man
nichts.

### Der Weg zurück ins Repo

GitHub Pages ist statisch — die Seite kann nicht ins Repo schreiben, und ein
Zugangstoken im Quelltext wäre die falsche Lösung für das richtige Problem.
Also über eine Datei:

```bash
python werkzeuge/einpflegen.py urteile-2026-09-01.json
```

Der Lauf listet die Abweichungen auf. Die **Richtung** wirkt sofort zurück, sie
landet in `korrekturen.json` und schlägt ab dem nächsten Lauf die Automatik. Die
**Wichtigkeit** wird gesammelt (`urteile.json`), aber noch nicht angewandt —
dafür braucht es erst genug Urteile, um zu prüfen, ob sich daraus überhaupt eine
Regel ableiten lässt.

`--trocken` zeigt, was passieren würde, ohne zu schreiben.

## Der Lernfilter

`werkzeuge/lernfilter.py` lernt aus den sortierten Urteilen, was wichtig ist —
Naive Bayes über Titelwörter, Quelle und ein paar Zählmerkmale. Kein Fremdpaket,
und jede Entscheidung lässt sich in ihre Bestandteile zerlegen:

```
DELL, HPE Stocks Draw Focus Ahead Of Earnings This Week
  -> unwichtig  (Sicherheit 100%)
  spricht dafuer:
    w:stocks    +3.15    w:earnings  +2.98    w:dell  +2.98
```

Das ist keine Kosmetik: ein Filter, der nicht sagen kann, warum er etwas
wegwirft, ist nicht korrigierbar.

### Die wichtigste Zahl ist nicht die Trefferquote

Ein Modell, das auf seinen eigenen Trainingsdaten geprüft wird, hat immer recht.
Deshalb misst `pruefen` mit Kreuzvalidierung und vergleicht gegen zwei
Messlatten. Stand 02.09.2026 mit 109 Urteilen:

| | |
|---|---|
| immer „wichtig" raten | 64 % |
| handgeschriebene Regeln | 84 % |
| **das Modell** | **85 %** auf 86 % der Fälle |

**Urteil: nicht einsetzen.** 85 gegen 84 Prozent ist Rauschen, kein Fortschritt.
Ein Filter, der falsch aussortiert, kostet mehr als keiner. Das Werkzeug sagt
das selbst und endet mit Rückgabewert 2.

### Warum mehr Sortieren allein nicht hilft

```bash
python werkzeuge/lernfilter.py pruefen --kurve
```

| Beispiele | Genauigkeit |
|---|---|
| 40 | 86 % |
| 60 | 87 % |
| 80 | 86 % |
| 109 | 86 % |

Flach. Der Engpass ist nicht die Menge der Urteile, sondern das Material: aus
Titelwörtern ist herausgeholt, was drin ist. Was hilft, sind die Fälle, bei
denen das Modell **unsicher** ist — dort steckt die Information.

### Etiketten sind selbst fehlerbehaftet

Selbstauskunft beim Sortieren: *„manchmal mache ich nicht alles korrekt, weil zu
viel Aktien-Blabla."* Beim schnellen Durchwischen langer Strecken Börsenrauschen
rutscht etwas in die falsche Richtung. Das ist normal — aber ein Lernfilter, der
jedes Etikett für Wahrheit hält, übernimmt diese Ausrutscher.

Zwei Antworten darauf:

**Strukturell.** Die 22 Aktien-Meldungen, die den Rhythmus erzeugt haben, fängt
`MARKTGEPLAUDER` jetzt vorher ab. Sie werden gar nicht mehr vorgelegt.

**Prüfend.** `lernfilter.py zweifel` sucht Urteile, denen ein Modell *das sie
nicht gesehen hat* mit über 90 % Sicherheit widerspricht:

```
du: unwichtig   Modell: wichtig (96%)
    TSMC packaging shift could boost AMD CoWoS share and trim Nvidia's allocation
```

Das ist **Verdacht, keine Feststellung** — ein Modell mit 85 % Genauigkeit irrt
in jedem siebten Fall selbst. Nichts wird automatisch gedreht. Die Fälle landen
in `zweifel.json` und auf `sortieren.html` unter *„nochmal ansehen"*, wo die
bestehende Beurteilung ausnahmsweise sichtbar bleibt.

### Wegwerfen, aber umkehrbar

Der Feed blendet aus, was Regeln oder Lernfilter für unwichtig halten. Die
Zählzeile nennt die Zahl, ein Klick auf **„Aussortiertes zeigen"** holt alles
zurück, und an jeder Meldung steht, wer sie aussortiert hat und mit welcher
Sicherheit.

Das ist der Kompromiss: wegräumen ja, löschen nein. Bei 85 % Genauigkeit ist
ungefähr jede siebte Aussortierung falsch — wer das nicht nachprüfen kann,
merkt es nie.

### Der Weg zur Automatisierung

1. **Schattenbetrieb** (läuft bereits): Der Lernfilter schätzt jede Meldung ein,
   gefiltert wird nichts. Aktuell 818 wichtig, 3761 unwichtig, **1702
   Enthaltungen**.
2. **Gezielt sortieren**: auf `sortieren.html` die Auswahl *„wo das Modell
   unsicher ist"* — das sind genau jene 1702.
3. **Erneut prüfen**: `lernfilter.py pruefen`. Erst wenn der Rückgabewert 0 ist
   *und* die Genauigkeit spürbar über den Regeln liegt, gehört er in den Weg.

Bis dahin bleibt er ein Beobachter. Das ist die ganze Absicherung: er darf
mitschreiben, aber nichts wegwerfen.

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
