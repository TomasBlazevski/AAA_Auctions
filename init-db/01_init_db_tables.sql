CREATE DATABASE a_auctions;

\c a_auctions;

CREATE TABLE IF NOT EXISTS past_auctions (
	id SERIAL PRIMARY KEY,
    auctioner TEXT,
    location TEXT,
    date DATE,
    year INTEGER,
    make VARCHAR(100),
    model VARCHAR(100),
    engine TEXT,
    hp INTEGER,
    transmission TEXT,
    ratio DECIMAL(5, 2),
    mileage INTEGER,
    notes TEXT,
    repairs_cost DECIMAL(12, 2) DEFAULT 0,
    transport_costs DECIMAL(12, 2) DEFAULT 0,
    target_price DECIMAL(12, 2),
    max_bidding_price DECIMAL(12, 2),
    sold_for DECIMAL(12, 2),
    details JSONB
);

CREATE TABLE IF NOT EXISTS upcoming_auctions (
	id SERIAL PRIMARY KEY,
    Name_Of_Auction TEXT,
    Location TEXT,
    Date_of_A DATE,
	Time_of_A Time,
	Lot Int,
	Vin VARCHAR(17) UNIQUE,
    Year INTEGER,
    Make VARCHAR(100),
    Model VARCHAR(100),
    Engine TEXT,
    HP INTEGER,
    Transmission TEXT,
    Ratio DECIMAL(5, 2),
    Mileage INTEGER,
    Notes TEXT,
    RepairCosts DECIMAL(12, 2) DEFAULT 0,
    Transport_Costs DECIMAL(12, 2) DEFAULT 0,
    Target_Price DECIMAL(12, 2),
    Max_Bid DECIMAL(12, 2),
    Sold_For DECIMAL(12, 2),
	URL TEXT,
	details JSONB
);

CREATE TABLE if not exists truck_paper_data (
	id serial PRIMARY KEY,
	Manufacturer TEXT,
	Model VARCHAR(20),
	Vin VARCHAR(17),
	Year INTEGER,
	Mileage INTEGER,
	HP INTEGER,
	Engine TEXT,
	Transmission TEXT,
	Price INTEGER,
	URL TEXT
);