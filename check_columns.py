import pandas as pd

df = pd.read_csv('csv/csvGenerados/players_with_features.csv')

print("All columns:")
for col in sorted(df.columns):
    print(f"  {col}")

print("\n\nDefensive-related columns:")
defensive_cols = [c for c in df.columns if any(word in c.lower() for word in ['duel', 'tackle', 'intercept', 'clear', 'block', 'aerial'])]
for col in sorted(defensive_cols):
    print(f"  {col}")

print("\n\nDF sample (first row):")
print(df.iloc[0])
