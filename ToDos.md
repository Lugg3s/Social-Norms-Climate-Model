# Aktuelle ToDos (priorisiert):
1. Equilibria und kipppunkte im code berechnen und plotten/ausgeben
	1. Auch die Formel für Equilibria bestimmen (um zu sehen von welchen Parametern diese abhängig sind)
1. Bei der dynamischen Norm: Berechnen für welche Parameter die Oszillation am gröpten ist (heatmap mit parametern auf den achsen (heat = oszillationsstärke/amplitude/frequenz))
1. dynamic social norm mit dynamic social norm2 vergleichen (und entsprechend auch Descriptive, injunctive, dynamic mit Descriptive, injunctive, dynamic2)
1. Equations und model simulations in 2 Files aufteilen?
1. Batch_runner logisch in mehrere Files aufteilen
1. Plots entwickeln, bei denen man die Parameter direkt in dem Plot bearbeiten kann mit Slidern o..
1. Solver prüfen, um artifakte zu eliminieren

1. latin hyper cube sampling vergleichen mit meiner aktuellen Sensitivitätsanalyse (sobol indices)
1. regression trees?
1. unabhängig von Runs einmal T plotten, um zu sehen ab wann T x positiv/negativ beeinflusst.

###############################################################################################
1. Sensitivitätsanalyse laufen lassen
###############################################################################################

# Offene Fragen:
1. Um Struktur in die Auswertung zu bekommen: Konkrete Fragestellungen formulieren
1. Warum fällt die dynamic norm während zb baseline steigt
Bspw. bei x0=0.9
1. Nachschauen, ob die Logik von Observation-based / intention motivation (agents) der aus dem Paper entspricht
1. Agent.py ToDo Kommentare
1. Warum ist in Descriptive, injunctive, dynamic immer so ein Sprung in der social norm value?
1. Welchen Wert muss x haben, damit die Temperatur fällt?
1. falls sensitivitätsanalyse nicht funktioniert wegen Solver, im Team nochmal fragen



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
