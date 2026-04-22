import os
import json
import gspread
from garminconnect import Garmin
from datetime import datetime, timedelta
from dotenv import load_dotenv
import garth

# Load environment variables from .env file if it exists
load_dotenv()

# 1. Authenticate with Garmin using environment variables or session cache
garmin_email = os.environ.get("GARMIN_EMAIL")
garmin_pass = os.environ.get("GARMIN_PASSWORD")

session_dir = '~/.garminconnect'
client = Garmin(garmin_email, garmin_pass)

def sync_data_with_dynamic_headers(worksheet, data_list):
    """Syncs a list of dictionaries to a gspread worksheet with dynamic headers."""
    if not data_list:
        return
        
    # Extract all unique keys
    all_keys = set()
    for item in data_list:
        all_keys.update(item.keys())
    
    # Sort keys to keep them consistent
    new_keys = list(all_keys)
    
    # Get existing headers
    try:
        headers = worksheet.row_values(1)
    except Exception:
        headers = []
        
    # If no headers, write them
    if not headers:
        headers = new_keys
        worksheet.append_row(headers)
        print(f"Created headers: {headers}")
    else:
        # Find missing keys
        missing_keys = [k for k in new_keys if k not in headers]
        if missing_keys:
            headers.extend(missing_keys)
            # Update header row
            worksheet.update([headers], "A1")
            print(f"Added new headers: {missing_keys}")
            
    # Map data to headers
    rows_to_append = []
    for item in data_list:
        row = []
        for header in headers:
            val = item.get(header, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row.append(val)
        rows_to_append.append(row)
        
    worksheet.append_rows(rows_to_append)
    print(f"Appended {len(rows_to_append)} rows.")

try:
    # login will use tokens from session_dir if valid, or use credentials and save tokens
    client.login(tokenstore=session_dir)
    print("Successfully logged in to Garmin.")
except Exception as e:
    print(f"Critical failure during Garmin login: {e}")
    raise e

# Fetch some data (example: yesterday's stats and activities)
today = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Fetching data for {today}...")

# 1. Fetch Daily Summary
try:
    summary = client.get_user_summary(today)
    print(f"Fetched daily summary for {today}")
    # Add Date to the summary dict so it appears as a column
    summary['Date'] = today
except Exception as e:
    print(f"Error fetching user summary: {e}")
    summary = {'Date': today, 'error': str(e)}

# 2. Fetch Activities
try:
    activities = client.get_activities_by_date(today, today)
    print(f"Fetched {len(activities)} activities.")
    # Add Date to each activity
    for act in activities:
        act['Date'] = today
except Exception as e:
    print(f"Error fetching activities: {e}")
    activities = []

# 3. Authenticate with Google Sheets using the JSON secret
google_creds_json = os.environ.get("GSPREAD_CREDENTIALS")
if google_creds_json:
    creds_dict = json.loads(google_creds_json)
    gc = gspread.service_account_from_dict(creds_dict)
else:
    # Fallback to local file for testing
    local_key_path = 'secrets/garmin-logger-key.json'
    if os.path.exists(local_key_path):
        gc = gspread.service_account(filename=local_key_path)
    else:
        raise Exception("Google credentials not found in environment or local file.")

# 4. Update the Sheets
sheet_name = 'Garmin Log'
try:
    sh = gc.open(sheet_name)
    
    # Handle Daily Stats sheet
    try:
        ws_daily = sh.worksheet("Daily")
    except gspread.WorksheetNotFound:
        ws_daily = sh.add_worksheet(title="Daily", rows=100, cols=50)
        print("Created 'Daily' worksheet.")
        
    sync_data_with_dynamic_headers(ws_daily, [summary])
    print(f"Synced daily stats for {today}")

    # Handle Activities sheet
    try:
        ws_activities = sh.worksheet("Activities")
    except gspread.WorksheetNotFound:
        ws_activities = sh.add_worksheet(title="Activities", rows=100, cols=50)
        print("Created 'Activities' worksheet.")

    sync_data_with_dynamic_headers(ws_activities, activities)
    print(f"Synced activities for {today}")

except gspread.SpreadsheetNotFound:
    print(f"Error: Spreadsheet '{sheet_name}' not found. Please make sure you created it and shared it with the service account.")
except Exception as e:
    print(f"Error updating sheet: {e}")
