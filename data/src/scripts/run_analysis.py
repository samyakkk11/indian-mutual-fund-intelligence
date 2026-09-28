import duckdb
from config import DB_FILE, PROCESSED_DIR

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(DB_FILE))
OUTPUT_DIR = PROCESSED_DIR

print("=" * 75)
print("INDIAN MUTUAL FUND INTELLIGENCE")
print("ANALYTICAL PIPELINE")
print("=" * 75)


# ============================================================
# 0. EXCLUDE SCHEMES WITH NAV DISCONTINUITIES
# ============================================================

print("\n[0/8] Building clean daily returns view...")

con.execute("""
CREATE OR REPLACE VIEW fund_daily_returns_clean AS
SELECT *
FROM fund_daily_returns
WHERE scheme_code NOT IN (SELECT scheme_code FROM excluded_schemes)
""")

excluded = con.execute("SELECT COUNT(*) FROM excluded_schemes").fetchone()[0]
print(f"Schemes excluded (NAV discontinuities): {excluded:,}")


# ============================================================
# 1. BASIC DATA VALIDATION
# ============================================================

print("\n[1/8] Validating source data...")

validation = con.execute("""
SELECT
    COUNT(*) AS nav_rows,
    COUNT(DISTINCT scheme_code) AS schemes,
    MIN(nav_date) AS earliest_date,
    MAX(nav_date) AS latest_date
FROM fund_daily_returns_clean
""").fetchone()

print(f"NAV rows       : {validation[0]:,}")
print(f"Schemes        : {validation[1]:,}")
print(f"Earliest date  : {validation[2]}")
print(f"Latest date    : {validation[3]}")


# ============================================================
# 2. PERFORMANCE SUMMARY
# ============================================================

print("\n[2/8] Creating fund_performance_summary...")

con.execute("""
CREATE OR REPLACE TABLE fund_performance_summary AS

WITH fund_dates AS (

    SELECT
        scheme_code,
        MIN(nav_date) AS first_nav_date,
        MAX(nav_date) AS latest_nav_date
    FROM fund_daily_returns_clean
    GROUP BY scheme_code

),

latest AS (

    SELECT
        d.scheme_code,
        d.latest_nav_date,
        r.nav AS latest_nav

    FROM fund_dates d

    INNER JOIN fund_daily_returns_clean r
        ON d.scheme_code = r.scheme_code
       AND d.latest_nav_date = r.nav_date

),

historical AS (

    SELECT
        l.scheme_code,

        l.latest_nav_date,
        l.latest_nav,

        -- NAV approximately 1 year ago
        (
            SELECT r.nav
            FROM fund_daily_returns_clean r
            WHERE r.scheme_code = l.scheme_code
              AND r.nav_date <= l.latest_nav_date - INTERVAL '1 year'
            ORDER BY r.nav_date DESC
            LIMIT 1
        ) AS nav_1y,

        -- NAV approximately 3 years ago
        (
            SELECT r.nav
            FROM fund_daily_returns_clean r
            WHERE r.scheme_code = l.scheme_code
              AND r.nav_date <= l.latest_nav_date - INTERVAL '3 years'
            ORDER BY r.nav_date DESC
            LIMIT 1
        ) AS nav_3y,

        -- NAV approximately 5 years ago
        (
            SELECT r.nav
            FROM fund_daily_returns_clean r
            WHERE r.scheme_code = l.scheme_code
              AND r.nav_date <= l.latest_nav_date - INTERVAL '5 years'
            ORDER BY r.nav_date DESC
            LIMIT 1
        ) AS nav_5y,

        -- NAV approximately 10 years ago
        (
            SELECT r.nav
            FROM fund_daily_returns_clean r
            WHERE r.scheme_code = l.scheme_code
              AND r.nav_date <= l.latest_nav_date - INTERVAL '10 years'
            ORDER BY r.nav_date DESC
            LIMIT 1
        ) AS nav_10y

    FROM latest l
)

SELECT

    f.scheme_code,
    f.scheme_name,
    f.amc,

    f.category,
    f.category_sub,
    f.category_group_clean,

    f.scheme_plan,
    f.scheme_option,

    f.first_date,
    h.latest_nav_date,

    h.latest_nav,

    -- 1 YEAR
    CASE
        WHEN h.nav_1y IS NOT NULL
        THEN (h.latest_nav / h.nav_1y) - 1
    END AS return_1y,

    -- 3 YEAR CAGR
    CASE
        WHEN h.nav_3y IS NOT NULL
        THEN POWER(h.latest_nav / h.nav_3y, 1.0 / 3) - 1
    END AS cagr_3y,

    -- 5 YEAR CAGR
    CASE
        WHEN h.nav_5y IS NOT NULL
        THEN POWER(h.latest_nav / h.nav_5y, 1.0 / 5) - 1
    END AS cagr_5y,

    -- 10 YEAR CAGR
    CASE
        WHEN h.nav_10y IS NOT NULL
        THEN POWER(h.latest_nav / h.nav_10y, 1.0 / 10) - 1
    END AS cagr_10y,

    f.aaum_cr_quarterly_avg,
    f.aaum_quarter,

    f.is_active,
    f.is_stale

FROM historical h

INNER JOIN fund_universe f
    ON h.scheme_code = f.scheme_code
""")


