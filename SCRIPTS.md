# Ausführbare Skripte

Stand: 6. November 2026. Befehle im Repository-Hauptordner ausführen.
Szenarionamen mit Leerzeichen in Anführungszeichen setzen. Jedes CLI bietet
zusätzlich `-h` / `--help`. Tabellen nennen die tatsächlichen CLI-Argumente;
Modellparameter kommen aus `config/scenarios.json`, sofern nicht ausdrücklich
variiert. Zeitangaben sind Jahre seit Simulationsbeginn, aktuell Kalenderjahr 1800.

Die Spalte „Standard bei Weglassen“ nennt den tatsächlich verwendeten Wert oder
das resultierende Verhalten, einschließlich der Auswahl aus der Konfiguration.
Pflichtargumente haben keinen Standardwert; ohne sie bricht der Aufruf ab.
Bei Schaltern bedeutet `False`, dass die Option ohne Angabe nicht aktiviert ist.
Relative Standardpfade wie `plots/...` beziehen sich auf den Repository-Hauptordner.

Diese Übersicht bei neuen Skripten und bei Änderungen von Argumenten oder
Standardwerten zusammen mit dem Code aktualisieren. Bibliotheksmodule ohne
Startfunktion sind keine eigenen CLI-Skripte. Tests sind unten gesammelt aufgeführt.

Die gemeinsamen Simulationsstandards stehen ausschließlich in
[`config/simulation_settings.json`](config/simulation_settings.json).
Sie gelten für Sensi/Pipeline, Bifurkation, neue Batchgruppen, CSV-Simulationen,
Profiling, direkte `simulate()`-Aufrufe und die Notebook-Plotfunktionen.
Aktuell: 600 Jahre, 24 Ausgabepunkte/Jahr, 0,1 Jahre Kopplungsintervall,
Seed 42, 1.000 Agenten, BDF, `dt=null`, temperaturabhängige Kosten und
`simulate_only_x=false`. Fehlende Konfigurationseinträge verursachen einen Fehler.
Nach einer Änderung neue Python-Prozesse starten bzw. den Notebook-Kernel neu starten.

Vorrang: explizites CLI-Argument → explizite Experimentgruppeneinstellung →
zentraler Standard. Die aktive historische Batchgruppe behält ihre gespeicherten
Einstellungen; numerische historische Prüfungen behalten ihre festen Prüfvarianten.
Die Tabellen zeigen den aktuellen Stand der zentralen Werte. Die beiden booleschen
Simulationsoptionen können mit `--no-constant-temperature-costs` bzw.
`--no-simulate-only-x` auch ausdrücklich ausgeschaltet werden.
Ergebnis-Metadaten speichern alle tatsächlich verwendeten Simulationseinstellungen;
Notebook-Plots schreiben dafür `simulation_manifest.jsonl` in ihren Ausgabeordner.

## 1. Endwert-/Bifurkationsdiagramm

`python -m analysis.bifurcation_diagram` — ein Scatterplot pro Szenario:
genau ein variierender Parameter gegen `x` am festgelegten Endzeitpunkt.

```powershell
python -m analysis.bifurcation_diagram --scenarios "Descriptive, injunctive, dynamic2 (custom)" --parameter-name beta --simulation-time 1000 --workers 11
```

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | Die neun Einträge aus `parameter_ranges.sensitivity_scenarios` in `scenarios.json` | Gleiche Normenauswahl wie bei der Sensi; jedes Szenario erhält einen eigenen Plot. Explizite Namen ersetzen die Standardauswahl. |
| `--parameter-name NAME` | `beta` | Genau ein variierender numerischer Modellparameter. |
| `--parameter-values WERT ...` | Gleichmäßiges Raster aus Bereich und `--num-points` | Explizite Einzelwerte statt JSON-Bereich; alternativ zu `--parameter-range`. |
| `--parameter-range MIN MAX` | Globaler Bereich aus `scenarios.json`; für `beta` aktuell `[0, 5]` | Überschreibt die beiden Grenzen. Die alte Form `MIN MAX ANZAHL` bleibt gültig; deren Anzahl hat Vorrang vor `--num-points`. |
| `--num-points ANZAHL` | `100` | Gleichmäßig verteilte Werte einschließlich beider Grenzen; mindestens 2. Explizite Einzelwerte bestimmen ihre eigene Anzahl. |
| `--simulation-time JAHRE` | `600` | Zeitpunkt des ausgewerteten Endwerts; erscheint auch in der y-Achse. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--seed ZAHL` | `42` | Derselbe Seed für jeden unabhängigen Lauf. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl für ABM-Szenarien. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung der Simulation. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | `None`; bei `RK4` kein gültiger Standard | Integrationsschritt für `RK4`, dort erforderlich; bei `BDF` und `LSODA` nicht verwendet. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | `False`; temperaturabhängige Kostenfunktion | Setzt die Temperaturkostenfunktion auf 1. |
| `--simulate-only-x` / `--no-simulate-only-x` | `False`; Kohlenstoffbestände werden mit simuliert | Friert Kohlenstoffbestände ein; Temperaturgleichung bleibt aktiv. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\bifurcation_diagrams` | Überordner für einen neuen Zeitstempelordner. |

