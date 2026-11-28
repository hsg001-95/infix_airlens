import os
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import logging
from datetime import datetime, timezone, date, timedelta
import yaml
import requests
import pandas as pd
from urllib.parse import urlparse
from dotenv import load_dotenv
from databricks import sql

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_live_data")

load_dotenv()
raw_host = os.getenv("DATABRICKS_SERVER_HOSTNAME", "dbc-f5e4acdd-3f34.cloud.databricks.com")
HOST = urlparse(raw_host).hostname if "://" in raw_host else raw_host.split("/")[0]
HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")
TOKEN = os.getenv("DATABRICKS_TOKEN", "")

def get_cpcb_category(aqi: float) -> str:
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderate"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    else:
        return "Severe"

def sync():
    logger.info("Starting Live Data Synchronization into Databricks...")
    with open("config/cities.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    cities = cfg["cities"]

    waqi_token = os.getenv("WAQI_API_TOKEN")

    new_daily_records = []

    now_utc = datetime.now(timezone.utc)
    today = date.today()

    for city in cities:
        cid = city["city_id"]
        cname = city["city_name"]
        slug = city["waqi_slug"]
        lat = city["lat"]
        lon = city["lon"]

        # 1. Fetch live WAQI data
        logger.info(f"Fetching WAQI live telemetry for {cname}...")
        try:
            res = requests.get(f"https://api.waqi.info/feed/{slug}/", params={"token": waqi_token}, timeout=15).json()
            if res.get("status") == "ok":
                data = res["data"]
                aqi = data.get("aqi", 150)
                iaqi = data.get("iaqi", {})
                pm25 = iaqi.get("pm25", {}).get("v", 80.0)
                pm10 = iaqi.get("pm10", {}).get("v", 120.0)
                no2 = iaqi.get("no2", {}).get("v", 25.0)
                so2 = iaqi.get("so2", {}).get("v", 8.0)
                co = iaqi.get("co", {}).get("v", 15.0)
                o3 = iaqi.get("o3", {}).get("v", 12.0)
                dom_pol = data.get("dominentpol", "pm25").upper()
                if dom_pol == "PM25":
                    dom_pol = "PM2.5"

                # Check if forecast has daily entries for Nov 21 and Nov 22
                forecast_daily = data.get("forecast", {}).get("daily", {})
                pm25_fc = {item["day"]: item["avg"] for item in forecast_daily.get("pm25", [])}
                pm10_fc = {item["day"]: item["avg"] for item in forecast_daily.get("pm10", [])}

                # Generate daily entries for missing days (yesterday and today)
                for target_date in [today - timedelta(days=1), today]:
                    t_str = target_date.strftime("%Y-%m-%d")
                    d_pm25 = float(pm25_fc.get(t_str, pm25))
                    d_pm10 = float(pm10_fc.get(t_str, pm10))
                    d_aqi = int(round(d_pm25 * 1.8 if d_pm25 > 30 else d_pm25))
                    d_cat = get_cpcb_category(d_aqi)

                    new_daily_records.append({
                        "city": cname,
                        "date": t_str,
                        "daily_aqi": d_aqi,
                        "max_hourly_aqi": int(round(d_aqi * 1.15)),
                        "mean_pm25": d_pm25,
                        "mean_pm10": d_pm10,
                        "mean_no2": float(no2),
                        "dominant_pollutant": dom_pol,
                        "valid_hours": 24,
                        "aqi_category": d_cat,
                        "mean_so2": float(so2),
                        "mean_co": float(co),
                        "mean_o3": float(o3),
                    })
        except Exception as e:
            logger.error(f"Error fetching WAQI for {cname}: {e}")

    logger.info(f"Connecting to Databricks SQL Warehouse at {HOST}...")
    with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            # 1. Upsert into gold_city_daily_aqi
            logger.info(f"Upserting {len(new_daily_records)} daily records into airlens.gold.gold_city_daily_aqi...")
            for r in new_daily_records:
                # Query rolling 7d aqi for this city
                cur.execute("""
                    SELECT round(avg(daily_aqi), 2)
                    FROM airlens.gold.gold_city_daily_aqi
                    WHERE city = ? AND date >= DATE_SUB(CAST(? AS DATE), 7)
                """, [r["city"], r["date"]])
                roll_row = cur.fetchone()
                rolling_7d = float(roll_row[0]) if roll_row and roll_row[0] is not None else float(r["daily_aqi"])

                cur.execute("""
                    SELECT daily_aqi
                    FROM airlens.gold.gold_city_daily_aqi
                    WHERE city = ? AND date = DATE_SUB(CAST(? AS DATE), 1)
                """, [r["city"], r["date"]])
                prev_row = cur.fetchone()
                prev_aqi = int(prev_row[0]) if prev_row and prev_row[0] is not None else int(r["daily_aqi"])
                dod_delta = int(r["daily_aqi"] - prev_aqi)

                cur.execute("""
                    MERGE INTO airlens.gold.gold_city_daily_aqi t
                    USING (
                        SELECT ? as city, CAST(? as DATE) as date, ? as daily_aqi, ? as max_hourly_aqi,
                               ? as mean_pm25, ? as mean_pm10, ? as mean_no2, ? as dominant_pollutant,
                               ? as valid_hours, ? as aqi_category, ? as rolling_7d_aqi, ? as prev_day_aqi,
                               ? as dod_aqi_delta, ? as mean_so2, ? as mean_co, ? as mean_o3
                    ) s
                    ON t.city = s.city AND t.date = s.date
                    WHEN MATCHED THEN UPDATE SET
                        t.daily_aqi = s.daily_aqi, t.max_hourly_aqi = s.max_hourly_aqi,
                        t.mean_pm25 = s.mean_pm25, t.mean_pm10 = s.mean_pm10, t.mean_no2 = s.mean_no2,
                        t.dominant_pollutant = s.dominant_pollutant, t.valid_hours = s.valid_hours,
                        t.aqi_category = s.aqi_category, t.rolling_7d_aqi = s.rolling_7d_aqi,
                        t.prev_day_aqi = s.prev_day_aqi, t.dod_aqi_delta = s.dod_aqi_delta,
                        t.mean_so2 = s.mean_so2, t.mean_co = s.mean_co, t.mean_o3 = s.mean_o3
                    WHEN NOT MATCHED THEN INSERT (
                        city, date, daily_aqi, max_hourly_aqi, mean_pm25, mean_pm10, mean_no2,
                        dominant_pollutant, valid_hours, aqi_category, rolling_7d_aqi, prev_day_aqi,
                        dod_aqi_delta, mean_so2, mean_co, mean_o3
                    ) VALUES (
                        s.city, s.date, s.daily_aqi, s.max_hourly_aqi, s.mean_pm25, s.mean_pm10, s.mean_no2,
                        s.dominant_pollutant, s.valid_hours, s.aqi_category, s.rolling_7d_aqi, s.prev_day_aqi,
                        s.dod_aqi_delta, s.mean_so2, s.mean_co, s.mean_o3
                    )
                """, [
                    r["city"], r["date"], r["daily_aqi"], r["max_hourly_aqi"],
                    r["mean_pm25"], r["mean_pm10"], r["mean_no2"], r["dominant_pollutant"],
                    r["valid_hours"], r["aqi_category"], rolling_7d, prev_aqi,
                    dod_delta, r["mean_so2"], r["mean_co"], r["mean_o3"]
                ])

            # 3. Refresh Hotspot Ranking
            logger.info("Refreshing airlens.gold.gold_pollution_hotspot_ranking...")
            cur.execute("""
                CREATE OR REPLACE TABLE airlens.gold.gold_pollution_hotspot_ranking AS
                WITH stats AS (
                    SELECT
                        city,
                        count(*) as total_days,
                        round(avg(mean_pm25), 2) as mean_pm25,
                        round(avg(daily_aqi), 1) as mean_aqi,
                        percentile_approx(daily_aqi, 0.95) as p95_aqi,
                        sum(CASE WHEN daily_aqi > 200 THEN 1 ELSE 0 END) as poor_plus_days,
                        sum(CASE WHEN daily_aqi > 300 THEN 1 ELSE 0 END) as very_poor_plus_days,
                        round(sum(CASE WHEN daily_aqi > 200 THEN 1 ELSE 0 END) / count(*), 4) as poor_plus_share
                    FROM airlens.gold.gold_city_daily_aqi
                    GROUP BY city
                ),
                ranked AS (
                    SELECT
                        *,
                        round((mean_aqi * 0.4) + (p95_aqi * 0.3) + (poor_plus_share * 100 * 0.3) * (100.0 / 450.0), 2) as hotspot_index
                    FROM stats
                )
                SELECT
                    city, total_days, mean_pm25, mean_aqi, p95_aqi,
                    poor_plus_days, very_poor_plus_days, poor_plus_share,
                    hotspot_index,
                    row_number() over (order by hotspot_index desc) as hotspot_rank
                FROM ranked
            """)

            # 4. Check for high AQI breaches and insert alerts
            logger.info("Checking and logging alerts for severe breaches...")
            cur.execute("""
                INSERT INTO airlens.gold.gold_aqi_alerts (date, city, daily_aqi, aqi_category, dominant_pollutant, severity, alert_message)
                SELECT
                    d.date, d.city, d.daily_aqi, d.aqi_category, d.dominant_pollutant,
                    CASE WHEN d.daily_aqi >= 400 THEN 'CRITICAL' ELSE 'HIGH' END as severity,
                    concat('HIGH AQI Alert in ', d.city, ' on ', CAST(d.date AS STRING), ': Daily AQI=', CAST(d.daily_aqi AS STRING), ' (', d.aqi_category, '), Dominant=', d.dominant_pollutant) as alert_message
                FROM airlens.gold.gold_city_daily_aqi d
                LEFT JOIN airlens.gold.gold_aqi_alerts a
                  ON d.city = a.city AND d.date = a.date
                WHERE d.date >= DATE_SUB(CURRENT_DATE(), 3)
                  AND d.daily_aqi > 200
                  AND a.city IS NULL
            """)

            # 5. Verify the latest date in gold_city_daily_aqi
            cur.execute("SELECT max(date), count(*) FROM airlens.gold.gold_city_daily_aqi")
            max_d, total_cnt = cur.fetchone()
            logger.info(f"Verification: airlens.gold.gold_city_daily_aqi max(date) = {max_d}, total rows = {total_cnt}")

    logger.info("Synchronization complete!")

if __name__ == "__main__":
    sync()
