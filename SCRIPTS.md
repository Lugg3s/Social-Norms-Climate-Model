# Ausführbare Skripte

Stand: 6. November 2026. Befehle im Repository-Hauptordner ausführen.
Szenarionamen mit Leerzeichen in Anführungszeichen setzen. Jedes CLI bietet
zusätzlich `-h` / `--help`. Tabellen nennen die tatsächlichen CLI-Argumente;
Modellparameter kommen aus `config/scenarios.json`, sofern nicht ausdrücklich
variiert. Zeitangaben sind Jahre seit Simulationsbeginn, aktuell Kalenderjahr 1800.

Diese Übersicht bei neuen Skripten und bei Änderungen von Argumenten oder
Standardwerten zusammen mit dem Code aktualisieren. Bibliotheksmodule ohne
Startfunktion sind keine eigenen CLI-Skripte. Tests sind unten gesammelt aufgeführt.

## 1. Endwert-/Bifurkationsdiagramm

`python -m analysis.bifurcation_diagram` — ein Scatterplot pro Szenario:
genau ein variierender Parameter gegen `x` am festgelegten Endzeitpunkt.

```powershell
python -m analysis.bifurcation_diagram --scenarios "Descriptive, injunctive, dynamic2 (custom)" --parameter-name beta --parameter-range 0 5 101 --simulation-time 1000 --workers 11
```

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | `baseline` | Szenarien; jedes erhält einen eigenen Plot. |
| `--parameter-name NAME` | `beta` | Genau ein variierender numerischer Modellparameter. |
| `--parameter-values WERT ...` | Pflichtalternative | Einzelwerte; alternativ zu `--parameter-range`. |
| `--parameter-range MIN MAX ANZAHL` | Pflichtalternative | Gleichmäßig verteilte Werte einschließlich beider Grenzen; ganzzahlige Anzahl ≥ 2. |
| `--simulation-time JAHRE` | `600` | Zeitpunkt des ausgewerteten Endwerts; erscheint auch in der y-Achse. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--seed ZAHL` | `42` | Derselbe Seed für jeden unabhängigen Lauf. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl für ABM-Szenarien. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung der Simulation. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | nicht gesetzt | Integrationsschritt für `RK4`, dort erforderlich. |
| `--constant-temperature-costs` | aus | Setzt die Temperaturkostenfunktion auf 1. |
| `--simulate-only-x` | aus | Friert Kohlenstoffbestände ein; Temperaturgleichung bleibt aktiv. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\Runs\bifurcation_diagrams` | Überordner für einen neuen Zeitstempelordner. |

Alle anderen Modellparameter bleiben pro Szenario unverändert. Jeder Wert startet
aus den konfigurierten Anfangsbedingungen, ohne Übernahme des vorherigen Endzustands.
Auch die Anfangsbedingungen sind fest, außer wenn ausdrücklich deren Parameter
(z. B. `x0`) als einziger Sweep-Parameter ausgewählt wird.
PNG/SVG und szenarioweise CSVs liegen unter `<Zeitstempel>/scenario_01/` usw.;
`metadata.json` ordnet die Szenarien zu und dokumentiert Parameter, Einstellungen
und Quellcode-Hashes. `results.csv` enthält alle Läufe und ihren Status und wird
während der Berechnung aktualisiert. Fehlgeschlagene oder abgebrochene Läufe
erzeugen keine künstlichen Punkte bei `x = 0`.
Der Plot zeigt endliche Endwerte, keine automatisch bestimmten Gleichgewichte,
Stabilitäten oder vollständigen Attraktoräste; bei Oszillationen ist der Endwert
phasenabhängig. Es werden keine benachbarten Punkte verbunden.

## 2. Globale Sobol-Sensitivitätsanalyse