Alle anderen Modellparameter bleiben pro Szenario unverändert. Jeder Wert startet
aus den konfigurierten Anfangsbedingungen, ohne Übernahme des vorherigen Endzustands.
Auch die Anfangsbedingungen sind fest, außer wenn ausdrücklich deren Parameter
(z. B. `x0`) als einziger Sweep-Parameter ausgewählt wird.
PNG/SVG und szenarioweise CSVs liegen direkt unter `<Zeitstempel>/` und heißen
`<Parameter>_<Szenarioname>.png`, `.svg` bzw. `.csv`, z. B. `beta_baseline.png`
und `beta_baseline.csv`. Leerzeichen und ungültige Windows-Pfadzeichen werden
durch `_` ersetzt; Varianten behalten ihren Namenszusatz. `metadata.json` ordnet
die Ausgabestämme über `scenario_output_stems` zu und dokumentiert Parameter,
Einstellungen und Quellcode-Hashes. `results.csv` enthält weiterhin alle Läufe
und ihren Status und wird
während der Berechnung aktualisiert. Fehlgeschlagene oder abgebrochene Läufe
erzeugen keine künstlichen Punkte bei `x = 0`.
Der Plot zeigt endliche Endwerte, keine automatisch bestimmten Gleichgewichte,
Stabilitäten oder vollständigen Attraktoräste; bei Oszillationen ist der Endwert
phasenabhängig. Es werden keine benachbarten Punkte verbunden.

Die Bereiche stehen in `config/scenarios.json` im Block `parameter_ranges`:
`bounds` definiert jeden Parameterbereich genau einmal für alle Normen.
Jedes Szenario enthält `ABM`, `social_norm` und einen Block `defaults` mit seinen
expliziten Verhaltensparametern. Die Sensi verwendet die Reihenfolge dieser
Einträge und variiert diejenigen mit globalem oder explizitem CLI-Bereich.
Eine separate Parameterliste gibt es nicht. Die Agentennorm definiert
beispielsweise weder `social_norm_factor` noch `kappa`.
`common_parameters` enthält die gemeinsamen Klimagrundlagen, die Temperaturkosten-
Funktion und die Anfangsbedingungen. Zusätzliche Einträge in `defaults`, etwa
`C_at0` oder `x0`, dürfen diese Werte für ein Szenario überschreiben. Ohne Bereich
bleiben sie fest; mit globalem oder CLI-Bereich werden sie in der Sensi variiert.
Ein globaler Bereich allein nimmt einen nur gemeinsam definierten Parameter
nicht automatisch in die Sensi jedes Szenarios auf.
Der Endwertplot liest direkt den globalen Bereich des gewählten Parameters.
`sensitivity_scenarios` legt die gemeinsame Standardauswahl von neun Szenarien für
Sensi/Pipeline und Bifurkationsdiagramme fest: ein Standardszenario pro Norm.
Weitere konfigurierte Szenarien, etwa `(custom)` oder `(chaos candidate)`, werden
nur durch explizite Auswahl mit `--scenarios` einbezogen. Die Auswahl erfolgt über
die Liste, nicht automatisch anhand der Szenarionamen oder des Feldes `social_norm`.
Die Bereiche sind keine festen Modellwerte und ändern die Simulation außerhalb
der gesampelten Parameter nicht. Fehlende Bereiche werden nicht durch Python-Werte ersetzt.
Für ganzzahlige Modellparameter wie `network_size` müssen die erzeugten Werte
ebenfalls ganzzahlig sein; gegebenenfalls explizite `--parameter-values` verwenden.

Beispiele für andere Punktzahlen und überschreibende Grenzen:

