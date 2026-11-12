# Status der Dokumentationsbereinigung

- Der Nutzer hat die Punkte 1–14 am 21.10.2026 ausdrücklich freigegeben; sie sind umgesetzt und geprüft. Die Übersicht der Änderungen steht am Anfang von `ToDos.md`.
- Die gewünschte Erinnerung ist erledigt. Keine erneute Erinnerung oder Freigabeanfrage für diese abgeschlossene Liste erforderlich.
- Datierte Auswertungen behalten ihre historischen Ergebnisse und Parameterdefinitionen. Sie sind keine Beschreibung des jeweils aktuellen Modells.

# Literaturrecherchen

- Bei künftigen Paper-Recherchen hochwertige, wissenschaftlich gut rezipierte Quellen bevorzugen. Vor einer Empfehlung die Zitationszahl prüfen und mit Datenbank, eindeutigem Paper/DOI und Abrufdatum angeben (Nutzervorgabe vom 24.10.2026).
- Für Vergleiche möglichst dieselbe Zitationsdatenbank verwenden; unterschiedliche Datenbanken oder Publikationsversionen nicht ungekennzeichnet vermischen. Fehlende Daten nicht als null Zitationen ausgeben; Selbstzitate sind ohne gesonderte Bereinigung nicht ausgeschlossen.
- Zitationszahlen als Hinweis auf wissenschaftliche Rezeption nutzen und Publikationsalter, Fachgebiet, Publikationsstatus sowie die inhaltliche und methodische Qualität berücksichtigen. Hohe Zitationszahlen allein belegen keine hohe Qualität; niedrige Zahlen bei neuen Papers nicht automatisch als Qualitätsmangel bewerten.
- Relevanzratings getrennt von Zitationszahlen halten. Wenig zitierte Quellen kennzeichnen und ihre Verwendung begründen, besonders bei übernommenen Modellmechanismen. Es ist bislang keine feste Mindestzahl an Zitationen vereinbart; keine eigenmächtige Ausschlussgrenze einführen.
- Relevante Papers mit wenigen Zitationen dürfen ausdrücklich weiterhin vorgeschlagen werden. Sie bei jeder Empfehlung sichtbar als **wenig zitiert** kennzeichnen, die geprüfte Zitationszahl mit Quelle und Abrufdatum nennen und ihre Relevanz kurz begründen (Klarstellung des Nutzers vom 24.10.2026).

# Regeln für die Bearbeitung von Masterarbeit.docx

- Vor jedem Bearbeitungsschritt den aktuellen Dokumentstand committen und pushen. Erst nach erfolgreicher Sicherung im Remote-Repository mit der Dokumentbearbeitung beginnen. Falls keine neuen Dokumentänderungen zu committen sind, sicherstellen, dass der aktuelle Dokumentstand bereits committed und gepusht ist.
- Nur die konkret mit dem Nutzer besprochenen Abschnitte verändern. Änderungen außerhalb dieses Umfangs und größere Umstrukturierungen vorher abstimmen.
- Formatierungen ausschließlich mit ausdrücklicher Erlaubnis des Nutzers ändern. Vorhandene Formatvorlagen, Zitatformatierungen, Nummerierungen und Querverweise erhalten.
- Die Masterarbeit wird auf Englisch geschrieben. Dokumenttexte auf Englisch formulieren; Schreibstil und Terminologie des Nutzers beibehalten und klar, präzise und wissenschaftlich schreiben.
- Keine Quellen, Ergebnisse oder Begründungen erfinden. Unsichere Aussagen kennzeichnen und inhaltliche Fragen als Kommentare festhalten.
- Gleichungen und Modellbeschreibungen mit dem Code abgleichen; Widersprüche mit dem Nutzer besprechen.
- Textänderungen sichtbar und nachvollziehbar halten. Bei Sicherungs-Commits keine anderen offenen Repository-Änderungen ungefragt mit aufnehmen.

# Übersicht ausführbarer Skripte

- `SCRIPTS.md` ist die zentrale Übersicht der ausführbaren Skripte. Bei neuen Startskripten oder geänderten CLI-Argumenten, Standardwerten und Ausgabepfaden diese Datei im selben Arbeitsschritt aktualisieren.
- Jedes Skript erhält einen kurzen eigenen Bereich mit Aufruf und einer Tabelle aller anwendungsspezifischen CLI-Argumente. Historische Spezialauswertungen und Bibliotheksmodule ohne CLI ausdrücklich kennzeichnen.

# Sprache von Plots

- Alle neu erstellten Plots auf Englisch beschriften: Titel, Achsen, Legenden, Klassenbezeichnungen, Annotationen und Bildtexte.
- Bestehende Plots müssen nicht gesammelt umgestellt werden. Sobald ein Plot künftig bearbeitet wird, seine sichtbaren Beschriftungen im selben Arbeitsschritt auf Englisch umstellen. Modellparameter und Variablennamen beibehalten.
