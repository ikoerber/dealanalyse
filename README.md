# HubSpot Deal Data Fetcher

Automatischer Abruf von Deal-Daten aus HubSpot zur Datenqualitätsprüfung und anschließenden Analyse für Aufsichtsrat-Berichte.

## Übersicht

Dieses Skript ruft alle relevanten Deal-Daten aus HubSpot ab und exportiert sie in zwei CSV-Dateien:

1. **Deal Snapshot** - Aktueller Status aller Deals
2. **Deal History** - Vollständige Historie aller Änderungen an Deals

## Voraussetzungen

- Python 3.8 oder höher
- HubSpot Account mit Private App Access Token
- Lesezugriff auf Deals (`crm.objects.deals.read` Scope)

## Installation

### 1. Repository klonen / Verzeichnis navigieren

```bash
cd /Users/ikoerber/AIProjects/dealanalyse
```

### 2. Virtual Environment erstellen

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# oder
venv\Scripts\activate  # Windows
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 4. Konfiguration erstellen

Erstellen Sie eine `.env` Datei basierend auf dem Template:

```bash
cp .env.example .env
```

Öffnen Sie `.env` und tragen Sie Ihren HubSpot Access Token ein:

```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## HubSpot Access Token erstellen

1. Melden Sie sich in Ihrem HubSpot Account an
2. Navigieren Sie zu **Settings** > **Integrations** > **Private Apps**
3. Klicken Sie auf **Create a private app**
4. Geben Sie einen Namen ein (z.B. "Deal Analysis Tool")
5. Unter **Scopes** wählen Sie:
   - `crm.objects.deals.read`
6. Klicken Sie auf **Create app**
7. Kopieren Sie den generierten Access Token und fügen Sie ihn in Ihre `.env` Datei ein

## Verwendung

### Skript ausführen

```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Skript starten
python fetch_deals.py
```

### Ausgabe

Das Skript erstellt folgende Dateien im `output/` Verzeichnis:

#### 1. `deals_snapshot_YYYY-MM-DD.csv`

Enthält den aktuellen Status aller Deals:

| Spalte | Beschreibung |
|--------|--------------|
| deal_id | HubSpot Deal-ID |
| deal_name | Name des Deals |
| current_amount | Aktueller Deal-Wert |
| current_dealstage | Aktuelle Pipeline-Phase |
| current_closedate | Geplantes Abschlussdatum |
| create_date | Erstellungsdatum |
| has_history | Ob Historie verfügbar ist |
| fetch_timestamp | Zeitpunkt des Datenabrufs |

#### 2. `deal_history_YYYY-MM-DD.csv`

Enthält alle historischen Änderungen (eine Zeile pro Änderung):

| Spalte | Beschreibung |
|--------|--------------|
| deal_id | HubSpot Deal-ID |
| deal_name | Name des Deals |
| property_name | Geänderte Eigenschaft (dealstage, amount, closedate) |
| property_value | Wert zu diesem Zeitpunkt |
| change_timestamp | Zeitpunkt der Änderung |
| source_type | Quelle der Änderung (CRM_UI, API, etc.) |
| change_order | Chronologische Reihenfolge |

#### 3. `data_quality_issues_YYYY-MM-DD.csv` (optional)

Liste aller Datenqualitätsprobleme (fehlende Namen, Beträge, etc.)

### Fortschritt überwachen

Das Skript gibt Fortschrittsmeldungen in der Konsole aus. Für detaillierte Informationen können Sie die Log-Datei in Echtzeit verfolgen:

```bash
tail -f logs/fetch_deals_YYYY-MM-DD_HH-MM-SS.log
```

## Konfiguration

Alle Einstellungen können in der `.env` Datei angepasst werden:

| Variable | Beschreibung | Standard |
|----------|--------------|----------|
| HUBSPOT_ACCESS_TOKEN | HubSpot Private App Token | *erforderlich* |
| HUBSPOT_BASE_URL | HubSpot API Basis-URL | https://api.hubapi.com |
| START_DATE | Startdatum für Deal-Abruf | 2025-01-01 |
| RATE_LIMIT_DELAY | Verzögerung zwischen API-Aufrufen (Sekunden) | 0.11 |
| MAX_RETRIES | Maximale Anzahl Wiederholungen bei Fehlern | 3 |

## Features

### Rate Limiting

Das Skript respektiert die HubSpot API Rate Limits:
- 110ms Pause zwischen Requests (sicher unter dem Limit von 100 Requests/10 Sekunden)
- Automatische Wiederholung bei Rate-Limit-Fehlern mit exponentiellem Backoff

### Checkpoint-System

Bei großen Datenmengen speichert das Skript alle 100 Deals einen Checkpoint:
- Bei Unterbrechung (z.B. Netzwerkfehler): Einfach neu starten, es wird fortgesetzt
- Checkpoint-Datei: `output/.checkpoint_deals.json`
- Wird automatisch gelöscht nach erfolgreichem Abschluss

### Error Handling

- **401 (Authentifizierung)**: Klare Fehlermeldung mit Hinweis auf Token-Prüfung
- **429 (Rate Limit)**: Automatische Wiederholung mit Backoff
- **404 (Not Found)**: Warning-Log, Deal wird übersprungen
- **500+ (Server-Fehler)**: Wiederholung mit Backoff

### Logging

Zwei Log-Ebenen:
- **Konsole**: INFO-Level für wichtige Fortschrittsmeldungen
- **Datei**: Vollständiges DEBUG-Log in `logs/`

## Performance

Geschwindigkeit (abhängig von Deal-Anzahl):

| Deals | Geschätzte Dauer |
|-------|------------------|
| 100 | ~2 Minuten |
| 1.000 | ~20-30 Minuten |
| 10.000 | ~3 Stunden |

## Datenqualitäts-Checkliste

Nach dem Export sollten Sie folgende Punkte prüfen:

- [ ] Snapshot-CSV in Excel öffnen - deutsche Umlaute korrekt dargestellt?
- [ ] Deal-Anzahl entspricht HubSpot UI?
- [ ] Keine fehlenden Werte in `deal_id`, `deal_name`?
- [ ] `amount`-Werte numerisch und realistisch?
- [ ] `createdate` >= 2025-01-01?
- [ ] History-CSV chronologisch sortiert pro Deal?
- [ ] `change_timestamp` im ISO 8601 Format?
- [ ] `dealstage`-Werte entsprechen HubSpot-Pipeline?
- [ ] Mehrere History-Records für aktive Deals vorhanden?
- [ ] `data_quality_issues.csv` auf Warnungen prüfen

## Fehlerbehebung

### "Configuration Error: Required environment variable 'HUBSPOT_ACCESS_TOKEN' is not set"

- Prüfen Sie, ob die `.env` Datei existiert
- Stellen Sie sicher, dass `HUBSPOT_ACCESS_TOKEN` gesetzt ist
- Kein `#` Kommentarzeichen vor der Zeile

