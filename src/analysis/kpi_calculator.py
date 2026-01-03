"""KPI calculation for monthly reports"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

from .monthly_analyzer import MonthBoundary, DealStateAtTime
from ..data_fetcher import DealSnapshot, HistoryRecord

logger = logging.getLogger(__name__)


@dataclass
class DealMovement:
    """Represents a deal's movement within a month"""
    deal_id: str
    deal_name: str
    month: int
    year: int
    state_start: DealStateAtTime
    state_end: DealStateAtTime
    movement_type: str
    amount: str
    comment: str
    # Additional fields for enhanced reporting
    amount_start: Optional[str] = None
    amount_end: Optional[str] = None
    amount_change_eur: Optional[float] = None
    amount_change_percent: Optional[float] = None
    closedate_start: Optional[str] = None
    closedate_end: Optional[str] = None
    closedate_days_shifted: Optional[int] = None
    days_in_current_stage: int = 0


@dataclass
class MonthlyKPI:
    """Monthly aggregated KPIs"""
    month: int
    year: int
    pipeline_new_eur: int      # Sum of deals created this month
    revenue_won_eur: int       # Sum of deals won this month
    win_rate_percent: float    # (Won deals / Created deals) * 100
    deals_created: int         # Count of deals created
    deals_won: int             # Count of deals won
    deals_lost: int            # Count of deals lost


class KPICalculator:
    """Calculates monthly KPIs from deal movements"""

    def __init__(self, snapshots: List[DealSnapshot]):
        """
        Initialize KPI calculator

        Args:
            snapshots: List of deal snapshots
        """
        self.snapshots = {s.deal_id: s for s in snapshots}

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ISO 8601 timestamp"""
        if not timestamp_str:
            return None

        try:
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'

            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return None

    def get_deals_created_in_month(self, month_boundary: MonthBoundary) -> List[DealSnapshot]:
        """
        Find all deals created within month boundary

        Args:
            month_boundary: Month boundary

        Returns:
            List of DealSnapshot objects created in this month
        """
        created_deals = []

        for snapshot in self.snapshots.values():
            create_time = self._parse_timestamp(snapshot.create_date)
            if not create_time:
                continue

            # Check if created within month boundary
            if month_boundary.start_datetime <= create_time <= month_boundary.end_datetime:
                created_deals.append(snapshot)

        return created_deals

    def calculate_monthly_kpis(
        self,
        month_boundary: MonthBoundary,
        movements: List[DealMovement]
    ) -> MonthlyKPI:
        """
        Calculate KPIs for a specific month

        Args:
            month_boundary: Month boundary
            movements: List of deal movements for this month

        Returns:
            MonthlyKPI object
        """
        # 1. Pipeline New - deals created this month
        created_deals = self.get_deals_created_in_month(month_boundary)
        pipeline_new_eur = 0

        for deal in created_deals:
            if deal.current_amount and deal.current_amount.replace('.', '').replace(',', '').isdigit():
                try:
                    amount = float(deal.current_amount.replace(',', '.'))
                    pipeline_new_eur += int(amount)
                except (ValueError, AttributeError):
                    pass

        deals_created_count = len(created_deals)

        # 2. Revenue Won - deals won this month
        won_movements = [m for m in movements if m.movement_type == "WON"]
        revenue_won_eur = 0

        for movement in won_movements:
            if movement.amount and movement.amount.replace('.', '').replace(',', '').isdigit():
                try:
                    amount = float(movement.amount.replace(',', '.'))
                    revenue_won_eur += int(amount)
                except (ValueError, AttributeError):
                    pass

        deals_won_count = len(won_movements)

        # 3. Deals Lost
        lost_movements = [m for m in movements if m.movement_type == "LOST"]
        deals_lost_count = len(lost_movements)

        # 4. Win Rate calculation
        # Prefer: (Won / Created) * 100
        # Fallback: (Won / (Won + Lost)) * 100
        if deals_created_count > 0:
            win_rate = (deals_won_count / deals_created_count) * 100
        elif (deals_won_count + deals_lost_count) > 0:
            win_rate = (deals_won_count / (deals_won_count + deals_lost_count)) * 100
        else:
            win_rate = 0.0

        return MonthlyKPI(
            month=month_boundary.month,
            year=month_boundary.year,
            pipeline_new_eur=pipeline_new_eur,
            revenue_won_eur=revenue_won_eur,
            win_rate_percent=round(win_rate, 1),
            deals_created=deals_created_count,
            deals_won=deals_won_count,
            deals_lost=deals_lost_count
        )
