#!/usr/bin/env python3
"""
HubSpot Deal Report Pipeline

Runs the complete pipeline:
1. Fetch deals from HubSpot API
2. Run monthly analysis
3. Generate PDF comparison report

Usage:
    python generate_report.py                    # Fetch + Analyze + PDF (last 2 months)
    python generate_report.py --skip-fetch       # Only Analyze + PDF (use existing data)
    python generate_report.py --months "Januar 2026" "Februar 2026"  # Specific months
"""
import sys
import os
import argparse
import logging
import subprocess
from datetime import datetime
from glob import glob
from pathlib import Path
import json

import pandas as pd


def setup_logging():
    """Setup logging configuration"""
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filepath = f"{logs_dir}/generate_report_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_filepath


def run_fetch():
    """Run fetch_deals.py to get latest data from HubSpot"""
    print("\n" + "=" * 60)
    print("SCHRITT 1: Daten von HubSpot abrufen")
    print("=" * 60 + "\n")

    result = subprocess.run(
        [sys.executable, "fetch_deals.py"],
        capture_output=False
    )

    if result.returncode != 0:
        logging.error("fetch_deals.py fehlgeschlagen")
        return False

    return True


def run_analysis():
    """Run analyze_deals.py to generate movement reports"""
    print("\n" + "=" * 60)
    print("SCHRITT 2: Datenanalyse durchführen")
    print("=" * 60 + "\n")

    result = subprocess.run(
        [sys.executable, "analyze_deals.py"],
        capture_output=False
    )

    if result.returncode != 0:
        logging.error("analyze_deals.py fehlgeschlagen")
        return False

    return True


def run_fetch_contacts():
    """Run fetch_contacts.py to get contact data from HubSpot"""
    print("\n" + "=" * 60)
    print("SCHRITT 1b: Contact-Daten von HubSpot abrufen")
    print("=" * 60 + "\n")

    result = subprocess.run(
        [sys.executable, "fetch_contacts.py"],
        capture_output=False
    )

    if result.returncode != 0:
        logging.error("fetch_contacts.py fehlgeschlagen")
        return False

    return True


def run_analysis_contacts():
    """Run analyze_contacts.py to generate contact funnel reports"""
    print("\n" + "=" * 60)
    print("SCHRITT 2b: Contact-Analyse durchführen")
    print("=" * 60 + "\n")

    result = subprocess.run(
        [sys.executable, "analyze_contacts.py"],
        capture_output=False
    )

    if result.returncode != 0:
        logging.error("analyze_contacts.py fehlgeschlagen")
        return False

    return True


def load_contact_data():
    """Load latest contact analysis reports"""
    try:
        # Find latest contact KPI file
        kpi_pattern = "output/reports/contacts_kpi_*.csv"
        kpi_files = glob(kpi_pattern)
        if not kpi_files:
            logging.warning(f"Keine Contact-KPI-Daten gefunden: {kpi_pattern}")
            return None

        latest_kpi = max(kpi_files, key=os.path.getmtime)
        kpis_df = pd.read_csv(latest_kpi, encoding='utf-8-sig')
        logging.info(f"Lade Contact-KPIs: {latest_kpi}")

        # Find latest SQL details file
        sql_pattern = "output/reports/sql_details_*.csv"
        sql_files = glob(sql_pattern)
        if not sql_files:
            logging.warning(f"Keine SQL-Details gefunden: {sql_pattern}")
            sql_details_df = pd.DataFrame()
        else:
            latest_sql = max(sql_files, key=os.path.getmtime)
            sql_details_df = pd.read_csv(latest_sql, encoding='utf-8-sig')
            logging.info(f"Lade SQL-Details: {latest_sql}")

        # Find latest source breakdown file
        source_pattern = "output/reports/source_breakdown_*.csv"
        source_files = glob(source_pattern)
        if not source_files:
            logging.warning(f"Keine Quellen-Übersicht gefunden: {source_pattern}")
            source_breakdown_df = pd.DataFrame()
        else:
            latest_source = max(source_files, key=os.path.getmtime)
            source_breakdown_df = pd.read_csv(latest_source, encoding='utf-8-sig')
            logging.info(f"Lade Quellen-Übersicht: {latest_source}")

        return {
            'kpis': kpis_df,
            'sql_details': sql_details_df,
            'source_breakdown': source_breakdown_df
        }

    except Exception as e:
        logging.error(f"Fehler beim Laden der Contact-Daten: {e}")
        return None


