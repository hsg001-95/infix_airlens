import os
import time
from urllib.parse import urlparse
from datetime import datetime
import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

load_dotenv()

raw_host = os.getenv("DATABRICKS_SERVER_HOSTNAME", "dbc-f5e4acdd-3f34.cloud.databricks.com")
HOST = urlparse(raw_host).hostname if "://" in raw_host else raw_host.split("/")[0]
HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")
TOKEN = os.getenv("DATABRICKS_TOKEN", "")


@st.cache_data(ttl=600, show_spinner="Fetching live Gold tables from Databricks Unity Catalog...")
def fetch_airlens_gold_data() -> dict:
    """Queries airlens.gold and airlens.ops tables directly via Databricks SQL Warehouse."""
    if not HTTP_PATH or not TOKEN or "YOUR_" in HTTP_PATH or "YOUR_" in TOKEN:
        raise ValueError("Missing DATABRICKS_HTTP_PATH or DATABRICKS_TOKEN in .env")

    t0 = time.perf_counter()
    with sql.connect(
        server_hostname=HOST,
        http_path=HTTP_PATH,
        access_token=TOKEN,
        user_agent_entry="InfixAirLens-Dashboard/1.0",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_catalog(), current_schema(), current_version()")
            meta_row = cur.fetchone()

        hotspots = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_pollution_hotspot_ranking ORDER BY hotspot_index DESC", conn
        )
        daily = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_city_daily_aqi ORDER BY date", conn
        )
        fire = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_fire_aqi_impact ORDER BY fire_date", conn
        )
        weather = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_weather_aqi_correlation ORDER BY corr_wind_pm25", conn
        )
        forecast = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_aqi_forecast ORDER BY forecast_date", conn
        )
        alerts = pd.read_sql(
            "SELECT * FROM airlens.gold.gold_aqi_alerts ORDER BY date DESC LIMIT 150", conn
        )
        dq_audit = pd.read_sql(
            "SELECT * FROM airlens.ops.dq_audit_log", conn
        )
        backtest = pd.read_sql(
            "SELECT * FROM airlens.ops.forecast_backtest_metrics ORDER BY rmse", conn
        )

    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {
        "hotspots": hotspots,
        "daily": daily,
        "fire": fire,
        "weather": weather,
        "forecast": forecast,
        "alerts": alerts,
        "dq_audit": dq_audit,
        "backtest": backtest,
        "meta": {
            "host": HOST,
            "warehouse_path": HTTP_PATH,
            "dbr_version": meta_row[2] if meta_row else "Serverless SQL",
            "latency_ms": latency_ms,
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
            "total_rows": sum(len(df) for df in [hotspots, daily, fire, weather, forecast, alerts]),
        },
    }
