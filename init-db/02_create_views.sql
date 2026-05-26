\c a_auctions;

-- 1. View for today's date up to the next 7 days
CREATE OR REPLACE VIEW view_auctions_next_7_days AS
SELECT 
    id, Name_Of_Auction, Location, Date_of_A, Time_of_A, Lot, Vin, 
    Year, Make, Model, Engine, HP, Transmission, Mileage, Target_Price, URL
FROM upcoming_auctions
WHERE Date_of_A >= CURRENT_DATE 
  AND Date_of_A <= CURRENT_DATE + INTERVAL '7 days'
ORDER BY Date_of_A ASC, Time_of_A ASC;

-- 2. View for ONLY today's records
CREATE OR REPLACE VIEW view_auctions_today AS
SELECT 
    id, Name_Of_Auction, Location, Date_of_A, Time_of_A, Lot, Vin, 
    Year, Make, Model, Engine, HP, Transmission, Mileage, Target_Price, URL
FROM upcoming_auctions
WHERE Date_of_A = CURRENT_DATE
ORDER BY Time_of_A ASC;