import requests
from bs4 import BeautifulSoup
import re
import time
import pandas as pd
import numpy as np

# -----------------------------
# Collect all links
# -----------------------------
def collect_links():
    baseurl = "https://www.taylorandmartin.com"
    start_url = (
        "https://www.taylorandmartin.com/live-auctions?types=Truck%2FTractor"
        "&subtypes=Sleeper&years=2026&years=2025&years=2024&years=2023&years=2022&years=2027"
        "&makes=FREIGHTLINER&makes=VOLVO"
        "&engineMakes=Cummins&engineMakes=Detroit&engineMakes=Volvo"
    )

    all_links = []
    page = 1

    while True:
        url = f"{start_url}&pageNumber={page}&ItemCount=12"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        link_div = soup.find('div', attrs={'class': 'equipment-list view-grid'})
        if not link_div:
            break

        h3_divs = link_div.find_all('h3')
        if not h3_divs:
            break

        for h3 in h3_divs:
            a = h3.find('a', href=True)
            if a:
                href = a['href']
                full_url = baseurl + href
                all_links.append(full_url)

        print(f"Page {page} collected {len(h3_divs)} links")
        page += 1
        time.sleep(1)  # polite delay

    print(f"✅ Total collected links: {len(all_links)}")
    return all_links

# -----------------------------
# Extract data for one truck
# -----------------------------
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
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    data = {}
    NameOfAuction = "Taylor&Martin"

    child_div = soup.find("div", class_="equipment-body")
    if not child_div:
        print(f"⚠️ Could not find truck info in {url}")
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
        "Name_Of_Auction": NameOfAuction,
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
        "url": url,
        "Details": details,
    }

    return data

# -----------------------------
# Run scraper
# -----------------------------

def preprocess_df(df):

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Date'] = df['Date'].dt.strftime('%m/%d/%Y')

    df = df.sort_values(by=['Date', 'Location', 'Lot'], ascending=[True, True, True])

    df['Mileage_NEW'] = df['Mileage'].replace('Awaiting Verification', np.nan)
    df['Mileage_NEW'] = ( df['Mileage_NEW'] .astype(str).str.replace(',', '', regex=False).replace('nan', np.nan).fillna(0).astype(int) )

    df = df[df['Mileage_NEW'] <= 500000]
    df = df.drop('Mileage_NEW', axis=1)
    df = df[df['Transmission'] != 'Manual']

    df = df.reset_index(drop=True)

    return df

if __name__ == "__main__":
    all_links = collect_links()
    all_data = []

    for link in all_links:
        truck_info = truck_data(link)
        if truck_info:
            all_data.append(truck_info)
        time.sleep(1)

    df = pd.DataFrame(all_data)
    df = preprocess_df(df)
    df.to_csv("/content/drive/MyDrive/Colab Notebooks/taylor_martin_trucks.csv", index=False)
    print("✅ Data saved to CSV")
