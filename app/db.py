#db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings


db_url = settings.get_db_url()
connect_args = {}
engine = create_engine(db_url, echo=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    """ FastAPI DB Session """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()