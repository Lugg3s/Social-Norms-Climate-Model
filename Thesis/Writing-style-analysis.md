# Schreibstilanalyse der Bachelorarbeit

Analysiert am 23. Oktober 2026. Diese Datei beschreibt den tatsächlich
beobachteten Stil. Die daraus abgeleiteten Regeln für die englische
Masterarbeit stehen in [Writing-style-guide.md](Writing-style-guide.md).

## 1. Grundlage und Reichweite

Grundlage ist die vom Nutzer bereitgestellte Datei
`C:/Users/lukas/Downloads/Bachelorarbeit.zip`, SHA-256:
`8fa6627adc4f6cab7246c7f2f0454271d858eaae24d835f317acec1190a00ea3`.
Untersucht wurden die vollständigen Kapitelquellen, nicht lediglich das
Deckblatt, ein Abstract oder einzelne ausgewählte Absätze. Alle nachfolgenden
Quellpfade beziehen sich auf `thesis_CG_template_v173/` innerhalb dieses ZIPs.
Zeilenangaben beziehen sich auf die dort gespeicherten `.tex`-Dateien.

| Kürzel | Quelle | Inhalt |
| --- | --- | --- |
| Z | `Zusammenfassung.tex` | Zusammenfassung |
| E | `Chapters/Einfuehrung.tex` | Einleitung |
| G | `Chapters/Grundlagen.tex` | Grundlagen, Posenschätzung und DTW |
| V | `Chapters/Verwandte_Arbeiten.tex` | Verwandte Arbeiten |
| U | `Chapters/Umsetzung.tex` | Methodik und Umsetzung |
| R | `Chapters/Ergebnisse.tex` | Ergebnisse und Diskussion |
| F | `Chapters/Fazit.tex` | Fazit und Ausblick |

LaTeX-Kommandos, Kommentare, Tabellenwerte und Pseudocode werden nicht als
gewöhnlicher Fließtext interpretiert. Bildunterschriften werden zusätzlich
qualitativ betrachtet. Die Erklärung der Dokumentklasse und das mitgelieferte
Beispiel-PDF sind keine Grundlage für Aussagen über den persönlichen
Schreibstil. Der Abschnitt zum Einsatz von Hilfsmitteln in F wird nicht für
die unten genannten Fließtextkennzahlen verwendet.

Die Bachelorarbeit ist deutsch. Deshalb sind die Beobachtungen zum deutschen
Originalstil und die Vorschläge für ein natürliches englisches Gegenstück
auseinanderzuhalten. Es liegt hier kein englischer Vergleichstext des Autors
vor. Die englischen Regeln sind eine begründete Übertragung, keine Messung
eines bereits vorhandenen englischen Autorenstils.

## 2. Gesamtprofil

Der Text ist überwiegend **anwendungsbezogen, erklärend und schrittweise
argumentierend**. Der Leser soll nachvollziehen können, welches Problem ein
Verfahren löst, wie es funktioniert und weshalb es in dieser Anwendung
eingesetzt wird. Die Darstellung ähnelt einer technischen Erläuterung mit
wissenschaftlicher Begründung stärker als einem stark verdichteten
Fachartikel oder einem rein mathematischen Beweistext.

Ein wiederkehrender Ablauf lautet:

> Problem oder Anforderung -> Mechanismus -> konkrete Umsetzung -> Wirkung
> oder Einschränkung.

Die fachliche Aussage wird häufig erst allgemein eingeführt und anschließend
auf den konkreten Anwendungsfall eingegrenzt. Die Stimme ist unpersönlich,
aber nicht distanziert-abstrakt: Sie orientiert sich an konkreten Daten,
Parametern, Arbeitsschritten, Videos, Gelenken und beobachtbaren Fehlern.

Nicht durchgängig ist dagegen eine vollkommen zurückhaltende Bewertung.
Neben sorgfältigen Einschränkungen stehen Formulierungen wie „enorme
Bedeutung“, „qualitativ hochwertige Ergebnisse“, „immensen Einfluss“ oder
„gut klassifiziert“. Diese wertenden Stellen gehören zur beobachteten
Fassung, sollten aber nicht zum Zielmerkmal der Masterarbeit werden.

## 3. Orientierende sprachliche Kennzahlen

