# Aktueller Prüfstand 2026-10-26

Neuer Stand in `Platypuschan/sp-downloader`:

- 15 automatisierte Tests erfolgreich, einschließlich fehlgeschlagener Downloads,
  Verarbeitung, Veröffentlichung, Wiederaufnahme nach fehlgeschlagenem Rename,
  Dateisystem-/Pfadkonflikten, Environment-Konfiguration und konkurrierenden Läufen.
- Lokaler Podman-Build erfolgreich.
- Live-Test S01E01 bei 360p: DE und EN vollständig geladen, im separaten Arbeitsordner
  verarbeitet und danach inklusive Begleitdateien veröffentlicht. Während EN noch
  Fragmente im Arbeitsordner schrieb, war im Ziel nur die fertige DE-Folge sichtbar.
  Keine Fragmente im Ziel. Explizit konfigurierte Pfade: DOWNLOAD_DIR=/data/fertig,
  WORK_DIR=/data/arbeit. Beide Fehlerberichte leer.
- Dual-MKV erfolgreich im Arbeitsordner erstellt und anschließend veröffentlicht.
- Wiederholter Downloadlauf überspringt beide fertigen Folgen ohne Streamabruf.

GitHub Actions führt Tests aus, baut AMD64/ARM64 und veröffentlicht auf `main`.
Anschließend lädt der Workflow das Image über seinen Commit-Tag aus GHCR und
prüft es mit echten, lokal erzeugten FFmpeg-Testmedien (DE/EN-Veröffentlichung
und Zusammenführen der Tonspuren). Maßgeblich ist der CI-Lauf des jeweiligen
Commits unter https://github.com/Platypuschan/sp-downloader/actions .
Die Einrichtung des Workflows allein ist kein Nachweis eines erfolgreichen CI-Laufs.

Keine produktive Installation. Die hörbare Synchronität und mögliche
Schnittunterschiede der Anbieterfassungen bleiben ungeprüft.

## Historischer Stand des lokalen Prototyps (2026-10-25/26)

Lokal unter Linux mit Podman, nicht mit Docker Compose ausgeführt:

- Image erfolgreich gebaut: Python 3.13, yt-dlp 2026.10.21,
  pycryptodomex 3.24.1, FFmpeg aus Debian Bookworm.
- Fünf automatisierte Tests erfolgreich: Katalogpaginierung und Filterung,
  fehlende Staffeln/leerer Katalog, Eingaben/Hostbegrenzung, Zuordnung über
  Inhalts-ID bei abweichender Folgennummer, Ablehnung abweichender Laufzeiten.
- Live-Katalog vollständig durchlaufen: 331 Folgen pro Sprache, 662 Einträge,
  alle 331 Inhalts-IDs stimmen zwischen DE und EN überein. Staffel 29 ist
  auswählbar, hat am Prüfstand aber keine gelisteten Folgen.
- S01E01 vollständig in beiden Sprachen bei 360p heruntergeladen. Deutsch
  erfolgreich über Archiv übersprungen. Englischen Fragmentdownload durch
  Container-Stopp unterbrochen und anschließend erfolgreich fortgesetzt.
- MKV mit deutschem Video, deutscher und englischer AAC-Tonspur und englischen
  WebVTT-Untertiteln erzeugt und mit FFprobe geprüft: 1319,985 Sekunden.
  Deutsche Untertitel werden bei dieser Testfolge nicht angeboten.

Zu diesem historischen Stand: keine CI, kein Remote des Zielprojekts, keine Veröffentlichung und kein
produktives Deployment. Die restlichen 330 Folgen wurden nur im Katalog
geprüft, nicht heruntergeladen. Die hörbare Synchronität und mögliche
Schnittunterschiede wurden nicht geprüft. Katalogzählung belegt keine
vollständige Sammlung aller jemals ausgestrahlten Episoden.
