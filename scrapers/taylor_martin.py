import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from db_writer import save_upcoming_auctions


OUTPUT_PATH = str(Path(__file__).resolve().parent / "output" / "taylor_martin_trucks.csv")
DEFAULT_BASE_URL = "https://www.taylorandmartin.com"
DEFAULT_PATH = "/live-auctions"
DEFAULT_PARAMS = {
    "types": ["Truck/Tractor"],
    "subtypes": ["Sleeper"],
    "years": ["2026", "2025", "2024", "2023", "2022", "2027"],
    "makes": ["FREIGHTLINER", "VOLVO"],
    "engineMakes": ["Cummins", "Detroit", "Volvo"],
    "ItemCount": "12",
}
CONFIG_PATH = Path(__file__).resolve().parent / "config" / "tm.json"


def load_tm_config():
    config = {
        "base_url": DEFAULT_BASE_URL,
        "path": DEFAULT_PATH,
        "params": dict(DEFAULT_PARAMS),
    }
    if not CONFIG_PATH.exists():
        return config

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            user_config = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: failed to load {CONFIG_PATH.name}, using defaults. {exc}")
        return config

    if isinstance(user_config.get("base_url"), str) and user_config["base_url"].strip():
        config["base_url"] = user_config["base_url"].strip().rstrip("/")
    if isinstance(user_config.get("path"), str) and user_config["path"].strip():
        config["path"] = user_config["path"].strip()

    if isinstance(user_config.get("params"), dict):
        merged = {}
        for key, value in user_config["params"].items():
            if not isinstance(key, str):
                continue
            if isinstance(value, list):
                merged[key] = [str(item) for item in value]
            else:
                merged[key] = str(value)
        config["params"].update(merged)
    return config


def collect_links():
    cfg = load_tm_config()
    baseurl = cfg["base_url"]
    base_path = cfg["path"].lstrip("/")
    params = dict(cfg["params"])
    item_count = str(params.pop("ItemCount", "12"))

    all_links = []
    page = 1

    while True:
        page_params = dict(params)
        page_params["pageNumber"] = str(page)
        page_params["ItemCount"] = item_count
        query = urlencode(page_params, doseq=True)
        url = f"{baseurl}/{base_path}?{query}"
        response = requests.get(url, timeout=40)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        link_div = soup.find("div", attrs={"class": "equipment-list view-grid"})
        if not link_div:
            break

        h3_divs = link_div.find_all("h3")
        if not h3_divs:
            break

        for h3 in h3_divs:
            a = h3.find("a", href=True)
            if a:
                href = a["href"]
                full_url = baseurl + href
                all_links.append(full_url)

        print(f"Page {page} collected {len(h3_divs)} links")
        page += 1
        time.sleep(1)

    print(f"Total collected links: {len(all_links)}")
    return all_links


def truck_data(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"Failed to fetch {url}: {exc}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    name_of_auction = "Taylor&Martin"

    child_div = soup.find("div", class_="equipment-body")
    if not child_div:
        print(f"Could not find truck info in {url}")
        return None

    h3_div = child_div.find("h3")
    truck_model = h3_div.get_text(strip=True) if h3_div else ""
    parts = truck_model.split(" ", 2)
    year = int(parts[0]) if parts and parts[0].isdigit() else None
    truck = parts[1] if len(parts) > 1 else None
    model = parts[2] if len(parts) > 2 else None

    specs = {}
    for div in soup.find_all("div"):
        dt_tags = div.find_all("dt")
        dd_tags = div.find_all("dd")
        for dt, dd in zip(dt_tags, dd_tags):
            key = dt.get_text(strip=True)
            value = dd.get_text(strip=True)
            specs[key] = value

    location = specs.get("Location")
    date = specs.get("Date")
    lot = specs.get("Lot #")
    engine = (specs.get("Engine", "") + " " + specs.get("Engine Description", "")).strip()
    try:
        hp = int(specs.get("Horsepower", "0").replace(",", ""))
    except ValueError:
        hp = None
    mileage = specs.get("Approx. Mileage")

    details = ""
    details_div = child_div.find_all("p")
    for p in details_div:
        if not p.get("class"):
            details = p.get_text(strip=True)

    transmission = None
    if details:
        transmission_match = re.search(r"\b(Automatic|Automated|Manual)\b", details, re.IGNORECASE)
        if transmission_match:
            transmission = transmission_match.group(1)

    ratio = None
    if details:
        ratio_match = re.search(r"(\d+\.?\d*)\s*Ratio", details)
        if ratio_match:
            try:
                ratio = float(ratio_match.group(1))
            except ValueError:
                ratio = None

    data = {
        "Name_Of_Auction": name_of_auction,
        "Location": location,
        "Date": date,
        "Time": None,
        "Lot": int(lot) if lot and lot.isdigit() else None,
        "Vin": "TBD",
        "Year": year,
        "Make": truck,
        "Model": model,
        "Engine": engine if engine else None,
        "HP": hp,
        "Transmission": transmission,
        "Ratio": ratio,
        "Mileage": mileage,
        "Notes": None,
        "RepairCosts": None,
        "Transport_Costs": None,
        "Target_Price": None,
        "Max_Bid": None,
        "Sold_For": None,
        "url": url,
        "Details": details,
    }
    return data


def preprocess_df(df):
    if df.empty:
        return df

    required_columns = ["Date", "Location", "Lot", "Mileage", "Transmission"]
    for column in required_columns:
        if column not in df.columns:
            df[column] = None

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Date"] = df["Date"].dt.strftime("%m/%d/%Y")

    df = df.sort_values(by=["Date", "Location", "Lot"], ascending=[True, True, True])

    df["Mileage_NEW"] = df["Mileage"].replace("Awaiting Verification", np.nan)
    df["Mileage_NEW"] = (
        df["Mileage_NEW"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .replace("nan", np.nan)
        .fillna(0)
        .astype(int)
    )

    df = df[df["Mileage_NEW"] <= 500000]
    df = df.drop("Mileage_NEW", axis=1)
    df = df[df["Transmission"] != "Manual"]

    return df.reset_index(drop=True)


def main():
    all_links = collect_links()
    all_data = []

    for link in all_links:
        truck_info = truck_data(link)
        if truck_info:
            all_data.append(truck_info)
        time.sleep(1)

    df = pd.DataFrame(all_data)
    if df.empty:
        print("No Taylor & Martin records scraped.")
        return

    df = preprocess_df(df)
    output_file = Path(OUTPUT_PATH)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    print(f"Data saved to CSV: {OUTPUT_PATH}")
    save_upcoming_auctions(df.to_dict(orient="records"))


if __name__ == "__main__":
    main()