Die folgenden Werte stammen aus einer einfachen Bereinigung der sieben
Quellen. Entfernt wurden Kommentare, die Umgebungen `table`, `figure`,
`algorithm`, `equation` und `eqnarray`, zentrale Referenzkommandos und
Überschriften. Inline-Mathematik wurde durch ein Platzhalterwort ersetzt;
LaTeX-Umlaute wurden normalisiert. Wortzahlen sind deshalb nur Näherungen,
keine publizierfähige linguistische Vermessung.

| Textteil | Ungefährer Fließtextumfang |
| --- | ---: |
| Zusammenfassung | 170 Wörter |
| Einleitung | 340 Wörter |
| Grundlagen | 1.610 Wörter |
| Verwandte Arbeiten | 850 Wörter |
| Methodik und Umsetzung | 3.550 Wörter |
| Ergebnisse und Diskussion | 1.820 Wörter |
| Fazit und Ausblick | 310 Wörter |
| Insgesamt | rund 8.600 Wörter |

Im entsprechend bereinigten Fließtext wurden unter anderem diese Ausdrücke
gefunden:

| Ausdruck oder Wortfamilie | Vorkommen |
| --- | ---: |
| „beispielsweise“ oder „bspw.“ | 27 |
| „darüber hinaus“ | 24 |
| „jedoch“ | 19 |
| „in dieser Arbeit“ | 18 |
| Formen von „jene“ | 18 |
| Formen von „besagt“ | 17 |
| „letztendlich“ | 14 |
| „zunächst“ | 12 |
| „im Folgenden“ | 12 |
| „aufgrund“ | 12 |
| „stattdessen“ | 6 |
| „demnach“ | 3 |
| „ich“ oder „wir“ als eigenständige Wörter | 0 |

Diese Zahlen stützen die qualitative Beobachtung: Beispiele, Orientierung
und explizite Verknüpfungen tragen einen großen Teil der Leserführung.
Sie sind **keine Häufigkeitsziele** für neue Texte. Insbesondere wäre es
falsch, englische Übergangswörter nach diesen Mengen zu verteilen.

Auf eine scheinpräzise durchschnittliche Satzlänge wird verzichtet:
Abkürzungen, Dezimalzahlen, Referenzen, mathematische Ausdrücke und die
Verwendung von `\\` machen eine einfache punktbasierte Satzsegmentierung
unzuverlässig. Die folgende Analyse des Satzbaus beruht auf der Lektüre.

## 4. Aufbau der Argumentation

### 4.1 Vom allgemeinen Anlass zur konkreten Aufgabe

Die Einleitung beginnt beim Nutzen sportlicher Aktivität, nennt ein
gesellschaftliches Defizit, führt ein praktisches Hindernis an und verengt
die Fragestellung dann auf technische Unterstützung bei Übungsausführungen
(E, Zeilen 3-18). Die eigene Anwendung erscheint dadurch als Antwort auf
eine vorher beschriebene Anforderung.

Charakteristisch ist der Übergang von allgemeiner Relevanz zu einer
konkreten Möglichkeit: „In dieser Arbeit werden besagte Fortschritte
genutzt, um ein System zu entwickeln“ (E, Zeile 15). Der Beitrag wird über
seine Funktion eingeführt, nicht über eine lange Reihe von Neuheitsattributen.

Für die Masterarbeit bleibt diese Eingrenzung erhalten. Das Ausgangsproblem
soll jedoch auf den Vergleich von Normformalisierungen hinführen. Ein
allgemeiner Einstieg über Klimawandel darf nicht so lang werden, dass die
eigentliche Modellierungsfrage erst spät sichtbar wird.

### 4.2 Entscheidungen werden begründet

Die Darstellung beschreibt nicht nur, dass ein Verfahren eingesetzt wird.
Sie stellt häufig einen Zusammenhang zwischen einer Anforderung und der
Wahl eines Verfahrens her. In G, Zeilen 10-15, werden alternative Arten der
Körpermodellierung erklärt; die Wahl des skelettbasierten Ansatzes wird
anschließend mit den benötigten Gelenkwinkeln begründet.

Ein zweites Beispiel ist die Entscheidung gegen FastDTW: Zunächst wird sein
Laufzeitvorteil erklärt, danach wird die fehlende Notwendigkeit sehr großer
Datenreihen und die Bedeutung eines geeigneten DTW-Ergebnisses genannt
(G, Zeilen 158-160). Besonders ausgeprägt ist dieses Muster beim Vergleich
von Sakoe-Chiba-Band und Itakura-Parallelogramm (U, Zeilen 196-203).

