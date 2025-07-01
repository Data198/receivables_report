# if we run after 06:30 PM today, we et today's bhavcopy, else yesterday's bhavcopy.

import requests
from datetime import datetime, timedelta
from pathlib import Path
import zipfile
import io

# === Target directory for saving only the extracted CSV ===
TARGET_FOLDER = r"F:\My Drive\Personal Info\Stock Market\New OI Analysis"

def get_latest_available_date():
    now = datetime.now()
    if now.weekday() >= 5:
        # Saturday/Sunday: use previous weekday
        return get_previous_weekday()
    elif now.hour >= 18:
        # After 6 PM on a weekday: try today
        return now
    else:
        # Before 6 PM: use T-1
        return get_previous_weekday()

def get_previous_weekday():
    today = datetime.now()
    offset = 1
    while True:
        prev_day = today - timedelta(days=offset)
        if prev_day.weekday() < 5:
            return prev_day
        offset += 1

def download_and_extract_csv_only(date_obj=None, save_dir=TARGET_FOLDER):
    if date_obj is None:
        date_obj = get_latest_available_date()

    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            for file in z.namelist():
                if file.endswith(".csv"):
                    z.extract(file, path=save_path)
                    print(f"✅ CSV extracted and saved to: {save_path / file}")
    else:
        print(f"❌ Download failed for date {date_str} | Status Code: {response.status_code}")

# Run the function
download_and_extract_csv_only()
