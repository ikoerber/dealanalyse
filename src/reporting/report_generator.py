"""Main orchestrator for report generation"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from ..config import Config
from ..analysis.csv_reader import load_deal_data
from ..analysis.stage_mapper import StageMapper
from ..analysis.monthly_analyzer import MonthlyAnalyzer
from ..analysis.movement_categorizer import MovementCategorizer
from ..analysis.kpi_calculator import KPICalculator, DealMovement, MonthlyKPI
from .report_writer import ReportWriter

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Orchestrates the full analysis and report generation process"""

    def __init__(self, config: Config, stage_mapper: StageMapper):
        """
        Initialize report generator

        Args:
            config: Configuration object
            stage_mapper: Stage mapping instance
        """
        self.config = config
        self.stage_mapper = stage_mapper

    def _safe_parse_amount(self, amount_str: str) -> Optional[float]:
        """
        Safely parse amount string to float

        Args:
            amount_str: Amount string

        Returns:
            Float value or None if parsing fails
        """
        try:
            return float(amount_str.replace(',', '.'))
        except (ValueError, AttributeError):
            return None

    def generate_reports(self, start_date: datetime) -> Tuple[str, str]:
        """
        Main entry point for report generation

        Args:
            start_date: Start date for analysis

        Returns:
            Tuple of (kpi_report_path, movements_report_path)
        """
        logger.info("=" * 60)
        logger.info("Starting report generation")
        logger.info("=" * 60)

        # Step 1: Load CSV data
        logger.info("Loading CSV data...")
        snapshots, history = load_deal_data(self.config.output_dir)

        # Step 2: Initialize analyzers
        logger.info("Initializing analyzers...")
        monthly_analyzer = MonthlyAnalyzer(snapshots, history, self.stage_mapper)
        movement_categorizer = MovementCategorizer(self.stage_mapper, history)
        kpi_calculator = KPICalculator(snapshots)

        # Step 3: Generate month boundaries
        logger.info(f"Generating month boundaries from {start_date.strftime('%Y-%m-%d')}...")
        month_boundaries = monthly_analyzer.generate_month_boundaries(start_date)

        # Step 4: Analyze each month
        all_movements: Dict[str, List[DealMovement]] = {}
        all_kpis: List[MonthlyKPI] = []

        for boundary in month_boundaries:
            month_key = f"{boundary.year}-{boundary.month:02d}"
            logger.info(f"Analyzing month: {month_key}")

            # Get state pairs for this month
            state_pairs = monthly_analyzer.analyze_month(boundary)

            # Categorize movements
            movements = []
            for deal_id, state_start, state_end in state_pairs:
                if state_end is None:
                    continue

                # Categorize movement
                movement_type, comment = movement_categorizer.categorize_movement(
                    state_start,
                    state_end
                )

                # Calculate additional metrics for enhanced reporting
                # 1. Amount changes
                amount_start_val = None
                amount_end_val = None
                if state_start and state_start.amount:
                    amount_start_val = self._safe_parse_amount(state_start.amount)
                if state_end.amount:
                    amount_end_val = self._safe_parse_amount(state_end.amount)

                amount_change_eur = None
                amount_change_percent = None
                if amount_start_val is not None and amount_end_val is not None:
                    amount_change_eur = amount_end_val - amount_start_val
                    if amount_start_val > 0:
                        amount_change_percent = (amount_change_eur / amount_start_val) * 100

                # 2. Closedate shifts
                closedate_start = state_start.closedate if state_start else None
                closedate_end = state_end.closedate
                closedate_days_shifted = None
                if closedate_start and closedate_end:
                    try:
                        date_start = datetime.fromisoformat(closedate_start.replace('Z', '+00:00'))
                        date_end = datetime.fromisoformat(closedate_end.replace('Z', '+00:00'))
                        closedate_days_shifted = (date_end - date_start).days
                    except (ValueError, AttributeError):
                        pass

                # 3. Days in current stage
                days_in_stage = movement_categorizer.calculate_stalled_days(state_end)

                # Create movement record
                movement = DealMovement(
                    deal_id=deal_id,
                    deal_name=state_end.deal_name,
                    month=boundary.month,
                    year=boundary.year,
                    state_start=state_start,
                    state_end=state_end,
                    movement_type=movement_type,
                    amount=state_end.amount or '',
                    comment=comment,
                    # Additional fields
                    amount_start=state_start.amount if state_start else None,
                    amount_end=state_end.amount,
                    amount_change_eur=amount_change_eur,
                    amount_change_percent=amount_change_percent,
                    closedate_start=closedate_start,
                    closedate_end=closedate_end,
                    closedate_days_shifted=closedate_days_shifted,
                    days_in_current_stage=days_in_stage
                )
                movements.append(movement)

            all_movements[month_key] = movements

            # Calculate KPIs for this month
            kpi = kpi_calculator.calculate_monthly_kpis(boundary, movements)
            all_kpis.append(kpi)

            logger.info(
                f"  {month_key}: {len(movements)} movements, "
                f"{kpi.deals_won} won, {kpi.deals_lost} lost"
            )

        # Step 5: Write reports
        logger.info("Writing reports...")
        writer = ReportWriter(self.config, self.stage_mapper)

        kpi_path = writer.write_kpi_overview(all_kpis)
        movements_path = writer.write_deal_movements(all_movements)

        logger.info("=" * 60)
        logger.info("Report generation complete")
        logger.info("=" * 60)

        return kpi_path, movements_path
