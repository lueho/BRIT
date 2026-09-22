# Validierung des BRIT-EU-Analysepakets

Stand: 22.09.2026. Getestet unter Linux/Ubuntu 24.04 mit R 4.6.1 und den Paketversionen aus `renv.lock`. Windows und macOS wurden nicht separat ausgeführt; für die geprüfte Laufzeit steht der Dockerfile bereit.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Vollständiger Lauf aus einem Paket ohne Ergebnisse und ohne generierte Zwischendaten | Alle sieben Skripte erfolgreich, keine R-Warnungen |
| Katalonien-Rohdatenvariante: `Rscript run.R --case=catalonia --rebuild-catalonia` | Separater vollständiger Lauf erfolgreich; Variante in der Provenienz als `rebuilt_from_raw` markiert |
| Ergebnisdateien | 38 PNG-Abbildungen, sieben PDF-Sammlungen, sieben RDS-Dateien mit Analyseobjekten |
| Originale Eingaben | Acht Rohdateien und ein bereinigter Katalonien-Analysestand, bytegleich zum gelieferten Projekt, SHA-256 im Manifest |
| Normale R-Einrichtung: `Rscript --vanilla setup.R` | Eigene Projektbibliothek erfolgreich wiederhergestellt; anschließend Client-Tests unter aktivierter renv-Umgebung erfolgreich |
| R-Client: `Rscript --vanilla tests/test_client.R` | Erfolgreich: Pagination, Schema, Gebietskennungen, Nullwerte, vollständig fehlende Spalten, wechselnder Server, doppelte IDs, Zählfehler, leerer Bestand und Snapshot-Manipulation |
| HTTP: `Rscript --vanilla tests/test_http.R` mit lokalem Testserver | Erfolgreich: tatsächlicher JSON-Abruf über zwei Seiten, Einheiten, HTTP-404-Hinweis, Download eines Datenrelease mit Prüfsumme |
| Django-API und benachbarte Funktionen | 55 Tests erfolgreich; darunter acht neue Tests des Analyse-Endpunkts |
| BRIT-Codeprüfung | Ruff, Formatprüfung und Prüfung auf fehlende Migrationen erfolgreich |

Der vollständige Lauf wurde mit `docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/analysis" brit-eu-r:2026-09-22 run.R` durchgeführt. Der Image-Build verwendet den mitgelieferten Dockerfile. `results/session-info.txt` dokumentiert die ausgeführte Umgebung; `results/input-provenance.json` enthält Datenvariante und Code-Prüfsummen. Diese Dateien entstehen bei jedem eigenen Lauf neu.

Der erste vollständige BRIT-Prüflauf war einschließlich erreichbarer Datenbank erfolgreich. Der abschließende Lauf mit `--no-up` bestätigte Ruff, Formatierung und fehlende Modelländerungen erneut; seine zusätzliche Prüfung der Datenbank-Migrationshistorie konnte wegen nicht auflösbarem Hostnamen `db` nicht erfolgen. Der zugehörige Warnhinweis bleibt im Prüfprotokoll erhalten. Die 55 Django-Tests wurden zuvor erfolgreich gegen die isolierte Testdatenbank ausgeführt. Es wurden keine Modelle oder Migrationen geändert.

Die Serverprüfung im isolierten BRIT-Zweig verwendete:

```sh
/home/phillipp/projects/BRIT-ops/scripts/brit-worktree-test /home/phillipp/documents/brit-eu-bericht/entwicklung/reproducible-r-analysis --parallel 2 -- sources.waste_collection.tests.test_analysis_api sources.waste_collection.tests.test_viewsets.CollectionViewSetTestCase sources.waste_collection.tests.test_serializers.CollectionFlatSerializerTestCase sources.waste_collection.tests.test_serializers.CollectionFlatSerializerNutsHierarchyTestCase
/home/phillipp/projects/BRIT-ops/scripts/brit-worktree-check /home/phillipp/documents/brit-eu-bericht/entwicklung/reproducible-r-analysis --no-up
```

