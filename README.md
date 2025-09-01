# Store Monitoring Service

A backend service that monitors restaurant online/offline status during business hours and generates comprehensive uptime/downtime reports.

## Problem Statement

Monitor several restaurants in the US to track if stores are online during business hours. The system polls each store roughly every hour and needs to:
- Handle multiple timezones
- Respect business hours
- Interpolate data between observations
- Generate historical reports


## Features

- **Timezone-aware calculations**: Handles stores across different US timezones
- **Business hours support**: Only counts uptime/downtime during operating hours
- **Data interpolation**: Intelligently fills gaps between observations
- **Async processing**: Non-blocking report generation
- **Parallel processing**: Optimized for handling thousands of stores
- **Robust error handling**: Continues processing even if individual stores fail

## Tech Stack

- **Backend Framework**: FastAPI (Python 3.8+)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Async Processing**: Threading with ThreadPoolExecutor
- **Timezone Handling**: pytz
- **Data Processing**: pandas
- **Testing**: pytest

## Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL 12 or higher
- pip package manager

### Setup Steps

1. **Clone the repository**
    ```bash
       git clone https://github.com/yourusername/store-monitoring.git
       cd store-monitoring
    ```
2. **Create virtual environment**
    ```bash
        python -m venv venv
        source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3. **Install dependencies**
    ```bash
        pip install -r requirements.txt
     ```
4. **Set up PostgreSQL Database**
    ```bash
        # Create database
        createdb store_monitoring
        # Or using psql
        psql -U postgres -c "CREATE DATABASE store_monitoring;"
    ```
5. **Configure environment variables**
    ```bash
        cp .env.example .env
        # Edit .env with your database credentials
    ```
6. **Intialize database variables**
    ```bash
        python -c "from app.db import Base, engine; Base.metadata.create_all(bind=engine)"
    ```
7. **Load Sample Data**
    ```bash
        # Download and extract data files to data/ directory
        # Then run ETL
        python etl.py
    ```
##  Usage

### Starting the Server
    ```bash 
        # Development mode with auto-reload
        uvicorn app.main:app --reload --port 8000
        # Production mode
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    ```

### API Documentation

Once the server is running access:
    • Swagger UI: http://localhost:8000/docs
    • ReDoc: http://localhost:8000/redoc

### Generating Reports

1. **Trigger a new report**
    ```bash
    curl -X POST http://localhost:8000/api/trigger_report
    ```

    **Response**
    ```bash
    {
        "report_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    ```
2. **Check report status**
    ```bash
    curl http://localhost:8000/api/get_report/{report_id}
    ```

    **Response**
    ```bash
    {
        "status": "Running"
    }
    ```

    Response (if complete): CSV file download

### Using Python Client
    ```bash
        import requests
        import time
    ```
### Trigger report
    ```bash
        response = requests.post("http://localhost:8000/api/trigger_report")
        report_id = response.json()["report_id"]
    ```
### Poll for completion
    ```bash
        while True:
            response = requests.get(f"http://localhost:8000/api/get_report/{report_id}")
            if response.headers.get('content-type', '').startswith('text/csv'):
                # Save the report
                with open(f"report_{report_id}.csv", "wb") as f:
                    f.write(response.content)
                break
            time.sleep(5)
    ```

## API Endpoints

### POST /api/trigger_report
Triggers asynchronous report generation for all stores.

**Request:**
```bash
    POST /api/trigger_report
    Content-Type: application/json
```

**Response:**
```bash
    {
        "report_id": "123e4567-e89b-12d3-a456-426614174000"
    }
```

### GET /api/get_report/{report_id}
Retrieves report status or downloads the completed report.

**Request:**
```bash
    GET /api/get_report/123e4567-e89b-12d3-a456-426614174000
```

**Response:**
if running:
    ```bash
        {
            "status": "Running"
        }
    ```
If complete:
    • Content-Type: text/csv
    • Body: CSV file with report data
If failed:
    ```bash
        {
            "status": "Failed: Error message"
        }
    ```

## Report Output Schema
The generated CSV contains the following columns:

| Column             | Type    | Description                                     | Range       |
|--------------------|---------|-------------------------------------------------|-------------|
| store_id           | string  | Unique store identifier                         | -           |
| uptime_last_hour   | integer | Minutes the store was active in the last hour   | 0-60        |
| uptime_last_day    | float   | Hours the store was active in the last day      | 0.00-24 00  |
| uptime_last_week   | float   | Hours the store was active in the last week     | 0.00-168.00 |
| downtime_last_hour | integer | Minutes the store was inactive in the last hour | 0-60        |
| downtime_last_day  | float   | Hours the store was inactive in the last day    | 0.00-24.00  |
| downtime_last_week | float   | Hours the store was inactive in the last week   | 0.00-168.00 |

## Sample output:
    ```bash
        store_id,uptime_last_hour,uptime_last_day,uptime_last_week,downtime_last_hour,downtime_last_day,downtime_last_week
        00017c6a-7a77-4a95-bb2d-40647868aff6,60,8.53,58.77,0,1.97,16.73
        000bba84-20af-4a8b-b68a-368922cc6ad1,0,0.0,0.0,60,24.0,168.0
        003222af-0b64-4f8c-b5c3-d2dc24636f02,60,11.25,78.75,0,0.0,0.0
    ```

## Project Structure:

store-monitoring/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── db.py                   # Database connection and session management
│   ├── models.py               # SQLAlchemy ORM models
│   ├── api/
│   │   └── routes.py           # API endpoint definitions
│   └── core/
|       ├── etl.py              # Data ingestion and transformatin script
│       ├── time_utils.py       # Timezone conversion utilities
│       ├── uptime.py           # Uptime/downtime calculation logic
│       └── report_generator.py # Async report generation
├── data/                       # CSV data files directory
│   ├── store_status.csv        # Hourly poll data
│   ├── menu_hours.csv          # Business hours data
│   └── timezones.csv           # Store timezone data
├── tests/                      # Test suite
│   ├── test_metrics.py         # Metrics calculation tests
│   └── test_time_utils.py      # Timezone utility tests
├── reports/                    # Generated reports directory  
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
└── README.md                   # This file

## Data Processing Logic

### Business Hours Handling
    • Stores without defined hours are assumed to be 24/7
    • Business hours are converted from local time to UTC for calculations
    • Overnight hours (e.g., 10 PM - 2 AM) are handled correctly

### Status Interpolation
    • If no data exists before a time window, the first observation within the window is extrapolated backwards
    • Status is assumed to remain constant between observations
    • Missing data defaults to "inactive" status

### Timezone Conversion
    • All calculations are performed in UTC
    • Local business hours are converted to UTC for each store's timezone
    • Daylight Saving Time is handled automatically

### Performance Metrics

Based on testing with sample data:

    • Dataset size: 3,678 stores
    • Processing time: ~2 minutes
    • Memory usage: < 500MB
    • Concurrent processing: 10 parallel workers by default

### Testing

Run Unit Tests
```bash
    # Run all tests
    pytest
    # Run with coverage report
    pytest --cov=app tests/
    # Run specific test file
    pytest tests/test_metrics.py -v
```

### Integration Testing:
```bash
    # Test the complete workflow
    python test_api.py
    # Validate generated reports
    python validate_results.py report_file.csv
```
### Configuration
Environment variables (set in .env):

| Variable    | Description                     | Default        
|-------------|---------------------------------|-----------------
| ENV         | Environment (dev/prod)          | dev              
| DB_USER     | PostgreSQL username             | postgres         
| DB_PASSWORD | PostgreSQL password             | -                
| DB_NAME     | Database name                   | store_monitoring 
| DB_HOST     | Database host                   | localhost        
| DB_PORT     | Database port                   | 5432             
| REPORTS_DIR | Directory for generated reports | reports          
| MAX_WORKERS | Maximum parallel workers        | 10               

### Troubleshooting
#### Common Issues
 1. Database connection errors
    • Verify PostgreSQL is running: pg_isready
    • Check credentials in .env
    • Ensure database exists: psql -U postgres -l

 2. Report generation timeout
    • Check server logs for errors
    • Verify data is loaded: python -c "from app.db import SessionLocal;     from app.models \ import StoreStatus; db = SessionLocal();            print(db.query(StoreStatus).count())"
    • Increase MAX_WORKERS for faster processing

 3. Memory issues with large datasets
    • Reduce MAX_WORKERS
    • Process in smaller batches
    • Increase system memory

## Future Improvements
 1. Performance Optimizations
    • Implement caching with Redis for frequently accessed data
    • Add database indexes for faster queries
    • Use connection pooling for better resource management

 2. Feature Enhancements
    • Support custom date ranges for reports
    • Add real-time monitoring with WebSockets
    • Implement incremental updates instead of full recalculation
    • Add data visualization dashboard

 3. Scalability
    • Migrate to Celery for distributed task processing
    • Implement horizontal scaling with Kubernetes
    • Add message queue (RabbitMQ/Kafka) for async processing
 4. Monitoring & Observability
    • Add Prometheus metrics
    • Implement structured logging
    • Create Grafana dashboards
    • Add health check endpoints

5. Data Quality
    • Implement data validation pipelines
    • Add anomaly detection for unusual patterns
    • Create data quality reports

### Coding Standards
 1. Follow PEP 8 style guide
 2. Add type hints for all functions
 3. Write docstrings for modules, classes, and functions
 4. Maintain test coverage above 80%

### License
This project is part of a technical assessment for Loop.

Note: This is a technical assessment project demonstrating backend development skills including data processing, API design, timezone handling, and asynchronous programming.