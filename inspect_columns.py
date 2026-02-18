import pandas as pd

df = pd.read_csv('csv/csvGenerados/players_with_features.csv')
print("COLUMNAS DEL CSV:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print("\nBuscando columnas relacionadas a minutos...")
minutos_cols = [c for c in df.columns if 'min' in c.lower()]
print(f"Minutos: {minutos_cols}")

print("\nBuscando columnas relacionadas a puntos/fantasy...")
puntos_cols = [c for c in df.columns if 'punt' in c.lower() or 'fantasy' in c.lower() or 'pf' in c.lower()]
print(f"Puntos: {puntos_cols}")

print("\nPrimeras 3 filas:")
print(df.head(3))