# ============================================================
# 3. RISK METRICS
# ============================================================

print("[3/8] Creating fund_risk_metrics...")

con.execute("""
CREATE OR REPLACE TABLE fund_risk_metrics AS

WITH returns AS (

    SELECT
        scheme_code,
        nav_date,
        daily_return
    FROM fund_daily_returns_clean
    WHERE daily_return IS NOT NULL

),

statistics AS (

    SELECT

        scheme_code,

        COUNT(*) AS trading_days,

        AVG(daily_return) AS avg_daily_return,

        STDDEV_SAMP(daily_return) AS daily_volatility,

        MIN(daily_return) AS worst_daily_return,

        MAX(daily_return) AS best_daily_return,

        SUM(
            CASE
                WHEN daily_return > 0 THEN 1
                ELSE 0
            END
        ) AS positive_days,

        SUM(
            CASE
                WHEN daily_return < 0 THEN 1
                ELSE 0
            END
        ) AS negative_days,

        -- Downside deviation
        SQRT(
            AVG(
                CASE
                    WHEN daily_return < 0
                    THEN POWER(daily_return, 2)
                    ELSE 0
                END
            )
        ) AS downside_deviation

    FROM returns

    GROUP BY scheme_code

)

SELECT

    scheme_code,

    trading_days,

    avg_daily_return,

    daily_volatility,

    -- Annualized volatility
    daily_volatility * SQRT(252)
        AS annualized_volatility,

    worst_daily_return,

    best_daily_return,

    positive_days,

    negative_days,

    CASE
        WHEN trading_days > 0
        THEN positive_days * 1.0 / trading_days
    END AS positive_day_ratio,

    downside_deviation,

    downside_deviation * SQRT(252)
        AS annualized_downside_deviation

FROM statistics
""")


# ============================================================
# 4. MAXIMUM DRAWDOWN
# ============================================================

print("[4/8] Creating fund_drawdowns...")

con.execute("""
CREATE OR REPLACE TABLE fund_drawdowns AS

WITH running_values AS (

    SELECT

        scheme_code,
        nav_date,
        nav,

        MAX(nav) OVER (
            PARTITION BY scheme_code
            ORDER BY nav_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak

    FROM fund_daily_returns_clean

),

drawdowns AS (

    SELECT

        scheme_code,
        nav_date,
        nav,
        running_peak,

        (nav / running_peak) - 1 AS drawdown

    FROM running_values

),

max_dd AS (

    SELECT

        scheme_code,

        MIN(drawdown) AS maximum_drawdown

    FROM drawdowns

    GROUP BY scheme_code

)

SELECT

    scheme_code,
    maximum_drawdown

FROM max_dd
""")


# ============================================================
# 5. MERGED PERFORMANCE + RISK TABLE
# ============================================================

print("[5/8] Creating final fund analytics table...")

con.execute("""
CREATE OR REPLACE TABLE fund_analytics AS

SELECT

    p.*,

    r.trading_days,
    r.avg_daily_return,
    r.daily_volatility,
    r.annualized_volatility,

    r.worst_daily_return,
    r.best_daily_return,

    r.positive_days,
    r.negative_days,
    r.positive_day_ratio,

    r.downside_deviation,
    r.annualized_downside_deviation,

    d.maximum_drawdown

FROM fund_performance_summary p

LEFT JOIN fund_risk_metrics r
    ON p.scheme_code = r.scheme_code

LEFT JOIN fund_drawdowns d
    ON p.scheme_code = d.scheme_code
""")


# ============================================================
# 6. ANNUAL RETURNS
# ============================================================

print("[6/8] Creating fund_annual_returns...")

con.execute("""
CREATE OR REPLACE TABLE fund_annual_returns AS

WITH yearly AS (

    SELECT

        scheme_code,

        YEAR(nav_date) AS year,

        FIRST_VALUE(nav) OVER (
            PARTITION BY scheme_code, YEAR(nav_date)
            ORDER BY nav_date
        ) AS beginning_nav,

        LAST_VALUE(nav) OVER (
            PARTITION BY scheme_code, YEAR(nav_date)
            ORDER BY nav_date
            ROWS BETWEEN UNBOUNDED PRECEDING
            AND UNBOUNDED FOLLOWING
        ) AS ending_nav

    FROM fund_daily_returns_clean

)

SELECT DISTINCT

    scheme_code,
    year,
    beginning_nav,
    ending_nav,

    (ending_nav / beginning_nav) - 1 AS annual_return

FROM yearly

ORDER BY scheme_code, year
""")


