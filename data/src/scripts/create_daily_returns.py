import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # add read_only=True on the check scripts

print("Creating fund_daily_returns...")

con.execute("""
CREATE OR REPLACE TABLE fund_daily_returns AS

WITH nav_data AS (

    SELECT
        n.scheme_code,
        n.nav_date,
        n.nav,

        LAG(n.nav) OVER (
            PARTITION BY n.scheme_code
            ORDER BY n.nav_date
        ) AS previous_nav

    FROM nav_master n

    INNER JOIN fund_universe f
        ON n.scheme_code = f.scheme_code

    WHERE n.nav IS NOT NULL
      AND n.nav > 0
)

SELECT
    scheme_code,
    nav_date,
    nav,
    previous_nav,

    CASE
        WHEN previous_nav IS NOT NULL
             AND previous_nav > 0
        THEN (nav / previous_nav) - 1
        ELSE NULL
    END AS daily_return

FROM nav_data
""")

print("Daily returns table created.")

# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

result = con.execute("""
SELECT
    COUNT(*) AS rows,
    COUNT(DISTINCT scheme_code) AS schemes,
    MIN(nav_date) AS earliest_date,
    MAX(nav_date) AS latest_date,
    COUNT(daily_return) AS calculated_returns
FROM fund_daily_returns
""").fetchdf()

print("\nSUMMARY")
print("=" * 60)
print(result.to_string(index=False))


# ------------------------------------------------------------
# SAMPLE
# ------------------------------------------------------------

print("\nSAMPLE")
print("=" * 60)

sample = con.execute("""
SELECT *
FROM fund_daily_returns
ORDER BY scheme_code, nav_date
LIMIT 15
""").fetchdf()

print(sample.to_string(index=False))


con.close()

print("\nDone.")