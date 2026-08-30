@echo off
REM Taeglicher Lauf um 06:00, angestossen von der Aufgabenplanung.
REM Von Hand aufrufen geht genauso - der Lauf merkt sich, was er schon hatte.
REM
REM   1. sammeln.py    Nachrichten zu allen beobachteten Eintraegen holen
REM   2. schreiben.py  lokales Modell: eindeutschen und Lage schreiben
REM   3. committen und pushen
REM
REM Faellt Schritt 2 aus (Modell nicht erreichbar, Code 2), wird trotzdem
REM gepusht - der Feed steht dann ohne deutsche Zeilen, aber er steht.
REM Protokoll: lauf.log im Repo.

setlocal
set WURZEL=%~dp0..
cd /d "%WURZEL%"

echo. >> lauf.log
echo ===== %DATE% %TIME% ===== >> lauf.log

python werkzeuge\sammeln.py >> lauf.log 2>&1
if errorlevel 1 (
  echo Sammeln fehlgeschlagen - Lauf abgebrochen, alter Stand bleibt >> lauf.log
  endlocal
  exit /b 1
)

python werkzeuge\schreiben.py >> lauf.log 2>&1
set SCHREIB=%ERRORLEVEL%
if "%SCHREIB%"=="2" echo Modell war aus - Feed ohne deutsche Zeilen >> lauf.log

git add -A nachrichten.json themen.json archiv artikel analyse lauf.log >> lauf.log 2>&1
git diff --cached --quiet
if errorlevel 1 (
  git commit -q -m "Stand %DATE%" >> lauf.log 2>&1
  git push -q >> lauf.log 2>&1
  echo Gepusht >> lauf.log
) else (
  echo Nichts geaendert >> lauf.log
)

echo Beendet mit %SCHREIB% >> lauf.log
endlocal