def load_movement_data():
    """Load the latest deal movements CSV"""
    pattern = "output/reports/deal_movements_detail_*.csv"
    files = glob(pattern)

    if not files:
        logging.error(f"Keine Bewegungsdaten gefunden: {pattern}")
        return None

    latest = max(files, key=os.path.getmtime)
    logging.info(f"Lade Bewegungsdaten: {latest}")

    df = pd.read_csv(latest, encoding='utf-8-sig')
    if 'Deal ID' in df.columns:
        df['Deal ID'] = df['Deal ID'].astype(str)

    # Create MonthYear column from Monat and Jahr
    if 'Monat' in df.columns and 'Jahr' in df.columns:
        df['MonthYear'] = df['Monat'] + ' ' + df['Jahr'].astype(str)

    return df


def load_snapshot_data():
    """Load the latest snapshot data"""
    pattern = "output/deals_snapshot_*.csv"
    files = glob(pattern)

    if not files:
        return pd.DataFrame()

    latest = max(files, key=os.path.getmtime)
    logging.info(f"Lade Snapshot-Daten: {latest}")

    df = pd.read_csv(latest, encoding='utf-8-sig')
    df['deal_id'] = df['deal_id'].astype(str)

    rename_map = {
        'deal_id': 'Deal ID',
        'hs_forecast_amount': 'HubSpot_Forecast',
        'hs_forecast_probability': 'HubSpot_Probability',
        'create_date': 'Create_Date',
        'hubspot_owner_id': 'Owner_ID'
    }

    existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=existing_renames)

    return df


def load_owners():
    """Load owner mapping"""
    pattern = "output/owners_*.json"
    files = glob(pattern)

    if not files:
        return {}

    latest = max(files, key=os.path.getmtime)
    logging.info(f"Lade Owner-Mapping: {latest}")

    with open(latest, 'r') as f:
        return json.load(f)


def load_history_data():
    """Load the latest deal history CSV"""
    pattern = "output/deal_history_*.csv"
    files = glob(pattern)

    if not files:
        logging.warning(f"Keine History-Daten gefunden: {pattern}")
        return pd.DataFrame()

    latest = max(files, key=os.path.getmtime)
    logging.info(f"Lade History-Daten: {latest}")

    df = pd.read_csv(latest, encoding='utf-8-sig')
    df['deal_id'] = df['deal_id'].astype(str)

    # Convert change_timestamp to datetime (mixed format support)
    df['change_timestamp'] = pd.to_datetime(df['change_timestamp'], format='ISO8601', utc=True)

    return df


def get_probability_at_time(deal_id, target_time, history_df, current_probability=None):
    """
    Get the deal probability at a specific point in time.

    Args:
        deal_id: Deal ID
        target_time: Target datetime (timezone-aware)
        history_df: DataFrame with history data
        current_probability: Current probability from snapshot (fallback)

    Returns:
        Probability value (0-1 scale) or None if not found
    """
    if history_df.empty:
        return current_probability

    # Filter for this deal and hs_deal_stage_probability changes
    deal_history = history_df[
        (history_df['deal_id'] == str(deal_id)) &
        (history_df['property_name'] == 'hs_deal_stage_probability')
    ].copy()

    if deal_history.empty:
        # No history found - use current probability
        return current_probability

    # Get all changes up to target_time
    changes_until_target = deal_history[deal_history['change_timestamp'] <= target_time]

    if changes_until_target.empty:
        # No changes before target_time - deal didn't exist or probability not set
        return None

    # Get the last change before target_time
    latest_change = changes_until_target.sort_values('change_timestamp').iloc[-1]

    try:
        prob = float(latest_change['property_value'])
        return prob
    except (ValueError, TypeError):
        return current_probability


def get_available_months(df):
    """Get chronologically sorted list of months"""
    if 'MonthYear' not in df.columns:
        return []

    unique_months = df['MonthYear'].unique()

    month_order = {
        'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
        'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
    }

    def sort_key(month_year):
        parts = month_year.split(' ')
        if len(parts) == 2:
            month, year = parts
            return (int(year), month_order.get(month, 0))
        return (0, 0)

    return sorted(unique_months, key=sort_key)


