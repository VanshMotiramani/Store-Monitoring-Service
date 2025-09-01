#main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.routes import router as api_router
from .db import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from . import models

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting..")
    logging.info("Create tables")
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables ready")
    yield
    logger.info("Shutting..")

app = FastAPI(
    title="Store Monitoring Service",
    version="0.1.0",
    description=(
        "APIs for ingesting store data and generating uptime/downtime report"
        "Monitor store status online/offline during business hours"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api", tags=["core"])


@app.get("/")
async def root():
    return {
        "message": "Store Monitoring API running",
        "version": "0.1.0",
        "endpoints": {
            "trigger_report": "/api/trigger_report",
            "get_report": "/api/get_report/{report_id}",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy"} 