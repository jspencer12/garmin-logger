import os
import json
import gspread
from garminconnect import Garmin
from datetime import date, timedelta
from dotenv import load_dotenv
import garth

SPREADSHEET_LOGGING_ENABLED = True

# Load environment variables from .env file if it exists
load_dotenv()

# 1. Authenticate with Garmin using environment variables or session cache
garmin_email = os.environ.get("GARMIN_EMAIL")
garmin_pass = os.environ.get("GARMIN_PASSWORD")

session_dir = '~/.garminconnect'
garmin = Garmin(garmin_email, garmin_pass)

def sync_data_with_dynamic_headers(worksheet, data_list, primary_key=None):
    """Syncs a list of dictionaries to a gspread worksheet with dynamic headers.
    Ensures primary_key is always the first column if specified."""
    if not data_list:
        return
        
    # Extract all unique keys
    all_keys = set()
    for item in data_list:
        all_keys.update(item.keys())
        
    if primary_key and primary_key in all_keys:
        all_keys.remove(primary_key)
        new_keys = [primary_key] + sorted(list(all_keys))
    else:
        new_keys = sorted(list(all_keys))
        
    # Get existing headers
    try:
        headers = worksheet.row_values(1)
    except Exception:
        headers = []
        
    # If no headers, write them
    if not headers:
        headers = new_keys
        worksheet.append_row(headers)
        print(f"Created headers: {headers[:5]}...")
    else:
        # Find missing keys
        missing_keys = [k for k in new_keys if k not in headers]
        if missing_keys:
            headers.extend(missing_keys)
            worksheet.update([headers], "A1")
            print(f"Added new headers: {missing_keys}")
            
        if primary_key and primary_key in headers and headers[0] != primary_key:
            # Move primary_key to front of headers
            idx = headers.index(primary_key)
            headers.pop(idx)
            headers.insert(0, primary_key)
            worksheet.update([headers], "A1")
            print(f"Reordered existing headers to put '{primary_key}' in column A.")
            
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

def aggregate_daily_fetch(client, target_date: str) -> dict:
    """Fetches and aggregates comprehensive daily metrics across multiple Garmin endpoints."""
    summary = {'calendarDate': target_date}
    
    # 1. Core Daily Stats & Body Composition
    try:
        stats = client.get_stats_and_body(target_date)
        if isinstance(stats, dict):
            summary.update(stats)
    except Exception as e:
        print(f"Error fetching daily stats for {target_date}: {e}")
        
    # 2. Sleep Quality & Stages
    try:
        sleep = client.get_sleep_data(target_date) or {}
        sleep_dto = sleep.get("dailySleepDTO", {}) or {}
        sleep_scores = sleep_dto.get("sleepScores", {}) or {}
        overall_score = sleep_scores.get("overall", {}) or {}
        summary.update({
            "sleep_score": overall_score.get("value"),
            "sleep_duration_hrs": round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 2) if sleep_dto.get("sleepTimeSeconds") else None,
            "deep_sleep_hrs": round(sleep_dto.get("deepSleepSeconds", 0) / 3600, 2) if sleep_dto.get("deepSleepSeconds") else None,
            "rem_sleep_hrs": round(sleep_dto.get("remSleepSeconds", 0) / 3600, 2) if sleep_dto.get("remSleepSeconds") else None,
        })
    except Exception as e:
        print(f"Error fetching sleep data for {target_date}: {e}")
        
    # 3. Heart Rate Variability (HRV)
    try:
        hrv = client.get_hrv_data(target_date) or {}
        hrv_summary = hrv.get("hrvSummary", {}) or {}
        summary.update({
            "hrv_last_night_avg": hrv_summary.get("lastNightAvg"),
            "hrv_status": hrv_summary.get("status"),
        })
    except Exception as e:
        print(f"Error fetching HRV for {target_date}: {e}")
        
    # 4. Resting Heart Rate (RHR)
    try:
        rhr = client.get_rhr_day(target_date) or {}
        metrics_map = rhr.get("allMetrics", {}).get("metricsMap", {}) or {}
        rhr_list = metrics_map.get("WELLNESS_RESTING_HEART_RATE", [{}])
        if rhr_list and len(rhr_list) > 0 and isinstance(rhr_list[0], dict):
            summary["resting_heart_rate"] = rhr_list[0].get("value")
    except Exception as e:
        print(f"Error fetching RHR for {target_date}: {e}")
        
    # 5. Body Battery Energy
    try:
        bb = client.get_body_battery(target_date)
        if bb and isinstance(bb, list) and len(bb) > 0 and isinstance(bb[0], dict):
            summary.update({
                "body_battery_max": bb[0].get("highestBodyBatteryValue"),
                "body_battery_min": bb[0].get("lowestBodyBatteryValue"),
                "body_battery_charged": bb[0].get("chargedValue"),
                "body_battery_drained": bb[0].get("drainedValue"),
            })
    except Exception as e:
        print(f"Error fetching Body Battery for {target_date}: {e}")
        
    # 6. Daily Stress Breakdown
    try:
        stress = client.get_all_day_stress(target_date) or {}
        summary.update({
            "stress_avg_score": stress.get("avgStressLevel"),
            "stress_duration_secs": stress.get("stressDuration"),
            "rest_duration_secs": stress.get("restStressDuration"),
        })
    except Exception as e:
        print(f"Error fetching stress data for {target_date}: {e}")
        
    # 7. Training Readiness
    try:
        readiness = client.get_training_readiness(target_date) or {}
        if isinstance(readiness, dict):
            summary["training_readiness_score"] = readiness.get("readinessScore")
    except Exception as e:
        print(f"Error fetching training readiness for {target_date}: {e}")
        
    # 8. Lifestyle Logging
    try:
        lifestyle = client.get_lifestyle_logging_data(target_date) or {}
        logs = lifestyle.get("dailyLogsReport", [])
        for item in logs:
            name = item.get("name", "").replace(" ", "_").replace("/", "_")
            if name:
                log_status = item.get("logStatus", "YES")
                summary[f"lifestyle_{name}"] = log_status
    except Exception as e:
        print(f"Error fetching lifestyle logging for {target_date}: {e}")
        
    # 9. Precise VO2 Max & Max Metrics
    try:
        max_metrics = client.get_max_metrics(target_date)
        if max_metrics and isinstance(max_metrics, list) and len(max_metrics) > 0:
            generic = max_metrics[0].get("generic", {}) or {}
            if "vo2MaxPreciseValue" in generic:
                summary["vo2MaxPreciseValue"] = generic.get("vo2MaxPreciseValue")
    except Exception as e:
        print(f"Error fetching max metrics for {target_date}: {e}")
        
    return summary


