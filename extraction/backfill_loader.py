import os
import time
import yaml
import requests
import pandas as pd
from datetime import date, timedelta

os.makedirs("data_dumps/backfill", exist_ok=True)

with open("config/cities.yaml", "r") as f:
    cfg = yaml.safe_load(f)

end_date = (date.today() - timedelta(days=1)).isoformat()
start_date = (date.today() - timedelta(days=430)).isoformat()  # ~14 months

for city in cfg["cities"]:
    cid = city["city_id"]
    cname = city["city_name"]
    lat, lon = city["lat"], city["lon"]
    print(f"Fetching {cname} ({cid}) from {start_date} to {end_date}...")

    # 1. Historical Air Quality
    aq_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}"
        f"&hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
        f"&timezone=Asia%2FKolkata"
    )
    aq_res = requests.get(aq_url, timeout=30).json()
    df_aq = pd.DataFrame(aq_res["hourly"])

    # 2. Historical Weather Archive
    wx_url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}"
        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure"
        f"&timezone=Asia%2FKolkata"
    )
    wx_res = requests.get(wx_url, timeout=30).json()
    df_wx = pd.DataFrame(wx_res["hourly"])

    # Merge on hourly timestamp and tag city metadata
    df = pd.merge(df_aq, df_wx, on="time", how="inner")
    df.insert(0, "city_id", cid)
    df.insert(1, "city_name", cname)
    df.insert(2, "latitude", lat)
    df.insert(3, "longitude", lon)

    out_path = f"data_dumps/backfill/{cid.lower()}_backfill_{start_date}_to_{end_date}.csv"
    df.to_csv(out_path, index=False)
    print(f"  -> Saved {len(df):,} rows to {out_path}")
    time.sleep(1)

print("Backfill complete!")
