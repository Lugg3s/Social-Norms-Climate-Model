# Aktuelle ToDos:
1. aktuellen stand commiten, pushen und pullen
1. alle varianten nochmal laufen lassen (verschiedene x0, standard und const_temperature)
1. globale sensi analysieren und auswerten
    1. jeden Ordner einzeln durchgehen
        1. largest annual change nochmal kontrollieren. Vorher waren oscillations nicht in steeper/flatter/... enthalten. Jetzt schon. NOt comparable wurde dort entfernt.
    1. Vergleiche zwischen den Normen
    1. Research Questions beantworten
1. globale sensi mit konsanten Temperaturkosten auswerten und vergleichen


# Punkte aus der sensi, die ich noch analysieren muss
1. social_norm_factor fehlt bei der agents norm. Dadurch wird natürlich tendeziell der temperature_term viel größer als der norm_term.
    1. sieht so aus, als wäre eta der Ersatz für social_norm_factor
    1. evtl kann man das in den Equations und den Sensi-Ergebnissen einfach umbenennen in social_norm_factor (ABER NUR, WENN DIE WERTEBEREICHE GLEICH SIND)
1. 0.1% der runs in baseline sind als "stable intermediate level" klassifiziert. Wie kann das sein?

## Themen zum besprechen mit Hannah
1. 


## ToDos für codex


# ToDos die ich auf jeden Fall noch machen muss
1. related work chapter (chatis Entwurf) kontrollieren
1. regressiontrees statt anzahl läufe prozente angeben
1. Bury Paper nochmal gründlich lesen (ab Discussion)
1. Sensitivitätsanalyse auch nochmal mit anderen x0-Werten durchführen, um zu prüfen ob sich etwas ändert.
1. Sensi mit konstantem temperatur-term laufen lassen
    1. dann sollten die Aussagen über Oszillationen aussagekräftiger sein verglichen zwischen den Normtypen.
1. bifurcation diagramme auswerten. Begründung für Oszillationen in dem Plot finden.
    1. evtl. zum Vergleich mit 1500 Jahren ausprobieren
1. Lokale Sensi mit den Relevantesten Parametern aus der globalen sensi
    1. Lokale Sensi laufen lassen
1. Klassifizierung auch bei lokaler sensi
1. Hysterese untersuchen
    
# ToDos Für die Ausarbeitung
1. In der Arbeit erläutern warum es Sinn macht die jeweiligen normen (Kombinationen) sich anzuschauen
    ○ Vorschlag von Hannah: Anhand von einem Beispiel (Papierbecherfirma oderso) (nicht nur für mich sondern auch für die Arbeit)
In Arbeit Erwähnen warum ich das Bury modell genommen habe
1. Konvergenzen Mathematisch berechnen
    1. vorallem relevant für nicht-dynamische und nicht-abm plots. Damit kann ich zb ausschließen, dass es Zwischenzustände bei bestimmten Normen gibt, sondern dass diese immer zu 0/1 konvergieren.

# ToDos, die man evtl. noch machen könnte, aber nicht muss
1. vergleichen wieviel Prozent einer Norm erreichen das gleiche Ergebnis (x>=95%, oder x<=95%) wie die no-norm referenz. In Wie vielen Fällen führt das implementieren der Norm dazu, dass sich das Ergebnis/Endergebnis unterscheidet?
1. latin hyper cube sampling vergleichen mit meiner aktuellen Sensitivitätsanalyse (sobol indices)
1. Mit Parametern die aktuelle Entwicklung reverse engineeren (also von 1800 zb laufen lasssen)
    1. Und dann schauen, welche Normen die aktuelle Entwicklung besonders gut darstellen
    1. Oder das nutzen, um Parameter zu kalibrieren und dann die Normen mit diesen Parameterkombinationen miteinander vergleichen (dann auch für t>2026)
1. Ggf. langfristige Simulationen mit kleinerer samplpesize laufen lassen
1. dynamic social norm mit dynamic social norm2 vergleichen (und entsprechend auch Descriptive, injunctive, dynamic mit Descriptive, injunctive, dynamic2)
1. Plots entwickeln, bei denen man die Parameter direkt in dem Plot bearbeiten kann mit Slidern o..

# Offene Fragen:
1. warum wurde bei der sensi mit konstantem f(T) nur oszillation bei descriptive, injunctive, dynamic gefunden?
    1. mit f(T) haben die dynamischen normen solo auch keine oszillation???
1. Warum fällt die dynamic norm während zb baseline steigt
Bspw. bei x0=0.9
1. Welchen Wert muss x haben, damit die Temperatur fällt?
    1. das kann man doch einfach mathematisch berechnen oder?
1. Warum ist social_norm_term = N belief based? Beliefbased heißt doch, dass da auch eine Wertung drin steckt. Wo ist die? N ist laut Beckage konstant

# ToDos, die ich verworfen habe:
Idee für einheitliche skalierung
- scale_factor scaliert die Wertebereiche von allen Normen auf den selben Bereich
- scale_factor wird pro Norm automatisch berechnet
- social_norm_factor und temperature_factor bleiben frei variierbar, um Norm- und Temperatureinfluss unterschiedlich zu gewichten.
- Der Normbeitrag lautet dann: social_norm_factor * scale_factor * Normterm. Für die dynamischen Normen mit x_ref muss noch ein sinnvoller Skalierungsmaßstab festgelegt werden.
1. Zeitschritt vom solver gleichsetzen mit Theta und schauen ob oszillationen noch auftreten (insbesondere auf Folie 34)
    1. das hat bei mir nicht funktioniert 
    1. ggf. im mattermost chat fragen
1. Klassifizierung nach Flache et al. (2017, Abb. 1) prüfen: pro Norm Anteile der Sensi-Läufe mit Konsens, Clustering oder Bi-Polarisierung bestimmen; vorher klären, ob und wie die Kategorien auf aggregiertes x bzw. individuelle Intentionen übertragbar sind ([Paper](https://doi.org/10.18564/jasss.3521)).
1. Logistic choice / logistische regression statt replicator equation ausprobieren (könnte interessant sein, aber könnte auch zu viel sein)

