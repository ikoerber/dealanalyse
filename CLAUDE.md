# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HubSpot Deal Reporting Service for board (Aufsichtsrat) reports. Fetches deal data from HubSpot CRM API v3, analyzes monthly deal movements, and generates KPI reports with an interactive Streamlit dashboard.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Full pipeline: Fetch + Analyze + PDF generation
python generate_report.py

# Pipeline options
python generate_report.py --skip-fetch              # Use existing data
python generate_report.py --skip-analysis           # Use existing reports
python generate_report.py --months "Dezember 2025" "Januar 2026"  # Specific months

# Individual steps (if needed)
python fetch_deals.py                               # Fetch from HubSpot
python analyze_deals.py                             # Generate analysis CSVs
streamlit run dashboard_monthly.py                  # Interactive dashboard
```

## Architecture

### Data Flow
1. `fetch_deals.py` → HubSpot API → `output/deals_snapshot_*.csv` + `output/deal_history_*.csv`
2. `analyze_deals.py` → Reads CSVs → Generates `kpi_overview.csv` + `deal_movements_detail.csv`
3. `generate_report.py` → Runs 1+2 + Generates PDF comparison report
4. `dashboard_monthly.py` → Reads CSVs → Interactive Streamlit UI

### Core Modules (`src/`)

- **hubspot_client.py**: HubSpot API v3 client with rate limiting (tenacity), handles auth, pagination, and owner lookups
- **data_fetcher.py**: Orchestrates data retrieval, checkpointing for large datasets
- **csv_writer.py**: CSV export with UTF-8-BOM encoding for Excel compatibility
- **config.py**: Environment configuration via python-dotenv

### Analysis Layer (`src/analysis/`)

- **stage_mapper.py**: Maps HubSpot stage IDs to human-readable names using `config/stage_mapping.json`
- **movement_categorizer.py**: Categorizes deals as WON, LOST, ADVANCED, STALLED, PUSHED, REGRESSED
- **monthly_analyzer.py**: Reconstructs deal state at any point using `propertiesWithHistory`
- **kpi_calculator.py**: Aggregates Revenue Won, Pipeline Generation, Win Rate per month

### Reporting (`src/reporting/`)

- **report_generator.py**: Coordinates analysis and report creation
- **report_writer.py**: Writes final CSV reports
- **pdf_generator.py**: ReportLab-based PDF export with metrics summary and color-coded deal comparison tables (landscape A4, German formatting)

## Key Concepts

### Deal Movement Logic (Snapshot Comparison)
For each deal, compare state at month start vs. month end:
- **WON**: Ended in `closedwon` stage
- **LOST**: Ended in `closedlost` or `16932893` (Kein Angebot)
- **PUSHED**: `closedate` moved to future (slippage detection)
- **ADVANCED**: Moved forward in pipeline
- **REGRESSED**: Moved backward in pipeline
- **STALLED**: No stage change (warning signal)

### Stage Configuration
Pipeline stages are defined in `config/stage_mapping.json`:
- `stage_names`: ID → display name mapping
- `pipeline_order`: Stage sequence for comparison
- `won_stages`/`lost_stages`: Terminal stage arrays

## Configuration

Required in `.env`:
```
HUBSPOT_ACCESS_TOKEN=pat-na1-...
```

Optional:
```
HUBSPOT_BASE_URL=https://api.hubapi.com
START_DATE=2025-01-01
RATE_LIMIT_DELAY=0.11
```

Dashboard requires `HUBSPOT_PORTAL_ID` in `dashboard_monthly.py` (line 13) for clickable deal links.

## API Notes

- HubSpot Search API: `POST /crm/v3/objects/deals/search`
- History API: `GET /crm/v3/objects/deals/{id}?propertiesWithHistory=dealstage,amount,closedate`
- Rate limit: 100 requests/10 seconds (configured 110ms delay)
- Checkpoint system saves progress every 100 deals in `output/.checkpoint_deals.json`
