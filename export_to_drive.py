import datetime
import os.path
import gspread
import pandas as pd
import psycopg2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. SYSTEM CONFIGURATIONS (HIDDEN SECURELY)
# ==========================================

DB_SETTINGS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": "127.0.0.1",
    "port": "5435",
}

# The scopes required to access Google Sheets and Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_user_authenticated_client():
    """Authenticates using your actual user profile via browser login"""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run so you don't have to log in every time
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return gspread.authorize(creds)


# ==========================================
# 2. CORE UTILITY FUNCTIONS
# ==========================================


def fetch_data_from_view(view_name):
    try:
        conn = psycopg2.connect(**DB_SETTINGS)
        query = f"SELECT * FROM {view_name};"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        df = df.fillna("")  # Replace NaN with empty strings for better Google Sheets compatibility

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

    print("Authenticating with your Google Account...")
    try:
        client = get_user_authenticated_client()
    except Exception as e:
        print(f"Authentication failed: {e}")
        return

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    sheet_title = f"AAA Auctions Report ({today_str})"

    try:
        print(f"Creating new spreadsheet: '{sheet_title}'...")
        # This will now safely create the file directly using YOUR corporate account storage
        spreadsheet = client.create(sheet_title)

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
            "👉 Look at your main Google Drive dashboard! The file is sitting right there."
        )

    except Exception as e:
        print(f"\n❌ Google Sheets API Process failed: {e}")


if __name__ == "__main__":
    export_and_share()