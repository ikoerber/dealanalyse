#!/usr/bin/env python3
"""
HubSpot Monthly Deal Analysis & Board Reporting

Reads deal snapshot and history CSV files and generates:
1. KPI Overview - Monthly aggregated metrics
2. Deal Movements Detail - Operational analysis per deal per month
"""
import sys
import logging
import os
from datetime import datetime

from src.config import load_config, ConfigurationError
from src.analysis.stage_mapper import StageMapper
from src.reporting.report_generator import ReportGenerator


def setup_logging(config):
    """Setup logging for analysis"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f"analysis_{timestamp}.log"
    log_filepath = os.path.join(config.logs_dir, log_filename)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_filepath


def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("HubSpot Monthly Deal Analysis & Board Reporting")
    print("=" * 60)
    print()


def print_summary(kpi_report: str, movements_report: str, log_file: str):
    """Print execution summary"""
    print()
    print("=" * 60)
    print("Analysis Complete")
    print("=" * 60)
    print()
    print("Generated Reports:")
    print(f"  - KPI Overview:    {kpi_report}")
    print(f"  - Deal Movements:  {movements_report}")
    print()
    print(f"Check logs: {log_file}")
    print("=" * 60)


def main():
    """Main execution function"""
    print_banner()

    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()

        # Setup logging
        log_file = setup_logging(config)
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Starting HubSpot Deal Analysis")
        logger.info("=" * 60)
        logger.info(f"Configuration: {config}")

        # Load stage mapping
        print("Loading stage mapping configuration...")
        stage_mapping_path = os.path.join(os.getcwd(), 'config', 'stage_mapping.json')

        if not os.path.exists(stage_mapping_path):
            print()
            print(f"ERROR: Stage mapping file not found: {stage_mapping_path}")
            print()
            print("Please ensure config/stage_mapping.json exists.")
            return 1

        stage_mapper = StageMapper(config_path=stage_mapping_path)
        logger.info(f"Loaded {len(stage_mapper.stage_names)} stage mappings")

        # Initialize report generator
        print("Initializing report generator...")
        report_gen = ReportGenerator(config, stage_mapper)

        # Generate reports
        print()
        print("Analyzing deal data and generating reports...")
        print("This may take a few minutes depending on data volume.")
        print()

        kpi_report, movements_report = report_gen.generate_reports(
            start_date=config.start_date
        )

        # Print summary
        print_summary(kpi_report, movements_report, log_file)

        logger.info("Analysis complete")
        logger.info("=" * 60)

        return 0

    except ConfigurationError as e:
        print()
        print(f"Configuration Error: {e}")
        print()
        print("Please check your .env file and ensure all required variables are set.")
        return 1

    except FileNotFoundError as e:
        print()
        print(f"File Not Found: {e}")
        print()
        print("Please ensure:")
        print("1. fetch_deals.py has been run first to generate CSV files")
        print("2. config/stage_mapping.json exists")
        return 1

    except Exception as e:
        print()
        print(f"Unexpected Error: {e}")
        print()
        print("Please check the logs for more details.")
        logging.exception("Unexpected error occurred")
        return 1


if __name__ == '__main__':
    sys.exit(main())