def get_month_data(df, month_year, all_months, comparison_start_month=None):
    """
    Get deal state at end of a specific month (matching dashboard logic).

    Shows active deals + deals closed in comparison period only.
    """
    target_idx = all_months.index(month_year)
    months_until_target = all_months[:target_idx + 1]

    df_until_target = df[df['MonthYear'].isin(months_until_target)].copy()
    df_until_target['sort_key'] = df_until_target['MonthYear'].map(
        {m: i for i, m in enumerate(all_months)}
    )

    latest_states = df_until_target.sort_values('sort_key').groupby('Deal ID').last().reset_index()
    latest_states['Current_Phase'] = latest_states['Status (Monatsende)']
    latest_states['Current_Amount'] = latest_states['Wert Monatsende (€)']

    # Filter out deals that are already won/lost (no longer active)
    active_deals = latest_states[
        ~latest_states['Current_Phase'].isin(['Gewonnen', 'Verloren', 'Kein Angebot'])
    ].copy()

    # Determine which months to include for won/lost deals
    if comparison_start_month:
        start_idx = all_months.index(comparison_start_month)
        comparison_months = all_months[start_idx:target_idx + 1]
    else:
        comparison_months = [month_year]

    # Include deals won/lost in the comparison period
    won_lost_in_period = df_until_target[
        (df_until_target['MonthYear'].isin(comparison_months)) &
        (df_until_target['Status (Monatsende)'].isin(['Gewonnen', 'Verloren', 'Kein Angebot']))
    ].copy()

    if not won_lost_in_period.empty:
        won_lost_in_period['Current_Phase'] = won_lost_in_period['Status (Monatsende)']
        won_lost_in_period['Current_Amount'] = won_lost_in_period['Wert Monatsende (€)']
        all_deals = pd.concat([active_deals, won_lost_in_period], ignore_index=True)
        all_deals = all_deals.drop_duplicates(subset=['Deal ID'], keep='last')
    else:
        all_deals = active_deals

    return all_deals


# Phase probabilities (same as dashboard)
PHASE_PROBABILITIES = {
    'New': 0.10,
    'Qualification': 0.20,
    'Cover Buying Center': 0.30,
    'Proposal': 0.40,
    'Short Listed': 0.50,
    'Selected': 0.60,
    'Negotiation': 0.75,
    'Gewonnen': 1.00,
    'Verloren': 0.00,
    'Kein Angebot': 0.00,
    '-': 0.00
}


def calculate_weighted_value(amount_str, phase, hubspot_probability=None):
    """
    Calculate weighted deal value based on probability

    Args:
        amount_str: Deal amount as string or number
        phase: Deal phase/stage name
        hubspot_probability: Optional HubSpot forecast probability (0-100 or 0-1)
                            If provided and valid, this is used instead of phase-based probability

    Returns:
        Weighted value (amount * probability)
    """
    if amount_str == '-' or pd.isna(amount_str):
        return 0

    try:
        amount = float(str(amount_str).replace('.', '').replace('€', '').replace(',', '.').strip())

        # Use HubSpot probability if available and valid
        if hubspot_probability is not None and not pd.isna(hubspot_probability):
            try:
                prob = float(hubspot_probability)
                # Handle both 0-100 and 0-1 formats
                if prob > 1:
                    prob = prob / 100.0
                # Validate range
                if 0 <= prob <= 1:
                    return amount * prob
            except (ValueError, TypeError):
                pass

        # Fallback to phase-based probability
        probability = PHASE_PROBABILITIES.get(phase, 0)
        return amount * probability
    except (ValueError, AttributeError, TypeError):
        return 0


