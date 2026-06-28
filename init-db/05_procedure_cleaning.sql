CREATE OR REPLACE PROCEDURE process_truck_paper_batch()
LANGUAGE plpgsql
AS $$
BEGIN

    INSERT INTO truck_paper_data (
        manufacturer, model, vin, year, mileage,
        hp, engine, transmission, price, url, created_at
    )
    SELECT
        manufacturer,
        model,
        NULLIF(vin, '') AS vin,
        year,
        mileage,
        hp,
        engine,
        transmission,
        price,
        url,
        created_at
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY vin, created_at, price
                   ORDER BY id
               ) AS rn
        FROM staging_truck_paper_data
        WHERE vin IS NOT NULL
          AND vin NOT IN ('null', '[null]', '')
    ) t
    WHERE rn = 1;

    INSERT INTO dump_truck_paper (
        manufacturer, model, vin, year, mileage,
        hp, engine, transmission, price, url, created_at
    )
    SELECT
        manufacturer,
        model,
        NULLIF(vin, '') AS vin,
        year,
        mileage,
        hp,
        engine,
        transmission,
        price,
        url,
        created_at
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY vin, created_at, price
                   ORDER BY id
               ) AS rn
        FROM staging_truck_paper_data
        WHERE vin IS NOT NULL
          AND vin NOT IN ('null', '[null]', '')
    ) t
    WHERE rn > 1;

    INSERT INTO truck_paper_data (
        manufacturer, model, vin, year, mileage,
        hp, engine, transmission, price, url, created_at
    )
    SELECT
        manufacturer, model, NULL, year, mileage,
        hp, engine, transmission, price, url, created_at
    FROM staging_truck_paper_data
    WHERE vin IS NULL
       OR vin IN ('null', '[null]', '');

    TRUNCATE staging_truck_paper_data;

END;
$$;