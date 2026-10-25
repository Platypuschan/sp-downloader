# sp-downloader

Container für vollständige, öffentlich abrufbare Folgen von southpark.de.
Standard: alle gelisteten Staffeln auf Deutsch und Englisch, beste verfügbare
Qualität, MKV und vorhandene deutsche/englische Untertitel.

Image: `ghcr.io/platypuschan/sp-downloader:latest` (Linux AMD64 und ARM64).
GitHub Actions testet und baut jeden Stand auf `main` und veröffentlicht zusätzlich
einen Tag `sha-<vollständige Commit-SHA>` zur eindeutigen Zuordnung zum Quellstand.

## Auf deinem Docker-Rechner starten

```bash
git clone https://github.com/Platypuschan/sp-downloader.git
cd sp-downloader
cp .env.example .env
# Bei Bedarf die Pfade in .env anpassen, dann:
docker compose pull
# Erst eine Folge je Sprache testen:
docker compose run --rm southpark download --seasons 1 --limit 1
# Alle verfügbaren Folgen und Staffeln:
docker compose run --rm southpark download
# Zusätzliche MKVs mit beiden Tonspuren erstellen:
docker compose run --rm southpark merge
```

Falls das GHCR-Paket privat ist, vor `pull` einmal mit einem GitHub-Token mit
`read:packages` anmelden (Passwort nicht in Compose oder Git speichern):

```bash
docker login ghcr.io -u DEIN_GITHUB_BENUTZERNAME
```

Das Image wird direkt von GHCR geladen; lokal bauen ist nicht nötig.
Der Container beendet sich nach Abschluss. Ein späterer Aufruf setzt Downloads
fort und überspringt fertig veröffentlichte Folgen ohne erneuten Streamabruf.

## Ordner per Environment konfigurieren

Beispiel für `.env` neben `compose.yaml`:

```dotenv
# Hostpfad, hier beispielhaft:
DATA_DIR=/mnt/media/southpark
# Pfade IM Container:
DOWNLOAD_DIR=/data/fertig
WORK_DIR=/data/arbeit
```

Compose bindet `DATA_DIR` auf `/data` ein. In diesem Beispiel erscheinen fertige
Folgen auf dem Host unter `/mnt/media/southpark/fertig`. Fragmente, Zwischenstände,
Kataloge und Fehlerberichte bleiben unter `/mnt/media/southpark/arbeit`.
Ohne `.env` sind die Hostpfade `./data/downloads` und `./data/work`.

`DOWNLOAD_DIR` und `WORK_DIR` sind Container-Umgebungsvariablen, auch ohne Compose.
`--output` und `--work-dir` überschreiben sie bei Bedarf für einen Lauf.

Beispiel auf dem Docker-Rechner, nachdem `/mnt/media/southpark` angelegt wurde:

```bash
docker run --rm --init -v /mnt/media/southpark:/data -e DOWNLOAD_DIR=/data/fertig -e WORK_DIR=/data/arbeit ghcr.io/platypuschan/sp-downloader:latest download
```

**Beide Ordner müssen auf demselben Dateisystem liegen und außerhalb voneinander
liegen.** Ein gemeinsamer Bind-Mount wie oben erfüllt das. Verschiedene
Dateisysteme werden vor dem Download mit einer Fehlermeldung abgewiesen.
Der Arbeitsordner muss persistent bleiben, damit Downloads fortgesetzt werden.
Für `--user UID:GID` müssen beide Ordner und der Elternordner des Zielordners für
diesen Benutzer beschreibbar sein.

## Nur fertig verarbeitete Folgen im Downloadordner

Download, Remux, Einbetten der Untertitel und Prüfung mit FFprobe laufen unter
`WORK_DIR`. Erst bei Erfolg wird der gesamte Folgenordner mit MKV, vorhandenen
Untertiteldateien und Metadaten atomar nach `DOWNLOAD_DIR` verschoben. Das gilt
auch für das Zusammenführen der Sprachfassungen. Es gibt keine teilweise
kopierten Folgen und keine `.part`-Dateien im Zielordner. Bei Fehler oder Abbruch
bleibt der Zwischenstand im Arbeitsordner; die übrigen Folgen können weiterlaufen.

