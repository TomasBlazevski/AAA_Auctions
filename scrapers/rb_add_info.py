import os
import json
import time
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Return a PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        user=os.getenv("DB_USER", "Tomas"),
        password=os.getenv("DB_PASS", "celtic46"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5435"),
        dbname=os.getenv("DB_NAME", "a_auctions")
    )

def fetch_urls():
    """Retrieve all non‑empty URLs from rb_trucks_specs."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT url
            FROM rb_trucks_specs
            WHERE url IS NOT NULL AND url != ''
            AND Date_of_A BETWEEN CURRENT_DATE AND (CURRENT_DATE + interval '14 days')
        """)
        rows = cur.fetchall()
        urls = [row[0] for row in rows]
        return urls
    finally:
        cur.close()
        conn.close()
        
def split_engine_hours(text):
    if not text:
        return None, None
    match = re.match(r'^([\d,]+)', text.strip())
    if match:
        int_str = match.group(1).replace(',', '')
        try:
            int_part = int(int_str)
        except ValueError:
            int_part = None
        notes_part = text.strip()[match.end():].strip()
        return int_part, notes_part if notes_part else None
    else:
        return None, text.strip()
        
def scrape_truck(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, impersonate="chrome120", timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch {url}: status {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"Request error for {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    script_tag = soup.find('script', id='__NEXT_DATA__')
    if not script_tag:
        logger.error(f"__NEXT_DATA__ missing for {url}")
        return None

    try:
        data = json.loads(script_tag.string)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for {url}: {e}")
        return None

    try:
        page_props = data['props']['pageProps']
        items = page_props.get('items', [])
        if not items:    
            if 'product' in page_props:
                items = [page_props['product']]
            elif 'listing' in page_props:
                items = [page_props['listing']]
            else:
                raise KeyError("No items, product, or listing found")
        inspection_modules = items[0]['inspection']['modules']
    except KeyError as e:
        logger.error(f"Missing key in JSON structure for {url}: {e}")
        return None

    all_tasks = []
    for module in inspection_modules:
        for task in module.get('tasks', []):
            task_name = task.get('task_name', '')
            description = task.get('description') or task.get('result') or task.get('value') or ''
            if description:
                all_tasks.append({'task_name': task_name, 'description': description})

    def get_value(component_name):
        for task in all_tasks:
            if component_name.lower() in task['task_name'].lower():
                return task['description']
        return None

    vin = get_value("Serial Number / VIN") or get_value("VIN")
    if not vin:
        logger.warning(f"VIN not found for {url}")       
        return None

    odometer_raw = get_value("Hour Meter / Odometer") or get_value("Odometer")
    odometer_int = None
    if odometer_raw:
        match = re.match(r'^([\d,]+)', odometer_raw.strip())
        if match:
            int_str = match.group(1).replace(',', '')
            try:
                odometer_int = int(int_str)
            except ValueError:
                odometer_int = None
    odometer = odometer_int
    engine_hours_raw = get_value("Engine Hours")
    engine_hours, engine_hours_notes = split_engine_hours(engine_hours_raw)
    emissions = get_value("Emissions Status")
    deficiencies = get_value("Deficiencies") or get_value("Deficient Components")
    if deficiencies is None:
        deficiencies = "No deficiencies reported"

    limited_findings = []
    for task in all_tasks:
        task_name = task['task_name']
        desc = task['description']
        if "Limited Function Check" in task_name:
            limited_findings.append(desc)
        elif any(phrase in desc for phrase in [
            "engine started and ran", "drivetrain was operational",
            "main components are in place", "brakes are operational"
        ]):
            limited_findings.append(desc)
        elif "Brakes" in task_name:
            limited_findings.append(desc)
    limited_checks = " | ".join(limited_findings)

    return {
        'vin': vin,
        'odometer': odometer,
        'engine_hours': engine_hours,
        'engine_hours_notes': engine_hours_notes,
        'emissions_status': emissions,
        'limited_function_check': limited_checks,
        'deficiencies': deficiencies,
        'url': url
    }
    
# ------------------------------------------------------------
# 5. Upsert(update & insert) a single record into rb_add_info
# ------------------------------------------------------------
def upsert_record(conn, record):
    """
    record is a dict with keys: vin, odometer, engine_hours,
    engine_hours_notes, emissions_status, limited_function_check, deficiencies.
    """
    upsert_sql = """
        INSERT INTO rb_add_info
        (vin, odometer, engine_hours, engine_hours_notes, emissions_status,
         limited_function_check, deficiencies, URL)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (vin) DO UPDATE SET
            odometer = EXCLUDED.odometer,
            engine_hours = EXCLUDED.engine_hours,
            engine_hours_notes = EXCLUDED.engine_hours_notes,
            emissions_status = EXCLUDED.emissions_status,
            limited_function_check = EXCLUDED.limited_function_check,
            deficiencies = EXCLUDED.deficiencies,
            URL = EXCLUDED.URL,
            scraped_at = CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(upsert_sql, (
            record['vin'],
            record['odometer'],
            record['engine_hours'],
            record['engine_hours_notes'],
            record['emissions_status'],
            record['limited_function_check'],
            record['deficiencies'],
            record['url']
        ))
    conn.commit()
    logger.info(f"Inserted/Updated VIN {record['vin']}")


def main():
    urls = fetch_urls()
    if not urls:
        logger.info("No URLs to process. Exiting.")
        return

    conn = get_db_connection()
    processed = 0
    failed = 0

    for idx, url in enumerate(urls, start=1):
        logger.info(f"Processing {idx}/{len(urls)}: {url}")
        record = scrape_truck(url)
        if record is None:
            failed += 1
            continue

        try:
            upsert_record(conn, record)
            processed += 1
        except Exception as e:
            logger.error(f"Database error for VIN {record.get('vin', 'unknown')}: {e}")
            failed += 1

        time.sleep(1)

    conn.close()
    logger.info(f"Done. Processed: {processed}, Failed: {failed}")

if __name__ == "__main__":
    main()

