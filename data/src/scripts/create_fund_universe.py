import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # read_only=True on the check scripts

print("Creating fund_universe...")


con.execute("""
CREATE OR REPLACE TABLE fund_universe AS

SELECT
    scheme_code,
    scheme_name,
    amc,

    scheme_type,

    category,
    category_sub,

    category_group_clean,
    category_group,

    scheme_plan,
    scheme_option,

    isin,
    isin2,

    first_date,
    last_date,

    is_active,
    is_stale,

    txic_code,

    aaum_cr_quarterly_avg,
    aaum_quarter,
    aaum_quarter_end,

    latest_nav_date,
    latest_nav

FROM scheme_master

WHERE is_active = TRUE
  AND scheme_plan = 'Direct'
  AND scheme_option = 'Growth'
""")


# ============================================================
# VALIDATION
# ============================================================

print("\nFUND UNIVERSE")
print("=" * 60)

result = con.execute("""
SELECT
    COUNT(*) AS schemes,
    COUNT(DISTINCT amc) AS amcs
FROM fund_universe
""").fetchone()

print(f"Total schemes : {result[0]:,}")
print(f"Total AMCs    : {result[1]:,}")


print("\nBY CATEGORY")
print("-" * 60)

df = con.execute("""
SELECT
    category_group_clean,
    COUNT(*) AS schemes
FROM fund_universe
GROUP BY category_group_clean
ORDER BY schemes DESC
""").fetchdf()

print(df.to_string(index=False))


print("\nTOP 20 AMCs")
print("-" * 60)

df = con.execute("""
SELECT
    amc,
    COUNT(*) AS schemes
FROM fund_universe
GROUP BY amc
ORDER BY schemes DESC
LIMIT 20
""").fetchdf()

print(df.to_string(index=False))


print("\nSAMPLE")
print("-" * 60)

df = con.execute("""
SELECT *
FROM fund_universe
LIMIT 10
""").fetchdf()

print(df.to_string(index=False))


con.close()

print("\n✓ fund_universe created")