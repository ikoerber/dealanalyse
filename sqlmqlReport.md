# Spezifikation: Contact Reporting & Funnel Analytics

Dieses Dokument definiert die Erweiterung des bestehenden HubSpot-Reporting-Services (bisher Deals) um eine **Lead-Entwicklungs-Analyse** (Contacts).

**Zielgruppe:** Entwickler & Data Analysts
**Status:** Finalized Specification v1.2 (2026-01-15) - Quellen-Übersicht als historische Matrix (12 Monate)
**Kontext:** Erweiterung der Python-Architektur (`fetch -> analyze -> report`).

---

## 1. Management Summary (Zielsetzung)
Für den Aufsichtsrat soll ein Report erstellt werden, der die **Qualität und Geschwindigkeit** der Lead-Bearbeitung transparent macht. Zentrale Fragen: *"Füllt das Marketing die Pipeline schnell genug?"* und *"Welche konkreten Firmen haben wir letzten Monat als SQL gewonnen?"*

**Deliverable:** Kombinierter PDF-Report mit Deal- UND Contact-Analyse in einem Dokument.

---

## 2. Kern-Anforderungen (KPIs) - Phase 1

Das Reporting muss folgende fünf Kernbereiche abdecken:

### A. Volumen (Menge)
* **Definition:** Anzahl neuer MQLs und SQLs pro Kalendermonat.
* **Analysezeitraum:** Letzte **12 abgeschlossene Monate**.
* **Visualisierung:** Tabelle mit monatlicher Aufschlüsselung (in PDF).
* **Datenquelle:** Contacts mit `hs_v2_date_entered_marketingqualifiedlead` bzw. `hs_v2_date_entered_salesqualifiedlead` im jeweiligen Monat.

### B. Konvertierung (Qualität)
* **Definition:** Conversion Rate (MQL → SQL).
* **Formel:** $\frac{\text{Anzahl SQLs (konvertiert im Zeitraum)}}{\text{Anzahl MQLs (erstellt im Zeitraum)}} \times 100$
* **Wichtig:** Zählt nur MQLs und SQLs, die **im selben Berichtsmonat** erstellt/konvertiert wurden.

### C. Durchlaufzeit (Velocity)
* **Definition:** Ø Dauer in Tagen von MQL → SQL.
* **Logik:** Zeitstempel-Differenz: `hs_v2_date_entered_salesqualifiedlead` - `hs_v2_date_entered_marketingqualifiedlead`.
* **Berechnung:** Nur für SQLs, die **im Berichtsmonat konvertiert** sind (nicht für historische SQLs).
* **Ausgabe:** Durchschnitt in Tagen (Dezimalstelle).

### D. SQL-Detail-Liste (Transparenz)
* **Ziel:** Zeige die konkreten Firmen/Kontakte, die **letzten Monat** zu SQL wurden.
* **Definition "Letzter Monat":** Abgeschlossener Kalendermonat vor dem aktuellen (z.B. wenn heute 10. Jan 2026 → Dezember 2025).
* **Inhalt:** Tabelle mit Spalten:
    1. **Datum:** Wann wurde der Kontakt SQL? (`hs_v2_date_entered_salesqualifiedlead`)
    2. **Kontakt:** `firstname` + `lastname`
    3. **Firma:** Name der **Primary Company** (via Associations API)
    4. **Quelle:** Lead-Quelle (`ursprungliche_quelle__analog_unternehmensquelle_`)
* **Filter:** Nur SQLs mit `hs_v2_date_entered_salesqualifiedlead` im letzten abgeschlossenen Monat.
* **Fallback:** Falls keine Company verknüpft: Anzeige "–". Falls keine Quelle: Anzeige "–".

### E. Quellen-Übersicht (Lead-Qualität nach Kanal - Historische Entwicklung)
* **Ziel:** Zeige Verteilung der MQLs und SQLs nach Lead-Quelle über **letzte 12 abgeschlossene Monate**.
* **Analysezeitraum:** Letzte **12 abgeschlossene Monate** (analog zu KPI A).
* **Inhalt:** Matrix-Tabelle gruppiert nach `ursprungliche_quelle__analog_unternehmensquelle_`:
    - **Zeilen:** Lead-Quellen
    - **Spalten:** Monate (Jul MQL/SQL | Aug MQL/SQL | ... | Dez MQL/SQL | Gesamt MQL/SQL | Conv.Rate)
    - **Format pro Monat:** "X MQL / Y SQL" (z.B. "10/2" = 10 MQLs, 2 SQLs)
    - **Gesamt-Spalte:** Summe aller MQLs und SQLs über 12 Monate
    - **Conv.Rate:** Berechnet über gesamten Zeitraum (Gesamt SQLs / Gesamt MQLs × 100)
