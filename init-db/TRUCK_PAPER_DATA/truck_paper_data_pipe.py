import os
import re
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


def clean_and_load_trucks(df, db_config):
    # ----------------------------------------------------
    # 1. PIPELINE: CLEAN DATA
    # ----------------------------------------------------
    df_clean = df.copy()
    
    mfg = df_clean["Engine Manufacturer"].replace("Not found", "").fillna("")
    model = df_clean["Engine Model"].replace("Not found", "").fillna("")
    df_clean["Engine"] = (mfg + " " + model).str.strip()

    df_clean["Mileage"] = (
        df_clean["Mileage"]
        .astype(str)
        .str.replace(r"[^\d]", "", regex=True)
    )
    df_clean["Mileage"] = pd.to_numeric(df_clean["Mileage"], errors="coerce")
    
    df_clean["Price"] = (
        df_clean["Price"]
        .astype(str)
        .str.replace(r"[^\d]", "", regex=True)
    )
    df_clean["Price"] = pd.to_numeric(df_clean["Price"], errors="coerce")
    
    df_clean["HP"] = (
        df_clean["Horsepower"]
        .astype(str)
        .str.replace(r"[^\d]", "", regex=True)
    )
    df_clean["HP"] = pd.to_numeric(df_clean["HP"], errors="coerce")
    
    df_clean["Year"] = (
        df_clean["Year"]
        .astype(str)
        .str.replace(r"[^\d]", "", regex=True)
    )
    df_clean["Year"] = pd.to_numeric(df_clean["Year"], errors="coerce")
    
    text_cols = ["Manufacturer", "Model", "VIN", "Transmission", "URL", "Engine"]
    for col in text_cols:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .str.strip()
            .replace(["Not found", "nan", "None", "Failed (no specs)"], None)
        )
    
    df_clean = df_clean.replace({np.nan: None})
    
    text_cols = ["Manufacturer", "Model", "VIN", "Transmission", "URL", "Engine"]
    for col in text_cols:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .replace(["Not found", "nan", "None"], None)
            .str.strip()
        )
    
    df_clean = df_clean.replace({np.nan: None})

    # ----------------------------------------------------
    # 2. MAP TO POSTGRESQL TABLE COLUMNS
    # ----------------------------------------------------
    
    db_data = list(
        df_clean[
            [
                "Manufacturer",
                "Model",
                "VIN",
                "Year",
                "Mileage",
                "HP",
                "Engine",
                "Transmission",
                "Price",
                "URL",
            ]
        ].itertuples(index=False, name=None)
    )

    # ----------------------------------------------------
    # 3. BULK INSERT INTO POSTGRESQL
    # ----------------------------------------------------
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    try:        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS truck_paper_data (
                id SERIAL PRIMARY KEY,
                Manufacturer TEXT,
                Model VARCHAR(20),
                Vin VARCHAR(17),
                Year INTEGER,
                Mileage INTEGER,
                HP INTEGER,
                Engine TEXT,
                Transmission TEXT,
                Price INTEGER,
                URL TEXT,
                created_at DATE DEFAULT CURRENT_DATE
            );
        """
        )

        insert_query = """
            INSERT INTO truck_paper_data (Manufacturer, Model, Vin, Year, Mileage, HP, Engine, Transmission, Price, URL)
            VALUES %s            
        """

        # Execute all rows at once
        execute_values(cur, insert_query, db_data)
        conn.commit()
        print(f"Successfully processed and loaded {len(db_data)} trucks!")

    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    
    db_config = {
        "dbname": "a_auctions",
        "user": "Tomas",
        "password": "celtic46",
        "host": "127.0.0.1",
        "port": "5435"
    }    
    
    try:
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = input("Enter the CSV filename: ")
        csv_path = os.path.join(script_dir, filename)
        
        df_scraped = pd.read_csv(csv_path) 
        
        print(f"✅ Target file found at: {csv_path}")
        print("Starting the cleaning and loading pipeline...")
        clean_and_load_trucks(df_scraped, db_config)
        
    except FileNotFoundError:
        print(f"Error: Could not find your scraped data file at expected path: {csv_path if 'csv_path' in locals() else 'truck_paper_scraped_2026-06-06.csv'}")