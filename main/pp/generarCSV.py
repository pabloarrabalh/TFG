"""
MODELO PORTEROS - MÍNIMO FIX COMPLETO
Fix: odds processing + shapes
"""

import pandas as pd
import ast,os
import numpy as np
from pathlib import Path

EQUIV_EQUIPOS = {
    "las palmas": "las palmas", "ud las palmas": "las palmas",
    "athletic": "athletic", "ath bilbao": "athletic", "athletic club": "athletic",
    "atletico madrid": "atletico madrid", "ath madrid": "atletico madrid", "atl madrid": "atletico madrid",
    "barcelona": "barcelona", "fc barcelona": "barcelona",
    "real madrid": "real madrid", "rm": "real madrid",
    "real sociedad": "real sociedad", "sociedad": "real sociedad", "real sociedad de futbol": "real sociedad",
    "rayo vallecano": "rayo vallecano", "rayo": "rayo vallecano", "vallecano": "rayo vallecano",
    "valencia": "valencia", "valencia cf": "valencia",
    "mallorca": "mallorca", "rcd mallorca": "mallorca",
    "celta": "celta", "rc celta": "celta", "rc celta de vigo": "celta",
    "cadiz": "cadiz", "cadiz cf": "cadiz",
    "girona": "girona", "girona fc": "girona",
    "granada": "granada", "granada cf": "granada",
    "osasuna": "osasuna", "ca osasuna": "osasuna",
    "almeria": "almeria", "ud almeria": "almeria",
    "villarreal": "villarreal", "villarreal cf": "villarreal",
    "getafe": "getafe", "getafe cf": "getafe",
    "betis": "betis", "real betis": "betis", "real betis balompie": "betis",
    "espanyol": "espanyol", "rcd espanyol": "espanyol", "espanol": "espanyol",
    "leganes": "leganes", "cd leganes": "leganes",
    "valladolid": "valladolid", "real valladolid": "valladolid", "real valladolid cf": "valladolid",
}

def normalizar_equipo_series(s: pd.Series) -> pd.Series:
    return s.str.lower().str.strip().replace(EQUIV_EQUIPOS)

def load_data_temporada(base_folder: str, temporada_tag: str):
    base = Path(base_folder)
    frames = []
    
    for jornada_dir in base.glob("jornada_*"):
        for csv_file in jornada_dir.glob("*.csv"):
            df = pd.read_csv(csv_file)
            if "roles" in df.columns:
                df["roles"] = df["roles"].fillna("[]").apply(ast.literal_eval)
            df["temporada"] = temporada_tag
            df["jornada"] = df["jornada"].astype(int)
            df["fecha_partido"] = pd.to_datetime(df["fecha_partido"], format="%Y-%m-%d", errors="coerce")
            frames.append(df)
    
    return pd.concat(frames, ignore_index=True).sort_values(["player", "temporada", "jornada", "fecha_partido"]).reset_index(drop=True)

def add_role_features(df):
    df = df.copy()
    if "rank_porterias_cero" not in df.columns or "rank_save_pct" not in df.columns:
        return df
    
    max_rank_pc = df["rank_porterias_cero"].max()
    max_rank_sp = df["rank_save_pct"].max()
    
    df["rank_porterias_cero"] = df["rank_porterias_cero"].fillna(max_rank_pc)
    df["rank_save_pct"] = df["rank_save_pct"].fillna(max_rank_sp)
    
    df["score_porterias_cero"] = 1 - (df["rank_porterias_cero"] - 1) / (max_rank_pc - 1) if max_rank_pc > 1 else 1.0
    df["score_save_pct"] = 1 - (df["rank_save_pct"] - 1) / (max_rank_sp - 1) if max_rank_sp > 1 else 1.0
    
    df["is_top5_porterias_cero"] = (df["rank_porterias_cero"] <= 5).astype(int)
    df["is_top5_save_pct"] = (df["rank_save_pct"] <= 5).astype(int)
    
    df["score_pc_boost"] = df["score_porterias_cero"] * (1 + 0.5 * df["is_top5_porterias_cero"])
    df["score_sp_boost"] = df["score_save_pct"] * (1 + 0.5 * df["is_top5_save_pct"])
    
    for col in ["score_porterias_cero", "score_save_pct", "is_top5_porterias_cero", "is_top5_save_pct", "score_pc_boost", "score_sp_boost"]:
        df[col] = df[col].fillna(0)
    
    return df

def build_all_data():
    temporadas = ["23_24", "24_25", "25_26"]
    
    df_players = pd.concat([
        load_data_temporada(f"data/temporada_{t}", t) for t in temporadas
    ], ignore_index=True)
    
    for col in ["Equipo_propio", "Equipo_rival"]:
        df_players[col] = normalizar_equipo_series(df_players[col])
    
    df_players = add_role_features(df_players)
    
    standings = pd.concat([
        pd.read_csv(f"data/temporada_{t}/clasificacion_temporada.csv").assign(temporada=t, jornada=lambda x: x.jornada.astype(int))
        .assign(equipo=lambda x: normalizar_equipo_series(x.equipo)) 
        for t in temporadas
    ], ignore_index=True)
    
    odds = pd.concat([
        pd.read_csv(f"data/temporada_{t}/SP1.csv").assign(temporada=t)
        .assign(Date=lambda x: pd.to_datetime(x.Date, format="%d/%m/%Y", errors="coerce"))
        .assign(**{k: normalizar_equipo_series(v) for k, v in [("HomeTeam", "HomeTeam"), ("AwayTeam", "AwayTeam")]})
        for t in temporadas
    ], ignore_index=True)
    
    df_players.to_csv("players_matches_all_seasons.csv", index=False)
    standings.to_csv("standings_all_seasons.csv", index=False)
    odds.to_csv("odds_all_seasons.csv", index=False)
    
    return df_players, standings, odds

