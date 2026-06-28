\c a_auctions;

BEGIN;

TRUNCATE TABLE upcoming_auctions RESTART IDENTITY;

INSERT INTO upcoming_auctions (name_of_auction, location, date_of_a,
			time_of_a, lot, vin, year, make, model, engine,
			hp, ratio, mileage, url) 
SELECT name_of_auction, location, date_of_a,
			time_of_a, lot, vin, year, make, model, engine,
			hp, ratio, mileage, url FROM rb_trucks_specs
UNION ALL
SELECT name_of_auction, location, date_of_a,
			time_of_a, lot, vin, year, make, model, engine,
			hp, ratio, mileage, url FROM tm_trucks_specs;

COMMIT;