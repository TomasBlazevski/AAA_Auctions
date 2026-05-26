import datetime
import gspread
import pandas as pd
import psycopg2
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SYSTEM CONFIGURATIONS
# ==========================================

# Database settings matched exactly to your Docker .env file
DB_SETTINGS = {
    "dbname": "a_auctions",
    "user": "Tomas",
    "password": "celtic46",
    "host": "127.0.0.1",  # Explicitly forces IPv4 connection
    "port": "5435",  # Docker host-mapped port
}

# The target corporate email addresses to receive the report
TARGET_EMAILS = [
    "tomas.b@aaalease.net",
    # "coworker@aaalease.net"  # <-- Uncomment and add your coworker's email here later if needed
]

# Google Sheets API Auth setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDS_FILE = "service_account.json"

# ==========================================
# 2. CORE UTILITY FUNCTIONS
# ==========================================


def fetch_data_from_view(view_name):
    """Connects to Postgres and extracts view data into a DataFrame"""
    try:
        conn = psycopg2.connect(**DB_SETTINGS)
        query = f"SELECT * FROM {view_name};"
        df = pd.read_sql_query(query, conn)
        conn.close()

        # FIXED: Added the missing 'in' keyword here 
        for col in df.select_dtypes(
            include=["datetime", "datetimetz", "object"]
        ).columns:
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
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)

    # Generate a dynamic title based on today's date
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    sheet_title = f"AAA Auctions Report ({today_str})"

    try:
        print(f"Creating new spreadsheet: '{sheet_title}'...")
        # Create the file in the Service Account's baseline space to bypass corporate 404 block
        spreadsheet = client.create(sheet_title)

        # Loop through and share with everyone in TARGET_EMAILS as an Editor
        for email in TARGET_EMAILS:
            print(f"Sharing editing access with {email}...")
            spreadsheet.share(email, perm_type="user", role="writer")

        # --- Populate Sheet 1: Auctions Next 7 Days ---
        print("Populating 'Next 7 Days' worksheet...")
        worksheet_7_days = spreadsheet.get_worksheet(0)
        worksheet_7_days.update_title("Next 7 Days")
        worksheet_7_days.update(
            [df_7_days.columns.values.tolist()] + df_7_days.values.tolist()
        )

        # --- Populate Sheet 2: Auctions Today ---
        print("Populating 'Auctions Today' worksheet...")
        worksheet_today = spreadsheet.add_worksheet(
            title="Auctions Today",
            rows=str(len(df_today) + 50),
            cols=str(len(df_today.columns)),
        )
        worksheet_today.update(
            [df_today.columns.values.tolist()] + df_today.values.tolist()
        )

        print("\n🎉 Success! The report has been compiled completely.")
        print(
            "👉 Check your 'Shared with me' tab in Google Drive to view and organize the file!"
        )

    except Exception as e:
        print(f"\n❌ Google Sheets API Process failed: {e}")


# ==========================================
# 3. EXECUTION RUNNER
# ==========================================
if __name__ == "__main__":
    export_and_share()