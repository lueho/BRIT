# BRIT-EU: reproduzierbare R-Analysen und Live-Datenzugang

Dieses Paket enthält die ursprünglichen Fallstudienanalysen als ausführbare R-Skripte, einen festen Datenstand und einen R-Client für die BRIT-Analyse-API. Die statistischen Verfahren können im Quelltext angepasst werden.

## 1. Die ursprünglichen Analysen ausführen

**Voraussetzungen:** R 4.3.3 (Paketversion von Ubuntu 24.04 LTS) und Internetzugang zur erstmaligen Installation der in `renv.lock` festgelegten Pakete. Unter Windows/macOS werden verfügbare Binärpakete verwendet. Unter Linux können Systembibliotheken und Compiler erforderlich sein; der unten beschriebene Docker-Weg enthält diese bereits.

Auf Ubuntu 24.04 können die benötigten Systempakete so installiert werden (falls sie noch fehlen):

```sh
sudo apt update
sudo apt install r-base r-base-dev libcurl4-openssl-dev libssl-dev libxml2-dev \
  libfontconfig1-dev libfreetype6-dev libharfbuzz-dev libfribidi-dev \
  libpng-dev libtiff-dev libjpeg-dev libgit2-dev libx11-dev cmake make g++ gfortran \
  pandoc fonts-dejavu-core
```

Das **vollständige Release-ZIP** entpacken. Es enthält acht Rohdateien unter `data/raw/` und den archivierten, bereinigten Katalonien-Analysestand unter `data/reference/`. Die Version aus dem BRIT-Git-Repository enthält aus Gründen der getrennten Datenbereitstellung nur Code und das Datenmanifest.

Im Paketordner:

```sh
Rscript --vanilla setup.R
Rscript run.R
```

Alternativ `BRIT.Rproj` in RStudio öffnen, einmal `source("setup.R")` und danach `source("run.R")` ausführen. Die erstmalige Installation kann unter Linux wegen der Quellcodekompilierung deutlich länger dauern. Anschließend benötigen die historischen Analysen keinen BRIT-Server und keinen API-Schlüssel.

Einzelne Fallstudie:

```sh
Rscript run.R --case=nrw
Rscript run.R --case=catalonia
```

Weitere Namen: `rlp`, `sweden`, `south_tyrol`, `rlp_bw`. Bei Katalonien wird der notwendige Verarbeitungsschritt für die Störstoffdaten automatisch zuerst ausgeführt. Alle Fälle zusammen werden ebenfalls in der richtigen Reihenfolge gestartet.

Ergebnisse:

- `results/figures/`: PNG-Abbildungen sowie PDF-Sammlung je Skript.
- `results/logs/`: Ausgaben und statistische Ergebnisse je Analyse.
- `results/objects/`: RDS mit allen erzeugten Analyseobjekten, Tabellen und Modellen. Beispiel: `objects <- readRDS("results/objects/nrw.rds"); names(objects)`.
- `results/session-info.txt`: tatsächlich verwendete R- und Paketversionen.
- `results/input-provenance.json`: Datenrelease, gewählte Katalonien-Variante, Prüfsummen des Auswertungscodes und Kennzeichnung eigener Datenänderungen.

## 2. Vollständig definierte Laufzeit mit Docker

Der Dockerfile verwendet ein über seinen Digest fixiertes Ubuntu-24.04-Image, installiert daraus R 4.3.3 und die Analysepakete aus dem festen CRAN-Stand vom 15.04.2024. Beim Bau werden alle installierten Versionen gegen `renv.lock` geprüft. Für die Nutzung unter Ubuntu 24.04 kann auch das Paket `r-base` aus den regulären Ubuntu-Paketquellen verwendet werden; danach genügt `Rscript --vanilla setup.R` im entpackten Projektordner.

```sh
docker build -t brit-eu-r .
docker run --rm -v "$PWD:/analysis" brit-eu-r run.R
```

