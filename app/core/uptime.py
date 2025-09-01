# app/core/uptime.py
from __future__ import annotations
import pytz
from pytz import timezone
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func, asc
from typing import List, Tuple, Dict
from app.core.time_utils import expand_business_hours_to_utc, get_business_hours_map, get_store_timezone_str, to_aware_utc
from app.models import StoreStatus

def get_dataset_now(session: Session) -> datetime:
    """
    'Now': max timestamp in store_status, returned as timezone-aware UTC
    If store has no data, we default to downtime (0)
    """

    max_ts = session.query(func.max(StoreStatus.timestamp_utc)).scalar()
    if max_ts is None:
        max_ts = datetime.now(timezone.utc)
    return to_aware_utc(max_ts)

def metrics_for_store(
        session: Session,
        store_id: str,
        now_utc: datetime,
) -> Dict[str, float]:
    """
    Compute uptime/downtime for last hour/day/week, clipped to business hours,
    returns mins for hours windows, hours for day/week windows as req

    Output: 
        uptime_last_hour, downtime_last_hour (minutes)
        uptime_last_day, downtime_last_day (hours)
        uptime_last_week, downtime_last_week (hours)
    """
    
    import os
    suppress_debug = os.environ.get('SUPPRESS_DEBUG', '0') == '1'
    
    now_utc = to_aware_utc(now_utc)
    windows = {
        "hour": (now_utc - timedelta(hours=1), now_utc),
        "day": (now_utc - timedelta(days=1), now_utc),
        "week": (now_utc - timedelta(days=7), now_utc)
    }

    tz_str = get_store_timezone_str(session, store_id)
    bh_map = get_business_hours_map(session, store_id)
    
    if not suppress_debug:
        print(f"\n=== METRICS DEBUG for {store_id} ===")
        print(f"Timezone: {tz_str}")
        print(f"Business hours map: {bh_map}")
        print(f"Now UTC: {now_utc}")

    results = {}

    for label, (ws, we) in windows.items():
        # UTC business windows inside [ws, we]
        bh_intervals_utc = expand_business_hours_to_utc(tz_str, bh_map, ws, we)
        
        # debug
        if not suppress_debug:
            print(f"\n{label} window: {ws} to {we}")
            print(f"Business hour intervals: {bh_intervals_utc}")
        
        if not bh_intervals_utc:
            # no overlap
            up_s = down_s = 0.0
        else:
            segments = _status_segments(session, store_id, ws, we)
            if not suppress_debug:
                print(f"Status segments: {segments}")
            
            up_s, down_s = _accumulate_overlaps(segments, bh_intervals_utc)
            if not suppress_debug:
                print(f"Uptime seconds: {up_s}, Downtime seconds: {down_s}")
        
        if label == "hour":
            results["uptime_last_hour"] = int(up_s / 60)
            results["downtime_last_hour"] = int(down_s / 60)
        elif label == "day":
            results["uptime_last_day"] = round(up_s / 3600.0, 2)
            results["downtime_last_day"] = round(down_s / 3600.0, 2)
        else:
            results["uptime_last_week"] = round(up_s / 3600.0, 2)
            results["downtime_last_week"] = round(down_s / 3600.0, 2)
    
    if not suppress_debug:
        print(f"\nFinal results: {results}")
    
    return results

def _status_segments(session: Session, store_id: str,
                     window_start_utc: datetime,
                     window_end_utc: datetime):
    ws = to_aware_utc(window_start_utc)
    we = to_aware_utc(window_end_utc)

    # Get ALL observations for this store up to window end
    all_obs = (
        session.query(StoreStatus)
        .filter(StoreStatus.store_id == store_id,
                StoreStatus.timestamp_utc <= we)
        .order_by(StoreStatus.timestamp_utc)
        .all()
    )
    
    if not all_obs:
        # no obs
        print(f"Warning: No observations found for store {store_id}")
        return [(ws, we, "inactive")]
    
    # Find the last observation before or at window start
    prev_obs = None
    window_obs = []
    for obs in all_obs:
        obs_time = to_aware_utc(obs.timestamp_utc)
        if obs_time <= ws:
            prev_obs = obs
        elif obs_time <= we:
            window_obs.append(obs)
    
    segments = []
    
    # Determine initial status and starting point
    if prev_obs:
        # Use status from the last observation before window start
        current_status = prev_obs.status
    elif window_obs:
        # Extrapolate status from the first observation in the window
        current_status = window_obs[0].status
    else:
        # Use status from the last observation
        current_status = all_obs[-1].status
    
    current_time = ws
    
    # Process observations in the window
    for obs in window_obs:
        obs_time = to_aware_utc(obs.timestamp_utc)
        
        # If the status changes, add a segment for the previous status
        if obs.status != current_status:
            segments.append((current_time, obs_time, current_status))
            current_status = obs.status
            current_time = obs_time
    
    # Add the final segment
    if current_time < we:
        segments.append((current_time, we, current_status))
    
    return segments
    
def _accumulate_overlaps(
        status_segments: List[Tuple[datetime, datetime, str]],
        bh_intervals_utc: List[Tuple[datetime, datetime]],
) -> Tuple[float, float]:
    """ Return (uptime_sec, downtime_sec) inside business_hours intervals"""
    up = 0.0
    down = 0.0

    for seg_s, seg_e, state in status_segments:
        for bh_s, bh_e in bh_intervals_utc:
            s = max(seg_s, bh_s)
            e = min(seg_e, bh_e)
            if s >= e:
                continue
            dur = (e - s).total_seconds()
            if state == "active":
                up += dur
            else: 
                down += dur
    
    return up, down


