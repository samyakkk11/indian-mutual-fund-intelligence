from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

# config.py is located at:
# project/data/src/scripts/config.py
#
# parents[0] = scripts
# parents[1] = src
# parents[2] = data
# parents[3] = project root

ROOT = Path(__file__).resolve().parents[3]


# ============================================================
# DIRECTORIES
# ============================================================

RAW_DIR = ROOT / "data" / "raw"

DB_DIR = ROOT / "data" / "src" / "database"

PROCESSED_DIR = ROOT / "data" / "src" / "processed"


# ============================================================
# FILES
# ============================================================

NAV_FILE = RAW_DIR / "amfi_nav_master.parquet"

SCHEME_FILE = RAW_DIR / "amfi_nav_master_latest.csv"

DB_FILE = DB_DIR / "mutual_funds.duckdb"
