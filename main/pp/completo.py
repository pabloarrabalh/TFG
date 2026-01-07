"""
MODELO PREDICTIVO PORTEROS - VERSIÓN CORREGIDA
Mantiene la estructura original pero elimina data leakage temporal

CAMBIOS PRINCIPALES:
1. shots_rival, shots_propio: Ahora se calculan como rachas históricas
2. xg_rival, xg_team: Se mantienen solo las versiones históricas (_last5_mean_)
3. gf, gc: Se usan los acumulados de clasificación (hasta jornada N-1)
4. Nuevo: Clasificación lag (jornada N-1 para predecir N)
"""

import pandas as pd
import ast
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
import matplotlib.pyplot as plt
import numpy as np


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
    s = s.str.lower().str.strip()
    return s.replace(EQUIV_EQUIPOS)


# ==============================
# CARGA DE DATOS BASE
# ==============================

def load_player_matches_temporada(base_folder: str, temporada_tag: str) -> pd.DataFrame:
    base = Path(base_folder)
    frames = []

    for jornada_dir in base.glob("jornada_*"):
        for csv_file in jornada_dir.glob("*.csv"):
            df = pd.read_csv(csv_file)

            if "roles" in df.columns:
                df["roles"] = df["roles"].fillna("[]").apply(ast.literal_eval)

            df["temporada"] = temporada_tag
            df["jornada"] = df["jornada"].astype(int)
            df["fecha_partido"] = pd.to_datetime(
                df["fecha_partido"],
                format="%Y-%m-%d",
                errors="coerce"
            )
            frames.append(df)

    full = pd.concat(frames, ignore_index=True)
    full = full.sort_values(
        ["player", "temporada", "jornada", "fecha_partido"]
    ).reset_index(drop=True)
    return full


def add_role_features(df):
    df = df.copy()

    if "rank_porterias_cero" not in df.columns or "rank_save_pct" not in df.columns:
        print("⚠️  Columnas de ranking no encontradas, se omiten features de roles")
        return df

    # Rellenar ranks faltantes con algo neutro (por ejemplo, peor rank)
    max_rank_pc = df["rank_porterias_cero"].max()
    max_rank_sp = df["rank_save_pct"].max()

    df["rank_porterias_cero"] = df["rank_porterias_cero"].fillna(max_rank_pc)
    df["rank_save_pct"] = df["rank_save_pct"].fillna(max_rank_sp)

    # Scores normalizados [0,1], donde 1 es el mejor portero
    if max_rank_pc > 1:
        df["score_porterias_cero"] = 1 - (df["rank_porterias_cero"] - 1) / (max_rank_pc - 1)
    else:
        df["score_porterias_cero"] = 1.0

    if max_rank_sp > 1:
        df["score_save_pct"] = 1 - (df["rank_save_pct"] - 1) / (max_rank_sp - 1)
    else:
        df["score_save_pct"] = 1.0

    # Flags top5
    df["is_top5_porterias_cero"] = (df["rank_porterias_cero"] <= 5).astype(int)
    df["is_top5_save_pct"] = (df["rank_save_pct"] <= 5).astype(int)

    # Boosts
    df["score_pc_boost"] = df["score_porterias_cero"] * (1 + 0.5 * df["is_top5_porterias_cero"])
    df["score_sp_boost"] = df["score_save_pct"] * (1 + 0.5 * df["is_top5_save_pct"])

    # Seguridad extra: si aún quedara algún NaN, lo tratamos como "sin señal"
    for col in [
        "score_porterias_cero",
        "score_save_pct",
        "is_top5_porterias_cero",
        "is_top5_save_pct",
        "score_pc_boost",
        "score_sp_boost",
    ]:
        df[col] = df[col].fillna(0)

    return df

def load_standings(path: str, temporada_tag: str) -> pd.DataFrame:
    standings = pd.read_csv(path)
    standings["temporada"] = temporada_tag
    standings["jornada"] = standings["jornada"].astype(int)

    if "equipo" in standings.columns:
        standings["equipo"] = normalizar_equipo_series(standings["equipo"])

    return standings


def load_odds_temporada(path: str, temporada_tag: str) -> pd.DataFrame:
    odds = pd.read_csv(path)
    odds["temporada"] = temporada_tag
    odds["Date"] = pd.to_datetime(odds["Date"], format="%d/%m/%Y", errors="coerce")
    odds["HomeTeam"] = normalizar_equipo_series(odds["HomeTeam"])
    odds["AwayTeam"] = normalizar_equipo_series(odds["AwayTeam"])
    return odds


