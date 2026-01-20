"""
Generic Base Analyzer for HubSpot Objects

Provides abstract base class for analyzing different object types and generating reports.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd

from ..config import Config
from .object_registry import ObjectTypeConfig

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """
    Abstract base class for HubSpot object analyzers

    Analyzers transform raw object snapshots into analytical insights
    (KPIs, trends, breakdowns, etc.)
    """

    def __init__(
        self,
        config: Config,
        object_type_config: ObjectTypeConfig,
        **kwargs
    ):
        """
        Initialize base analyzer

        Args:
            config: Application configuration
            object_type_config: Object type configuration from ObjectRegistry
            **kwargs: Additional analyzer-specific arguments
        """
        self.config = config
        self.object_type_config = object_type_config
        self.object_type = object_type_config.object_type_id

        logger.info(
            f"Initialized {self.__class__.__name__} for {object_type_config.display_name}"
        )

    @abstractmethod
    def analyze(self, snapshots: List[Any]) -> Dict[str, pd.DataFrame]:
        """
        Analyze snapshots and generate insights

        This is the main entry point for analysis.

        Args:
            snapshots: List of object snapshots (type depends on object type)

        Returns:
            Dictionary mapping insight names to DataFrames
            e.g., {
                'kpi_overview': DataFrame with KPIs,
                'movements': DataFrame with object movements,
                'breakdown_by_source': DataFrame with source breakdown
            }
        """
        pass

    def export_to_csv(
        self,
        results: Dict[str, pd.DataFrame],
        output_dir: str
    ) -> Dict[str, str]:
        """
        Export analysis results to CSV files

        Args:
            results: Dictionary of DataFrames from analyze()
            output_dir: Directory to write CSV files

        Returns:
            Dictionary mapping insight names to file paths
        """
        import os
        from datetime import datetime

        timestamp = datetime.now().strftime('%Y-%m-%d')
        file_paths = {}

        for insight_name, df in results.items():
            if df is None or df.empty:
                logger.warning(f"Skipping empty result: {insight_name}")
                continue

            # Generate filename
            filename = f"{self.object_type}_{insight_name}_{timestamp}.csv"
            filepath = os.path.join(output_dir, filename)

            # Write CSV with UTF-8 BOM for Excel compatibility
            df.to_csv(
                filepath,
                index=False,
                encoding='utf-8-sig',
                na_rep='–'
            )

            file_paths[insight_name] = filepath
            logger.info(f"Exported {insight_name} to {filepath}")

        return file_paths

    def get_summary_stats(self, snapshots: List[Any]) -> Dict[str, Any]:
        """
        Calculate summary statistics

        Subclasses can override to provide custom statistics.

        Args:
            snapshots: List of snapshots

        Returns:
            Dictionary with summary statistics
        """
        return {
            'total_objects': len(snapshots),
            'object_type': self.object_type
        }
