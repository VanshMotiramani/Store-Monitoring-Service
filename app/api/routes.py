# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.core.report_generator import generate_report_async
from app.models import Report
import os

router = APIRouter()

@router.post("/trigger_report")
async def trigger_report(db: Session = Depends(get_db)):
    """Trigger report generation"""
    # Create report entry
    report = Report()  # Let the model generate the UUID
    db.add(report)
    db.commit()
    db.refresh(report)
    
    # Trigger async report generation
    generate_report_async(report.report_id)
    
    return {"report_id": report.report_id}

@router.get("/get_report/{report_id}")
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """Get report status or download"""
    report = db.query(Report).filter(Report.report_id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report.status == "Running":
        return {"status": "Running"}
    
    if report.status == "Complete" and report.file_path:
        # Check if file exists
        if not os.path.exists(report.file_path):
            raise HTTPException(status_code=404, detail="Report file not found")
        
        # Return CSV file
        return FileResponse(
            path=report.file_path,
            media_type="text/csv",
            filename=f"report_{report_id}.csv",
            headers={
                "Content-Disposition": f"attachment; filename=report_{report_id}.csv"
            }
        )
    
    # Report failed or in unknown state
    return {"status": report.status}