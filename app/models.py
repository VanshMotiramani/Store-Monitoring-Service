# models.py
from sqlalchemy import Column, Integer, String, DateTime, Time, Index
from .db import Base
import uuid
from datetime import datetime, timezone

class StoreStatus(Base):
    __tablename__ = "store_status"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime(timezone=True), nullable=False)  # Add timezone=True
    status = Column(String, nullable=False)
    
    # Add composite index for better query performance
    __table_args__ = (
        Index('idx_store_timestamp', 'store_id', 'timestamp_utc'),
    )

class BusinessHours(Base):
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time_local = Column(Time, nullable=False)
    end_time_local = Column(Time, nullable=False)

class StoreTimezone(Base):
    __tablename__ = "store_timezone"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True, nullable=False, unique=True)
    timezone_str = Column(String, nullable=False)

class Report(Base):
    __tablename__ = "reports"

    report_id = Column(String, index=True, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="Running")
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))