import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LINKS_FILE = SCRIPT_DIR / "truckpaper_all_links.json"
CHROME_VERSION = 148
MAX_SESSION_MINUTES = 30
SAVE_INTERVAL = 100

REQUIRED_FIELDS = [
    "Year",
    "Manufacturer",
    "Model",
    "Mileage",
    "VIN",
    "Horsepower",
    "Engine Manufacturer",
    "Engine Model",
    "Transmission",
    "Sleeper Size",
    "Price",
]


def load_links(links_path=DEFAULT_LINKS_FILE):
    links_path = Path(links_path)
    suffix = links_path.suffix.lower()

    if suffix == ".json":
        with links_path.open(encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return [link.strip() for link in data if isinstance(link, str) and link.strip()]
        if isinstance(data, dict) and isinstance(data.get("links"), list):
            return [
                link.strip()
                for link in data["links"]
                if isinstance(link, str) and link.strip()
            ]
        raise ValueError(f"Unsupported JSON format in {links_path}")

    if suffix == ".csv":
        df = pd.read_csv(links_path)
        column = "URL" if "URL" in df.columns else df.columns[0]
        return [str(url).strip() for url in df[column].dropna() if str(url).strip()]

    lines = links_path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def _default_output_paths():
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        SCRIPT_DIR / f"truck_listings_{today}.csv",
        SCRIPT_DIR / f"truck_listings_{today}.json",
    )


def _save_results(results, csv_path, json_path):
    pd.DataFrame(results).to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)


def _extract_listing(html, url):
    if (
        "Pardon Our Interruption" in html
        or "Access Denied" in html
        or (
            "cloudflare" in html.lower()
            and "checking your browser" in html.lower()
        )
    ):
        return None, "cloudflare"

    soup = BeautifulSoup(html, "html.parser")

    price_tag = soup.find("strong", class_="listing-prices__retail-price")
    if price_tag:
        price = price_tag.get_text(strip=True)
    else:
        match = re.search(r"\$\d{1,3}(?:,\d{3})*", html)
        price = match.group(0) if match else "Not found"

    specs = {}
    specs_container = soup.find("div", class_="detail__specs")
    if specs_container:
        wrappers = specs_container.find_all("div", class_="detail__specs-wrapper")
        for wrapper in wrappers:
            labels = wrapper.find_all("div", class_="detail__specs-label")
            values = wrapper.find_all("div", class_="detail__specs-value")
            for label, value in zip(labels, values):
                specs[label.get_text(strip=True)] = value.get_text(
                    strip=True, separator=" "
                )
    else:
        print("  Specs container not found - data may be missing")

    row = {"URL": url, "Price": price}
    for field in REQUIRED_FIELDS:
        if field != "Price":
            row[field] = specs.get(field, "Not found")
    return row, None


def scrape_listings(
    links,
    csv_path=None,
    json_path=None,
    chrome_version=CHROME_VERSION,
    max_session_minutes=MAX_SESSION_MINUTES,
    save_interval=SAVE_INTERVAL,
):
    if not links:
        print("No links to scrape.")
        return []

    if csv_path is None or json_path is None:
        default_csv, default_json = _default_output_paths()
        csv_path = csv_path or default_csv
        json_path = json_path or default_json

    csv_path = Path(csv_path)
    json_path = Path(json_path)
    results = []
    total_links = len(links)
    current_idx = 0

    print(f"Launching pipeline for {total_links} links...")

    while current_idx < total_links:
        session_start_time = time.time()
        print("\nInitializing Chrome process (30-minute session TTL)...")

        driver = uc.Chrome(version_main=chrome_version)
        driver.maximize_window()

        try:
            while current_idx < total_links:
                elapsed_minutes = (time.time() - session_start_time) / 60
                if elapsed_minutes >= max_session_minutes:
                    print(
                        f"\nSession hit {elapsed_minutes:.1f} minutes. Recycling browser..."
                    )
                    break

                url = links[current_idx]
                display_idx = current_idx + 1
                print(
                    f"\nProcessing {display_idx}/{total_links} "
                    f"(session {elapsed_minutes:.1f}m): {url[:80]}..."
                )

                try:
                    driver.get(url)
                    time.sleep(3)
                    html = driver.page_source

                    row, block_reason = _extract_listing(html, url)
                    if block_reason == "cloudflare":
                        print("Cloudflare barrier detected.")
                        print(
                            "Complete any CAPTCHA in the browser, then press ENTER..."
                        )
                        input()
                        html = driver.page_source
                        row, _ = _extract_listing(html, url)

                    if row is None:
                        row = {"URL": url, "Price": "Error"}
                        for field in REQUIRED_FIELDS:
                            if field != "Price":
                                row[field] = "Scraping error"
                    else:
                        print(
                            f"  {row['Year']} {row['Manufacturer']} {row['Model']} "
                            f"| Price: {row['Price']}"
                        )

                except Exception as exc:
                    print(f"  Error: {exc}")
                    row = {"URL": url, "Price": "Error"}
                    for field in REQUIRED_FIELDS:
                        if field != "Price":
                            row[field] = "Scraping error"

                results.append(row)
                current_idx += 1

                if display_idx % save_interval == 0:
                    print(f"\nAuto-save: syncing {len(results)} items to disk...")
                    _save_results(results, csv_path, json_path)

                time.sleep(random.uniform(1, 5))
        finally:
            print("Closing browser...")
            try:                
                driver.quit()
            except Exception:
                pass

    _save_results(results, csv_path, json_path)
    print(f"\nFinished! Scraped {len(results)} listings.")
    print(f"Saved to: {csv_path} and {json_path}")
    return results


if __name__ == "__main__":
    links = load_links()
    scrape_listings(links)
