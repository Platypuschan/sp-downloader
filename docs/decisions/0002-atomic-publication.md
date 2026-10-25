# Fertige Folgen atomar veröffentlichen — 2026-10-26

Nutzerauftrag: Projekt in `Platypuschan/sp-downloader` verwenden, Image abrufbar
veröffentlichen, Downloadordner per Environment konfigurieren und nur komplett
verarbeitete Folgen in diesen Ordner verschieben.

`DOWNLOAD_DIR` enthält abgeschlossene Folgen. `WORK_DIR` enthält sämtliche
Downloadfragmente, Medienverarbeitung, Kataloge und Fehlerberichte. Die Pfade
sind getrennt und liegen auf demselben Dateisystem. Das wird vor jedem Lauf
geprüft. Eine Folge einschließlich ihrer Begleitdateien wird als Verzeichnis
mit einem Rename veröffentlicht; ein dateisystemübergreifendes Kopieren würde
teilweise sichtbare Dateien verursachen und wird deshalb nicht angeboten.

Nach erfolgreichem yt-dlp-/FFmpeg-Lauf prüft FFprobe Video, Ton und eine positive
Laufzeit. Übrig gebliebene Downloadfragmente verhindern die Veröffentlichung.
Bei Dual-MKV werden mindestens zwei Tonspuren verlangt. Erst danach wird ein
Abschlussnachweis im Arbeitsordner geschrieben und der Folgenordner verschoben.
Ein Abbruch zwischen Nachweis und Rename kann ohne erneuten Download fortgesetzt
werden. Die fertige Folge mit Nachweis ersetzt das frühere yt-dlp-Archiv,
das bereits vor einem möglicherweise fehlgeschlagenen Verschieben den Download
als erfolgreich eingetragen hätte.

Sperren liegen außerhalb des Downloadordners. Sowohl gemeinsam genutzte
Arbeitsordner als auch gemeinsam genutzte Zielordner werden gesperrt.

Die Prüfungen bestätigen Verarbeitung und Containerstruktur. Sie sind keine
vollständige Dekodierprüfung aller Frames und kein Nachweis hörbarer Synchronität.

GitHub Actions testet und veröffentlicht auf `main` AMD64-/ARM64-Images in GHCR.
PR-Läufe bauen ohne Veröffentlichung. Workflow-Abhängigkeiten sind auf Commits
fixiert. Ein `sha-<Commit>`-Tag erlaubt die Zuordnung zum gebauten Quellstand.