* **Filter:** Alle Contacts mit `mql_date` oder `sql_date` in den letzten 12 Monaten.
* **Sortierung:** Nach Gesamt-Anzahl SQLs absteigend (wichtigste Quellen zuerst).
* **Fallback:** Falls Quelle leer → Gruppiere unter "Unbekannt".
* **Visualisierung:** Kompakte Matrix wie Referenz-Tabelle (siehe Beispiel).

---

## 3. Erweiterte Reporting-Module (Phase 2 - Später)

**Status:** Zurückgestellt. Erst nach erfolgreicher Implementierung von Phase 1 (KPIs A-E).

### Modul 1: Lead-Verrottungs-Rate (Stagnation)
* **Ziel:** Identifikation ignorierter Leads.
* **Logik:** MQLs > 60 Tage ohne Statuswechsel.

### Modul 2: Kohorten-Analyse (Trend)
* **Ziel:** Bereinigung des Zeitversatzes.
* **Darstellung:** Tabelle (Zeile: MQL-Monat / Spalte: Konvertiert nach 30/60/90 Tagen).

### Modul 3: Pipeline-Abdeckungsgrad (Coverage)
* **Ziel:** Sicherheits-Metrik.
* **Formel:** $\frac{\text{Summe Deal-Betrag (Offene SQLs)}}{\text{Umsatzziel}}$

---

## 4. Technische Architektur

### 4.1 Output-Format
* **PDF:** Kombiniert mit Deal-Report (eine PDF-Datei)
  - Seiten 1-N: Deal-Analyse (wie bisher)
  - Seiten N+1-M: Contact/Lead-Analyse (neu)
  - Dateiname: `board_report_YYYY-MM-DD.pdf` (oder ähnlich)

### 4.2 HubSpot Datenfelder

#### Lifecycle Stage
* **Filter:** Nur Contacts mit `lifecyclestage` in `["marketingqualifiedlead", "salesqualifiedlead"]`

#### Datumsfelder (Präzise Feldnamen)
* **MQL-Datum:** `hs_v2_date_entered_marketingqualifiedlead` (Timestamp, wann Contact MQL wurde)
* **SQL-Datum:** `hs_v2_date_entered_salesqualifiedlead` (Timestamp, wann Contact SQL wurde)
* **Wichtig:** Nicht `hs_lifecyclestage_*_date` verwenden (veraltet), sondern `hs_v2_date_entered_*`.

#### Contact Properties
* `firstname`
* `lastname`
* `email`
* `lifecyclestage`
* `hs_v2_date_entered_marketingqualifiedlead`
* `hs_v2_date_entered_salesqualifiedlead`
* `ursprungliche_quelle__analog_unternehmensquelle_` (Lead-Quelle für Quellen-Gruppierung)

#### Company Association
* **Quelle:** HubSpot Associations API `/crm/v3/objects/contacts/{contactId}/associations/companies`
* **Regel:** Verwende **Primary Company** (wenn mehrere Companies assoziiert sind)
  - **Primary Company Identifikation:** Filter auf `associationTypes.typeId === 1` (HubSpot Standard)
  - Fallback: Falls kein typeId=1 vorhanden → Erste Company in Liste
* **Fallback:** Falls keine Company → Spalte leer oder "–"

#### Datumsfelder Fallbacks
* **MQL-Datum:** Falls `hs_v2_date_entered_marketingqualifiedlead` leer → Verwende `createdate` (Contact-Erstellungsdatum)
* **SQL-Datum:** Falls `hs_v2_date_entered_salesqualifiedlead` leer → Bleibt NULL (Contact wurde nie SQL)

### 4.3 Datenerfassung (`fetch_contacts.py`)

