#!/usr/bin/env python3
"""
Side-by-Side Monatsvergleich Dashboard (Excel-Style)
"""
import streamlit as st
import pandas as pd
from glob import glob
import os

# HubSpot Configuration
# Set HUBSPOT_PORTAL_ID in .env or environment
# You can find it in HubSpot: Settings > Account Setup > Account Defaults
HUBSPOT_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "19645216")

# Page Config
st.set_page_config(
    page_title="Monatsvergleich Pipeline",
    page_icon="📊",
    layout="wide"
)

# Load latest CSV
@st.cache_data
def load_data():
    pattern = "output/reports/deal_movements_detail_*.csv"
    files = glob(pattern)
    if not files:
        return pd.DataFrame()
    latest = max(files, key=os.path.getmtime)
    df = pd.read_csv(latest, encoding='utf-8-sig')
    # Convert Deal ID to string for consistent merging
    if 'Deal ID' in df.columns:
        df['Deal ID'] = df['Deal ID'].astype(str)
    return df

@st.cache_data
def load_snapshot_data():
    """Load latest snapshot data with HubSpot projected amounts and create date"""
    pattern = "output/deals_snapshot_*.csv"
    files = glob(pattern)
    if not files:
        return pd.DataFrame()
    latest = max(files, key=os.path.getmtime)
    df = pd.read_csv(latest, encoding='utf-8-sig')
    # Convert Deal ID to string to match with main data
    df['deal_id'] = df['deal_id'].astype(str)

    # Rename columns for easier merging (only if they exist)
    rename_map = {
        'deal_id': 'Deal ID',
        'hs_forecast_amount': 'HubSpot_Forecast',
        'hs_forecast_probability': 'HubSpot_Probability',
        'create_date': 'Create_Date',
        'hubspot_owner_id': 'Owner_ID',
        'notes_last_contacted': 'Last_Contacted',
        'notes_last_updated': 'Last_Updated',
        'num_notes': 'Num_Notes',
        'hs_lastmodifieddate': 'Last_Modified',
        'hs_num_associated_queue_tasks': 'Open_Tasks',
        'num_associated_contacts': 'Num_Contacts'
    }

    # Only rename columns that exist
    existing_renames = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=existing_renames)

    # Select only columns that exist in the dataframe
    desired_columns = ['Deal ID', 'HubSpot_Forecast', 'HubSpot_Probability', 'Create_Date',
                      'Owner_ID', 'Last_Contacted', 'Last_Updated', 'Num_Notes', 'Last_Modified',
                      'Open_Tasks', 'Num_Contacts']
    available_columns = [col for col in desired_columns if col in df.columns]

    # Add missing columns as empty
    for col in desired_columns:
        if col not in df.columns:
            df[col] = ''

    return df[desired_columns]

@st.cache_data
def load_owners():
    """Load owner mapping from HubSpot API"""
    # This will be populated when we run analyze_deals.py
    # For now, we return an empty dict that will be populated dynamically
    pattern = "output/owners_*.json"
    files = glob(pattern)
    if not files:
        return {}
    latest = max(files, key=os.path.getmtime)
    import json
    with open(latest, 'r') as f:
        return json.load(f)

