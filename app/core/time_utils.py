from __future__ import annotations

from typing import Dict, List, Tuple
from datetime import datetime, time, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import BusinessHours, StoreTimezone
from collections import defaultdict

UTC = pytz.UTC

def get_store_timezone_str(session: Session, store_id: str) -> str:
    """ Return IANA timezone for store or default to America/Chicago """
    tz = (
        session.query(StoreTimezone.timezone_str)
        .filter(StoreTimezone.store_id == store_id)
        .scalar()
    )
    if not tz or tz not in pytz.all_timezones:
        return "America/Chicago"
    return tz

def to_aware_utc(dt: datetime) -> datetime:
    """Datetimes treated as UTC"""
    if dt.tzinfo is None:
        return UTC.localize(dt)
    return dt.astimezone(UTC)

def utc_to_local(utc_dt: datetime, tz_str: str) -> datetime:
    tz = pytz.timezone(tz_str)
    return to_aware_utc(utc_dt).astimezone(tz)

def local_to_utc(local_dt: datetime, tz_str: str) -> datetime:
    tz = pytz.timezone(tz_str)
    if local_dt.tzinfo is None:
        local_dt = tz.localize(local_dt)
    else:
        local_dt = local_dt.astimezone(tz)
    return local_dt.astimezone(UTC)

def get_business_hours_map(session: Session, store_id: str) -> dict[int, list[tuple[time, time]]]:
    """
    Query DB for business hours of a store.
    If no rows exist, assume store is open 24x7.
    """
    rows = (
        session.query(BusinessHours.day_of_week,
                      BusinessHours.start_time_local,
                      BusinessHours.end_time_local)
        .filter(BusinessHours.store_id == store_id)
        .all()
    )
    if not rows:
        # Fallback: store is open 24x7
        # Return empty dict to signal 24x7 operation
        return {}

    business_hours = defaultdict(list)
    for day, start_t, end_t in rows:
        business_hours[day].append((start_t, end_t))

    return dict(business_hours)

def expand_business_hours_to_utc(
    tz_str: str,
    bh_map: Dict[int, List[Tuple[time, time]]],
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> List[Tuple[datetime, datetime]]:
    """
    Convert business hours (local times) into UTC intervals,
    clipped to the given UTC window.
    """
    window_start_utc = to_aware_utc(window_start_utc)
    window_end_utc = to_aware_utc(window_end_utc)

    # Special case: empty bh_map means 24x7
    if not bh_map:
        return [(window_start_utc, window_end_utc)]

    tz = pytz.timezone(tz_str)
    
    # Expand the window slightly to catch business hours that might span across days
    local_start = utc_to_local(window_start_utc, tz_str)
    local_end = utc_to_local(window_end_utc, tz_str)
    
    # Go one day before and after to catch overnight spans
    start_date = local_start.date() - timedelta(days=1)
    end_date = local_end.date() + timedelta(days=1)

    intervals_utc: List[Tuple[datetime, datetime]] = []

    cur_date = start_date
    while cur_date <= end_date:
        dow = cur_date.weekday()
        day_rules = bh_map.get(dow, [])

        for start_t, end_t in day_rules:
            if start_t == end_t == time(0, 0):
                # Special case: 00:00 to 00:00 means 24 hours
                s_local = tz.localize(datetime.combine(cur_date, time(0, 0)))
                e_local = tz.localize(datetime.combine(cur_date + timedelta(days=1), time(0, 0)))
            elif start_t <= end_t:
                # Same day interval
                s_local = tz.localize(datetime.combine(cur_date, start_t))
                e_local = tz.localize(datetime.combine(cur_date, end_t))
            else:
                # Overnight interval
                s_local = tz.localize(datetime.combine(cur_date, start_t))
                e_local = tz.localize(datetime.combine(cur_date + timedelta(days=1), end_t))
            
            # Convert to UTC
            s_utc = s_local.astimezone(UTC)
            e_utc = e_local.astimezone(UTC)
            
            # Only add if it overlaps with our window
            if e_utc > window_start_utc and s_utc < window_end_utc:
                clipped_start = max(s_utc, window_start_utc)
                clipped_end = min(e_utc, window_end_utc)
                if clipped_start < clipped_end:
                    intervals_utc.append((clipped_start, clipped_end))

        cur_date += timedelta(days=1)

    return merge_utc_intervals(intervals_utc)

def merge_utc_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    
    for s, e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    
    return merged