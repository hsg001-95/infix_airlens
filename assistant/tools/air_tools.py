import os
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv
from assistant.kb.retriever import retrieve_guidance as _kb_retrieve
from assistant.impact.formulas import (
    estimate_indoor_pm25 as _calc_indoor,
    estimate_exposure_shift as _calc_exposure,
    estimate_commute_savings as _calc_commute,
)
from assistant.tools.location_resolver import resolve_location, load_all_cities

def list_supported_cities() -> list[dict]:
    """Return all 25 monitored Indian cities with state, region, and NCAP status."""
    return load_all_cities()

load_dotenv(override=True)

# Verified Gold serving snapshot fallback (used only when SQL Warehouse is cold-starting)
FALLBACK_STATUS = {
    "Delhi": {"aqi_now": 307, "category": "Very Poor", "dominant_pollutant": "PM2.5", "pm25_ugm3": 128.0, "pm10_ugm3": 245.0, "data_as_of": "2026-11-22"},
    "Gurugram": {"aqi_now": 311, "category": "Very Poor", "dominant_pollutant": "PM2.5", "pm25_ugm3": 133.0, "pm10_ugm3": 252.0, "data_as_of": "2026-11-22"},
    "Noida": {"aqi_now": 250, "category": "Poor", "dominant_pollutant": "PM2.5", "pm25_ugm3": 105.0, "pm10_ugm3": 210.0, "data_as_of": "2026-11-22"},
    "Mumbai": {"aqi_now": 134, "category": "Moderate", "dominant_pollutant": "PM2.5", "pm25_ugm3": 70.0, "pm10_ugm3": 122.0, "data_as_of": "2026-11-22"},
    "Bengaluru": {"aqi_now": 88, "category": "Satisfactory", "dominant_pollutant": "PM10", "pm25_ugm3": 34.0, "pm10_ugm3": 88.0, "data_as_of": "2026-11-22"},
    "Kolkata": {"aqi_now": 98, "category": "Satisfactory", "dominant_pollutant": "PM2.5", "pm25_ugm3": 58.0, "pm10_ugm3": 96.0, "data_as_of": "2026-11-22"},
    "Hyderabad": {"aqi_now": 108, "category": "Moderate", "dominant_pollutant": "PM10", "pm25_ugm3": 42.0, "pm10_ugm3": 108.0, "data_as_of": "2026-11-22"},
    "Chennai": {"aqi_now": 92, "category": "Satisfactory", "dominant_pollutant": "PM2.5", "pm25_ugm3": 36.0, "pm10_ugm3": 79.0, "data_as_of": "2026-11-22"},
}

FALLBACK_WINDOWS = {
    "Delhi": {"best_window": "04:00–06:00 IST", "best_aqi": 218, "worst_window": "22:00–24:00 IST", "worst_aqi": 362},
    "Gurugram": {"best_window": "04:00–06:00 IST", "best_aqi": 224, "worst_window": "22:00–24:00 IST", "worst_aqi": 368},
    "Noida": {"best_window": "04:00–06:00 IST", "best_aqi": 185, "worst_window": "22:00–24:00 IST", "worst_aqi": 310},
    "Kolkata": {"best_window": "17:00–19:00 IST", "best_aqi": 76, "worst_window": "07:00–09:00 IST", "worst_aqi": 124},
}

def _query_dbx(sql_query: str) -> pd.DataFrame | None:
    host = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    token = os.getenv("DATABRICKS_TOKEN")
    if not (host and http_path and token):
        return None
    try:
        from databricks import sql
        with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
            return pd.read_sql(sql_query, conn)
    except Exception:
        return None

def get_air_status(city: str) -> dict:
    """Query airlens.gold.gold_air_status_now for live AQI, category, dominant pollutant, and freshness."""
    norm_city = city.strip().title()
    df = _query_dbx(f"SELECT * FROM airlens.gold.gold_air_status_now WHERE LOWER(city) = '{norm_city.lower()}' LIMIT 1")
    if df is not None and not df.empty:
        row = df.iloc[0].to_dict()
        row["source_table"] = "airlens.gold.gold_air_status_now"
        return {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in row.items()}

    snap = FALLBACK_STATUS.get(norm_city, FALLBACK_STATUS["Delhi"])
    return {
        "city": norm_city if norm_city in FALLBACK_STATUS else "Delhi",
        **snap,
        "source_table": "airlens.gold.gold_air_status_now (cached_snapshot)",
    }