```powershell
python -m analysis.bifurcation_diagram --scenarios baseline --num-points 50
python -m analysis.bifurcation_diagram --scenarios baseline --parameter-range 1 3 --num-points 80
```

## 2. Globale Sobol-Sensitivitätsanalyse

`python -m analysis.sensitivity.sensitivity_analysis` — Simulationen, Sobol-Indizes,
Rankings und Verteilungsplots; speichert standardmäßig auch Zeitreihen.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | Die neun Einträge aus `parameter_ranges.sensitivity_scenarios` in `scenarios.json` | Auswahl der Normen. |
| `--parameter-range NAME MIN MAX` | Globale Bereiche aus `parameter_ranges.bounds` für die Einträge unter Szenario-`defaults` | Bereich für einen unter `defaults` deklarierten Parameter angeben/überschreiben; wiederholbar. Gilt für alle gewählten Szenarien, die diesen Eintrag jeweils enthalten müssen. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--base-sample-size ANZAHL` | `256` | Sobol-Basisstichprobe; üblicherweise Zweierpotenz. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--seed ZAHL` | `42` | Seed für Sampling und Simulationen. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | `False`; temperaturabhängige Kostenfunktion | Temperaturkostenfunktion konstant 1. |
| `--no-save-time-series` | Zeitreihen speichern (`save_time_series=True`) | Schaltet die standardmäßige Zeitreihenspeicherung ab. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\Sensitivity` | Überordner der Ergebnisläufe. |
| `--append-existing-folder ORDNER` | Neuer Zeitstempelordner; kein bestehender Lauf wird ergänzt | Weitere Szenarien zu einem bestehenden Lauf unter `--output-root` ergänzen. |
| `--score-mode MODUS` | `simple_mean` | Gesamtranking: `simple_mean` oder `grouped_mean`. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall in Jahren. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl bei ABM-Szenarien. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | `None` | Erforderlicher positiver RK4-Schritt; bei adaptiven Solvern ungenutzt. |
| `--simulate-only-x` / `--no-simulate-only-x` | `False` | Kohlenstoffspeicher einfrieren bzw. Einfrieren deaktivieren; Temperatur entwickelt sich weiter. |

## 3. Sensi mit anschließenden Regressionsbäumen

`python -m analysis.sensitivity.sensitivity_pipeline` — führt die Sensi aus und
erstellt danach Bäume aus den gespeicherten Daten, ohne zusätzliche Simulationen.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | Die neun Einträge aus `parameter_ranges.sensitivity_scenarios` in `scenarios.json` | Auswahl der Normen. |
| `--parameter-range NAME MIN MAX` | Globale Bereiche aus `parameter_ranges.bounds` für die Einträge unter Szenario-`defaults` | Überschreibt einen Bereich für die ausgewählten Szenarien; wiederholbar wie im Sensi-Skript. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--base-sample-size ANZAHL` | `256` | Sobol-Basisstichprobe. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--seed ZAHL` | `42` | Seed für Sensi und Baumkonfiguration. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | `False`; temperaturabhängige Kostenfunktion | Temperaturkostenfunktion konstant 1. |
| `--no-save-time-series` | Zeitreihen speichern (`save_time_series=True`) | Zeitreihenspeicherung abschalten. |
| `--sample-timeout-minutes MINUTEN` | `20` | Zeitlimit je Simulation. |
| `--output-root PFAD` | `E:\Masterarbeit\Sensitivity` | Überordner; Bäume unter `<Lauf>/regression_trees/<Zeitstempel>/`. |
| `--append-existing-folder ORDNER` | Neuer Zeitstempelordner; kein bestehender Lauf wird ergänzt | Szenarien ergänzen; Bäume anschließend aus allen fertigen Szenarien neu erstellen. |
| `--score-mode MODUS` | `simple_mean` | `simple_mean` oder `grouped_mean`. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall in Jahren. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl bei ABM-Szenarien. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | `None` | Erforderlicher positiver RK4-Schritt; bei adaptiven Solvern ungenutzt. |
| `--simulate-only-x` / `--no-simulate-only-x` | `False` | Kohlenstoffspeicher einfrieren bzw. Einfrieren deaktivieren; Temperatur entwickelt sich weiter. |

## 4. Regressionsbäume aus gespeicherter Sensi

`python -m analysis.regression_trees.regression_tree_analysis --input-root "<Sensi-Lauf>"`
— erzeugt Bäume, Validierung und SVG-Übersichten.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | Kein Standard; erforderlich | Sensi-Lauf oder einzelner Szenarioordner. |
| `--output-root PFAD` | `plots/regression_tree_results` | Überordner für einen neuen Ergebnisordner. |
| `--scenarios NAME ...` | Alle im Eingabelauf verfügbaren Szenarien | Szenarienauswahl. |
| `--targets NAME ...` | Alle zwölf unten aufgeführten Zielgrößen | Auswahl der Zielgrößen. |
| `--seed ZAHL` | `42` | Seed für Aufteilung und Validierung. |
| `--test-fraction ANTEIL` | `0.25` | Anteil zurückgehaltener Sobol-Blöcke. |
| `--max-depths TIEFE ...` | `2 3 4` | In der Kreuzvalidierung geprüfte Baumtiefen. |
| `--analysis-modes MODUS ...` | Eine Norm: `per_norm`; mehrere: `per_norm`, `pooled_common`, `per_norm_common` | Analysearten auswählen. |

Zielgrößen: `x_mean`, `final_temperature`, `cumulative_emissions`, `first_time_x95`,
`bool_x95`, `oscillation_occurrence`, `oscillations_per_500_years`, `final_x`,
`median_period`, `oscillation_amplitude`, `damping_index`, `damping_rate`.
Bei mehreren Normen werden standardmäßig alle drei Analysearten erstellt;
gemeinsame Parameteranalysen liegen unter `_common_parametes/`, gegebenenfalls
zusätzlich in einer Variante ohne Agentennorm unter `without_agents/`.

## 5. Regressionsbaum-Übersicht erneut erstellen

`python -m analysis.regression_trees.regression_tree_plots --input-root "<Baum-Ergebnisordner>"`
— kombiniert vorhandene Baum-SVGs; passt keine Bäume neu an.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | Kein Standard; erforderlich | Gespeicherter Baum-Ergebnisordner. |
| `--output-path PFAD` | `<input-root>/regressiontrees_alle_normen.svg` | Ziel der Übersicht. |
| `--columns ANZAHL` | `2` | Bäume nebeneinander. |

## 6. Batch-Simulationen

`python -m simulation.batch_runner` — führt konfigurierte Experimentgruppen aus.
Szenarien und Modell-/Solvereinstellungen stehen in `ExperimentGroup` im Skript.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--groups NAME ...` | Alle Gruppen in `DEFAULT_EXPERIMENT_GROUPS`; aktuell `dynamic2_top5_sensi128` | Experimentgruppen auswählen. |
| `--output-root PFAD` | `E:\Masterarbeit\Runs` | Überordner der Ergebnisse. |
| `--overwrite` | `False`; fertige Kombinationen überspringen | Bereits fertige Kombinationen erneut berechnen. |
| `--save-outputs-per-run` | `False`; nur zusammengefasste Ausgaben | Einzelne Zeitreihen und Plots zusätzlich speichern. |
| `--workers ANZAHL` | CPU-Anzahl minus eins, mindestens 1 | Parallele Simulationen. |
| `--simulation-time JAHRE` | Experimentgruppe; sonst `600` (zentral) | Simulationsdauer in Jahren seit Modellbeginn. |
| `--output-points-per-year ANZAHL` | Experimentgruppe; sonst `24` (zentral) | Ausgabepunkte pro simuliertem Jahr. |
| `--coupling-interval JAHRE` | Experimentgruppe; sonst `0.1` (zentral) | Kopplungsintervall in Jahren. |
| `--seed ZAHL` | Experimentgruppe; sonst `42` (zentral) | Seed zur Initialisierung. |
| `--n-agents ANZAHL` | Experimentgruppe; sonst `1000` (zentral) | Agentenzahl bei ABM-Szenarien. |
| `--solver NAME` | Experimentgruppe; sonst `BDF` (zentral) | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | Experimentgruppe; sonst `None` (zentral) | Erforderlicher positiver RK4-Schritt; bei adaptiven Solvern ungenutzt. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | Experimentgruppe; sonst `False` (zentral) | Temperaturkostenfunktion auf 1 setzen bzw. deaktivieren; Gewichtung via temperature_factor. |
| `--simulate-only-x` / `--no-simulate-only-x` | Experimentgruppe; sonst `False` (zentral) | Kohlenstoffspeicher einfrieren bzw. Einfrieren deaktivieren; Temperatur entwickelt sich weiter. |

