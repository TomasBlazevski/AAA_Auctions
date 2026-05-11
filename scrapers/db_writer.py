import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2.extras import Json, execute_values


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
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
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
    notes = row.get("Notes")
    if repair_cost is None and row.get("RepairCosts"):
        extra_note = f"RepairCosts raw value: {row.get('RepairCosts')}"
        notes = f"{notes} | {extra_note}" if notes else extra_note

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

    with psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname=db_name,
    ) as conn:
        with conn.cursor() as cur:
            execute_values(cur, INSERT_SQL, values, page_size=200)
        conn.commit()
    print(f"Saved {len(values)} row(s) to upcoming_auctions.")
