#!/usr/bin/env python3
"""
HubSpot Contact Data Fetcher

Fetches contact data (MQLs and SQLs) from HubSpot and exports to CSV for lead funnel analysis.
"""
import sys
import logging
import time
import argparse
from datetime import datetime

from src.config import load_config, ConfigurationError
from src.hubspot_client import HubSpotClient, HubSpotAPIError, HubSpotAuthenticationError
from src.csv_writer import CSVWriter
from src.cli import setup_logging, format_duration, print_banner, CLIErrorHandler


def fetch_contacts_with_companies(client: HubSpotClient, limit: int = None):
    """
    Fetch all contacts and their associated companies

    Args:
        client: HubSpot API client
        limit: Optional limit on number of contacts to fetch (for testing)

    Returns:
        List of contact dictionaries with company information
    """
    logger = logging.getLogger(__name__)

    # Fetch all contacts
    logger.info("Fetching all contacts...")
    contacts = client.get_all_contacts()
    logger.info(f"Retrieved {len(contacts)} contacts")

    # Apply limit if specified
    if limit and limit > 0:
        contacts = contacts[:limit]
        logger.info(f"Limited to first {limit} contacts for testing")
        print(f"⚠️  TEST MODE: Processing only first {limit} contacts")
        print()

    if not contacts:
        return []

    # Process each contact to add company information
    contacts_with_companies = []

    print(f"Processing {len(contacts)} contacts...")
    print("Fetching company associations (this may take a while)...")

    for idx, contact in enumerate(contacts, 1):
        if idx % 50 == 0:
            print(f"Progress: {idx}/{len(contacts)} contacts processed")
            logger.info(f"Processed {idx}/{len(contacts)} contacts")

        contact_id = contact.get('id')
        properties = contact.get('properties', {})

        # Extract contact properties
        contact_data = {
            'contact_id': contact_id,
            'firstname': properties.get('firstname', ''),
            'lastname': properties.get('lastname', ''),
            'email': properties.get('email', ''),
            'lifecyclestage': properties.get('lifecyclestage', ''),
            'mql_date': properties.get('hs_v2_date_entered_marketingqualifiedlead', properties.get('createdate', '')),
            'sql_date': properties.get('hs_v2_date_entered_salesqualifiedlead', ''),
            'source': properties.get('ursprungliche_quelle__analog_unternehmensquelle_', 'Unbekannt'),
        }

        # Fetch associated companies
        try:
            companies = client.get_contact_companies(contact_id)

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
                        company_details = client.get_company_by_id(company_id)
                        if company_details:
                            company_name = company_details.get('properties', {}).get('name', '')
                            contact_data['company_id'] = company_id
                            contact_data['company_name'] = company_name
                        else:
                            contact_data['company_id'] = ''
                            contact_data['company_name'] = ''
                    except Exception as e:
                        logger.warning(f"Failed to fetch company {company_id}: {e}")
                        contact_data['company_id'] = company_id
                        contact_data['company_name'] = ''
                else:
                    # Company ID is None
                    contact_data['company_id'] = ''
                    contact_data['company_name'] = ''
            else:
                contact_data['company_id'] = ''
                contact_data['company_name'] = ''

        except Exception as e:
            logger.warning(f"Failed to fetch companies for contact {contact_id}: {e}")
            contact_data['company_id'] = ''
            contact_data['company_name'] = ''

        contacts_with_companies.append(contact_data)

    return contacts_with_companies