## 7. Batch-Plots aus gespeicherten Sensi-Zeitreihen

`python -m analysis.sensitivity.sensitivity_batch_plots --input-root "<Sensi-Lauf>"`
— erstellt Batch-Plots, Videos und 3D-Darstellungen ohne neue Simulationen;
benötigt gespeicherte NPZ-Zeitreihen.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--input-root PFAD` | Kein Standard; erforderlich | Sensi-Lauf oder einzelner Normordner. |
| `--output-root PFAD` | `<input-root>/batch_plots/<Zeitstempel>` | Ergebnisordner. |
| `--scenarios NAME ...` | Alle im Eingabelauf verfügbaren Szenarien | Szenarienauswahl. |
| `--sample-indices INDEX ...` | Alle gespeicherten Sample-IDs der gewählten Szenarien | Bestimmte Sample-IDs auswählen. |
| `--max-samples ANZAHL` | keine Begrenzung | Höchstzahl je Norm. |
| `--workers ANZAHL` | `1` | Parallele Verarbeitung. |
| `--no-videos` | `False`; Videos erstellen | Vergleichsvideos abschalten. |
| `--no-3d` | `False`; 3D-Ausgaben erstellen | 3D-Ausgaben abschalten. |
| `--parameter-pair X Y` | erste zwei gesampelte Parameter je Norm | Parameterachsen; Argument für weitere Paare wiederholen. |
| `--max-video-frames ANZAHL` | `240` | Maximale Framezahl je 3D-Zeitanimation. |
| `--video-fps ZAHL` | `2` | Bildrate der Plot-Vergleichsvideos. |
| `--animation-fps ZAHL` | `12` | Bildrate der 3D-Zeitanimationen. |
| `--include-boundary-cases` | `False`; Nullrandfälle ausschließen | Gespeicherte Nullrandfälle zusätzlich darstellen. |

## 8. Interessante Parameterkombinationen aus CSV

`python -m simulation.interesting_parameter_loader` — simuliert und zeichnet
die in einer CSV hinterlegten Parameterkombinationen.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--input PFAD` | `data/interesting_parameter_sets.csv` | Eingabetabelle. |
| `--output-root PFAD` | `plots` | Überordner der Ausgaben. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--no-store-files` | `False`; Dateien speichern | Plots anzeigen, keine Dateien speichern. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabepunkte pro simuliertem Jahr. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall in Jahren. |
| `--seed ZAHL` | `42` | Seed zur Initialisierung. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl bei ABM-Szenarien. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | `None` | Erforderlicher positiver RK4-Schritt; bei adaptiven Solvern ungenutzt. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | `False` | Temperaturkostenfunktion auf 1 setzen bzw. deaktivieren; Gewichtung via temperature_factor. |
| `--simulate-only-x` / `--no-simulate-only-x` | `False` | Kohlenstoffspeicher einfrieren bzw. Einfrieren deaktivieren; Temperatur entwickelt sich weiter. |

## 9. Videos aus vorhandenen Plotbildern

`python -m visualization.make_plot_videos "<Laufordner>"` — kombiniert vorhandene
PNG-Dateien zu MP4s innerhalb der vorhandenen Gruppen-/Normordner.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `root` | Kein Standard; erforderlich, positional | Ordner mit Gruppen-, Norm- und Einzelrun-Unterordnern. |
| `--plot DATEINAME` | alle gefundenen PNG-Namen | Bestimmten Plot wählen, z. B. `x.png`. |

Die Bildrate ist hier fest auf 2 fps gesetzt. `--scenario`, `--output` und
`--fps` sind im Code auskommentiert und keine verfügbaren CLI-Argumente.

## 10. Review älterer Sensitivitätsdaten

`python -m analysis.sensitivity.sensitivity_review --source "<alter Sensi-Lauf>" --output "<separater Reviewordner>"`
— historische Audit-/Konvergenzauswertung mit festgelegten Stichproben 128/256/512
und älteren Zielgrößennamen; kein allgemeiner Ersatz für die aktuelle Sensi.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--source PFAD` | Kein Standard; erforderlich | Passender historischer Sensi-Lauf. |
| `--output PFAD` | Kein Standard; erforderlich | Separater Reviewordner außerhalb des Quelllaufs. |
| `--reuse-analysis` | `False`; Audit-Tabellen neu berechnen | Audit-Tabellen nach Prüfung der Quellen-Hashes wiederverwenden. |

