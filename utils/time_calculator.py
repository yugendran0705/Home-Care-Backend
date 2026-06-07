# utils/time_calculator.py
from datetime import datetime, timedelta

def calculate_end_time(start_time: datetime, duration: int, duration_type: str) -> datetime:
    """
    Calculates the scheduled end time based on duration and type.
    """
    duration_type = duration_type.lower()
    
    if duration_type in ['hour', 'hours']:
        return start_time + timedelta(hours=duration)
    elif duration_type in ['day', 'days']:
        return start_time + timedelta(days=duration)
    elif duration_type in ['week', 'weeks']:
        return start_time + timedelta(weeks=duration)
    else:
        raise ValueError(f"Unsupported duration type: {duration_type}")

def get_total_days(duration: int, duration_type: str) -> int:
    """Helper to convert weeks to days for the Daily_Shift loop."""
    if duration_type.lower() in ['week', 'weeks']:
        return duration * 7
    return duration