def write_contacts_csv(writer: CSVWriter, contacts: list) -> str:
    """
    Write contacts data to CSV file

    Args:
        writer: CSV writer instance
        contacts: List of contact dictionaries

    Returns:
        Path to written CSV file
    """
    import csv
    timestamp = datetime.now().strftime('%Y-%m-%d')
    filename = f"contacts_snapshot_{timestamp}.csv"
    filepath = f"{writer.config.output_dir}/{filename}"

    # CSV header matching spec
    fieldnames = [
        'contact_id',
        'firstname',
        'lastname',
        'email',
        'lifecyclestage',
        'mql_date',
        'sql_date',
        'company_id',
        'company_name',
        'source'
    ]

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        csv_writer = csv.DictWriter(f, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(contacts)

    return filepath


def print_summary(
    contacts_count: int,
    mqls_count: int,
    sqls_count: int,
    api_stats: dict,
    snapshot_file: str,
    duration: float,
    log_file: str
):
    """Print execution summary"""
    print()
    print("=" * 60)
    print("HubSpot Contact Fetch Complete")
    print("=" * 60)
    print()
    print(f"Total Contacts Fetched: {contacts_count:,}")
    print(f"  - MQLs: {mqls_count:,}")
    print(f"  - SQLs: {sqls_count:,}")
    print()
    print("Output File:")
    print(f"  - Contacts: {snapshot_file}")
    print()
    print(f"Execution Time: {format_duration(duration)}")
    print(f"API Calls Made: {api_stats['total_api_calls']:,}")
    print()
    print(f"Check logs: {log_file}")
    print("=" * 60)


def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Fetch contact data (MQLs and SQLs) from HubSpot'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of contacts to fetch (for testing, e.g., --limit 100)'
    )
    args = parser.parse_args()

    start_time = time.time()

    print_banner("HubSpot Contact Data Fetcher (MQL/SQL Analysis)")

    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        print(f"Configuration loaded: {config}")
        print()

        # Setup logging
        log_file = setup_logging(config, 'fetch_contacts')
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Starting HubSpot Contact Data Fetch")
        logger.info("=" * 60)
        logger.info(f"Configuration: {config}")
        if args.limit:
            logger.info(f"TEST MODE: Limiting to {args.limit} contacts")

        # Initialize components
        print("Initializing HubSpot client...")
        client = HubSpotClient(config)

        print("Initializing CSV writer...")
        writer = CSVWriter(config)
        print()

        # Fetch data
        print("Fetching contact data from HubSpot...")
        print("This may take several minutes depending on the number of contacts.")
        print()

        logger.info("Starting contact fetch process")
        contacts = fetch_contacts_with_companies(client, limit=args.limit)

        if not contacts:
            print("No contacts found. Exiting.")
            logger.warning("No contacts found")
            return 0

        # Calculate statistics
        mqls_count = sum(1 for c in contacts if c['lifecyclestage'] == 'marketingqualifiedlead')
        sqls_count = sum(1 for c in contacts if c['lifecyclestage'] == 'salesqualifiedlead')

        api_stats = client.get_api_stats()

        logger.info(f"Data fetch complete: {len(contacts)} contacts, {mqls_count} MQLs, {sqls_count} SQLs")

        # Write CSV file
        print("Writing CSV file...")
        logger.info("Writing CSV file")

        snapshot_file = write_contacts_csv(writer, contacts)

        # Calculate duration
        duration = time.time() - start_time

        # Print summary
        print_summary(
            contacts_count=len(contacts),
            mqls_count=mqls_count,
            sqls_count=sqls_count,
            api_stats=api_stats,
            snapshot_file=snapshot_file,
            duration=duration,
            log_file=log_file
        )

        logger.info(f"Execution complete in {format_duration(duration)}")
        logger.info("=" * 60)

        return 0

    except ConfigurationError as e:
        return CLIErrorHandler.handle_configuration_error(e)

    except HubSpotAuthenticationError as e:
        return CLIErrorHandler.handle_authentication_error(e)

    except HubSpotAPIError as e:
        return CLIErrorHandler.handle_api_error(e)

    except KeyboardInterrupt:
        return CLIErrorHandler.handle_keyboard_interrupt(checkpoint_available=False)

    except Exception as e:
        return CLIErrorHandler.handle_generic_error(e)


if __name__ == '__main__':
    sys.exit(main())
