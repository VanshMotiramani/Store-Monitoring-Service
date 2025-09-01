# test_api.py
import requests
import time
import json

# Test API is running
response = requests.get("http://localhost:8000/")
print("API Status:", response.json())

# Trigger report generation
response = requests.post("http://localhost:8000/api/trigger_report")
report_data = response.json()
report_id = report_data["report_id"]
print(f"Report triggered: {report_id}")

# Poll for report completion
max_attempts = 60  # Try for up to 5 minutes
attempt = 0

while attempt < max_attempts:
    response = requests.get(f"http://localhost:8000/api/get_report/{report_id}")
    
    # Check if response is CSV (completed report)
    content_type = response.headers.get('content-type', '')
    
    if 'text/csv' in content_type or 'application/octet-stream' in content_type:
        # Report is ready, save it
        filename = f"test_report_{report_id}.csv"
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"Report downloaded successfully! Saved as: {filename}")
        
        # Show first few lines of the report
        with open(filename, "r") as f:
            lines = f.readlines()[:5]
            print("\nFirst few lines of the report:")
            for line in lines:
                print(line.strip())
        break
    else:
        # Try to parse as JSON (status response)
        try:
            status = response.json()
            print(f"Report status: {status}")
            
            if status.get("status") == "Complete":
                print("Report marked as complete but no file received")
                break
            elif "Failed" in status.get("status", ""):
                print("Report generation failed!")
                break
        except json.JSONDecodeError:
            print(f"Unexpected response: {response.text[:100]}")
            break
    
    attempt += 1
    time.sleep(5)  # Wait 5 seconds before checking again

if attempt >= max_attempts:
    print("Report generation timed out!")