def get_month_data(df, month_year, all_months, comparison_start_month=None):
    """
    Get ALL active deals at the end of a specific month

    This reconstructs the complete state by looking at all months up to and including
    the target month, finding the last known state for each deal.

    Args:
        df: DataFrame with deal data
        month_year: Target month (e.g., "Januar 2026")
        all_months: Sorted list of all available months
        comparison_start_month: Optional start month for comparison range
    """
    # Get index of target month
    target_idx = all_months.index(month_year)

    # Get all months up to and including target month
    months_until_target = all_months[:target_idx + 1]

    # Filter dataframe to only include these months
    df_until_target = df[df['MonthYear'].isin(months_until_target)].copy()

    # For each deal, get the LAST known state (most recent entry)
    # Group by Deal ID and take the last entry (chronologically)
    df_until_target['sort_key'] = df_until_target['MonthYear'].map(
        {m: i for i, m in enumerate(all_months)}
    )

    latest_states = df_until_target.sort_values('sort_key').groupby('Deal ID').last().reset_index()

    # Use the end-of-month state as current state
    latest_states['Current_Phase'] = latest_states['Status (Monatsende)']
    latest_states['Current_Amount'] = latest_states['Wert Monatsende (€)']

    # Filter out deals that are already won or lost (no longer active)
    active_deals = latest_states[
        ~latest_states['Current_Phase'].isin(['Gewonnen', 'Verloren', 'Kein Angebot'])
    ].copy()

    # Determine which months to include for won/lost deals
    if comparison_start_month:
        # Include won/lost deals from comparison start month onwards
        start_idx = all_months.index(comparison_start_month)
        comparison_months = all_months[start_idx:target_idx + 1]
    else:
        # Default: only this month
        comparison_months = [month_year]

    # Include deals won/lost in the comparison period
    won_lost_in_period = df_until_target[
        (df_until_target['MonthYear'].isin(comparison_months)) &
        (df_until_target['Status (Monatsende)'].isin(['Gewonnen', 'Verloren', 'Kein Angebot']))
    ].copy()

    if not won_lost_in_period.empty:
        won_lost_in_period['Current_Phase'] = won_lost_in_period['Status (Monatsende)']
        won_lost_in_period['Current_Amount'] = won_lost_in_period['Wert Monatsende (€)']

        # Combine active deals with won/lost deals from comparison period
        all_deals = pd.concat([active_deals, won_lost_in_period], ignore_index=True)
        # Remove duplicates (keep the won/lost version)
        all_deals = all_deals.drop_duplicates(subset=['Deal ID'], keep='last')
    else:
        all_deals = active_deals

    return all_deals[['Deal ID', 'Deal Name', 'Current_Phase', 'Current_Amount']]

def create_hubspot_link(deal_id, deal_name):
    """
    Create a clickable HubSpot link for a deal

    Args:
        deal_id: HubSpot Deal ID
        deal_name: Deal name

    Returns:
        Markdown link if portal ID is configured, otherwise just the deal name
    """
    if HUBSPOT_PORTAL_ID != "YOUR_PORTAL_ID":
        url = f"https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{deal_id}"
        return f"[{deal_name}]({url})"
    else:
        return deal_name

# Phase probabilities for weighted values
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

def calculate_weighted_value(amount_str, phase):
    """Calculate weighted deal value based on phase probability"""
    if amount_str == '-' or pd.isna(amount_str):
        return 0
    try:
        # Parse amount
        amount = float(str(amount_str).replace('.', '').replace('€', '').replace(',', '.').strip())
        # Get probability for phase
        probability = PHASE_PROBABILITIES.get(phase, 0)
        return amount * probability
    except:
        return 0