def merge_months(month_a_df, month_b_df, month_a_name, month_b_name, snapshot_df=None, owners_map=None, history_df=None):
    """Merge two months side-by-side for comparison"""
    month_a_df = month_a_df.copy()
    month_b_df = month_b_df.copy()
    month_a_df['Deal ID'] = month_a_df['Deal ID'].astype(str)
    month_b_df['Deal ID'] = month_b_df['Deal ID'].astype(str)

    merged = pd.merge(
        month_a_df,
        month_b_df,
        on=['Deal ID', 'Deal Name'],
        how='outer',
        suffixes=('_A', '_B')
    )

    if snapshot_df is not None and not snapshot_df.empty:
        merged['Deal ID'] = merged['Deal ID'].astype(str)
        merged = pd.merge(merged, snapshot_df, on='Deal ID', how='left')

    # Calculate month-end timestamps for historical probability lookup
    month_order = {
        'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
        'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
    }

    def get_month_end_timestamp(month_year_str):
        """Get the last second of a month as UTC timestamp"""
        try:
            parts = month_year_str.split(' ')
            if len(parts) == 2:
                month_name, year_str = parts
                month_num = month_order.get(month_name, 1)
                year = int(year_str)

                # Get last day of month
                import calendar
                last_day = calendar.monthrange(year, month_num)[1]

                # Create timestamp for last second of the month (23:59:59)
                from datetime import datetime, timezone
                month_end = datetime(year, month_num, last_day, 23, 59, 59, tzinfo=timezone.utc)
                return month_end
        except Exception:
            pass
        return None

    month_a_end = get_month_end_timestamp(month_a_name)
    month_b_end = get_month_end_timestamp(month_b_name)

    # Add historical probability columns if history data is available
    if history_df is not None and not history_df.empty and month_a_end and month_b_end:
        logging.info(f"Rekonstruiere historische Wahrscheinlichkeiten für {month_a_name} und {month_b_name}")

        def get_hist_prob(row, target_time):
            """Get historical probability for a deal at target time"""
            deal_id = row['Deal ID']
            current_prob = row.get('HubSpot_Probability', None) if 'HubSpot_Probability' in row.index else None
            return get_probability_at_time(deal_id, target_time, history_df, current_prob)

        merged['HubSpot_Probability_A'] = merged.apply(lambda row: get_hist_prob(row, month_a_end), axis=1)
        merged['HubSpot_Probability_B'] = merged.apply(lambda row: get_hist_prob(row, month_b_end), axis=1)
    else:
        # Fallback: use current probability for both months
        if 'HubSpot_Probability' in merged.columns:
            merged['HubSpot_Probability_A'] = merged['HubSpot_Probability']
            merged['HubSpot_Probability_B'] = merged['HubSpot_Probability']
        else:
            merged['HubSpot_Probability_A'] = None
            merged['HubSpot_Probability_B'] = None

    # Owner names
    def get_owner_name(owner_id):
        if pd.isna(owner_id) or str(owner_id) in ['', 'nan']:
            return 'Unbekannt'
        try:
            owner_id_str = str(int(float(owner_id)))
        except (ValueError, TypeError):
            return 'Unbekannt'
        if owners_map and owner_id_str in owners_map:
            return owners_map[owner_id_str]
        return 'Unbekannt'

    if 'Owner_ID' in merged.columns:
        merged['Owner_Name'] = merged['Owner_ID'].apply(get_owner_name)
    else:
        merged['Owner_Name'] = 'Unbekannt'

    # Fill NaN values
    merged['Current_Phase_A'] = merged['Current_Phase_A'].fillna('-')
    merged['Current_Phase_B'] = merged['Current_Phase_B'].fillna('-')
    merged['Current_Amount_A'] = merged['Current_Amount_A'].fillna('-')
    merged['Current_Amount_B'] = merged['Current_Amount_B'].fillna('-')

    # Deal value
    def get_current_amount(row):
        if row['Current_Amount_B'] != '-':
            return row['Current_Amount_B']
        return row['Current_Amount_A']

    merged['Deal_Value'] = merged.apply(get_current_amount, axis=1)

    # Probabilities
    # Use historical HubSpot probability if available, otherwise fall back to phase-based
    def get_probability_display(row, phase_col, prob_col):
        """Get probability for display (0-100 scale)"""
        phase = row[phase_col]

        # Try to use historical HubSpot probability first
        if prob_col in row.index and pd.notna(row[prob_col]):
            try:
                prob = float(row[prob_col])
                # Handle both 0-100 and 0-1 formats
                if prob <= 1:
                    prob = prob * 100
                return prob
            except (ValueError, TypeError):
                pass

        # Fallback to phase-based probability
        return PHASE_PROBABILITIES.get(phase, 0) * 100

    merged['Probability_A'] = merged.apply(
        lambda row: get_probability_display(row, 'Current_Phase_A', 'HubSpot_Probability_A'),
        axis=1
    )
    merged['Probability_B'] = merged.apply(
        lambda row: get_probability_display(row, 'Current_Phase_B', 'HubSpot_Probability_B'),
        axis=1
    )

    # Weighted values - use historical HubSpot probability if available
    def calculate_weighted_for_row(row, phase_col, prob_col):
        """Calculate weighted value using historical HubSpot probability if available"""
        phase = row[phase_col]
        hubspot_prob = row.get(prob_col, None) if prob_col in row.index else None
        return calculate_weighted_value(row['Deal_Value'], phase, hubspot_prob)

    merged['Weighted_Value_A'] = merged.apply(
        lambda row: calculate_weighted_for_row(row, 'Current_Phase_A', 'HubSpot_Probability_A'),
        axis=1
    )
    merged['Weighted_Value_B'] = merged.apply(
        lambda row: calculate_weighted_for_row(row, 'Current_Phase_B', 'HubSpot_Probability_B'),
        axis=1
    )

    # Deal age
    def calculate_deal_age(create_date_str):
        if pd.isna(create_date_str) or create_date_str in ['', '-']:
            return None
        try:
            create_date = pd.to_datetime(create_date_str, utc=True).tz_localize(None)
            today = pd.Timestamp.now().tz_localize(None)
            return (today - create_date).days
        except (ValueError, TypeError, AttributeError):
            return None

    if 'Create_Date' in merged.columns:
        merged['Deal_Age_Days'] = merged['Create_Date'].apply(calculate_deal_age)
    else:
        merged['Deal_Age_Days'] = None

    # Status change
    def get_status_change(row):
        phase_a = row['Current_Phase_A']
        phase_b = row['Current_Phase_B']
        prob_a = row.get('Probability_A', 0)
        prob_b = row.get('Probability_B', 0)
        closed = ['Gewonnen', 'Verloren', 'Kein Angebot']

        # Check for probability change (threshold: 5% to ignore minor changes)
        prob_changed = abs(prob_b - prob_a) > 5
        prob_change_text = ""
        if prob_changed and prob_a > 0 and prob_b > 0:
            prob_change_text = f" (Prob: {prob_a:.0f}% → {prob_b:.0f}%)"

        if phase_a in closed and phase_b in closed:
            if phase_a == phase_b:
                return f'⚫ Bereits abgeschlossen'
            return f'🔵 {phase_a} → {phase_b}'

        if phase_b == 'Gewonnen' and phase_a not in closed:
            return f'🟢 Gewonnen'
        elif phase_b in ['Verloren', 'Kein Angebot'] and phase_a not in closed:
            return f'🔴 {phase_b}'
        elif phase_a == '-' and phase_b != '-':
            return f'🆕 Neu'
        elif phase_a != phase_b:
            # Phase changed - add probability change if present
            return f'🔵 {phase_a} → {phase_b}{prob_change_text}'
        elif prob_changed:
            # Only probability changed, no phase change
            return f'📊 Prob: {prob_a:.0f}% → {prob_b:.0f}%'

        return '⚪ Keine Änderung'

    merged['Status_Änderung'] = merged.apply(get_status_change, axis=1)

    return merged


