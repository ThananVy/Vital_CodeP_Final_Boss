import pandas as pd
df = pd.read_excel('MaterData 04-02-26.xlsx', nrows=5)
print("Columns:", list(df.columns))
print("\nFirst 2 rows:")
print(df.head(2).to_string())