# Technische Entscheidungen — 2026-10-25

- Der Katalog kommt aus dem öffentlich ausgelieferten Seitenzustand
  `window.__DATA__` und dessen verlinkten Episode-Paginierungsendpunkten.
  Feste Staffellisten oder externe Episodendatenbanken würden neue Staffeln
  und regionale Abweichungen unzuverlässig abbilden.
- yt-dlp übernimmt Streamauswahl und Download, FFmpeg das verlustfreie Verpacken.
  Tonsprachen werden ausdrücklich ausgewählt: Die englische Seite kann auch
  spanische Tonspuren enthalten. pycryptodomex ermöglicht nativen HLS-Download
  mit Fragmentfortsetzung bei den vom Player bereitgestellten AES-128-Streams.
- Sprachfassungen werden separat archiviert. Eine gemeinsame MKV ist ein
  zusätzlicher Arbeitsschritt; die Originale bleiben erhalten. Inhalts-UUIDs
  gleichen unterschiedliche Ausstrahlungsreihenfolgen ab. Ein Laufzeitvergleich
  verhindert offensichtliche Fehlzuordnungen, beweist aber keine Synchronität.
- Anbieter-, Regionen- und Untertitelverfügbarkeit bestimmen den Umfang.
  Downloads erzeugen Fehlerberichte, damit fehlgeschlagene Folgen sichtbar bleiben.
  Es gibt keine automatische Veränderung von Netzstandort oder Zugriffsschutz.
