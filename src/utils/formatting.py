"""
Formatting utilities for German number, date, and currency formats.

This module provides helper functions for formatting data according to German conventions:
- Numbers: 1.234.567 (dot as thousand separator)
- Currency: 1.234.567 €
- Percentages: +18,5% (comma as decimal separator)
- Dates: 08.01.2026 (DD.MM.YYYY)
"""

from datetime import datetime
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


def format_euro(amount: Union[float, int, str, None], include_symbol: bool = True) -> str:
    """
    Format number as Euro with German thousand separators.

    Args:
        amount: Amount to format (can be float, int, string, or None)
        include_symbol: Whether to include the € symbol (default: True)

    Returns:
        Formatted string like "1.234.567 €" or "1.234.567"
        Returns "-" for None or invalid values

    Examples:
        >>> format_euro(1234567.89)
        '1.234.568 €'
        >>> format_euro(50000, include_symbol=False)
        '50.000'
        >>> format_euro(None)
        '-'
    """
    if amount is None or amount == '' or amount == '-':
        return '-'

    try:
        # Convert to float if string
        if isinstance(amount, str):
            # Remove existing formatting
            cleaned = amount.replace('.', '').replace(',', '.').replace('€', '').strip()
            amount_val = float(cleaned)
        else:
            amount_val = float(amount)

        # Format with thousand separator (German style: dot as thousand separator)
        # Python's format uses comma, so we replace it with dot
        formatted = f"{amount_val:,.0f}".replace(',', '.')

        if include_symbol:
            return f"{formatted} €"
        return formatted

    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format amount '{amount}': {e}")
        return '-'


def format_percentage(value: Union[float, int, None], decimals: int = 1, include_sign: bool = False) -> str:
    """
    Format number as percentage with German decimal separator.

    Args:
        value: Percentage value to format (e.g., 18.5 for 18.5%)
        decimals: Number of decimal places (default: 1)
        include_sign: Whether to include + sign for positive values (default: False)

    Returns:
        Formatted string like "18,5%" or "+18,5%"
        Returns "-" for None or invalid values

    Examples:
        >>> format_percentage(18.5)
        '18,5%'
        >>> format_percentage(18.5, include_sign=True)
        '+18,5%'
        >>> format_percentage(-5.2, include_sign=True)
        '-5,2%'
    """
    if value is None:
        return '-'

    try:
        value_float = float(value)

        # Format with specified decimals, replacing dot with comma
        formatted = f"{value_float:.{decimals}f}".replace('.', ',')

        # Add sign if requested
        if include_sign and value_float > 0:
            return f"+{formatted}%"
        return f"{formatted}%"

    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format percentage '{value}': {e}")
        return '-'


def format_date_german(date_input: Union[str, datetime, None]) -> str:
    """
    Format date in German format (DD.MM.YYYY).

    Args:
        date_input: Date to format (ISO string, datetime object, or None)

    Returns:
        Formatted string like "08.01.2026"
        Returns "-" for None or invalid dates

    Examples:
        >>> format_date_german("2026-01-08")
        '08.01.2026'
        >>> format_date_german(datetime(2026, 1, 8))
        '08.01.2026'
        >>> format_date_german(None)
        '-'
    """
    if date_input is None or date_input == '' or date_input == '-':
        return '-'

    try:
        # Convert string to datetime if needed
        if isinstance(date_input, str):
            # Try to parse ISO format or other common formats
            if 'T' in date_input:
                # ISO format with time
                date_obj = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            else:
                # Try simple date format
                date_obj = datetime.strptime(date_input, '%Y-%m-%d')
        elif isinstance(date_input, datetime):
            date_obj = date_input
        else:
            raise ValueError(f"Unsupported date type: {type(date_input)}")

        # Format as DD.MM.YYYY
        return date_obj.strftime('%d.%m.%Y')

    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not format date '{date_input}': {e}")
        return '-'


def parse_euro_amount(amount_str: Union[str, float, int, None]) -> Optional[float]:
    """
    Parse Euro string back to float.

    Args:
        amount_str: Amount string like "1.234.567 €" or "1234567"

    Returns:
        Float value or None if parsing fails

    Examples:
        >>> parse_euro_amount("1.234.567 €")
        1234567.0
        >>> parse_euro_amount("50.000")
        50000.0
        >>> parse_euro_amount(None)
        None
    """
    if amount_str is None or amount_str == '' or amount_str == '-':
        return None

    try:
        # If already a number, just convert to float
        if isinstance(amount_str, (int, float)):
            return float(amount_str)

        # Remove Euro symbol and thousand separators
        cleaned = str(amount_str).replace('€', '').replace('.', '').replace(',', '.').strip()
        return float(cleaned)

    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Could not parse amount '{amount_str}': {e}")
        return None


def format_number_compact(value: Union[float, int, None], decimals: int = 0) -> str:
    """
    Format number with German thousand separators (no currency symbol).

    Args:
        value: Number to format
        decimals: Number of decimal places (default: 0)

    Returns:
        Formatted string like "1.234.567" or "1.234,56"

    Examples:
        >>> format_number_compact(1234567)
        '1.234.567'
        >>> format_number_compact(1234.567, decimals=2)
        '1.234,57'
    """
    if value is None:
        return '-'

    try:
        value_float = float(value)

        if decimals == 0:
            # Integer formatting
            formatted = f"{value_float:,.0f}".replace(',', '.')
        else:
            # Decimal formatting
            formatted = f"{value_float:,.{decimals}f}"
            # Replace comma with dot for thousands, and dot with comma for decimals
            # This is a bit tricky, so we do it in steps
            parts = formatted.split('.')
            integer_part = parts[0].replace(',', '.')
            decimal_part = parts[1] if len(parts) > 1 else ''
            formatted = f"{integer_part},{decimal_part}" if decimal_part else integer_part

        return formatted

    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format number '{value}': {e}")
        return '-'
