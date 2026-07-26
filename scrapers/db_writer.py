import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2.extras import Json, execute_values
from psycopg2 import sql
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()

# --- DEBUG TEST ---
db_user = os.getenv('DB_USER')
if db_user:
    print(f"✅ Success: Connected as {db_user}")
else:
    print("❌ Warning: DB_USER not found in environment.")

INSERT_TEMPLATE = """
INSERT INTO {} (
    "name_of_auction", "location", "date_of_a", "time_of_a", "lot", "vin", 
    "year", "make", "model", "engine", "hp", "transmission", "ratio", 
    "mileage", "notes", "repaircosts", "transport_costs", "target_price", 
    "max_bid", "sold_for", "url", "details"
) VALUES %s
ON CONFLICT ("vin") DO UPDATE
SET
    "name_of_auction" = EXCLUDED."name_of_auction",
    "location" = EXCLUDED."location",
    "date_of_a" = EXCLUDED."date_of_a",
    "time_of_a" = EXCLUDED."time_of_a",
    "lot" = EXCLUDED."lot",
    "year" = EXCLUDED."year",
    "make" = EXCLUDED."make",
    "model" = EXCLUDED."model",
    "engine" = EXCLUDED."engine",
    "hp" = EXCLUDED."hp",
    "transmission" = EXCLUDED."transmission",
    "ratio" = EXCLUDED."ratio",
    "mileage" = EXCLUDED."mileage",
    "notes" = EXCLUDED."notes",
    "repaircosts" = EXCLUDED."repaircosts",
    "transport_costs" = EXCLUDED."transport_costs",
    "target_price" = EXCLUDED."target_price",
    "max_bid" = EXCLUDED."max_bid",
    "sold_for" = EXCLUDED."sold_for",
    "url" = EXCLUDED."url",
    "details" = EXCLUDED."details";
"""

UPDATE_BY_URL_TEMPLATE = """
UPDATE {}
SET
    "name_of_auction" = %s, "location" = %s, "date_of_a" = %s, "time_of_a" = %s, 
    "lot" = %s, "vin" = %s, "year" = %s, "make" = %s, "model" = %s, "engine" = %s, 
    "hp" = %s, "transmission" = %s, "ratio" = %s, "mileage" = %s, "notes" = %s, 
    "repaircosts" = %s, "transport_costs" = %s, "target_price" = %s, "max_bid" = %s, 
    "sold_for" = %s, "details" = %s
WHERE "url" = %s;
"""

INSERT_SINGLE_TEMPLATE = """
INSERT INTO {} (
    "name_of_auction", "location", "date_of_a", "time_of_a", "lot", "vin", 
    "year", "make", "model", "engine", "hp", "transmission", "ratio", 
    "mileage", "notes", "repaircosts", "transport_costs", "target_price", 
    "max_bid", "sold_for", "url", "details"
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
);
"""

DELETE_OLD_TEMPLATE = """
DELETE FROM {}
WHERE "date_of_a" >= %s
"""

VIN_IDX = 5
URL_IDX = 20

# --- DATA NORMALIZATION HELPERS ---
def _to_int(value):
    if value is None: return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "tbd"}: return None
    try: return int(float(text))
    except ValueError: return None

def _to_decimal(value):
    if value is None: return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "tbd"}: return None
    try: return Decimal(text)
    except (InvalidOperation, ValueError): return None

def _to_date(value):
    if value is None: return None
    text = str(value).strip()
    if not text: return None
    try: return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError: return None

