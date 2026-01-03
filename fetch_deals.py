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


def setup_logging(config):
    """Setup logging configuration"""
    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f"fetch_deals_{timestamp}.log"
    log_filepath = f"{config.logs_dir}/{log_filename}"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_filepath


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("HubSpot Deal Data Fetcher")
    print("=" * 60)
    print()


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

    print_banner()

    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        print(f"Configuration loaded: {config}")
        print()

        # Setup logging
        log_file = setup_logging(config)
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

        # Write CSV files
        print("Writing CSV files...")
        logger.info("Writing CSV files")

        snapshot_file = writer.write_snapshot_csv(snapshots)
        history_file = writer.write_history_csv(history_records)
        quality_file = writer.write_data_quality_report(snapshots)

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
        print()
        print(f"Configuration Error: {e}")
        print()
        print("Please check your .env file and ensure all required variables are set.")
        print("See .env.example for the required format.")
        return 1

    except HubSpotAuthenticationError as e:
        print()
        print(f"Authentication Error: {e}")
        print()
        print("Please verify your HUBSPOT_ACCESS_TOKEN in the .env file.")
        print("You can create a private app access token in your HubSpot settings:")
        print("Settings > Integrations > Private Apps")
        return 1

    except HubSpotAPIError as e:
        print()
        print(f"HubSpot API Error: {e}")
        print()
        print("Please check the logs for more details.")
        return 1

    except KeyboardInterrupt:
        print()
        print("Interrupted by user. Progress has been saved to checkpoint.")
        print("Run the script again to resume from where it left off.")
        return 130

    except Exception as e:
        print()
        print(f"Unexpected Error: {e}")
        print()
        print("Please check the logs for more details.")
        logging.exception("Unexpected error occurred")
        return 1


if __name__ == '__main__':
    sys.exit(main())
