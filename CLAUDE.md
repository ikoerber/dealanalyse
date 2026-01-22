# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HubSpot Multi-Object Reporting Service with extensible architecture for analyzing Deals, Contacts, and Companies. Provides:

1. **Interactive Dashboard** - Streamlit web app for side-by-side monthly deal comparison
2. **PDF Report Generator** - Automated PDF reports for board presentations
3. **Multi-Object Architecture** - Config-driven system for fetching and analyzing different HubSpot object types

Fetches data from HubSpot CRM API v3, analyzes movements and trends, and presents insights through visual and printable formats.

## Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Phase 2 Architecture Demo
```bash
# Demonstrates new multi-object architecture
python demo_phase2_architecture.py
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
# Full pipeline: Fetch + Analyze + PDF (generates 2 PDFs)
python generate_report.py

# Skip steps for faster iteration
python generate_report.py --skip-fetch              # Use existing snapshot data
python generate_report.py --skip-analysis           # Use existing CSV reports

# Compare specific months
python generate_report.py --months "Dezember 2025" "Januar 2026"

# Generate specific PDFs only
python generate_report.py --pdf-parts 1             # Only Pipeline Comparison (PDF 1)
python generate_report.py --pdf-parts 2             # Only Supplementary Reports (PDF 2)
python generate_report.py --pdf-parts 1 2           # Both PDFs (default)

# Fast iteration during layout changes
python generate_report.py --skip-fetch --skip-analysis --pdf-parts 1
```

### Data Pipeline (Manual Steps)
```bash
# Legacy scripts (still fully functional)
python fetch_deals.py        # Fetch from HubSpot → output/deals_snapshot_*.csv
python fetch_contacts.py     # Fetch contacts (MQL/SQL) → output/contacts_snapshot_*.csv
python analyze_deals.py      # Generate analysis → output/reports/*.csv
python analyze_contacts.py   # Contact funnel analysis → output/reports/*.csv
```

### New Architecture Usage (Phase 2)
```python
# Example: Fetch companies with new architecture
from src.config import load_config
from src.hubspot_client import HubSpotClient
from src.core import ObjectRegistry
from src.fetchers import CompaniesFetcher

config = load_config()
client = HubSpotClient(config)
registry = ObjectRegistry()

# Get companies configuration from JSON
companies_config = registry.get('companies')

# Create fetcher (automatic pagination, checkpoint, progress)
fetcher = CompaniesFetcher(config, client, companies_config)
companies = fetcher.fetch_all()

# Get statistics
stats = fetcher.get_summary_stats(companies)
print(f'Fetched {stats["total_companies"]} companies')
```

## Main Features

### 1. Interactive Dashboard (`dashboard_monthly.py`)

**UI Components:**
- **Month Selector**: Choose two months for side-by-side comparison
- **Pipeline Metrics**: Total weighted value, deal count, average deal size
- **Closed Deals**: Won/Lost/No Offer counts and amounts
- **Deal Tables**: Expandable sections with filters

**Features:**
- Owner name display with initials (e.g., "Max Mustermann" → "MM")
- Color-coded status changes (🟢 Won, 🔴 Lost, 🔵 Phase changed, 🆕 New)
- Clickable deal links to HubSpot (requires `HUBSPOT_PORTAL_ID`)
- Last activity date tracking
- Deal age calculation
- German number formatting (1.234.567 €, DD.MM.YYYY)

### 2. PDF Report Generator (`generate_report.py`)

**Generates 2 separate PDFs:**

**PDF 1: Pipeline Comparison (`1_pipeline_vergleich_*.pdf`)**
- **Page 1**: Metrics summary (Pipeline comparison, Closed deals)
- **Page 2+**: Detailed deal comparison table (Landscape A4, 20 deals/page)

**PDF 2: Supplementary Reports (`2_zusatzberichte_*.pdf`)**
- **Contact Funnel**: MQL/SQL conversion tracking
- **2025 Deals Overview**: Complete list with sources and rejection reasons

**Key Features:**
- **Historical HubSpot Probabilities**: Uses actual `hs_forecast_probability` from deal history instead of phase-based estimates
- **Probability Change Tracking**: Status column shows probability changes (e.g., "🔵 Negotiation → Proposal (Prob: 75% → 40%)")
- **Time-Travel Reconstruction**: Reconstructs probability at month-end for accurate historical comparison
- **Selective Generation**: `--pdf-parts 1|2` to generate only specific PDFs

