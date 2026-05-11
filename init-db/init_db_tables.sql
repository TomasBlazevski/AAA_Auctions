CREATE DATABASE a_auctions;

\c a_auctions;

CREATE TABLE past_auctions (
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