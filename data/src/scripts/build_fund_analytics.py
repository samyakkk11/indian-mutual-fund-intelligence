import duckdb
from config import NAV_FILE, SCHEME_FILE, DB_FILE, PROCESSED_DIR

# ============================================================
# CONFIG
# ============================================================

NAV = NAV_FILE.as_posix()
SCHEME = SCHEME_FILE.as_posix()

DB_FILE.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_FILE))


print("=" * 80)
print("INDIAN MUTUAL FUND INTELLIGENCE")
print("BUILDING COMPLETE ANALYTICAL LAYER")
print("=" * 80)


# ============================================================
# 1. CHECK REQUIRED TABLES
# ============================================================

print("\n[1/8] Checking database tables...")

tables = con.execute("SHOW TABLES").fetchdf()
print(tables)

required_tables = {
    "fund_universe",
    "nav_master",
    "fund_daily_returns"
}

available_tables = set(tables["name"].tolist())

missing = required_tables - available_tables

if missing:
    raise Exception(
        f"Missing required tables: {missing}"
    )

print("\nRequired tables found.")


# ============================================================
# 2. FUND PERFORMANCE
# ============================================================

print("\n[2/8] Calculating return metrics...")


# ------------------------------------------------------------
# Latest NAV for every fund
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE latest_fund_nav AS

SELECT
    scheme_code,
    MAX(nav_date) AS latest_nav_date

FROM nav_master

WHERE nav IS NOT NULL

GROUP BY scheme_code
""")


# ------------------------------------------------------------
# First NAV for every fund
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE first_fund_nav AS

SELECT
    scheme_code,
    MIN(nav_date) AS first_nav_date

FROM nav_master

WHERE nav IS NOT NULL

GROUP BY scheme_code
""")


# ------------------------------------------------------------
# Historical NAV corresponding to 1Y / 3Y / 5Y
#
# ASOF JOIN finds the latest available NAV on or before
# the target date.
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE fund_horizon_nav AS

WITH targets AS (

    SELECT
        l.scheme_code,
        l.latest_nav_date,

        l.latest_nav_date - INTERVAL '1 year'
            AS target_1y,

        l.latest_nav_date - INTERVAL '3 years'
            AS target_3y,

        l.latest_nav_date - INTERVAL '5 years'
            AS target_5y

    FROM latest_fund_nav l

),

horizon_dates AS (

    SELECT
        scheme_code,
        latest_nav_date,
        '1Y' AS horizon,
        target_1y AS target_date

    FROM targets

    UNION ALL

    SELECT
        scheme_code,
        latest_nav_date,
        '3Y',
        target_3y

    FROM targets

    UNION ALL

    SELECT
        scheme_code,
        latest_nav_date,
        '5Y',
        target_5y

    FROM targets

)

SELECT
    h.scheme_code,
    h.latest_nav_date,
    h.horizon,
    h.target_date,
    n.nav AS historical_nav,
    n.nav_date AS historical_nav_date

FROM horizon_dates h

ASOF JOIN nav_master n

    ON h.scheme_code = n.scheme_code
    AND n.nav_date <= h.target_date

WHERE n.nav IS NOT NULL
""")


# ------------------------------------------------------------
# Latest NAV values
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE latest_nav_values AS

SELECT
    n.scheme_code,
    n.nav AS latest_nav,
    n.nav_date AS latest_nav_date

FROM nav_master n

INNER JOIN latest_fund_nav l

    ON n.scheme_code = l.scheme_code
    AND n.nav_date = l.latest_nav_date

WHERE n.nav IS NOT NULL
""")


# ------------------------------------------------------------
# Calculate returns
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE fund_performance AS

WITH horizon_returns AS (

    SELECT

        scheme_code,

        MAX(
            CASE
                WHEN horizon = '1Y'
                THEN
                    (historical_nav)
            END
        ) AS nav_1y_ago,

        MAX(
            CASE
                WHEN horizon = '3Y'
                THEN
                    (historical_nav)
            END
        ) AS nav_3y_ago,

        MAX(
            CASE
                WHEN horizon = '5Y'
                THEN
                    (historical_nav)
            END
        ) AS nav_5y_ago

    FROM fund_horizon_nav

    GROUP BY scheme_code

),

base AS (

    SELECT

        u.scheme_code,
        u.scheme_name,
        u.amc,
        u.scheme_type,
        u.category,
        u.category_sub,
        u.category_group_clean,
        u.category_group,
        u.scheme_plan,
        u.scheme_option,
        u.first_date,
        u.last_date,
        u.is_active,
        u.is_stale,

        l.latest_nav_date,
        l.latest_nav,

        f.first_nav_date,

        h.nav_1y_ago,
        h.nav_3y_ago,
        h.nav_5y_ago

    FROM fund_universe u

    LEFT JOIN latest_nav_values l
        ON u.scheme_code = l.scheme_code

    LEFT JOIN first_fund_nav f
        ON u.scheme_code = f.scheme_code

    LEFT JOIN horizon_returns h
        ON u.scheme_code = h.scheme_code

)

