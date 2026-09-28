import duckdb

from config import DB_FILE, PROCESSED_DIR

PARQUET_IN = (PROCESSED_DIR / "investor_fund_dataset.parquet").as_posix()
PARQUET_OUT = PARQUET_IN
con = duckdb.connect(str(DB_FILE), read_only=True)


print("=" * 70)
print("INVESTOR FUND DATASET - MISSING VALUE NESTING CHECK")
print("=" * 70)


# ------------------------------------------------------------
# NESTING VIOLATIONS
# ------------------------------------------------------------

print("\nNESTING VIOLATIONS (should be 0 rows)")

violations = con.execute(f"""
    SELECT
        scheme_code,
        scheme_name,
        return_1y,
        cagr_3y,
        cagr_5y
    FROM read_parquet('{PARQUET_IN}')
    WHERE
        (cagr_5y IS NOT NULL AND (cagr_3y IS NULL OR return_1y IS NULL))
        OR
        (cagr_3y IS NOT NULL AND return_1y IS NULL)
""").fetchdf()

print(f"Violations found: {len(violations)}")
if len(violations) > 0:
    print(violations.to_string(index=False))


# ------------------------------------------------------------
# NULL PERCENTAGE BY COLUMN
# ------------------------------------------------------------

print("\nNULL PERCENTAGE BY COLUMN")

print(
    con.execute(f"""
        SELECT
            'return_1y' AS column_name,
            COUNT(*) AS total_rows,
            SUM(CASE WHEN return_1y IS NULL THEN 1 ELSE 0 END) AS null_count,
            ROUND(100.0 * SUM(CASE WHEN return_1y IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS null_pct
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'cagr_3y',
            COUNT(*),
            SUM(CASE WHEN cagr_3y IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN cagr_3y IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'cagr_5y',
            COUNT(*),
            SUM(CASE WHEN cagr_5y IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN cagr_5y IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'annualized_volatility',
            COUNT(*),
            SUM(CASE WHEN annualized_volatility IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN annualized_volatility IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'nav_1y_ago',
            COUNT(*),
            SUM(CASE WHEN nav_1y_ago IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN nav_1y_ago IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'nav_3y_ago',
            COUNT(*),
            SUM(CASE WHEN nav_3y_ago IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN nav_3y_ago IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')

        UNION ALL

        SELECT
            'nav_5y_ago',
            COUNT(*),
            SUM(CASE WHEN nav_5y_ago IS NULL THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN nav_5y_ago IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM read_parquet('{PARQUET_IN}')
    """).fetchdf().to_string(index=False)
)


con.close()