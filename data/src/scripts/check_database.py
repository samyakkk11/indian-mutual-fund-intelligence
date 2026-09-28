import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # add read_only=True on the check scripts
result = con.execute("""
SELECT
    f.category_group_clean,
    COUNT(DISTINCT f.scheme_code) AS schemes,
    COUNT(n.scheme_code) AS nav_records,
    MIN(n.nav_date) AS earliest_nav,
    MAX(n.nav_date) AS latest_nav
FROM fund_universe f
LEFT JOIN nav_master n
    ON f.scheme_code = n.scheme_code
GROUP BY f.category_group_clean
ORDER BY schemes DESC;
""").fetchdf()

print(result.to_string(index=False))

con.close()