Dieses anforderungsbezogene Begründen ist ein Kernmerkmal. In der
Masterarbeit soll zu wichtigen Modellierungsentscheidungen erkennbar sein,
welche Annahme oder Forschungsfrage die Entscheidung trägt. Das bedeutet
nicht, dass jede kleine technische Einzelheit einen Rechtfertigungsabsatz
benötigt.

### 4.3 Alternative, Problem und Anpassung

Wiederholt wird eine zunächst plausible Lösung vorgestellt, ihre Schwäche
an einem konkreten Fall erklärt und danach eine Anpassung eingeführt.
Beim Vergleich von Userausführung und Optimum folgt auf einen lokalen
Schwellenwertvergleich die Erklärung seiner Ausreißerempfindlichkeit und
anschließend die Wahl einer mittleren Abweichung (U, Zeilen 283-290).

Die spätere Ergebnisdiskussion greift auch die Schwäche dieser Alternative
auf: Eine mittlere Abweichung kann einen lokalen Fehler verdecken
(R, Zeilen 31-39). Die Argumentation ist somit nicht bloß eine nachträgliche
Aufzählung ausschließlich erfolgreicher Entscheidungen.

Für neue Texte ist diese Verbindung wertvoll: Eine Entscheidung darf einen
Nachteil vermindern, ohne dadurch als allgemein überlegen dargestellt zu
werden. Frühere Lösungsversuche gehören allerdings nur dann in den Text,
wenn sie eine relevante methodische Abwägung erklären.

## 5. Leserführung und Kapitelübergänge

Die größeren Kapitel beginnen mit einer kurzen Orientierung. G, Zeile 3;
V, Zeile 3; U, Zeile 3; und R, Zeilen 4-5, nennen jeweils die kommenden
Themen. Auch die Einleitung endet mit einem Überblick über die Arbeit
(E, Zeile 20).

Innerhalb der Kapitel signalisieren „zunächst“, „nachfolgend“,
„anschließend“ und „abschließend“ die Reihenfolge. Der Text führt den Leser
damit sichtbar durch eine Verarbeitungskette. Besonders in U ist diese
Reihenfolge fachlich sinnvoll, weil spätere Größen aus früheren Schritten
entstehen.

Die Grenze dieses Stils liegt in redundanter Ankündigung. Wenn eine
Überschrift bereits eindeutig bezeichnet, was folgt, bringt ein weiterer
Satz wie „Im Folgenden werden ... erläutert“ nicht immer zusätzlichen
Nutzen. Für die Masterarbeit werden funktionale Übergänge übernommen:
Ein Übergang erklärt möglichst, **warum** der nächste Abschnitt benötigt
wird, statt lediglich sein Kommen anzukündigen.

## 6. Absätze und Informationsreihenfolge

Viele Absätze besitzen einen nachvollziehbaren Gegenstand: eine Methode,
ein Arbeitsschritt, ein Parameter oder eine Testbedingung. Der Einstieg
benennt diesen Gegenstand; die folgenden Sätze konkretisieren ihn.

Allerdings werden teilweise mehrere Aufgaben in einen langen Absatz
gezogen. U, Zeile 166, verbindet beispielsweise das Auswahlproblem, eine
besondere Form von Extrempunkten, die Begründung eines Filters und dessen
Abschaltmöglichkeit. U, Zeile 313, verbindet Pflichtangaben, Presets,
optionale Parameter und weitere Verweise.

Das Ziel ist deshalb keine Kopie der sichtbaren LaTeX-Absatzlängen. Ein
Absatz soll eine zentrale Frage beantworten. Definition, Begründung und
Folge dürfen zusammenstehen, sofern sie denselben Gedankengang bilden.
Ein Wechsel von der allgemeinen Regel zum Sonderfall oder zur Durchführung
eines anderen Tests rechtfertigt häufig einen neuen Absatz.

Die verbreitete Verwendung von `\\` zur Textgliederung ist eine technische
Eigenschaft der Quelle. Sie wird nicht als sprachliches Stilmerkmal
übernommen. Im Masterprojekt dienen reguläre Absätze der Gliederung.

## 7. Satzbau und Satzrhythmus

