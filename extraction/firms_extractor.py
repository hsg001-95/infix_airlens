import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import yaml
import logging
from dotenv import load_dotenv
from extraction.utils.retry import fetch_with_retry
from extraction.utils.storage import save_raw_payload

load_dotenv()
logger = logging.getLogger("firms_extractor")

def run(days: int = 2):
    map_key = os.getenv("NASA_FIRMS_MAP_KEY")
    with open("config/cities.yaml", "r") as f:
        bbox = yaml.safe_load(f)["firms_region"]["bbox"]

    csv_text = ""
    lines = []
    for source in ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"]:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{days}"
        try:
            resp = fetch_with_retry(url, timeout=30)
            text = resp.text.strip()
            cur_lines = text.splitlines()
            if len(cur_lines) > 1:
                csv_text = text
                lines = cur_lines
                logger.info(f"Retrieved {len(lines) - 1} detections from {source}.")
                break
        except Exception as e:
            logger.warning(f"Failed querying {source}: {e}")
    if len(lines) > 1:
        save_raw_payload("firms", csv_text, ext="csv")
        logger.info(f"NASA FIRMS extraction complete: {len(lines) - 1} fire detections.")
    else:
        logger.warning("NASA FIRMS returned header only (0 detections).")

if __name__ == "__main__":
    run()
