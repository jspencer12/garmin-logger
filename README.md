# Daily Garmin Exporter

Automated daily sync of Garmin data to Google Sheets using GitHub Actions.

## Setup Instructions

Follow these steps to set up the automated sync:

### 1. Google Sheets Setup
1.  Create a new Google Sheet where you want to store the data.
2.  Name it `Garmin Log` (or change the name in `main.py` if you want a different name).

### 2. Google Service Account (For Authentication)
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new Project (if you don't have one).
3.  Search for **Google Sheets API** and **Google Drive API** in the main search bar and enable them.
4.  Go to **IAM & Admin > Service Accounts** and create a new **Service Account**.
5.  After generating the accout, click on **Keys > Add Key** and generate a **JSON Key**. Download this file.
6.  Open your Google Sheet, click **Share**, and add the email address of your Service Account (e.g., `my-bot@my-project.iam.gserviceaccount.com`) as an Editor.

### 3. GitHub Secrets Setup
Clone this repository. After cloning, open the repository in your browser and go to **Settings > Secrets and variables > Actions** and add the following **Repository Secrets**:
*   `GARMIN_EMAIL`: Your Garmin account email.
*   `GARMIN_PASSWORD`: Your Garmin account password.
*   `GSPREAD_CREDENTIALS`: The entire contents of the Google JSON key file you downloaded in step 2.

### 4. Enable GitHub Actions
1.  Go to the **Actions** tab in your GitHub repository.
2.  Select **Daily Garmin Sync**.
3.  Click **Run workflow** to test it manually.
4.  The workflow is scheduled to run daily at 11:00 AM UTC.

## Customization
You can modify `main.py` to extract more data or change the layout of the spreadsheet.
