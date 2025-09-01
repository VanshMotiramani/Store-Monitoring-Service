import datetime
import pytz
import pytest
from app.core import time_utils


def t(h, m=0):
    """Helper to create datetime.time"""
    return datetime.time(h, m)


def test_basic_conversion():
    # May 1, 2025 = Thursday (weekday = 3)
    bh_map = {
        3: [(t(9, 0), t(17, 0))]  # Thursday: 9 AM - 5 PM
    }
    start = datetime.datetime(2025, 5, 1, 0, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2025, 5, 1, 23, 59, tzinfo=pytz.UTC)

    intervals = time_utils.expand_business_hours_to_utc(
        "America/Chicago", bh_map, start, end
    )
    assert len(intervals) == 1

    s, e = intervals[0]
    # 9am Chicago = 14:00 UTC
    assert s == datetime.datetime(2025, 5, 1, 14, 0, tzinfo=pytz.UTC)
    # 5pm Chicago = 22:00 UTC
    assert e == datetime.datetime(2025, 5, 1, 22, 0, tzinfo=pytz.UTC)


def test_clipping_window():
    bh_map = {
        3: [(t(9, 0), t(17, 0))]  # Thursday
    }
    start = datetime.datetime(2025, 5, 1, 15, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2025, 5, 1, 18, 0, tzinfo=pytz.UTC)

    intervals = time_utils.expand_business_hours_to_utc(
        "America/Chicago", bh_map, start, end
    )
    assert len(intervals) == 1

    s, e = intervals[0]
    # Should clip to provided window
    assert s == start
    assert e == end


def test_overnight_hours():
    bh_map = {
        4: [(t(22, 0), t(6, 0))]  # Friday: 10 PM – Saturday 6 AM
    }
    start = datetime.datetime(2025, 5, 2, 0, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2025, 5, 3, 23, 59, tzinfo=pytz.UTC)

    intervals = time_utils.expand_business_hours_to_utc(
        "America/Chicago", bh_map, start, end
    )

    # Implementation keeps overnight as one interval
    assert len(intervals) == 1
    s, e = intervals[0]
    assert s.tzinfo == pytz.UTC
    assert e.tzinfo == pytz.UTC

def test_24x7_hours():
    bh_map = {
        1: [(t(0, 0), t(0, 0))]  # Tuesday: open 24h (interpreted as 00:00–23:59)
    }
    start = datetime.datetime(2025, 5, 6, 0, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2025, 5, 6, 23, 59, tzinfo=pytz.UTC)

    intervals = time_utils.expand_business_hours_to_utc(
        "America/Chicago", bh_map, start, end
    )
    assert len(intervals) == 1

    s, e = intervals[0]

    # Chicago 00:00 local == 05:00 UTC
    assert s == datetime.datetime(2025, 5, 6, 5, 0, tzinfo=pytz.UTC)
    # Implementation clips to same-day 23:59 UTC
    assert e == datetime.datetime(2025, 5, 6, 23, 59, tzinfo=pytz.UTC)


def test_multiple_days():
    bh_map = {
        0: [(t(9, 0), t(12, 0))],   # Monday: 9 AM - 12 PM
        1: [(t(13, 0), t(18, 0))]   # Tuesday: 1 PM - 6 PM
    }
    start = datetime.datetime(2025, 5, 5, 0, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2025, 5, 6, 23, 59, tzinfo=pytz.UTC)

    intervals = time_utils.expand_business_hours_to_utc(
        "America/Chicago", bh_map, start, end
    )
    # Should span across two days
    assert len(intervals) == 2

    # Monday slot check
    mon_start, mon_end = intervals[0]
    assert mon_start.hour == 14  # 9 AM CDT = 14 UTC
    assert mon_end.hour == 17    # 12 PM CDT = 17 UTC

    # Tuesday slot check
    tue_start, tue_end = intervals[1]
    assert tue_start.hour == 18  # 1 PM CDT = 18 UTC
    assert tue_end.hour == 23    # 6 PM CDT = 23 UTC