def calculate_metrics(comparison_df):
    """Calculate metrics for PDF report"""
    metrics = {
        'total_weighted_a': comparison_df['Weighted_Value_A'].sum(),
        'total_weighted_b': comparison_df['Weighted_Value_B'].sum(),
        'gewonnen_count': 0,
        'gewonnen_amount': 0,
        'verloren_count': 0,
        'verloren_amount': 0,
        'kein_angebot_count': 0,
        'kein_angebot_amount': 0
    }

    metrics['weighted_change'] = metrics['total_weighted_b'] - metrics['total_weighted_a']
    if metrics['total_weighted_a'] > 0:
        metrics['weighted_change_pct'] = (metrics['weighted_change'] / metrics['total_weighted_a']) * 100
    else:
        metrics['weighted_change_pct'] = 0

    # Count closed deals
    for _, row in comparison_df.iterrows():
        status = str(row.get('Status_Änderung', ''))

        try:
            amount = float(str(row.get('Deal_Value', 0)).replace('.', '').replace('€', '').replace(',', '.').strip())
        except (ValueError, AttributeError, TypeError):
            amount = 0

        if '🟢' in status:
            metrics['gewonnen_count'] += 1
            metrics['gewonnen_amount'] += amount
        elif '🔴' in status:
            if 'Kein Angebot' in status:
                metrics['kein_angebot_count'] += 1
                metrics['kein_angebot_amount'] += amount
            else:
                metrics['verloren_count'] += 1
                metrics['verloren_amount'] += amount

    return metrics


