"""
Report Registry for HubSpot Analytics

Manages report definitions and provides access to report configurations.
"""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReportDataSource:
    """Data source configuration for a report"""
    fetcher: str
    requires_history: bool = False
    requires_associations: List[str] = field(default_factory=list)


@dataclass
class ReportAnalysis:
    """Analysis configuration for a report"""
    analyzer: str
    method: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportOutput:
    """Output configuration for a report"""
    format: str
    template: Optional[str] = None
    filename_pattern: Optional[str] = None
    sections: List[str] = field(default_factory=list)
    layout: Dict[str, Any] = field(default_factory=dict)
    files: List[str] = field(default_factory=list)


@dataclass
class ReportSchedule:
    """Schedule configuration for a report"""
    frequency: str  # 'daily', 'weekly', 'monthly', 'quarterly', 'on_demand'
    day_of_month: Optional[int] = None
    recipients: List[str] = field(default_factory=list)


@dataclass
class ReportDefinition:
    """Complete report definition"""
    report_id: str
    name: str
    description: str
    object_type: str
    enabled: bool
    data_source: ReportDataSource
    analysis: ReportAnalysis
    outputs: List[ReportOutput]
    schedule: ReportSchedule
    note: Optional[str] = None


class ReportRegistry:
    """
    Registry for report definitions

    Loads report configurations from JSON and provides access to report settings.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize report registry

        Args:
            config_path: Path to report_definitions.json (defaults to config/report_definitions.json)
        """
        if config_path is None:
            # Default to config/report_definitions.json relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'config', 'report_definitions.json')

        self.config_path = config_path
        self.report_definitions: Dict[str, ReportDefinition] = {}
        self._load_definitions()

    def _load_definitions(self):
        """Load report definitions from JSON file"""
        logger.info(f"Loading report definitions from {self.config_path}")

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Report definitions file not found: {self.config_path}"
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Skip schema metadata fields
            for report_id, config in data.items():
                if report_id.startswith('_'):
                    logger.debug(f"Skipping metadata field: {report_id}")
                    continue

                try:
                    # Parse data source
                    data_source_config = config.get('data_source', {})
                    data_source = ReportDataSource(
                        fetcher=data_source_config['fetcher'],
                        requires_history=data_source_config.get('requires_history', False),
                        requires_associations=data_source_config.get('requires_associations', [])
                    )

                    # Parse analysis
                    analysis_config = config.get('analysis', {})
                    analysis = ReportAnalysis(
                        analyzer=analysis_config['analyzer'],
                        method=analysis_config['method'],
                        parameters=analysis_config.get('parameters', {})
                    )

                    # Parse outputs
                    outputs = []
                    for output_config in config.get('outputs', []):
                        output = ReportOutput(
                            format=output_config['format'],
                            template=output_config.get('template'),
                            filename_pattern=output_config.get('filename_pattern'),
                            sections=output_config.get('sections', []),
                            layout=output_config.get('layout', {}),
                            files=output_config.get('files', [])
                        )
                        outputs.append(output)

                    # Parse schedule
                    schedule_config = config.get('schedule', {})
                    schedule = ReportSchedule(
                        frequency=schedule_config.get('frequency', 'on_demand'),
                        day_of_month=schedule_config.get('day_of_month'),
                        recipients=schedule_config.get('recipients', [])
                    )

                    # Create report definition
                    report_def = ReportDefinition(
                        report_id=report_id,
                        name=config['name'],
                        description=config.get('description', ''),
                        object_type=config['object_type'],
                        enabled=config.get('enabled', True),
                        data_source=data_source,
                        analysis=analysis,
                        outputs=outputs,
                        schedule=schedule,
                        note=config.get('note')
                    )

                    self.report_definitions[report_id] = report_def
                    logger.debug(f"Loaded report definition: {report_id}")

                except (KeyError, ValueError) as e:
                    logger.error(f"Failed to load report definition '{report_id}': {e}")
                    raise

            logger.info(f"Successfully loaded {len(self.report_definitions)} report definitions")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Invalid JSON in {self.config_path}: {e}")

    def get(self, report_id: str) -> ReportDefinition:
        """
        Get report definition by ID

        Args:
            report_id: Report identifier

        Returns:
            ReportDefinition

        Raises:
            KeyError: If report not found
        """
        if report_id not in self.report_definitions:
            available = ', '.join(self.report_definitions.keys())
            raise KeyError(
                f"Report '{report_id}' not found. Available reports: {available}"
            )

        return self.report_definitions[report_id]

    def list_reports(self, object_type: Optional[str] = None, enabled_only: bool = False) -> List[str]:
        """
        List available report IDs

        Args:
            object_type: Filter by object type (e.g., 'deals', 'contacts')
            enabled_only: Only return enabled reports

        Returns:
            List of report IDs
        """
        reports = self.report_definitions.values()

        if object_type:
            reports = [r for r in reports if r.object_type == object_type]

        if enabled_only:
            reports = [r for r in reports if r.enabled]

        return [r.report_id for r in reports]

    def get_by_object_type(self, object_type: str) -> List[ReportDefinition]:
        """
        Get all reports for a specific object type

        Args:
            object_type: Object type (e.g., 'deals', 'contacts')

        Returns:
            List of ReportDefinitions
        """
        return [
            report for report in self.report_definitions.values()
            if report.object_type == object_type
        ]

    def get_scheduled_reports(self, frequency: str) -> List[ReportDefinition]:
        """
        Get reports by schedule frequency

        Args:
            frequency: Schedule frequency ('daily', 'monthly', etc.)

        Returns:
            List of ReportDefinitions
        """
        return [
            report for report in self.report_definitions.values()
            if report.schedule.frequency == frequency and report.enabled
        ]

    def reload(self):
        """Reload report definitions from JSON file"""
        self.report_definitions.clear()
        self._load_definitions()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of report registry

        Returns:
            Dictionary with registry statistics
        """
        enabled_count = sum(1 for r in self.report_definitions.values() if r.enabled)
        object_types = set(r.object_type for r in self.report_definitions.values())

        return {
            'total_reports': len(self.report_definitions),
            'enabled_reports': enabled_count,
            'disabled_reports': len(self.report_definitions) - enabled_count,
            'object_types': list(object_types),
            'report_ids': list(self.report_definitions.keys())
        }