**Neu zu erstellen:**
```python
# Analog zu fetch_deals.py
# 1. HubSpot Search API: /crm/v3/objects/contacts/search
# 2. Filter: lifecyclestage in [marketingqualifiedlead, salesqualifiedlead]
# 3. Properties: siehe 4.2
# 4. Associations API: Batch-Abruf der Primary Company für alle Contacts
# 5. CSV Export: contacts_snapshot_YYYY-MM-DD.csv
```

**CSV-Struktur:**
| Column | Type | Nullable | Fallback/Logic |
|--------|------|----------|----------------|
| `contact_id` | str | No | HubSpot Contact ID |
| `firstname` | str | No | Vorname |
| `lastname` | str | No | Nachname |
| `email` | str | Yes | E-Mail |
| `lifecyclestage` | str | No | MQL oder SQL |
| `mql_date` | datetime | No | `hs_v2_date_entered_marketingqualifiedlead` ODER `createdate` falls leer |
| `sql_date` | datetime | **Yes** | `hs_v2_date_entered_salesqualifiedlead` ODER NULL |
| `company_id` | str | Yes | Primary Company ID (typeId=1) |
| `company_name` | str | Yes | Name der Primary Company |
| `source` | str | Yes | `ursprungliche_quelle__analog_unternehmensquelle_` ODER "Unbekannt" falls leer |

**Wiederverwendung:**
* `src/hubspot_client.py` (API-Client mit Rate Limiting)
* `src/csv_writer.py` (UTF-8-BOM Export)
* `src/config.py` (Environment Config)

### 4.4 Datenanalyse

**Option A:** Neue Datei `analyze_contacts.py` (Empfohlen für Modularität)
**Option B:** Integration in `generate_report.py` (Schnellere Implementierung)

**Analyselogik:**
```python
# 1. Lade contacts_snapshot_*.csv
# 2. Berechne für letzte 12 Monate:
#    - Anzahl MQLs (gruppiert nach Monat aus mql_date)
#    - Anzahl SQLs (gruppiert nach Monat aus sql_date)
#    - Conversion Rate pro Monat
#    - Ø Durchlaufzeit (sql_date - mql_date) für SQLs im Monat
# 3. Filtere SQL-Detail-Liste für letzten abgeschlossenen Monat
# 4. Berechne Quellen-Übersicht für letzte 12 Monate:
#    - Gruppiere nach 'source' und Monat
#    - Zähle MQLs und SQLs pro Quelle pro Monat
#    - Pivot zu Matrix-Format (Zeilen: Quellen, Spalten: Monate)
#    - Berechne Gesamt-Spalte (Summe über alle Monate)
#    - Berechne Conv.Rate über gesamten Zeitraum
#    - Sortiere nach Gesamt-SQLs absteigend
# 5. Export: contacts_kpi_YYYY-MM-DD.csv + sql_details_YYYY-MM-DD.csv + source_breakdown_YYYY-MM-DD.csv
```

**Wiederverwendung:**
* `src/utils/formatting.py` (Datum-Formatierung)
* Analog zu `src/analysis/monthly_analyzer.py` (Monatsgrenzen)

### 4.5 PDF-Generierung (`src/reporting/pdf_generator.py`)

**Erweiterung der bestehenden Klasse:**
```python
class PDFGenerator:
    # Bestehend: generate_comparison_pdf() für Deals

    # Neu hinzufügen:
    def _create_contact_report_section(self, contact_data: dict) -> List:
        """
        Generate contact/lead analysis section for PDF.

        Returns List of Flowables:
        - Page: Contact KPIs Overview (12 Monate Tabelle)
        - Page: SQL Detail List (Datum | Kontakt | Firma | Quelle)
        - Page: Source Breakdown (Quelle | MQLs | SQLs | Conv.Rate)
        """
        pass
```

**Layout:**
- **Seite N+1:** KPI-Übersicht (analog zu Deal Metrics Page)
  - Tabelle: Monat | MQLs | SQLs | Conv.Rate | Ø Tage
  - 12 Zeilen (letzte 12 Monate)

- **Seite N+2:** SQL-Detail-Liste
  - Tabelle: Datum | Kontakt | Firma | Quelle
  - Nur letzter abgeschlossener Monat
  - Sortierung: Datum absteigend (neueste zuerst)

