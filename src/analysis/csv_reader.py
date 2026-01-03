"""CSV reader for loading snapshot and history data"""
import os
import logging
from typing import Dict, List, Tuple
from glob import glob

import pandas as pd

from ..data_fetcher import DealSnapshot, HistoryRecord

logger = logging.getLogger(__name__)


def get_latest_csv_files(output_dir: str) -> Tuple[str, str]:
    """
    Find the most recent snapshot and history CSV files

    Args:
        output_dir: Directory containing CSV files

    Returns:
        Tuple of (snapshot_path, history_path)

    Raises:
        FileNotFoundError: If CSV files not found
    """
    # Find all snapshot files
    snapshot_pattern = os.path.join(output_dir, 'deals_snapshot_*.csv')
    snapshot_files = glob(snapshot_pattern)

    if not snapshot_files:
        raise FileNotFoundError(
            f"No snapshot CSV files found in {output_dir}. "
            f"Please run fetch_deals.py first."
        )

    # Find all history files
    history_pattern = os.path.join(output_dir, 'deal_history_*.csv')
    history_files = glob(history_pattern)

    if not history_files:
        raise FileNotFoundError(
            f"No history CSV files found in {output_dir}. "
            f"Please run fetch_deals.py first."
        )

    # Get the most recent files (by modification time)
    snapshot_path = max(snapshot_files, key=os.path.getmtime)
    history_path = max(history_files, key=os.path.getmtime)

    logger.info(f"Found snapshot file: {snapshot_path}")
    logger.info(f"Found history file: {history_path}")

    return snapshot_path, history_path


def read_snapshot_csv(filepath: str) -> List[DealSnapshot]:
    """
    Read snapshot CSV into list of DealSnapshot objects

    Args:
        filepath: Path to snapshot CSV file

    Returns:
        List of DealSnapshot objects
    """
    logger.info(f"Reading snapshot CSV from {filepath}")

    # Read CSV
    df = pd.read_csv(filepath, encoding='utf-8-sig')

    # Convert to DealSnapshot objects
    snapshots = []
    for _, row in df.iterrows():
        snapshot = DealSnapshot(
            deal_id=str(row['deal_id']),
            deal_name=str(row['deal_name']),
            current_amount=str(row['current_amount']) if pd.notna(row['current_amount']) else '',
            current_dealstage=str(row['current_dealstage']) if pd.notna(row['current_dealstage']) else '',
            current_closedate=str(row['current_closedate']) if pd.notna(row['current_closedate']) else '',
            create_date=str(row['create_date']) if pd.notna(row['create_date']) else '',
            has_history=bool(row['has_history']),
            fetch_timestamp=str(row['fetch_timestamp'])
        )
        snapshots.append(snapshot)

    logger.info(f"Loaded {len(snapshots)} deal snapshots")

    return snapshots


def read_history_csv(filepath: str) -> Dict[str, List[HistoryRecord]]:
    """
    Read history CSV and group by deal_id

    Args:
        filepath: Path to history CSV file

    Returns:
        Dictionary mapping deal_id to list of HistoryRecords, sorted by change_order
    """
    logger.info(f"Reading history CSV from {filepath}")

    # Read CSV
    df = pd.read_csv(filepath, encoding='utf-8-sig')

    # Group by deal_id
    history_by_deal = {}

    for _, row in df.iterrows():
        deal_id = str(row['deal_id'])

        record = HistoryRecord(
            deal_id=deal_id,
            deal_name=str(row['deal_name']),
            property_name=str(row['property_name']),
            property_value=str(row['property_value']) if pd.notna(row['property_value']) else '',
            change_timestamp=str(row['change_timestamp']),
            source_type=str(row['source_type']) if pd.notna(row['source_type']) else '',
            change_order=int(row['change_order'])
        )

        if deal_id not in history_by_deal:
            history_by_deal[deal_id] = []

        history_by_deal[deal_id].append(record)

    # Sort each deal's history by property_name and change_order
    for deal_id in history_by_deal:
        history_by_deal[deal_id].sort(
            key=lambda x: (x.property_name, x.change_order)
        )

    logger.info(
        f"Loaded history for {len(history_by_deal)} deals, "
        f"{len(df)} total records"
    )

    return history_by_deal


def load_deal_data(output_dir: str) -> Tuple[List[DealSnapshot], Dict[str, List[HistoryRecord]]]:
    """
    Convenience function to load both snapshot and history data

    Args:
        output_dir: Directory containing CSV files

    Returns:
        Tuple of (snapshots, history_by_deal)
    """
    snapshot_path, history_path = get_latest_csv_files(output_dir)

    snapshots = read_snapshot_csv(snapshot_path)
    history = read_history_csv(history_path)

    return snapshots, history
