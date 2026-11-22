import os
import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from databricks.sdk import WorkspaceClient
from databricks import sql

load_dotenv()
logger = logging.getLogger("raw_storage")

def save_raw_payload(source: str, content: str, ext: str = "json") -> str:
    now_utc = datetime.now(timezone.utc)
    date_path = now_utc.strftime("%Y/%m/%d")
    ts_str = now_utc.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{source}_{ts_str}.{ext}"

    # 1. Write immutable local copy
    local_dir = os.path.join("data_dumps", "raw", source, date_path)
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, filename)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Saved local raw file: {local_path}")

    # 2. Upload to Databricks Unity Catalog Volume (or fallback to SQL direct insert)
    raw_host = os.getenv("DATABRICKS_SERVER_HOSTNAME") or os.getenv("DATABRICKS_HOST")
    host = None
    if raw_host:
        host = raw_host.split("://")[-1].split("/")[0]

    token = os.getenv("DATABRICKS_TOKEN")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "")

    uploaded_to_volume = False
    if host and token:
        try:
            w = WorkspaceClient(host=f"https://{host}", token=token)
            volume_path = f"/Volumes/airlens/raw/landing_zone/{source}/{filename}"
            with open(local_path, "rb") as f:
                w.files.upload(volume_path, f, overwrite=True)
            logger.info(f"Uploaded to Volume: {volume_path}")
            uploaded_to_volume = True
        except Exception as e:
            logger.warning(f"Volume upload skipped ({e}); falling back to direct SQL bronze insert.")

    # 3. Direct SQL Bronze Ingestion fallback
    if not uploaded_to_volume and host and token and http_path:
        try:
            with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
                with conn.cursor() as cur:
                    batch_id = f"batch_{ts_str}"
                    source_file = f"dbfs:/Volumes/airlens/raw/landing_zone/{source}/{filename}"
                    if source == "waqi":
                        cur.execute(
                            "INSERT INTO airlens.bronze.bronze_waqi_openaq (raw_payload, _source, _ingest_ts, _batch_id, _source_file) VALUES (?, ?, current_timestamp(), ?, ?)",
                            [content, "waqi", batch_id, source_file],
                        )
                    elif source == "weather":
                        cur.execute(
                            "INSERT INTO airlens.bronze.bronze_weather (raw_payload, _source, _ingest_ts, _batch_id, _source_file) VALUES (?, ?, current_timestamp(), ?, ?)",
                            [content, "open_meteo_weather", batch_id, source_file],
                        )
                    logger.info(f"Direct SQL insert into airlens.bronze for source '{source}' succeeded.")
        except Exception as e:
            logger.error(f"Direct SQL bronze insert failed: {e}")

    return local_path
