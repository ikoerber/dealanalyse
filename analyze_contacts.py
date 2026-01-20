#!/usr/bin/env python3
"""
HubSpot Contact Lead Funnel Analysis

Reads contact snapshot CSV and generates:
1. Monthly KPI Overview (12 months): MQLs, SQLs, Conv.Rate, Velocity
2. SQL Details List (last month): Contacts that became SQL
3. Source Breakdown Matrix (12 months): Lead quality by marketing channel
"""
import sys
import logging
import os
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Tuple
import pandas as pd

from src.config import load_config, ConfigurationError
from src.cli import setup_logging, print_banner, CLIErrorHandler


def get_last_12_months() -> List[Tuple[str, datetime, datetime]]:
    """
    Get list of last 12 completed months

    Returns:
        List of tuples (month_name, start_date, end_date)
    """
    today = datetime.now(timezone.utc)
    # Go to first day of current month
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    months = []
    for i in range(12):
        # Calculate month (going backwards)
        month_end = current_month_start - timedelta(days=1)  # Last day of previous month
        month_start = month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # German month name
        month_name = month_start.strftime('%B %Y')
        # Map English to German month names
        month_map = {
            'January': 'Januar', 'February': 'Februar', 'March': 'März',
            'April': 'April', 'May': 'Mai', 'June': 'Juni',
            'July': 'Juli', 'August': 'August', 'September': 'September',
            'October': 'Oktober', 'November': 'November', 'December': 'Dezember'
        }
        for eng, ger in month_map.items():
            month_name = month_name.replace(eng, ger)

        months.append((month_name, month_start, month_end))
        current_month_start = month_start

    # Reverse to get chronological order
    return list(reversed(months))


def parse_date(date_str: str) -> datetime:
    """Parse ISO datetime string to datetime object"""
    if not date_str or date_str == '':
        return None

    try:
        # Try ISO format with timezone
        if 'T' in date_str:
            # Remove timezone info for simplicity
            date_str = date_str.split('+')[0].split('Z')[0].split('.')[0]
            return datetime.fromisoformat(date_str)
        else:
            # Try simple date format
            return datetime.strptime(date_str, '%Y-%m-%d')
    except Exception:
        return None


def calculate_monthly_kpis(contacts_df: pd.DataFrame, months: List[Tuple]) -> pd.DataFrame:
    """
    Calculate monthly KPIs: Volume, Conversion Rate, Velocity

    Args:
        contacts_df: DataFrame with contact data
        months: List of (month_name, start_date, end_date) tuples

    Returns:
        DataFrame with monthly KPIs
    """
    logger = logging.getLogger(__name__)

    kpis = []

    for month_name, month_start, month_end in months:
        # Count MQLs created in this month
        mqls = contacts_df[
            (contacts_df['mql_date'] >= month_start) &
            (contacts_df['mql_date'] <= month_end)
        ]
        mql_count = len(mqls)

        # Count SQLs created in this month
        sqls = contacts_df[
            (contacts_df['sql_date'] >= month_start) &
            (contacts_df['sql_date'] <= month_end)
        ]
        sql_count = len(sqls)

        # Calculate conversion rate (only for SQLs converted in same month as MQL created)
        # This is tricky - we need MQLs that converted to SQL in same month
        same_month_conversions = contacts_df[
            (contacts_df['mql_date'] >= month_start) &
            (contacts_df['mql_date'] <= month_end) &
            (contacts_df['sql_date'] >= month_start) &
            (contacts_df['sql_date'] <= month_end) &
            (contacts_df['sql_date'].notna())
        ]
        conversion_count = len(same_month_conversions)

        # Conversion rate: converted SQLs / total MQLs in month
        conv_rate = (conversion_count / mql_count * 100) if mql_count > 0 else 0.0

        # Calculate velocity (average days from MQL to SQL for SQLs in this month)
        sqls_with_both_dates = sqls[
            (sqls['sql_date'].notna()) &
            (sqls['mql_date'].notna())
        ].copy()

        if len(sqls_with_both_dates) > 0:
            # Calculate days difference
            sqls_with_both_dates['days_diff'] = (
                sqls_with_both_dates['sql_date'] - sqls_with_both_dates['mql_date']
            ).dt.days
            avg_velocity = sqls_with_both_dates['days_diff'].mean()
        else:
            avg_velocity = 0.0

        kpis.append({
            'Monat': month_name,
            'MQLs': mql_count,
            'SQLs': sql_count,
            'Conv.Rate (%)': round(conv_rate, 1),
            'Ø Tage (MQL→SQL)': round(avg_velocity, 1)
        })

        logger.info(f"{month_name}: {mql_count} MQLs, {sql_count} SQLs, {conv_rate:.1f}% conv, {avg_velocity:.1f} days velocity")

    return pd.DataFrame(kpis)