Der Text kombiniert kurze erläuternde Sätze mit längeren
Begründungs- und Bedingungssätzen. Beispiele für die knappe Seite sind
„Diese Funktion wird auch ... genannt“ (G, Zeile 86), „Ein Pfad ist optimal,
wenn die Summe seiner Kosten minimal ist“ (G, Zeile 119) und „Dies
kompensiert den zuvor genannten Nachteil“ (U, Zeile 290).

Die längeren Sätze entstehen meist aus fachlich motivierten Beziehungen:
Wenn-Bedingungen, Relativsätzen zur Definition eines Objekts und
weil-/da-Begründungen. Das ist funktional, solange der Bezug der Größen
und Nebensätze deutlich bleibt. In dicht beschriebenen Methoden können
jedoch mehrere Voraussetzungen vor der eigentlichen Aussage stehen.

Übernommen wird der Wechsel zwischen Erklärung und Präzisierung. Nicht
übernommen wird eine deutsche Satzstruktur um ihrer Wiedererkennbarkeit
willen. Im Englischen soll die zentrale Aussage früh erscheinen. Ein Satz,
der zugleich Definition, Ausnahme, Parameterwahl und Folge enthält, wird
meist sinnvoll geteilt.

## 8. Stimme, Perspektive und Zeitformen

Im untersuchten Fließtext finden sich keine eigenständigen „ich“- oder
„wir“-Formulierungen. Die eigene Arbeit wird mit „in dieser Arbeit“,
„in dieser Ausarbeitung“ oder über den untersuchten Algorithmus bezeichnet.
Passivkonstruktionen wie „wird berechnet“, „wird genutzt“ und „wurde
untersucht“ sind besonders in Methoden und Ergebnissen häufig.

Trotz des unpersönlichen Tons gibt es erkennbare handelnde Subjekte: Der
Instruktor legt Größen fest, der User wählt ein Level, ein Parameter
reguliert eine Eigenschaft und ein Algorithmus erzeugt eine Ausgabe. Der
Stil ist daher nicht mit einem durchgängigen Passivgebot gleichzusetzen.

Allgemeine Eigenschaften und die Funktionsweise des Systems stehen häufig
im Präsens. Tatsächlich durchgeführte Tests und getroffene Entscheidungen
stehen oft im Präteritum oder Passiv der Vergangenheit. Der Ausblick nutzt
„könnten“, „könnte“ und „würde“ (F, Zeilen 14-17).

Für Englisch entspricht dem eine überwiegend unpersönliche Perspektive:
„This thesis compares ...“, „The model represents ...“, „The simulations
were evaluated ...“. Verfahrenseigenschaften stehen im Präsens, vergangene
Versuchsdurchführung in der Vergangenheit. Ein gezieltes Aktiv mit „the
model“ oder „the parameter“ ist häufig klarer als ein schweres Passiv.

## 9. Wortwahl, Verknüpfungen und Wiederholungen

Das Vokabular ist größtenteils fachnah und zweckbezogen. Häufige Verben sind
bestimmen, berechnen, vergleichen, auswählen, entfernen, filtern,
darstellen und untersuchen. Diese Verben benennen überwiegend konkrete
Operationen und sind ein geeigneter Ausgangspunkt für die englische Stimme.

Daneben treten auffällige Verweiswörter auf: „besagt“, „jene“, „dies“ und
„daraus“. Sie sollen bereits eingeführte Gegenstände verbinden und
Wiederholungen vermeiden. Bei mehreren möglichen Bezugspunkten können sie
jedoch unklarer sein als eine erneute Nennung des Fachbegriffs.

Übergänge erfüllen drei häufige Aufgaben:

- Reihenfolge: zunächst, anschließend, nachfolgend, letztendlich.
- Ergänzung: darüber hinaus, des Weiteren, außerdem.
- Begründung und Einschränkung: aufgrund, da, jedoch, wenngleich, dennoch.

Die hohe Wiederholung von „darüber hinaus“ ist diagnostisch sichtbar.
Eine englische Fassung soll nicht entsprechend oft „furthermore“ oder
„moreover“ einstreuen. Die logische Beziehung darf auch durch Satzstellung,
ein wiederholtes fachliches Subjekt oder die direkte Fortführung des
Gedankens entstehen. „Besagter Parameter“ wird eher zu „this parameter“
oder zum konkreten Parameternamen als zu „the aforementioned parameter“.

