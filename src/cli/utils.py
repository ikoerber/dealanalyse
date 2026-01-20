#!/usr/bin/env python3
"""
CLI Utilities for HubSpot Data Processing

Shared utilities for CLI scripts to eliminate code duplication.
"""
import sys
import logging
from datetime import datetime
from typing import Callable

from src.config import Config, ConfigurationError
from src.hubspot_client import HubSpotAPIError, HubSpotAuthenticationError


def setup_logging(config: Config, script_name: str) -> str:
    """
    Setup logging configuration for CLI scripts

    Args:
        config: Configuration object containing logs_dir
        script_name: Name of the script (e.g., 'fetch_deals', 'analyze_contacts')

    Returns:
        Path to log file
    """
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f"{script_name}_{timestamp}.log"
    log_filepath = f"{config.logs_dir}/{log_filename}"

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
    """
    Format duration in seconds to human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "45s", "2.3m", "1.5h")
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def print_banner(title: str):
    """
    Print application banner

    Args:
        title: Title to display in banner
    """
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()


class CLIErrorHandler:
    """
    Standardized CLI error handling for HubSpot scripts

    Handles common exceptions with user-friendly messages.
    """

    @staticmethod
    def handle_configuration_error(error: ConfigurationError) -> int:
        """Handle ConfigurationError"""
        print()
        print(f"Configuration Error: {error}")
        print()
        print("Please check your .env file and ensure all required variables are set.")
        print("See .env.example for the required format.")
        return 1

    @staticmethod
    def handle_authentication_error(error: HubSpotAuthenticationError) -> int:
        """Handle HubSpotAuthenticationError"""
        print()
        print(f"Authentication Error: {error}")
        print()
        print("Please verify your HUBSPOT_ACCESS_TOKEN in the .env file.")
        print("You can create a private app access token in your HubSpot settings:")
        print("Settings > Integrations > Private Apps")
        return 1

    @staticmethod
    def handle_api_error(error: HubSpotAPIError) -> int:
        """Handle HubSpotAPIError"""
        print()
        print(f"HubSpot API Error: {error}")
        print()
        print("Please check the logs for more details.")
        return 1

    @staticmethod
    def handle_keyboard_interrupt(checkpoint_available: bool = False) -> int:
        """Handle KeyboardInterrupt"""
        print()
        if checkpoint_available:
            print("Interrupted by user. Progress has been saved to checkpoint.")
            print("Run the script again to resume from where it left off.")
        else:
            print("Interrupted by user.")
        return 130

    @staticmethod
    def handle_generic_error(error: Exception) -> int:
        """Handle generic Exception"""
        print()
        print(f"Unexpected Error: {error}")
        print()
        print("Please check the logs for more details.")
        logging.exception("Unexpected error occurred")
        return 1

    @staticmethod
    def run_with_error_handling(main_func: Callable, checkpoint_available: bool = False) -> int:
        """
        Run a main function with standardized error handling

        Args:
            main_func: The main function to execute
            checkpoint_available: Whether checkpoint system is available (for KeyboardInterrupt message)

        Returns:
            Exit code (0 for success, non-zero for errors)
        """
        try:
            return main_func()
        except ConfigurationError as e:
            return CLIErrorHandler.handle_configuration_error(e)
        except HubSpotAuthenticationError as e:
            return CLIErrorHandler.handle_authentication_error(e)
        except HubSpotAPIError as e:
            return CLIErrorHandler.handle_api_error(e)
        except KeyboardInterrupt:
            return CLIErrorHandler.handle_keyboard_interrupt(checkpoint_available)
        except Exception as e:
            return CLIErrorHandler.handle_generic_error(e)
