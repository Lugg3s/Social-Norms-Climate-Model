# Vergleich nach Umstellung auf Szenario-defaults

Stand: 6. November 2026. Vergleich mit dem unmittelbar vor dieser Umstellung gesicherten Zustand.

**Ergebnis:** Alle 14 Szenarien haben unveränderte Sensi-Parameter, Parameterreihenfolgen und Bereiche. Die neun Standardszenarien bleiben dieselben.

| Szenario | Parameter vorher | Parameter nachher | Namen/Reihenfolge/Bereiche | Sobol-Stichprobe |
| --- | ---: | ---: | --- | --- |
| baseline | 4 | 4 | identisch | identisch |
| Dynamic social norm | 6 | 6 | identisch | identisch |
| Observation-based / intention motivation (agents) | 6 | 6 | identisch | identisch |
| Belief-based / intention motivation | 5 | 5 | identisch | identisch |
| Observation based / approval (punish only one behaviour) | 4 | 4 | identisch | identisch |
| Static injunctive | 5 | 5 | identisch | identisch |
| Descriptive, injunctive, dynamic | 9 | 9 | identisch | identisch |
| Descriptive, injunctive, dynamic (transient oscillations) | 9 | 9 | identisch | identisch |
| Descriptive, injunctive, dynamic2 | 10 | 10 | identisch | identisch |
| Descriptive, injunctive, dynamic2 (testing) | 10 | 10 | identisch | identisch |
| Descriptive, injunctive, dynamic2 (tau_timestep) | 10 | 10 | identisch | identisch |
| Descriptive, injunctive, dynamic2 (custom) | 10 | 10 | identisch | identisch |
| Descriptive, injunctive, dynamic2 (chaos candidate) | 10 | 10 | identisch | identisch |
| dynamic social norm2 | 7 | 7 | identisch | identisch |

Die Stichproben wurden mit Basisgröße 4, Seed 42 und ohne Second-Order-Indizes erzeugt und elementweise verglichen. Das prüft die unveränderte Zuordnung der Sobol-Eingaben; es ist keine statistische Konvergenzprüfung.

Bei den geladenen Modellparametern entfallen ausschließlich `kappa` und `social_norm_factor` im Agentenszenario. Sie wurden dort zuvor aus `baseline` geerbt, werden in der Agentengleichung aber nicht verwendet und waren bereits vorher keine Sensi-Eingaben. Alle anderen Modellwerte sind unverändert.

Zusätzlich wurden Baseline und Agentennorm mit den alten und neuen Modellparametern jeweils bis Jahr 218 simuliert. Beide Vergleiche lieferten exakt gleiche Zustandszeitreihen; Einstellungen und Ergebnisse stehen in der JSON-Auswertung.

Die Sensi-Auswahl wird jetzt aus den Einträgen unter `defaults` und den verfügbaren globalen oder expliziten CLI-Bereichen abgeleitet. Zusätzliche Szenario-Overrides ohne Bereich bleiben fest. Eine neue explizite Eingabe mit Bereich kann die Sensi künftig bewusst erweitern.

Vollständige Vorher-/Nachher-Definitionen, Stichproben-Hashes und Unterschiede der geladenen Modellparameter: [scenario_defaults_migration_2026-11-06.json](scenario_defaults_migration_2026-11-06.json).