## 10. Fachbegriffe und Nähe zur Implementierung

Neue Begriffe werden häufig kurz erklärt oder mit ihrem englischen
Fachausdruck verbunden, etwa bei Human Pose Estimation, Landmarks,
Fenstergröße und Range of Motion. Fachwissen wird nicht vorausgesetzt,
wenn es für die nachfolgende Erklärung erst aufgebaut werden muss.

Besonders in U ist die Nähe zum Code groß: `minVisibility`,
`repRelevantTriples`, `initialRep` und weitere Bezeichner erscheinen direkt
im Fließtext. Diese Nähe macht die Umsetzung nachvollziehbar. Sie kann den
Text aber auch in eine Abfolge von Variablennamen verwandeln, wenn mehrere
Codeobjekte ohne zuvor erklärte fachliche Rolle aufeinandertreffen.

Die Masterarbeit sollte deshalb zuerst erklären, was eine Größe fachlich
bedeutet. Danach kann ihre mathematische Bezeichnung oder bei Bedarf der
Codebezeichner folgen. Bereits vereinbarte Parameter- und Variablennamen
werden nicht zur sprachlichen Glättung verändert. Reine Konfigurations- oder
Dateidetails sind nur nötig, wenn sie die Reproduzierbarkeit oder
Interpretation unterstützen.

## 11. Formeln und Algorithmen erklären

Mathematik wird in der Bachelorarbeit fast immer von Prosa begleitet.
In G, Zeilen 55-60, wird zunächst das Matchingproblem erläutert. Danach
werden Sequenzen und Dimensionen eingeführt. Auf den Algorithmus folgen
Erklärungen zur Initialisierung, zu den Rändern und zu den Nachbarn
(G, Zeilen 83-88). Die Bedingungen eines gültigen Pfades werden anschließend
einzeln auf ihre praktische Bedeutung zurückgeführt (G, Zeilen 103-123).

Auch zusammengesetzte Ausdrücke werden in Bestandteile zerlegt. Nach der
gewichteten Auswahlfunktion erklärt U, Zeilen 190-194, die Aufgabe der
einzelnen Summanden und deren Konsequenzen. Das ist eines der stärksten
übertragbaren Merkmale: Eine Formel wird nicht nur angegeben, sondern
lesbar gemacht.

Bei der Übertragung auf die DGL des sozio-klimatischen Modells sollte die
Reihenfolge lauten: Gegenstand und Größen einführen, Gleichung zeigen,
Terme erklären, Richtung oder Bedingung eines Effekts beschreiben und auf
Rückkopplungen oder Grenzen hinweisen, wenn sie die Interpretation ändern.
Eine mathematische Definition benötigt nicht zwingend ein Alltagsbeispiel;
bei schwer anschaulichen Zeitvergleichen oder Schwellen ist ein kleines
Beispiel dagegen stilistisch sehr passend.

## 12. Parameter werden über ihre Wirkung erklärt

Parameter werden nicht nur durch Symbol und Wertebereich definiert.
Der Text fragt häufig, was eine größere oder kleinere Einstellung bewirkt.
Besonders klar ist „Umso höher die einzelnen Gewichte sind, umso stärker
werden ungeeignete Werte bestraft“ (U, Zeile 191). Auch die DTW-Fenstergröße
wird über die zugelassene zeitliche Verzerrung erklärt
(U, Zeilen 198-202).

Die Masterarbeit soll dieses intuitive Erklären erhalten. Neu ist die
stärkere Bedeutung von Rückkopplungen: Ein größerer Vorfaktor kann einen
momentanen Term verstärken, ohne das langfristige Ergebnis in jedem
Szenario monoton zu verändern. Eine Größer-kleiner-Erklärung muss deshalb
zwischen direkter Wirkung bei festgehaltenem Zustand und dem Ergebnis einer
gekoppelten Simulation unterscheiden.

Ebenso gehören Einheit, Referenzgröße und Bezugszeitraum zur Erklärung.
Ein Zeitparameter in Jahren ist beispielsweise nicht automatisch ein
exakter zeitlicher Versatz. Verständlichkeit entsteht hier durch die
präzise Benennung des Mechanismus, nicht durch eine vereinfachende,
aber falsche Gleichsetzung.

