# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HubSpot Deal Reporting Service for board (Aufsichtsrat) reports. Provides two main interfaces for analyzing deal data:

1. **Interactive Dashboard** - Streamlit web app for side-by-side monthly comparison
2. **PDF Report Generator** - Automated PDF reports for board presentations

Fetches deal data from HubSpot CRM API v3, analyzes monthly deal movements, tracks pipeline changes, and presents insights through both visual and printable formats.

## Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Interactive Dashboard
```bash
streamlit run dashboard_monthly.py
```
Opens web interface at `http://localhost:8501` with:
- Side-by-side monthly comparison
- Filterable deal tables with owner tracking
- Pipeline metrics and closed deals summary
- Clickable HubSpot deal links

### PDF Report Generation
```bash
# Full pipeline: Fetch + Analyze + PDF
python generate_report.py

# Skip steps for faster iteration
python generate_report.py --skip-fetch              # Use existing snapshot data
python generate_report.py --skip-analysis           # Use existing CSV reports

# Compare specific months
python generate_report.py --months "Dezember 2025" "Januar 2026"
```

### Data Pipeline (Manual Steps)
```bash
python fetch_deals.py        # Fetch from HubSpot → output/deals_snapshot_*.csv
python analyze_deals.py      # Generate analysis → output/reports/*.csv
```

## Main Features

### 1. Interactive Dashboard (`dashboard_monthly.py`)

**UI Components:**
- **Month Selector**: Choose two months for side-by-side comparison
- **Pipeline Metrics**: Total weighted value, deal count, average deal size
- **Closed Deals**: Won/Lost/No Offer counts and amounts
- **Deal Tables**: Expandable sections with filters:
  - Active Pipeline Deals
  - Won Deals
  - Lost Deals
  - Newly Created Deals

**Features:**
- Owner name display with initials (e.g., "Max Mustermann" → "MM")
- Color-coded status changes (🟢 Won, 🔴 Lost, 🔵 Phase changed, 🆕 New)
- Clickable deal links to HubSpot (requires `HUBSPOT_PORTAL_ID`)
- Last activity date tracking
- Deal age calculation
- German number formatting (1.234.567 €, DD.MM.YYYY)

**Data Filtering Logic:**
- Shows active deals + deals closed in comparison period
- Excludes deals closed before comparison start (prevents historical noise)
- Matches PDF report filtering for consistency

### 2. PDF Report Generator (`generate_report.py` + `src/reporting/pdf_generator.py`)

**Report Structure:**
- **Page 1**: Metrics summary
  - Pipeline comparison table (month A vs month B)
  - Closed deals breakdown (Won/Lost/No Offer)
- **Page 2+**: Detailed deal comparison table
  - Landscape A4 format
  - Color-coded rows based on deal status
  - 20 deals per page with pagination

**Table Columns:**
| Column | Width | Description | Alignment |
|--------|-------|-------------|-----------|
| Deal Name | 54mm | Deal title with text wrapping | Left |
| Vtw | 10mm | Owner initials (e.g., "MM") | Center |
| Wert | 18mm | Deal value | Right |
| Alter | 12mm | Deal age in days | Right |
| Phase [Month] | 26mm | Pipeline stage (wraps text) | Left |
| % [Month] | 14mm | Probability percentage | Right |
| Gewichtet [Month] | 22mm | Weighted value | Right |
| Status | 40mm | Status change description (wraps text) | Left |

**Formatting:**
- German locale: `1.234.567 €`, `DD.MM.YYYY`, `18,5%`
- Month headers shortened: "Dezember 2025" → "Dez 25"
- Text wrapping enabled for Deal Name, Phase, and Status columns
- Owner initials format: First letter of first name + first letter of last name

**Color Coding:**
- 🟢 Green: Won deals
- 🔴 Red: Lost deals / No offer
- 🔵 Blue: Phase changed
- 🆕 Yellow: Newly created
- ⚫ Gray: Already closed (before period)

## Architecture

### Data Flow
```
HubSpot API v3
    ↓
fetch_deals.py → deals_snapshot_*.csv + deal_history_*.csv + owners_*.json
    ↓
analyze_deals.py → kpi_overview_*.csv + deal_movements_detail_*.csv
    ↓
    ├─→ dashboard_monthly.py (Streamlit WebApp)
    └─→ generate_report.py → PDF Report (output/reports/*.pdf)
```

### Core Modules (`src/`)

- **hubspot_client.py**: HubSpot API v3 client
  - Rate limiting with tenacity (100 req/10s)
  - Pagination handling
  - Owner lookups with caching
- **data_fetcher.py**: Data retrieval orchestration
  - Checkpoint system for resume-on-failure
  - Progress logging (every 50 deals)
- **csv_writer.py**: CSV export with UTF-8-BOM encoding for Excel
- **config.py**: Environment configuration via python-dotenv

### Analysis Layer (`src/analysis/`)

- **stage_mapper.py**: Maps HubSpot stage IDs → human names (`config/stage_mapping.json`)
- **movement_categorizer.py**: Categorizes deal movements
  - WON, LOST, ADVANCED, STALLED, PUSHED, REGRESSED
