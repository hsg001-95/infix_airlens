import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import json
import yaml
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from extraction.utils.retry import fetch_with_retry
from extraction.utils.storage import save_raw_payload

load_dotenv()
logger = logging.getLogger("waqi_extractor")

def run():
    token = os.getenv("WAQI_API_TOKEN")
    with open("config/cities.yaml", "r") as f:
        cities = yaml.safe_load(f)["cities"]

    records = []
    batch_ts = datetime.now(timezone.utc).isoformat()

    for city in cities:
        slug = city["waqi_slug"]
        url = f"https://api.waqi.info/feed/{slug}/"
        try:
            resp = fetch_with_retry(url, params={"token": token})
            payload = resp.json()
            if payload.get("status") == "ok":
                records.append({
                    "city_id": city["city_id"],
                    "city_name": city["city_name"],
                    "ingested_at_utc": batch_ts,
                    "raw_data": payload["data"]
                })
            else:
                logger.error(f"WAQI API error for {slug}: {payload}")
        except Exception as e:
            logger.error(f"Skipping {slug} after retries: {e}")

    if records:
        ndjson = "\n".join(json.dumps(r) for r in records)
        save_raw_payload("waqi", ndjson, ext="json")
        logger.info(f"WAQI extraction complete: {len(records)}/{len(cities)} cities.")
    else:
        logger.warning("WAQI extraction returned 0 records.")

if __name__ == "__main__":
    run()
