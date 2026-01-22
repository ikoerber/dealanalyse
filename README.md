# HubSpot Multi-Object Reporting Service

Automatisierte HubSpot-Datenanalyse und Report-Generierung für Aufsichtsrat-Berichte. Mit Multi-Object-Architecture für Deals, Contacts und Companies.

## Übersicht

Umfassendes Reporting-System mit drei Hauptkomponenten:

1. **Interactive Dashboard** - Streamlit Web-App für monatlichen Deal-Vergleich
2. **PDF Report Generator** - Automatisierte Board-Reports (2 separate PDFs)
3. **Multi-Object Architecture** - Erweiterbare, config-basierte Architektur für HubSpot-Objekte

### Hauptfeatures

- ✅ **Historische HubSpot-Wahrscheinlichkeiten**: Verwendet echte `hs_forecast_probability` aus der Deal-History
- ✅ **Wahrscheinlichkeitsänderungs-Tracking**: Status-Spalte zeigt Änderungen an (z.B. "🔵 Negotiation → Proposal (Prob: 75% → 40%)")
- ✅ **Split-PDFs**: Separate PDFs für Pipeline-Vergleich und Zusatzberichte
- ✅ **Time-Travel Rekonstruktion**: Rekonstruiert Wahrscheinlichkeit zum Monatsende für genauen historischen Vergleich
- ✅ **Selektive PDF-Generierung**: `--pdf-parts 1|2` für schnellere Iterationen

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

### 1. Interactive Dashboard

```bash
source venv/bin/activate
streamlit run dashboard_monthly.py
```

Öffnet Web-Interface auf `http://localhost:8501` mit:
- Side-by-side Monatsvergleich
- Pipeline-Metriken mit gewichteten Werten
- Filterbare Deal-Tabellen
- Clickable HubSpot Deal-Links

### 2. PDF Report Generation

```bash
source venv/bin/activate

# Komplette Pipeline (Fetch + Analyze + 2 PDFs)
python generate_report.py

# Schnelle Iteration (nutzt vorhandene Daten)
python generate_report.py --skip-fetch --skip-analysis

# Nur bestimmte PDFs generieren
python generate_report.py --pdf-parts 1  # Nur Pipeline-Vergleich
python generate_report.py --pdf-parts 2  # Nur Zusatzberichte

# Spezifische Monate vergleichen
python generate_report.py --months "Dezember 2025" "Januar 2026"
```

### 3. Data Pipeline (Manuell)

```bash
# Legacy Skripte (noch voll funktionsfähig)
python fetch_deals.py        # Fetch von HubSpot
python fetch_contacts.py     # Contact-Daten abrufen
python analyze_deals.py      # Analyse generieren
python analyze_contacts.py   # Contact-Funnel-Analyse
```

### Ausgabe

#### PDF Reports (`output/reports/`)

**Zwei separate PDFs:**

1. **`1_pipeline_vergleich_[MonthA]_vs_[MonthB]_YYYY-MM-DD.pdf`**
   - Seite 1: Metriken-Übersicht (Pipeline-Vergleich, Abgeschlossene Deals)
   - Seite 2+: Detail-Tabelle mit allen Deals (20 Deals/Seite, Landscape A4)
   - Historische HubSpot-Wahrscheinlichkeiten
   - Wahrscheinlichkeitsänderungen im Status

2. **`2_zusatzberichte_[MonthA]_vs_[MonthB]_YYYY-MM-DD.pdf`**
   - Contact-Funnel (MQL/SQL Conversion)
   - 2025 Deals Übersicht mit Quellen und Ablehnungsgründen

#### CSV Snapshots (`output/`)

- `deals_snapshot_YYYY-MM-DD.csv`: Aktueller Deal-Status (16+ Felder inkl. `hs_forecast_probability`)
- `deal_history_YYYY-MM-DD.csv`: Vollständige Änderungshistorie inkl. `hs_deal_stage_probability` Änderungen
- `contacts_snapshot_YYYY-MM-DD.csv`: Contact-Daten mit Company-Assoziationen
- `companies_snapshot_YYYY-MM-DD.csv`: Company-Daten
- `owners_YYYY-MM-DD.json`: Owner ID → Name Mapping

#### CSV Reports (`output/reports/`)

- `kpi_overview_YYYY-MM-DD.csv`: Monatliche KPI-Zusammenfassung
- `deal_movements_detail_YYYY-MM-DD.csv`: Deal-by-Deal Bewegungslog
- `contacts_kpi_YYYY-MM-DD.csv`: Contact-Funnel KPIs
- `sql_details_YYYY-MM-DD.csv`: SQL Details letzter Monat
- `source_breakdown_YYYY-MM-DD.csv`: Lead-Quellen Matrix

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

## Schlüssel-Features

### Historische HubSpot-Wahrscheinlichkeiten

Das System verwendet **echte HubSpot Forecast-Wahrscheinlichkeiten** aus der Deal-History statt fixer Phasen-basierter Schätzungen:

**Funktionsweise:**
1. Lädt `deal_history_*.csv` mit allen `hs_deal_stage_probability` Änderungen
2. Berechnet für jeden Monatsvergleich den Monatsende-Zeitstempel (z.B. 31. Dez, 23:59:59 UTC)
3. Rekonstruiert Wahrscheinlichkeit für jeden Deal zu diesem spezifischen Zeitpunkt
4. Erstellt separate `HubSpot_Probability_A` und `HubSpot_Probability_B` Spalten
5. Verwendet diese historischen Werte für gewichtete Pipeline-Berechnungen