`python -m analysis.sensitivity.sensitivity_analysis` — Simulationen, Sobol-Indizes,
Rankings und Verteilungsplots; speichert standardmäßig auch Zeitreihen.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | alle unterstützten Sensi-Szenarien | Auswahl der Normen. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--base-sample-size ANZAHL` | `256` | Sobol-Basisstichprobe; üblicherweise Zweierpotenz. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--seed ZAHL` | `42` | Seed für Sampling und Simulationen. |
| `--constant-temperature-costs` | aus | Temperaturkostenfunktion konstant 1. |
| `--no-save-time-series` | aus | Schaltet die standardmäßige Zeitreihenspeicherung ab. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\Sensitivity` | Überordner der Ergebnisläufe. |
| `--append-existing-folder ORDNER` | nicht gesetzt | Weitere Szenarien zu einem bestehenden Lauf unter `--output-root` ergänzen. |
| `--score-mode MODUS` | `simple_mean` | Gesamtranking: `simple_mean` oder `grouped_mean`. |

## 3. Sensi mit anschließenden Regressionsbäumen

`python -m analysis.sensitivity.sensitivity_pipeline` — führt die Sensi aus und
erstellt danach Bäume aus den gespeicherten Daten, ohne zusätzliche Simulationen.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | alle unterstützten Sensi-Szenarien | Auswahl der Normen. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--base-sample-size ANZAHL` | `256` | Sobol-Basisstichprobe. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--seed ZAHL` | `42` | Seed für Sensi und Baumkonfiguration. |
| `--constant-temperature-costs` | aus | Temperaturkostenfunktion konstant 1. |
| `--no-save-time-series` | aus | Zeitreihenspeicherung abschalten. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\Sensitivity` | Überordner; Bäume unter `<Lauf>/regression_trees/<Zeitstempel>/`. |
| `--append-existing-folder ORDNER` | nicht gesetzt | Szenarien ergänzen; Bäume anschließend aus allen fertigen Szenarien neu erstellen. |
| `--score-mode MODUS` | `simple_mean` | `simple_mean` oder `grouped_mean`. |

## 4. Regressionsbäume aus gespeicherter Sensi

`python -m analysis.regression_trees.regression_tree_analysis --input-root "<Sensi-Lauf>"`
— erzeugt Bäume, Validierung und SVG-Übersichten.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | erforderlich | Sensi-Lauf oder einzelner Szenarioordner. |
| `--output-root PFAD` | `plots/regression_tree_results` | Überordner für einen neuen Ergebnisordner. |
| `--scenarios NAME ...` | alle verfügbaren | Szenarienauswahl. |
| `--targets NAME ...` | alle 12 unterstützten Zielgrößen | Auswahl der Zielgrößen. |
| `--seed ZAHL` | `42` | Seed für Aufteilung und Validierung. |
| `--test-fraction ANTEIL` | `0.25` | Anteil zurückgehaltener Sobol-Blöcke. |
| `--max-depths TIEFE ...` | `2 3 4` | In der Kreuzvalidierung geprüfte Baumtiefen. |
| `--analysis-modes MODUS ...` | automatisch nach Anzahl der Normen | `per_norm`, `pooled_common`, `per_norm_common`. |

Zielgrößen: `x_mean`, `final_temperature`, `cumulative_emissions`, `first_time_x95`,
`bool_x95`, `oscillation_occurrence`, `oscillations_per_500_years`, `final_x`,
`median_period`, `oscillation_amplitude`, `damping_index`, `damping_rate`.
Bei mehreren Normen werden standardmäßig alle drei Analysearten erstellt;
gemeinsame Parameteranalysen liegen unter `_common_parametes/`, gegebenenfalls
zusätzlich in einer Variante ohne Agentennorm unter `without_agents/`.

## 5. Regressionsbaum-Übersicht erneut erstellen

`python -m analysis.regression_trees.regression_tree_plots --input-root "<Baum-Ergebnisordner>"`
— kombiniert vorhandene Baum-SVGs; passt keine Bäume neu an.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | erforderlich | Gespeicherter Baum-Ergebnisordner. |
| `--output-path PFAD` | `<input-root>/regressiontrees_alle_normen.svg` | Ziel der Übersicht. |
| `--columns ANZAHL` | `2` | Bäume nebeneinander. |

