"""Timezone utilities for CAT (Harare timezone)."""
from datetime import datetime
import pytz

# Central Africa Time (Harare, Zimbabwe)
CAT_TIMEZONE = pytz.timezone('Africa/Harare')


def get_cat_now() -> datetime:
    """Get current datetime in CAT timezone."""
    return datetime.now(CAT_TIMEZONE)


def utc_to_cat(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to CAT timezone."""
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(CAT_TIMEZONE)


def format_cat_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime in CAT timezone."""
    if isinstance(dt, str):
        # Parse ISO format string
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    
    # Convert to CAT
    cat_dt = utc_to_cat(dt)
    return cat_dt.strftime(format_str)


def get_cat_date_str() -> str:
    """Get current date in CAT timezone as YYYY-MM-DD."""
    return get_cat_now().strftime('%Y-%m-%d')


def get_cat_timestamp_str() -> str:
    """Get current timestamp in CAT timezone as YYYYMMDD_HHMMSS."""
    return get_cat_now().strftime('%Y%m%d_%H%M%S')
