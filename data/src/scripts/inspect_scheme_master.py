import pandas as pd

from config import SCHEME_FILE


df = pd.read_csv(SCHEME_FILE)


print("Shape:", df.shape)


print("\nColumns:")
print(df.columns.tolist())


print("\nFirst 5 rows:")
print(df.head().to_string())


print("\nMissing values:")
print(
    df.isna().sum().sort_values(ascending=False)
)