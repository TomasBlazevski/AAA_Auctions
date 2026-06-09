import os
import psycopg2
import holidays
from dotenv import load_dotenv

# Force loading .env explicitly from the current working directory
env_path = os.path.join(os.getcwd(), '.env')
print(f"DEBUG: Looking for .env file at: {env_path}")
load_dotenv(dotenv_path=env_path)

DB_SETTINGS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": "127.0.0.1",
    "port": "5435",
}

print(f"DEBUG: Database Settings Target -> Host: {DB_SETTINGS['host']}, Port: {DB_SETTINGS['port']}, DB: {DB_SETTINGS['dbname']}, User: {DB_SETTINGS['user']}")

def populate_us_holidays():
    if not DB_SETTINGS["dbname"] or not DB_SETTINGS["user"]:
        print("❌ ERROR: Missing database configuration variables! Check your .env file content.")
        return

    try:
        print("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(**DB_SETTINGS)
        cursor = conn.cursor()
        print("⚡ Connected successfully!")

        print("Fetching calendar timelines from 'date' table...")
        cursor.execute("SELECT datekey FROM date ORDER BY datekey;")
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ Date table is empty. Please generate your calendar matrix first!")
            return

        start_year = rows[0][0].year
        end_year = rows[-1][0].year
        
        print(f"Initializing US Federal Holiday engine ({start_year} - {end_year})...")
        us_holiday_engine = holidays.US(years=range(start_year, end_year + 1))

        print("Scanning dates for holiday matches...")
        updates = []
        for row in rows:
            date_item = row[0]
            if date_item in us_holiday_engine:
                holiday_title = us_holiday_engine.get(date_item)
                updates.append((True, holiday_title, date_item))

        if updates:
            print(f"🚀 Found {len(updates)} US Holidays! Syncing to database...")
            update_query = """
                UPDATE date 
                SET isholiday = %s, holidaytext = %s 
                WHERE datekey = %s;
            """
            cursor.executemany(update_query, updates)
            conn.commit()
            print("🎉 Success! Your calendar is now fully loaded with US Federal Holidays.")
        else:
            print("No holidays matched your current calendar range.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Automation process failed completely: {e}")

if __name__ == "__main__":
    print("--- STARTING HOLIDAY EXTRACTION ENGINE ---")
    populate_us_holidays()
    print("--- PROCESS FINISHED ---")