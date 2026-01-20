"""
Contacts Fetcher - HubSpot Contacts specific implementation

Fetches contact data (MQLs/SQLs) with company associations.
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from ..core import BaseFetcher
from ..config import Config
from ..hubspot_client import HubSpotClient
from ..core.object_registry import ObjectTypeConfig

logger = logging.getLogger(__name__)


@dataclass
class ContactSnapshot:
    """Snapshot of a HubSpot contact"""
    contact_id: str
    firstname: str
    lastname: str
    email: str
    lifecyclestage: str
    mql_date: str
    sql_date: str
    company_id: str
    company_name: str
    source: str
    fetch_timestamp: str


class ContactsFetcher(BaseFetcher):
    """
    Fetcher for HubSpot Contacts

    Extends BaseFetcher with contact-specific logic:
    - Company association fetching
    - MQL/SQL lifecycle stage filtering
    - Source field extraction
    """

    def __init__(
        self,
        config: Config,
        client: HubSpotClient,
        object_type_config: ObjectTypeConfig
    ):
        """
        Initialize contacts fetcher

        Args:
            config: Application configuration
            client: HubSpot API client
            object_type_config: Contacts configuration from ObjectRegistry
        """
        super().__init__(config, client, object_type_config)

    def _extract_snapshot(self, obj: Dict, fetch_timestamp: str) -> ContactSnapshot:
        """
        Extract contact snapshot from API object

        Args:
            obj: Raw contact dictionary from API
            fetch_timestamp: ISO timestamp of fetch operation

        Returns:
            ContactSnapshot object
        """
        contact_id = obj.get('id')
        properties = obj.get('properties', {})

        # Extract contact properties
        snapshot = ContactSnapshot(
            contact_id=str(contact_id),
            firstname=properties.get('firstname', ''),
            lastname=properties.get('lastname', ''),
            email=properties.get('email', ''),
            lifecyclestage=properties.get('lifecyclestage', ''),
            mql_date=properties.get(
                'hs_v2_date_entered_marketingqualifiedlead',
                properties.get('createdate', '')
            ),
            sql_date=properties.get('hs_v2_date_entered_salesqualifiedlead', ''),
            source=properties.get('ursprungliche_quelle__analog_unternehmensquelle_', 'Unbekannt'),
            company_id='',  # Will be populated in _enrich_snapshot
            company_name='',  # Will be populated in _enrich_snapshot
            fetch_timestamp=fetch_timestamp
        )

        return snapshot

    def _enrich_snapshot(self, snapshot: ContactSnapshot, obj: Dict) -> ContactSnapshot:
        """
        Enrich contact snapshot with company association

        Args:
            snapshot: ContactSnapshot created by _extract_snapshot()
            obj: Raw contact dictionary from API

        Returns:
            Enriched ContactSnapshot with company data
        """
        contact_id = snapshot.contact_id

        # Fetch associated companies
        try:
            companies = self.client.get_contact_companies(contact_id)

            # Find primary company (typeId === 1)
            primary_company = None
            for company_assoc in companies:
                # Check if this is a primary company association
                assoc_types = company_assoc.get('associationTypes', [])
                for assoc_type in assoc_types:
                    if assoc_type.get('typeId') == 1:  # Primary company
                        primary_company = company_assoc
                        break
                if primary_company:
                    break

            # Fallback to first company if no primary found
            if not primary_company and companies:
                primary_company = companies[0]

            # Get company details if found
            if primary_company:
                company_id = primary_company.get('toObjectId')

                # Check if company_id is valid before API call
                if company_id:
                    try:
                        company_details = self.client.get_company_by_id(company_id)
                        if company_details:
                            company_name = company_details.get('properties', {}).get('name', '')
                            snapshot.company_id = str(company_id)
                            snapshot.company_name = company_name
                        else:
                            snapshot.company_id = ''
                            snapshot.company_name = ''
                    except Exception as e:
                        logger.warning(f"Failed to fetch company {company_id}: {e}")
                        snapshot.company_id = str(company_id)
                        snapshot.company_name = ''
                else:
                    # Company ID is None
                    snapshot.company_id = ''
                    snapshot.company_name = ''
            else:
                snapshot.company_id = ''
                snapshot.company_name = ''

        except Exception as e:
            logger.warning(f"Failed to fetch companies for contact {contact_id}: {e}")
            snapshot.company_id = ''
            snapshot.company_name = ''

        return snapshot

    def get_summary_stats(self, snapshots: List[ContactSnapshot]) -> Dict:
        """
        Calculate summary statistics for contacts

        Args:
            snapshots: List of contact snapshots

        Returns:
            Dictionary with summary statistics
        """
        mqls_count = sum(1 for c in snapshots if c.lifecyclestage == 'marketingqualifiedlead')
        sqls_count = sum(1 for c in snapshots if c.lifecyclestage == 'salesqualifiedlead')

        return {
            'total_contacts': len(snapshots),
            'mqls': mqls_count,
            'sqls': sqls_count
        }