**Formatting:**
- German locale: `1.234.567 €`, `DD.MM.YYYY`, `18,5%`
- Text wrapping for long fields
- Color-coded rows (Green=Won, Red=Lost, Blue=Changed, Yellow=New)
- Probability changes highlighted in status text

### 3. Multi-Object Architecture (Phase 1 & 2)

**Supported Object Types:**
- ✅ **Deals** - Full history, contact enrichment, rejection reasons
- ✅ **Contacts** - MQL/SQL funnel, company associations, source tracking
- ✅ **Companies** - Customer pipeline, deal/contact associations
- ⏳ **Activities** - Placeholder (future)

**Key Features:**
- **Config-Driven**: Object types defined in `config/object_types.json`
- **Reusable Patterns**: BaseFetcher handles pagination, checkpoint, progress
- **Report Registry**: Reports defined in `config/report_definitions.json`
- **Type-Safe**: Dataclasses for all configurations and snapshots
- **Zero Breaking Changes**: Old scripts still work

## Architecture

### Multi-Object Architecture (Phase 1 & 2)

```
Configuration Layer
    ├─→ config/object_types.json (Object type definitions)
    └─→ config/report_definitions.json (Report configurations)
         ↓
Core Framework (src/core/)
    ├─→ ObjectRegistry (Load object configs)
    ├─→ CheckpointManager (Generic checkpoint system)
    ├─→ BaseFetcher (Abstract fetch pattern)
    └─→ BaseAnalyzer (Abstract analysis pattern)
         ↓
Specialized Implementations
    ├─→ src/fetchers/ (DealsFetcher, ContactsFetcher, CompaniesFetcher)
    ├─→ src/analyzers/ (BaseAnalyzer framework)
    └─→ src/reporting/ (PDF Generator, ReportRegistry)
         ↓
HubSpot API v3
```

### Data Flow (Updated)

```
HubSpot API v3
    ↓
┌─────────────────────────────────────────────────┐
│ New Architecture (Phase 2)                      │
│ - ObjectRegistry → Fetcher → Snapshots          │
│ - Supports: Deals, Contacts, Companies          │
│ - Config-driven, reusable patterns              │
└─────────────────────────────────────────────────┘
    ↓
CSV Snapshots (output/)
    ├─→ deals_snapshot_*.csv + deal_history_*.csv
    ├─→ contacts_snapshot_*.csv
    └─→ companies_snapshot_*.csv (new)
    ↓
Analysis Layer
    ├─→ analyze_deals.py → kpi_overview_*.csv
    ├─→ analyze_contacts.py → contact_funnel_*.csv
    └─→ BaseAnalyzer framework (extensible)
    ↓
Visualization
    ├─→ dashboard_monthly.py (Streamlit)
    └─→ generate_report.py → PDF Reports
```

### Core Modules (`src/`)

#### Phase 1 & 2: Core Framework

- **cli/utils.py**: Shared CLI utilities (~150 lines deduplication)
  - `setup_logging()`, `format_duration()`, `print_banner()`
  - `CLIErrorHandler` with standardized error messages

- **core/object_registry.py**: Centralized object type configuration
  - Loads `config/object_types.json`
  - Provides `ObjectTypeConfig` dataclass
  - Methods: `get()`, `list_types()`, `has()`

- **core/checkpoint_manager.py**: Generic checkpoint system
  - Object-type-specific checkpoints (`.checkpoint_deals.json`, etc.)
  - Resume-on-failure for any object type
  - Methods: `load()`, `save()`, `clear()`, `get_info()`

- **core/base_fetcher.py**: Abstract base class for fetchers
  - Common patterns: pagination, progress logging, checkpoint
  - Hooks: `_extract_snapshot()`, `_enrich_snapshot()`
  - Uses `search_objects()` generic API method

- **core/base_analyzer.py**: Abstract base class for analyzers
  - Abstract `analyze()` method
  - Generic `export_to_csv()` for DataFrames
  - Extensible for KPI calculations