Unter PowerShell entspricht die zweite Zeile:

```powershell
docker run --rm -v "${PWD}:/analysis" brit-eu-r run.R
```

Auf Linux kann `--user "$(id -u):$(id -g)"` hinzugefügt werden, damit Ausgaben dem eigenen Benutzer gehören. Installation und Nutzung greifen nicht auf eine BRIT-Datenbank zu. Das Image wird lokal gebaut; es wird kein vorexistierendes privates Image vorausgesetzt.

## 3. Datenstand und Reproduzierbarkeit

`data/manifest.json` beschreibt Release `brit-eu-2024-report-2026-09-22`: die neun bereitgestellten Eingabedateien mit Dateiname, SHA-256, Zeilenanzahl, Spalten und Zeichencodierung. Die Dateien bleiben bytegleich zu den gelieferten Projektdateien. Der Runner kontrolliert die Prüfsummen vor jeder Auswertung. Der Release ist **kein nachträglich rekonstruierter Datenbankstand zum Förderende**, sondern der archivierte Eingabestand der Fallstudienskripte mit Bezugsjahr 2024.

Verarbeitungsergebnisse für Katalonien und Rheinland-Pfalz werden aus den Rohdaten neu erzeugt. Bei Katalonien verwendet die statistische Auswertung standardmäßig den zusätzlich archivierten, bereinigten Analysestand. Dieser enthält 454 Zellabweichungen gegenüber der Neuberechnung, darunter manuell ausgeschlossene Mengenwerte und Systemangaben. Die Bereinigung ist im gelieferten Vorbereitungsskript nicht vollständig abgebildet. Für die ursprüngliche Auswertung bleibt deshalb dieser tatsächlich verwendete Eingang verbindlich.

Mit `Rscript run.R --case=catalonia --rebuild-catalonia` lässt sich stattdessen der neu erzeugte Stand auswerten. Dies ist eine **abweichende Datenvariante** und wird in der Provenienz festgehalten; ihre Ergebnisse dürfen nicht ungeprüft den veröffentlichten Factsheets zugeordnet werden. Der neue Zwischenstand wird als UTF-8-BOM eingelesen, das Archivoriginal unverändert als Windows-1252. Vorhandene Ergebnisdateien aus früheren Läufen werden nicht benötigt. Schriftarten sind plattformneutral (`sans`); dadurch können sich Schriftbild und Bilddateien von den ursprünglichen Windows-Grafiken unterscheiden, ohne die statistischen Verfahren zu verändern.

Für eigene Daten eine Kopie des Pakets anlegen und die Spaltenkonventionen beibehalten. Bewusste Änderungen an den Eingangsdaten lassen sich mit `Rscript run.R --allow-custom-data` ausführen; sie werden als eigene Analyse protokolliert. Änderungen an Filtern, Modellen, Tests und Grafiken erfolgen direkt in `scripts/*.R`; gemeinsame Statistikfunktionen stehen in `R/helpers.R`.

## 4. Aktuelle BRIT-Daten über die Live-API

Die neue API muss auf der angesprochenen BRIT-Instanz bereitgestellt sein:

```text
GET /waste_collection/api/collection/analysis/
```

Sie liefert flache Datensätze einschließlich stabiler IDs, Quellenangaben, zeitlicher Gültigkeit, Regionsmerkmalen und verfügbaren Jahreswerten mit Einheiten. Der öffentliche Zugriff liefert ausschließlich freigegebene Daten. Nicht öffentliche Daten benötigen ein BRIT-Token und die entsprechenden bestehenden Berechtigungen.

```r
source("R/brit_api.R")
collections <- brit_collections(
  base_url = "https://brit.bioresource-tools.net",
  filters = list(scope = "published", catchment = 123, valid_on = "2024-12-31")
)
# 123 ist ein Beispiel: durch die tatsächliche Sammelgebiets-ID ersetzen.
names(collections)
brit_save_snapshot(collections, "results/my-analysis/input.rds")
# Später exakt dieselben Daten verwenden, ohne erneuten Live-Abruf:
collections <- brit_read_snapshot("results/my-analysis/input.rds")
```