## Befunde zu den ursprünglichen Analysen

- Absolute Windows-Pfade im RLP/Baden-Württemberg-Skript wurden durch Paketpfade ersetzt. Verzeichnisstruktur und Ausführungsreihenfolge werden automatisch hergestellt. Eine zusätzliche, nicht im Lockfile enthaltene Abhängigkeit von `here` wird nicht mehr benötigt.
- Das NRW-Skript verwies dreimal auf das nicht definierte Grafikobjekt `theme_boxplot`. Es verwendet jetzt das bereits vorhandene, gleich aufgebaute `theme_plot`. Die statistischen Verfahren wurden dabei nicht geändert.
- Plattformabhängige Calibri-Vorgaben wurden durch `sans` ersetzt. Die PDF-Sammlungen verwenden Cairo, damit etwa das Symbol η korrekt dargestellt wird. Abbildungen müssen deshalb nicht bytegleich zu den ursprünglichen Windows-Dateien sein.
- Die neu erzeugte Rheinland-Pfalz-Zwischendatei stimmt nach Normalisierung der Zeilenenden vollständig mit der gelieferten Datei überein: 64 Zeilen und 67 Spalten.
- Bei Katalonien stimmen zehn der neu erzeugten Prüf-/Zuordnungstabellen bytegleich mit den vorhandenen Dateien überein. Weitere Tabellen unterscheiden sich unter anderem in Spaltenreihenfolge und bereits im gelieferten Skript geänderten Erläuterungstexten. Eine zusätzliche Tabelle wird vom gelieferten Skript neu erzeugt.

## Katalonien: zwei unterscheidbare Datenstände

Die archivierte Datei `data/reference/Catalonia/BRIT_Katalonien_2024_merged_datasets_incl_impropis.csv` enthält 1.894 Zeilen und 28 Spalten. Die Neuberechnung aus Rohdaten hat dieselbe Struktur, weicht aber in 454 Zellen ab. Dazu gehören 418 in der archivierten Datei leere Mengenfelder, die im Rohdatenlauf als Null erscheinen, sowie weitere bereinigte Mengen, Anschlussgrade und Systemeigenschaften. Es handelt sich somit nicht allein um unterschiedliche Codierungen. Die Störstoffwerte für 2024 stimmen überein.

Diese Unterschiede lagen bereits zwischen dem gelieferten Vorbereitungsskript und dem gelieferten Analysestand vor. Die fachlichen Gründe sämtlicher manueller Eingriffe sind nicht vollständig im Skript dokumentiert; sie wurden nicht nachträglich erfunden. Die vollständige Differenzliste liegt im Release unter `validation/catalonia-input-differences.csv`.

Standardmäßig verwendet die statistische Katalonien-Auswertung den archivierten Eingang, den auch das ursprüngliche Analyseskript einlas. Dadurch bleibt dieser Projektstand wiederverwendbar. Mit `--rebuild-catalonia` kann die Rohdatenvariante untersucht werden; diese ist ausdrücklich eine andere Datenvariante. Die Wiederherstellung des archivierten Katalonien-Eingangs ausschließlich aus Rohdaten und vollständig begründeten Bereinigungsregeln bleibt eine fachliche Nachdokumentation. Eine Übereinstimmung sämtlicher Zahlen aller veröffentlichten Factsheets wird durch den technischen Lauf allein nicht behauptet.

## Bereitstellungsstand

Der API-Endpunkt `/waste_collection/api/collection/analysis/` wurde lokal implementiert und getestet. Er ist noch nicht produktiv bereitgestellt. Der R-Client funktioniert nach Bereitstellung auf einer BRIT-Instanz; eine öffentliche Bereitstellung wurde in diesem Arbeitsschritt nicht vorgenommen. Das feste Analysepaket funktioniert unabhängig davon. Ein mehrseitiger Live-Abruf ist kein transaktionaler Datenbank-Snapshot; abgerufene Daten können mit Prüfsumme für spätere Wiederverwendung archiviert werden.
