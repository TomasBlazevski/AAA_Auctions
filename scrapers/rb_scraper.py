import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup


OUTPUT_PATH = "/content/drive/MyDrive/Colab Notebooks/rb_auctions.csv"
DEFAULT_BASE_URL = "https://www.rbauction.com/cp/tandem-axle-sleeper-truck-tractor"
DEFAULT_PARAMS = {
    "rbaLocationLevelOne": "USA",
    "manufactureYearRange": "2022-2027",
    "manufacturers": "Freightliner,Volvo",
    "usageMilesRange": "1000-500000",
    "size": "60",
}
CONFIG_PATH = Path(__file__).resolve().parent / "config" / "rb.json"


def load_rb_config():
    config = {"base_url": DEFAULT_BASE_URL, "params": dict(DEFAULT_PARAMS)}
    if not CONFIG_PATH.exists():
        return config

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            user_config = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: failed to load {CONFIG_PATH.name}, using defaults. {exc}")
        return config

    if isinstance(user_config.get("base_url"), str) and user_config["base_url"].strip():
        config["base_url"] = user_config["base_url"].strip()

    if isinstance(user_config.get("params"), dict):
        config["params"].update(
            {k: str(v) for k, v in user_config["params"].items() if isinstance(k, str)}
        )
    return config


def collect_links():
    cfg = load_rb_config()
    base_url = cfg["base_url"]
    params = cfg["params"]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def fetch_page(from_param):
        params["from"] = from_param
        response = requests.get(base_url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    all_links = set()
    page = 0

    while True:
        soup = fetch_page(page * 60)
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/pdp/" in href:
                if not href.startswith("https://www.rbauction.com"):
                    href = "https://www.rbauction.com" + href
                links.append(href)

        if not links:
            break

        all_links.update(links)
        print(f"Page {page + 1}: collected {len(links)} links")
        page += 1
        time.sleep(1)

    all_links = list(all_links)
    print(f"Total collected links: {len(all_links)}")
    return all_links, headers


def truck_data_v2(url, headers):
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag:
        raise Exception("Could not find __NEXT_DATA__ script")

    json_data = json.loads(script_tag.string)

    try:
        item = json_data["props"]["pageProps"]["data"]["results"]["records"][0]

        timestamp_ms = item["biddingEndTime"]
        tz_str = item["eventTimeZone"]
        dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        local_tz = ZoneInfo(tz_str)
        dt_local = dt_utc.astimezone(local_tz) if dt_utc else None
        date = dt_utc.strftime("%m/%d/%Y")
        time_str = dt_local.strftime("%I:%M%p").lstrip("0").lower() if dt_local else None

        yop = item.get("manufactureYear")
        vin = item.get("serialNumber")
        make = item.get("manufacturerLocalized")
        model = item.get("modelLocalized")
        inspection_status = item.get("inspectionStatus")
        miles = item.get("usageMiles")

        loc_city = item.get("locationCity")
        loc_state = item.get("locationState")
        loc = f"{loc_city}, {loc_state}" if loc_city and loc_state else "Not Found"

        lot = item.get("lotNumber", "TBD")
        features = item.get("features", "")
    except (KeyError, IndexError) as exc:
        raise Exception(f"Could not extract data from __NEXT_DATA__ script: {exc}") from exc

    engine_name, hp = None, None
    hp_match = re.search(r"(\d{2,4}(?:,\d{3})?)\s*(?:hp|horsepower)\b", features, re.IGNORECASE)
    if hp_match:
        hp = int(hp_match.group(1).replace(",", ""))
        engine_section = features[: hp_match.start()].strip().rstrip(",;:- ")
        engine_match = re.search(
            r"\b(Cummins|Detroit|Paccar|International|Volvo|Mack|CAT|Caterpillar)\s*([A-Z]?\d+[A-Z]*)\b",
            engine_section,
            re.IGNORECASE,
        )
        if engine_match:
            engine_name = f"{engine_match.group(1)}{engine_match.group(2)}"
        else:
            clean_engine = re.sub(
                r"\b(\d+(?:\.\d+)?\s*[L]?|Cylinder|Diesel|Gasoline|Electric|Hybrid)\b",
                "",
                engine_section,
                flags=re.IGNORECASE,
            )
            engine_name = " ".join(clean_engine.split()).replace(" ", "")
    engine = engine_name

    transmission = None
    transmission_match = re.search(r"\b(Automated|Automatic|Manual)\b", features, re.IGNORECASE)
    if transmission_match:
        transmission = transmission_match.group(1)

    sleeper = None
    sleeper_match = re.search(
        r"(\d+\s*in\s*(?:[A-Za-z\s]+)?Sleeper\s*Cab(?:\s*[A-Za-z\s]*)?)",
        features,
        re.IGNORECASE,
    )
    if sleeper_match:
        sleeper = sleeper_match.group(1).strip().rstrip(",;:- ")

    data = {
        "Name_Of_Auction": "Richie Bros",
        "Location": loc,
        "Date": date,
        "Time": time_str,
        "Lot": lot,
        "Vin": vin,
        "Year": yop,
        "Make": make,
        "Model": model,
        "Engine": engine,
        "HP": hp,
        "Transmission": transmission,
        "Ratio": "",
        "Mileage": miles,
        "Notes": None,
        "RepairCosts": inspection_status,
        "Transport_Costs": "",
        "Target_Price": "",
        "Max_Bid": "",
        "Sold_For": "",
        "URL": url,
        "Details": features,
        "Sleeper": sleeper,
    }
    return data


def main():
    all_links, headers = collect_links()

    all_data = []
    for link in all_links:
        try:
            truck = truck_data_v2(link, headers)
            all_data.append(truck)
            print(f"Scraped: {link}")
            time.sleep(1)
        except Exception as exc:
            print(f"Error scraping {link}: {exc}")

    df_rb = pd.DataFrame(all_data)
    df_rb = df_rb[df_rb["Transmission"] != "Manual"]
    df_rb = df_rb[~df_rb["Engine"].str.contains("Paccar", case=False, na=False)]
    df_rb = df_rb[~df_rb["Sleeper"].str.contains(r"Mid[-\s]?Roof", case=False, na=False)]
    df_rb = df_rb.sort_values(by=["Date", "Location", "Lot"], ascending=[True, True, True])
    df_rb = df_rb.reset_index(drop=True)

    df_rb.to_csv(OUTPUT_PATH, index=False)
    print(f"Data saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
