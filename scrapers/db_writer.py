import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2.extras import Json, execute_values
from dotenv import load_dotenv

# Agnostic loading: 
# This looks for a .env file in the folder where you RUN the command.
load_dotenv()

# --- DEBUG TEST ---
db_user = os.getenv('DB_USER')

if db_user:
    print(f"✅ Success: Connected as {db_user}")
else:
    print("❌ Warning: DB_USER not found in environment.")

INSERT_SQL = """
INSERT INTO upcoming_auctions (
    "name_of_auction",
    "location",
    "date_of_a",
    "time_of_a",
    "lot",
    "vin",
    "year",
    "make",
    "model",
    "engine",
    "hp",
    "transmission",
    "ratio",
    "mileage",
    "notes",
    "repaircosts",
    "transport_costs",
    "target_price",
    "max_bid",
    "sold_for",
    "url",
    "details"
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

UPDATE_BY_URL_SQL = """
UPDATE upcoming_auctions
SET
    "name_of_auction" = %s,
    "location" = %s,
    "date_of_a" = %s,
    "time_of_a" = %s,
    "lot" = %s,
    "vin" = %s,
    "year" = %s,
    "make" = %s,
    "model" = %s,
    "engine" = %s,
    "hp" = %s,
    "transmission" = %s,
    "ratio" = %s,
    "mileage" = %s,
    "notes" = %s,
    "repaircosts" = %s,
    "transport_costs" = %s,
    "target_price" = %s,
    "max_bid" = %s,
    "sold_for" = %s,
    "details" = %s
WHERE "url" = %s;
"""

INSERT_SINGLE_SQL = """
INSERT INTO upcoming_auctions (
    "name_of_auction",
    "location",
    "date_of_a",
    "time_of_a",
    "lot",
    "vin",
    "year",
    "make",
    "model",
    "engine",
    "hp",
    "transmission",
    "ratio",
    "mileage",
    "notes",
    "repaircosts",
    "transport_costs",
    "target_price",
    "max_bid",
    "sold_for",
    "url",
    "details"
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
);
"""

VIN_IDX = 5
URL_IDX = 20


def _to_int(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "tbd"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _to_decimal(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "tbd"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _to_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def _to_time(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%I:%M%p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _normalize_vin(value):
    if value is None:
        return None
    vin = str(value).strip()
    if not vin or vin.lower() in {"tbd", "none", "nan"}:
        return None
    return vin[:17]


def _normalize_row(row):
    details_text = row.get("Details") or ""
    source = row.get("URL") or row.get("url")

    repair_cost = _to_decimal(row.get("RepairCosts"))
    notes = row.get("Notes") or ""

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
        notes,
        repair_cost,
        _to_decimal(row.get("Transport_Costs")),
        _to_decimal(row.get("Target_Price")),
        _to_decimal(row.get("Max_Bid")),
        _to_decimal(row.get("Sold_For")),
        source,
        Json({"raw_text": details_text, "source": source}),
    )


def save_upcoming_auctions(rows):
    if not rows:
        print("No rows to save to DB.")
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

    # 🛠️ PREVENT CARDINALITY ERROR: Keep only the newest duplicate row inside this batch array.
    # Because we are processing oldest to newest, assigning keys sequentially to a dictionary
    # ensures that if a duplicate VIN is found, the NEWEST record overwrites the old one.
    if values_with_vin:
        unique_vin_dict = {}
        for val in values_with_vin:
            vin_key = val[VIN_IDX]
            unique_vin_dict[vin_key] = val # Fresh record forces the drop of the older internal clone
        
        values_with_vin = list(unique_vin_dict.values())

    with psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname=db_name,
    ) as conn:
        with conn.cursor() as cur:
            if values_with_vin:
                execute_values(cur, INSERT_SQL, values_with_vin, page_size=200)

            for value in values_without_vin:
                url = value[URL_IDX]
                if url:
                    update_params = (
                        value[0],
                        value[1],
                        value[2],
                        value[3],
                        value[4],
                        value[5],
                        value[6],
                        value[7],
                        value[8],
                        value[9],
                        value[10],
                        value[11],
                        value[12],
                        value[13],
                        value[14],
                        value[15],
                        value[16],
                        value[17],
                        value[18],
                        value[19],
                        value[21],
                        url,
                    )
                    cur.execute(UPDATE_BY_URL_SQL, update_params)
                    if cur.rowcount > 0:
                        continue

                cur.execute(INSERT_SINGLE_SQL, value)
        conn.commit()
    print(f"Saved {len(values)} row(s) to upcoming_auctions.")