Oder `live.R` öffnen, dessen Filter anpassen und mit `Rscript live.R` ausführen. Die Serveradresse kann durch `BRIT_API_URL` geändert werden. Für geschützte Daten `BRIT_API_TOKEN` ausschließlich in der lokalen Umgebung setzen; Tokens nicht in Skripten, Protokollen oder veröffentlichten Dateien speichern.

Unterstützte Filter entsprechen BRIT, unter anderem `id`, `catchment`, `collector`, `waste_category`, `collection_system`, `participation_policy`, `fee_system`, `valid_on` und `scope`. Referenzfilter erwarten IDs, keine Regionsnamen. `valid_on` wählt die gültige Sammlungsversion; Jahreswerte heißen beispielsweise `specific_waste_collected_2024` mit zugehöriger Spalte `specific_waste_collected_2024_unit`.

Der Client lädt automatisch alle Seiten, prüft Schemaversion, Gesamtzahl und doppelte IDs und verhindert bei Pagination einen Wechsel auf einen anderen Server. Nullwerte bleiben erhalten, fehlende Spalten werden ergänzt, Gebietskennungen bleiben Zeichenketten. Ein Live-Abruf über mehrere Seiten ist keine Datenbanktransaktion: Änderungen während des Abrufs können den Stand verändern. Für Publikationen den abgerufenen Bestand mit Code und Metadaten archivieren; die Prüfsumme sichert spätere Wiederverwendung.

**Die Live-Daten werden nicht stillschweigend in die historischen Factsheet-Skripte eingesetzt.** Die Fallstudien verwenden ergänzende Zuordnungen, Sortieranalysen und eigene Bezugsgrößen. Eine Übertragung auf neue Daten benötigt diese fachlichen Schritte erneut. `live.R` zeigt deshalb einen eigenständigen, frei anpassbaren Auswertungsweg. Aggregierte Angaben sind nicht ohne Prüfung unabhängige kommunale Beobachtungen; Einheiten und Datenlücken sind vor Berechnungen zu berücksichtigen.

Der API-Code liegt im BRIT-Zweig `feat/reproducible-r-analysis`. Vor dessen Bereitstellung meldet der Client einen eindeutigen HTTP-404-Hinweis; die archivierten Analysen funktionieren unabhängig davon.

## 5. Optionaler Download von einem archivierten Datenrelease

Das vollständige ZIP enthält die Daten bereits. Werden Paket und Datensatz getrennt auf einem HTTPS-Server archiviert, kann `brit_download_release("https://example.org/releases/brit-eu-2024", ".")` das dortige `data/manifest.json` und die zugehörigen Dateien herunterladen und die Prüfsummen kontrollieren. Den Beispiel-URL durch die tatsächlich veröffentlichte Adresse ersetzen. Es wird kein nicht vorhandener öffentlicher Daten-URL vorausgesetzt.

## 6. Herkunft und Weitergabe

Die Ausgangsskripte und Projektdateien stammen aus dem bereitgestellten BRIT-EU-R-Projekt des Verbunds (TUHH/ECN). Änderungen dieses Pakets betreffen Ausführbarkeit, Datenzugang, Prüfsummen, Pfade, Schriften und Codierung; methodische Befunde und Korrekturen aus den Testläufen werden in `VALIDIERUNG.md` dokumentiert. Die Softwarelizenz von BRIT ersetzt keine Freigabe der zugrunde liegenden Daten. Öffentliche Archivierung und Datenlizenzen sind entsprechend der Bericht-Prüfliste O09 festzulegen.

Technische Grundlagen: [renv wiederherstellen](https://rstudio.github.io/renv/reference/restore.html), [R-Projekt](https://www.r-project.org/).