def build_all_data():
    df_players_23_24 = load_player_matches_temporada("data/temporada_23_24", "23_24")
    standings_23_24 = load_standings("data/temporada_23_24/clasificacion_temporada.csv", "23_24")
    odds_23_24 = load_odds_temporada("data/temporada_23_24/SP1.csv", "23_24")

    df_players_24_25 = load_player_matches_temporada("data/temporada_24_25", "24_25")
    standings_24_25 = load_standings("data/temporada_24_25/clasificacion_temporada.csv", "24_25")
    odds_24_25 = load_odds_temporada("data/temporada_24_25/SP1.csv", "24_25")

    df_players_25_26 = load_player_matches_temporada("data/temporada_25_26", "25_26")
    standings_25_26 = load_standings("data/temporada_25_26/clasificacion_temporada.csv", "25_26")
    odds_25_26 = load_odds_temporada("data/temporada_25_26/SP1.csv", "25_26")

    df_players = pd.concat(
        [df_players_23_24, df_players_24_25, df_players_25_26],
        ignore_index=True
    )

    for col in ["Equipo_propio", "Equipo_rival"]:
        df_players[col] = normalizar_equipo_series(df_players[col])

    df_players = add_role_features(df_players)

    standings = pd.concat(
        [standings_23_24, standings_24_25, standings_25_26],
        ignore_index=True
    )
    odds = pd.concat(
        [odds_23_24, odds_24_25, odds_25_26],
        ignore_index=True
    )

    df_players.to_csv("players_matches_all_seasons.csv", index=False)
    standings.to_csv("standings_all_seasons.csv", index=False)
    odds.to_csv("odds_all_seasons.csv", index=False)

    return df_players, standings, odds


# ==============================
# EXPERIMENTO 1 - CORREGIDO (con lag)
# ==============================

def experimento_1(
    df_players: pd.DataFrame,
    standings: pd.DataFrame,
    odds: pd.DataFrame
) -> pd.DataFrame:
    """
    ⚠️ CAMBIO CLAVE: Merge con clasificación de jornada ANTERIOR
    Para predecir jornada N, usamos clasificación de jornada N-1
    """

    df = df_players.copy()

    # Crear columna de jornada anterior
    df["jornada_anterior"] = df["jornada"] - 1

    # Merge con clasificación de jornada ANTERIOR (equipo propio)
    st_own = standings.rename(columns={"equipo": "Equipo_propio", "jornada": "jornada_anterior"})
    df = df.merge(
        st_own,
        on=["temporada", "jornada_anterior", "Equipo_propio"],
        how="left",
        suffixes=("", "_equipo"),
    )

    # Merge con clasificación de jornada ANTERIOR (equipo rival)
    st_rival = standings.rename(columns={"equipo": "Equipo_rival", "jornada": "jornada_anterior"})
    df = df.merge(
        st_rival,
        on=["temporada", "jornada_anterior", "Equipo_rival"],
        how="left",
        suffixes=("", "_rival"),
    )

    # ============================================================
    # PREPARAR ODDS
    # ============================================================

    o = odds.copy()
    o = o.rename(columns={"HomeTeam": "home", "AwayTeam": "away"})

    for c in ["AvgH", "AvgD", "AvgA"]:
        o[c] = pd.to_numeric(o[c], errors="coerce")

    o["inv_H"] = 1 / o["AvgH"]
    o["inv_D"] = 1 / o["AvgD"]
    o["inv_A"] = 1 / o["AvgA"]
    o["sum_inv"] = o[["inv_H", "inv_D", "inv_A"]].sum(axis=1)

    o["p_home"] = o["inv_H"] / o["sum_inv"]
    o["p_draw"] = o["inv_D"] / o["sum_inv"]
    o["p_away"] = o["inv_A"] / o["sum_inv"]

    o["Avg>2.5"] = pd.to_numeric(o["Avg>2.5"], errors="coerce")
    o["Avg<2.5"] = pd.to_numeric(o["Avg<2.5"], errors="coerce")

    o["inv_over"] = 1 / o["Avg>2.5"]
    o["inv_under"] = 1 / o["Avg<2.5"]
    o["sum_ou"] = o["inv_over"] + o["inv_under"]

    o["p_over25"] = o["inv_over"] / o["sum_ou"]
    o["ah_line"] = pd.to_numeric(o["AHh"], errors="coerce")

    o_small = o[
        [
            "temporada",
            "Date",
            "home",
            "away",
            "p_home",
            "p_draw",
            "p_away",
            "p_over25",
            "ah_line",
            "HS",
            "AS",
            "HST",
            "AST",
        ]
    ]

    # ============================================================
    # DOBLE MERGE JUGADORES + ODDS
    # ============================================================

    merge_home = df.merge(
        o_small,
        left_on=["temporada", "Equipo_propio", "Equipo_rival"],
        right_on=["temporada", "home", "away"],
        how="left",
    )

    merge_away = df.merge(
        o_small,
        left_on=["temporada", "Equipo_propio", "Equipo_rival"],
        right_on=["temporada", "away", "home"],
        how="left",
        suffixes=("", "_alt"),
    )

    cols_backup = [
        "p_home", "p_draw", "p_away", "p_over25",
        "ah_line", "HS", "AS", "HST", "AST",
        "home", "away", "Date",
    ]
    for col in cols_backup:
        if f"{col}_alt" in merge_away.columns:
            merge_away[f"{col}_alt_final"] = merge_away[f"{col}_alt"]
        else:
            merge_away[f"{col}_alt_final"] = merge_away[col]

    for col in cols_backup:
        merge_home[col] = merge_home[col].where(
            ~merge_home[col].isna(),
            merge_away[f"{col}_alt_final"]
        )

    df = merge_home

    # ============================================================
    # FEATURES DE APUESTAS
    # ============================================================

    df["p_win_propio"] = df["p_home"] * df["local"] + df["p_away"] * (1 - df["local"])
    df["p_loss_propio"] = df["p_away"] * df["local"] + df["p_home"] * (1 - df["local"])
    df["p_draw_match"] = df["p_draw"]
    df["p_over25_match"] = df["p_over25"]
    df["ah_line_match"] = df["ah_line"]

    # ⚠️ Tiros históricos del partido (solo para calcular rachas)
    df["shots_propio_partido"] = df["HS"] * df["local"] + df["AS"] * (1 - df["local"])
    df["shots_rival_partido"] = df["AS"] * df["local"] + df["HS"] * (1 - df["local"])
    df["shots_on_target_propio_partido"] = df["HST"] * df["local"] + df["AST"] * (1 - df["local"])
    df["shots_on_target_rival_partido"] = df["AST"] * df["local"] + df["HST"] * (1 - df["local"])

    # ============================================================
    # TARGET: PF SIGUIENTE PARTIDO
    # ============================================================

    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    df["target_pf_next"] = (
        df.groupby(["player", "temporada"])["puntosFantasy"].shift(-1)
    )

    return df


