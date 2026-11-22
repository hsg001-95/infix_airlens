import time
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def fetch_with_retry(url: str, params: dict = None, headers: dict = None, max_retries: int = 3, timeout: int = 20):
    logger = logging.getLogger("retry_client")
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            wait_sec = 4 ** (attempt - 1)  # 1s, 4s, 16s
            logger.warning(f"Attempt {attempt}/{max_retries} failed for {url}: {e}")
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts exhausted for {url}")
                raise
            time.sleep(wait_sec)
