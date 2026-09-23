# Validierung des BRIT-EU-Analysepakets

## Kompatibilität mit Ubuntu-R (23.09.2026)

Die zusätzlich bereitgestellte Einzeldatei `BRIT_Datenanalyse.R` wurde unter Ubuntu/R 4.3.3 mit dem lokalen HTTP-Testserver geprüft: Anmeldung über `/api-token-auth/`, Nutzung des Tokens bei einem geschützten Abruf der erweiterten Sammlungsansicht über zwei Seiten sowie CSV-/RDS-Export ohne Zugangsdaten in den Metadaten. Ein direkter Start mit `Rscript BRIT_Datenanalyse.R` und interaktiver, verdeckter Passworteingabe wurde ebenfalls mit Testzugangsdaten und neu erzeugten Ergebnisdateien erfolgreich ausgeführt. In einem sauberen Ubuntu/R-4.3.3-Image installierte die Datei die vier benötigten Pakete automatisch in eine neue Benutzerbibliothek. Der zugehörige Django-Integrationstest bestätigte den Tokenaustausch und den Zugriff auf eigene private Sammlungen. Die öffentliche BRIT-Instanz wurde nicht mit echten Zugangsdaten getestet.

Nach der Umstellung auf `?view=extended` bestanden 57 benachbarte Django-Tests (API, ViewSet und Export-Serializer) sowie die R-Client-, HTTP- und Einzeldatei-Tests im Ubuntu/R-4.3.3-Image. Ruff-Lint, Ruff-Formatprüfung und die Prüfung auf fehlende Migrationen bestanden mit `brit-worktree-check --no-up`. Der erste Check-Aufruf ohne `--no-up` konnte wegen drei bereits aktiver fremder BRIT-Web-Stacks keinen weiteren Stack starten; die abschließende Prüfung verwendete die bereits gestarteten lokalen Datenbank- und Redis-Dienste.

Anonyme Live-Prüfung am 23.09.2026: Die vorhandene Sammlungs-Listen-API lieferte auch mit `?view=extended` HTTP 200, aber noch die schlanke Antwort ohne `schema_version` und Jahreswerte. Die erweiterte Variante ist auf diesem Server somit nicht bereitgestellt. Der R-Client lehnt diese Antwort durch die Schemaversion-Prüfung ab.

Ubuntu 24.04 stellt R 4.3.3 über `r-base` bereit. Das bisherige Lockfile für R 4.6.1 scheiterte im gezielten Test bereits an der R-Mindestversion. Das neue Lockfile wurde aus einer sauberen Ubuntu-24.04-Umgebung mit R 4.3.3 und dem datierten CRAN-Stand 15.04.2024 erzeugt. Es enthält 149 Paketversionen. `Rscript --vanilla tests/test_environment.R` bestätigte, dass alle 149 unter R 4.3.3 geladen werden und der aufgezeichneten Version entsprechen.

Der vollständige Lauf mit `Rscript --vanilla run.R` in der vorbereiteten Ubuntu-Umgebung war erfolgreich: sieben Skripte, 38 PNG-Abbildungen, sieben PDF-Dateien und sieben RDS-Dateien mit Analyseobjekten; keine R-Warnungen. `Rscript --vanilla tests/test_client.R` sowie der HTTP-Integrationstest mit `Rscript --vanilla tests/test_http.R` waren ebenfalls erfolgreich. Für den HTTP-Test lief der mitgelieferte lokale Server `python3 tests/http_fixture.py` im selben Container.

Für den Zahlenvergleich wurden 157 statistische Objekte aus dem früheren R-4.6.1-Lauf und dem neuen R-4.3.3-Lauf in einfache Datenstrukturen übertragen. `Rscript --vanilla tests/compare_numeric_results.R validation/numeric-reference-r461.rds validation/numeric-current-r433.rds` bestand: Bei 145 Objekten stimmen sämtliche geprüften Werte bis auf eine Rechentoleranz von 1e-8 überein. Bei 12 Objekten unterscheiden sich ausschließlich p-Werte und ihre Adjustierungen. Die größte absolute Abweichung beträgt 0,000460253; keine Entscheidung an der 5-%-Grenze ändert sich. Diese Differenzen entstehen beim Wechsel der R- und Paketversionen. Für eine buchstabengetreue Wiederholung der alten p-Werte bleibt die frühere Umgebung maßgeblich; der hier veröffentlichte R-4.3.3-Stand ist in sich festgelegt.

