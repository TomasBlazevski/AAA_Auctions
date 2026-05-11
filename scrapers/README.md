# Scrapers Organization

This folder now uses a simple non-breaking structure:

- `taylor_martin.py`: core Taylor & Martin scraper implementation.
- `rb_scraper.py`: core Ritchie Bros scraper implementation.
- `taylor_martin_scraper.py`: compatibility wrapper that runs `taylor_martin.main()`.
- `RB_scraper_V2.py`: compatibility wrapper that runs `rb_scraper.main()`.
- `config/tm.json`: Taylor & Martin URL/filter parameters.
- `config/rb.json`: Ritchie Bros URL/filter parameters.

You can keep running the old filenames exactly as before, while gradually importing from the new core modules for cleaner reuse.

## Updating filters in production

Update only the JSON files in `scrapers/config/` to change auction filters, years, makes, or page sizes.
If a config file is missing or invalid, scraper code falls back to built-in defaults.
