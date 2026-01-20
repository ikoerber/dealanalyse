"""CSV export functionality"""
import os
import logging
from datetime import datetime
from typing import List
from dataclasses import asdict

import pandas as pd

from .config import Config
from .data_fetcher import DealSnapshot, HistoryRecord

logger = logging.getLogger(__name__)


class CSVWriter:
    """Handles writing deal data to CSV files"""

    def __init__(self, config: Config):
        """
        Initialize CSV writer

        Args:
            config: Configuration object
        """
        self.config = config
        self.output_dir = config.output_dir

    def _generate_filename(self, prefix: str) -> str:
        """
        Generate timestamped filename

        Args:
            prefix: Filename prefix (e.g., 'deals_snapshot')

        Returns:
            Filename with date (e.g., 'deals_snapshot_2025-01-02.csv')
        """
        date_str = datetime.now().strftime('%Y-%m-%d')
        return f"{prefix}_{date_str}.csv"

    def write_snapshot_csv(self, snapshots: List[DealSnapshot]) -> str:
        """
        Write deal snapshots to CSV

        Args:
            snapshots: List of DealSnapshot objects

        Returns:
            Path to created CSV file
        """
        if not snapshots:
            logger.warning("No snapshots to write")
            return ""

        # Convert to list of dictionaries
        data = [asdict(s) for s in snapshots]

        # Create DataFrame
        df = pd.DataFrame(data)

        # Reorder columns for better readability
        column_order = [
            'deal_id',
            'deal_name',
            'current_amount',
            'current_dealstage',
            'current_closedate',
            'create_date',
            'has_history',
            'fetch_timestamp',
            'hs_forecast_amount',
            'hs_forecast_probability',
            'hubspot_owner_id',
            'notes_last_contacted',
            'notes_last_updated',
            'num_notes',
            'hs_lastmodifieddate',
            'hs_num_associated_queue_tasks',
            'num_associated_contacts',
            'rejection_reason',
            'contact_source',
            'primary_contact_id'
        ]

        # Ensure all columns exist (in case some are missing)
        for col in column_order:
            if col not in df.columns:
                df[col] = ''

        df = df[column_order]

        # Generate filename and path
        filename = self._generate_filename('deals_snapshot')
        filepath = os.path.join(self.output_dir, filename)

        # Write to CSV with UTF-8 BOM for Excel compatibility
        df.to_csv(
            filepath,
            index=False,
            encoding='utf-8-sig',  # BOM for proper Excel display of German characters
            na_rep=''  # Empty string for null values
        )

        logger.info(f"Written {len(snapshots)} snapshots to {filepath}")

        return filepath

    def write_history_csv(self, history_records: List[HistoryRecord]) -> str:
        """
        Write history records to CSV

        Args:
            history_records: List of HistoryRecord objects

        Returns:
            Path to created CSV file
        """
        if not history_records:
            logger.warning("No history records to write")
            return ""

        # Convert to list of dictionaries
        data = [asdict(r) for r in history_records]

        # Create DataFrame
        df = pd.DataFrame(data)

        # Reorder columns for better readability
        column_order = [
            'deal_id',
            'deal_name',
            'property_name',
            'property_value',
            'change_timestamp',
            'source_type',
            'change_order'
        ]

        # Ensure all columns exist
        for col in column_order:
            if col not in df.columns:
                df[col] = ''

        df = df[column_order]

        # Sort by deal_id, property_name, and change_order for easy analysis
        df = df.sort_values(
            by=['deal_id', 'property_name', 'change_order'],
            ascending=True
        )

        # Generate filename and path
        filename = self._generate_filename('deal_history')
        filepath = os.path.join(self.output_dir, filename)

        # Write to CSV with UTF-8 BOM for Excel compatibility
        df.to_csv(
            filepath,
            index=False,
            encoding='utf-8-sig',  # BOM for proper Excel display
            na_rep=''  # Empty string for null values
        )

        logger.info(f"Written {len(history_records)} history records to {filepath}")

        return filepath

    def write_data_quality_report(self, snapshots: List[DealSnapshot]) -> str:
        """
        Write data quality report highlighting potential issues

        Args:
            snapshots: List of DealSnapshot objects

        Returns:
            Path to created report file
        """
        issues = []

        for snapshot in snapshots:
            # Check for missing deal name
            if not snapshot.deal_name or snapshot.deal_name.strip() == '':
                issues.append({
                    'deal_id': snapshot.deal_id,
                    'issue_type': 'Missing Deal Name',
                    'details': 'Deal name is empty'
                })

            # Check for missing amount
            if not snapshot.current_amount or snapshot.current_amount.strip() == '':
                issues.append({
                    'deal_id': snapshot.deal_id,
                    'issue_type': 'Missing Amount',
                    'details': 'Deal amount is empty'
                })

            # Check for missing history
            if not snapshot.has_history:
                issues.append({
                    'deal_id': snapshot.deal_id,
                    'issue_type': 'No History',
                    'details': 'No history data available for this deal'
                })

        if not issues:
            logger.info("No data quality issues found")
            return ""

        # Create DataFrame
        df = pd.DataFrame(issues)

        # Generate filename and path
        filename = self._generate_filename('data_quality_issues')
        filepath = os.path.join(self.output_dir, filename)

        # Write to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding='utf-8-sig'
        )

        logger.info(f"Written {len(issues)} data quality issues to {filepath}")

        return filepath