# ============================================================
# 7. MONTHLY RETURNS
# ============================================================

print("[7/8] Creating fund_monthly_returns...")

con.execute("""
CREATE OR REPLACE TABLE fund_monthly_returns AS

WITH monthly AS (

    SELECT

        scheme_code,

        DATE_TRUNC('month', nav_date) AS month,

        FIRST_VALUE(nav) OVER (
            PARTITION BY
                scheme_code,
                DATE_TRUNC('month', nav_date)
            ORDER BY nav_date
        ) AS beginning_nav,

        LAST_VALUE(nav) OVER (
            PARTITION BY
                scheme_code,
                DATE_TRUNC('month', nav_date)
            ORDER BY nav_date
            ROWS BETWEEN UNBOUNDED PRECEDING
            AND UNBOUNDED FOLLOWING
        ) AS ending_nav

    FROM fund_daily_returns_clean

)

SELECT DISTINCT

    scheme_code,
    month,
    beginning_nav,
    ending_nav,

    (ending_nav / beginning_nav) - 1 AS monthly_return

FROM monthly

ORDER BY scheme_code, month
""")


# ============================================================
# 8. CATEGORY & AMC ANALYSIS
# ============================================================

print("[8/8] Creating category and AMC summaries...")

con.execute("""
CREATE OR REPLACE TABLE fund_category_summary AS

SELECT

    category_group_clean,

    COUNT(*) AS scheme_count,

    AVG(return_1y) AS avg_return_1y,

    AVG(cagr_3y) AS avg_cagr_3y,

    AVG(cagr_5y) AS avg_cagr_5y,

    AVG(annualized_volatility) AS avg_volatility,

    AVG(maximum_drawdown) AS avg_max_drawdown,

    AVG(aaum_cr_quarterly_avg) AS avg_aum_cr,

    SUM(aaum_cr_quarterly_avg) AS total_aum_cr

FROM fund_analytics

GROUP BY category_group_clean

ORDER BY total_aum_cr DESC
""")


con.execute("""
CREATE OR REPLACE TABLE fund_amc_summary AS

SELECT

    amc,

    COUNT(*) AS scheme_count,

    AVG(return_1y) AS avg_return_1y,

    AVG(cagr_3y) AS avg_cagr_3y,

    AVG(cagr_5y) AS avg_cagr_5y,

    AVG(annualized_volatility) AS avg_volatility,

    AVG(maximum_drawdown) AS avg_max_drawdown,

    SUM(aaum_cr_quarterly_avg) AS total_aum_cr

FROM fund_analytics

GROUP BY amc

ORDER BY total_aum_cr DESC
""")


# ============================================================
# VALIDATION
# ============================================================

print("\n" + "=" * 75)
print("ANALYSIS VALIDATION")
print("=" * 75)

tables = [
    "fund_analytics",
    "fund_annual_returns",
    "fund_monthly_returns",
    "fund_risk_metrics",
    "fund_drawdowns",
    "fund_category_summary",
    "fund_amc_summary"
]

for table in tables:

    count = con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    print(f"{table:<30} {count:>12,} rows")

# Proof that exclusions worked (must be 0)
leaked = con.execute("""
SELECT COUNT(*)
FROM fund_analytics
WHERE scheme_code IN (SELECT scheme_code FROM excluded_schemes)
""").fetchone()[0]

print(f"\nExcluded schemes present in fund_analytics: {leaked}  (must be 0)")


# ============================================================
# TOP FUNDS
# ============================================================

print("\n" + "=" * 75)
print("TOP 20 FUNDS — 3Y CAGR")
print("=" * 75)

top_funds = con.execute("""
SELECT

    scheme_name,
    amc,
    category_group_clean,

    return_1y,
    cagr_3y,
    cagr_5y,

    annualized_volatility,
    maximum_drawdown,

    aaum_cr_quarterly_avg

FROM fund_analytics

WHERE cagr_3y IS NOT NULL

ORDER BY cagr_3y DESC

LIMIT 20
""").fetchdf()

print(top_funds.to_string(index=False))


# ============================================================
# EXPORT FOR POWER BI / ANALYSIS
# ============================================================

print("\nExporting analytical tables...")

export_tables = [
    "fund_analytics",
    "fund_annual_returns",
    "fund_monthly_returns",
    "fund_category_summary",
    "fund_amc_summary"
]

for table in export_tables:

    output_file = OUTPUT_DIR / f"{table}.parquet"

    con.execute(f"""
        COPY {table}
        TO '{output_file.as_posix()}'
        (FORMAT PARQUET)
    """)

    print(f"✓ {output_file}")


# ============================================================
# CLOSE
# ============================================================