**Vorteile:**
- ✅ Genaue historische Forecasts (verwendet tatsächliche Werte von damals)
- ✅ Erfasst manuelle Wahrscheinlichkeitsanpassungen in HubSpot
- ✅ Unterschiedliche Wahrscheinlichkeiten für gleiche Phase (z.B. Negotiation: 75% → 90%)
- ✅ Fallback auf Phasen-basierte Wahrscheinlichkeiten wenn History nicht verfügbar

### Wahrscheinlichkeitsänderungs-Tracking

Status-Spalte zeigt Wahrscheinlichkeitsänderungen > 5% an:
- Mit Phasenwechsel: `🔵 Qualification → Negotiation (Prob: 20% → 90%)`
- Ohne Phasenwechsel: `📊 Prob: 50% → 75%`

### Split-PDF-Generierung

Zwei separate PDFs für bessere Organisation:
- **PDF 1**: Pipeline-Vergleich (schnelle Board-Präsentation)
- **PDF 2**: Zusatzberichte (detaillierte Analysen)
- Selektive Generierung mit `--pdf-parts 1|2` für schnellere Iterationen

### Multi-Object Architecture

Config-basiertes System für erweiterbare HubSpot-Objekt-Unterstützung:
- ✅ Deals (mit Historie und Contact-Enrichment)
- ✅ Contacts (MQL/SQL Funnel)
- ✅ Companies (Customer Pipeline)
- Neue Object-Types in ~10 Minuten hinzufügen

### Rate Limiting & Checkpoint System

- 110ms Pause zwischen Requests (respektiert HubSpot API Limits)
- Automatische Wiederholung bei Rate-Limit-Fehlern
- Checkpoint bei großen Datenmengen (automatische Fortsetzung bei Unterbrechung)
- Object-spezifische Checkpoints (`.checkpoint_deals.json`, `.checkpoint_contacts.json`, etc.)

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
├── .env                           # Konfiguration (nicht committen!)
├── .env.example                   # Konfigurations-Template
├── requirements.txt               # Python-Dependencies
├── README.md                      # Diese Datei
├── CLAUDE.md                      # Detaillierte Entwickler-Dokumentation
│
├── generate_report.py             # Haupt-Pipeline (Fetch + Analyze + PDF)
├── dashboard_monthly.py           # Streamlit Dashboard
├── fetch_deals.py                 # Legacy Deal-Fetcher
├── fetch_contacts.py              # Legacy Contact-Fetcher
├── analyze_deals.py               # Legacy Deal-Analyzer
├── analyze_contacts.py            # Legacy Contact-Analyzer
├── demo_phase2_architecture.py    # Architecture Demo
│
├── config/
│   ├── object_types.json          # Object Type Definitions (Deals, Contacts, Companies)
│   ├── report_definitions.json    # Report Configurations
│   └── stage_mapping.json         # Pipeline Stage Mappings
│
├── src/
│   ├── core/                      # Core Framework (Phase 1 & 2)
│   │   ├── object_registry.py     # Object Type Registry
│   │   ├── checkpoint_manager.py  # Generic Checkpoint System
│   │   ├── base_fetcher.py        # Abstract Fetcher Base Class
│   │   └── base_analyzer.py       # Abstract Analyzer Base Class
│   │
│   ├── fetchers/                  # Specialized Fetchers
│   │   ├── deals_fetcher.py       # DealsFetcher with history
│   │   ├── contacts_fetcher.py    # ContactsFetcher with companies
│   │   └── companies_fetcher.py   # CompaniesFetcher
│   │
│   ├── reporting/                 # Reporting Layer
│   │   ├── pdf_generator.py       # PDF Generation (2 separate PDFs)
│   │   └── report_registry.py     # Report Definition Registry
│   │
│   ├── analysis/                  # Analysis Modules
│   │   ├── monthly_analyzer.py    # Monthly Deal State Reconstruction
│   │   ├── stage_mapper.py        # Stage ID → Name Mapping
│   │   ├── movement_categorizer.py # Deal Movement Categorization
│   │   └── deals_2025_analyzer.py # 2025 Deals Overview
│   │
│   └── utils/                     # Utilities
│       └── formatting.py          # German Number/Date Formatting
│
├── output/                        # Generated Files (git-ignored)
│   ├── deals_snapshot_*.csv       # Deal Snapshots
│   ├── deal_history_*.csv         # Deal History (inkl. hs_deal_stage_probability)
│   ├── contacts_snapshot_*.csv    # Contact Snapshots
│   ├── companies_snapshot_*.csv   # Company Snapshots
│   ├── owners_*.json              # Owner Mappings
│   └── reports/                   # Generated Reports
│       ├── 1_pipeline_vergleich_*.pdf
│       ├── 2_zusatzberichte_*.pdf
│       └── *.csv                  # CSV Reports
│
└── logs/                          # Log Files (git-ignored)
```

## Lizenz

Internes Tool für Sales-Analyse.

## Support

Bei Fragen oder Problemen:
1. Prüfen Sie die Log-Dateien in `logs/`
2. Prüfen Sie die `data_quality_issues.csv` Datei
3. Konsultieren Sie die HubSpot API-Dokumentation: https://developers.hubspot.com/docs/api/overview