## 11. Numerische Prüfung ausgewählter historischer Extremfälle

`python -m analysis.sensitivity.sensitivity_numerical_probe --review "<Reviewordner>" --source "<historischer Sensi-Lauf>"`
— prüft zwei fest ausgewählte Fälle mit verschiedenen Ausgabe-/Integrationsauflösungen;
benötigt `targeted_review_samples.json` aus dem historischen Review.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--review PFAD` | Kein Standard; erforderlich | Reviewordner; Ausgaben unter `numerical_probes/`. |
| `--source PFAD` | Kein Standard; erforderlich | Historischer Sensi-Lauf für den Vergleich. |
| `--only-case FALL` | `inj1763` und `did267` | Einzelnen Fall auswählen. |
| `--only-variant NAME` | `reference`, `dense` und `refined` | Einzelne Variante auswählen. |
| `--timeout-minutes MINUTEN` | `15` | Zeitlimit je Prüfung. |
| `--workers ANZAHL` | `3` | Parallele Prüfungen. |

## 12. Laufzeit-Profiling

`python -m support.tools.profile_dynamic_norms` — untersucht, in welchen Funktionen
ausgewählte Simulationen Rechenzeit verbrauchen.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--scenarios NAME ...` | `baseline`, `Dynamic social norm`, `Descriptive, injunctive, dynamic2` | Szenarienauswahl. |
| `--simulation-time JAHRE` | `600` | Simulationsdauer. |
| `--coupling-interval JAHRE` | `0.1` | Kopplungsintervall. |
| `--output-points-per-year ANZAHL` | `24` | Ausgabeauflösung. |
| `--max-seconds SEKUNDEN` | `60` | Profiling-Zeitlimit je Fall. |
| `--zero-boundaries` | `False`; keine zusätzlichen Nullrandfälle | Nullrandfälle ergänzen. |
| `--samples-file PFAD` | Kein Sample-Import; konfigurierte Szenariowerte verwenden | `samples.csv` einer Sensi; erfordert genau ein Szenario. |
| `--sample-indices INDEX ...` | `0` (nur bei `--samples-file` verwendet) | Zeilen aus `--samples-file`. |
| `--output-root PFAD` | `support/profiling_results` | Überordner der Profile. |
| `--seed ZAHL` | `42` | Seed zur Initialisierung. |
| `--n-agents ANZAHL` | `1000` | Agentenzahl bei ABM-Szenarien. |
| `--solver NAME` | `BDF` | `BDF`, `LSODA` oder `RK4`. |
| `--dt JAHRE` | `None` | Erforderlicher positiver RK4-Schritt; bei adaptiven Solvern ungenutzt. |
| `--constant-temperature-costs` / `--no-constant-temperature-costs` | `False` | Temperaturkostenfunktion auf 1 setzen bzw. deaktivieren; Gewichtung via temperature_factor. |
| `--simulate-only-x` / `--no-simulate-only-x` | `False` | Kohlenstoffspeicher einfrieren bzw. Einfrieren deaktivieren; Temperatur entwickelt sich weiter. |

