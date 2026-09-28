import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # add read_only=True on the check scripts

print("Detecting NAV discontinuities...")

con.execute("""
CREATE OR REPLACE TABLE nav_discontinuities AS

WITH ratios AS (
    SELECT
        scheme_code,
        nav_date,
        previous_nav,
        nav,
        nav / previous_nav AS ratio
    FROM fund_daily_returns
    WHERE previous_nav > 0
)
SELECT *
FROM ratios
WHERE ratio BETWEEN 8     AND 12
   OR ratio BETWEEN 80    AND 120
   OR ratio BETWEEN 0.08  AND 0.125
   OR ratio BETWEEN 0.008 AND 0.0125
""")

con.execute("""
CREATE OR REPLACE TABLE excluded_schemes AS
SELECT DISTINCT scheme_code FROM nav_discontinuities
""")

affected = con.execute("SELECT COUNT(*) FROM excluded_schemes").fetchone()[0]
total = con.execute("SELECT COUNT(DISTINCT scheme_code) FROM fund_daily_returns").fetchone()[0]

print(f"Schemes with NAV discontinuities : {affected:,}")
print(f"Total schemes                    : {total:,}")
print(f"Share excluded                   : {affected / total:.2%}")

print("\nBreak events by ratio type:")
print(con.execute("""
    SELECT
        CASE
            WHEN ratio BETWEEN 8 AND 12         THEN 'x10'
            WHEN ratio BETWEEN 80 AND 120       THEN 'x100'
            WHEN ratio BETWEEN 0.08 AND 0.125   THEN '/10'
            ELSE '/100'
        END AS break_type,
        COUNT(*) AS events,
        COUNT(DISTINCT scheme_code) AS schemes
    FROM nav_discontinuities
    GROUP BY 1
    ORDER BY events DESC
""").fetchdf().to_string(index=False))

con.close()
print("\nDone.")