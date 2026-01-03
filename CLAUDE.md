HubSpot Deal Reporting Service (AR Report)
Dieses Dokument beschreibt die Anforderungen und die technische Umsetzung für einen automatisierten Sales-Report. Ziel ist es, monatliche Kennzahlen (Revenue, Pipeline Growth, Conversion) sowie konkrete Veränderungen einzelner Deals aus HubSpot zu extrahieren, um dem Aufsichtsrat (AR) die Performance und Dynamik des Sales-Teams darzustellen.

📋 Inhaltsverzeichnis
Business Case & Zielsetzung

Technische Voraussetzungen

API Endpunkte & Datenabruf

Logik der Daten-Aggregation (Monthly Buckets)

Feature: Deal Movement & Slippage (Veränderungsanalyse)

Output Format

Business Case & Zielsetzung
Der AR benötigt einen monatlichen Bericht ("Month-over-Month"), der folgende Fragen beantwortet:

KPIs: Umsatz, Pipeline-Wachstum und Win-Rates pro Monat.

Deal-Tracking: Was ist konkret aus Deals geworden, die im Vormonat noch in der Pipeline waren? (Wurden sie gewonnen, verloren oder verschoben?)

Transparenz: Identifikation von "Leichen" im CRM (Deals, die sich nicht bewegen).

Das Skript soll am 1. eines jeden Monats laufen und die Daten des vergangenen Monats/Jahres analysieren.

Technische Voraussetzungen
API Standard: HubSpot CRM API v3

Auth Methode: Private App Access Token (Bearer Token)

Benötigte Scopes: crm.objects.deals.read

API Endpunkte & Datenabruf
1. Haupt-Abruf: Search API & Details

Wir benötigen eine Kombination aus Suche und Detail-Historie, um Veränderungen sichtbar zu machen.

Endpoint: POST /crm/v3/objects/deals/search

Filter: Alle Deals, die im Berichtszeitraum (z.B. letztes Jahr bis heute) entweder erstellt wurden ODER abgeschlossen wurden ODER noch offen sind.

Request Body

JSON
{
  "filterGroups": [
    {
       "filters": [
         { "propertyName": "createdate", "operator": "GTE", "value": "1735689600000" } // Ab 01.01.2025
       ]
    }
    // Weitere Filterlogik um auch offene alte Deals zu erfassen
  ],
  "properties": [
    "dealname", "amount", "dealstage", "closedate", "createdate", "hs_object_id"
  ]
}
2. Historien-Abruf (Crucial für AR-Fragen)

Um zu beantworten "Was war letzten Monat?", müssen wir für die relevanten Deals die Historie abrufen.

Endpoint: GET /crm/v3/objects/deals/{dealId}?propertiesWithHistory=dealstage,amount,closedate

Logik: Iteriere über die Liste der Deals und rufe diesen Endpunkt auf (Batch-Anfragen nutzen, falls möglich, oder Rate-Limiting beachten).

Logik der Daten-Aggregation (Monthly Buckets)
Aggregation der KPI-Zahlen für die High-Level-Übersicht:

Revenue (Won): Summe amount aller Deals mit dealstage == closedwon im jeweiligen Monat.

Pipeline Generation: Summe amount aller Deals mit createdate im jeweiligen Monat.

Win Rate: (Won Deals / Total Created Deals) * 100.

Feature: Deal Movement & Slippage (Veränderungsanalyse)
Dieser Teil ist essenziell, um die Frage "Was ist aus Deal XYZ geworden?" zu beantworten.

Die Logik ("Snapshot-Vergleich")

Das Skript muss für jeden Deal prüfen, wo er sich am Ersten des Monats befand und wo er sich am Letzten des Monats befand.

Algorithmus:

Definiere Berichtsmonat (z.B. Februar).

Prüfe die propertiesWithHistory für dealstage:

Status Start: Welchen Wert hatte dealstage am 01.02. um 00:00 Uhr?

Status Ende: Welchen Wert hatte dealstage am 28.02. um 23:59 Uhr?

Kategorisiere die Bewegung:

WON: Status Start != Won -> Status Ende == Won.

LOST: Status Start != Lost -> Status Ende == Lost.

ADVANCED: Deal ist eine Phase weitergerutscht (z.B. "Qualifikation" -> "Angebot").

STALLED: Status Start == Status Ende (Deal hat sich den ganzen Monat nicht bewegt -> Warnsignal für AR!).

PUSHED: Prüfe propertiesWithHistory für closedate. Hat sich das geplante Abschlussdatum im Laufe des Monats in die Zukunft verschoben?

Output Format
Das System generiert zwei CSV-Dateien sowie ein interaktives Streamlit Dashboard.

Datei 1: kpi_overview.csv (Management Summary)

Monat	Jahr	Pipeline Neu (€)	Revenue Won (€)	Win Rate (%)
Januar	2025	500.000	120.000	24%
...	...	...	...	...

Datei 2: deal_movements_detail.csv (Erweiterte Operative Analyse)

Diese Liste erklärt die Details hinter den Zahlen mit erweiterten Spalten:

Spalten:
- Deal ID, Deal Name
- Monat, Jahr
- Status (Monatsanfang), Status (Monatsende)
- Bewegungstyp (WON, LOST, ADVANCED, STALLED, etc.)
- Wert Monatsanfang (€), Wert Monatsende (€)
- Wertänderung (€), Wertänderung (%)
- Zieldatum Anfang, Zieldatum Ende
- Tage verschoben
- Tage in aktueller Phase
- Kommentar

Interaktives Dashboard
Das Streamlit Dashboard (dashboard_monthly.py) bietet eine Excel-ähnliche Side-by-Side Ansicht:

Features:
1. **Monatsvergleich**: Zwei beliebige Monate nebeneinander vergleichen
2. **Chronologische Navigation**: Dropdown-Menüs mit chronologisch sortierten Monaten
3. **Farbcodierung**:
   - 🟢 Grün: Gewonnene Deals
   - 🔴 Rot: Verlorene Deals
   - 🔵 Blau: Phase-Änderungen
4. **HubSpot Integration**: Klickbare Links zu Deals direkt in HubSpot
5. **Vollständiger Zustand**: Zeigt ALLE aktiven Deals, nicht nur jene mit Änderungen
6. **Statistiken**: Anzahl Gesamt, Gewonnen, Verloren, Neu
7. **CSV Export**: Download der Vergleichsdaten

Ausführung:

# 1. Daten abrufen und analysieren
python analyze_deals.py

# 2. Dashboard starten
streamlit run dashboard_monthly.py

Konfiguration:
- HubSpot Portal ID in dashboard_monthly.py anpassen (Zeile 13)
- API Token in .env Datei hinterlegen

Definition of Done

[x] KPI-Berechnung (Aggregation) korrekt implementiert
[x] Historien-Abruf (propertiesWithHistory) für Deals implementiert
[x] Logik zur Erkennung von Status-Änderungen funktioniert
[x] Erkennung von verschobenen Abschlussdaten (closedate changes)
[x] Export beider CSV-Dateien mit erweiterten Spalten
[x] Interaktives Streamlit Dashboard mit Side-by-Side Vergleich
[x] HubSpot-Integration mit klickbaren Links
[x] Chronologische Sortierung und Navigation
[x] Vollständige Zustandsrekonstruktion für alle aktiven Deals