### "Authentication failed"

- Prüfen Sie, ob Ihr Access Token noch gültig ist
- Token könnte abgelaufen oder widerrufen sein
- Erstellen Sie ggf. einen neuen Token in HubSpot

### "No deals found"

- Prüfen Sie das `START_DATE` in der `.env` Datei
- Möglicherweise wurden keine Deals nach diesem Datum erstellt
- Prüfen Sie in HubSpot UI, ob Deals existieren

### Skript läuft sehr langsam

- Dies ist normal bei vielen Deals (Rate Limiting)
- Lassen Sie das Skript im Hintergrund laufen
- Nutzen Sie das Checkpoint-System bei Bedarf

## Nächste Schritte

Nach erfolgreicher Datenprüfung:

1. **Datenqualität verbessern**: Fehlende oder ungültige Daten in HubSpot korrigieren
2. **Pipeline-Stages dokumentieren**: Welche `dealstage`-Werte gibt es?
3. **Analyse-Kategorien definieren**: Mapping von Stages zu Bewegungstypen (WON, LOST, etc.)
4. **Phase 2 starten**: Entwicklung des monatlichen Analyse-Reports

## Projektstruktur

```
dealanalyse/
├── .env                    # Ihre Konfiguration (nicht committen!)
├── .env.example           # Konfigurations-Template
├── .gitignore            # Git-Ignorierungen
├── requirements.txt      # Python-Dependencies
├── README.md            # Diese Datei
│
├── src/
│   ├── __init__.py
│   ├── config.py         # Konfigurationsmanagement
│   ├── hubspot_client.py # HubSpot API-Client
│   ├── data_fetcher.py   # Daten-Orchestrierung
│   └── csv_writer.py     # CSV-Export
│
├── output/              # CSV-Ausgaben (git-ignoriert)
│   └── .gitkeep
│
├── logs/                # Log-Dateien (git-ignoriert)
│   └── .gitkeep
│
└── fetch_deals.py       # Hauptskript
```

## Lizenz

Internes Tool für Sales-Analyse.

## Support

Bei Fragen oder Problemen:
1. Prüfen Sie die Log-Dateien in `logs/`
2. Prüfen Sie die `data_quality_issues.csv` Datei
3. Konsultieren Sie die HubSpot API-Dokumentation: https://developers.hubspot.com/docs/api/overview
