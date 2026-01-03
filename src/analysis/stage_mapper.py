"""Stage mapping and pipeline progression logic"""
import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class StageMapper:
    """Handles stage ID to name mapping and pipeline progression logic"""

    def __init__(self, config_path: str):
        """
        Initialize stage mapper

        Args:
            config_path: Path to stage_mapping.json
        """
        self.config_path = config_path
        self.stage_names: Dict[str, str] = {}
        self.pipeline_order: List[str] = []
        self.won_stages: List[str] = []
        self.lost_stages: List[str] = []

        self._load_config()

    def _load_config(self):
        """Load stage mapping configuration from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.stage_names = config.get('stage_names', {})
            self.pipeline_order = config.get('pipeline_order', [])
            self.won_stages = config.get('won_stages', [])
            self.lost_stages = config.get('lost_stages', [])

            logger.info(
                f"Loaded stage mapping: {len(self.stage_names)} stages, "
                f"{len(self.pipeline_order)} pipeline stages"
            )

        except FileNotFoundError:
            logger.error(f"Stage mapping file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in stage mapping file: {e}")
            raise

    def get_stage_name(self, stage_id: str) -> str:
        """
        Get readable name for stage ID

        Args:
            stage_id: Stage identifier

        Returns:
            Readable stage name, or [UNKNOWN: id] if not found
        """
        if not stage_id:
            return ""

        if stage_id in self.stage_names:
            return self.stage_names[stage_id]
        else:
            logger.warning(f"Unknown stage ID: {stage_id}")
            return f"[UNKNOWN: {stage_id}]"

    def is_won_stage(self, stage_id: str) -> bool:
        """
        Check if stage represents a win

        Args:
            stage_id: Stage identifier

        Returns:
            True if stage is a won stage
        """
        return stage_id in self.won_stages

    def is_lost_stage(self, stage_id: str) -> bool:
        """
        Check if stage represents a loss

        Args:
            stage_id: Stage identifier

        Returns:
            True if stage is a lost stage
        """
        return stage_id in self.lost_stages

    def is_terminal_stage(self, stage_id: str) -> bool:
        """
        Check if stage is terminal (won or lost)

        Args:
            stage_id: Stage identifier

        Returns:
            True if stage is terminal
        """
        return self.is_won_stage(stage_id) or self.is_lost_stage(stage_id)

    def compare_stages(self, stage1: str, stage2: str) -> int:
        """
        Compare two stages in pipeline order

        Args:
            stage1: First stage ID
            stage2: Second stage ID

        Returns:
            -1 if stage1 comes before stage2 (ADVANCED when moving from 1 to 2)
             0 if same stage (STALLED)
             1 if stage1 comes after stage2 (REGRESSED when moving from 1 to 2)
        """
        # Same stage
        if stage1 == stage2:
            return 0

        # Try to find stages in pipeline order
        try:
            index1 = self.pipeline_order.index(stage1)
        except ValueError:
            logger.warning(f"Stage {stage1} not found in pipeline order")
            # If stage1 not in order, we can't compare
            return 0

        try:
            index2 = self.pipeline_order.index(stage2)
        except ValueError:
            logger.warning(f"Stage {stage2} not found in pipeline order")
            # If stage2 not in order, we can't compare
            return 0

        # Compare indices
        if index1 < index2:
            return -1  # stage1 is earlier in pipeline
        elif index1 > index2:
            return 1  # stage1 is later in pipeline
        else:
            return 0

    def categorize_stage_movement(self, stage_start: str, stage_end: str) -> str:
        """
        Determine movement type based on stage change

        Args:
            stage_start: Starting stage ID
            stage_end: Ending stage ID

        Returns:
            Movement type: WON, LOST, ADVANCED, REGRESSED, or STALLED
        """
        # Check for won/lost first (highest priority)
        if self.is_won_stage(stage_end):
            return "WON"

        if self.is_lost_stage(stage_end):
            return "LOST"

        # Compare pipeline positions
        comparison = self.compare_stages(stage_start, stage_end)

        if comparison == 0:
            return "STALLED"
        elif comparison == -1:
            return "ADVANCED"
        else:  # comparison == 1
            return "REGRESSED"