#### Specialized Fetchers (`src/fetchers/`)

- **deals_fetcher.py**: DealsFetcher (~350 lines)
  - Fetches deal history with `propertiesWithHistory`
  - Enriches with primary contact source
  - Returns `DealSnapshot` + `HistoryRecord` lists

- **contacts_fetcher.py**: ContactsFetcher (~170 lines)
  - Fetches MQL/SQL contacts with lifecycle stages
  - Enriches with company associations (primary company)
  - Extracts source field for lead attribution
  - Returns `ContactSnapshot` list

- **companies_fetcher.py**: CompaniesFetcher (~120 lines)
  - Fetches company data (name, domain, industry, etc.)
  - Tracks associated contacts and deals counts
  - Returns `CompanySnapshot` list

#### Reporting Layer (`src/reporting/`)

- **report_registry.py**: Report definition registry (NEW)
  - Loads `config/report_definitions.json`
  - Type-safe dataclasses: `ReportDefinition`, `ReportDataSource`, etc.
  - Methods: `get()`, `list_reports()`, `get_by_object_type()`
  - Supports filtering by object type, enabled status, schedule

- **pdf_generator.py**: ReportLab-based PDF generation
  - Landscape A4 layout (297×210mm)
  - Metrics summary tables
  - Paginated deal comparison tables (20 rows/page)
  - 2025 Deals Overview section (25 rows/page)
  - Color-coded rows and formatted columns

#### Legacy Modules (Still Active)

- **hubspot_client.py**: HubSpot API v3 client
  - Rate limiting with tenacity (100 req/10s)
  - Pagination handling
  - **NEW**: `search_objects()` generic method for all object types
  - Owner lookups with caching

- **data_fetcher.py**: Data retrieval orchestration (legacy)
  - **UPDATED**: Now uses `CheckpointManager` internally
  - Backward compatible with old scripts
  - Progress logging (every 50 objects)

- **csv_writer.py**: CSV export with UTF-8-BOM encoding
  - **UPDATED**: Supports new fields (rejection_reason, contact_source)

### Analysis Layer (`src/analysis/`)

- **stage_mapper.py**: Maps HubSpot stage IDs → human names
- **movement_categorizer.py**: Categorizes deal movements
- **monthly_analyzer.py**: Reconstructs deal state at any timestamp
- **kpi_calculator.py**: Aggregates monthly KPIs
- **csv_reader.py**: Loads CSV data with dataclass conversion
- **deals_2025_analyzer.py**: Analyzes all deals created in 2025 (NEW)

### Utilities (`src/utils/`)

- **formatting.py**: German number/date/currency formatting

## Configuration Files (NEW)

### config/object_types.json
Defines HubSpot object types with their properties and behavior:
```json
{
  "deals": {
    "object_type_id": "deals",
    "api_endpoint": "/crm/v3/objects/deals/search",
    "properties": ["dealname", "amount", ...],
    "history_properties": ["dealstage", "amount"],
    "has_stages": true,
    "has_history": true
  },
  "contacts": { ... },
  "companies": { ... }
}
```

**Adding a New Object Type:**
1. Add entry to `config/object_types.json`
2. Create `ObjectTypeFetcher` class (~150 lines)
3. Done! Checkpoint, pagination, progress all automatic

### config/report_definitions.json
Defines report configurations:
```json
{
  "deal_monthly_comparison": {
    "name": "Deal Monthly Comparison Report",
    "object_type": "deals",
    "enabled": true,
    "data_source": { ... },
    "outputs": [
      {"format": "pdf", "template": "comparison_landscape"},
      {"format": "csv", "files": ["kpi_overview", "movements"]}
    ],
    "schedule": {"frequency": "monthly"}
  }
}
```

**Available Reports:**
- ✅ `deal_monthly_comparison` - Deals, Monthly, PDF+CSV
- ✅ `contact_funnel_analysis` - Contacts, Monthly, PDF+CSV
- ✅ `deals_2025_overview` - Deals, On-demand, PDF+CSV
- ⏸️ `company_pipeline` - Companies, Quarterly, Disabled (placeholder)

## Key Concepts

### Multi-Object Architecture Benefits

**Before (Legacy):**
- Hardcoded logic for each object type
- ~150 lines duplication per script
- No reusability between deals/contacts/companies