def get_sql_details_last_month(contacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get SQL details for last completed month

    Args:
        contacts_df: DataFrame with contact data

    Returns:
        DataFrame with SQL details (Date, Contact, Company, Source)
    """
    logger = logging.getLogger(__name__)

    # Get last completed month
    today = datetime.now(timezone.utc)
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = current_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    logger.info(f"Filtering SQLs for last completed month: {last_month_start.strftime('%B %Y')}")

    # Filter SQLs from last month
    last_month_sqls = contacts_df[
        (contacts_df['sql_date'] >= last_month_start) &
        (contacts_df['sql_date'] <= last_month_end) &
        (contacts_df['sql_date'].notna())
    ].copy()

    # Format for output
    sql_details = []
    for _, row in last_month_sqls.iterrows():
        sql_details.append({
            'SQL Datum': row['sql_date'].strftime('%d.%m.%Y'),
            'Kontakt': f"{row['firstname']} {row['lastname']}".strip(),
            'Firma': row['company_name'] if row['company_name'] else '–',
            'Quelle': row['source'] if row['source'] else '–'
        })

    # Create DataFrame with proper columns even if empty
    columns = ['SQL Datum', 'Kontakt', 'Firma', 'Quelle']
    if sql_details:
        sql_df = pd.DataFrame(sql_details)
        # Sort by date descending (newest first)
        sql_df = sql_df.sort_values('SQL Datum', ascending=False)
    else:
        # Empty DataFrame with correct columns
        sql_df = pd.DataFrame(columns=columns)

    logger.info(f"Found {len(sql_df)} SQLs in last completed month")

    return sql_df


def calculate_source_breakdown(contacts_df: pd.DataFrame, months: List[Tuple]) -> pd.DataFrame:
    """
    Calculate source breakdown matrix over 12 months

    Args:
        contacts_df: DataFrame with contact data
        months: List of (month_name, start_date, end_date) tuples

    Returns:
        DataFrame with source breakdown matrix
    """
    logger = logging.getLogger(__name__)

    # Group by source
    sources = contacts_df['source'].unique()
    logger.info(f"Found {len(sources)} unique sources")

    # Build matrix data
    matrix_data = []

    for source in sources:
        source_contacts = contacts_df[contacts_df['source'] == source]

        row = {'Quelle': source}

        total_mqls = 0
        total_sqls = 0

        # Calculate for each month
        for month_name, month_start, month_end in months:
            # MQLs from this source in this month
            mqls = source_contacts[
                (source_contacts['mql_date'] >= month_start) &
                (source_contacts['mql_date'] <= month_end)
            ]
            mql_count = len(mqls)
            total_mqls += mql_count

            # SQLs from this source in this month
            sqls = source_contacts[
                (source_contacts['sql_date'] >= month_start) &
                (source_contacts['sql_date'] <= month_end) &
                (source_contacts['sql_date'].notna())
            ]
            sql_count = len(sqls)
            total_sqls += sql_count

            # Format: "X/Y" (e.g., "10/2")
            # Shorten month name for column header (e.g., "Juli 2024" -> "Jul 24")
            month_short = month_name.split()[0][:3] + ' ' + month_name.split()[1][2:]
            row[month_short] = f"{mql_count}/{sql_count}" if mql_count > 0 or sql_count > 0 else "-"

        # Add totals and conversion rate
        row['Gesamt'] = f"{total_mqls}/{total_sqls}"
        conv_rate = (total_sqls / total_mqls * 100) if total_mqls > 0 else 0.0
        row['Conv.Rate (%)'] = round(conv_rate, 1)

        # Store total SQLs for sorting
        row['_total_sqls'] = total_sqls

        matrix_data.append(row)

    # Convert to DataFrame
    if matrix_data:
        matrix_df = pd.DataFrame(matrix_data)
        # Sort by total SQLs descending (most important sources first)
        matrix_df = matrix_df.sort_values('_total_sqls', ascending=False)
        # Drop sorting helper column
        matrix_df = matrix_df.drop(columns=['_total_sqls'])
    else:
        # Empty DataFrame with at least Quelle column
        matrix_df = pd.DataFrame(columns=['Quelle'])

    logger.info(f"Generated source breakdown matrix with {len(matrix_df)} sources")

    return matrix_df


def write_csv_reports(config, kpis_df: pd.DataFrame, sql_details_df: pd.DataFrame, source_matrix_df: pd.DataFrame) -> Tuple[str, str, str]:
    """
    Write analysis results to CSV files

    Args:
        config: Configuration object
        kpis_df: Monthly KPIs DataFrame
        sql_details_df: SQL details DataFrame
        source_matrix_df: Source breakdown matrix DataFrame

    Returns:
        Tuple of (kpis_path, sql_details_path, source_matrix_path)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d')
    reports_dir = os.path.join(config.output_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    # Write KPIs
    kpis_path = os.path.join(reports_dir, f'contacts_kpi_{timestamp}.csv')
    kpis_df.to_csv(kpis_path, index=False, encoding='utf-8-sig')

    # Write SQL details
    sql_details_path = os.path.join(reports_dir, f'sql_details_{timestamp}.csv')
    sql_details_df.to_csv(sql_details_path, index=False, encoding='utf-8-sig')

    # Write source matrix
    source_matrix_path = os.path.join(reports_dir, f'source_breakdown_{timestamp}.csv')
    source_matrix_df.to_csv(source_matrix_path, index=False, encoding='utf-8-sig')

    return kpis_path, sql_details_path, source_matrix_path


def print_summary(kpis_path: str, sql_details_path: str, source_matrix_path: str, log_file: str):
    """Print execution summary"""
    print()
    print("=" * 60)
    print("Contact Analysis Complete")
    print("=" * 60)
    print()
    print("Generated Reports:")
    print(f"  - KPI Overview:       {kpis_path}")
    print(f"  - SQL Details:        {sql_details_path}")
    print(f"  - Source Breakdown:   {source_matrix_path}")
    print()
    print(f"Check logs: {log_file}")
    print("=" * 60)


def main():
    """Main execution function"""
    print_banner("HubSpot Contact Lead Funnel Analysis")

    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()

        # Setup logging
        log_file = setup_logging(config, 'analyze_contacts')
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Starting Contact Lead Funnel Analysis")
        logger.info("=" * 60)
        logger.info(f"Configuration: {config}")

        # Find latest contact snapshot file
        print("Looking for contact snapshot file...")
        output_dir = config.output_dir
        contact_files = [f for f in os.listdir(output_dir) if f.startswith('contacts_snapshot_') and f.endswith('.csv')]

        if not contact_files:
            print()
            print(f"ERROR: No contact snapshot file found in {output_dir}")
            print()
            print("Please run fetch_contacts.py first to generate contact data.")
            return 1

        # Get latest file
        contact_files.sort(reverse=True)
        latest_file = contact_files[0]
        contacts_path = os.path.join(output_dir, latest_file)

        print(f"Using contact snapshot: {latest_file}")
        logger.info(f"Loading contacts from: {contacts_path}")

        # Load contacts
        print("Loading contact data...")
        contacts_df = pd.read_csv(contacts_path, encoding='utf-8-sig')
        logger.info(f"Loaded {len(contacts_df)} contacts")

        # Parse dates
        print("Parsing dates...")
        contacts_df['mql_date'] = pd.to_datetime(contacts_df['mql_date'], errors='coerce')
        contacts_df['sql_date'] = pd.to_datetime(contacts_df['sql_date'], errors='coerce')

        # Get last 12 months
        print("Calculating last 12 completed months...")
        months = get_last_12_months()
        logger.info(f"Analyzing {len(months)} months: {months[0][0]} to {months[-1][0]}")

        # Calculate monthly KPIs
        print()
        print("Calculating monthly KPIs...")
        kpis_df = calculate_monthly_kpis(contacts_df, months)

        # Get SQL details for last month
        print("Extracting SQL details for last completed month...")
        sql_details_df = get_sql_details_last_month(contacts_df)

        # Calculate source breakdown matrix
        print("Calculating source breakdown matrix...")
        source_matrix_df = calculate_source_breakdown(contacts_df, months)

        # Write reports
        print()
        print("Writing CSV reports...")
        kpis_path, sql_details_path, source_matrix_path = write_csv_reports(
            config, kpis_df, sql_details_df, source_matrix_df
        )

        # Print summary
        print_summary(kpis_path, sql_details_path, source_matrix_path, log_file)

        logger.info("Analysis complete")
        logger.info("=" * 60)

        return 0

    except ConfigurationError as e:
        return CLIErrorHandler.handle_configuration_error(e)

    except FileNotFoundError as e:
        print()
        print(f"File Error: {e}")
        print()
        print("Please ensure the contact snapshot file exists.")
        return 1

    except Exception as e:
        return CLIErrorHandler.handle_generic_error(e)


if __name__ == '__main__':
    sys.exit(main())
