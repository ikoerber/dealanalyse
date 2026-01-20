"""Data fetching and transformation logic"""
import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from .config import Config
from .hubspot_client import HubSpotClient
from .core import CheckpointManager

logger = logging.getLogger(__name__)

# Configuration constants
PROGRESS_LOG_INTERVAL = 50  # Log progress every N deals
CHECKPOINT_SAVE_INTERVAL = 100  # Save checkpoint every N deals
CONTACT_ENRICHMENT_LOG_INTERVAL = 25  # Log contact enrichment progress every N deals


@dataclass
class DealSnapshot:
    """Represents current state of a deal"""
    deal_id: str
    deal_name: str
    current_amount: str
    current_dealstage: str
    current_closedate: str
    create_date: str
    has_history: bool
    fetch_timestamp: str
    hs_forecast_amount: str = ''
    hs_forecast_probability: str = ''
    hubspot_owner_id: str = ''
    notes_last_contacted: str = ''
    notes_last_updated: str = ''
    num_notes: str = ''
    hs_lastmodifieddate: str = ''
    hs_num_associated_queue_tasks: str = ''
    num_associated_contacts: str = ''
    rejection_reason: str = ''
    contact_source: str = ''
    primary_contact_id: str = ''


@dataclass
class HistoryRecord:
    """Represents a single property change in deal history"""
    deal_id: str
    deal_name: str
    property_name: str
    property_value: str
    change_timestamp: str
    source_type: str
    change_order: int


