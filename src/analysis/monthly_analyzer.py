"""Monthly deal analysis - core algorithm for determining deal state at specific times"""
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from calendar import monthrange

from ..data_fetcher import DealSnapshot, HistoryRecord
from .stage_mapper import StageMapper

logger = logging.getLogger(__name__)


@dataclass
class MonthBoundary:
    """Represents a calendar month boundary"""
    year: int
    month: int
    start_datetime: datetime  # First day 00:00:00
    end_datetime: datetime    # Last day 23:59:59


@dataclass
class DealStateAtTime:
    """State of a deal at a specific point in time"""
    deal_id: str
    deal_name: str
    dealstage: Optional[str]
    amount: Optional[str]
    closedate: Optional[str]
    timestamp: datetime


class MonthlyAnalyzer:
    """Analyzes deal movements on a monthly basis"""

    def __init__(
        self,
        snapshots: List[DealSnapshot],
        history: Dict[str, List[HistoryRecord]],
        stage_mapper: StageMapper
    ):
        """
        Initialize monthly analyzer

        Args:
            snapshots: List of deal snapshots
            history: Dictionary mapping deal_id to list of history records
            stage_mapper: Stage mapping instance
        """
        self.snapshots = {s.deal_id: s for s in snapshots}
        self.history = history
        self.stage_mapper = stage_mapper

    def generate_month_boundaries(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> List[MonthBoundary]:
        """
        Generate all month boundaries from start_date to end_date

        Args:
            start_date: Start date
            end_date: End date (defaults to current date)

        Returns:
            List of MonthBoundary objects
        """
        if end_date is None:
            end_date = datetime.now()

        boundaries = []

        current_year = start_date.year
        current_month = start_date.month

        while True:
            # Create month boundary
            boundary = self._create_month_boundary(current_year, current_month)
            boundaries.append(boundary)

            # Check if we've reached the end
            if current_year > end_date.year or \
               (current_year == end_date.year and current_month >= end_date.month):
                break

            # Move to next month
            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        logger.info(f"Generated {len(boundaries)} month boundaries")

        return boundaries

    def _create_month_boundary(self, year: int, month: int) -> MonthBoundary:
        """
        Create month boundary with precise timestamps

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            MonthBoundary object
        """
        # Start of month: 00:00:00.000000 UTC
        start_datetime = datetime(year, month, 1, 0, 0, 0, 0, tzinfo=timezone.utc)

        # End of month: last day at 23:59:59.999999 UTC
        last_day = monthrange(year, month)[1]
        end_datetime = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)

        return MonthBoundary(
            year=year,
            month=month,
            start_datetime=start_datetime,
            end_datetime=end_datetime
        )

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse ISO 8601 timestamp string to datetime

        Args:
            timestamp_str: ISO 8601 timestamp string

        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None

        try:
            # Handle both with and without 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'

            # Parse ISO format
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return None

    def get_deal_state_at_time(
        self,
        deal_id: str,
        target_time: datetime
    ) -> Optional[DealStateAtTime]:
        """
        CORE ALGORITHM: Determine deal state at specific timestamp

        Args:
            deal_id: Deal ID
            target_time: Target timestamp

        Returns:
            DealStateAtTime object or None if deal didn't exist at target_time
        """
        # Get deal snapshot for basic info
        snapshot = self.snapshots.get(deal_id)
        if not snapshot:
            logger.warning(f"Deal {deal_id} not found in snapshots")
            return None

        # Check if deal existed at target_time
        create_time = self._parse_timestamp(snapshot.create_date)
        if not create_time:
            logger.warning(f"Deal {deal_id} has no valid create_date")
            return None

        if create_time > target_time:
            # Deal didn't exist yet
            return None

        # Get history for this deal
        deal_history = self.history.get(deal_id, [])

        # Initialize state variables
        dealstage = None
        amount = None
        closedate = None

        # For each property, find value at target_time
        for property_name in ['dealstage', 'amount', 'closedate']:
            # Filter history for this property
            property_changes = [
                h for h in deal_history
                if h.property_name == property_name
            ]

            # Sort by timestamp and change_order
            property_changes.sort(
                key=lambda x: (self._parse_timestamp(x.change_timestamp) or datetime.min, x.change_order)
            )

            # Find last change before or at target_time
            value_at_time = None
            for change in property_changes:
                change_time = self._parse_timestamp(change.change_timestamp)
                if not change_time:
                    continue

                if change_time <= target_time:
                    value_at_time = change.property_value
                else:
                    # Changes are sorted, so we can stop
                    break

            # Assign to appropriate field
            if property_name == 'dealstage':
                dealstage = value_at_time
            elif property_name == 'amount':
                amount = value_at_time
            elif property_name == 'closedate':
                closedate = value_at_time

        return DealStateAtTime(
            deal_id=deal_id,
            deal_name=snapshot.deal_name,
            dealstage=dealstage,
            amount=amount,
            closedate=closedate,
            timestamp=target_time
        )

    def get_deals_active_in_month(self, month_boundary: MonthBoundary) -> List[str]:
        """
        Get list of deal IDs that were active or relevant during the month

        A deal is relevant if:
        - It existed at start of month, OR
        - It was created during the month, OR
        - It was closed during the month

        Args:
            month_boundary: Month boundary

        Returns:
            List of deal IDs
        """
        relevant_deals = set()

        for deal_id, snapshot in self.snapshots.items():
            create_time = self._parse_timestamp(snapshot.create_date)
            if not create_time:
                continue

            # Deal created before or during this month
            if create_time <= month_boundary.end_datetime:
                relevant_deals.add(deal_id)

        return list(relevant_deals)

    def analyze_month(
        self,
        month_boundary: MonthBoundary
    ) -> List[Tuple[str, Optional[DealStateAtTime], Optional[DealStateAtTime]]]:
        """
        Analyze all deals for a specific month

        Args:
            month_boundary: Month boundary to analyze

        Returns:
            List of (deal_id, state_start, state_end) tuples
        """
        relevant_deals = self.get_deals_active_in_month(month_boundary)

        logger.info(
            f"Analyzing {month_boundary.year}-{month_boundary.month:02d}: "
            f"{len(relevant_deals)} relevant deals"
        )

        results = []

        for deal_id in relevant_deals:
            # Get state at start of month
            state_start = self.get_deal_state_at_time(
                deal_id,
                month_boundary.start_datetime
            )

            # Get state at end of month
            state_end = self.get_deal_state_at_time(
                deal_id,
                month_boundary.end_datetime
            )

            # Only include if deal existed at end of month OR was created during month
            if state_end is not None:
                # Skip if deal has no change in this month (both states exist and are identical)
                if state_start is not None and state_end is not None:
                    # Check if there was any change
                    has_change = (
                        state_start.dealstage != state_end.dealstage or
                        state_start.amount != state_end.amount or
                        state_start.closedate != state_end.closedate
                    )
                    if has_change or state_start.dealstage is None:
                        results.append((deal_id, state_start, state_end))
                else:
                    # Deal was created during this month (state_start is None)
                    results.append((deal_id, state_start, state_end))

        return results
