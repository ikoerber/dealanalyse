"""Configuration management for HubSpot Deal Fetcher"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class Config:
    """Configuration object for HubSpot API and application settings"""

    def __init__(self):
        """Load and validate configuration from environment variables"""
        # Load .env file
        load_dotenv()

        # Required settings
        self.hubspot_access_token = self._get_required_env('HUBSPOT_ACCESS_TOKEN')
        self.hubspot_base_url = self._get_env('HUBSPOT_BASE_URL', 'https://api.hubapi.com')

        # Date configuration
        start_date_str = self._get_env('START_DATE', '2025-01-01')
        self.start_date = self._parse_date(start_date_str)
        self.start_date_timestamp = self._date_to_timestamp_ms(self.start_date)

        # Rate limiting and retry configuration
        self.rate_limit_delay = float(self._get_env('RATE_LIMIT_DELAY', '0.11'))
        self.max_retries = int(self._get_env('MAX_RETRIES', '3'))

        # Application paths
        self.output_dir = os.path.join(os.getcwd(), 'output')
        self.logs_dir = os.path.join(os.getcwd(), 'logs')
        self.checkpoint_file = os.path.join(self.output_dir, '.checkpoint_deals.json')

        # Ensure directories exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(key)
        if not value:
            raise ConfigurationError(
                f"Required environment variable '{key}' is not set. "
                f"Please check your .env file."
            )
        return value

    def _get_env(self, key: str, default: str) -> str:
        """Get environment variable with default value"""
        return os.getenv(key, default)

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string in YYYY-MM-DD format"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError as e:
            raise ConfigurationError(
                f"Invalid date format for START_DATE: '{date_str}'. "
                f"Expected format: YYYY-MM-DD"
            ) from e

    def _date_to_timestamp_ms(self, dt: datetime) -> int:
        """Convert datetime to Unix timestamp in milliseconds (HubSpot format)"""
        return int(dt.timestamp() * 1000)

    def get_auth_header(self) -> dict:
        """Get authorization header for HubSpot API requests"""
        return {
            'Authorization': f'Bearer {self.hubspot_access_token}',
            'Content-Type': 'application/json'
        }

    def __repr__(self) -> str:
        """String representation (without sensitive data)"""
        return (
            f"Config(base_url={self.hubspot_base_url}, "
            f"start_date={self.start_date.strftime('%Y-%m-%d')}, "
            f"rate_limit_delay={self.rate_limit_delay}s, "
            f"max_retries={self.max_retries})"
        )


def load_config() -> Config:
    """Load and return configuration object"""
    try:
        config = Config()
        return config
    except ConfigurationError as e:
        print(f"Configuration Error: {e}")
        raise