SELECT

    *,

    -- 1 YEAR ABSOLUTE RETURN
    CASE
        WHEN nav_1y_ago > 0
        THEN latest_nav / nav_1y_ago - 1
    END AS return_1y,

    -- 3 YEAR CAGR
    CASE
        WHEN nav_3y_ago > 0
        THEN POWER(
            latest_nav / nav_3y_ago,
            1.0 / 3
        ) - 1
    END AS cagr_3y,

    -- 5 YEAR CAGR
    CASE
        WHEN nav_5y_ago > 0
        THEN POWER(
            latest_nav / nav_5y_ago,
            1.0 / 5
        ) - 1
    END AS cagr_5y,

    -- SINCE INCEPTION CAGR
    CASE
        WHEN first_nav_date IS NOT NULL
         AND first_nav_date < latest_nav_date
         AND latest_nav > 0
        THEN POWER(
            latest_nav / (
                SELECT n2.nav
                FROM nav_master n2
                WHERE n2.scheme_code = base.scheme_code
                  AND n2.nav_date = base.first_nav_date
                LIMIT 1
            ),
            365.25 /
            DATE_DIFF(
                'day',
                first_nav_date,
                latest_nav_date
            )
        ) - 1
    END AS cagr_since_inception

FROM base
""")


# ============================================================
# 3. RISK ANALYSIS
# ============================================================

print("[3/8] Calculating risk metrics...")


# ------------------------------------------------------------
# Annualized volatility
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE fund_risk AS

WITH returns AS (

    SELECT

        scheme_code,
        nav_date,
        daily_return

    FROM fund_daily_returns

    WHERE daily_return IS NOT NULL

),

statistics AS (

    SELECT

        scheme_code,

        COUNT(*) AS return_observations,

        STDDEV_SAMP(daily_return)
            * SQRT(252)
            AS annualized_volatility

    FROM returns

    GROUP BY scheme_code

),

drawdown_base AS (

    SELECT

        scheme_code,
        nav_date,

        -- Running maximum NAV
        MAX(nav) OVER (
            PARTITION BY scheme_code
            ORDER BY nav_date
            ROWS BETWEEN UNBOUNDED PRECEDING
                 AND CURRENT ROW
        ) AS running_max_nav,

        nav

    FROM nav_master

    WHERE nav IS NOT NULL

),

drawdowns AS (

    SELECT

        scheme_code,
        nav_date,

        CASE
            WHEN running_max_nav > 0
            THEN nav / running_max_nav - 1
        END AS drawdown

    FROM drawdown_base

),

maximum_drawdown AS (

    SELECT

        scheme_code,

        MIN(drawdown) AS maximum_drawdown

    FROM drawdowns

    GROUP BY scheme_code

)

SELECT

    s.scheme_code,
    s.return_observations,
    s.annualized_volatility,
    d.maximum_drawdown

FROM statistics s

LEFT JOIN maximum_drawdown d
    ON s.scheme_code = d.scheme_code
""")


# ============================================================
# 4. MASTER ANALYTICS TABLE
# ============================================================

print("[4/8] Creating master fund analytics table...")


con.execute("""
CREATE OR REPLACE TABLE fund_analytics AS

SELECT

    p.*,

    r.return_observations,
    r.annualized_volatility,
    r.maximum_drawdown,

    -- Return per unit of volatility
    CASE
        WHEN r.annualized_volatility > 0
        THEN p.cagr_3y / r.annualized_volatility
    END AS return_volatility_ratio,

    -- Return adjusted for drawdown
    CASE
        WHEN ABS(r.maximum_drawdown) > 0
        THEN p.cagr_3y / ABS(r.maximum_drawdown)
    END AS return_drawdown_ratio

FROM fund_performance p

LEFT JOIN fund_risk r
    ON p.scheme_code = r.scheme_code
""")


# ============================================================
# 5. FUND COMPARISON
# ============================================================

print("[5/8] Creating fund comparison tables...")


# ------------------------------------------------------------
# Direct vs Regular
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE direct_regular_comparison AS

SELECT

    category_group_clean,
    category,
    category_sub,

    COUNT(
        DISTINCT
        CASE
            WHEN scheme_plan = 'Direct'
            THEN scheme_code
        END
    ) AS direct_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN scheme_plan = 'Regular'
            THEN scheme_code
        END
    ) AS regular_schemes,

    AVG(
        CASE
            WHEN scheme_plan = 'Direct'
            THEN cagr_3y
        END
    ) AS avg_direct_3y_cagr,

    AVG(
        CASE
            WHEN scheme_plan = 'Regular'
            THEN cagr_3y
        END
    ) AS avg_regular_3y_cagr,

    MEDIAN(
        CASE
            WHEN scheme_plan = 'Direct'
            THEN cagr_3y
        END
    ) AS median_direct_3y_cagr,

    MEDIAN(
        CASE
            WHEN scheme_plan = 'Regular'
            THEN cagr_3y
        END
    ) AS median_regular_3y_cagr

