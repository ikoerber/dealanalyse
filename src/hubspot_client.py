"""HubSpot API Client with rate limiting and retry logic"""
import time
import logging
from typing import Dict, List, Optional
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .config import Config

logger = logging.getLogger(__name__)


class HubSpotAPIError(Exception):
    """Base exception for HubSpot API errors"""
    pass


class HubSpotAuthenticationError(HubSpotAPIError):
    """Raised when authentication fails"""
    pass


class HubSpotRateLimitError(HubSpotAPIError):
    """Raised when rate limit is exceeded"""
    pass


class HubSpotClient:
    """Client for interacting with HubSpot CRM API v3"""

    def __init__(self, config: Config):
        """
        Initialize HubSpot client

        Args:
            config: Configuration object with API credentials and settings
        """
        self.config = config
        self.base_url = config.hubspot_base_url
        self.headers = config.get_auth_header()
        self.rate_limit_delay = config.rate_limit_delay
        self.last_request_time = 0
        self.api_call_count = 0

    def _rate_limit(self):
        """Enforce rate limiting between API requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    @retry(
        retry=retry_if_exception_type((HubSpotRateLimitError, requests.exceptions.RequestException)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request to HubSpot API with rate limiting and retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            HubSpotAuthenticationError: If authentication fails
            HubSpotRateLimitError: If rate limit exceeded (will retry)
            HubSpotAPIError: For other API errors
        """
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"

        logger.debug(f"Making {method} request to {endpoint}")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=30,
                **kwargs
            )

            self.api_call_count += 1

            # Handle different error codes
            if response.status_code == 401:
                logger.error("Authentication failed - check your access token")
                raise HubSpotAuthenticationError(
                    "Authentication failed. Please verify your HUBSPOT_ACCESS_TOKEN in .env"
                )

            elif response.status_code == 429:
                logger.warning("Rate limit exceeded, will retry")
                raise HubSpotRateLimitError("Rate limit exceeded")

            elif response.status_code == 404:
                logger.warning(f"Resource not found: {endpoint}")
                return response

            elif response.status_code >= 500:
                logger.error(f"Server error {response.status_code}: {response.text}")
                raise HubSpotAPIError(f"Server error: {response.status_code}")

            elif not response.ok:
                logger.error(f"API error {response.status_code}: {response.text}")
                raise HubSpotAPIError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

            return response

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {endpoint}")
            raise HubSpotAPIError("Request timeout")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HubSpotAPIError(f"Connection error: {e}")

    def search_deals(
        self,
        limit: int = 100,
        after: Optional[str] = None
    ) -> Dict:
        """
        Search for deals using HubSpot Search API

        Args:
            limit: Number of results per page (max 100)
            after: Pagination cursor from previous response

        Returns:
            Dictionary with search results including deals and pagination info
        """
        endpoint = "/crm/v3/objects/deals/search"

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "createdate",
                            "operator": "GTE",
                            "value": str(self.config.start_date_timestamp)
                        }
                    ]
                }
            ],
            "properties": [
                "dealname",
                "amount",
                "dealstage",
                "closedate",
                "createdate",
                "hs_object_id",
                "hs_forecast_amount",
                "hs_forecast_probability",
                "hubspot_owner_id",
                "notes_last_contacted",
                "notes_last_updated",
                "num_notes",
                "hs_lastmodifieddate",
                "hs_num_associated_queue_tasks",
                "num_associated_contacts"
            ],
            "limit": limit
        }

        if after:
            payload["after"] = after

        logger.info(f"Searching deals (limit={limit}, after={after})")

        response = self._make_request("POST", endpoint, json=payload)
        data = response.json()

        results_count = len(data.get('results', []))
        has_more = 'paging' in data and 'next' in data['paging']

        logger.info(f"Retrieved {results_count} deals (has_more={has_more})")

        return data

    def get_deal_history(self, deal_id: str) -> Dict:
        """
        Get deal history including property changes over time

        Args:
            deal_id: HubSpot deal ID

        Returns:
            Dictionary with deal data and property history
        """
        endpoint = f"/crm/v3/objects/deals/{deal_id}"
        params = {
            "propertiesWithHistory": "dealstage,amount,closedate,hs_projected_amount,hs_deal_stage_probability"
        }

        logger.debug(f"Fetching history for deal {deal_id}")

        response = self._make_request("GET", endpoint, params=params)

        if response.status_code == 404:
            logger.warning(f"Deal {deal_id} not found")
            return {}

        data = response.json()
        return data

    def get_all_deals(self) -> List[Dict]:
        """
        Fetch all deals matching the search criteria (handles pagination)

        Returns:
            List of all deal dictionaries
        """
        all_deals = []
        after = None
        page = 1

        while True:
            logger.info(f"Fetching deals page {page}")

            result = self.search_deals(limit=100, after=after)

            deals = result.get('results', [])
            all_deals.extend(deals)

            # Check if there are more pages
            paging = result.get('paging', {})
            if 'next' in paging:
                after = paging['next'].get('after')
                page += 1
            else:
                break

        logger.info(f"Fetched total of {len(all_deals)} deals across {page} page(s)")
        return all_deals

    def get_api_stats(self) -> Dict[str, int]:
        """Get API usage statistics"""
        return {
            'total_api_calls': self.api_call_count
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((HubSpotRateLimitError, requests.exceptions.RequestException)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_owners(self) -> Dict[str, str]:
        """
        Fetch all HubSpot owners and return a mapping of owner ID to owner name

        Returns:
            Dict mapping owner ID (str) to owner name (str)
        """
        self._rate_limit()

        url = f"{self.base_url}/crm/v3/owners/"
        logger.info(f"Fetching owners from: {url}")

        response = requests.get(url, headers=self.headers, timeout=30)
        self.api_call_count += 1

        if response.status_code == 429:
            raise HubSpotRateLimitError("Rate limit exceeded")
        elif response.status_code == 401:
            raise HubSpotAuthenticationError("Authentication failed - check your API key")
        elif response.status_code != 200:
            raise HubSpotAPIError(f"API request failed with status {response.status_code}: {response.text}")

        data = response.json()
        owners = data.get('results', [])

        # Create mapping of owner ID to full name
        owner_map = {}
        for owner in owners:
            owner_id = str(owner.get('id', ''))
            first_name = owner.get('firstName', '')
            last_name = owner.get('lastName', '')
            email = owner.get('email', '')

            # Use full name if available, otherwise email
            if first_name or last_name:
                full_name = f"{first_name} {last_name}".strip()
            else:
                full_name = email

            owner_map[owner_id] = full_name

        logger.info(f"Fetched {len(owner_map)} owners")
        return owner_map

    def search_contacts(
        self,
        limit: int = 100,
        after: Optional[str] = None
    ) -> Dict:
        """
        Search for contacts using HubSpot Search API

        Args:
            limit: Number of results per page (max 100)
            after: Pagination cursor from previous response

        Returns:
            Dictionary with search results including contacts and pagination info
        """
        endpoint = "/crm/v3/objects/contacts/search"

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "lifecyclestage",
                            "operator": "IN",
                            "values": ["marketingqualifiedlead", "salesqualifiedlead"]
                        }
                    ]
                }
            ],
            "properties": [
                "firstname",
                "lastname",
                "email",
                "lifecyclestage",
                "hs_v2_date_entered_marketingqualifiedlead",
                "hs_v2_date_entered_salesqualifiedlead",
                "ursprungliche_quelle__analog_unternehmensquelle_",
                "createdate",
                "hs_object_id"
            ],
            "limit": limit
        }

        if after:
            payload["after"] = after

        logger.info(f"Searching contacts (limit={limit}, after={after})")

        response = self._make_request("POST", endpoint, json=payload)
        data = response.json()

        results_count = len(data.get('results', []))
        has_more = 'paging' in data and 'next' in data['paging']

        logger.info(f"Retrieved {results_count} contacts (has_more={has_more})")

        return data

    def get_contact_companies(self, contact_id: str) -> List[Dict]:
        """
        Get companies associated with a contact via Associations API

        Args:
            contact_id: HubSpot contact ID

        Returns:
            List of company dictionaries with association type info
        """
        endpoint = f"/crm/v3/objects/contacts/{contact_id}/associations/companies"

        logger.debug(f"Fetching companies for contact {contact_id}")

        response = self._make_request("GET", endpoint)

        if response.status_code == 404:
            logger.debug(f"No companies found for contact {contact_id}")
            return []

        data = response.json()
        return data.get('results', [])

    def get_company_by_id(self, company_id: str) -> Optional[Dict]:
        """
        Get company details by ID

        Args:
            company_id: HubSpot company ID

        Returns:
            Company dictionary or None if not found
        """
        endpoint = f"/crm/v3/objects/companies/{company_id}"
        params = {
            "properties": "name"
        }

        logger.debug(f"Fetching company {company_id}")

        response = self._make_request("GET", endpoint, params=params)

        if response.status_code == 404:
            logger.debug(f"Company {company_id} not found")
            return None

        data = response.json()
        return data

    def get_all_contacts(self) -> List[Dict]:
        """
        Fetch all contacts matching the search criteria (handles pagination)

        Returns:
            List of all contact dictionaries
        """
        all_contacts = []
        after = None
        page = 1

        while True:
            logger.info(f"Fetching contacts page {page}")

            result = self.search_contacts(limit=100, after=after)

            contacts = result.get('results', [])
            all_contacts.extend(contacts)

            # Check if there are more pages
            paging = result.get('paging', {})
            if 'next' in paging:
                after = paging['next'].get('after')
                page += 1
            else:
                break

        logger.info(f"Fetched total of {len(all_contacts)} contacts across {page} page(s)")
        return all_contacts
