import pandas as pd

from config import NAV_FILE


print("=" * 70)
print("LOADING MUTUAL FUND NAV DATA")
print("=" * 70)


df = pd.read_parquet(NAV_FILE)


print("\nShape:")
print(df.shape)


print("\nColumns:")

for column in df.columns:
    print(" -", column)


print("\nData types:")
print(df.dtypes)


print("\nFirst 10 rows:")
print(df.head(10).to_string())


print("\nMissing values:")
print(df.isna().sum())


print("\nDuplicate rows:")
print(df.duplicated().sum())


print("\nMemory usage:")
print(
    f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
)