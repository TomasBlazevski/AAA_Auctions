import os
from sqlalchemy import create_engine, text

def run_sync():    
    DB_USER = os.getenv("DB_USER", "Tomas")
    DB_PASS = os.getenv("DB_PASS", "celtic46")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "5435")
    DB_NAME = os.getenv("DB_NAME", "a_auctions")
    
    database_uri = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(database_uri)

    sql_script = """
    ROLLBACK;
    BEGIN;
    TRUNCATE TABLE upcoming_auctions RESTART IDENTITY;
    INSERT INTO upcoming_auctions (
        name_of_auction, location, date_of_a, time_of_a, lot, 
        vin, year, make, model, engine, hp, ratio, mileage, url
    ) 
    SELECT 
        name_of_auction, location, date_of_a, time_of_a, lot, 
        vin, year, make, model, engine, hp, ratio, mileage, url 
    FROM rb_trucks_specs
    WHERE date_of_a >= CURRENT_DATE
    
    UNION ALL
    
    SELECT 
        name_of_auction, location, date_of_a, time_of_a, lot, 
        vin, year, make, model, engine, hp, ratio, mileage, url 
    FROM tm_trucks_specs
    WHERE date_of_a >= CURRENT_DATE
    
    ORDER BY date_of_a, name_of_auction;
    COMMIT;
    """

    try:
        print("Starting data sync to upcoming_auctions...")
        with engine.connect() as conn:            
            conn.execute(text(sql_script))
        print("Data sync completed successfully!")
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    run_sync()