FROM fund_analytics

WHERE cagr_3y IS NOT NULL

GROUP BY
    category_group_clean,
    category,
    category_sub
""")


# ------------------------------------------------------------
# Growth vs IDCW distribution
# ------------------------------------------------------------

con.execute("""
CREATE OR REPLACE TABLE growth_idcw_comparison AS

SELECT

    category_group_clean,

    COUNT(
        DISTINCT
        CASE
            WHEN scheme_option = 'Growth'
            THEN scheme_code
        END
    ) AS growth_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN scheme_option = 'IDCW'
            THEN scheme_code
        END
    ) AS idcw_schemes,

    AVG(
        CASE
            WHEN scheme_option = 'Growth'
            THEN cagr_3y
        END
    ) AS avg_growth_3y_cagr,

    AVG(
        CASE
            WHEN scheme_option = 'IDCW'
            THEN cagr_3y
        END
    ) AS avg_idcw_3y_cagr

FROM fund_analytics

WHERE cagr_3y IS NOT NULL

GROUP BY category_group_clean
""")


# ============================================================
# 6. AMC ANALYSIS
# ============================================================

print("[6/8] Creating AMC analytics...")


con.execute("""
CREATE OR REPLACE TABLE amc_analytics AS

SELECT

    amc,

    COUNT(DISTINCT scheme_code)
        AS total_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN is_active = TRUE
            THEN scheme_code
        END
    ) AS active_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN category_group_clean = 'Equity Scheme'
            THEN scheme_code
        END
    ) AS equity_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN category_group_clean = 'Debt Scheme'
            THEN scheme_code
        END
    ) AS debt_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN category_group_clean = 'Hybrid Scheme'
            THEN scheme_code
        END
    ) AS hybrid_schemes,

    COUNT(
        DISTINCT
        CASE
            WHEN category_group_clean = 'Other Scheme'
            THEN scheme_code
        END
    ) AS other_schemes,

    AVG(cagr_3y)
        AS average_3y_cagr,

    MEDIAN(cagr_3y)
        AS median_3y_cagr,

    AVG(annualized_volatility)
        AS average_volatility,

    AVG(maximum_drawdown)
        AS average_maximum_drawdown,

    STDDEV_SAMP(cagr_3y)
        AS cagr_consistency_spread

FROM fund_analytics

WHERE cagr_3y IS NOT NULL

GROUP BY amc
""")


# ============================================================
# 7. CATEGORY-LEVEL FUND RANKINGS
# ============================================================

print("[7/8] Creating category-level rankings...")


con.execute("""
CREATE OR REPLACE TABLE fund_rankings AS

SELECT

    *,

    -- Return rank
    RANK() OVER (
        PARTITION BY category_group_clean, category
        ORDER BY cagr_3y DESC NULLS LAST
    ) AS return_rank_3y,

    RANK() OVER (
        PARTITION BY category_group_clean, category
        ORDER BY cagr_5y DESC NULLS LAST
    ) AS return_rank_5y,

    -- Lower volatility is better
    RANK() OVER (
        PARTITION BY category_group_clean, category
        ORDER BY annualized_volatility ASC NULLS LAST
    ) AS volatility_rank,

    -- Smaller drawdown is better
    RANK() OVER (
        PARTITION BY category_group_clean, category
        ORDER BY maximum_drawdown DESC NULLS LAST
    ) AS drawdown_rank,

    -- Higher return / volatility is better
    RANK() OVER (
        PARTITION BY category_group_clean, category
        ORDER BY return_volatility_ratio DESC NULLS LAST
    ) AS risk_adjusted_rank,

    -- Composite ranking
    (
        COALESCE(
            RANK() OVER (
                PARTITION BY category_group_clean, category
                ORDER BY cagr_3y DESC NULLS LAST
            ),
            999999
        )

        +

        COALESCE(
            RANK() OVER (
                PARTITION BY category_group_clean, category
                ORDER BY cagr_5y DESC NULLS LAST
            ),
            999999
        )

        +

        COALESCE(
            RANK() OVER (
                PARTITION BY category_group_clean, category
                ORDER BY annualized_volatility ASC NULLS LAST
            ),
            999999
        )

        +

        COALESCE(
            RANK() OVER (
                PARTITION BY category_group_clean, category
                ORDER BY maximum_drawdown DESC NULLS LAST
            ),
            999999
        )
    ) AS composite_score