**After (Phase 1 & 2):**
- ✅ Config-driven (JSON instead of code)
- ✅ Reusable patterns (BaseFetcher, BaseAnalyzer)
- ✅ Type-safe (Dataclasses everywhere)
- ✅ Checkpoint for all object types
- ✅ Report Registry system
- ✅ Zero breaking changes

### Object Type Extensibility

Add a new object type in **<10 minutes**:

1. **Configure** (config/object_types.json):
```json
{
  "tickets": {
    "object_type_id": "tickets",
    "api_endpoint": "/crm/v3/objects/tickets/search",
    "properties": ["subject", "status", "priority"]
  }
}
```

2. **Implement Fetcher** (~150 lines):
```python
class TicketsFetcher(BaseFetcher):
    def _extract_snapshot(self, obj, timestamp):
        return TicketSnapshot(
            ticket_id=obj.get('id'),
            subject=obj.get('properties', {}).get('subject', ''),
            ...
        )
```

3. **Done!** Automatic pagination, checkpoint, progress logging

### Deal Movement Logic (Snapshot Comparison)

Compares deal state at month start vs. month end:
- **WON**: Ended in `closedwon` stage
- **LOST**: Ended in `closedlost` or `16932893` (Kein Angebot)
- **PUSHED**: `closedate` moved to future (slippage detection)
- **ADVANCED**: Moved forward in pipeline
- **REGRESSED**: Moved backward in pipeline
- **STALLED**: No stage change (warning signal)

Priority: WON > LOST > PUSHED > ADVANCED > REGRESSED > STALLED

### Historical HubSpot Probabilities

The system uses **actual HubSpot forecast probabilities** from deal history instead of fixed phase-based estimates:

**How it Works:**
1. Loads `deal_history_*.csv` containing all `hs_deal_stage_probability` changes
2. For each month comparison, calculates month-end timestamp (e.g., Dec 31, 23:59:59 UTC)
3. Reconstructs probability for each deal at that specific point in time
4. Creates separate `HubSpot_Probability_A` and `HubSpot_Probability_B` columns
5. Uses these historical values for weighted pipeline calculations

**Benefits:**
- ✅ Accurate historical forecasts (uses actual values from that time)
- ✅ Tracks manual probability adjustments in HubSpot
- ✅ Different probabilities for same phase (e.g., Negotiation: 75% → 90%)
- ✅ Fallback to phase-based probabilities if history unavailable

**Probability Change Display:**
Status column shows probability changes > 5%:
- With phase change: `🔵 Qualification → Negotiation (Prob: 20% → 90%)`
- Without phase change: `📊 Prob: 50% → 75%`

**Implementation:**
- `load_history_data()`: Loads deal history CSV
- `get_probability_at_time()`: Time-travel reconstruction function
- `merge_months()`: Creates historical probability columns
- `calculate_weighted_value()`: Uses HubSpot values with fallback

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

### Checkpoint System (Updated)

**Object-Specific Checkpoints:**
- `.checkpoint_deals.json` - Deal fetch progress
- `.checkpoint_contacts.json` - Contact fetch progress
- `.checkpoint_companies.json` - Company fetch progress

Format:
```json
{
  "object_type": "deals",
  "processed_ids": ["12345", "67890"],
  "count": 2,
  "last_updated": "2026-01-20T10:00:00"
}
```

Resume from checkpoint if fetch fails (all object types).

## Environment Variables

### Required
```bash
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxx...
```

### Optional
```bash
HUBSPOT_BASE_URL=https://api.hubapi.com
START_DATE=2025-01-01
RATE_LIMIT_DELAY=0.11
HUBSPOT_PORTAL_ID=12345678  # For clickable dashboard links
```

## API Details

### HubSpot API Endpoints

- **Search API** (Generic): `POST /crm/v3/objects/{type}/search`
  - Works for deals, contacts, companies, activities
  - Supports pagination (limit: 100/request)
  - Used by `search_objects()` method (NEW)

- **History API**: `GET /crm/v3/objects/deals/{id}?propertiesWithHistory=...`
  - Returns full property change history
  - Used for time-travel queries

