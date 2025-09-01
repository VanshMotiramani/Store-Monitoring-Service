#config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    """ settings loader"""
    env: str = os.getenv("ENV", "dev")

    database_url: str = os.getenv("DATABASE_URL")
    db_user: str = os.getenv("DB_USER")
    db_pass: str = os.getenv("DB_PASSWORD")
    db_name: str = os.getenv("DB_NAME")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: str = os.getenv("DB_PORT", "5433")

    report_generation_timeout: int = int(os.getenv("REPORT_TIMEOUT", "300"))
    max_parallel_workers: int = int(os.getenv("MAX_WORKERS", "10"))

    reports_dir: str = os.getenv("REPORTS_DIR", "reports")

    def get_db_url(self):
        if self.database_url:
            return self.database_url
        return f"postgresql+psycopg2://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def is_production(self) -> bool:
        return self.env.lower() in ("prod", "production")
    
    @property
    def is_development(self) -> bool:
        return self.env.lower() in {"env", "development"}
    
settings = Settings()