- **Seite N+3:** Quellen-Übersicht (neu) - Matrix-Format
  - Tabelle: Quelle | Jul MQL/SQL | Aug MQL/SQL | ... | Dez MQL/SQL | Gesamt | Conv.Rate
  - Letzte 12 abgeschlossene Monate
  - Format: Kompakte Zellen mit "X/Y" (z.B. "10/2" = 10 MQLs, 2 SQLs)
  - Gesamt-Spalte: Summe über alle Monate
  - Sortierung: Nach Gesamt-SQLs absteigend
  - Zeigt historische Marketing-Kanal-Performance

**Wiederverwendung:**
* Bestehende Styles (`TableCell`, `TableHeader`, etc.)
* `format_date_german()` für Datumsanzeige
* `format_percentage()` für Conversion Rate

### 4.6 Pipeline-Integration (`generate_report.py`)

**Erweitere `main()` Funktion:**
```python
def main():
    # === DEALS (Bestehend) ===
    if not args.skip_fetch:
        fetch_deals()
    if not args.skip_analysis:
        analyze_deals()

    deal_comparison_df = ...
    deal_metrics = ...

    # === CONTACTS (Neu mit Error Handling) ===
    contact_data = None
    try:
        if not args.skip_fetch:
            fetch_contacts()  # Neuer Aufruf
        if not args.skip_analysis:
            contact_kpis, sql_details, source_breakdown = analyze_contacts()  # Neuer Aufruf
            contact_data = {
                'kpis': contact_kpis,
                'sql_details': sql_details,
                'source_breakdown': source_breakdown
            }
    except Exception as e:
        logger.error(f"❌ Contact-Analyse fehlgeschlagen: {e}")
        print(f"\n⚠️  WARNUNG: Contact-Analyse fehlgeschlagen.")
        print(f"    Fehler: {e}")
        print(f"    → PDF wird ohne Contact-Sektion generiert\n")
        contact_data = None  # PDF wird nur Deal-Report enthalten

    # === PDF GENERATION ===
    pdf_generator = PDFGenerator()

    # Erweitere generate_comparison_pdf() um contact_data Parameter (Optional)
    pdf_generator.generate_comparison_pdf(
        deal_comparison_df,
        deal_metrics,
        contact_data=contact_data,  # Neu: Optional, kann None sein
        output_path=...
    )
```

**Error Handling Strategie:**
- Contact-Fetch oder -Analyse fehlgeschlagen → Fehler auf Console ausgeben + Warning
- PDF wird trotzdem generiert, aber nur mit Deal-Report (ohne Contact-Sektion)
- Pipeline bricht **NICHT** ab bei Contact-Fehlern

---

## 5. Implementierungs-Checkliste

### Phase 1: Basis-KPIs (A-E) - JETZT

**Schritt 1: Datenerfassung**
- [ ] `fetch_contacts.py` erstellen (analog zu `fetch_deals.py`)
  - [ ] HubSpot Search API Integration
  - [ ] Filter: `lifecyclestage` in MQL/SQL
  - [ ] Properties: firstname, lastname, email, mql_date, sql_date, **source**
  - [ ] Associations API: Primary Company abrufen
  - [ ] CSV-Export: `contacts_snapshot_YYYY-MM-DD.csv`
  - [ ] Wiederverwendung: `hubspot_client.py`, `csv_writer.py`, `config.py`

**Schritt 2: Analyse**
- [ ] Contact-Analyse-Logik implementieren
  - [ ] Option A: Neue Datei `analyze_contacts.py` ODER
  - [ ] Option B: Integration in `generate_report.py`
  - [ ] KPI-Berechnung für letzte 12 Monate (Volumen, Conv.Rate, Durchlaufzeit)
  - [ ] SQL-Detail-Liste filtern (letzter abgeschlossener Monat)
  - [ ] **Quellen-Übersicht berechnen (gruppiert nach source für letzten Monat)**
  - [ ] CSV-Export: `contacts_kpi_YYYY-MM-DD.csv`, `sql_details_YYYY-MM-DD.csv`, **`source_breakdown_YYYY-MM-DD.csv`**