FROM fund_analytics
""")


# ============================================================
# 8. FINAL INVESTOR DATASET
# ============================================================

print("[8/8] Creating final investor dataset...")


con.execute("""
CREATE OR REPLACE TABLE investor_fund_dataset AS

SELECT

    f.*,

    fr.return_rank_3y,
    fr.return_rank_5y,
    fr.volatility_rank,
    fr.drawdown_rank,
    fr.risk_adjusted_rank,
    fr.composite_score,

    -- Final category ranking
    RANK() OVER (
        PARTITION BY f.category_group_clean, f.category
        ORDER BY fr.composite_score ASC
    ) AS overall_category_rank

FROM fund_analytics f

LEFT JOIN fund_rankings fr

    ON f.scheme_code = fr.scheme_code
""")


# ============================================================
# EXPORT TABLES
# ============================================================

print("\nExporting analytical datasets...")


tables_to_export = [
    "fund_analytics",
    "fund_performance",
    "fund_risk",
    "fund_rankings",
    "amc_analytics",
    "direct_regular_comparison",
    "growth_idcw_comparison",
    "investor_fund_dataset"
]


for table in tables_to_export:

    output_file = PROCESSED_DIR / f"{table}.parquet"

    con.execute(f"""
        COPY {table}
        TO '{output_file.as_posix()}'
        (FORMAT PARQUET)
    """)

    print(f"  ✓ {output_file}")


# ============================================================
# VALIDATION
# ============================================================

print("\n" + "=" * 80)
print("VALIDATION")
print("=" * 80)


print("\nFUND ANALYTICS SUMMARY")

print(
    con.execute("""
        SELECT

            COUNT(*) AS schemes,

            COUNT(cagr_3y)
                AS schemes_with_3y_cagr,

            COUNT(cagr_5y)
                AS schemes_with_5y_cagr,

            COUNT(cagr_since_inception)
                AS schemes_with_inception_cagr,

            COUNT(annualized_volatility)
                AS schemes_with_volatility,

            COUNT(maximum_drawdown)
                AS schemes_with_drawdown

        FROM fund_analytics
    """).fetchdf().to_string(index=False)
)


print("\nTOP EQUITY FUNDS — 3Y CAGR")


print(
    con.execute("""
        SELECT

            overall_category_rank,
            scheme_name,
            amc,
            category,
            scheme_plan,
            scheme_option,

            ROUND(cagr_3y * 100, 2)
                AS cagr_3y_pct,

            ROUND(cagr_5y * 100, 2)
                AS cagr_5y_pct,

            ROUND(annualized_volatility * 100, 2)
                AS volatility_pct,

            ROUND(maximum_drawdown * 100, 2)
                AS max_drawdown_pct,

            return_rank_3y,
            risk_adjusted_rank

        FROM investor_fund_dataset

        WHERE category_group_clean = 'Equity Scheme'
          AND cagr_3y IS NOT NULL

        ORDER BY cagr_3y DESC

        LIMIT 20
    """).fetchdf().to_string(index=False)
)


print("\nTOP AMCs BY MEDIAN 3Y CAGR")


print(
    con.execute("""
        SELECT

            amc,
            active_schemes,

            ROUND(median_3y_cagr * 100, 2)
                AS median_3y_cagr_pct,

            ROUND(average_3y_cagr * 100, 2)
                AS average_3y_cagr_pct,

            ROUND(average_volatility * 100, 2)
                AS average_volatility_pct,

            ROUND(average_maximum_drawdown * 100, 2)
                AS average_drawdown_pct

        FROM amc_analytics

        WHERE active_schemes > 0

        ORDER BY median_3y_cagr DESC

        LIMIT 20
    """).fetchdf().to_string(index=False)
)


print("\nCATEGORY DISTRIBUTION")


print(
    con.execute("""
        SELECT

            category_group_clean,

            COUNT(*) AS schemes,

            COUNT(
                CASE
                    WHEN is_active = TRUE
                    THEN 1
                END
            ) AS active_schemes,

            ROUND(
                AVG(cagr_3y) * 100,
                2
            ) AS average_3y_cagr_pct,

            ROUND(
                MEDIAN(cagr_3y) * 100,
                2
            ) AS median_3y_cagr_pct,

            ROUND(
                AVG(annualized_volatility) * 100,
                2
            ) AS average_volatility_pct

        FROM fund_analytics

        GROUP BY category_group_clean

        ORDER BY schemes DESC
    """).fetchdf().to_string(index=False)
)


con.close()


print("\n" + "=" * 80)
print("ANALYTICAL LAYER COMPLETED")
print("=" * 80)

print("""
Created:

1. fund_performance
2. fund_risk
3. fund_analytics
4. fund_rankings
5. investor_fund_dataset
6. amc_analytics
7. direct_regular_comparison
8. growth_idcw_comparison

Parquet files exported to:

data/processed/
""")