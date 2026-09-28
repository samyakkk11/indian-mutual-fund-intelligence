import duckdb

from config import DB_FILE, PROCESSED_DIR

PARQUET_IN = (PROCESSED_DIR / "investor_fund_dataset.parquet").as_posix()
PARQUET_OUT = PARQUET_IN
con = duckdb.connect(str(DB_FILE), read_only=True)


print("=" * 70)
print("ADD FUND_AGE_TIER TO INVESTOR_FUND_DATASET")
print("=" * 70)


# ------------------------------------------------------------
# PREVIEW: age tier counts, joining first_date from scheme_master
# ------------------------------------------------------------

print("\nFUND AGE TIER COUNTS (preview before writing)")

preview = con.execute(f"""
    SELECT
        CASE
            WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 365 THEN '<1Y'
            WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 1095 THEN '1-3Y'
            WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 1825 THEN '3-5Y'
            ELSE '5Y+'
        END AS fund_age_tier,
        COUNT(*) AS schemes
    FROM read_parquet('{PARQUET_IN}') ifd
    JOIN scheme_master sm ON ifd.scheme_code = sm.scheme_code
    GROUP BY fund_age_tier
    ORDER BY
        CASE fund_age_tier
            WHEN '<1Y' THEN 1
            WHEN '1-3Y' THEN 2
            WHEN '3-5Y' THEN 3
            ELSE 4
        END
""").fetchdf()

print(preview.to_string(index=False))

print("\nCross-check: '<1Y' count above should be close to the 167 nulls")
print("you saw for return_1y/nav_1y_ago in the earlier check.")


# ------------------------------------------------------------
# WRITE: new parquet with fund_age_tier column added
# ------------------------------------------------------------

print("\nWriting updated parquet with fund_age_tier column...")

con.execute(f"""
    COPY (
        SELECT
            ifd.*,
            CASE
                WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 365 THEN '<1Y'
                WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 1095 THEN '1-3Y'
                WHEN DATE_DIFF('day', sm.first_date, CURRENT_DATE) < 1825 THEN '3-5Y'
                ELSE '5Y+'
            END AS fund_age_tier
        FROM read_parquet('{PARQUET_IN}') ifd
        JOIN scheme_master sm ON ifd.scheme_code = sm.scheme_code
    ) TO '{PARQUET_OUT}' (FORMAT PARQUET)
""")

print(f"Done. Updated file written to: {PARQUET_OUT}")

con.close()