Beispielstruktur (UUID bezeichnet die Inhalts-ID des Anbieters):

```text
DOWNLOAD_DIR/
  de/Staffel 01/UUID/South Park - S01E01 [UUID].mkv
  en/Staffel 01/UUID/South Park - S01E01 [UUID].mkv
  dual/Staffel 01/UUID/South Park - S01E01 [UUID].mkv
```

Ein `completed.json` je Folgenordner dokumentiert den Abschluss. Fertige Ordner
werden nicht überschrieben. Für einen bewussten erneuten Download den betreffenden
fertigen Folgenordner vorher aus dem Zielverzeichnis verschieben. Der Ablauf
ersetzt die Archive der früheren lokalen Prototypversion; alte flache Downloads
werden nicht automatisch übernommen oder gelöscht.

## Auswahl und Sprachen

```bash
docker compose run --rm southpark download --seasons 1,3-5
docker compose run --rm southpark download --languages de
docker compose run --rm southpark download --max-height 720
docker compose run --rm southpark catalog
docker compose run --rm southpark merge
```

`merge` erstellt zusätzliche Dateien unter `DOWNLOAD_DIR/dual`: deutsches Video,
deutsche und englische Tonspur sowie vorhandene eingebettete Untertitel beider
Fassungen. Die Sprachfassungen unter `de` und `en` bleiben erhalten.
Ohne erneute Kodierung; zusätzliche Dateien benötigen Speicher.

Die Zuordnung erfolgt über die Inhalts-UUID, **nicht** über die Folgennummer:
Die deutsche und englische Ausstrahlungsreihenfolge kann abweichen. Fehlende
Gegenstücke und Laufzeitunterschiede über 0,25 Sekunden werden gemeldet.
Gleiche Laufzeit garantiert keine identische Schnittfassung oder Synchronität;
Zweiton-Dateien vor Nutzung am Anfang und Ende anhören. Keine automatische Tonanpassung.

## Verfügbarkeit und Fehler

Es werden die aktuell gelisteten und am Standort abrufbaren Folgen geladen.
Nicht gelistete, entfernte oder gesperrte Folgen können nicht ergänzt werden.
Kein DRM- oder Geoblocking-Bypass. Untertitel werden nur übernommen, wenn der
Anbieter sie liefert; keine automatische Übersetzung oder Transkription.

Unter `WORK_DIR` liegen `catalog.json`, `errors.json` und `merge-errors.json`.
Fehlerberichte beziehen sich auf den letzten jeweiligen Lauf. Fehler bei einzelnen
Folgen stoppen nicht die übrigen Folgen, führen aber zu Exitcode 1. Fehler bei
Katalogabfragen stoppen vor dem Download. Gelistete, aber leere Staffeln werden
mit einer Warnung übersprungen. Ein vollständig leerer Katalog führt zum Abbruch.
Sperren verhindern parallele Läufe auf denselben Arbeits- oder Downloadordnern.

## Selbst bauen und prüfen

```bash
python3 -m unittest -v
docker build -t sp-downloader:local .
```

Abhängigkeiten stehen versioniert in `requirements.txt`. Bei Anbieteränderungen
yt-dlp gezielt aktualisieren und das Image neu bauen. Keine Paketänderungen beim Start.

[Prüfstand](VALIDATION.md) · [Entscheidungen](docs/decisions/0002-atomic-publication.md)

Quellen: [Offizieller Katalog](https://www.southpark.de/seasons/south-park),
[englischer Katalog](https://www.southpark.de/en/seasons/south-park),
[Anbieterhilfe zu den Sprachen](https://viacom.helpshift.com/hc/en/79-south-park/faq/2459-language-link-request-english-gsa/),
[yt-dlp-Extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/southpark.py).
