#!/usr/bin/env python3
"""
HubSpot Deal Data Fetcher

Fetches deal data from HubSpot and exports to CSV files for data quality verification.
"""
import sys
import logging
import time
from datetime import datetime

from src.config import load_config, ConfigurationError
from src.hubspot_client import HubSpotClient, HubSpotAPIError, HubSpotAuthenticationError
from src.data_fetcher import DataFetcher
from src.csv_writer import CSVWriter
from src.cli import setup_logging, format_duration, print_banner, CLIErrorHandler


def print_summary(
    snapshots_count: int,
    history_count: int,
    stats: dict,
    api_stats: dict,
    snapshot_file: str,
    history_file: str,
    quality_file: str,
    duration: float,
    log_file: str
):
    """Print execution summary"""
    print()
    print("=" * 60)
    print("HubSpot Data Fetch Complete")
    print("=" * 60)
    print()
    print(f"Total Deals Fetched: {stats['total_deals']:,}")
    print(f"Deals with History: {stats['deals_with_history']:,}")
    print(f"Deals without History: {stats['deals_without_history']:,}")
    print(f"History Records: {stats['total_history_records']:,}")
    print()
    print("Output Files:")
    print(f"  - Snapshot: {snapshot_file}")
    print(f"  - History:  {history_file}")
    if quality_file:
        print(f"  - Quality Issues: {quality_file}")
    print()
    print(f"Execution Time: {format_duration(duration)}")
    print(f"API Calls Made: {api_stats['total_api_calls']:,}")
    print()
    print(f"Check logs: {log_file}")
    print("=" * 60)


def main():
    """Main execution function"""
    start_time = time.time()

    print_banner("HubSpot Deal Data Fetcher")

    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        print(f"Configuration loaded: {config}")
        print()

        # Setup logging
        log_file = setup_logging(config, 'fetch_deals')
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Starting HubSpot Deal Data Fetch")
        logger.info("=" * 60)
        logger.info(f"Configuration: {config}")

        # Initialize components
        print("Initializing HubSpot client...")
        client = HubSpotClient(config)

        print("Initializing data fetcher...")
        fetcher = DataFetcher(config, client)

        print("Initializing CSV writer...")
        writer = CSVWriter(config)
        print()

        # Fetch data
        print("Fetching deal data from HubSpot...")
        print("This may take several minutes depending on the number of deals.")
        print("Progress updates will be logged every 50 deals.")
        print()

        logger.info("Starting data fetch process")
        snapshots, history_records = fetcher.fetch_all_data()

        if not snapshots:
            print("No deals found. Exiting.")
            logger.warning("No deals found")
            return 0

        # Get statistics
        stats = fetcher.get_summary_stats(snapshots, history_records)
        api_stats = client.get_api_stats()

        logger.info(f"Data fetch complete: {stats}")

        # Fetch owners mapping (optional - requires crm.objects.owners.read scope)
        print("Fetching HubSpot owners...")
        logger.info("Fetching HubSpot owners")
        try:
            owners_map = client.get_owners()
            logger.info(f"Fetched {len(owners_map)} owners")
        except Exception as e:
            logger.warning(f"Could not fetch owners (missing scope?): {e}")
            print(f"⚠️  Warning: Could not fetch owners. Owner names will show as 'Unbekannt'.")
            print("    To enable: Add 'crm.objects.owners.read' scope to your HubSpot Private App.")
            owners_map = {}

        # Write CSV files
        print("Writing CSV files...")
        logger.info("Writing CSV files")

        snapshot_file = writer.write_snapshot_csv(snapshots)
        history_file = writer.write_history_csv(history_records)
        quality_file = writer.write_data_quality_report(snapshots)

        # Write owners mapping to JSON file
        import json
        owners_timestamp = datetime.now().strftime('%Y-%m-%d')
        owners_file = f"{config.output_dir}/owners_{owners_timestamp}.json"
        with open(owners_file, 'w', encoding='utf-8') as f:
            json.dump(owners_map, f, ensure_ascii=False, indent=2)
        logger.info(f"Owners mapping written to: {owners_file}")

        # Clear checkpoint on successful completion
        fetcher.clear_checkpoint()

        # Calculate duration
        duration = time.time() - start_time

        # Print summary
        print_summary(
            snapshots_count=len(snapshots),
            history_count=len(history_records),
            stats=stats,
            api_stats=api_stats,
            snapshot_file=snapshot_file,
            history_file=history_file,
            quality_file=quality_file,
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
        return CLIErrorHandler.handle_keyboard_interrupt(checkpoint_available=True)

    except Exception as e:
        return CLIErrorHandler.handle_generic_error(e)


if __name__ == '__main__':
    sys.exit(main())
