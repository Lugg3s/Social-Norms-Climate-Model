# Aktuelle ToDos:
1. Sensitivitätsanalyse validieren. Ist die jetzt abgeschlossen?
    1. Gibt es fehlgeschlagene Simulationen? Warum?
1. Warum hatte ich das chaotische Verhalten nicht in meinen Batch runs?
1. Sensitivitätsanalyse auch nochmal mit anderen x0-Werten durchführen, um zu prüfen ob sich etwas ändert.


# Sonstige ToDos:
1. dynamic social norm mit dynamic social norm2 vergleichen (und entsprechend auch Descriptive, injunctive, dynamic mit Descriptive, injunctive, dynamic2)
1. Equations und model simulations in 2 Files aufteilen?
1. Batch_runner logisch in mehrere Files aufteilen
1. Plots entwickeln, bei denen man die Parameter direkt in dem Plot bearbeiten kann mit Slidern o..
1. Solver prüfen, um artefakte zu eliminieren
1. latin hyper cube sampling vergleichen mit meiner aktuellen Sensitivitätsanalyse (sobol indices)
1. regression trees?
1. Bifurcation-style plots: systematically sweep a key parameter (e.g., norm strength delta) and track whether the system undergoes a sharp transition. Different norm types may have different critical thresholds for tipping from a high-emission to a low-emission equilibrium.
1. Konvergenzen Mathematisch berechnen
    1. vorallem relevant für nicht-dynamische und nicht-abm plots. Damit kann ich zb ausschließen, dass es Zwischenzustände bei bestimmten Normen gibt, sondern dass diese immer zu 0/1 konvergieren.
1. Bobachtung bei descriptive injunctve dynamic 2:
    1. Der initiale Fall wird nach ca tau Jahren (hier ca. 40) wieder abgebildet
    1. TODO: auch für kleiner tau testen.
    1. ![alt text](image.png)

1. Zeitschritt vom solver gleichsetzen mit Theta und schauen ob oszillationen noch auftreten (insbesondere auf Folie 34)
    1. das hat bei mir nicht funktioniert 
    1. ggf. im mattermost chat fragen
    
1. Mit Parametern die aktuelle Entwicklung reverse engineeren (also von 1800 zb laufen lasssen)
    1. Und dann schauen, welche Normen die aktuelle Entwicklung besonders gut darstellen
    1. Oder das nutzen, um Parameter zu kalibrieren und dann diese Parameterkombinationen miteinander vergleichen (auch für t>2026)



# Offene Fragen:
1. Um Struktur in die Auswertung zu bekommen: Konkrete Fragestellungen formulieren
1. Warum fällt die dynamic norm während zb baseline steigt
Bspw. bei x0=0.9
1. Nachschauen, ob die Logik von Observation-based / intention motivation (agents) der aus dem Paper entspricht
1. Agent.py ToDo Kommentare
1. Welchen Wert muss x haben, damit die Temperatur fällt?
1. Warum ist social_norm_term = N belief based? Beliefbased heißt doch, dass da auch eine Wertung drin steckt. Wo ist die? N ist laut Beckage konstant
1. Gibt es bestimmte Verhaltensmuster, die nur bei bestimmten Normen auftreten?


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
