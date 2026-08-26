# Aktuelle ToDos (priorisiert):
1. Equilibria und kipppunkte im code berechnen und plotten/ausgeben
	1. Auch die Formel für Equilibria bestimmen (um zu sehen von welchen Parametern diese abhängig sind)
1. Bei der dynamischen Norm: Berechnen für welche Parameter die Oszillation am gröpten ist (heatmap mit parametern auf den achsen (heat = oszillationsstärke/amplitude/frequenz))
1. dynamic social norm mit dynamic social norm2 vergleichen (und entsprechend auch Descriptive, injunctive, dynamic mit Descriptive, injunctive, dynamic2)
1. Equations und model simulations in 2 Files aufteilen?
1. Batch_runner logisch in mehrere Files aufteilen
1. Plots entwickeln, bei denen man die Parameter direkt in dem Plot bearbeiten kann mit Slidern o.ä.
1. Ich möchte einen Batch-Run machen bei dem ich Parameter verändere, die in allen Sozialen Normen vorkommen. Wie wähle ich für diesen Run die Parameter, die Normspezifisch sind?
    1. Man könnte zb. für jede Norm mehrere Varianten simulieren. (eine Mit viel Oszillation, eine mit Zwischenzustand, eine mit wenig Oszilaation, eine mit KOnvergenz gegen 0 und eine mit Konvergenz gegen 1)
        1. Aber auch dann wirkt das auf mich sehr schwammig.
    1. TODO: Jedes Scenario einmal mit Standard-Baseline-Parametern laufen lassen und dann mit der Heatmap jeweils 1 Parameterkombination pro Klasse raussuchen.


# Offene Fragen:
1. Um Struktur in die Auswertung zu bekommen: Konkrete Fragestellungen formulieren
1. Warum fällt die dynamic norm während zb baseline steigt
Bspw. bei x0=0.9
1. Nachschauen, ob die Logik von Observation-based / intention motivation (agents) der aus dem Paper entspricht
1. Agent.py ToDo Kommentare
1. Warum ist in Descriptive, injunctive, dynamic immer so ein Sprung in der social norm value?