## 13. Regressionsbaum-Demo

`python -m analysis.regression_trees.regression_tree_demo` — synthetisches Beispiel
mit bekannten Regeln, ohne Klimasimulation.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--output-root PFAD` | `plots/regression_tree_example` | Überordner für Beispieldaten und Ergebnisse. |

## 14. Qualitatives Normen-Werkbuch

`python support/qualitative_norms/serve.py` — startet die lokale Weboberfläche.

| Argument | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `--port NUMMER` | `8765` | Port auf `127.0.0.1`. |
| `--no-browser` | `False`; Browser automatisch öffnen | Browser nicht automatisch öffnen. |

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

| Aufrufparameter | Standard bei Weglassen | Bedeutung |
| --- | --- | --- |
| `discover` | Ohne Testnamen startet `unittest` ebenfalls die Testsuche | Tests rekursiv suchen. |
| `-s support/tests` | `.` (aktueller Arbeitsordner) | Startordner der unittest-Suche. |
| `-t .` | Startordner der Suche, also der Wert von `-s` | Oberstes Importverzeichnis bei unittest. |
| `-v` | Normale Ausgabe (`verbosity=1`) | Ausführliche unittest-Ausgabe (`verbosity=2`). |
| `support.tests.<Modul>` | Ohne Testnamen: Testsuche | Statt Gesamtsuche ein bestimmtes unittest-Modul ausführen. |
| Testdateipfad bei `pytest` | Testsuche ab aktuellem Arbeitsordner; derzeit keine abweichende pytest-Konfiguration im Repo | Auswahl der pytest-Tests. |
