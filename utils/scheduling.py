# utils/scheduling.py
"""
Pure, DB-free scheduling helpers shared by SearchService/NurseRepository and
BookingService: computing the time window(s) a service occupies, and the
per-day working-hours segments those windows require (midnight-crossing
safe). No DB session, no availability decisions - just date/time math so
both callers use one definition.
"""
from datetime import datetime, timedelta, time
from typing import List, Tuple
from zoneinfo import ZoneInfo

from utils.time_calculator import calculate_end_time, get_total_days

# Working hours are stored as local wall-clock times (day_of_week + start/end,
# no date). This app is India-centric, so wall-clock checks are anchored to IST.
APP_TZ = ZoneInfo("Asia/Kolkata")


def ensure_aware(dt: datetime, tz: ZoneInfo = APP_TZ) -> datetime:
    """Naive input is assumed to be local (tz) time; aware input is kept as-is."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=tz)


def to_local_naive(dt: datetime, tz: ZoneInfo = APP_TZ) -> datetime:
    """Absolute instant -> naive local wall-clock, for working-hours comparison."""
    return ensure_aware(dt, tz).astimezone(tz).replace(tzinfo=None)


def compute_service_windows(
    service, scheduled_start_time: datetime, tz: ZoneInfo = APP_TZ
) -> List[Tuple[datetime, datetime]]:
    """
    Returns the list of tz-aware (start, end) windows a booking/search request
    for this service occupies.
      - Continuous: a single window spanning the full duration.
      - Daily_Shift: one window per day (start = day N's shift start).
    Raises ValueError for missing config or an unknown schedule_type.
    """
    start = ensure_aware(scheduled_start_time, tz)

    if service.schedule_type == "Continuous":
        end = calculate_end_time(start, service.duration, service.duration_type)
        return [(start, end)]

    if service.schedule_type == "Daily_Shift":
        if not service.shift_duration_hours:
            raise ValueError(
                "Daily_Shift services must have a shift_duration_hours defined."
            )
        total_days = get_total_days(service.duration, service.duration_type)
        windows = []
        for day_offset in range(total_days):
            shift_start = start + timedelta(days=day_offset)
            shift_end = shift_start + timedelta(hours=service.shift_duration_hours)
            windows.append((shift_start, shift_end))
        return windows

    raise ValueError(f"Unknown schedule type: {service.schedule_type}")


def compute_required_segments(
    windows: List[Tuple[datetime, datetime]], tz: ZoneInfo = APP_TZ
) -> List[Tuple[int, time, time]]:
    """
    Converts tz-aware (start, end) windows into the deduplicated, sorted set of
    local (weekday, seg_start, seg_end) working-hours segments that must be
    covered, splitting any window crossing midnight into per-day segments.
    E.g. 22:00 -> 06:00 becomes [(dayN, 22:00, 23:59:59), (dayN+1, 00:00, 06:00)].
    """
    segments = []
    for start, end in windows:
        local_start = to_local_naive(start, tz)
        local_end = to_local_naive(end, tz)
        current = local_start
        while current < local_end:
            next_midnight = datetime.combine(current.date() + timedelta(days=1), time.min)
            segment_end = min(local_end, next_midnight)
            end_time = (
                time(23, 59, 59) if segment_end == next_midnight else segment_end.time()
            )
            segments.append((current.weekday(), current.time(), end_time))
            current = segment_end
    return sorted(set(segments))
