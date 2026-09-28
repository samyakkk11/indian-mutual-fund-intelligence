
import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # add read_only=True on the check scripts
# 1. Which funds have implausible 5Y CAGR?
print(con.execute("""
    SELECT scheme_code, scheme_name, category_group_clean,
           ROUND(cagr_5y * 100, 2) AS cagr_5y_pct
    FROM fund_analytics
    WHERE cagr_5y IS NOT NULL
    ORDER BY cagr_5y DESC
    LIMIT 15
""").fetchdf().to_string(index=False))

# 2. Inspect the suspect fund's NAV around the lookback date and today
print(con.execute("""
    SELECT nav_date, nav
    FROM fund_daily_returns
    WHERE scheme_code = (
        SELECT scheme_code FROM fund_analytics
        ORDER BY cagr_5y DESC LIMIT 1
    )
    AND (nav_date <= DATE '2021-09-10' AND nav_date >= DATE '2021-08-25'
         OR nav_date >= DATE '2026-08-25')
    ORDER BY nav_date
""").fetchdf().to_string(index=False))

print(con.execute("""
    SELECT nav_date, nav, previous_nav, ROUND(daily_return * 100, 2) AS daily_return_pct
    FROM fund_daily_returns
    WHERE scheme_code = 145536
      AND ABS(daily_return) > 0.02
    ORDER BY ABS(daily_return) DESC
    LIMIT 10
""").fetchdf().to_string(index=False))
print(con.execute("""
    SELECT scheme_code, COUNT(*) AS suspect_days,
           MAX(ABS(daily_return)) AS max_abs_move
    FROM fund_daily_returns
    WHERE ABS(daily_return) > 0.25
    GROUP BY scheme_code
    ORDER BY max_abs_move DESC
    LIMIT 30
""").fetchdf().to_string(index=False))
print(con.execute("""
    SELECT scheme_code, nav_date, previous_nav, nav,
           ROUND(daily_return * 100, 1) AS pct
    FROM fund_daily_returns
    WHERE scheme_code IN (120497, 119164, 120520, 145486)
      AND ABS(daily_return) > 0.25
    ORDER BY scheme_code, nav_date
""").fetchdf().to_string(index=False))

print(con.execute("""
    WITH b AS (
        SELECT scheme_code, nav_date
        FROM fund_daily_returns WHERE ABS(daily_return) > 0.25
    )
    SELECT r.scheme_code, r.nav_date, r.nav
    FROM fund_daily_returns r
    JOIN b ON r.scheme_code = b.scheme_code
          AND r.nav_date BETWEEN b.nav_date - INTERVAL 3 DAY
                             AND b.nav_date + INTERVAL 3 DAY
    WHERE r.scheme_code IN (119164, 120497)
    ORDER BY r.scheme_code, r.nav_date
""").fetchdf().to_string(index=False))