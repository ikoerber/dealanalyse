"""Deal movement categorization logic"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .monthly_analyzer import DealStateAtTime
from .stage_mapper import StageMapper
from ..data_fetcher import HistoryRecord

logger = logging.getLogger(__name__)


class MovementCategorizer:
    """Categorizes deal movements into WON, LOST, ADVANCED, STALLED, PUSHED, REGRESSED"""

    def __init__(self, stage_mapper: StageMapper, history: Dict[str, List[HistoryRecord]]):
        """
        Initialize movement categorizer

        Args:
            stage_mapper: Stage mapping instance
            history: Dictionary mapping deal_id to history records
        """
        self.stage_mapper = stage_mapper
        self.history = history

    def categorize_movement(
        self,
        state_start: Optional[DealStateAtTime],
        state_end: DealStateAtTime
    ) -> Tuple[str, str]:
        """
        Categorize deal movement

        Args:
            state_start: Deal state at start of period (None if created during period)
            state_end: Deal state at end of period

        Returns:
            Tuple of (movement_type, comment)

        Priority order:
        1. WON - Ended in won stage
        2. LOST - Ended in lost stage
        3. PUSHED - closedate moved to future
        4. ADVANCED - Moved forward in pipeline
        5. REGRESSED - Moved backward in pipeline
        6. STALLED - No change in stage
        """
        # Handle deal created during period
        if state_start is None or state_start.dealstage is None:
            # Deal was created during this period
            if self.stage_mapper.is_won_stage(state_end.dealstage):
                return ("WON", f"Erstellt und gewonnen: {self.stage_mapper.get_stage_name(state_end.dealstage)}")
            elif self.stage_mapper.is_lost_stage(state_end.dealstage):
                return ("LOST", f"Erstellt und verloren: {self.stage_mapper.get_stage_name(state_end.dealstage)}")
            else:
                return ("ADVANCED", f"Neu erstellt in Phase: {self.stage_mapper.get_stage_name(state_end.dealstage)}")

        stage_start = state_start.dealstage
        stage_end = state_end.dealstage

        # Priority 1: Check for WON
        if self.stage_mapper.is_won_stage(stage_end):
            if self.stage_mapper.is_won_stage(stage_start):
                return ("WON", "Bereits gewonnen zu Monatsbeginn")
            else:
                start_name = self.stage_mapper.get_stage_name(stage_start)
                end_name = self.stage_mapper.get_stage_name(stage_end)
                return ("WON", f"{start_name} → {end_name}")

        # Priority 2: Check for LOST
        if self.stage_mapper.is_lost_stage(stage_end):
            if self.stage_mapper.is_lost_stage(stage_start):
                return ("LOST", "Bereits verloren zu Monatsbeginn")
            else:
                start_name = self.stage_mapper.get_stage_name(stage_start)
                end_name = self.stage_mapper.get_stage_name(stage_end)
                return ("LOST", f"{start_name} → {end_name}")

        # Priority 3: Check for PUSHED (closedate change)
        closedate_pushed = self.is_closedate_pushed(
            state_start.closedate,
            state_end.closedate
        )

        # Priority 4: Check stage movement
        stage_comparison = self.stage_mapper.compare_stages(stage_start, stage_end)

        if stage_comparison == 0:  # STALLED
            days_stalled = self.calculate_stalled_days(state_end)
            stage_name = self.stage_mapper.get_stage_name(stage_end)

            if closedate_pushed:
                return ("PUSHED", f"Abschlussdatum verschoben, {days_stalled} Tage in Phase '{stage_name}'")
            else:
                return ("STALLED", f"Keine Bewegung, {days_stalled} Tage in Phase '{stage_name}'")

        elif stage_comparison == -1:  # ADVANCED
            start_name = self.stage_mapper.get_stage_name(stage_start)
            end_name = self.stage_mapper.get_stage_name(stage_end)

            if closedate_pushed:
                return ("ADVANCED", f"{start_name} → {end_name}, aber Abschlussdatum verschoben")
            else:
                return ("ADVANCED", f"{start_name} → {end_name}")

        else:  # REGRESSED
            start_name = self.stage_mapper.get_stage_name(stage_start)
            end_name = self.stage_mapper.get_stage_name(stage_end)
            return ("REGRESSED", f"Rückschritt: {start_name} → {end_name}")

    def is_closedate_pushed(
        self,
        closedate_start: Optional[str],
        closedate_end: Optional[str]
    ) -> bool:
        """
        Detect if closedate was pushed into the future

        Args:
            closedate_start: closedate at start of period
            closedate_end: closedate at end of period

        Returns:
            True if closedate was pushed to a later date
        """
        if not closedate_start or not closedate_end:
            return False

        try:
            # Parse dates
            date_start = self._parse_date(closedate_start)
            date_end = self._parse_date(closedate_end)

            if not date_start or not date_end:
                return False

            # Check if end date is later than start date
            return date_end > date_start

        except Exception as e:
            logger.warning(f"Error comparing closedates: {e}")
            return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse ISO 8601 date string"""
        if not date_str:
            return None

        try:
            # Handle both with and without 'Z' suffix
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'

            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
            return None

    def calculate_stalled_days(self, state_end: DealStateAtTime) -> int:
        """
        Calculate how many days deal has been in current stage

        Args:
            state_end: Deal state at end of period

        Returns:
            Number of days in current stage
        """
        deal_history = self.history.get(state_end.deal_id, [])

        # Find dealstage changes
        stage_changes = [
            h for h in deal_history
            if h.property_name == 'dealstage'
        ]

        if not stage_changes:
            # No stage history, use current timestamp
            return 0

        # Sort by timestamp
        stage_changes.sort(
            key=lambda x: (self._parse_date(x.change_timestamp) or datetime.min, x.change_order)
        )

        # Find most recent change to current stage
        current_stage = state_end.dealstage
        last_change_time = None

        for change in reversed(stage_changes):
            if change.property_value == current_stage:
                last_change_time = self._parse_date(change.change_timestamp)
                break

        if not last_change_time:
            # No change to current stage found, assume from beginning
            return 0

        # Calculate days
        days = (state_end.timestamp - last_change_time).days

        return max(0, days)  # Ensure non-negative
