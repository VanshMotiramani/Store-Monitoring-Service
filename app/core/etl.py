#etl.py
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import StoreStatus, BusinessHours, StoreTimezone
from app.db import engine
import pytz

#Extract files
def load_csv(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)

def truncate_tables(session: Session):
    """ Truncate all target tables before reload """
    for model in [StoreStatus, BusinessHours, StoreTimezone]:
        table = model.__table__
        session.execute(table.delete())
    session.commit()
    print("Tables truncated")

def bulk_insert_in_batches(session: Session, records: list, batch_size: int = 500):
    """Insert records in batches to avoid parameter limits."""
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        session.bulk_save_objects(batch)
        session.commit()

# Transform & Load
def ingest_store_status(session: Session, df: pd.DataFrame):
    required_cols = {"store_id", "timestamp_utc", "status"}
    if not required_cols.issubset(df.columns):
        raise ValueError("store_status missing required columns")
    
    df = df.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df["status"] = df["status"].str.lower().str.strip()
    df = df[df["status"].isin(["active", "inactive"])]
    df.dropna(subset=["timestamp_utc"], inplace=True)

    records = [StoreStatus(**row) for row in df.to_dict(orient="records")]
    bulk_insert_in_batches(session, records, batch_size=500)
    print(f"Loaded {len(df)} rows into store_status")

def ingest_business_hours(session: Session, df: pd.DataFrame):
    required_cols = {"store_id", "dayOfWeek", "start_time_local", "end_time_local"}
    if not required_cols.issubset(df.columns):
        raise ValueError("menu_hours.csv missing required columns")
    
    df = df.copy()
    df["dayOfWeek"] = df["dayOfWeek"].astype(int)
    df["start_time_local"] = pd.to_datetime(df["start_time_local"], format="%H:%M:%S", errors="coerce").dt.time
    df["end_time_local"] = pd.to_datetime(df["end_time_local"], format="%H:%M:%S", errors="coerce").dt.time
    df.dropna(inplace=True)

    df.rename(columns={"dayOfWeek": "day_of_week"}, inplace=True)

    records = [BusinessHours(**row) for row in df.to_dict(orient="records")]
    bulk_insert_in_batches(session, records, batch_size=500)
    print(f"Loaded {len(df)} rows into business_hours")

def ingest_store_timezone(session: Session, df: pd.DataFrame):
    required_cols = {"store_id", "timezone_str"}
    if not required_cols.issubset(df.columns):
        raise ValueError("timezone.csv missing required columns")

    df = df.copy()
    df["timezone_str"] = df["timezone_str"].fillna("America/Chicago").str.strip()
    df.loc[~df["timezone_str"].isin(pytz.all_timezones), "timezone_str"] = "America/Chicago"

    records = [StoreTimezone(**row) for row in df.to_dict(orient="records")]
    bulk_insert_in_batches(session, records, batch_size=500)
    print(f"Loaded {len(df)} rows into store_timezone")

def run_etl():
    store_status_df = load_csv('data/store_status.csv')
    business_hours_df = load_csv('data/menu_hours.csv')
    timezone_df = load_csv('data/timezones.csv')

    
    print("Store Status Sample:", store_status_df.head())
    print("Business Hours Sample:", business_hours_df.head())
    print("Timezone Sample:", timezone_df.head())


    with Session(engine) as session:
        truncate_tables(session)
        ingest_store_status(session, store_status_df)
        ingest_business_hours(session, business_hours_df)
        ingest_store_timezone(session, timezone_df)

if __name__ == "__main__":
    run_etl()