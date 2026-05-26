import psycopg2
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# =====================================================================
# CONFIGURATION
# =====================================================================
DB_SETTINGS = {
    "dbname": "a_auctions",
    "user": "Tomas",
    "password": "celtic46",
    "host": "localhost",
    "port": "5432"
}

CO_WORKER_EMAIL = "tomislavblazevski46@gmail.com" 

GOOGLE_CREDS_FILE = "service_account.json" 
# =====================================================================

def fetch_data_from_view(view_name):
    """Connects to Postgres and extracts view data into a DataFrame"""
    try:
        conn = psycopg2.connect(**DB_SETTINGS)
        query = f"SELECT * FROM {view_name};"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert any datetime/date columns to strings so Google Sheets can ingest them easily
        for col in df.select_dtypes(include=['datetime', 'datetimetz', 'object']).columns:
            df[col] = df[col].astype(str)
            
        return df
    except Exception as e:
        print(f"Error fetching data from {view_name}: {e}")
        return None

def export_and_share():
    print("Fetching data from PostgreSQL views...")
    df_7_days = fetch_data_from_view("view_auctions_next_7_days")
    df_today = fetch_data_from_view("view_auctions_today")
    
    if df_7_days is None or df_today is None:
        print("Export aborted due to database errors.")
        return

    print("Authenticating with Google Drive API...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
    client = gspread.authorize(creds)

    # Create a unique title using today's date
    today_str = datetime.now().strftime("%Y-%m-%d")
    sheet_title = f"AAA Auctions Report ({today_str})"
    
    print(f"Creating new spreadsheet: '{sheet_title}'...")
    spreadsheet = client.create(sheet_title)

    # Tab 1: Next 7 Days
    sheet_7 = spreadsheet.get_worksheet(0)
    sheet_7.update_title("Next 7 Days")
    # Format data: includes headers + rows
    data_7 = [df_7_days.columns.values.tolist()] + df_7_days.values.tolist()
    sheet_7.update(data_7)

    # Tab 2: Today Only
    sheet_today = spreadsheet.add_worksheet(title="Today Only", rows="100", cols="20")
    data_today = [df_today.columns.values.tolist()] + df_today.values.tolist()
    sheet_today.update(data_today)

    print(f"Sharing spreadsheet with {CO_WORKER_EMAIL}...")
    spreadsheet.share(CO_WORKER_EMAIL, perm_type='user', role='writer')

    print(f"🎉 Success! Sheet created and shared. Link: {spreadsheet.url}")

if __name__ == "__main__":
    export_and_share()