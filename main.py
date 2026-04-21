import os
import json
import gspread
from garminconnect import Garmin
from datetime import datetime

# 1. Authenticate with Garmin using environment variables
garmin_email = os.environ.get("GARMIN_EMAIL")
garmin_pass = os.environ.get("GARMIN_PASSWORD")
client = Garmin(garmin_email, garmin_pass)
client.login()

# Fetch some data (example: today's steps)
today = datetime.now().strftime("%Y-%m-%d")
steps_data = client.get_steps_data(today)

# Extract structure or total steps
# Note: The structure of steps_data can vary. We attempt to sum steps if it's a list of entries.
total_steps = 0
if isinstance(steps_data, list):
    for entry in steps_data:
        total_steps += entry.get('steps', 0)
else:
    # If it's not a list, we might need to inspect it or use a default
    total_steps = "N/A (Check logs)"
    print(f"Unexpected steps_data structure: {steps_data}")

# 2. Authenticate with Google Sheets using the JSON secret
google_creds_json = os.environ.get("GSPREAD_CREDENTIALS")
creds_dict = json.loads(google_creds_json)
gc = gspread.service_account_from_dict(creds_dict)

# 3. Update the Sheet
sheet_name = 'Garmin Log'
try:
    sh = gc.open(sheet_name)
    worksheet = sh.get_worksheet(0)
    # Appending Date, Status, Steps Summary, and Raw Data
    worksheet.append_row([today, "Success", f"Steps: {total_steps}", json.dumps(steps_data)])
    print(f"Successfully updated sheet {sheet_name} for {today}")
except gspread.SpreadsheetNotFound:
    print(f"Error: Spreadsheet '{sheet_name}' not found. Please make sure you created it and shared it with the service account.")
except Exception as e:
    print(f"Error updating sheet: {e}")
