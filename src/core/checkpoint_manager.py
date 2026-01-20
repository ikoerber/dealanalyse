"""
Unified Checkpoint Manager for HubSpot Data Processing

Provides checkpoint/resume functionality for all object types (deals, contacts, companies, etc.).
"""
import json
import os
import logging
from datetime import datetime
from typing import Set, Optional, Dict, Any

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Generic checkpoint manager for tracking processed objects

    Supports resume-on-failure functionality by tracking which objects
    have been successfully processed.
    """

    def __init__(self, object_type: str, checkpoint_dir: str = "output"):
        """
        Initialize checkpoint manager

        Args:
            object_type: Type of object (e.g., 'deals', 'contacts', 'companies')
            checkpoint_dir: Directory where checkpoint files are stored
        """
        self.object_type = object_type
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_file = os.path.join(
            checkpoint_dir,
            f".checkpoint_{object_type}.json"
        )

        # Create directory if it doesn't exist
        os.makedirs(checkpoint_dir, exist_ok=True)

        logger.debug(f"Initialized CheckpointManager for {object_type}: {self.checkpoint_file}")

    def load(self) -> Set[str]:
        """
        Load previously processed object IDs from checkpoint file

        Returns:
            Set of processed object IDs (empty set if no checkpoint exists)
        """
        if not os.path.exists(self.checkpoint_file):
            logger.debug(f"No checkpoint file found for {self.object_type}")
            return set()

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Support both old and new checkpoint formats
                if 'processed_deal_ids' in data:
                    # Old format (deals only)
                    processed_ids = set(data['processed_deal_ids'])
                else:
                    # New format (generic)
                    processed_ids = set(data.get('processed_ids', []))

                last_updated = data.get('last_updated', 'unknown')

                logger.info(
                    f"Loaded checkpoint for {self.object_type}: "
                    f"{len(processed_ids)} processed objects "
                    f"(last updated: {last_updated})"
                )

                return processed_ids

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Could not load checkpoint for {self.object_type}: {e}")
            logger.warning("Starting fresh without checkpoint")
            return set()

        except Exception as e:
            logger.error(f"Unexpected error loading checkpoint for {self.object_type}: {e}")
            return set()

    def save(self, processed_ids: Set[str], metadata: Optional[Dict[str, Any]] = None):
        """
        Save processed object IDs to checkpoint file

        Args:
            processed_ids: Set of processed object IDs
            metadata: Optional additional metadata to store (e.g., statistics, counts)
        """
        try:
            checkpoint_data = {
                'object_type': self.object_type,
                'processed_ids': list(processed_ids),
                'count': len(processed_ids),
                'last_updated': datetime.utcnow().isoformat(),
            }

            # Add optional metadata
            if metadata:
                checkpoint_data['metadata'] = metadata

            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.debug(f"Checkpoint saved for {self.object_type}: {len(processed_ids)} objects")

        except Exception as e:
            logger.warning(f"Could not save checkpoint for {self.object_type}: {e}")

    def clear(self):
        """
        Remove checkpoint file

        Should be called after successful completion to clean up.
        """
        if os.path.exists(self.checkpoint_file):
            try:
                os.remove(self.checkpoint_file)
                logger.info(f"Checkpoint file cleared for {self.object_type}")
            except Exception as e:
                logger.warning(f"Could not remove checkpoint file for {self.object_type}: {e}")
        else:
            logger.debug(f"No checkpoint file to clear for {self.object_type}")

    def exists(self) -> bool:
        """
        Check if a checkpoint file exists

        Returns:
            True if checkpoint file exists, False otherwise
        """
        return os.path.exists(self.checkpoint_file)

    def get_info(self) -> Optional[Dict[str, Any]]:
        """
        Get checkpoint information without loading full processed IDs

        Returns:
            Dictionary with checkpoint metadata or None if no checkpoint exists
        """
        if not self.exists():
            return None

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Extract summary information
                info = {
                    'object_type': data.get('object_type', self.object_type),
                    'count': data.get('count', len(data.get('processed_ids', []))),
                    'last_updated': data.get('last_updated', 'unknown'),
                }

                # Include metadata if present
                if 'metadata' in data:
                    info['metadata'] = data['metadata']

                return info

        except Exception as e:
            logger.warning(f"Could not read checkpoint info for {self.object_type}: {e}")
            return None
