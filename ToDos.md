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
1. interesting_parameter_sets.csv befüllen
1. Chati hatte mal davon erzählt, dass man in einer sensitivitätsanalyse/monte carlo analyse bestimmen kann, welche Parameter das Endergebnis am stärksten verändern (maximal diverse Kurven erzeugen)
    1. Das sollte man pro Social-norm einmal laufen lassen und dann den batch runner mit den beiden Parametern laufen lassen, die die größte Veränderung aufweisen.

# Offene Fragen:
1. Um Struktur in die Auswertung zu bekommen: Konkrete Fragestellungen formulieren
1. Warum fällt die dynamic norm während zb baseline steigt
Bspw. bei x0=0.9
1. Nachschauen, ob die Logik von Observation-based / intention motivation (agents) der aus dem Paper entspricht
1. Agent.py ToDo Kommentare
1. Warum ist in Descriptive, injunctive, dynamic immer so ein Sprung in der social norm value?
1. Warum gibt es bei größterem Zeithorizont fast überall Oszillationen? (außer bei static_injunctive)
1. Welchen Wert muss x haben, damit die Temperatur fällt?




# Parameterkombinationen

### Observation-based / imitation

`delta` ✅

### Dynamic social norm

`tau_ref`, `tau_STref` ✅  
`tau_ref`, `tau_xp` ✅  
`tau_STref`, `tau_xp` ✅

### Observation-based / intention motivation (agents)

`network_size`, `agent_susceptibility`

### Belief-based / intention motivation

`N` ✅

### Observation-based / approval (punish only one behaviour)

`alpha` ✅

### Static injunctive

`c_inj`, `x_target` ✅

### Descriptive, injunctive, dynamic

`delta`, `c_inj`  
`delta`, `x_target`  
`delta`, `c_dyn`  
`delta`, `tau_ref`  
`delta`, `tau_STref`  
`delta`, `tau_xp`  
`c_inj`, `x_target`  
`c_inj`, `c_dyn` ✅  
`c_inj`, `tau_ref`  
`c_inj`, `tau_STref`  
`c_inj`, `tau_xp`  
`x_target`, `c_dyn`  
`x_target`, `tau_ref`  
`x_target`, `tau_STref`  
`x_target`, `tau_xp`  
`c_dyn`, `tau_ref`  
`c_dyn`, `tau_STref`  
`c_dyn`, `tau_xp`  
`tau_ref`, `tau_STref`  
`tau_ref`, `tau_xp`  
`tau_STref`, `tau_xp`

### Descriptive, injunctive, dynamic2

`delta`, `c_inj`  
`delta`, `x_target`  
`delta`, `c_dyn`  
`delta`, `tau`  
`delta`, `theta`  
`c_inj`, `x_target`  
`c_inj`, `c_dyn` ✅  
`c_inj`, `tau`  
`c_inj`, `theta`  
`x_target`, `c_dyn`  
`x_target`, `tau`  
`x_target`, `theta`  
`c_dyn`, `tau`  
`c_dyn`, `theta`  
`tau`, `theta`

### Injunctive, dynamic2

`c_inj`, `x_target`  
`c_inj`, `c_dyn`  
`c_inj`, `tau`  
`c_inj`, `theta`  
`x_target`, `c_dyn`  
`x_target`, `tau`  
`x_target`, `theta`  
`c_dyn`, `tau`  
`c_dyn`, `theta`  
`tau`, `theta` ✅

### Dynamic social norm2

`c_dyn`, `tau`  
`c_dyn`, `theta`  
`tau`, `theta` ✅