- **monthly_analyzer.py**: Reconstructs deal state at any timestamp
  - Uses `propertiesWithHistory` for time-travel queries
  - Month boundaries: first day 00:00:00 to last day 23:59:59
- **kpi_calculator.py**: Aggregates monthly KPIs
  - Revenue Won, Pipeline Generation, Win Rate
- **csv_reader.py**: Loads CSV data with dataclass conversion

### Reporting Layer (`src/reporting/`)

- **report_generator.py**: Orchestrates full analysis pipeline
- **report_writer.py**: Exports CSV reports with German formatting
- **pdf_generator.py**: ReportLab-based PDF generation
  - Landscape A4 layout (297×210mm)
  - Metrics summary tables
  - Paginated deal comparison tables
  - Color-coded rows and formatted columns

### Utilities (`src/utils/`)

- **formatting.py**: German number/date/currency formatting
  - `format_euro()`: 1234567 → "1.234.567 €"
  - `format_percentage()`: 0.185 → "18,5%"
  - `format_date_german()`: datetime → "31.12.2025"

## Key Concepts

### Deal Movement Logic (Snapshot Comparison)
Compares deal state at month start vs. month end:
- **WON**: Ended in `closedwon` stage
- **LOST**: Ended in `closedlost` or `16932893` (Kein Angebot)
- **PUSHED**: `closedate` moved to future (slippage detection)
- **ADVANCED**: Moved forward in pipeline
- **REGRESSED**: Moved backward in pipeline
- **STALLED**: No stage change (warning signal)

Priority: WON > LOST > PUSHED > ADVANCED > REGRESSED > STALLED

### Stage Configuration
Pipeline stages defined in `config/stage_mapping.json`:
```json
{
  "stage_names": {
    "appointmentscheduled": "New",
    "qualifiedtobuy": "Qualification",
    "16932893": "Kein Angebot"
  },
  "pipeline_order": ["New", "Qualification", ...],
  "won_stages": ["closedwon"],
  "lost_stages": ["closedlost", "Kein Angebot"]
}
```

### Data Filtering (Dashboard + PDF)
Both interfaces use identical filtering:
1. Include all **active deals** (not won/lost)
2. Include deals **won/lost in comparison period** only
3. Exclude deals won/lost before comparison start

Example: Comparing Dec 2025 vs Jan 2026
- ✓ Shows deals won in Dec or Jan
- ✗ Hides deals won in Nov (already closed)

## Configuration

### Required Environment Variables
Create `.env` file:
```bash
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxx...
```

### Optional Environment Variables
```bash
HUBSPOT_BASE_URL=https://api.hubapi.com
START_DATE=2025-01-01
RATE_LIMIT_DELAY=0.11
HUBSPOT_PORTAL_ID=12345678  # For clickable dashboard links
```

### Dashboard Configuration
Set `HUBSPOT_PORTAL_ID` in `.env` or environment to enable clickable deal links:
```python
# dashboard_monthly.py line 13
HUBSPOT_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "19645216")
```

## API Details

### HubSpot API Endpoints
- **Search API**: `POST /crm/v3/objects/deals/search`
  - Fetches deal snapshots with filters
  - Supports pagination (limit: 100/request)
- **History API**: `GET /crm/v3/objects/deals/{id}?propertiesWithHistory=dealstage,amount,closedate`
  - Returns full property change history
  - Used for time-travel queries

### Rate Limiting
- Limit: 100 requests / 10 seconds
- Configured delay: 110ms between requests
- Retry logic with exponential backoff (tenacity)

### Checkpoint System
Progress saved every 100 deals in `output/.checkpoint_deals.json`:
```json
{
  "last_deal_id": "12345678",
  "processed_count": 500,
  "timestamp": "2026-01-10T10:00:00"
}
```
Resume from checkpoint if fetch fails.

## Output Files

### CSV Snapshots (`output/`)
- `deals_snapshot_YYYY-MM-DD.csv`: Current deal state
- `deal_history_YYYY-MM-DD.csv`: Property change history
- `owners_YYYY-MM-DD.json`: Owner ID → name mapping

### CSV Reports (`output/reports/`)
- `kpi_overview_YYYY-MM-DD.csv`: Monthly KPI summary
- `deal_movements_detail_YYYY-MM-DD.csv`: Deal-by-deal movement log

### PDF Reports (`output/reports/`)
- `deal_comparison_[MonthA]_vs_[MonthB]_YYYY-MM-DD.pdf`
- Example: `deal_comparison_Dezember_2025_vs_Januar_2026_2026-01-10.pdf`

## Development Notes

### Adding New Pipeline Stages
1. Update `config/stage_mapping.json`:
   - Add to `stage_names` mapping
   - Insert in correct position in `pipeline_order`
   - Add to `won_stages` or `lost_stages` if terminal
2. Re-run analysis: `python analyze_deals.py`

### Changing PDF Layout
Edit `src/reporting/pdf_generator.py`:
- Column widths: `_calculate_column_widths()` (line ~560)
- Table styles: `_create_comparison_table()` (line ~470)
- Header formatting: `_setup_custom_styles()` (line ~98)

### Debugging
- Logs saved to `logs/hubspot_deals_YYYY-MM-DD_HH-MM-SS.log`
- Rotating file handler (max 10MB, 5 backups)
- Console output shows progress every 50 deals