Die neue Docker-Rezeptur verwendet das per Digest festgelegte Ubuntu-24.04-Image, die regulären R-4.3.3-Pakete und den festen CRAN-Stand. `docker build -t brit-eu-r:ubuntu24.04-r433 .` wurde vollständig ausgeführt; der abschließende Image-Bauschritt bestätigte alle 149 Paketversionen. Eine frische Extraktion des Release-ZIP wurde mit diesem Image und `run.R --case=nrw` erfolgreich ausgewertet. Das RDS-Ergebnis und die Laufzeitinformationen wurden dabei neu erzeugt.

Auch der für Nutzer vorgesehene Einrichtungsweg wurde in einer frischen Paketkopie geprüft: `Rscript --vanilla setup.R` stellte die Projektbibliothek vollständig wieder her und bestätigte anschließend alle 149 Paketversionen mit `tests/test_environment.R`. Der Befehl endete ohne Fehler. Das zugehörige Protokoll liegt unter `validation/native-setup-r433.txt`.

Historischer Prüfstand 22.09.2026: Die erste Ausgabe lief unter Linux/Ubuntu 24.04 mit R 4.6.1 und dem **damaligen** `renv.lock`. Diese Prüfung ist die Vergleichsbasis für die neue Ausgabe. Der aktuelle Paketstand zielt auf Ubuntu 24.04 mit R 4.3.3; dessen zusätzliche Prüfergebnisse stehen im Abschnitt „Kompatibilität mit Ubuntu-R“. Windows und macOS wurden nicht separat ausgeführt.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Vollständiger Lauf aus einem Paket ohne Ergebnisse und ohne generierte Zwischendaten | Alle sieben Skripte erfolgreich, keine R-Warnungen |
| Katalonien-Rohdatenvariante: `Rscript run.R --case=catalonia --rebuild-catalonia` | Separater vollständiger Lauf erfolgreich; Variante in der Provenienz als `rebuilt_from_raw` markiert |
| Ergebnisdateien | 38 PNG-Abbildungen, sieben PDF-Sammlungen, sieben RDS-Dateien mit Analyseobjekten |
| Originale Eingaben | Acht Rohdateien und ein bereinigter Katalonien-Analysestand, bytegleich zum gelieferten Projekt, SHA-256 im Manifest |
| Normale R-Einrichtung im historischen Prüfstand: `Rscript --vanilla setup.R` | Eigene Projektbibliothek erfolgreich wiederhergestellt; anschließend Client-Tests unter aktivierter renv-Umgebung erfolgreich |
| R-Client: `Rscript --vanilla tests/test_client.R` | Erfolgreich: Pagination, Schema, Gebietskennungen, Nullwerte, vollständig fehlende Spalten, wechselnder Server, doppelte IDs, Zählfehler, leerer Bestand und Snapshot-Manipulation |
| HTTP: `Rscript --vanilla tests/test_http.R` mit lokalem Testserver | Erfolgreich: tatsächlicher JSON-Abruf über zwei Seiten, Einheiten, HTTP-404-Hinweis, Download eines Datenrelease mit Prüfsumme |
| Django-API und benachbarte Funktionen | Ursprünglicher Prüfstand: 55 Tests erfolgreich; aktualisierte Tests der erweiterten Listenansicht siehe unten |
| BRIT-Codeprüfung | Ruff, Formatprüfung und Prüfung auf fehlende Migrationen erfolgreich |

Der vollständige Lauf wurde mit `docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/analysis" brit-eu-r:2026-09-22 run.R` durchgeführt. Der damalige Image-Build verwendete den seinerzeit mitgelieferten Dockerfile. `results/session-info.txt` dokumentiert die ausgeführte Umgebung; `results/input-provenance.json` enthält Datenvariante und Code-Prüfsummen. Diese Dateien entstehen bei jedem eigenen Lauf neu.

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

Die erweiterte Listenansicht `/waste_collection/api/collection/?view=extended` wurde lokal implementiert und getestet. Sie ist noch nicht produktiv bereitgestellt. Der R-Client funktioniert nach Bereitstellung auf einer BRIT-Instanz; eine öffentliche Bereitstellung wurde in diesem Arbeitsschritt nicht vorgenommen. Das feste Analysepaket funktioniert unabhängig davon. Ein mehrseitiger Live-Abruf ist kein transaktionaler Datenbank-Snapshot; abgerufene Daten können mit Prüfsumme für spätere Wiederverwendung archiviert werden.