def _to_time(value):
    if value is None: return None
    text = str(value).strip()
    if not text: return None
    for fmt in ("%I:%M%p", "%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(text, fmt).time()
        except ValueError: continue
    return None

def _normalize_vin(value):
    if value is None: return None
    vin = str(value).strip()
    if not vin or vin.lower() in {"tbd", "none", "nan"}: return None
    return vin[:17]

def _normalize_row(row):
    details_text = row.get("Details") or ""
    source = row.get("URL") or row.get("url")
    return (
        row.get("Name_Of_Auction"),
        row.get("Location"),
        _to_date(row.get("Date")),
        _to_time(row.get("Time")),
        _to_int(row.get("Lot")),
        _normalize_vin(row.get("Vin")),
        _to_int(row.get("Year")),
        row.get("Make"),
        row.get("Model"),
        row.get("Engine"),
        _to_int(row.get("HP")),
        row.get("Transmission"),
        _to_decimal(row.get("Ratio")),
        _to_int(row.get("Mileage")),
        row.get("Notes") or "",
        _to_decimal(row.get("RepairCosts")),
        _to_decimal(row.get("Transport_Costs")),
        _to_decimal(row.get("Target_Price")),
        _to_decimal(row.get("Max_Bid")),
        _to_decimal(row.get("Sold_For")),
        source,
        Json({"raw_text": details_text, "source": source}),
    )

# --- MAIN EXPORT FUNCTION ---
def save_upcoming_auctions(rows, table="upcoming_auctions", delete_future=True):
    """
    Saves scraped items to the specified table.

    Args:
        rows: list of dicts, each with keys like "Name_Of_Auction", "Date", etc.
        table: name of the target PostgreSQL table.
        delete_future: if True, delete all rows where date_of_a >= today before inserting.
    """
    if not rows:
        print(f"No rows to save to DB table: {table}.")
        return

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5435"))
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "a_auctions")

    if not db_user or not db_password:
        raise RuntimeError("DB_USER and DB_PASSWORD must be set in environment variables.")

    values = [_normalize_row(row) for row in rows]
    values_with_vin = [value for value in values if value[VIN_IDX] is not None]
    values_without_vin = [value for value in values if value[VIN_IDX] is None]

    # Deduplicate internal batch duplicates by VIN
    if values_with_vin:
        unique_vin_dict = {}
        for val in values_with_vin:
            unique_vin_dict[val[VIN_IDX]] = val
        values_with_vin = list(unique_vin_dict.values())

    with psycopg2.connect(
        host=db_host, port=db_port, user=db_user, password=db_password, dbname=db_name
    ) as conn:
        with conn.cursor() as cur:
            
            if delete_future:
                delete_sql = sql.SQL(DELETE_OLD_TEMPLATE).format(sql.Identifier(table))
                cur.execute(delete_sql, (date.today(),))
                deleted = cur.rowcount
                print(f"Deleted {deleted} record(s) with date_of_a >= {date.today()} from table '{table}'.")
            
            # 1. Safe dynamic Table Name binding using psycopg2.sql
            final_insert_sql = sql.SQL(INSERT_TEMPLATE).format(sql.Identifier(table))
            final_update_sql = sql.SQL(UPDATE_BY_URL_TEMPLATE).format(sql.Identifier(table))
            final_insert_single_sql = sql.SQL(INSERT_SINGLE_TEMPLATE).format(sql.Identifier(table))

            # 2. Process items containing a VIN (Batch Upsert)
            if values_with_vin:
                execute_values(cur, final_insert_sql, values_with_vin, page_size=200)

            # 3. Process items without a VIN (Fallback URL update loop)
            for value in values_without_vin:
                url = value[URL_IDX]
                if url:
                    update_params = (
                        value[0], value[1], value[2], value[3], value[4], value[5],
                        value[6], value[7], value[8], value[9], value[10], value[11],
                        value[12], value[13], value[14], value[15], value[16], value[17],
                        value[18], value[19], value[21], # details
                        url                              # WHERE target
                    )
                    cur.execute(final_update_sql, update_params)
                    if cur.rowcount > 0:
                        continue

                cur.execute(final_insert_single_sql, value)
                
        conn.commit()
        
    print(f"Successfully saved {len(values)} row(s) to table: {table}.")
    
def save_from_dataframe(df, table="upcoming_auctions", delete_future=True):
    """
    Convert a pandas DataFrame to a list of dicts and call save_upcoming_auctions.

    The DataFrame columns must match the expected keys:
        Name_Of_Auction, Location, Date, Time, Lot, Vin, Year, Make, Model,
        Engine, HP, Transmission, Ratio, Mileage, Notes, RepairCosts,
        Transport_Costs, Target_Price, Max_Bid, Sold_For, URL, Details
    (case-sensitive).
    """
    rows = df.to_dict(orient='records')
    save_upcoming_auctions(rows, table=table, delete_future=delete_future)