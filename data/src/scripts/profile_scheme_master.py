import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE))          # add read_only=True on the check scripts


print("=" * 70)
print("SCHEME MASTER PROFILE")
print("=" * 70)


# ------------------------------------------------------------
# AMC
# ------------------------------------------------------------

print("\nTOP AMCs")

print(
    con.execute("""
        SELECT
            amc,
            COUNT(*) AS schemes
        FROM scheme_master
        GROUP BY amc
        ORDER BY schemes DESC
        LIMIT 20
    """).fetchdf().to_string(index=False)
)


# ------------------------------------------------------------
# PLAN
# ------------------------------------------------------------

print("\nSCHEME PLAN")

print(
    con.execute("""
        SELECT
            scheme_plan,
            COUNT(*) AS schemes
        FROM scheme_master
        GROUP BY scheme_plan
        ORDER BY schemes DESC
    """).fetchdf().to_string(index=False)
)


# ------------------------------------------------------------
# OPTION
# ------------------------------------------------------------

print("\nSCHEME OPTION")

print(
    con.execute("""
        SELECT
            scheme_option,
            COUNT(*) AS schemes
        FROM scheme_master
        GROUP BY scheme_option
        ORDER BY schemes DESC
    """).fetchdf().to_string(index=False)
)


# ------------------------------------------------------------
# CATEGORY GROUP
# ------------------------------------------------------------

print("\nCATEGORY GROUP")

print(
    con.execute("""
        SELECT
            category_group_clean,
            COUNT(*) AS schemes
        FROM scheme_master
        GROUP BY category_group_clean
        ORDER BY schemes DESC
    """).fetchdf().to_string(index=False)
)


# ------------------------------------------------------------
# ACTIVE STATUS
# ------------------------------------------------------------

print("\nACTIVE STATUS")

print(
    con.execute("""
        SELECT
            is_active,
            COUNT(*) AS schemes
        FROM scheme_master
        GROUP BY is_active
    """).fetchdf().to_string(index=False)
)


# ------------------------------------------------------------
# ACTIVE + DIRECT + GROWTH
# ------------------------------------------------------------

print("\nACTIVE + DIRECT + GROWTH")

print(
    con.execute("""
        SELECT
            category_group_clean,
            COUNT(*) AS schemes
        FROM scheme_master
        WHERE is_active = TRUE
          AND LOWER(scheme_plan) = 'direct'
          AND LOWER(scheme_option) = 'growth'
        GROUP BY category_group_clean
        ORDER BY schemes DESC
    """).fetchdf().to_string(index=False)
)


con.close()