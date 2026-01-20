"""
Analyzer for 2025 Deals Overview

Generates a comprehensive list of all deals created in 2025 with:
- Deal name, value, status
- Contact source (from primary contact)
- Rejection reason (for lost deals)
"""

import logging
import os
from datetime import datetime
from typing import List, Dict
from glob import glob
import pandas as pd

from src.config import Config

logger = logging.getLogger(__name__)


class Deals2025Analyzer:
    """Analyzes and generates report for all deals created in 2025"""

    def __init__(self, config: Config, stage_mapper=None, owners_map: Dict[str, str] = None):
        """
        Initialize 2025 deals analyzer

        Args:
            config: Configuration object
            stage_mapper: Optional stage mapper for human-readable stage names
            owners_map: Optional dictionary mapping owner IDs to names
        """
        self.config = config
        self.stage_mapper = stage_mapper
        self.owners_map = owners_map or {}

    def _get_deal_status(self, stage: str) -> str:
        """
        Determine deal status from stage

        Args:
            stage: Deal stage ID

        Returns:
            Status string: "Won", "Lost", "Kein Angebot", or "Active"
        """
        if not stage:
            return "Active"

        stage_lower = stage.lower()

        # Check if won
        if 'closedwon' in stage_lower or stage_lower == 'closedwon':
            return "Won"

        # Check custom "Kein Angebot" stage (from stage_mapping.json)
        if stage == '16932893':
            return "Kein Angebot"

        # Check if lost
        if 'closedlost' in stage_lower or stage_lower == 'closedlost':
            return "Lost"

        # All other stages are active
        return "Active"

    def _format_amount(self, amount_str: str) -> float:
        """
        Convert amount string to float

        Args:
            amount_str: Amount as string

        Returns:
            Amount as float (0.0 if invalid)
        """
        try:
            if not amount_str or amount_str == '':
                return 0.0
            return float(amount_str)
        except (ValueError, TypeError):
            return 0.0

    def _is_created_in_2025(self, create_date_str: str) -> bool:
        """
        Check if deal was created in 2025

        Args:
            create_date_str: Create date as ISO string

        Returns:
            True if created in 2025, False otherwise
        """
        if not create_date_str:
            return False

        try:
            # Parse ISO timestamp
            create_date = datetime.fromisoformat(create_date_str.replace('Z', '+00:00'))
            return create_date.year == 2025
        except (ValueError, AttributeError):
            return False

    def _get_owner_name(self, owner_id: str) -> str:
        """
        Get owner name from ID

        Args:
            owner_id: HubSpot owner ID

        Returns:
            Owner name or "Unbekannt" if not found
        """
        if not owner_id:
            return "Unbekannt"

        return self.owners_map.get(owner_id, "Unbekannt")

    def _get_stage_name(self, stage_id: str) -> str:
        """
        Get human-readable stage name

        Args:
            stage_id: HubSpot stage ID

        Returns:
            Stage name or stage_id if mapper not available
        """
        if not self.stage_mapper or not stage_id:
            return stage_id

        try:
            return self.stage_mapper.get_stage_name(stage_id)
        except (AttributeError, KeyError, Exception) as e:
            logger.debug(f"Could not map stage {stage_id}: {e}")
            return stage_id

    def generate_2025_deals_list(self) -> pd.DataFrame:
        """
        Generate list of all deals created in 2025

        Returns:
            DataFrame with columns:
            - deal_name
            - amount
            - status (Won/Lost/Active)
            - contact_source
            - rejection_reason
            - owner_name
            - create_date
            - close_date
            - deal_stage
        """
        logger.info("Generating 2025 deals list...")

        # Load deal snapshot data
        snapshot_pattern = os.path.join(self.config.output_dir, 'deals_snapshot_*.csv')
        snapshot_files = glob(snapshot_pattern)

        if not snapshot_files:
            logger.warning(f"No snapshot files found: {snapshot_pattern}")
            return pd.DataFrame()

        # Get the most recent snapshot file
        latest_snapshot = max(snapshot_files, key=os.path.getmtime)
        logger.info(f"Loading snapshot from: {latest_snapshot}")

        # Read CSV
        snapshot_df = pd.read_csv(latest_snapshot, encoding='utf-8-sig')

        if snapshot_df.empty:
            logger.warning("Snapshot data is empty")
            return pd.DataFrame()

        # Filter deals created in 2025
        logger.info(f"Total deals in snapshot: {len(snapshot_df)}")

        deals_2025 = []

        for _, row in snapshot_df.iterrows():
            if self._is_created_in_2025(row.get('create_date', '')):
                deal_id = row.get('deal_id', '')
                deal_name = row.get('deal_name', '')
                amount = self._format_amount(row.get('current_amount', '0'))
                stage = row.get('current_dealstage', '')
                status = self._get_deal_status(stage)
                contact_source = row.get('contact_source', '')
                rejection_reason = row.get('rejection_reason', '')
                owner_id = row.get('hubspot_owner_id', '')
                owner_name = self._get_owner_name(owner_id)
                create_date = row.get('create_date', '')
                close_date = row.get('current_closedate', '')
                stage_name = self._get_stage_name(stage)

                deals_2025.append({
                    'deal_id': deal_id,
                    'deal_name': deal_name,
                    'amount': amount,
                    'status': status,
                    'contact_source': contact_source if contact_source else '–',
                    'rejection_reason': rejection_reason if rejection_reason else '–',
                    'owner_name': owner_name,
                    'create_date': create_date,
                    'close_date': close_date if close_date else '–',
                    'deal_stage': stage_name
                })

        if not deals_2025:
            logger.warning("No deals found created in 2025")
            return pd.DataFrame()

        df = pd.DataFrame(deals_2025)

        # Sort by create_date descending (newest first)
        df = df.sort_values('create_date', ascending=False)

        logger.info(f"Found {len(df)} deals created in 2025")
        logger.info(f"  - Won: {len(df[df['status'] == 'Won'])}")
        logger.info(f"  - Lost: {len(df[df['status'] == 'Lost'])}")
        logger.info(f"  - Kein Angebot: {len(df[df['status'] == 'Kein Angebot'])}")
        logger.info(f"  - Active: {len(df[df['status'] == 'Active'])}")

        return df

    def export_to_csv(self, output_path: str) -> str:
        """
        Generate and export 2025 deals list to CSV

        Args:
            output_path: Path where CSV should be saved

        Returns:
            Path to the generated CSV file
        """
        logger.info(f"Exporting 2025 deals list to {output_path}")

        df = self.generate_2025_deals_list()

        if df.empty:
            logger.warning("No data to export")
            return ""

        # Export to CSV with UTF-8 BOM for Excel compatibility
        df.to_csv(
            output_path,
            index=False,
            encoding='utf-8-sig',
            na_rep='–'
        )

        logger.info(f"Successfully exported {len(df)} deals to {output_path}")

        return output_path
