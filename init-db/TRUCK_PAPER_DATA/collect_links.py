import json
import time
from pathlib import Path

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SEARCH_URL = (
    "https://www.truckpaper.com/listings/search?Category=16045&ListingType=For%20Retail"
    "&Manufacturer=FREIGHTLINER%7CVOLVO&Year=2022%2A2027&Mileage=%2A500000"
    "&Engine=DETROIT%7CVOLVO&Sleeper=Raised%20Roof%20Sleeper&Country=178"
    "&Transmission=Automated%7CAutomatic"
)
DEFAULT_TOTAL_PAGES = 80
DEFAULT_OUTPUT = SCRIPT_DIR / "truckpaper_all_links.json"
CHROME_VERSION = 148


def _make_driver(chrome_version=CHROME_VERSION):
    options = uc.ChromeOptions()
    options.set_capability("unhandledPromptBehavior", "dismiss")
    return uc.Chrome(version_main=chrome_version, options=options)


def collect_links(
    search_url=DEFAULT_SEARCH_URL,
    total_pages=DEFAULT_TOTAL_PAGES,
    output_path=DEFAULT_OUTPUT,
    chrome_version=CHROME_VERSION,
):
    all_links = []
    driver = _make_driver(chrome_version)
    wait = WebDriverWait(driver, 15)

    try:
        for page_num in range(1, total_pages + 1):
            page_url = search_url if page_num == 1 else f"{search_url}&page={page_num}"
            print(f"Fetching page {page_num}/{total_pages}: {page_url}")

            try:
                driver.get(page_url)
                wait.until(EC.presence_of_element_located((By.ID, "listContainer")))
            except (UnexpectedAlertPresentException, TimeoutException):
                print(
                    f"  Page layout glitch or alert on page {page_num}. Refreshing..."
                )
                time.sleep(2)
                try:
                    driver.refresh()
                    time.sleep(3)
                    wait.until(EC.presence_of_element_located((By.ID, "listContainer")))
                except Exception:
                    print(f"  Failed to load page {page_num} after refresh. Skipping.")
                    continue

            soup = BeautifulSoup(driver.page_source, "html.parser")
            links_on_page = []
            for anchor in soup.find_all("a", class_="view-listing-details-link"):
                href = anchor.get("href")
                if href:
                    links_on_page.append("https://www.truckpaper.com" + href)

            print(f"  Found {len(links_on_page)} listing URLs")
            all_links.extend(links_on_page)
            time.sleep(2)
    finally:
        driver.quit()

    unique_links = list(dict.fromkeys(all_links))
    output_path = Path(output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(unique_links, file, indent=2)

    print(f"\nDone! Total unique listing URLs: {len(unique_links)}")
    print(f"Saved to: {output_path}")
    return unique_links


if __name__ == "__main__":
    collect_links()
