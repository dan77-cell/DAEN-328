SELECT 
    c.specimen_date,
    c.extract_date,
    c.number_tested,
    c.number_hospitalized,
    c.number_deaths
FROM covid_outcomes AS c
JOIN (
    SELECT 
        specimen_date,
        MAX(extract_date) AS latest_extract_date
    FROM covid_outcomes
    WHERE specimen_date IN (
        '2020-12-22',
        '2021-08-30',
        '2021-02-08',
        '2020-05-14'
    )
    GROUP BY specimen_date
) AS latest
ON c.specimen_date = latest.specimen_date
AND c.extract_date = latest.latest_extract_date;