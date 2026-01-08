"""CSV report writer"""
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from ..config import Config
from ..analysis.stage_mapper import StageMapper
from ..analysis.kpi_calculator import DealMovement, MonthlyKPI

logger = logging.getLogger(__name__)

# German month names
MONTH_NAMES = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
}


class ReportWriter:
    """Writes formatted CSV reports"""

    def __init__(self, config: Config, stage_mapper: StageMapper):
        """
        Initialize report writer

        Args:
            config: Configuration object
            stage_mapper: Stage mapping instance
        """
        self.config = config
        self.stage_mapper = stage_mapper
        self.reports_dir = os.path.join(config.output_dir, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)

    def _parse_amount(self, amount_str: Optional[str]) -> Optional[float]:
        """
        Parse amount string to float

        Args:
            amount_str: Amount string (e.g. "50000" or "50.000,00")

        Returns:
            Float value or None
        """
        if not amount_str:
            return None

        try:
            # Handle both formats: "50000" and "50.000,00"
            cleaned = amount_str.replace('.', '').replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse amount: {amount_str}")
            return None

    def _format_amount(self, amount_str: Optional[str]) -> str:
        """
        Format amount as Euro value with thousand separators

        Args:
            amount_str: Amount string (e.g. "50000")

        Returns:
            Formatted string like "50.000 €" or "-"
        """
        if not amount_str or amount_str == '-':
            return "-"

        amount = self._parse_amount(amount_str)
        if amount is None:
            return "-"

        # Format with thousand separator (German style: dot as thousand separator)
        return f"{amount:,.0f} €".replace(',', '.')

    def _format_amount_change(
        self,
        amount_start: Optional[float],
        amount_end: Optional[float]
    ) -> str:
        """
        Format amount change with absolute and percentage value

        Args:
            amount_start: Start amount
            amount_end: End amount

        Returns:
            Formatted string like "+5.000 € (+10,0%)" or "-"
        """
        if amount_start is None or amount_end is None:
            return "-"

        if amount_start == 0 and amount_end == 0:
            return "0 € (0,0%)"

        change = amount_end - amount_start

        # Calculate percentage
        if amount_start == 0:
            if amount_end > 0:
                percent_str = "+∞%"
            else:
                percent_str = "0,0%"
        else:
            percent = (change / amount_start) * 100
            percent_str = f"{percent:+.1f}%".replace('.', ',')

        # Format change
        sign = "+" if change > 0 else ""
        change_str = f"{sign}{change:,.0f} €".replace(',', '.')

        return f"{change_str} ({percent_str})"

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO 8601 date string

        Args:
            date_str: ISO date string

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        try:
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
            return None

    def _format_date(self, date_str: Optional[str]) -> str:
        """
        Format date for display (DD.MM.YYYY)

        Args:
            date_str: ISO date string

        Returns:
            Formatted date string or "-"
        """
        date = self._parse_date(date_str)
        if not date:
            return "-"

        return date.strftime('%d.%m.%Y')

    def _calculate_days_shifted(
        self,
        closedate_start: Optional[str],
        closedate_end: Optional[str]
    ) -> Optional[int]:
        """
        Calculate days shifted between two closedates

        Args:
            closedate_start: Start closedate
            closedate_end: End closedate

        Returns:
            Days shifted (positive = future, negative = earlier) or None
        """
        date_start = self._parse_date(closedate_start)
        date_end = self._parse_date(closedate_end)

        if not date_start or not date_end:
            return None

        delta = (date_end - date_start).days
        return delta

    def write_kpi_overview(self, kpis: List[MonthlyKPI]) -> str:
        """
        Write KPI overview CSV

        Args:
            kpis: List of MonthlyKPI objects

        Returns:
            Path to generated CSV file
        """
        # Convert to records
        records = []
        for kpi in kpis:
            records.append({
                'Monat': MONTH_NAMES[kpi.month],
                'Jahr': kpi.year,
                'Pipeline Neu (€)': self._format_amount(str(kpi.pipeline_new_eur) if kpi.pipeline_new_eur else None),
                'Revenue Won (€)': self._format_amount(str(kpi.revenue_won_eur) if kpi.revenue_won_eur else None),
                'Win Rate (%)': kpi.win_rate_percent,
                'Deals Erstellt': kpi.deals_created,
                'Deals Gewonnen': kpi.deals_won,
                'Deals Verloren': kpi.deals_lost
            })

        # Create DataFrame
        df = pd.DataFrame(records)

        # Generate filename
        timestamp = datetime.now().strftime('%Y-%m-%d')
        filename = f"kpi_overview_{timestamp}.csv"
        filepath = os.path.join(self.reports_dir, filename)

        # Write to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding='utf-8-sig'  # UTF-8 with BOM for Excel
        )

        logger.info(f"Written KPI overview to {filepath}")

        return filepath

    def write_deal_movements(self, movements_by_month: Dict[str, List[DealMovement]]) -> str:
        """
        Write deal movements detail CSV

        Args:
            movements_by_month: Dictionary mapping month_key to list of DealMovements

        Returns:
            Path to generated CSV file
        """
        # Convert to records
        records = []

        # Sort months chronologically
        sorted_months = sorted(movements_by_month.keys())

        for month_key in sorted_months:
            movements = movements_by_month[month_key]

            for movement in movements:
                # Get readable stage names
                state_start_name = ""
                if movement.state_start and movement.state_start.dealstage:
                    state_start_name = self.stage_mapper.get_stage_name(
                        movement.state_start.dealstage
                    )

                state_end_name = self.stage_mapper.get_stage_name(
                    movement.state_end.dealstage
                ) if movement.state_end.dealstage else ""

                # Format amount change
                amount_start_parsed = self._parse_amount(movement.amount_start)
                amount_end_parsed = self._parse_amount(movement.amount_end)
                amount_change_formatted = self._format_amount_change(
                    amount_start_parsed,
                    amount_end_parsed
                )

                # Format days shifted
                days_shifted_str = "-"
                if movement.closedate_days_shifted is not None:
                    days = movement.closedate_days_shifted
                    if days > 0:
                        days_shifted_str = f"+{days}"
                    elif days < 0:
                        days_shifted_str = f"{days}"
                    else:
                        days_shifted_str = "0"

                records.append({
                    'Monat': MONTH_NAMES[movement.month],
                    'Jahr': movement.year,
                    'Deal Name': movement.deal_name,
                    'Deal ID': movement.deal_id,
                    'Status (Monatsanfang)': state_start_name,
                    'Status (Monatsende)': state_end_name,
                    'Bewegungstyp': movement.movement_type,
                    # Amount changes
                    'Wert Monatsanfang (€)': self._format_amount(movement.amount_start),
                    'Wert Monatsende (€)': self._format_amount(movement.amount_end),
                    'Wertänderung (€)': amount_change_formatted,
                    # Closedate changes
                    'Zieldatum Anfang': self._format_date(movement.closedate_start),
                    'Zieldatum Ende': self._format_date(movement.closedate_end),
                    'Tage verschoben': days_shifted_str,
                    # Stage duration
                    'Tage in Phase': movement.days_in_current_stage,
                    # Comment
                    'Kommentar / Slippage': movement.comment
                })

        # Create DataFrame
        df = pd.DataFrame(records)

        # Generate filename
        timestamp = datetime.now().strftime('%Y-%m-%d')
        filename = f"deal_movements_detail_{timestamp}.csv"
        filepath = os.path.join(self.reports_dir, filename)

        # Write to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding='utf-8-sig'  # UTF-8 with BOM for Excel
        )

        logger.info(f"Written deal movements to {filepath}")

        return filepath