- **Associations API**: `GET /crm/v3/objects/{type}/{id}/associations/{toType}`
  - Fetches associated objects (e.g., deal → contacts)

### Rate Limiting
- Limit: 100 requests / 10 seconds
- Configured delay: 110ms between requests
- Retry logic with exponential backoff (tenacity)

## Output Files

### CSV Snapshots (`output/`)
- `deals_snapshot_YYYY-MM-DD.csv`: Current deal state (16+ fields)
- `deal_history_YYYY-MM-DD.csv`: Property change history
- `contacts_snapshot_YYYY-MM-DD.csv`: Contact data with companies (NEW)
- `companies_snapshot_YYYY-MM-DD.csv`: Company data (NEW, Phase 2)
- `owners_YYYY-MM-DD.json`: Owner ID → name mapping

### CSV Reports (`output/reports/`)
- `kpi_overview_YYYY-MM-DD.csv`: Monthly KPI summary
- `deal_movements_detail_YYYY-MM-DD.csv`: Deal-by-deal movement log
- `contacts_kpi_YYYY-MM-DD.csv`: Contact funnel KPIs
- `sql_details_YYYY-MM-DD.csv`: SQL details last month
- `source_breakdown_YYYY-MM-DD.csv`: Lead source matrix

### PDF Reports (`output/reports/`)
**Two separate PDFs generated:**
- `1_pipeline_vergleich_[MonthA]_vs_[MonthB]_YYYY-MM-DD.pdf` - Pipeline comparison with metrics and deal detail table
- `2_zusatzberichte_[MonthA]_vs_[MonthB]_YYYY-MM-DD.pdf` - Contact funnel and 2025 deals overview

**Examples:**
- `1_pipeline_vergleich_Dezember_2025_vs_Januar_2026_2026-01-22.pdf`
- `2_zusatzberichte_Dezember_2025_vs_Januar_2026_2026-01-22.pdf`

## Development Notes

### Adding New Object Types
1. Add to `config/object_types.json` (properties, filters, endpoint)
2. Create `ObjectTypeFetcher(BaseFetcher)` class
3. Create `ObjectTypeSnapshot` dataclass
4. Optional: Add to `config/report_definitions.json`
5. That's it! (~10 minutes)

### Adding New Reports
1. Add to `config/report_definitions.json`
2. Specify: object_type, data_source, analysis, outputs, schedule
3. No code changes needed!

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
- Logs saved to `logs/hubspot_[script]_YYYY-MM-DD_HH-MM-SS.log`
- Rotating file handler (max 10MB, 5 backups)
- Console output shows progress every 50 objects

### Testing New Architecture
```bash
# Demo script shows all Phase 2 components
python demo_phase2_architecture.py

# Test ObjectRegistry
python -c "from src.core import ObjectRegistry; r = ObjectRegistry(); print(r.list_types())"

# Test ReportRegistry
python -c "from src.reporting.report_registry import ReportRegistry; r = ReportRegistry(); print(r.get_summary())"

# Test Fetchers
python -c "from src.fetchers import DealsFetcher, ContactsFetcher, CompaniesFetcher; print('All fetchers import successfully')"
```

## Architecture Evolution

### Phase 1: Foundation (Complete)
- ✅ CLI Utilities (~150 lines deduplication)
- ✅ Object Type Registry (JSON-based configs)
- ✅ Unified Checkpoint System (all object types)

### Phase 2: Multi-Object Support (Complete)
- ✅ BaseFetcher pattern (pagination, checkpoint, progress)
- ✅ DealsFetcher, ContactsFetcher, CompaniesFetcher
- ✅ BaseAnalyzer framework
- ✅ Report Registry system
- ✅ Demo script and documentation

### Phase 3: Advanced Features (Optional)
- ⏳ Concrete Analyzer implementations
- ⏳ Template-based PDF generation (Jinja2)
- ⏳ Plugin system for external reports
- ⏳ Streamlit Report Builder UI

## Notes

- **Backward Compatibility**: All old scripts (`fetch_deals.py`, `analyze_deals.py`, etc.) still work
- **Migration Path**: New architecture is opt-in; migrate scripts gradually
- **Performance**: Identical to legacy (same API calls, same checkpoint system)
- **Type Safety**: Dataclasses everywhere for better IDE support and validation
