import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import yaml
import logging
from datetime import datetime, timezone
from extraction.utils.retry import fetch_with_retry
from extraction.utils.storage import save_raw_payload

logger = logging.getLogger("weather_extractor")

def run():
    with open("config/cities.yaml", "r") as f:
        cities = yaml.safe_load(f)["cities"]

    records = []
    batch_ts = datetime.now(timezone.utc).isoformat()

    for city in cities:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": city["lat"],
            "longitude": city["lon"],
            "current": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Kolkata"
        }
        try:
            resp = fetch_with_retry(url, params=params)
            payload = resp.json()
            records.append({
                "city_id": city["city_id"],
                "city_name": city["city_name"],
                "ingested_at_utc": batch_ts,
                "raw_data": payload
            })
        except Exception as e:
            logger.error(f"Skipping weather for {city['city_name']}: {e}")

    if records:
        ndjson = "\n".join(json.dumps(r) for r in records)
        save_raw_payload("weather", ndjson, ext="json")
        logger.info(f"Weather extraction complete: {len(records)}/{len(cities)} cities.")

if __name__ == "__main__":
    run()