## 13. Beispiele und anschauliche Fälle

Beispiele dienen überwiegend dazu, eine konkrete Schwierigkeit verständlich
zu machen: unterschiedliche Griffweiten beim Latziehen (U, Zeile 43),
Extrempunkte in Wiederholungen (U, Zeilen 112-120), verdeckte Gelenke bei
seitlicher Kameraposition (R, Zeilen 17-24) oder lokale Fehler trotz kleiner
mittlerer Abweichung (R, Zeilen 31-39).

Sie sind damit keine dekorativen Alltagsvergleiche. Der Fall verdeutlicht
eine Regel, begründet eine Entscheidung oder zeigt eine Grenze. Für die
Masterarbeit passen kurze Zahlenbeispiele zu Normanteilen und Schwellen
sowie ausgewählte Simulationsverläufe mit benanntem Mechanismus. Fiktive
Beispiele werden als solche kenntlich gemacht und nicht als Beobachtung
oder empirischer Beleg ausgegeben.

## 14. Abbildungen, Tabellen und Bildunterschriften

Die Prosa nennt häufig eine Darstellung und erläutert anschließend, was
daran relevant ist. Bei der Kostenmatrix wird zusätzlich erklärt, wie
einzelne Zellen entstehen; bei DTW-Abbildungen werden die Folgen der
Zuordnung beschrieben. Mehrere Bildunterschriften enthalten nicht nur
Objektnamen, sondern Leseschlüssel für Farben, Markierungen oder
Parameterwerte (G, Zeilen 92-100; U, Zeilen 120 und 273).

Die Ergebnistabellen werden durch Auswahlregeln eingegrenzt: R, Zeilen
86-89 und 148-151, erläutert, welche Parameterkombinationen und Frames
gezeigt beziehungsweise ausgewertet werden. Die Verbindung zwischen Text
und Darstellung ist damit fachlich und nicht nur referenziell.

Für die Masterarbeit sollen Bildunterschriften Variable, verglichene
Szenarien, Einheiten und entscheidende Bedingungen erkennbar machen. Der
Absatz benennt das zentrale Muster und seine Bedeutung. Nicht jeder
Tabelleneintrag wird im Text wiederholt. Die Formel „Figure X shows ...“
reicht allein noch nicht als Interpretation.

## 15. Literaturdarstellung und Belege

Der Literaturteil ist überwiegend **themen- und methodenorientiert**.
V gruppiert nach Posenschätzung, Posenbewertung und Zeitreihenanalyse.
Innerhalb dieser Bereiche werden Verfahren und Eigenschaften verglichen:
Modelle, Sensorarten, zwei- und dreidimensionale Ansätze, Referenzdaten und
Vergleichsmetriken. Mehrere Studien stehen häufig gemeinsam hinter einer
Aussage. Das Kapitel endet mit einer Einordnung der eigenen Kombination
(V, Zeilen 42-46).

Dieses Vorgehen ist näher an einer Synthese als an einer chronologischen
Liste unabhängiger Paper-Zusammenfassungen. Für Related Work sollte deshalb
auch die bereits geplante Paperreihenfolge als Argumentationsfolge genutzt
werden. Unterschiede in Normherkunft, Wirkungspfad, Aggregation, Dynamik
und Klima-Rückkopplung bilden die Vergleichsachsen.

Verbessert werden sollte die Reichweite pauschaler Literaturbehauptungen.
Aussagen wie „die meisten Arbeiten“, „nur in wenigen Arbeiten“ oder ein
„signifikanter Mangel“ benötigen eine erkennbare Grundlage und Abgrenzung.
Die Masterarbeit soll benennen, ob eine Aussage aus einem systematischen
Review, einer begrenzten Auswahl oder einer einzelnen Studie folgt.
Statistische Signifikanz wird nicht durch das Wort „significant“ für
„auffällig“ oder „wichtig“ ersetzt.

## 16. Ergebnisse, Unsicherheit und Interpretation

Eine Stärke ist die ausführliche Kontextualisierung der Tests. R, Zeilen
7-8, nennt Anzahl und Zusammensetzung der Videos und die fehlende
Ground-Truth-Grundlage für bestimmte Bewertungen. R, Zeilen 50-53,
grenzt den untersuchten Fehlertyp ein und berichtet Zähler, Gesamtzahl
und prozentualen Anteil. R, Zeilen 77-89, erläutert, weshalb ein
Ersatzdatensatz genutzt wird und welche Bewegungen darin vorkommen.

