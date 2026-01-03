#!/usr/bin/env python3
"""
Side-by-Side Monatsvergleich Dashboard (Excel-Style)
"""
import streamlit as st
import pandas as pd
from glob import glob
import os

# HubSpot Configuration
# TODO: Replace with your actual HubSpot Portal ID
# You can find it in HubSpot: Settings > Account Setup > Account Defaults
HUBSPOT_PORTAL_ID = "19645216"  # Replace with your Portal ID

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
    return pd.read_csv(latest, encoding='utf-8-sig')

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

def merge_months(month_a_df, month_b_df, month_a_name, month_b_name):
    """Merge two months side-by-side"""
    # Outer join to get all deals from both months
    merged = pd.merge(
        month_a_df,
        month_b_df,
        on=['Deal ID', 'Deal Name'],
        how='outer',
        suffixes=('_A', '_B')
    )

    # Fill NaN values
    merged['Current_Phase_A'] = merged['Current_Phase_A'].fillna('-')
    merged['Current_Phase_B'] = merged['Current_Phase_B'].fillna('-')
    merged['Current_Amount_A'] = merged['Current_Amount_A'].fillna('-')
    merged['Current_Amount_B'] = merged['Current_Amount_B'].fillna('-')

    # Determine status change
    def get_status_change(row):
        phase_a = row['Current_Phase_A']
        phase_b = row['Current_Phase_B']

        if phase_b == 'Gewonnen' and phase_a != 'Gewonnen':
            return '🟢 Abgeschlossen und gewonnen'
        elif 'Verloren' in str(phase_b) and 'Verloren' not in str(phase_a):
            return '🔴 Abgeschlossen und verloren'
        elif phase_a == '-' and phase_b != '-':
            return '🆕 Neu hinzugekommen'
        elif phase_a != '-' and phase_b == '-':
            return '❌ Entfernt'
        elif phase_a == phase_b:
            return '-'
        else:
            return '🔵 Phase geändert'

    merged['Status_Änderung'] = merged.apply(get_status_change, axis=1)

    # Reorder columns (keep Deal ID for HubSpot links)
    display_cols = [
        'Deal ID',
        'Deal Name',
        'Current_Phase_A',
        'Current_Phase_B',
        'Status_Änderung',
        'Current_Amount_A',
        'Current_Amount_B'
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
    if df.empty:
        st.error("Keine Daten gefunden. Bitte führen Sie 'python analyze_deals.py' aus.")
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
    comparison = merge_months(month_a_data, month_b_data, month_a, month_b)

    # Statistics (before renaming columns)
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    won_count = len(comparison[comparison['Status_Änderung'].str.contains('gewonnen', na=False)])
    lost_count = len(comparison[comparison['Status_Änderung'].str.contains('verloren', na=False)])
    new_count = len(comparison[comparison['Status_Änderung'].str.contains('Neu', na=False)])

    with col_s1:
        st.metric("Gesamt Deals", len(comparison))
    with col_s2:
        st.metric("🟢 Gewonnen", won_count)
    with col_s3:
        st.metric("🔴 Verloren", lost_count)
    with col_s4:
        st.metric("🆕 Neu", new_count)

    st.divider()

    # Display table with styling
    st.subheader(f"Vergleich: {month_a} vs {month_b}")

    # Create display dataframe with renamed columns
    display_comparison = comparison.copy()

    # Store Deal Name for later, create URL column
    if 'Deal ID' in display_comparison.columns:
        display_comparison['Deal_Name_Text'] = display_comparison['Deal Name']
        display_comparison['Deal Name'] = display_comparison['Deal ID'].apply(
            lambda deal_id: f"https://app.hubspot.com/contacts/{HUBSPOT_PORTAL_ID}/deal/{deal_id}"
        )
        # Remove Deal ID column as it's only needed for links
        display_comparison = display_comparison.drop(columns=['Deal ID'])

    # Rename columns for display
    display_comparison.columns = [
        'HubSpot Link',
        f'Salesphase {month_a}',
        f'Salesphase {month_b}',
        'Status-Änderung',
        f'Wert {month_a}',
        f'Wert {month_b}',
        'Deal Name'
    ]

    # Reorder columns to put Deal Name first
    display_comparison = display_comparison[[
        'Deal Name',
        'HubSpot Link',
        f'Salesphase {month_a}',
        f'Salesphase {month_b}',
        'Status-Änderung',
        f'Wert {month_a}',
        f'Wert {month_b}'
    ]]

    # Apply styling
    styled_df = display_comparison.style.apply(
        lambda row: ['background-color: #d4edda'] * len(row) if '🟢' in str(row['Status-Änderung'])
        else ['background-color: #f8d7da'] * len(row) if '🔴' in str(row['Status-Änderung'])
        else ['background-color: #d1ecf1'] * len(row) if '🔵' in str(row['Status-Änderung'])
        else [''] * len(row),
        axis=1
    )

    # Display with column configuration for clickable links
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=600,
        hide_index=True,
        column_config={
            'HubSpot Link': st.column_config.LinkColumn(
                '🔗',
                help='Klicken um Deal in HubSpot zu öffnen',
                width='small'
            )
        }
    )

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
