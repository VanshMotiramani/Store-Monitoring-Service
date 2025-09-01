# app/core/report_generator.py

import csv
import os
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.config import settings
from app.core.uptime import get_dataset_now, metrics_for_store
from app.db import SessionLocal
from app.models import Report, StoreStatus
import logging

logger = logging.getLogger(__name__)

def generate_report_async(report_id: str):
    """Generate report asynchronously"""
    logger.info(f"Starting async report generation for {report_id}")
    thread = threading.Thread(target=generate_report_optimized, args=(report_id,))
    thread.daemon = True
    thread.start()
    logger.info(f"Report generation thread started for {report_id}")

def generate_report(report_id: str):
    """Generate report synchronously (simple version)"""
    db = SessionLocal()
    
    try:
        # Get all unique store IDs
        store_ids = db.query(StoreStatus.store_id).distinct().all()
        store_ids = [s[0] for s in store_ids]
        
        # Get current timestamp from dataset
        now = get_dataset_now(db)
        
        # Generate metrics for each store
        results = []
        total_stores = len(store_ids)
        
        for idx, store_id in enumerate(store_ids):
            try:
                print(f"Processing store {idx + 1}/{total_stores}: {store_id}")
                metrics = metrics_for_store(db, store_id, now)
                results.append({
                    "store_id": store_id,
                    "uptime_last_hour": metrics["uptime_last_hour"],
                    "uptime_last_day": metrics["uptime_last_day"],
                    "uptime_last_week": metrics["uptime_last_week"],
                    "downtime_last_hour": metrics["downtime_last_hour"],
                    "downtime_last_day": metrics["downtime_last_day"],
                    "downtime_last_week": metrics["downtime_last_week"]
                })
            except Exception as e:
                print(f"Error processing store {store_id}: {e}")
                continue
        
        # Write to CSV using configured directory
        output_dir = settings.reports_dir
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{report_id}.csv")
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "store_id", "uptime_last_hour", "uptime_last_day",
                "uptime_last_week", "downtime_last_hour", 
                "downtime_last_day", "downtime_last_week"
            ])
            writer.writeheader()
            writer.writerows(results)
        
        # Update report status
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if report:
            report.status = "Complete"
            report.file_path = file_path
            db.commit()
            print(f"Report {report_id} completed successfully. Processed {len(results)} stores.")
        
    except Exception as e:
        print(f"Report generation failed: {e}")
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if report:
            report.status = f"Failed: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()


def generate_report_optimized(report_id: str):
    """Generate report using parallel processing"""
    db = SessionLocal()
    
    try:
        # Get all unique store IDs
        store_ids = db.query(StoreStatus.store_id).distinct().all()
        store_ids = [s[0] for s in store_ids]
        
        # Get current timestamp from dataset
        now = get_dataset_now(db)
        db.close()  # Close before parallel processing
        
        print(f"Starting optimized report generation for {len(store_ids)} stores")
        
        results = []
        failed_stores = []
        
        # Use configured max workers
        with ThreadPoolExecutor(max_workers=settings.max_parallel_workers) as executor:
            # Submit all tasks
            future_to_store = {
                executor.submit(process_store, store_id, now): store_id
                for store_id in store_ids
            }
            
            # Process completed tasks
            for future in as_completed(future_to_store):
                store_id = future_to_store[future]
                try:
                    metrics = future.result()
                    results.append({
                        "store_id": store_id,
                        "uptime_last_hour": metrics["uptime_last_hour"],
                        "uptime_last_day": metrics["uptime_last_day"],
                        "uptime_last_week": metrics["uptime_last_week"],
                        "downtime_last_hour": metrics["downtime_last_hour"],
                        "downtime_last_day": metrics["downtime_last_day"],
                        "downtime_last_week": metrics["downtime_last_week"]
                    })
                except Exception as e:
                    print(f"Error processing store {store_id}: {e}")
                    failed_stores.append(store_id)
        
        # Sort results by store_id
        results.sort(key=lambda x: x["store_id"])
        
        # Write to CSV using configured directory
        output_dir = settings.reports_dir
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{report_id}.csv")
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "store_id", "uptime_last_hour", "uptime_last_day",
                "uptime_last_week", "downtime_last_hour", 
                "downtime_last_day", "downtime_last_week"
            ])
            writer.writeheader()
            writer.writerows(results)
        
        # Update report status
        db = SessionLocal()
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if report:
            report.status = "Complete"
            report.file_path = file_path
            db.commit()
            
            print(f"Report {report_id} completed successfully.")
            print(f"Processed: {len(results)} stores successfully, {len(failed_stores)} failed")
            if failed_stores:
                print(f"Failed stores (first 10): {failed_stores[:10]}")
        
    except Exception as e:
        print(f"Report generation failed: {e}")
        if not db:
            db = SessionLocal()
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if report:
            report.status = f"Failed: {str(e)}"
            db.commit()
        raise
    finally:
        if db:
            db.close()


def process_store(store_id: str, now: datetime) -> dict:
    """Process a single store in its own DB session"""
    db = SessionLocal()
    try:
        # Suppress debug prints for production
        os.environ['SUPPRESS_DEBUG'] = '1' if settings.is_production else '0'
        
        return metrics_for_store(db, store_id, now)
    except Exception as e:
        print(f"Error in process_store for {store_id}: {e}")
        raise
    finally:
        db.close()


def get_report_status(report_id: str) -> dict:
    """Get current status of a report"""
    db = SessionLocal()
    try:
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if not report:
            return {"status": "Not Found"}
        
        return {
            "status": report.status,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "file_path": report.file_path if report.status == "Complete" else None
        }
    finally:
        db.close()