Der Text bietet zudem Erklärungen für unerwartete Befunde an. Die mögliche
Ursache einer geringeren Genauigkeit wird mit „vermutlich“ markiert
(R, Zeile 166). Eine zunächst plausible Interpretation von
Outdoor-Ergebnissen wird anhand der Bewegungsunterschiede hinterfragt
(R, Zeile 168). Dieses Prüfen konkurrierender Erklärungen soll erhalten
bleiben.

Nicht überall bleibt die Schlussfolgerung gleich eng an den Daten.
„die Posen gut klassifiziert werden“ (R, Zeile 43, Auszug)
ist weiter gefasst als die zuvor beschriebene eingeschränkte
Bewertungsgrundlage. Auch Ausdrücke wie „lediglich“ oder „deutlich“
werten Ergebnisse, ohne immer eine Vergleichsschwelle zu benennen.

Für die Masterarbeit werden deshalb Beobachtung, mathematische Folge,
Interpretation und empirische Übertragbarkeit klar getrennt. Eine
Simulation zeigt zunächst etwas über das Modell unter seinen Einstellungen.
Eine plausible Erklärung darf als solche formuliert werden. Sie wird
nicht allein durch ihre Anschaulichkeit zu einem nachgewiesenen Mechanismus
der realen Gesellschaft.

## 17. Kapitelbezogene Stilprofile

| Kapitel der Bachelorarbeit | Charakteristische Darstellung | Übertragung auf die Masterarbeit |
| --- | --- | --- |
| Zusammenfassung | Anlass, Problem, System, eingesetzte Verfahren, Anwendungspotenzial | Forschungsfrage, Vergleichsansatz, tatsächlich vorhandene Hauptergebnisse und begrenzte Schlussfolgerung; keine bloße Methodenankündigung |
| Einleitung | Konkrete Eingrenzung von allgemeiner Relevanz zu einer technischen Aufgabe | Von Normen und Klimaverhalten zur Frage nach dem Einfluss ihrer Formalisierung; Beitrag und Umfang früh benennen |
| Grundlagen | Begriffe, Alternativen, intuitive Erklärung, Mathematik und kleine Beispiele | Theory erklärt normative Mechanismen; Model erläutert die tatsächlich implementierten Gleichungen |
| Verwandte Arbeiten | Gruppierung nach Verfahren und relevanten Unterschiedeigenschaften | Studien nach Mechanismen und Modellannahmen synthetisieren; ihre Verbindung zur Vergleichsfrage herausarbeiten |
| Methodik und Umsetzung | Ablauf, konkrete Größen, Parameterwahl, Alternativen und Sonderfälle | Model und Methods trennen; Reproduzierbarkeit gewährleisten, ohne eine bloße Code-Nacherzählung zu schreiben |
| Ergebnisse und Diskussion | Testbedingungen, Darstellungen, Beobachtungen, Einschränkungen und Erklärungen | Ergebnisse zuerst berichten; weitergehende Interpretation im vorgesehenen Discussion-Kapitel entwickeln |
| Fazit und Ausblick | Zusammenführung des entwickelten Verfahrens, Zahlen, Grenzen und konkrete Folgearbeiten | Forschungsfragen beantworten und Grenzen zusammenführen; daraus folgt nicht automatisch ein zusätzliches, bisher nicht vereinbartes Kapitel |

Die Kapitelaufteilung der Bachelorarbeit wird nicht automatisch auf die
Masterarbeit übertragen. Maßgeblich bleibt
[Chapter-overview.md](Chapter-overview.md), insbesondere die bereits
getrennten Kapitel Theory, Model, Methods, Results und Discussion.

## 18. Was erhalten bleibt und was überarbeitet wird

