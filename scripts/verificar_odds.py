#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICAR CARGA DE ODDS - Barcelona vs Osasuna Jornada 3
"""
import pandas as pd
import numpy as np

print("\n" + "="*80)
print("VERIFICACION DE CARGA DE ODDS")
print("="*80 + "\n")

# 1. Cargar datos principales
print("[1] Cargando datos de jugadores...")
df = pd.read_csv('csv/csvGenerados/players_with_features.csv')
print(f"    Total registros: {len(df)}")
print(f"    Columnas: {df.columns.tolist()[:10]}...")

# 2. Cargar odds
print("\n[2] Cargando odds...")
odds_df = pd.read_csv('csv/csvDescargados/live_odds_cache.csv')
print(f"    Total odds: {len(odds_df)}")
print(f"    Columnas odds: {odds_df.columns.tolist()}\n")

# 3. Mostrar primeras filas de odds
print("Primeras 5 filas de odds:")
print(odds_df[['jornada', 'home', 'away', 'p_home', 'p_draw', 'p_away']].head())

# 4. Buscar un partido específico
print("\n[3] Buscando Barcelona vs Osasuna Jornada 3...")
barcelona_match = odds_df[(odds_df['jornada'] == 3) & 
                          ((odds_df['home'].str.lower().str.contains('barcelona|barça', na=False)) |
                           (odds_df['away'].str.lower().str.contains('barcelona|barça', na=False)))]

print(f"\nPartidos de Barcelona en jornada 3:")
print(barcelona_match[['jornada', 'home', 'away', 'p_home', 'p_draw', 'p_away']])

# 5. Buscar jugadores de Barcelona en jornada 3
print("\n[4] Jugadores de Barcelona en jornada 3...")
barcelona_players = df[(df['jornada'] == 3) & (df['equipo_propio'].str.lower().str.contains('barcelona|barça', na=False))]
print(f"    Total jugadores Barcelona en jornada 3: {len(barcelona_players)}")
print(f"    Primeros 5:")
print(barcelona_players[['player', 'posicion', 'equipo_propio', 'equipo_rival', 'local', 'jornada']].head())

# 6. Normalizar nombres de equipos
def normalizar_equipo(nombre):
    if pd.isna(nombre):
        return None
    nombre = str(nombre).lower().strip()
    mapeos = {
        'ath bilbao': 'athletic bilbao',
        'ath madrid': 'atletico madrid',
        'vallecano': 'rayo',
        'ca osasuna': 'osasuna',
    }
    return mapeos.get(nombre, nombre)

# Aplicar normalizacion
df_test = df.copy()
df_test['equipo_propio_norm'] = df_test['equipo_propio'].apply(normalizar_equipo)
df_test['equipo_rival_norm'] = df_test['equipo_rival'].apply(normalizar_equipo)
odds_test = odds_df.copy()
odds_test['home_norm'] = odds_test['home'].apply(normalizar_equipo)
odds_test['away_norm'] = odds_test['away'].apply(normalizar_equipo)

print("\n[5] Nombres normalizados...")
print("Odds normalizados jornada 3:")
print(odds_test[odds_test['jornada'] == 3][['jornada', 'home_norm', 'away_norm', 'p_home', 'p_draw', 'p_away']])

# 7. Buscar si existe match Barcelona-Osasuna
print("\n[6] Buscando Barcelona vs Osasuna con nombres normalizados...")
barcelona_norm = df_test[(df_test['jornada'] == 3) & (df_test['equipo_propio_norm'] == 'barcelona')].iloc[:3] if len(df_test[(df_test['jornada'] == 3) & (df_test['equipo_propio_norm'] == 'barcelona')]) > 0 else df_test[(df_test['jornada'] == 3) & (df_test['equipo_rival_norm'] == 'barcelona')].iloc[:3] if len(df_test[(df_test['jornada'] == 3) & (df_test['equipo_rival_norm'] == 'barcelona')]) > 0 else None

if barcelona_norm is not None:
    print("Ejemplos de jugadores Barcelona jornada 3:")
    for idx, row in barcelona_norm.iterrows():
        print(f"\n  Jugador: {row['player']}")
        print(f"  Equipo propio: {row['equipo_propio']} (normalizado: {row['equipo_propio_norm']})")
        print(f"  Rival: {row['equipo_rival']} (normalizado: {row['equipo_rival_norm']})")
        print(f"  Local: {row['local']}")
        
        # Buscar odds
        if row['local'] == 1:
            match = odds_test[(odds_test['jornada'] == 3) & (odds_test['home_norm'] == row['equipo_propio_norm'])]
            if not match.empty:
                print(f"  MATCH ENCONTRADO (como LOCAL):")
                print(f"    p_home (victoria): {match.iloc[0]['p_home']:.4f}")
                print(f"    p_away (derrota): {match.iloc[0]['p_away']:.4f}")
            else:
                print(f"  NO MATCH (buscaba como local {row['equipo_propio_norm']})")
        else:
            match = odds_test[(odds_test['jornada'] == 3) & (odds_test['away_norm'] == row['equipo_propio_norm'])]
            if not match.empty:
                print(f"  MATCH ENCONTRADO (como VISITANTE):")
                print(f"    p_away (victoria): {match.iloc[0]['p_away']:.4f}")
                print(f"    p_home (derrota): {match.iloc[0]['p_home']:.4f}")
            else:
                print(f"  NO MATCH (buscaba como visitante {row['equipo_propio_norm']})")

print("\n" + "="*80 + "\n")
