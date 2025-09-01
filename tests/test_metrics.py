# tests/test_metrics.py
import datetime
import pytz
import pytest
from sqlalchemy.orm import Session
from app.db import engine
from sqlalchemy import text

from app.core.uptime import metrics_for_store, get_dataset_now
from app.core.time_utils import to_aware_utc
from app.models import StoreStatus, BusinessHours, StoreTimezone

UTC = pytz.UTC


@pytest.fixture()
def db_session():
    """
    Provide a SQLAlchemy Session bound to a connection with an outer
    transaction that will be rolled back at the end of the test.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)

    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()

def _utc(dt: datetime.datetime) -> datetime.datetime:
    # Instead of localizing naive as UTC (shifts incorrectly),
    # always force UTC meaning.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def _insert_status(session: Session, store_id: str, ts: datetime.datetime, status: str):
    # Ensure the timestamp is properly UTC
    if ts.tzinfo is None:
        ts = pytz.UTC.localize(ts)
    else:
        ts = ts.astimezone(pytz.UTC)
        
    session.add(StoreStatus(store_id=store_id, timestamp_utc=ts, status=status))
    session.flush()


def _insert_bh(session: Session, store_id: str, day: int, start_h: int, start_m: int, end_h: int, end_m: int):
    session.add(BusinessHours(store_id=store_id, day_of_week=day,
                              start_time_local=datetime.time(start_h, start_m),
                              end_time_local=datetime.time(end_h, end_m)))
    session.flush()


def _insert_tz(session: Session, store_id: str, tz_str: str):
    session.add(StoreTimezone(store_id=store_id, timezone_str=tz_str))
    session.flush()


def test_no_records_full_downtime(db_session):
    """Case 1: No records => all downtime"""
    store_id = "no_records_1"
    now = _utc(datetime.datetime(2025, 5, 6, 12, 0))

    res = metrics_for_store(db_session, store_id, now)

    assert res["uptime_last_hour"] == 0
    assert res["downtime_last_hour"] == 60
    assert res["uptime_last_day"] == 0.00
    assert res["downtime_last_day"] == 24.00
    assert res["uptime_last_week"] == 0.00
    assert res["downtime_last_week"] == 168.00


def test_always_active_store_full_uptime(db_session):
    """Case 2: Single previous 'active' observation leading to full uptime coverage"""
    store_id = "always_active"
    now = _utc(datetime.datetime(2025, 5, 6, 12, 0))
    _insert_status(db_session, store_id, now - datetime.timedelta(days=1), "active")
    db_session.commit()

    res = metrics_for_store(db_session, store_id, now)

    assert res["uptime_last_hour"] == 60
    assert res["downtime_last_hour"] == 0
    assert res["uptime_last_day"] == 24.00
    assert res["downtime_last_day"] == 0.00
    assert res["uptime_last_week"] == 168.00
    assert res["downtime_last_week"] == 0.00


def test_always_inactive_store_full_downtime(db_session):
    """Case 3: Single previous 'inactive' observation leading to full downtime coverage"""
    store_id = "always_inactive"
    now = _utc(datetime.datetime(2025, 5, 6, 12, 0))
    _insert_status(db_session, store_id, now - datetime.timedelta(days=1), "inactive")
    db_session.commit()

    res = metrics_for_store(db_session, store_id, now)

    assert res["uptime_last_hour"] == 0
    assert res["downtime_last_hour"] == 60
    assert res["uptime_last_day"] == 0.00
    assert res["downtime_last_day"] == 24.00
    assert res["uptime_last_week"] == 0.00
    assert res["downtime_last_week"] == 168.00


def test_mixed_last_hour_30_30_split(db_session):
    """Case 4: Mixed statuses in last hour produce 30/30 minute split"""
    store_id = "mixed_hour"
    now = pytz.UTC.localize(datetime.datetime(2025, 5, 6, 12, 0))

    _insert_status(db_session, store_id, 
                   pytz.UTC.localize(datetime.datetime(2025, 5, 6, 11, 0)), 
                   "active")
    _insert_status(db_session, store_id, 
                   pytz.UTC.localize(datetime.datetime(2025, 5, 6, 11, 30)), 
                   "inactive")
    db_session.commit()

    res = metrics_for_store(db_session, store_id, now)

    assert res["uptime_last_hour"] == 30
    assert res["downtime_last_hour"] == 30


def test_business_hours_clipping(db_session):
    """Case 5: Business hours 9-17 local should clip the day window to 8 hours"""
    store_id = "bh_clip"
    now = _utc(datetime.datetime(2025, 5, 6, 12, 0))

    _insert_tz(db_session, store_id, "America/Chicago")
    _insert_bh(db_session, store_id, 0, 9, 0, 17, 0)  # Monday
    _insert_bh(db_session, store_id, 1, 9, 0, 17, 0)  # Tuesday
    _insert_status(db_session, store_id, now - datetime.timedelta(days=1), "active")
    db_session.commit()

    res = metrics_for_store(db_session, store_id, now)

    assert res["uptime_last_day"] == 8.00
    assert res["downtime_last_day"] == 0.00

def test_business_hours_default_24x7(db_session):
    """Case 8: Missing business hours => treated as 24x7"""
    import uuid
    store_id = f"default_24x7_{uuid.uuid4().hex[:8]}"  # Unique store ID
    now = pytz.UTC.localize(datetime.datetime(2025, 5, 6, 12, 0))
    
    # Insert an active status 2 hours before now
    two_hours_ago = pytz.UTC.localize(datetime.datetime(2025, 5, 6, 10, 0))
    _insert_status(db_session, store_id, two_hours_ago, "active")
    db_session.commit()

    # Debug
    print("\n=== DEBUG test_business_hours_default_24x7 ===")
    
    res = metrics_for_store(db_session, store_id, now)
    print(f"Results: {res}")

    assert res["uptime_last_day"] == 24.00
    assert res["downtime_last_day"] == 0.00

def test_float_serialization_day_week(db_session):
    """Case 9: Ensure day/week values are floats rounded to two decimals"""
    store_id = "float_fmt"
    now = _utc(datetime.datetime(2025, 5, 6, 12, 0))

    _insert_status(db_session, store_id, now - datetime.timedelta(days=1), "active")
    _insert_bh(db_session, store_id, 1, 0, 0, 0, 0)  # full-day
    db_session.commit()

    res = metrics_for_store(db_session, store_id, now)

    # values should be floats with two decimals
    for key in ["uptime_last_day", "downtime_last_day",
                "uptime_last_week", "downtime_last_week"]:
        assert isinstance(res[key], float)
        assert round(res[key], 2) == res[key]