| Merkmal | Entscheidung für die englische Masterarbeit |
| --- | --- |
| Problem vor Lösung erklären | Beibehalten |
| Entscheidungen mit Anforderungen verbinden | Beibehalten |
| Fachbegriffe früh verständlich machen | Beibehalten |
| Formeln und Parameter in Worten erläutern | Beibehalten |
| Kleine Beispiele mit konkreter Funktion | Beibehalten |
| Methoden nach Gemeinsamkeiten und Unterschieden vergleichen | Beibehalten und stärker synthetisieren |
| Untersuchungsbedingungen und Grenzen nennen | Beibehalten und konsequenter an Schlussfolgerungen binden |
| Unpersönliche Perspektive | Beibehalten, ohne ein starres Passivgebot |
| Häufige Kapitelankündigungen | Auf hilfreiche Orientierung begrenzen |
| Wiederholte Übergangswörter | Reduzieren, nicht durch wechselnde Füllwörter ersetzen |
| „Besagte“, „jene“ und unklare „dies“-Bezüge | Durch eindeutige Bezüge oder Fachbegriffe ersetzen |
| Sehr lange Methodensätze | Nach unterschiedlichen Aussagen und Bedingungen aufteilen |
| Stark wertende Verstärker | Durch konkrete Wirkung, Vergleich oder Größenordnung ersetzen |
| Unbelegte Reichweite von Literatur- und Ergebnisbehauptungen | Enger und nachprüfbar formulieren |
| Rechtschreibfehler, inkonsistente Bezeichner und versehentliche Kommas | Korrigieren; keine zu imitierenden Stilmerkmale |
| Bachelor-spezifische UI-, Fitness- und Datensatzdetails | Nur als Analysebelege verwenden; nicht in die Masterarbeit übernehmen |

## 19. Prägnante Belegstellen

Die Auszüge geben den Wortlaut mit lesbaren Umlauten wieder; es handelt
sich nicht um stilistisch überarbeitete Neufassungen.

| Beleg | Kurzer Auszug | Was daran charakteristisch ist |
| --- | --- | --- |
| E, Zeile 15 | „In dieser Arbeit werden besagte Fortschritte genutzt“ | Eigener Beitrag als zweckbezogene Nutzung vorhandener Forschung |
| G, Zeile 12 | „Aus diesem Grund wird in dieser Arbeit der skelettbasierte Ansatz genutzt“ | Entscheidung folgt aus einer vorher erklärten Anforderung |
| G, Zeile 58 | „Seien A und B die Sequenzen“ | Größen werden vor ihrer formalen Verwendung eingeführt |
| G, Zeile 84 | „Der Grund dafür ist, dass“ | Explizite Erläuterung auch scheinbar kleiner Implementierungsdetails |
| G, Zeile 119 | „Ein Pfad ist optimal, wenn die Summe seiner Kosten minimal ist.“ | Kurzer verständlicher Definitionssatz |
| U, Zeile 160 | „Im Folgenden werden die einzelnen Schritte des Algorithmus erläutert.“ | Sichtbare Orientierung vor einem komplexeren Ablauf |
| U, Zeile 191 | „Umso höher die einzelnen Gewichte sind, umso stärker werden ungeeignete Werte bestraft.“ | Parameter werden über ihre Wirkung erklärt |
| U, Zeile 228 | „Dies bietet außerdem den Vorteil einer erhöhten Transparenz und Nachvollziehbarkeit der Ergebnisse.“ | Methodenwahl wird mit einem praktischen Nutzen verbunden |
| U, Zeile 290 | „Dies kompensiert den zuvor genannten Nachteil.“ | Rückbindung der Lösung an ein zuvor benanntes Problem |
| R, Zeile 51 | „Kleinere Ungenauigkeiten wurden nicht betrachtet.“ | Aussagekraft einer Auswertung wird eingegrenzt |
| R, Zeile 166 | „liegt vermutlich“ | Erklärung wird als unsicher markiert |
| F, Zeile 14 | „Zukünftige Arbeiten könnten“ | Konkreter, modal formulierter Ausblick |

## 20. Abgeleitetes Zielprofil

Die englische Masterarbeit soll **klar, technisch konkret, erklärend und
begründend** klingen. Sie soll den Leser durch fachliche Zusammenhänge
führen und Formeln, Parameter und Ergebnisse nachvollziehbar machen.
Sie soll weder eine wörtliche Übersetzung deutscher Satzmuster noch eine
sprachlich aufgeblähte Fassung des Originals sein.

Der separate [Schreibleitfaden](Writing-style-guide.md) setzt dieses Profil
in praktische Regeln, Kapitelmuster und ausdrücklich als solche markierte
englische Formulierungsbeispiele um. Er kann die Analyse für das spätere
Schreiben ersetzen, wenn keine erneute Detailprüfung erforderlich ist.
