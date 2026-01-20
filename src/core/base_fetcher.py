"""
Generic Base Fetcher for HubSpot Objects

Provides abstract base class for fetching different object types (deals, contacts, companies).
Implements common patterns: pagination, checkpointing, progress logging.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..config import Config
from ..hubspot_client import HubSpotClient
from .checkpoint_manager import CheckpointManager
from .object_registry import ObjectTypeConfig

logger = logging.getLogger(__name__)

# Configuration constants
PROGRESS_LOG_INTERVAL = 50  # Log progress every N objects
CHECKPOINT_SAVE_INTERVAL = 100  # Save checkpoint every N objects


@dataclass
class ObjectSnapshot:
    """
    Generic snapshot for any HubSpot object

    Subclasses should extend this with object-specific fields
    """
    object_id: str
    object_type: str
    fetch_timestamp: str


class BaseFetcher(ABC):
    """
    Abstract base class for HubSpot object fetchers

    Implements common fetching patterns and provides hooks for object-specific logic.
    """

    def __init__(
        self,
        config: Config,
        client: HubSpotClient,
        object_type_config: ObjectTypeConfig
    ):
        """
        Initialize base fetcher

        Args:
            config: Application configuration
            client: HubSpot API client
            object_type_config: Object type configuration from ObjectRegistry
        """
        self.config = config
        self.client = client
        self.object_type_config = object_type_config
        self.object_type = object_type_config.object_type_id

        # Initialize checkpoint manager for this object type
        self.checkpoint_manager = CheckpointManager(
            self.object_type,
            config.output_dir
        )

        logger.info(
            f"Initialized {self.__class__.__name__} for {object_type_config.display_name}"
        )

    def fetch_all(self, use_checkpoint: bool = True) -> List[Any]:
        """
        Fetch all objects from HubSpot

        This is the main entry point that orchestrates the fetch process.

        Args:
            use_checkpoint: Whether to use checkpoint for resume capability

        Returns:
            List of object snapshots (subclass-specific type)
        """
        logger.info(f"Starting {self.object_type} fetch process")

        # Fetch all objects from API
        objects = self._fetch_from_api()
        total_objects = len(objects)

        logger.info(f"Found {total_objects} {self.object_type} to process")

        if total_objects == 0:
            logger.warning(f"No {self.object_type} found matching criteria")
            return []

        # Load checkpoint if enabled
        processed_ids = set()
        if use_checkpoint:
            processed_ids = self.checkpoint_manager.load()
            if processed_ids:
                logger.info(
                    f"Resuming from checkpoint: {len(processed_ids)} "
                    f"{self.object_type} already processed"
                )

        # Process objects
        snapshots = []
        fetch_timestamp = datetime.utcnow().isoformat() + 'Z'

        for idx, obj in enumerate(objects, start=1):
            object_id = self._get_object_id(obj)

            # Skip if already processed (checkpoint recovery)
            if object_id in processed_ids:
                logger.debug(f"Skipping already processed {self.object_type} {object_id}")
                continue

            # Progress logging
            if idx % PROGRESS_LOG_INTERVAL == 0 or idx == total_objects:
                logger.info(
                    f"Progress: {idx}/{total_objects} {self.object_type} processed "
                    f"({idx/total_objects*100:.1f}%)"
                )

            try:
                # Extract snapshot (subclass implements this)
                snapshot = self._extract_snapshot(obj, fetch_timestamp)

                # Optional enrichment hook (subclass can override)
                snapshot = self._enrich_snapshot(snapshot, obj)

                snapshots.append(snapshot)

                # Update checkpoint
                processed_ids.add(object_id)
                if use_checkpoint and idx % CHECKPOINT_SAVE_INTERVAL == 0:
                    self.checkpoint_manager.save(processed_ids)

            except Exception as e:
                logger.error(
                    f"Error processing {self.object_type} {object_id}: {e}",
                    exc_info=True
                )
                # Continue processing other objects

        # Final checkpoint save
        if use_checkpoint:
            self.checkpoint_manager.save(processed_ids)

        logger.info(
            f"{self.object_type.capitalize()} fetch complete: "
            f"{len(snapshots)} snapshots"
        )

        return snapshots

    def _fetch_from_api(self) -> List[Dict]:
        """
        Fetch all objects from HubSpot API using search_objects()

        This uses the generic search_objects() method with ObjectRegistry config.

        Returns:
            List of raw object dictionaries from API
        """
        logger.info(f"Fetching {self.object_type} from HubSpot API...")

        all_objects = []
        after = None
        page = 1

        while True:
            logger.info(f"Fetching {self.object_type} page {page}")

            result = self.client.search_objects(
                self.object_type_config,
                limit=100,
                after=after,
                start_date_timestamp=self.config.start_date_timestamp
            )

            objects = result.get('results', [])
            all_objects.extend(objects)

            # Check if there are more pages
            paging = result.get('paging', {})
            if 'next' in paging:
                after = paging['next'].get('after')
                page += 1
            else:
                break

        logger.info(
            f"Fetched total of {len(all_objects)} {self.object_type} "
            f"across {page} page(s)"
        )

        return all_objects

    def _get_object_id(self, obj: Dict) -> str:
        """
        Extract object ID from API response

        Args:
            obj: Raw object dictionary from API

        Returns:
            Object ID string
        """
        # Try 'id' field first, then fall back to configured primary_id_field
        object_id = obj.get('id')
        if not object_id:
            # Try properties
            props = obj.get('properties', {})
            object_id = props.get(self.object_type_config.primary_id_field, '')

        return str(object_id)

    def clear_checkpoint(self):
        """Clear checkpoint file (call after successful completion)"""
        self.checkpoint_manager.clear()

    @abstractmethod
    def _extract_snapshot(self, obj: Dict, fetch_timestamp: str) -> Any:
        """
        Extract snapshot from raw API object

        Subclasses must implement this to create their specific snapshot type.

        Args:
            obj: Raw object dictionary from API
            fetch_timestamp: ISO timestamp of fetch operation

        Returns:
            Object snapshot (subclass-specific type)
        """
        pass

    def _enrich_snapshot(self, snapshot: Any, obj: Dict) -> Any:
        """
        Optional hook to enrich snapshot with additional data

        Subclasses can override this to add extra fields (e.g., associations, history).
        Default implementation returns snapshot unchanged.

        Args:
            snapshot: Snapshot created by _extract_snapshot()
            obj: Raw object dictionary from API

        Returns:
            Enriched snapshot
        """
        return snapshot

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
