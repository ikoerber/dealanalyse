"""
Companies Fetcher - HubSpot Companies specific implementation

Fetches company data from HubSpot.
"""
import logging
from typing import List, Dict
from dataclasses import dataclass

from ..core import BaseFetcher
from ..config import Config
from ..hubspot_client import HubSpotClient
from ..core.object_registry import ObjectTypeConfig

logger = logging.getLogger(__name__)


@dataclass
class CompanySnapshot:
    """Snapshot of a HubSpot company"""
    company_id: str
    name: str
    domain: str
    industry: str
    city: str
    state: str
    country: str
    phone: str
    createdate: str
    hs_lastmodifieddate: str
    hubspot_owner_id: str
    num_associated_contacts: str
    num_associated_deals: str
    lifecyclestage: str
    fetch_timestamp: str


class CompaniesFetcher(BaseFetcher):
    """
    Fetcher for HubSpot Companies

    Extends BaseFetcher with company-specific logic.
    Companies typically don't need additional enrichment.
    """

    def __init__(
        self,
        config: Config,
        client: HubSpotClient,
        object_type_config: ObjectTypeConfig
    ):
        """
        Initialize companies fetcher

        Args:
            config: Application configuration
            client: HubSpot API client
            object_type_config: Companies configuration from ObjectRegistry
        """
        super().__init__(config, client, object_type_config)

    def _extract_snapshot(self, obj: Dict, fetch_timestamp: str) -> CompanySnapshot:
        """
        Extract company snapshot from API object

        Args:
            obj: Raw company dictionary from API
            fetch_timestamp: ISO timestamp of fetch operation

        Returns:
            CompanySnapshot object
        """
        company_id = obj.get('id')
        properties = obj.get('properties', {})

        # Extract company properties
        snapshot = CompanySnapshot(
            company_id=str(company_id),
            name=properties.get('name', ''),
            domain=properties.get('domain', ''),
            industry=properties.get('industry', ''),
            city=properties.get('city', ''),
            state=properties.get('state', ''),
            country=properties.get('country', ''),
            phone=properties.get('phone', ''),
            createdate=properties.get('createdate', ''),
            hs_lastmodifieddate=properties.get('hs_lastmodifieddate', ''),
            hubspot_owner_id=properties.get('hubspot_owner_id', ''),
            num_associated_contacts=properties.get('num_associated_contacts', '0'),
            num_associated_deals=properties.get('num_associated_deals', '0'),
            lifecyclestage=properties.get('lifecyclestage', ''),
            fetch_timestamp=fetch_timestamp
        )

        return snapshot

    def get_summary_stats(self, snapshots: List[CompanySnapshot]) -> Dict:
        """
        Calculate summary statistics for companies

        Args:
            snapshots: List of company snapshots

        Returns:
            Dictionary with summary statistics
        """
        # Calculate total associated contacts and deals
        total_contacts = sum(
            int(c.num_associated_contacts) if c.num_associated_contacts.isdigit() else 0
            for c in snapshots
        )
        total_deals = sum(
            int(c.num_associated_deals) if c.num_associated_deals.isdigit() else 0
            for c in snapshots
        )

        return {
            'total_companies': len(snapshots),
            'total_associated_contacts': total_contacts,
            'total_associated_deals': total_deals
        }
