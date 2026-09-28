import duckdb
from config import NAV_FILE, SCHEME_FILE, DB_FILE

# ============================================================
# CONFIG
# ============================================================

NAV = NAV_FILE.as_posix()
SCHEME = SCHEME_FILE.as_posix()

DB_FILE.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_FILE))


# ============================================================
# 1. RAW NAV VIEW
# ============================================================

print("Creating nav_master...")

con.execute(f"""
CREATE OR REPLACE VIEW nav_master AS

SELECT
    scheme_code,
    CAST(date AS DATE) AS nav_date,
    TRY_CAST(nav AS DECIMAL(18,4)) AS nav,
    scheme_name,
    isin

FROM read_parquet('{NAV}')
""")


# ============================================================
# 2. RAW SCHEME MASTER
# ============================================================

print("Creating scheme_master...")

con.execute(f"""
CREATE OR REPLACE TABLE scheme_master AS

SELECT
    scheme_code,
    isin,
    isin2,
    scheme_name,
    amc,
    scheme_type,
    category,
    category_sub,
    category_group_clean,
    category_group,
    scheme_plan,
    scheme_option,
    CAST(first_date AS DATE) AS first_date,
    CAST(last_date AS DATE) AS last_date,
    is_active,
    is_stale,
    txic_code,
    TRY_CAST(aaum_cr_quarterly_avg AS DOUBLE)
        AS aaum_cr_quarterly_avg,
    aaum_quarter,
    CAST(aaum_quarter_end AS DATE)
        AS aaum_quarter_end,
    CAST(nav_date AS DATE) AS latest_nav_date,
    TRY_CAST(nav AS DOUBLE) AS latest_nav

FROM read_csv_auto('{SCHEME}')
""")


# ============================================================
# 3. VALIDATE SCHEME CODE UNIQUENESS
# ============================================================

print("Checking scheme_code uniqueness...")

duplicate_schemes = con.execute("""
SELECT
    scheme_code,
    COUNT(*) AS cnt

FROM scheme_master

GROUP BY scheme_code

HAVING COUNT(*) > 1

LIMIT 10
""").fetchdf()

if len(duplicate_schemes) == 0:
    print("✓ scheme_code is unique")
else:
    print("⚠ Duplicate scheme codes found:")
    print(duplicate_schemes)


# ============================================================
# 4. CREATE INDEX
# ============================================================

print("Creating indexes...")

con.execute("""
CREATE INDEX IF NOT EXISTS idx_scheme_master_code
ON scheme_master(scheme_code)
""")


# ============================================================
# 5. VALIDATE NAV → SCHEME RELATIONSHIP
# ============================================================

print("Checking NAV records against scheme master...")

validation = con.execute("""
SELECT
    COUNT(*) AS total_nav_rows,
    COUNT(sm.scheme_code) AS matched_rows,
    COUNT(*) - COUNT(sm.scheme_code) AS unmatched_rows

FROM nav_master nav

LEFT JOIN scheme_master sm
    ON nav.scheme_code = sm.scheme_code
""").fetchone()

print()
print("NAV / SCHEME MATCH")
print("-" * 50)
print(f"Total NAV rows : {validation[0]:,}")
print(f"Matched rows   : {validation[1]:,}")
print(f"Unmatched rows : {validation[2]:,}")


# ============================================================
# 6. DATA MODEL SUMMARY
# ============================================================

print()
print("=" * 70)
print("DATABASE SUMMARY")
print("=" * 70)

scheme_count = con.execute("""
SELECT COUNT(*) FROM scheme_master
""").fetchone()[0]

nav_count = con.execute("""
SELECT COUNT(*) FROM nav_master
""").fetchone()[0]

active_count = con.execute("""
SELECT COUNT(*)
FROM scheme_master
WHERE is_active = TRUE
""").fetchone()[0]

print(f"Schemes        : {scheme_count:,}")
print(f"Active schemes : {active_count:,}")
print(f"NAV records    : {nav_count:,}")


# ============================================================
# 7. SAMPLE JOIN
# ============================================================

print()
print("Sample joined data:")
print("-" * 70)

sample = con.execute("""
SELECT
    nav.scheme_code,
    sm.scheme_name,
    sm.amc,
    sm.category_group_clean,
    sm.scheme_plan,
    sm.scheme_option,
    nav.nav_date,
    nav.nav

FROM nav_master nav

INNER JOIN scheme_master sm
    ON nav.scheme_code = sm.scheme_code

LIMIT 10
""").fetchdf()

print(sample.to_string(index=False))


con.close()

print()
print("✓ Database model created successfully")