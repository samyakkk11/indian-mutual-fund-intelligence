import duckdb
from config import DB_FILE

con = duckdb.connect(str(DB_FILE), read_only=True)    # add read_only=True on the check scripts



print("=" * 70)
print("SCHEME MASTER - COLUMN NAMES")
print("=" * 70)

print(
    con.execute("""
        DESCRIBE scheme_master
    """).fetchdf().to_string(index=False)
)

con.close()