def analyze_2025_deals(snapshot_df, owners_map):
    """
    Analyze all deals created in 2025

    Args:
        snapshot_df: DataFrame with deal snapshot data
        owners_map: Dictionary mapping owner IDs to names

    Returns:
        DataFrame with 2025 deals or None on error
    """
    try:
        from src.analysis.deals_2025_analyzer import Deals2025Analyzer
        from src.analysis.stage_mapper import StageMapper
        from src.config import load_config

        logging.info("Starte 2025-Deals-Analyse")

        # Load configuration
        config = load_config()

        # Load stage mapping (optional)
        stage_mapper = None
        try:
            stage_mapping_path = os.path.join(os.getcwd(), 'config', 'stage_mapping.json')
            if os.path.exists(stage_mapping_path):
                stage_mapper = StageMapper(config_path=stage_mapping_path)
        except Exception as e:
            logging.warning(f"Stage mapper konnte nicht geladen werden: {e}")

        # Initialize analyzer
        analyzer = Deals2025Analyzer(config, stage_mapper=stage_mapper, owners_map=owners_map)

        # Generate 2025 deals list
        deals_2025_df = analyzer.generate_2025_deals_list()

        if not deals_2025_df.empty:
            logging.info(f"2025-Deals-Analyse erfolgreich: {len(deals_2025_df)} Deals gefunden")
            return deals_2025_df
        else:
            logging.warning("Keine Deals aus 2025 gefunden")
            return None

    except Exception as e:
        logging.error(f"Fehler bei 2025-Deals-Analyse: {e}")
        return None