try:
    # login will use tokens from session_dir if valid, or use credentials and save tokens
    garmin.login(tokenstore=session_dir)
    print("Successfully logged in to Garmin.")
except Exception as e:
    print(f"Critical failure during Garmin login: {e}")
    raise e

# Fetch some data (example: yesterday's stats and activities)
yesterday = date.today() - timedelta(days=2)
yesterday = yesterday.isoformat()

print(f"Fetching data for {yesterday}...")

# 1. Fetch Daily Summary
print(f"Fetching comprehensive daily summary for {yesterday}...")
summary = aggregate_daily_fetch(garmin, yesterday)

# 2. Fetch Activities
try:
    activities = garmin.get_activities_by_date(yesterday, yesterday)
    print(f"Fetched {len(activities)} activities.")
    summary["activity_count_today"] = len(activities)
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_key_path = os.path.join(script_dir, 'secrets', 'garmin-logger-google-cred.json')
    if os.path.exists(local_key_path):
        gc = gspread.service_account(filename=local_key_path)
    else:
        raise Exception("Google credentials not found in environment or local file.")

# 4. Update the Sheets
if SPREADSHEET_LOGGING_ENABLED:
    sheet_name = 'Garmin Log'
    try:
        sh = gc.open(sheet_name)
        
        # Handle Daily Stats sheet
        try:
            ws_daily = sh.worksheet("Daily")
        except gspread.WorksheetNotFound:
            ws_daily = sh.add_worksheet(title="Daily", rows=100, cols=50)
            print("Created 'Daily' worksheet.")
            
        sync_data_with_dynamic_headers(ws_daily, [summary], primary_key='calendarDate')
        print(f"Synced daily stats for {yesterday}")

        # Handle Activities sheet
        try:
            ws_activities = sh.worksheet("Activities")
        except gspread.WorksheetNotFound:
            ws_activities = sh.add_worksheet(title="Activities", rows=100, cols=50)
            print("Created 'Activities' worksheet.")

        sync_data_with_dynamic_headers(ws_activities, activities, primary_key='startTimeLocal')
        print(f"Synced activities for {yesterday}")

    except gspread.SpreadsheetNotFound:
        print(f"Error: Spreadsheet '{sheet_name}' not found. Please make sure you created it and shared it with the service account.")
    except Exception as e:
        print(f"Error updating sheet: {e}")
else:
    print("Spreadsheet logging is disabled. Printing summary and activities to console")
    print(f"Daily summary: {summary}")
    print(f"Activities: {activities}")
