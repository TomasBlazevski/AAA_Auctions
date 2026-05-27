    DROP TABLE IF EXISTS date;

CREATE TABLE date
(
    datekey                DATE NOT NULL,
    day                    SMALLINT NOT NULL,
    daysuffix              CHAR(2) NOT NULL,
    weekday                SMALLINT NOT NULL,
    weekdayname            VARCHAR(10) NOT NULL,
    isweekend              BOOLEAN NOT NULL,
    isholiday              BOOLEAN NOT NULL,
    holidaytext            VARCHAR(64),
    dowinmonth             SMALLINT NOT NULL,
    dayofyear              SMALLINT NOT NULL,
    weekofmonth            SMALLINT NOT NULL,
    weekofyear             SMALLINT NOT NULL,
    isoweekofyear          SMALLINT NOT NULL,
    month                  SMALLINT NOT NULL,
    monthname              VARCHAR(10) NOT NULL,
    quarter                SMALLINT NOT NULL,
    quartername            VARCHAR(6) NOT NULL,
    year                   INT NOT NULL,
    mmyyyy                 CHAR(6) NOT NULL,
    monthyear              CHAR(7) NOT NULL,
    firstdayofmonth        DATE NOT NULL,
    lastdayofmonth         DATE NOT NULL,
    firstdayofquarter      DATE NOT NULL,
    lastdayofquarter       DATE NOT NULL,
    firstdayofyear         DATE NOT NULL,
    lastdayofyear          DATE NOT NULL,
    firstdayofnextmonth    DATE NOT NULL,
    firstdayofnextyear     DATE NOT NULL,
    CONSTRAINT pk_date PRIMARY KEY (datekey)
);

CREATE OR REPLACE PROCEDURE generate_dimension_date()
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE date;

    INSERT INTO date (
        datekey, day, daysuffix, weekday, weekdayname, isweekend, isholiday, holidaytext, 
        dowinmonth, dayofyear, weekofmonth, weekofyear, isoweekofyear, month, monthname, 
        quarter, quartername, year, mmyyyy, monthyear, firstdayofmonth, lastdayofmonth, 
        firstdayofquarter, lastdayofquarter, firstdayofyear, lastdayofyear, 
        firstdayofnextmonth, firstdayofnextyear
    )
    WITH base_dates AS (
        SELECT d::date AS datum
        FROM generate_series(
            '2026-01-01'::date, 
            ('2026-01-01'::date + INTERVAL '30 years' - INTERVAL '1 day')::date, 
            '1 day'::interval
        ) s(d)
    ),
    extracted_features AS (
        SELECT 
            datum AS d,
            EXTRACT(DAY FROM datum)::smallint AS _day,
            CASE WHEN EXTRACT(ISODOW FROM datum) = 7 THEN 1 ELSE EXTRACT(ISODOW FROM datum)::smallint + 1 END AS _dow,
            EXTRACT(DOY FROM datum)::smallint AS _doy,
            EXTRACT(WEEK FROM datum)::smallint AS _week,
            EXTRACT(WEEK FROM datum)::smallint AS _isoweek,
            EXTRACT(MONTH FROM datum)::smallint AS _month,
            EXTRACT(QUARTER FROM datum)::smallint AS _quarter,
            EXTRACT(YEAR FROM datum)::int AS _year,
            DATE_TRUNC('month', datum)::date AS _first_of_month,
            DATE_TRUNC('year', datum)::date AS _first_of_year
        FROM base_dates
    )
    SELECT
        d AS datekey,
        _day AS day,
        CASE 
            WHEN _day IN (11, 12, 13) THEN 'th'
            WHEN _day % 10 = 1 THEN 'st'
            WHEN _day % 10 = 2 THEN 'nd'
            WHEN _day % 10 = 3 THEN 'rd'
            ELSE 'th'
        END::char(2) AS daysuffix,
        _dow AS weekday,
        TRIM(to_char(d, 'Day'))::varchar(10) AS weekdayname,
        CASE WHEN _dow IN (1, 7) THEN TRUE ELSE FALSE END AS isweekend,
        FALSE AS isholiday,
        NULL::varchar(64) AS holidaytext,
        ROW_NUMBER() OVER (PARTITION BY _first_of_month, _dow ORDER BY d)::smallint AS dowinmonth,
        _doy AS dayofyear,
        DENSE_RANK() OVER (PARTITION BY _year, _month ORDER BY _week)::smallint AS weekofmonth,
        _week AS weekofyear,
        _isoweek AS isoweekofyear,
        _month AS month,
        TRIM(to_char(d, 'Month'))::varchar(10) AS monthname,
        _quarter AS quarter,
        CASE _quarter 
            WHEN 1 THEN 'First' 
            WHEN 2 THEN 'Second' 
            WHEN 3 THEN 'Third' 
            WHEN 4 THEN 'Fourth' 
        END::varchar(6) AS quartername,
        _year AS year,
        (to_char(d, 'MM') || _year)::char(6) AS mmyyyy,
        (to_char(d, 'Mon') || _year)::char(7) AS monthyear,
        _first_of_month AS firstdayofmonth,
        (DATE_TRUNC('month', d) + INTERVAL '1 month' - INTERVAL '1 day')::date AS lastdayofmonth,
        DATE_TRUNC('quarter', d)::date AS firstdayofquarter,
        (DATE_TRUNC('quarter', d) + INTERVAL '3 months' - INTERVAL '1 day')::date AS lastdayofquarter,
        _first_of_year AS firstdayofyear,
        (DATE_TRUNC('year', d) + INTERVAL '1 year' - INTERVAL '1 day')::date AS lastdayofyear,
        (_first_of_month + INTERVAL '1 month')::date AS firstdayofnextmonth,
        (_first_of_year + INTERVAL '1 year')::date AS firstdayofnextyear
    FROM extracted_features;
END;
$$;
CALL generate_dimension_date();