def merge_months(month_a_df, month_b_df, month_a_name, month_b_name, snapshot_df=None, owners_map=None):
    """Merge two months side-by-side"""
    # Convert Deal ID to string to ensure consistent types
    month_a_df = month_a_df.copy()
    month_b_df = month_b_df.copy()
    month_a_df['Deal ID'] = month_a_df['Deal ID'].astype(str)
    month_b_df['Deal ID'] = month_b_df['Deal ID'].astype(str)

    # Outer join to get all deals from both months
    merged = pd.merge(
        month_a_df,
        month_b_df,
        on=['Deal ID', 'Deal Name'],
        how='outer',
        suffixes=('_A', '_B')
    )

    # Merge with snapshot data to get HubSpot projected values
    if snapshot_df is not None and not snapshot_df.empty:
        # Ensure Deal ID is string in merged df as well
        merged['Deal ID'] = merged['Deal ID'].astype(str)
        merged = pd.merge(
            merged,
            snapshot_df,
            on='Deal ID',
            how='left'
        )

    # Map owner IDs to owner names - ALWAYS create Owner_Name column
    def get_owner_name(owner_id):
        """Get owner name from ID, fallback to ID if name not found"""
        if pd.isna(owner_id) or str(owner_id) == '' or str(owner_id) == 'nan':
            return 'Unbekannt'
        # Convert to int first to remove any decimal points, then to string
        try:
            owner_id_str = str(int(float(owner_id)))
        except (ValueError, TypeError):
            return 'Unbekannt'
        # Try to get name from mapping
        if owners_map and owner_id_str in owners_map:
            return owners_map[owner_id_str]
        # Fallback: show ID if no name available
        return 'Unbekannt'

    # ALWAYS create these columns, even if snapshot_df wasn't merged
    if 'Owner_ID' in merged.columns:
        merged['Owner_Name'] = merged['Owner_ID'].apply(get_owner_name)
    else:
        merged['Owner_Name'] = 'Unbekannt'

    # Calculate last activity date (most recent of last_contacted, last_updated, last_modified)
    def get_last_activity(row):
        """Get the most recent activity date"""
        dates = []
        for col in ['Last_Contacted', 'Last_Updated', 'Last_Modified']:
            if col in row and pd.notna(row[col]) and row[col] != '' and str(row[col]) != 'nan':
                try:
                    dates.append(pd.to_datetime(row[col], utc=True))
                except:
                    pass
        if dates:
            return max(dates).strftime('%Y-%m-%d')
        return '-'

    # ALWAYS create Last_Activity column
    merged['Last_Activity'] = merged.apply(get_last_activity, axis=1)

    # ALWAYS create Open_Tasks column
    if 'Open_Tasks' in merged.columns:
        merged['Open_Tasks'] = merged['Open_Tasks'].fillna(0)
    else:
        merged['Open_Tasks'] = 0

    # Fill NaN values
    merged['Current_Phase_A'] = merged['Current_Phase_A'].fillna('-')
    merged['Current_Phase_B'] = merged['Current_Phase_B'].fillna('-')
    merged['Current_Amount_A'] = merged['Current_Amount_A'].fillna('-')
    merged['Current_Amount_B'] = merged['Current_Amount_B'].fillna('-')

    # Use the most recent (non-empty) amount value
    def get_current_amount(row):
        if row['Current_Amount_B'] != '-':
            return row['Current_Amount_B']
        return row['Current_Amount_A']

    merged['Deal_Value'] = merged.apply(get_current_amount, axis=1)

    # Calculate probabilities for each month
    # Month A (historical): Always use phase-based probability
    def get_probability_for_phase(phase):
        """Get probability percentage for a given phase"""
        return PHASE_PROBABILITIES.get(phase, 0) * 100

    merged['Probability_A'] = merged['Current_Phase_A'].apply(get_probability_for_phase)

    # Month B (current): Use HubSpot individual probability if available, otherwise phase-based
    def get_probability_b(row):
        """Get probability for month B - use HubSpot if available, otherwise phase-based"""
        # Try to use HubSpot's individual probability (only available for current month)
        if 'HubSpot_Probability' in row and pd.notna(row['HubSpot_Probability']) and row['HubSpot_Probability'] != '':
            try:
                hubspot_prob = float(row['HubSpot_Probability'])
                # HubSpot stores as decimal (0.0 to 1.0), convert to percentage
                return hubspot_prob * 100
            except (ValueError, TypeError):
                pass
        # Fallback to phase-based
        return get_probability_for_phase(row['Current_Phase_B'])

    merged['Probability_B'] = merged.apply(get_probability_b, axis=1)

    # Calculate weighted values
    # Month A (historical): Phase-based calculation
    merged['Weighted_Value_A'] = merged.apply(
        lambda row: calculate_weighted_value(row['Deal_Value'], row['Current_Phase_A']),
        axis=1
    )

    # Month B (current): Use HubSpot forecast amount if available, otherwise calculate
    def get_weighted_value_b(row):
        """Get weighted value for month B - use HubSpot forecast (manual) if available"""
        # Try to use HubSpot's forecast amount (manually set, already weighted)
        if 'HubSpot_Forecast' in row and pd.notna(row['HubSpot_Forecast']) and row['HubSpot_Forecast'] != '' and row['HubSpot_Forecast'] != 0:
            try:
                forecast_val = float(row['HubSpot_Forecast'])
                if forecast_val > 0:
                    return forecast_val
            except (ValueError, TypeError):
                pass
        # Fallback: Calculate from deal value and probability
        try:
            if row['Deal_Value'] == '-' or pd.isna(row['Deal_Value']):
                return 0
            amount = float(str(row['Deal_Value']).replace('.', '').replace('€', '').replace(',', '.').strip())
            probability = row['Probability_B'] / 100  # Convert percentage to decimal
            return amount * probability
        except:
            return 0

    merged['Weighted_Value_B'] = merged.apply(get_weighted_value_b, axis=1)

    # Calculate deal age in days
    def calculate_deal_age(create_date_str):
        """Calculate days since deal creation"""
        if pd.isna(create_date_str) or create_date_str == '' or create_date_str == '-':
            return None
        try:
            # Parse ISO format date and convert to tz-naive for comparison
            create_date = pd.to_datetime(create_date_str, utc=True).tz_localize(None)
            today = pd.Timestamp.now().tz_localize(None)
            age_days = (today - create_date).days
            return age_days
        except Exception as e:
            return None

    merged['Deal_Age_Days'] = merged.apply(
        lambda row: calculate_deal_age(row.get('Create_Date')),
        axis=1
    )

    # Determine status change with timing information
    def get_status_change(row, month_a_name, month_b_name):
        phase_a = row['Current_Phase_A']
        phase_b = row['Current_Phase_B']

        closed_statuses = ['Gewonnen', 'Verloren', 'Kein Angebot']

        # Check if deal was already closed before month A
        if phase_a in closed_statuses and phase_b in closed_statuses:
            if phase_a == phase_b:
                return f'⚫ Bereits abgeschlossen (vor {month_a_name})'
            else:
                # Status changed between closed states
                return f'🔵 Status geändert: {phase_a} → {phase_b}'

        # Check if deal was closed in the comparison period
        if phase_b == 'Gewonnen' and phase_a not in closed_statuses:
            return f'🟢 Gewonnen in {month_b_name}'
        elif phase_b == 'Verloren' and phase_a not in closed_statuses:
            return f'🔴 Verloren in {month_b_name}'
        elif phase_b == 'Kein Angebot' and phase_a not in closed_statuses:
            return f'🔴 Kein Angebot in {month_b_name}'

        # New deal
        elif phase_a == '-' and phase_b != '-':
            if phase_b in closed_statuses:
                return f'🆕 Neu und bereits abgeschlossen in {month_b_name}'
            else:
                return f'🆕 Neu hinzugekommen'

        # Deal removed (shouldn't happen normally)
        elif phase_a != '-' and phase_b == '-':
            return '❌ Entfernt'

        # No change
        elif phase_a == phase_b:
            return '-'

        # Phase changed (active to active)
        else:
            return f'🔵 Phase geändert: {phase_a} → {phase_b}'

    merged['Status_Änderung'] = merged.apply(lambda row: get_status_change(row, month_a_name, month_b_name), axis=1)

    # Reorder columns (keep Deal ID for HubSpot links)
    display_cols = [
        'Deal ID',
        'Deal Name',
        'Deal_Value',
        'Deal_Age_Days',
        'Current_Phase_A',
        'Current_Phase_B',
        'Probability_A',
        'Probability_B',
        'Weighted_Value_A',
        'Weighted_Value_B',
        'Status_Änderung',
        'Owner_Name',
        'Last_Activity',
        'Open_Tasks'
    ]

    return merged[display_cols]