def generate_pdf(comparison_df, month_a, month_b, metrics, contact_data=None, deals_2025_df=None, pdf_parts=None):
    """
    Generate PDF reports (split into two separate PDFs)

    Args:
        pdf_parts: List of integers [1, 2] specifying which parts to generate.
                  None or empty list means generate all parts.
    """
    print("\n" + "=" * 60)
    print("SCHRITT 3: PDF-Reports generieren")
    print("=" * 60 + "\n")

    from src.reporting.pdf_generator import PDFGenerator

    # Prepare output directory
    output_dir = Path("output/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d')
    month_a_short = month_a.replace(' ', '_')
    month_b_short = month_b.replace(' ', '_')

    generator = PDFGenerator(company_name="Smart Commerce SE")
    generated_pdfs = []

    # Determine which parts to generate
    generate_all = pdf_parts is None or len(pdf_parts) == 0
    generate_part_1 = generate_all or 1 in pdf_parts
    generate_part_2 = generate_all or 2 in pdf_parts

    # PDF 1: Pipeline Comparison (Übersicht + Deal-Vergleich Detail)
    if generate_part_1:
        print("📄 Generiere PDF 1: Pipeline-Vergleich (Übersicht + Deal-Vergleich Detail)")
        pipeline_pdf_path = str(output_dir / f"1_pipeline_vergleich_{month_a_short}_vs_{month_b_short}_{timestamp}.pdf")

        pdf1_path = generator.generate_pipeline_comparison_pdf(
            comparison_df=comparison_df,
            month_a=month_a,
            month_b=month_b,
            metrics=metrics,
            output_path=pipeline_pdf_path
        )

        logging.info(f"PDF 1 (Pipeline-Vergleich) generiert: {pdf1_path}")
        print(f"   ✅ {pdf1_path}")
        generated_pdfs.append(pdf1_path)
    else:
        print("⏭️  PDF 1 übersprungen (--pdf-parts)")
        logging.info("PDF 1 übersprungen (nicht in --pdf-parts)")

    # PDF 2: Supplementary Reports (Contact Funnel + 2025 Deals)
    if generate_part_2:
        has_supplementary_data = contact_data is not None or (deals_2025_df is not None and not deals_2025_df.empty)

        if has_supplementary_data:
            print("\n📄 Generiere PDF 2: Zusatzberichte (Contact Funnel + 2025 Deals Übersicht)")
            supplementary_pdf_path = str(output_dir / f"2_zusatzberichte_{month_a_short}_vs_{month_b_short}_{timestamp}.pdf")

            pdf2_path = generator.generate_supplementary_reports_pdf(
                month_a=month_a,
                month_b=month_b,
                output_path=supplementary_pdf_path,
                contact_data=contact_data,
                deals_2025_df=deals_2025_df
            )

            if pdf2_path:
                logging.info(f"PDF 2 (Zusatzberichte) generiert: {pdf2_path}")
                print(f"   ✅ {pdf2_path}")
                generated_pdfs.append(pdf2_path)
        else:
            print("\n⏭️  PDF 2 übersprungen (keine Zusatzdaten vorhanden)")
            logging.info("PDF 2 übersprungen - keine Contact-Daten oder 2025-Deals vorhanden")
    else:
        print("\n⏭️  PDF 2 übersprungen (--pdf-parts)")
        logging.info("PDF 2 übersprungen (nicht in --pdf-parts)")

    return generated_pdfs


def main():
    parser = argparse.ArgumentParser(
        description='HubSpot Deal Report Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python generate_report.py                           # Komplette Pipeline (beide PDFs)
  python generate_report.py --skip-fetch              # Ohne HubSpot-Abruf
  python generate_report.py --months "Dezember 2025" "Januar 2026"
  python generate_report.py --pdf-parts 1             # Nur Pipeline-Vergleich PDF
  python generate_report.py --pdf-parts 2             # Nur Zusatzberichte PDF
  python generate_report.py --pdf-parts 1 2           # Beide PDFs (default)
  python generate_report.py --skip-fetch --skip-analysis --pdf-parts 1  # Schnelle PDF-Iteration
        """
    )

    parser.add_argument(
        '--skip-fetch',
        action='store_true',
        help='HubSpot-Abruf überspringen (nutzt vorhandene Daten)'
    )

    parser.add_argument(
        '--skip-analysis',
        action='store_true',
        help='Analyse überspringen (nutzt vorhandene Reports)'
    )

    parser.add_argument(
        '--months',
        nargs=2,
        metavar=('MONAT_A', 'MONAT_B'),
        help='Zu vergleichende Monate (z.B. "Dezember 2025" "Januar 2026")'
    )

    parser.add_argument(
        '--pdf-parts',
        nargs='+',
        type=int,
        choices=[1, 2],
        metavar='N',
        help='Welche PDF-Teile generieren: 1 (Pipeline-Vergleich), 2 (Zusatzberichte). Standard: beide'
    )

    args = parser.parse_args()

    # Setup
    log_file = setup_logging()
    logging.info("=" * 60)
    logging.info("HubSpot Deal Report Pipeline gestartet")
    logging.info("=" * 60)

    print("\n" + "=" * 60)
    print("HubSpot Deal Report Pipeline")
    print("=" * 60)

    try:
        # Step 1: Fetch data
        if not args.skip_fetch:
            if not run_fetch():
                print("\n❌ Fehler beim Datenabruf")
                return 1
        else:
            print("\n⏭️  Datenabruf übersprungen (--skip-fetch)")
            logging.info("Datenabruf übersprungen")

        # Step 2: Run analysis
        if not args.skip_analysis:
            if not run_analysis():
                print("\n❌ Fehler bei der Analyse")
                return 1
        else:
            print("\n⏭️  Analyse übersprungen (--skip-analysis)")
            logging.info("Analyse übersprungen")

        # Step 3: Generate PDF
        logging.info("Lade Daten für PDF-Generierung")

        df = load_movement_data()
        if df is None or df.empty:
            print("\n❌ Keine Bewegungsdaten gefunden")
            print("   Bitte zuerst fetch_deals.py und analyze_deals.py ausführen")
            return 1

        snapshot_df = load_snapshot_data()
        owners_map = load_owners()
        history_df = load_history_data()

        all_months = get_available_months(df)
        if len(all_months) < 2:
            print(f"\n❌ Nicht genug Monate für Vergleich (gefunden: {len(all_months)})")
            return 1

        # Select months
        if args.months:
            month_a, month_b = args.months
            if month_a not in all_months or month_b not in all_months:
                print(f"\n❌ Ungültige Monate. Verfügbar: {', '.join(all_months)}")
                return 1
        else:
            # Default: last two months
            month_a = all_months[-2]
            month_b = all_months[-1]

        logging.info(f"Vergleiche: {month_a} vs {month_b}")
        print(f"\n📊 Vergleiche: {month_a} vs {month_b}")

        # Get month data (pass comparison_start_month to match dashboard filtering)
        month_a_data = get_month_data(df, month_a, all_months, comparison_start_month=month_a)
        month_b_data = get_month_data(df, month_b, all_months, comparison_start_month=month_a)

        # Merge and calculate
        comparison = merge_months(
            month_a_data, month_b_data, month_a, month_b,
            snapshot_df=snapshot_df, owners_map=owners_map, history_df=history_df
        )

        metrics = calculate_metrics(comparison)

        # Contact Pipeline (with error handling)
        contact_data = None
        try:
            logging.info("Starte Contact-Pipeline")

            # Step 1b: Fetch contacts
            if not args.skip_fetch:
                if not run_fetch_contacts():
                    print("\n⚠️  WARNUNG: Contact-Abruf fehlgeschlagen")
                    print("   → PDF wird ohne Contact-Sektion generiert\n")
                    logging.warning("Contact-Abruf fehlgeschlagen - fahre ohne Contact-Daten fort")
                else:
                    # Step 2b: Analyze contacts
                    if not args.skip_analysis:
                        if not run_analysis_contacts():
                            print("\n⚠️  WARNUNG: Contact-Analyse fehlgeschlagen")
                            print("   → PDF wird ohne Contact-Sektion generiert\n")
                            logging.warning("Contact-Analyse fehlgeschlagen - fahre ohne Contact-Daten fort")
                        else:
                            # Load contact data
                            contact_data = load_contact_data()
                            if contact_data:
                                logging.info("Contact-Daten erfolgreich geladen")
                            else:
                                print("\n⚠️  WARNUNG: Contact-Daten konnten nicht geladen werden")
                                print("   → PDF wird ohne Contact-Sektion generiert\n")
                    else:
                        # Analysis skipped, try to load existing data
                        contact_data = load_contact_data()
                        if contact_data:
                            logging.info("Vorhandene Contact-Daten geladen")
            else:
                # Fetch skipped, try to load existing data
                contact_data = load_contact_data()
                if contact_data:
                    logging.info("Vorhandene Contact-Daten geladen")

        except Exception as e:
            logging.error(f"Contact-Pipeline fehlgeschlagen: {e}")
            print(f"\n⚠️  WARNUNG: Contact-Pipeline fehlgeschlagen: {e}")
            print("   → PDF wird ohne Contact-Sektion generiert\n")
            contact_data = None

        # 2025 Deals Analysis
        deals_2025_df = None
        try:
            logging.info("Starte 2025-Deals-Analyse")
            deals_2025_df = analyze_2025_deals(snapshot_df, owners_map)
            if deals_2025_df is not None:
                logging.info("2025-Deals-Analyse erfolgreich")
            else:
                print("\n⚠️  WARNUNG: Keine Deals aus 2025 gefunden")
                print("   → PDF wird ohne 2025-Deals-Übersicht generiert\n")
        except Exception as e:
            logging.error(f"2025-Deals-Analyse fehlgeschlagen: {e}")
            print(f"\n⚠️  WARNUNG: 2025-Deals-Analyse fehlgeschlagen: {e}")
            print("   → PDF wird ohne 2025-Deals-Übersicht generiert\n")
            deals_2025_df = None

        # Generate PDFs
        pdf_paths = generate_pdf(
            comparison, month_a, month_b, metrics,
            contact_data=contact_data,
            deals_2025_df=deals_2025_df,
            pdf_parts=args.pdf_parts
        )

        # Summary
        print("\n" + "=" * 60)
        print("✅ Pipeline erfolgreich abgeschlossen")
        print("=" * 60)
        print(f"\n📄 Generierte PDF-Reports:")
        for idx, pdf_path in enumerate(pdf_paths, 1):
            print(f"   {idx}. {pdf_path}")
        print(f"\n📋 Log-Datei: {log_file}")
        print()

        logging.info("Pipeline erfolgreich abgeschlossen")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Abgebrochen durch Benutzer")
        return 130

    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        logging.exception("Unerwarteter Fehler")
        return 1


if __name__ == '__main__':
    sys.exit(main())