def process_odds(odds: pd.DataFrame) -> pd.DataFrame:
    """✅ FIX: procesado seguro de odds"""
    o = odds.rename(columns={"HomeTeam": "home", "AwayTeam": "away"}).copy()
    
    # Conversión numérica segura
    for c in ["AvgH", "AvgD", "AvgA", "Avg>2.5", "Avg<2.5", "AHh"]:
        o[c] = pd.to_numeric(o[c], errors="coerce").fillna(999)
    
    # Inversas seguras (evitar división por cero)
    o["inv_H"] = np.where(o["AvgH"] > 0, 1 / o["AvgH"], 0)
    o["inv_D"] = np.where(o["AvgD"] > 0, 1 / o["AvgD"], 0)
    o["inv_A"] = np.where(o["AvgA"] > 0, 1 / o["AvgA"], 0)
    o["sum_inv"] = o[["inv_H", "inv_D", "inv_A"]].sum(axis=1)
    
    # Normalizar probabilidades
    o["p_home"] = o["inv_H"] / o["sum_inv"].replace(0, 1)
    o["p_draw"] = o["inv_D"] / o["sum_inv"].replace(0, 1)
    o["p_away"] = o["inv_A"] / o["sum_inv"].replace(0, 1)
    
    # Over/Under seguro
    o["inv_over"] = np.where(o["Avg>2.5"] > 0, 1 / o["Avg>2.5"], 0)
    o["inv_under"] = np.where(o["Avg<2.5"] > 0, 1 / o["Avg<2.5"], 0)
    o["sum_ou"] = o["inv_over"] + o["inv_under"]
    o["p_over25"] = o["inv_over"] / o["sum_ou"].replace(0, 1)
    
    return o[["temporada", "Date", "home", "away", "p_home", "p_draw", "p_away", "p_over25", "AHh", "HS", "AS", "HST", "AST"]].rename(columns={"AHh": "ah_line"})

def main():
    print("="*40)
    print("MERGE MÍNIMO - FIX ODDS")
    print("="*40)
    
    try:
        df_players = pd.read_csv("players_matches_all_seasons.csv")
        standings = pd.read_csv("standings_all_seasons.csv")
        odds = pd.read_csv("odds_all_seasons.csv")
        print("✅ CSV cargados")
    except FileNotFoundError:
        print("🔨 Construyendo...")
        df_players, standings, odds = build_all_data()
    
    df = df_players.copy()
    df["jornada_anterior"] = df["jornada"] - 1
    
    # Standings lagged
    st_own = standings.rename(columns={"equipo": "Equipo_propio", "jornada": "jornada_anterior"})
    df = df.merge(st_own, on=["temporada", "jornada_anterior", "Equipo_propio"], how="left", suffixes=("", "_own"))
    
    st_rival = standings.rename(columns={"equipo": "Equipo_rival", "jornada": "jornada_anterior"})
    df = df.merge(st_rival, on=["temporada", "jornada_anterior", "Equipo_rival"], how="left", suffixes=("", "_rival"))
    
    # Odds
    o_small = process_odds(odds)
    merge_home = df.merge(o_small, left_on=["temporada", "Equipo_propio", "Equipo_rival"], 
                         right_on=["temporada", "home", "away"], how="left")
    merge_away = df.merge(o_small, left_on=["temporada", "Equipo_propio", "Equipo_rival"], 
                         right_on=["temporada", "away", "home"], how="left", suffixes=("", "_alt"))
    
    cols_odds = ["p_home", "p_draw", "p_away", "p_over25", "ah_line", "HS", "AS", "HST", "AST"]
    for col in cols_odds:
        merge_away[f"{col}_alt_final"] = merge_away.get(f"{col}_alt", merge_away[col])
        merge_home[col] = merge_home[col].fillna(merge_away[f"{col}_alt_final"])
    
    df = merge_home
    
    # Features odds
    df["p_win_propio"] = df["p_home"] * df["local"] + df["p_away"] * (1 - df["local"])
    df["p_loss_propio"] = df["p_away"] * df["local"] + df["p_home"] * (1 - df["local"])
    df["p_draw_match"] = df["p_draw"]
    df["p_over25_match"] = df["p_over25"]
    df["ah_line_match"] = df["ah_line"]
    
    df["shots_propio_partido"] = df["HS"] * df["local"] + df["AS"] * (1 - df["local"])
    df["shots_rival_partido"] = df["AS"] * df["local"] + df["HS"] * (1 - df["local"])
    df["shots_on_target_propio_partido"] = df["HST"] * df["local"] + df["AST"] * (1 - df["local"])
    df["shots_on_target_rival_partido"] = df["AST"] * df["local"] + df["HST"] * (1 - df["local"])
    
    # Target
    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    df["target_pf_next"] = df.groupby(["player", "temporada"])["puntosFantasy"].shift(-1)
    
    os.makedirs("csv/csvGenerados", exist_ok=True)
    df.to_csv("csv/csvGenerados/players_with_features_MINIMO.csv", index=False)
    print(f"✅ TODO OK: {df.shape}")
    print("Standings N-1 + odds procesados + roles")

if __name__ == "__main__":
    main()
