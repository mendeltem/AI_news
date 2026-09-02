@echo off
REM Taeglicher Lauf um 06:00, angestossen von der Aufgabenplanung.
REM Von Hand aufrufen geht genauso - der Lauf merkt sich, was er schon hatte.
REM
REM   0. pruefen.py    Selbsttest der Zuordnung - schlaegt er an, bricht der Lauf ab
REM   1. sammeln.py    Nachrichten zu allen beobachteten Eintraegen holen
REM   2. schreiben.py  lokales Modell: eindeutschen und Lage schreiben
REM   3. bewerten.py   Richtung je Meldung: Rueckenwind, Gegenwind, unbestimmt
REM   4. lernfilter.py Relevanz je Meldung, trainiert aus urteile.json
REM   5. archivieren.py  Tagesstand in archiv/korpus.jsonl fortschreiben
REM   6. committen und pushen, mit drei Versuchen
REM
REM Rueckgabewerte:
REM   0  fertig und gepusht
REM   1  Sammeln fehlgeschlagen, alter Stand bleibt stehen
REM   2  Modell war aus - gepusht, aber ohne deutsche Zeilen
REM   3  Push fehlgeschlagen - Commit liegt lokal, naechster Lauf schiebt nach
REM   4  Selbsttest gescheitert - nichts angefasst
REM
REM Protokoll: lauf.log (steht nicht im Repo, siehe .gitignore)

setlocal
set WURZEL=%~dp0..
cd /d "%WURZEL%"

echo. >> lauf.log
echo ===== %DATE% %TIME% ===== >> lauf.log

python werkzeuge\pruefen.py >> lauf.log 2>&1
if errorlevel 1 (
  echo FEHLER Selbsttest - Lauf abgebrochen, es wird nichts veroeffentlicht >> lauf.log
  exit /b 4
)

python werkzeuge\sammeln.py >> lauf.log 2>&1
if errorlevel 1 (
  echo FEHLER Sammeln - abgebrochen, alter Stand bleibt >> lauf.log
  exit /b 1
)

python werkzeuge\schreiben.py >> lauf.log 2>&1
set SCHREIB=%ERRORLEVEL%
if "%SCHREIB%"=="2" echo HINWEIS Modell war aus - Feed ohne deutsche Zeilen >> lauf.log

python werkzeuge\bewerten.py >> lauf.log 2>&1

REM Meldungen, die dieselbe Geschichte erzaehlen, zu einer Karte
REM zusammenfassen. Das alte Entdoppeln traf nur woertliche Wiederholungen -
REM ueber Redaktions- und Sprachgrenzen hinweg stand dieselbe Nachricht
REM achtmal untereinander.
python werkzeuge\gruppieren.py >> lauf.log 2>&1

REM Der Lernfilter schreibt seine Einschaetzung an jede Meldung. Die Seite
REM raeumt weg, was er und die Regeln fuer unwichtig halten - aber nur aus der
REM Ansicht: ein Klick blendet alles wieder ein, samt Begruendung. Bei rund 85
REM Prozent Genauigkeit ist etwa jede siebte Aussortierung falsch, deshalb
REM wegraeumen statt loeschen.
REM
REM Er trainiert bei jedem Lauf neu aus urteile.json - was gestern sortiert
REM wurde, wirkt heute. Scheitert er, ist das kein Grund zum Abbruch: dann
REM fehlt nur das Feld und die Seite zeigt wieder alles.
python werkzeuge\lernfilter.py anwenden >> lauf.log 2>&1

REM Welche der eigenen Urteile dem Modell verdaechtig sind. Dreht nichts um,
REM legt sie nur unter "nochmal ansehen" wieder auf den Stapel.
python werkzeuge\lernfilter.py zweifel >> lauf.log 2>&1

python werkzeuge\archivieren.py >> lauf.log 2>&1

git add -A nachrichten.json themen.json archiv artikel analyse ^
        korrekturen.json urteile.json zweifel.json >> lauf.log 2>&1
git diff --cached --quiet
if not errorlevel 1 (
  echo Nichts geaendert - kein Commit >> lauf.log
  exit /b %SCHREIB%
)

git commit -q -m "Stand %DATE%" >> lauf.log 2>&1

REM Der Push kann an einem DNS-Aussetzer scheitern. Dreimal versuchen - und
REM wenn es dann immer noch nicht geht, das auch sagen. Ein stiller Fehlschlag
REM hier heisst, die Seite steht tagelang still, ohne dass es auffaellt.
call :push && goto :gepusht
timeout /t 20 /nobreak >nul
call :push && goto :gepusht
timeout /t 30 /nobreak >nul
call :push && goto :gepusht

echo FEHLER Push nach drei Versuchen - Commit liegt lokal, >> lauf.log
echo        der naechste Lauf schiebt ihn mit nach >> lauf.log
exit /b 3

:gepusht
echo Gepusht >> lauf.log
exit /b %SCHREIB%

:push
git push -q >> lauf.log 2>&1
exit /b %ERRORLEVEL%