## 6. Batch-Simulationen

`python -m simulation.batch_runner` — führt konfigurierte Experimentgruppen aus.
Szenarien und Modell-/Solvereinstellungen stehen in `ExperimentGroup` im Skript.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--groups NAME ...` | alle aktiven Standardgruppen | Experimentgruppen auswählen. |
| `--output-root PFAD` | `E:\Masterarbeit\Runs` | Überordner der Ergebnisse. |
| `--overwrite` | aus | Bereits fertige Kombinationen erneut berechnen. |
| `--save-outputs-per-run` | aus | Einzelne Zeitreihen und Plots zusätzlich speichern. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |

## 7. Batch-Plots aus gespeicherten Sensi-Zeitreihen

`python -m analysis.sensitivity.sensitivity_batch_plots --input-root "<Sensi-Lauf>"`
— erstellt Batch-Plots, Videos und 3D-Darstellungen ohne neue Simulationen;
benötigt gespeicherte NPZ-Zeitreihen.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | erforderlich | Sensi-Lauf oder einzelner Normordner. |
| `--output-root PFAD` | `<input-root>/batch_plots/<Zeitstempel>` | Ergebnisordner. |
| `--scenarios NAME ...` | alle verfügbaren | Szenarienauswahl. |
| `--sample-indices INDEX ...` | alle verfügbaren | Bestimmte Sample-IDs auswählen. |
| `--max-samples ANZAHL` | keine Begrenzung | Höchstzahl je Norm. |
| `--workers ANZAHL` | `1` | Parallele Verarbeitung. |
| `--no-videos` | aus | Vergleichsvideos abschalten. |
| `--no-3d` | aus | 3D-Ausgaben abschalten. |
| `--parameter-pair X Y` | erste zwei gesampelte Parameter je Norm | Parameterachsen; Argument für weitere Paare wiederholen. |
| `--max-video-frames ANZAHL` | `240` | Maximale Framezahl je 3D-Zeitanimation. |
| `--video-fps ZAHL` | `2` | Bildrate der Plot-Vergleichsvideos. |
| `--animation-fps ZAHL` | `12` | Bildrate der 3D-Zeitanimationen. |
| `--include-boundary-cases` | aus | Gespeicherte Nullrandfälle zusätzlich darstellen. |

## 8. Interessante Parameterkombinationen aus CSV

`python -m simulation.interesting_parameter_loader` — simuliert und zeichnet
die in einer CSV hinterlegten Parameterkombinationen.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--input PFAD` | `data/interesting_parameter_sets.csv` | Eingabetabelle. |
| `--output-root PFAD` | `plots` | Überordner der Ausgaben. |
| `--simulation-time JAHRE` | `800` | Simulationsdauer. |
| `--no-store-files` | aus | Plots anzeigen, keine Dateien speichern. |

## 9. Videos aus vorhandenen Plotbildern

`python -m visualization.make_plot_videos "<Laufordner>"` — kombiniert vorhandene
PNG-Dateien zu MP4s innerhalb der vorhandenen Gruppen-/Normordner.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `root` | erforderlich, positional | Ordner mit Gruppen-, Norm- und Einzelrun-Unterordnern. |
| `--plot DATEINAME` | alle gefundenen PNG-Namen | Bestimmten Plot wählen, z. B. `x.png`. |

Die Bildrate ist hier fest auf 2 fps gesetzt. `--scenario`, `--output` und
`--fps` sind im Code auskommentiert und keine verfügbaren CLI-Argumente.

## 10. Review älterer Sensitivitätsdaten

