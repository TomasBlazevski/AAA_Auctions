import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LINKS_FILE = SCRIPT_DIR / "truckpaper_all_links.json"
CHROME_VERSION = 150
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


# ------------------------------------------------------------
#  CUSTOM DRIVER (fixes OSError: [WinError 6])
# ------------------------------------------------------------
class SafeChrome(uc.Chrome):
    def __del__(self):
        try:
            super().__del__()
        except OSError:
            pass


def _make_driver():
    options = uc.ChromeOptions()
    options.set_capability("unhandledPromptBehavior", "dismiss")
    if CHROME_VERSION:
        return SafeChrome(version_main=CHROME_VERSION, options=options)
    return SafeChrome(options=options)


# ------------------------------------------------------------
#  LOAD LINKS
# ------------------------------------------------------------
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


# ------------------------------------------------------------
#  OUTPUT HELPERS
# ------------------------------------------------------------
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


# ------------------------------------------------------------
#  DATA EXTRACTION
# ------------------------------------------------------------
def _extract_listing(html, url):
    if (
        "Pardon Our Interruption" in html
        or "Access Denied" in html
        or ("cloudflare" in html.lower() and "checking your browser" in html.lower())
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


# ------------------------------------------------------------
#  MAIN SCRAPER (with timer)
# ------------------------------------------------------------
def scrape_listings(
    links,
    csv_path=None,
    json_path=None,
    chrome_version=CHROME_VERSION,
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

    print(f"Launching pipeline for {total_links} links (single browser session)...")
    start_time = time.time()

    driver = _make_driver()
    wait = WebDriverWait(driver, 15)

    try:
        for idx, url in enumerate(links, start=1):
            item_start = time.time()

            print(f"\nProcessing {idx}/{total_links}: {url[:80]}...")

            try:
                driver.get(url)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "detail__specs")))
                time.sleep(1)

                html = driver.page_source
                row, block_reason = _extract_listing(html, url)

                if block_reason == "cloudflare":
                    print("Cloudflare barrier detected.")
                    print("Complete any CAPTCHA in the browser, then press ENTER...")
                    input()
                    html = driver.page_source
                    row, _ = _extract_listing(html, url)

                if row is None:
                    row = {"URL": url, "Price": "Error"}
                    for field in REQUIRED_FIELDS:
                        if field != "Price":
                            row[field] = "Scraping error"
                else:
                    print(f"  {row['Year']} {row['Manufacturer']} {row['Model']} | Price: {row['Price']}")

            except Exception as exc:
                print(f"  Error: {exc}")
                row = {"URL": url, "Price": "Error"}
                for field in REQUIRED_FIELDS:
                    if field != "Price":
                        row[field] = "Scraping error"

            results.append(row)

            item_elapsed = time.time() - item_start
            print(f"  ⏱️ Item took {item_elapsed:.1f}s")

            if idx % save_interval == 0:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta_seconds = (total_links - idx) / rate if rate > 0 else 0
                eta_str = str(timedelta(seconds=int(eta_seconds)))
                print(f"\n💾 Auto-save: syncing {len(results)} items to disk...")
                print(f"   ⏱️ Total elapsed: {str(timedelta(seconds=int(elapsed)))}")
                print(f"   📊 Avg. rate: {rate:.2f} items/s | Est. remaining: {eta_str}")
                _save_results(results, csv_path, json_path)

            time.sleep(random.uniform(1, 5))

    finally:
        print("Closing browser...")
        try:
            driver.quit()
        except Exception:
            pass

    _save_results(results, csv_path, json_path)
    
    total_elapsed = time.time() - start_time
    total_str = str(timedelta(seconds=int(total_elapsed)))
    print(f"\n✅ Finished! Scraped {len(results)} listings.")
    print(f"   ⏱️ Total runtime: {total_str}")
    print(f"   💾 Saved to: {csv_path} and {json_path}")
    return results


if __name__ == "__main__":
    links = load_links()
    scrape_listings(links)