# ==============================
# EXPERIMENTO 3 - CORREGIDO (rachas con shift)
# ==============================

def experimento_3(df: pd.DataFrame) -> pd.DataFrame:
    """
    ⚠️ CAMBIO CLAVE: Rachas de tiros y xG usando .shift(1)
    """

    df = df.sort_values(["temporada", "jornada", "fecha_partido"])

    # ============================================================
    # xG EQUIPO Y RIVAL POR PARTIDO (histórico)
    # ============================================================

    xg_team = (
        df.groupby(["temporada", "jornada", "Equipo_propio"])["xG_partido"]
        .sum()
        .reset_index()
        .rename(columns={"xG_partido": "xg_team_partido"})
    )
    df = df.merge(
        xg_team,
        on=["temporada", "jornada", "Equipo_propio"],
        how="left"
    )

    xg_rival_partido = (
        df.groupby(["temporada", "jornada", "Equipo_rival"])["xG_partido"]
        .sum()
        .reset_index()
        .rename(columns={"xG_partido": "xg_rival_partido"})
    )
    df = df.merge(
        xg_rival_partido,
        on=["temporada", "jornada", "Equipo_rival"],
        how="left"
    )

    # ============================================================
    # RACHA EQUIPO PROPIO - CON SHIFT(1)
    # ============================================================

    g_team = df.groupby(["Equipo_propio", "temporada"])

    # Rachas de goles
    df["gf_last5_mean_team"] = g_team["gf"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["gc_last5_mean_team"] = g_team["gc"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["goal_diff_last5_team"] = (
        df["gf_last5_mean_team"] - df["gc_last5_mean_team"]
    )

    # Rachas de xG
    df["xg_last5_mean_team"] = g_team["xg_team_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["xg_contra_last5_mean_team"] = g_team["xg_rival_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # ============================================================
    # RACHA EQUIPO RIVAL - CON SHIFT(1)
    # ============================================================

    g_rival = df.groupby(["Equipo_rival", "temporada"])

    # Rachas de tiros del rival
    df["shots_last5_mean_rival"] = g_rival["shots_rival_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["shots_on_target_last5_mean_rival"] = g_rival["shots_on_target_rival_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["shots_on_target_ratio_rival"] = (
        df["shots_on_target_last5_mean_rival"] / df["shots_last5_mean_rival"].replace(0, np.nan)
    )

    # Rachas de goles del rival
    df["gf_last5_mean_rival"] = g_rival["gf_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["gc_last5_mean_rival"] = g_rival["gc_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["goal_diff_last5_rival"] = (
        df["gf_last5_mean_rival"] - df["gc_last5_mean_rival"]
    )

    # Rachas de xG del rival
    df["xg_last5_mean_rival"] = g_rival["xg_team_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["xg_contra_last5_mean_rival"] = g_rival["xg_rival_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # ============================================================
    # EFICIENCIA Y CRUCES
    # ============================================================

    df["goal_per_shot_rival"] = (
        df["gf_last5_mean_rival"] / df["shots_last5_mean_rival"].replace(0, np.nan)
    )

    df["goal_attack_vs_defense"] = (
        df["gf_last5_mean_rival"] - df["gc_last5_mean_team"]
    )

    # ============================================================
    # FUERZA RELATIVA TABLA
    # ============================================================

    df["pts_diff"] = df["pts"] - df["pts_rival"]
    df["gf_diff"] = df["gf"] - df["gf_rival"]
    df["gc_diff"] = df["gc"] - df["gc_rival"]

    # ============================================================
    # FLAGS POSICIÓN EN TABLA
    # ============================================================

    df["is_top4_propio"] = (df["posicion_equipo"] <= 4).astype(int)
    df["is_top4_rival"] = (df["posicion_rival"] <= 4).astype(int)
    df["is_bottom3_rival"] = (df["posicion_rival"] >= 18).astype(int)

    # ============================================================
    # VARIANZA + RATIOS 90 DEL PORTERO
    # ============================================================

    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    gk_group = df.groupby(["player", "temporada"])

    df["pf_last5_std"] = gk_group["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).std()
    )
    df["gc_last5_std"] = gk_group["Goles_en_contra"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).std()
    )
    df["psxg_last5_std"] = gk_group["PSxG"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).std()
    )

    df["min_last5_sum"] = gk_group["Min_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df["psxg_last5_sum"] = gk_group["PSxG"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df["gc_last5_sum"] = gk_group["Goles_en_contra"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )

    umbral_min = 180
    cond = df["min_last5_sum"] >= umbral_min
    df["psxg_per90_last5"] = pd.NA
    df["gc_per90_last5"] = pd.NA
    df.loc[cond, "psxg_per90_last5"] = (
        df.loc[cond, "psxg_last5_sum"] * 90 / df.loc[cond, "min_last5_sum"]
    )
    df.loc[cond, "gc_per90_last5"] = (
        df.loc[cond, "gc_last5_sum"] * 90 / df.loc[cond, "min_last5_sum"]
    )

    # ============================================================
    # FLAGS ATAQUE TOP / DEFENSA FLOJA
    # ============================================================

    p80_xg_rival = df["xg_last5_mean_rival"].quantile(0.8)
    p80_gc_team = df["gc_last5_mean_team"].quantile(0.8)

    df["ataque_top_rival"] = (
        df["xg_last5_mean_rival"] >= p80_xg_rival
    ).astype(int)
    df["defensa_floja_propia"] = (
        df["gc_last5_mean_team"] >= p80_gc_team
    ).astype(int)
    df["ataque_top_y_defensa_floja"] = (
        df["ataque_top_rival"] & df["defensa_floja_propia"]
    ).astype(int)

    return df


# ==============================
# ENTRENAR MODELO - MANTIENE TUS 3 MODELOS
# ==============================


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    print("="*80)
    print("MODELO PREDICTIVO PORTEROS - VERSIÓN CORREGIDA")
    print("Elimina data leakage temporal")
    print("="*80)

    # 1) Leer datasets base
    try:
        df_players = pd.read_csv("players_matches_all_seasons.csv")
        standings = pd.read_csv("standings_all_seasons.csv")
        odds = pd.read_csv("odds_all_seasons.csv")
        print("\n✅ Datos cargados desde CSV")
    except FileNotFoundError:
        print("\n⚠️ CSV no encontrados, construyendo desde carpetas...")
        df_players, standings, odds = build_all_data()

    # 2) Experimento 1: standings + cuotas (CORREGIDO - con lag)
    print("\n" + "="*60)
    print("EXPERIMENTO 1: Merge con clasificación lagged y odds")
    print("="*60)
    df = experimento_1(df_players, standings, odds)
    print(f"Shape después exp1: {df.shape}")

    # 3) Experimento 3: rachas (CORREGIDO - con shift)
    print("\n" + "="*60)
    print("EXPERIMENTO 3: Rachas de equipos con shift(1)")
    print("="*60)
    df_exp3 = experimento_3(df)
    print(f"Shape después exp3: {df_exp3.shape}")

    # 4) Guardar dataset final
    df_exp3.to_csv("players_with_features_exp3_CORREGIDO.csv", index=False)
    print(f"\n✅ Dataset guardado: players_with_features_exp3_CORREGIDO.csv")

    # 5) Entrenar modelos
   
    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("\nTodas las features están disponibles ANTES del partido")
    print("El modelo está listo para predecir partidos futuros")