def style_row(row):
    """Apply styling based on status change"""
    if '🟢' in str(row['Status_Änderung']):
        return ['background-color: #d4edda'] * len(row)  # Green
    elif '🔴' in str(row['Status_Änderung']):
        return ['background-color: #f8d7da'] * len(row)  # Red
    elif '🔵' in str(row['Status_Änderung']):
        return ['background-color: #d1ecf1'] * len(row)  # Blue
    else:
        return [''] * len(row)

# Main App
def main():
    st.title("📊 Monatlicher Pipeline-Vergleich")
    st.markdown("**Side-by-Side Ansicht zweier Monate**")

    # Load data
    df = load_data()
    snapshot_df = load_snapshot_data()
    owners_map = load_owners()

    if df.empty:
        st.error("Keine Daten gefunden. Bitte führen Sie 'python fetch_deals.py' aus.")
        return

    # Prepare month labels
    df['MonthYear'] = df['Monat'] + ' ' + df['Jahr'].astype(str)

    # Sort months chronologically (not alphabetically)
    month_order = {
        'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
        'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
    }

    def sort_month_key(month_year_str):
        """Convert 'Monat YYYY' to sortable tuple (year, month_num)"""
        parts = month_year_str.split()
        month_name = parts[0]
        year = int(parts[1])
        month_num = month_order.get(month_name, 0)
        return (year, month_num)

    available_months = sorted(df['MonthYear'].unique().tolist(), key=sort_month_key)

    # Initialize session state
    if 'month_a_idx' not in st.session_state:
        st.session_state.month_a_idx = max(0, len(available_months) - 2)
    if 'month_b_idx' not in st.session_state:
        st.session_state.month_b_idx = len(available_months) - 1

    # Month selection
    col_a, col_b = st.columns(2)

    with col_b:
        # First select current month (right side)
        month_b = st.selectbox(
            "📅 Aktueller Monat (rechts)",
            available_months,
            index=st.session_state.month_b_idx,
            key='month_b_select'
        )
        # Get index of selected month_b
        month_b_idx = available_months.index(month_b)

    with col_a:
        # Filter month_a options to only show months BEFORE month_b
        available_months_a = available_months[:month_b_idx] if month_b_idx > 0 else []

        if not available_months_a:
            st.warning("Kein Vormonat verfügbar")
            month_a = None
        else:
            # Ensure month_a_idx is within valid range
            month_a_idx = min(st.session_state.month_a_idx, len(available_months_a) - 1)
            month_a = st.selectbox(
                "📅 Vormonat (links)",
                available_months_a,
                index=month_a_idx,
                key='month_a_select'
            )

    st.divider()

    # Check if month_a is available
    if month_a is None:
        st.info("Bitte wählen Sie einen späteren Monat als 'Aktueller Monat', um einen Vergleich anzuzeigen.")
        return

    # Get data for both months (all active deals at end of each month)
    # For month A: just this month
    month_a_data = get_month_data(df, month_a, available_months, comparison_start_month=month_a)
    # For month B: include won/lost deals from month A onwards
    month_b_data = get_month_data(df, month_b, available_months, comparison_start_month=month_a)

    # Merge and display
    comparison = merge_months(month_a_data, month_b_data, month_a, month_b, snapshot_df, owners_map)

    # Pipeline value metrics (weighted values)
    # Only include active deals (exclude Won, Lost, and "Kein Angebot")
    col_v1, col_v2, col_v3 = st.columns(3)

    # Filter for active deals only (not closed) - use original column names
    active_deals_a = comparison[~comparison['Current_Phase_A'].isin(['Gewonnen', 'Verloren', 'Kein Angebot', '-'])]
    active_deals_b = comparison[~comparison['Current_Phase_B'].isin(['Gewonnen', 'Verloren', 'Kein Angebot', '-'])]

    total_weighted_a = active_deals_a['Weighted_Value_A'].sum()
    total_weighted_b = active_deals_b['Weighted_Value_B'].sum()
    weighted_change = total_weighted_b - total_weighted_a
    weighted_change_pct = (weighted_change / total_weighted_a * 100) if total_weighted_a > 0 else 0

    with col_v1:
        st.metric(
            f"Pipeline Wert {month_a}",
            f"{total_weighted_a:,.0f} €".replace(',', '.'),
            help="Summe aller gewichteten Deal-Werte"
        )
    with col_v2:
        st.metric(
            f"Pipeline Wert {month_b}",
            f"{total_weighted_b:,.0f} €".replace(',', '.'),
            delta=f"{weighted_change:+,.0f} €".replace(',', '.'),
            help="Summe aller gewichteten Deal-Werte"
        )
    with col_v3:
        st.metric(
            "Veränderung",
            f"{weighted_change_pct:+.1f}%",
            help="Prozentuale Veränderung der Pipeline"
        )

    st.divider()

    # Closed deals metrics (Won, Lost, Kein Angebot)
    st.markdown("### 💰 Abgeschlossene Deals")
    col_c1, col_c2, col_c3 = st.columns(3)

    # Helper function to calculate amounts for specific status
    def calculate_amount_for_status(df, status_values):
        """Calculate total amount for deals with specific status in month B"""
        # Use original column name 'Current_Phase_B' instead of renamed column
        filtered_deals = df[df['Current_Phase_B'].isin(status_values)]
        total = 0
        for amount_str in filtered_deals['Deal_Value']:
            if amount_str != '-' and pd.notna(amount_str):
                try:
                    amount = float(str(amount_str).replace('.', '').replace('€', '').replace(',', '.').strip())
                    total += amount
                except:
                    pass
        return total

    # Calculate amounts for closed deals
    gewonnen_amount = calculate_amount_for_status(comparison, ['Gewonnen'])
    verloren_amount = calculate_amount_for_status(comparison, ['Verloren'])
    kein_angebot_amount = calculate_amount_for_status(comparison, ['Kein Angebot'])

    with col_c1:
        st.metric(
            "🟢 Gewonnen",
            f"{gewonnen_amount:,.0f} €".replace(',', '.'),
            help="Gesamtwert aller gewonnenen Deals"
        )
    with col_c2:
        st.metric(
            "🔴 Verloren",
            f"{verloren_amount:,.0f} €".replace(',', '.'),
            help="Gesamtwert aller verlorenen Deals"
        )
    with col_c3:
        st.metric(
            "⚫ Kein Angebot",
            f"{kein_angebot_amount:,.0f} €".replace(',', '.'),
            help="Gesamtwert aller Deals ohne Angebot"
        )

    st.divider()

    # Display table with styling
    st.subheader(f"Vergleich: {month_a} vs {month_b}")

    # Create display dataframe with renamed columns
    display_comparison = comparison.copy()

    # Helper function to parse Euro amounts
    def parse_euro_amount(amount_str):
        """Parse formatted Euro amount to float"""
        if pd.isna(amount_str) or amount_str == '-' or amount_str == '':
            return None
        try:
            # Remove Euro symbol and thousand separators, then convert
            cleaned = str(amount_str).replace('€', '').replace('.', '').replace(',', '.').strip()
            return float(cleaned)
        except:
            return None

    # Parse Deal_Value to numeric for right alignment
    display_comparison['Deal_Value_Numeric'] = display_comparison['Deal_Value'].apply(parse_euro_amount)

    # Weighted values and probabilities are already numeric (from merge_months)

    # Keep Deal Name as text, create separate clickable link column
    if 'Deal ID' in display_comparison.columns:
        # Create clickable HubSpot link column
        display_comparison['🔗'] = display_comparison['Deal ID'].apply(
            lambda deal_id: f"https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{deal_id}"
        )
        # Remove Deal ID column as it's only needed for links
        display_comparison = display_comparison.drop(columns=['Deal ID'])

    # Remove original Deal_Value column (we now use Deal_Value_Numeric)
    display_comparison = display_comparison.drop(columns=['Deal_Value'])

    # Rename columns for display
    display_comparison = display_comparison.rename(columns={
        'Deal_Value_Numeric': 'Auftragswert',
        'Deal_Age_Days': 'Alter (Tage)',
        'Owner_Name': 'Verantwortlich',
        'Last_Activity': 'Letzte Aktivität',
        'Open_Tasks': 'Offene Aufgaben',
        'Num_Notes': 'Notizen',
        'Current_Phase_A': f'Phase {month_a}',
        'Current_Phase_B': f'Phase {month_b}',
        'Probability_A': f'% {month_a}',
        'Probability_B': f'% {month_b}',
        'Weighted_Value_A': f'Gewichtet {month_a}',
        'Weighted_Value_B': f'Gewichtet {month_b}',
        'Status_Änderung': 'Status-Änderung'
    })

    # Reorder columns - compact view without owner/activity fields
    display_columns = [
        'Deal Name',
        'Auftragswert',
        'Alter (Tage)',
        f'Phase {month_a}',
        f'% {month_a}',
        f'Gewichtet {month_a}',
        f'Phase {month_b}',
        f'% {month_b}',
        f'Gewichtet {month_b}',
        'Status-Änderung',
        '🔗'
    ]

    # Keep full data for detail view below
    detail_data = display_comparison.copy()

    # Create display table
    display_comparison = display_comparison[display_columns]

    # Apply color styling based on status change with timing
    def style_row_by_status(row):
        status = str(row['Status-Änderung'])
        if '🟢' in status:  # Gewonnen
            return ['background-color: #d4edda'] * len(row)  # Grün
        elif '🔴' in status:  # Verloren oder Kein Angebot
            return ['background-color: #f8d7da'] * len(row)  # Rot
        elif '⚫' in status:  # Bereits abgeschlossen
            return ['background-color: #e9ecef'] * len(row)  # Grau
        elif '🔵' in status:  # Phase geändert
            return ['background-color: #d1ecf1'] * len(row)  # Blau
        elif '🆕' in status:  # Neu
            return ['background-color: #fff3cd'] * len(row)  # Gelb
        else:
            return [''] * len(row)

    styled_df = display_comparison.style.apply(style_row_by_status, axis=1)

    # Display with column configuration for clickable links and right-aligned amounts
    st.dataframe(
        styled_df,
        use_container_width=False,
        height=600,
        hide_index=True,
        column_config={
            '🔗': st.column_config.LinkColumn(
                '🔗',
                help='Deal in HubSpot öffnen',
                width='small'
            ),
            'Deal Name': st.column_config.TextColumn(
                'Deal Name',
                width='large',
                help='Name des Deals'
            ),
            'Auftragswert': st.column_config.NumberColumn(
                'Auftragswert',
                format='%.0f €',
                width='medium',
                help='Auftragswert in Euro'
            ),
            'Alter (Tage)': st.column_config.NumberColumn(
                'Alter (Tage)',
                format='%d',
                width='small',
                help='Tage seit Deal-Erstellung'
            ),
            f'Phase {month_a}': st.column_config.TextColumn(
                f'Phase {month_a}',
                width='medium',
                help=f'Sales-Phase am Ende von {month_a}'
            ),
            f'% {month_a}': st.column_config.NumberColumn(
                f'% {month_a}',
                format='%.0f%%',
                width='small',
                help='Gewichtung basierend auf Phase'
            ),
            f'Gewichtet {month_a}': st.column_config.NumberColumn(
                f'Gewichtet {month_a}',
                format='%.0f €',
                width='medium',
                help='Gewichteter Wert (Auftragswert × Wahrscheinlichkeit)'
            ),
            f'Phase {month_b}': st.column_config.TextColumn(
                f'Phase {month_b}',
                width='medium',
                help=f'Sales-Phase am Ende von {month_b}'
            ),
            f'% {month_b}': st.column_config.NumberColumn(
                f'% {month_b}',
                format='%.0f%%',
                width='small',
                help='Gewichtung basierend auf Phase'
            ),
            f'Gewichtet {month_b}': st.column_config.NumberColumn(
                f'Gewichtet {month_b}',
                format='%.0f €',
                width='medium',
                help='Gewichteter Wert (Auftragswert × Wahrscheinlichkeit)'
            ),
            'Status-Änderung': st.column_config.TextColumn(
                'Status-Änderung',
                width='large',
                help='Zeigt wann und wie sich der Deal-Status geändert hat'
            )
        }
    )

    # Deal Details List below table
    st.divider()
    st.subheader("📋 Deal-Details")
    st.markdown("**Verantwortliche, Aktivitäten und Aufgaben**")

    # Display deal details in expandable sections
    # Use comparison DataFrame directly (before column filtering) to ensure we have all data
    for _, row in comparison.iterrows():
        deal_name = row.get('Deal Name', 'Unbekannt')

        # Get Owner_Name directly from comparison (before renaming)
        if 'Owner_Name' in row:
            owner = row['Owner_Name']
        else:
            owner = 'Unbekannt'

        # Get Last_Activity directly
        if 'Last_Activity' in row:
            last_activity = row['Last_Activity']
        else:
            last_activity = '-'

        # Get Open_Tasks directly
        if 'Open_Tasks' in row:
            open_tasks = row['Open_Tasks']
        else:
            open_tasks = 0

        # Format open tasks
        if pd.notna(open_tasks) and open_tasks != '':
            try:
                open_tasks = int(float(open_tasks))
            except:
                open_tasks = 0
        else:
            open_tasks = 0

        # Create expander for each deal
        with st.expander(f"**{deal_name}**"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"👤 **Verantwortlich:** {owner}")
            with col2:
                st.markdown(f"📅 **Letzte Aktivität:** {last_activity}")
            with col3:
                tasks_emoji = "✅" if open_tasks == 0 else "⚠️"
                st.markdown(f"{tasks_emoji} **Offene Aufgaben:** {open_tasks}")

    # Download button
    csv = comparison.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 Als CSV herunterladen",
        data=csv,
        file_name=f"vergleich_{month_a}_vs_{month_b}.csv",
        mime="text/csv"
    )

if __name__ == '__main__':
    main()
