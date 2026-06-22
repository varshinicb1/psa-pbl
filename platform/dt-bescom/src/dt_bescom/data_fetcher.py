"""
BESCOM Open Data Fetcher.

Downloads real BESCOM datasets from public sources.
Working URLs verified against opencity.in data portal.
"""

from __future__ import annotations

import csv
import logging
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BESCOM_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Direct download URLs (verified working via data.opencity.in)
DATASET_URLS: Dict[str, str] = {
    "substations": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/3c779061-159d-40ee-bc07-92691d4eec70/download/9f945eb2-b531-4d5f-a096-b9d6ddd7b1d4.csv",
    "consumption": "https://data.opencity.in/dataset/c2e70b7b-2af9-4223-ad49-f67f32d9366f/resource/addf1f15-7c90-44db-ab13-572aae08b0f1/download/70d066f8-2145-4b98-9e94-d7657b8a04a0.csv",
    "ht_lines_2023": "https://data.opencity.in/dataset/b6bb6c50-19f7-49f9-8425-00f96fad7dd9/resource/61a564f1-1b4e-457d-9f63-9448c6ef13c8/download/9cce9046-a070-44ee-a85a-4868aa9e957c.csv",
    "energy_requirement": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/a2cebd72-0a37-4e78-86a9-4c419a560e50/download/b56ecf68-a00d-4912-ad3b-7928bd3b7219.csv",
    "num_consumers": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/f133d9c4-92b9-488b-bf1d-3c17425990cf/download/c180c1da-9684-4887-8d56-13a806b4953f.csv",
    "units_sold": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/b0ee93ea-65b6-4523-a500-235dd5f73896/download/e5e600c4-5686-4ad6-9920-8d05a659d226.csv",
}

USER_AGENT = "GridDigitalTwin/2.0"


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def download_csv(url: str, save_to: Optional[str] = None) -> Optional[List[Dict[str, str]]]:
    """Download a CSV and return parsed rows. Optionally save to file."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=30) as resp:
            content = resp.read().decode("utf-8-sig")
    except Exception as e:
        logger.warning(f"Download failed: {url[:80]}...: {e}")
        return None

    reader = csv.DictReader(content.splitlines())
    rows = list(reader)

    if save_to:
        path = Path(save_to)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=reader.fieldnames)
            w.writeheader()
            w.writerows(rows)
        logger.info(f"Saved {len(rows)} rows to {path}")

    return rows


def fetch_bescom_substations(save_to: Optional[str] = None) -> Optional[List[Dict[str, str]]]:
    """Fetch 280 BESCOM substations with voltage class, zone, district, taluk."""
    return download_csv(DATASET_URLS["substations"], save_to)


def fetch_bescom_ht_lines(save_to: Optional[str] = None) -> Optional[List[Dict[str, str]]]:
    """Fetch BESCOM HT lines by division for 2023-24."""
    return download_csv(DATASET_URLS["ht_lines_2023"], save_to)


def fetch_bescom_consumption(save_to: Optional[str] = None) -> Optional[List[Dict[str, str]]]:
    """Fetch BESCOM annual consumption (2010-11 to 2022-23)."""
    return download_csv(DATASET_URLS["consumption"], save_to)


def download_all_bescom_data(output_dir: Optional[str] = None) -> Dict[str, bool]:
    """Download all 6 BESCOM datasets."""
    out = output_dir or str(BESCOM_DATA_DIR)
    results = {}
    for name, url in DATASET_URLS.items():
        path = os.path.join(out, f"bescom_{name}.csv")
        rows = download_csv(url, save_to=path)
        results[name] = rows is not None
    ok = sum(1 for v in results.values() if v)
    logger.info(f"Downloaded {ok}/{len(results)} datasets to {out}")
    return results


def parse_substations_csv(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse the BESCOM substations CSV into structured records."""
    if path is None:
        path = str(BESCOM_DATA_DIR / "bescom_substations.csv")

    if not os.path.exists(path):
        logger.warning(f"Substations CSV not found at {path}")
        return []

    substations = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                voltage = int(row.get("Voltage Class (in kV)", "0").strip())
            except (ValueError, TypeError):
                voltage = 0
            substations.append({
                "zone": row.get("Zone", "").strip(),
                "district": row.get("District", "").strip(),
                "taluk": row.get("Taluk", "").strip(),
                "name": row.get("Name of Sub-Station", "").strip(),
                "voltage_kv": voltage,
                "commission_date": row.get("Date of commission", "").strip(),
            })
    logger.info(f"Parsed {len(substations)} substations from {path}")
    return substations


def list_available_datasets() -> List[str]:
    return [f"{k}: {v.split('/')[-1]}" for k, v in DATASET_URLS.items()]