**Schritt 3: PDF-Erweiterung**
- [ ] `src/reporting/pdf_generator.py` erweitern
  - [ ] Neue Methode: `_create_contact_report_section()`
  - [ ] KPI-Übersicht-Seite (Tabelle mit 12 Monaten)
  - [ ] SQL-Detail-Liste-Seite (Datum | Kontakt | Firma | **Quelle**)
  - [ ] **Quellen-Übersicht-Seite (Quelle | MQLs | SQLs | Conv.Rate)**
  - [ ] Wiederverwendung: Bestehende Styles + Formatierungsfunktionen

**Schritt 4: Pipeline-Integration**
- [ ] `generate_report.py` erweitern
  - [ ] `fetch_contacts()` Aufruf hinzufügen
  - [ ] `analyze_contacts()` Aufruf hinzufügen
  - [ ] `contact_data` Parameter an PDF-Generator übergeben
  - [ ] CLI-Argumente erweitern (optional: `--skip-contacts`)

**Schritt 5: Testing & Dokumentation**
- [ ] End-to-End Test: `python generate_report.py`
- [ ] PDF prüfen: Deal-Report + Contact-Report in einer Datei
- [ ] `CLAUDE.md` aktualisieren (Commands, Output Files, Architecture)
- [ ] `sqlmqlReport.md` auf "Implemented" setzen

### Phase 2: Erweiterte Module - SPÄTER (nach Phase 1)
- [ ] Modul 1: Lead-Verrottungs-Rate
- [ ] Modul 2: Kohorten-Analyse
- [ ] Modul 3: Pipeline-Abdeckungsgrad

---

## 6. Technische Entscheidungen (Dokumentiert)

| Entscheidung | Rationale |
|--------------|-----------|
| **Output:** Kombiniertes PDF | Einfachere Distribution, konsistentes Layout |
| **Zeitraum:** 12 Monate | Standard Board-Reporting-Periode |
| **"Letzter Monat":** Abgeschlossener Monat | Vermeidung von unvollständigen Daten |
| **Datumsfelder:** `hs_v2_date_entered_*` | Neuere, präzisere HubSpot-Felder |
| **Company:** Primary Company | Vermeidung von Duplikaten bei Multi-Company-Contacts |
| **Conv.Rate Berechnung:** Nur im Monat konvertiert | Faire Metrik ohne Zeitverzug |
| **Velocity:** Nur für SQLs im Berichtsmonat | Aktuelle Performance, keine historischen Verzerrungen |
| **Quellen-Gruppierung:** Letzte 12 Monate | Zeigt historische Entwicklung der Marketing-Kanäle, ermöglicht Trend-Analyse |
| **Matrix-Format:** Zeilen: Quellen, Spalten: Monate | Kompakte Darstellung wie Referenz-Tabelle, schneller Überblick |
| **Quellen-Sortierung:** Nach SQLs absteigend | Wichtigste Quellen (mit meisten Conversions) zuerst |
| **Source Fallback:** "Unbekannt" | Verhindert leere Gruppenbildung |
| **Phase 1 zuerst** | Iterative Entwicklung, früher Nutzen |
| **Wiederverwendung:** Alle Module | Code-DRY, konsistente Architektur |

---

## 7. Offene Fragen / Risiken

| Frage | Status | Antwort |
|-------|--------|---------|
| Multiple Companies pro Contact? | ✅ Geklärt | Primary Company verwenden |
| Conversion Rate Formel? | ✅ Geklärt | Nur im selben Monat erstellt/konvertiert |
| Velocity Berechnung? | ✅ Geklärt | Nur für SQLs im Berichtsmonat |
| Quellen-Gruppierung gewünscht? | ✅ Geklärt | Option 2: Historische Matrix über 12 Monate (wie Referenz-Tabelle) |
| Dashboard für Contacts? | ❌ Nicht gewünscht | Kein Contact-Dashboard geplant |
| Email im PDF anzeigen? | ⏸️ Optional | Zunächst nur Name + Firma + Quelle |

---

## 8. Nächste Schritte

1. **Review:** Spec final durchlesen und freigeben
2. **Start:** Implementierung Phase 1 (Schritt 1-5)
3. **Testing:** End-to-End Test mit echten HubSpot-Daten
4. **Deploy:** PDF-Report an Aufsichtsrat verteilen
5. **Phase 2:** Erweiterte Module nach Feedback implementieren