class DataFetcher:
    """Orchestrates fetching and transforming HubSpot deal data"""

    def __init__(self, config: Config, client: HubSpotClient):
        """
        Initialize data fetcher

        Args:
            config: Configuration object
            client: HubSpot API client
        """
        self.config = config
        self.client = client
        # Initialize checkpoint manager for deals
        self.checkpoint_manager = CheckpointManager('deals', config.output_dir)

    def load_checkpoint(self) -> set:
        """
        Load previously processed deal IDs from checkpoint file

        DEPRECATED: Use self.checkpoint_manager.load() instead
        Kept for backward compatibility
        """
        return self.checkpoint_manager.load()

    def save_checkpoint(self, processed_ids: set):
        """
        Save processed deal IDs to checkpoint file

        DEPRECATED: Use self.checkpoint_manager.save() instead
        Kept for backward compatibility
        """
        self.checkpoint_manager.save(processed_ids)

    def clear_checkpoint(self):
        """
        Remove checkpoint file

        DEPRECATED: Use self.checkpoint_manager.clear() instead
        Kept for backward compatibility
        """
        self.checkpoint_manager.clear()

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> str:
        """Parse HubSpot timestamp to ISO 8601 format"""
        if not timestamp_str:
            return ""

        try:
            # HubSpot timestamps are in ISO 8601 format already
            return timestamp_str
        except Exception as e:
            logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return timestamp_str or ""

    def _extract_deal_snapshot(
        self,
        deal: Dict,
        has_history: bool,
        fetch_timestamp: str
    ) -> DealSnapshot:
        """
        Extract snapshot data from deal object

        Args:
            deal: Deal dictionary from HubSpot API
            has_history: Whether history was successfully fetched
            fetch_timestamp: ISO timestamp of when data was fetched

        Returns:
            DealSnapshot object
        """
        properties = deal.get('properties', {})

        return DealSnapshot(
            deal_id=deal.get('id', ''),
            deal_name=properties.get('dealname', ''),
            current_amount=properties.get('amount', ''),
            current_dealstage=properties.get('dealstage', ''),
            current_closedate=properties.get('closedate', ''),
            create_date=self._parse_timestamp(properties.get('createdate', '')),
            has_history=has_history,
            fetch_timestamp=fetch_timestamp,
            hs_forecast_amount=properties.get('hs_forecast_amount', ''),
            hs_forecast_probability=properties.get('hs_forecast_probability', ''),
            hubspot_owner_id=properties.get('hubspot_owner_id', ''),
            notes_last_contacted=self._parse_timestamp(properties.get('notes_last_contacted', '')),
            notes_last_updated=self._parse_timestamp(properties.get('notes_last_updated', '')),
            num_notes=properties.get('num_notes', '0'),
            hs_lastmodifieddate=self._parse_timestamp(properties.get('hs_lastmodifieddate', '')),
            hs_num_associated_queue_tasks=properties.get('hs_num_associated_queue_tasks', '0'),
            num_associated_contacts=properties.get('num_associated_contacts', '0'),
            rejection_reason=properties.get('grunde_fur_verlorenen_deal__sc_', ''),
            contact_source='',  # Will be filled later by fetching primary contact
            primary_contact_id=''  # Will be filled later by fetching primary contact
        )

    def _get_primary_contact_source(self, deal_id: str) -> Tuple[str, str]:
        """
        Get primary contact ID and source for a deal

        Args:
            deal_id: Deal ID

        Returns:
            Tuple of (contact_id, source) - both empty strings if not found
        """
        try:
            # Get all contacts associated with the deal
            contacts = self.client.get_deal_contacts(deal_id)

            if not contacts:
                return '', ''

            # Find primary contact (associationTypes with typeId 1 or first contact)
            primary_contact = None

            for contact in contacts:
                association_types = contact.get('associationTypes', [])
                for assoc_type in association_types:
                    # Primary contact association
                    if assoc_type.get('typeId') == 1:
                        primary_contact = contact
                        break
                if primary_contact:
                    break

            # Fallback to first contact if no primary found
            if not primary_contact and contacts:
                primary_contact = contacts[0]

            if not primary_contact:
                return '', ''

            contact_id = primary_contact.get('toObjectId', primary_contact.get('id', ''))

            # Fetch contact details to get source
            contact_details = self.client.get_contact_by_id(contact_id)

            if not contact_details:
                return contact_id, ''

            # Extract source from contact properties
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
            deal_name: Deal name (for reference)
            history_data: Deal data with propertiesWithHistory

        Returns:
            List of HistoryRecord objects
        """
        records = []

        properties_with_history = history_data.get('propertiesWithHistory', {})

        # Process each property that has history
        for property_name in ['dealstage', 'amount', 'closedate', 'hs_projected_amount', 'hs_deal_stage_probability']:
            if property_name not in properties_with_history:
                continue

            history_items = properties_with_history[property_name]

            if not isinstance(history_items, list):
                logger.warning(
                    f"Unexpected history format for deal {deal_id}, "
                    f"property {property_name}"
                )
                continue

            # Sort by timestamp to ensure chronological order
            sorted_history = sorted(
                history_items,
                key=lambda x: x.get('timestamp', '')
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

    def fetch_all_data(self) -> Tuple[List[DealSnapshot], List[HistoryRecord]]:
        """
        Fetch all deal data and history from HubSpot

        Returns:
            Tuple of (snapshots, history_records)
        """
        logger.info("Starting data fetch process")

        # Fetch all deals
        deals = self.client.get_all_deals()
        total_deals = len(deals)
        logger.info(f"Found {total_deals} deals to process")

        if total_deals == 0:
            logger.warning("No deals found matching criteria")
            return [], []

        # Load checkpoint
        processed_ids = self.load_checkpoint()

        snapshots = []
        history_records = []
        fetch_timestamp = datetime.utcnow().isoformat() + 'Z'

        # Process each deal
        for idx, deal in enumerate(deals, start=1):
            deal_id = deal.get('id')
            deal_name = deal.get('properties', {}).get('dealname', 'Unknown')

            # Skip if already processed (checkpoint recovery)
            if deal_id in processed_ids:
                logger.debug(f"Skipping already processed deal {deal_id}")
                continue

            # Progress logging
            if idx % PROGRESS_LOG_INTERVAL == 0 or idx == total_deals:
                logger.info(
                    f"Progress: {idx}/{total_deals} deals processed "
                    f"({idx/total_deals*100:.1f}%)"
                )

            # Fetch history for this deal
            has_history = False
            try:
                history_data = self.client.get_deal_history(deal_id)

                if history_data:
                    has_history = True

                    # Extract history records
                    records = self._extract_history_records(
                        deal_id=deal_id,
                        deal_name=deal_name,
                        history_data=history_data
                    )
                    history_records.extend(records)
                else:
                    logger.warning(f"No history data returned for deal {deal_id}")

            except Exception as e:
                logger.error(f"Error fetching history for deal {deal_id}: {e}")
                # Continue processing other deals

            # Create snapshot
            snapshot = self._extract_deal_snapshot(
                deal=deal,
                has_history=has_history,
                fetch_timestamp=fetch_timestamp
            )
            snapshots.append(snapshot)

            # Update checkpoint every 100 deals
            processed_ids.add(deal_id)
            if idx % CHECKPOINT_SAVE_INTERVAL == 0:
                self.save_checkpoint(processed_ids)

        # Final checkpoint save
        self.save_checkpoint(processed_ids)

        logger.info(
            f"Data fetch complete: {len(snapshots)} snapshots, "
            f"{len(history_records)} history records"
        )

        # Second pass: Enrich snapshots with primary contact source
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

        return snapshots, history_records

    def get_summary_stats(
        self,
        snapshots: List[DealSnapshot],
        history_records: List[HistoryRecord]
    ) -> Dict:
        """
        Calculate summary statistics

        Args:
            snapshots: List of deal snapshots
            history_records: List of history records

        Returns:
            Dictionary with summary statistics
        """
        deals_with_history = sum(1 for s in snapshots if s.has_history)
        deals_without_history = len(snapshots) - deals_with_history

        return {
            'total_deals': len(snapshots),
            'deals_with_history': deals_with_history,
            'deals_without_history': deals_without_history,
            'total_history_records': len(history_records)
        }
