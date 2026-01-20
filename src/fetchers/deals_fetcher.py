"""
Deals Fetcher - HubSpot Deals specific implementation

Fetches deal data including history and primary contact associations.
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..core import BaseFetcher
from ..data_fetcher import DealSnapshot, HistoryRecord
from ..config import Config
from ..hubspot_client import HubSpotClient
from ..core.object_registry import ObjectTypeConfig

logger = logging.getLogger(__name__)

# Contact enrichment logging interval
CONTACT_ENRICHMENT_LOG_INTERVAL = 25


class DealsFetcher(BaseFetcher):
    """
    Fetcher for HubSpot Deals

    Extends BaseFetcher with deal-specific logic:
    - Deal history fetching
    - Primary contact association
    - Contact source enrichment
    """

    def __init__(
        self,
        config: Config,
        client: HubSpotClient,
        object_type_config: ObjectTypeConfig
    ):
        """
        Initialize deals fetcher

        Args:
            config: Application configuration
            client: HubSpot API client
            object_type_config: Deals configuration from ObjectRegistry
        """
        super().__init__(config, client, object_type_config)

        # Deal-specific: Track history records separately
        self.history_records: List[HistoryRecord] = []

    def fetch_all_with_history(
        self,
        use_checkpoint: bool = True
    ) -> Tuple[List[DealSnapshot], List[HistoryRecord]]:
        """
        Fetch all deals with history records

        This is the main entry point for deals fetching.

        Args:
            use_checkpoint: Whether to use checkpoint for resume capability

        Returns:
            Tuple of (deal_snapshots, history_records)
        """
        logger.info("Starting deals fetch process with history")

        # Reset history records
        self.history_records = []

        # Fetch deals using base class method
        snapshots = self.fetch_all(use_checkpoint=use_checkpoint)

        # Second pass: Enrich with primary contact sources
        if snapshots:
            self._enrich_with_contact_sources(snapshots)

        logger.info(
            f"Deals fetch complete: {len(snapshots)} snapshots, "
            f"{len(self.history_records)} history records"
        )

        return snapshots, self.history_records

    def _extract_snapshot(self, obj: Dict, fetch_timestamp: str) -> DealSnapshot:
        """
        Extract deal snapshot from API object

        Args:
            obj: Raw deal dictionary from API
            fetch_timestamp: ISO timestamp of fetch operation

        Returns:
            DealSnapshot object
        """
        deal_id = obj.get('id')
        properties = obj.get('properties', {})

        # Extract all properties
        snapshot = DealSnapshot(
            deal_id=str(deal_id),
            deal_name=properties.get('dealname', 'Unknown'),
            current_amount=properties.get('amount', ''),
            current_dealstage=properties.get('dealstage', ''),
            current_closedate=self._parse_timestamp(properties.get('closedate', '')),
            create_date=self._parse_timestamp(properties.get('createdate', '')),
            has_history=False,  # Will be updated in _enrich_snapshot
            fetch_timestamp=fetch_timestamp,
            hs_forecast_amount=properties.get('hs_forecast_amount', ''),
            hs_forecast_probability=properties.get('hs_forecast_probability', ''),
            hubspot_owner_id=properties.get('hubspot_owner_id', ''),
            notes_last_contacted=self._parse_timestamp(properties.get('notes_last_contacted', '')),
            notes_last_updated=self._parse_timestamp(properties.get('notes_last_updated', '')),
            num_notes=properties.get('num_notes', ''),
            hs_lastmodifieddate=self._parse_timestamp(properties.get('hs_lastmodifieddate', '')),
            hs_num_associated_queue_tasks=properties.get('hs_num_associated_queue_tasks', ''),
            num_associated_contacts=properties.get('num_associated_contacts', ''),
            rejection_reason=properties.get('grunde_fur_verlorenen_deal__sc_', ''),
            contact_source='',  # Will be populated in second pass
            primary_contact_id=''  # Will be populated in second pass
        )

        return snapshot

    def _enrich_snapshot(self, snapshot: DealSnapshot, obj: Dict) -> DealSnapshot:
        """
        Enrich deal snapshot with history data

        Args:
            snapshot: DealSnapshot created by _extract_snapshot()
            obj: Raw deal dictionary from API

        Returns:
            Enriched DealSnapshot with history
        """
        deal_id = snapshot.deal_id
        deal_name = snapshot.deal_name

        # Fetch history if configured
        if self.object_type_config.has_history:
            try:
                history_data = self.client.get_deal_history(deal_id)

                if history_data:
                    snapshot.has_history = True

                    # Extract history records
                    records = self._extract_history_records(
                        deal_id=deal_id,
                        deal_name=deal_name,
                        history_data=history_data
                    )
                    self.history_records.extend(records)
                else:
                    logger.debug(f"No history data returned for deal {deal_id}")

            except Exception as e:
                logger.error(f"Error fetching history for deal {deal_id}: {e}")
                # Continue without history

        return snapshot

    def _enrich_with_contact_sources(self, snapshots: List[DealSnapshot]):
        """
        Second pass: Enrich snapshots with primary contact sources

        Args:
            snapshots: List of DealSnapshot objects to enrich
        """
        logger.info("Starting second pass: Fetching primary contact sources...")
        logger.info("This may take a while depending on the number of deals.")

        for idx, snapshot in enumerate(snapshots, start=1):
            # Progress logging
            if idx % CONTACT_ENRICHMENT_LOG_INTERVAL == 0 or idx == len(snapshots):
                logger.info(
                    f"Contact enrichment progress: {idx}/{len(snapshots)} deals "
                    f"({idx/len(snapshots)*100:.1f}%)"
                )

            try:
                contact_id, source = self._get_primary_contact_source(snapshot.deal_id)
                snapshot.primary_contact_id = contact_id
                snapshot.contact_source = source if source else ''
            except Exception as e:
                logger.warning(f"Error fetching contact for deal {snapshot.deal_id}: {e}")
                # Continue with empty values
                snapshot.primary_contact_id = ''
                snapshot.contact_source = ''

        logger.info("Contact enrichment complete")

    def _get_primary_contact_source(self, deal_id: str) -> Tuple[str, str]:
        """
        Get primary contact ID and source for a deal

        Args:
            deal_id: Deal ID

        Returns:
            Tuple of (contact_id, source)
        """
        try:
            contacts = self.client.get_deal_contacts(deal_id)
            if not contacts:
                return '', ''

            # Find primary contact (typeId == 1)
            primary_contact = None
            for contact in contacts:
                association_types = contact.get('associationTypes', [])
                for assoc_type in association_types:
                    if assoc_type.get('typeId') == 1:
                        primary_contact = contact
                        break
                if primary_contact:
                    break

            # Fallback to first contact
            if not primary_contact and contacts:
                primary_contact = contacts[0]

            if not primary_contact:
                return '', ''

            contact_id = primary_contact.get('toObjectId', primary_contact.get('id', ''))
            contact_details = self.client.get_contact_by_id(contact_id)

            if not contact_details:
                return contact_id, ''

            properties = contact_details.get('properties', {})
            source = properties.get('ursprungliche_quelle__analog_unternehmensquelle_', '')
            return contact_id, source

        except Exception as e:
            logger.warning(f"Could not fetch primary contact for deal {deal_id}: {e}")
            return '', ''

    def _extract_history_records(
        self,
        deal_id: str,
        deal_name: str,
        history_data: Dict
    ) -> List[HistoryRecord]:
        """
        Extract history records from deal history data

        Args:
            deal_id: Deal ID
            deal_name: Deal name
            history_data: Raw history data from API

        Returns:
            List of HistoryRecord objects
        """
        records = []

        properties_with_history = history_data.get('propertiesWithHistory', {})

        for property_name, history_items in properties_with_history.items():
            if not history_items:
                continue

            # Sort by timestamp
            sorted_history = sorted(
                history_items,
                key=lambda x: x.get('timestamp', '0')
            )

            # Create a record for each history item
            for idx, item in enumerate(sorted_history, start=1):
                record = HistoryRecord(
                    deal_id=deal_id,
                    deal_name=deal_name,
                    property_name=property_name,
                    property_value=item.get('value', ''),
                    change_timestamp=self._parse_timestamp(item.get('timestamp', '')),
                    source_type=item.get('sourceType', ''),
                    change_order=idx
                )
                records.append(record)

        return records

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> str:
        """
        Parse HubSpot timestamp to ISO 8601 format

        Args:
            timestamp_str: Timestamp string from HubSpot

        Returns:
            ISO 8601 formatted timestamp or empty string
        """
        if not timestamp_str:
            return ""

        try:
            # Handle Unix timestamp (milliseconds)
            if timestamp_str.isdigit():
                timestamp_ms = int(timestamp_str)
                dt = datetime.utcfromtimestamp(timestamp_ms / 1000)
                return dt.isoformat() + 'Z'

            # Already ISO format
            if 'T' in timestamp_str:
                return timestamp_str

            return timestamp_str

        except (ValueError, AttributeError, OSError):
            logger.warning(f"Could not parse timestamp: {timestamp_str}")
            return ""

    def get_summary_stats(
        self,
        snapshots: List[DealSnapshot],
        history_records: Optional[List[HistoryRecord]] = None
    ) -> Dict:
        """
        Calculate summary statistics for deals

        Args:
            snapshots: List of deal snapshots
            history_records: Optional list of history records

        Returns:
            Dictionary with summary statistics
        """
        if history_records is None:
            history_records = self.history_records

        deals_with_history = sum(1 for s in snapshots if s.has_history)
        deals_without_history = len(snapshots) - deals_with_history

        return {
            'total_deals': len(snapshots),
            'deals_with_history': deals_with_history,
            'deals_without_history': deals_without_history,
            'total_history_records': len(history_records)
        }
