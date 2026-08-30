# archiv

Zwei Formate nebeneinander, weil sie zwei verschiedene Fragen beantworten.

## `JJJJ-MM-TT.json` — Momentaufnahme

Wie der Feed an genau diesem Tag aussah, samt Gewichtung und Reihenfolge.
Eine Meldung, die an fünf Tagen im Fenster lag, steht in fünf Dateien.
Gut zum Nachvollziehen, schlecht als Datensatz.

## `korpus.jsonl` — der Datensatz

Eine Zeile je Meldung, die es je gab, **genau einmal**. Wird nur angehängt,
nie umgeschrieben. Das ist das Format für Auswertung und Modelldaten.

```python
import pandas as pd
df = pd.read_json("archiv/korpus.jsonl", lines=True)

df[~df.rauschen]                                  # ohne Anlegertipp-Rauschen
df.explode("hashtags").hashtags.value_counts()    # welches Thema wie oft
df[df.hashtags.apply(lambda h: "#CoWoS" in h)]    # ein Thema über die Zeit
df.groupby("erstgesehen").size()                  # Meldungen je Tag
```

| Feld | |
|---|---|
| `id` | Hash des normalisierten Titels, stabil über alle Läufe |
| `erstgesehen` | Tag des ersten Auftauchens — die Achse für Zeitreihen |
| `datum` | Veröffentlichung laut Quelle, ISO 8601, kann fehlen |
| `titel` | Originalschlagzeile |
| `zeile` | deutsche Fassung, `null` wenn das Modell aus war |
| `quelle` | Publikation |
| `link` | Google-News-Weiterleitung |
| `bezug` | IDs der beobachteten Einträge, die im Titel vorkommen |
| `hashtags` | dieselben Einträge als Hashtag |
| `gewicht` | Sortierwert des Sammellaufs |
| `rauschen` | `true` = Anlegertipp-Quelle oder Kursmeldung ohne Nachricht |

## Vorbehalte für die Auswertung

- **`erstgesehen` ist nicht das Erscheinungsdatum.** Es ist der Tag, an dem der
  Lauf die Meldung zuerst sah. Fällt ein Lauf aus, verschiebt sich das.
- **Der Korpus beginnt am 30.08.2026.** Alles davor fehlt.
- **`rauschen` ist eine Heuristik**, keine Wahrheit — Quellenliste plus
  Titelmuster. Rund 30 % der Rohtreffer werden so markiert.
- **Vollständigkeit ist nicht behauptet.** Die Auswahl trifft Google News.
- **Titel bis 30.08.2026 tragen fehlerhafte `bezug`-Werte** bei den Themen
  CoWoS, Exportkontrolle und Rechenzentrum-Strom: die Stichwortprüfung nahm
  damals das erste Wort des Suchbegriffs, also `Advanced`, `semiconductor`
  und `data`. Ab dem 30.08.2026 nachmittags ist das behoben.

`gesehen.json` ist kein Datensatz, sondern das Kurzzeitgedächtnis des
Sammellaufs zum Entdoppeln — 60 Tage, dann fällt es raus.