`python -m analysis.sensitivity.sensitivity_review --source "<alter Sensi-Lauf>" --output "<separater Reviewordner>"`
— historische Audit-/Konvergenzauswertung mit festgelegten Stichproben 128/256/512
und älteren Zielgrößennamen; kein allgemeiner Ersatz für die aktuelle Sensi.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--source PFAD` | erforderlich | Passender historischer Sensi-Lauf. |
| `--output PFAD` | erforderlich | Separater Reviewordner außerhalb des Quelllaufs. |
| `--reuse-analysis` | aus | Audit-Tabellen nach Prüfung der Quellen-Hashes wiederverwenden. |

## 11. Numerische Prüfung ausgewählter historischer Extremfälle

`python -m analysis.sensitivity.sensitivity_numerical_probe --review "<Reviewordner>" --source "<historischer Sensi-Lauf>"`
— prüft zwei fest ausgewählte Fälle mit verschiedenen Ausgabe-/Integrationsauflösungen;
benötigt `targeted_review_samples.json` aus dem historischen Review.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--review PFAD` | erforderlich | Reviewordner; Ausgaben unter `numerical_probes/`. |
| `--source PFAD` | erforderlich | Historischer Sensi-Lauf für den Vergleich. |
| `--only-case FALL` | beide Fälle | `inj1763` oder `did267`. |
| `--only-variant NAME` | alle Varianten | `reference`, `dense` oder `refined`. |
| `--timeout-minutes MINUTEN` | `15` | Zeitlimit je Prüfung. |
| `--workers ANZAHL` | `3` | Parallele Prüfungen. |

## 12. Laufzeit-Profiling

`python -m support.tools.profile_dynamic_norms` — untersucht, in welchen Funktionen
ausgewählte Simulationen Rechenzeit verbrauchen.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | `baseline`, `Dynamic social norm`, `Descriptive, injunctive, dynamic2` | Szenarienauswahl. |
| `--simulation-time JAHRE` | `400` | Simulationsdauer. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--max-seconds SEKUNDEN` | `60` | Profiling-Zeitlimit je Fall. |
| `--zero-boundaries` | aus | Nullrandfälle ergänzen. |
| `--samples-file PFAD` | nicht gesetzt | `samples.csv` einer Sensi; erfordert genau ein Szenario. |
| `--sample-indices INDEX ...` | `0` | Zeilen aus `--samples-file`. |
| `--output-root PFAD` | `support/profiling_results` | Überordner der Profile. |

## 13. Regressionsbaum-Demo

`python -m analysis.regression_trees.regression_tree_demo` — synthetisches Beispiel
mit bekannten Regeln, ohne Klimasimulation.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--output-root PFAD` | `plots/regression_tree_example` | Überordner für Beispieldaten und Ergebnisse. |

## 14. Qualitatives Normen-Werkbuch

`python support/qualitative_norms/serve.py` — startet die lokale Weboberfläche.

| Argument | Standard | Bedeutung |
| --- | --- | --- |
| `--port NUMMER` | `8765` | Port auf `127.0.0.1`. |
| `--no-browser` | aus | Browser nicht automatisch öffnen. |

## Notebook und Bibliotheksaufrufe

`main.ipynb` in VSCode/Jupyter öffnen. `visualization/plotting.py`,
`analysis/symbolic_analysis.py` und `analysis/simulation_metrics.py` werden über
Python-Funktionen genutzt; sie besitzen keine eigene Kommandozeilenoberfläche.
Beispielsweise ist `plotting.plot_x_sensitivity(...)` ein Notebook-Aufruf.
Ihre Funktionsargumente stehen direkt in den Python-Signaturen und sind keine CLI-Flags.

## Tests

```powershell
python -m unittest discover -s support/tests -t . -v
python -m unittest support.tests.test_bifurcation_diagram -v
python -m pytest support/tests/sensitivity/test_sensitivity_review.py
```

| Aufrufparameter | Bedeutung |
| --- | --- |
| `discover` | Tests rekursiv suchen. |
| `-s support/tests` | Startordner der Suche. |
| `-t .` | Repository als oberstes Importverzeichnis. |
| `-v` | Ausführliche Ausgabe. |
| `support.tests.<Modul>` | Statt Gesamtsuche ein bestimmtes unittest-Modul ausführen. |
| Testdateipfad bei `pytest` | Auswahl der pytest-Tests. |