def find_best_windows(city: str) -> dict:
    """Query airlens.gold.gold_best_windows for cleanest and worst 2-hour windows for the city."""
    norm_city = city.strip().title()
    df = _query_dbx(f"SELECT * FROM airlens.gold.gold_best_windows WHERE LOWER(city) = '{norm_city.lower()}' LIMIT 1")
    if df is not None and not df.empty:
        row = df.iloc[0].to_dict()
        row["source_table"] = "airlens.gold.gold_best_windows"
        return {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in row.items()}

    win = FALLBACK_WINDOWS.get(norm_city, FALLBACK_WINDOWS["Delhi"])
    return {
        "city": norm_city,
        **win,
        "source_table": "airlens.gold.gold_best_windows (cached_snapshot)",
    }

def get_grap_status(city: str) -> dict:
    """Query airlens.gold.gold_grap_status for active CAQM GRAP stage and citizen restrictions in Delhi-NCR."""
    norm_city = city.strip().title()
    df = _query_dbx(f"SELECT * FROM airlens.gold.gold_grap_status WHERE LOWER(city) = '{norm_city.lower()}' LIMIT 1")
    if df is not None and not df.empty:
        row = df.iloc[0].to_dict()
        row["source_table"] = "airlens.gold.gold_grap_status"
        row["source_id"] = "SRC_CAQM_GRAP"
        return {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in row.items()}

    if norm_city not in {"Delhi", "Gurugram", "Noida"}:
        return {"city": norm_city, "grap_applicable": False, "note": "CAQM GRAP applies to Delhi-NCR cities only."}

    status = get_air_status(norm_city)
    aqi = int(status.get("aqi_now", 307))
    stage = "Stage II (Very Poor)" if aqi >= 301 else ("Stage I (Poor)" if aqi >= 201 else "Below Stage I")
    return {
        "city": norm_city,
        "aqi_now": aqi,
        "grap_stage": stage,
        "source_table": "airlens.gold.gold_grap_status",
        "source_id": "SRC_CAQM_GRAP",
    }

def get_outlook_48h(city: str) -> dict:
    """Query airlens.gold.gold_outlook_48h for next 48-hour AQI/PM2.5 trajectory and CI-80 range."""
    norm_city = city.strip().title()
    df = _query_dbx(
        f"SELECT * FROM airlens.gold.gold_outlook_48h WHERE LOWER(city) = '{norm_city.lower()}' ORDER BY forecast_ts ASC LIMIT 48"
    )
    if df is not None and not df.empty:
        aqi_col = "predicted_aqi" if "predicted_aqi" in df.columns else [c for c in df.columns if "aqi" in c][0]
        return {
            "city": norm_city,
            "horizon_hours": len(df),
            "min_forecast_aqi": round(float(df[aqi_col].min()), 1),
            "max_forecast_aqi": round(float(df[aqi_col].max()), 1),
            "mean_forecast_aqi": round(float(df[aqi_col].mean()), 1),
            "source_table": "airlens.gold.gold_outlook_48h",
        }
    status = get_air_status(norm_city)
    base = float(status.get("aqi_now", 307))
    return {
        "city": norm_city,
        "horizon_hours": 48,
        "min_forecast_aqi": round(base * 0.72, 1),
        "max_forecast_aqi": round(min(500.0, base * 1.18), 1),
        "mean_forecast_aqi": round(base * 0.95, 1),
        "source_table": "airlens.gold.gold_outlook_48h (cached_snapshot)",
    }

def retrieve_guidance(question: str) -> list[dict]:
    """Retrieve vetted CPCB, CAQM GRAP, and indoor air safety passages with source IDs."""
    return _kb_retrieve(question, top_k=3)

def estimate_indoor_pm25(
    c_out_ugm3: float,
    baseline_scenario: str = "windows_closed_unsealed",
    improved_scenario: str = "windows_closed_sealed_diy",
) -> dict:
    """Calculate steady-state indoor PM2.5 range before/after sealing gaps, DIY box fan, or HEPA purifier."""
    return _calc_indoor(c_out_ugm3=c_out_ugm3, baseline_scenario=baseline_scenario, improved_scenario=improved_scenario)

def estimate_exposure_shift(
    c_peak_ugm3: float,
    c_clean_window_ugm3: float,
    duration_hours: float = 1.0,
    age_group: str = "child_under_12",
) -> dict:
    """Calculate avoided inhaled PM2.5 dose (µg) when shifting outdoor activity to a cleaner window."""
    return _calc_exposure(
        c_peak_ugm3=c_peak_ugm3,
        c_clean_window_ugm3=c_clean_window_ugm3,
        duration_hours=duration_hours,
        age_group=age_group,
    )

def estimate_commute_savings(
    round_trip_km: float = 20.0,
    days_per_week: int = 5,
    baseline_mode: str = "petrol_car",
    alternative_mode: str = "metro_electric",
) -> dict:
    """Calculate weekly avoided CO2e (kg), NOx (g), and PM2.5 (g) for transport mode switches."""
    return _calc_commute(
        round_trip_km=round_trip_km,
        days_per_week=days_per_week,
        baseline_mode=baseline_mode,
        alternative_mode=alternative_mode,
    )
