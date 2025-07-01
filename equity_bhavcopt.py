import requests
from datetime import datetime, timedelta
from pathlib import Path

# Target save folder
TARGET_FOLDER = r"F:\My Drive\Personal Info\Stock Market\Equity Bhavcopy"

def get_latest_equity_bhavcopy_date():
    now = datetime.now()
    if now.weekday() >= 5:
        return get_previous_weekday()
    elif now.hour >= 18:
        return now
    else:
        return get_previous_weekday()

def get_previous_weekday():
    today = datetime.now()
    offset = 1
    while True:
        prev_day = today - timedelta(days=offset)
        if prev_day.weekday() < 5:
            return prev_day
        offset += 1

def download_security_bhavcopy(date_obj=None, save_dir=TARGET_FOLDER):
    if date_obj is None:
        date_obj = get_latest_equity_bhavcopy_date()

    date_str = date_obj.strftime("%d%m%Y")
    url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
    file_name = f"sec_bhavdata_full_{date_str}.csv"
    save_path = Path(save_dir) / file_name

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Equity Bhavcopy downloaded: {save_path}")
        else:
            print(f"❌ Download failed for {date_str} | Status Code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error downloading equity bhavcopy: {str(e)}")

# Run the function
download_security_bhavcopy()