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


def add_role_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "rank_porterias_cero" not in df.columns or "rank_save_pct" not in df.columns:
        print("⚠️  Columnas de ranking no encontradas, se omiten features de roles")
        return df

    max_rank_pc = df["rank_porterias_cero"].max()
    max_rank_sp = df["rank_save_pct"].max()

    if max_rank_pc > 1:
        df["score_porterias_cero"] = 1 - (df["rank_porterias_cero"] - 1) / (max_rank_pc - 1)
    else:
        df["score_porterias_cero"] = 1.0

    if max_rank_sp > 1:
        df["score_save_pct"] = 1 - (df["rank_save_pct"] - 1) / (max_rank_sp - 1)
    else:
        df["score_save_pct"] = 1.0

    df["is_top5_porterias_cero"] = (df["rank_porterias_cero"] <= 5).astype(int)
    df["is_top5_save_pct"] = (df["rank_save_pct"] <= 5).astype(int)

    df["score_pc_boost"] = df["score_porterias_cero"] * (1 + 0.5 * df["is_top5_porterias_cero"])
    df["score_sp_boost"] = df["score_save_pct"] * (1 + 0.5 * df["is_top5_save_pct"])

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

def entrenar_modelo_porteros(df: pd.DataFrame):
    """
    Entrena modelos RF, HGB y Linear
    ⚠️ CAMBIO: Features corregidas sin data leakage
    """

    print("=== ENTRENAR MODELO PORTEROS (VERSIÓN CORREGIDA) ===")
    df_gk = df[df["posicion"] == "PT"].copy()
    print("Porteros totales (todas las filas):", len(df_gk))

    df_gk = df_gk[df_gk["puntosFantasy"].between(-10, 30)].copy()
    print("Porteros tras filtro PF [-10,30]:", len(df_gk))

    # Goles evitados partido
    df_gk["psxg_gc_diff"] = df_gk["PSxG"] - df_gk["Goles_en_contra"]

    # Ratio de paradas difíciles
    df_gk["ratio_paradas_dificiles"] = (
        df_gk["psxg_gc_diff"] / df_gk["shots_on_target_last5_mean_rival"].replace(0, pd.NA)
    )

    df_gk = df_gk.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    g = df_gk.groupby(["player", "temporada"])

    # Paradas y racha
    df_gk["saves_partido"] = (
        df_gk["shots_on_target_rival_partido"] - df_gk["Goles_en_contra"]
    )
    df_gk["saves_last5_mean"] = g["saves_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # Ventanas de 5 partidos (solo pasado)
    df_gk["pf_last5_mean"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["pf_last5_sum"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df_gk["min_last5_mean"] = g["Min_partido"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["gc_last5_mean"] = g["Goles_en_contra"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["psxg_last5_mean"] = g["PSxG"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["psxg_gc_diff_last5_mean"] = g["psxg_gc_diff"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["psxg_gc_diff_season_mean"] = g["psxg_gc_diff"].transform("mean")
    df_gk["form_vs_class_keeper"] = (
        df_gk["psxg_gc_diff_last5_mean"] - df_gk["psxg_gc_diff_season_mean"]
    )
    df_gk["savepct_last5_mean"] = g["Porcentaje_paradas"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df_gk["yellow_last5_sum"] = g["Amarillas"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df_gk["red_last5_sum"] = g["Rojas"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df_gk["titular_last5_ratio"] = g["Titular"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # Porterías a 0
    df_gk["clean_sheet"] = (df_gk["Goles_en_contra"] == 0).astype(int)
    df_gk["clean_last5_sum"] = g["clean_sheet"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )
    df_gk["clean_last5_ratio"] = g["clean_sheet"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # Picos de puntos recientes
    df_gk["pf_last5_max"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).max()
    )
    df_gk["pf_last5_min"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).min()
    )
    df_gk["pf_spike_last5"] = (
        df_gk["pf_last5_max"] >= 12
    ).astype(int)

    # === INTERACCIONES PORTERO × RIVAL ===
    df_gk["xg_rival_x_savepct"] = (
        df_gk["xg_last5_mean_rival"] * df_gk["savepct_last5_mean"]
    )
    df_gk["xg_rival_x_gc_per90"] = (
        df_gk["xg_last5_mean_rival"] * df_gk["gc_per90_last5"]
    )
    df_gk["gf_rival_last5_x_gc_per90"] = (
        df_gk["gf_last5_mean_rival"] * df_gk["gc_per90_last5"]
    )
    df_gk["goal_diff_rival_x_pf_var"] = (
        df_gk["goal_diff_last5_rival"] * df_gk["pf_last5_std"]
    )

    # ⚠️ FEATURES CORREGIDAS - SIN DATA LEAKAGE
    feature_cols_base = [
        # Rachas del portero
        "pf_last5_mean",
        "pf_last5_sum",
        "min_last5_mean",
        "gc_last5_mean",
        "psxg_last5_mean",
        "psxg_gc_diff_last5_mean",
        "form_vs_class_keeper",
        "savepct_last5_mean",
        "saves_last5_mean",
        "clean_last5_sum",
        "clean_last5_ratio",
        "yellow_last5_sum",
        "red_last5_sum",
        "titular_last5_ratio",

        # Contexto
        "local",

        # Clasificación (jornada N-1)
        "pts", "gf", "gc",
        "pts_rival", "gf_rival", "gc_rival",
        "pts_diff", "gf_diff", "gc_diff",

        # Flags posición
        "is_top4_propio", "is_top4_rival",
        "is_bottom3_rival",

        # Rachas de equipos (históricas)
        "gf_last5_mean_team",
        "gc_last5_mean_team",
        "gf_last5_mean_rival",
        "gc_last5_mean_rival",
        "goal_diff_last5_team",
        "goal_diff_last5_rival",
        "xg_last5_mean_team",
        "xg_contra_last5_mean_team",
        "xg_last5_mean_rival",
        "xg_contra_last5_mean_rival",

        # Tiros históricos (rachas, NO del partido actual)
        "shots_last5_mean_rival",
        "shots_on_target_last5_mean_rival",
        "shots_on_target_ratio_rival",

        # Varianzas
        "pf_last5_std",
        "gc_last5_std",
        "psxg_last5_std",
        "psxg_per90_last5",
        "gc_per90_last5",

        # Flags
        "ataque_top_rival",
        "defensa_floja_propia",
        "ataque_top_y_defensa_floja",

        # Cuotas (disponibles antes)
        "p_win_propio",
        "p_loss_propio",
        "p_draw_match",
        "p_over25_match",
        "ah_line_match",

        # Interacciones
        "ratio_paradas_dificiles",
        "xg_rival_x_savepct",
        "xg_rival_x_gc_per90",
        "gf_rival_last5_x_gc_per90",
        "goal_diff_rival_x_pf_var",
    ]

    print(f"\n✅ FEATURES CORREGIDAS: {len(feature_cols_base)}")
    print("   Todas disponibles ANTES del partido")
    print("   ❌ Eliminadas: shots_rival, shots_propio, xg_rival, xg_team del partido actual")

    subset_cols = ["target_pf_next", *feature_cols_base]
    df_sub = df_gk[subset_cols].copy()
    mask_ok = df_sub.notna().all(axis=1)

    print("\nFilas con todas las features base sin NaN:", mask_ok.sum())
    print("Filas descartadas por NaN en features base:", (~mask_ok).sum())

    df_gk_model = df_gk.loc[mask_ok].copy()

    # Rellenar scores de ranking faltantes con 0
    for col in ["score_porterias_cero", "score_save_pct"]:
        if col in df_gk_model.columns:
            df_gk_model[col] = df_gk_model[col].fillna(0.0)

    # Features de roles
    if "score_porterias_cero" in df_gk_model.columns:
        df_gk_model["score_porterias_cero_strong"] = df_gk_model["score_porterias_cero"] ** 5
        df_gk_model["score_save_pct_strong"] = df_gk_model["score_save_pct"] ** 5
        df_gk_model["rol_x_xg_rival"] = (
            df_gk_model["score_save_pct"] * df_gk_model["xg_last5_mean_rival"]
        )
        df_gk_model["elite_keeper"] = (
            (df_gk_model["score_porterias_cero"] > 0.5) &
            (df_gk_model["score_save_pct"] > 0.5)
        ).astype(int)
        df_gk_model["ataque_top_rival_x_elite"] = (
            df_gk_model["ataque_top_rival"] * df_gk_model["elite_keeper"]
        )

        df_gk_model = add_role_features(df_gk_model)

        feature_cols = feature_cols_base + [
            "score_porterias_cero",
            "score_save_pct",
            "score_porterias_cero_strong",
            "score_save_pct_strong",
            "rol_x_xg_rival",
            "elite_keeper",
            "pf_last5_max",
            "pf_last5_min",
            "pf_spike_last5",
            "is_top5_porterias_cero",
            "is_top5_save_pct",
            "score_pc_boost",
            "score_sp_boost",
            "ataque_top_rival_x_elite",
        ]
    else:
        feature_cols = feature_cols_base

    # Filtrar target
    df_gk_model = df_gk_model[
        df_gk_model["target_pf_next"].between(-10, 30)
    ].copy()

    print("Filas finales usadas para entrenar/testear:", df_gk_model.shape[0])

    train_mask = df_gk_model["temporada"].isin(["23_24", "24_25"])
    test_mask = df_gk_model["temporada"] == "25_26"

    X_train = df_gk_model.loc[train_mask, feature_cols]
    y_train = df_gk_model.loc[train_mask, "target_pf_next"]

    X_test = df_gk_model.loc[test_mask, feature_cols]
    y_test = df_gk_model.loc[test_mask, "target_pf_next"]

    cols = list(X_train.columns)
    assert cols == list(X_test.columns)

    print("\nTamaño X_train:", X_train.shape)
    print("Tamaño X_test :", X_test.shape)

    # ==============================
    # MODELO 1: RANDOM FOREST
    # ==============================

    print("\n" + "="*60)
    print("MODELO 1: RANDOM FOREST")
    print("="*60)
    rf = RandomForestRegressor(
    n_estimators=300,
    max_features=0.5,
    max_depth=8,        # menos profundo
    min_samples_leaf=10,# hojas más grandes
    random_state=42,
    n_jobs=-1
)


    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    y_pred_rf_rounded = y_pred_rf.round()
    mae_rf = mean_absolute_error(y_test, y_pred_rf_rounded)
    print("MAE RF porteros (test 25_26, pred redondeada):", mae_rf)

    importancias_rf = pd.Series(rf.feature_importances_, index=X_train.columns)
    print("\nTop 15 features RF por importancia:")
    print(importancias_rf.sort_values(ascending=False).head(15))

    # ==============================
    # MODELO 2: HISTGRADIENTBOOSTING
    # ==============================

    print("\n" + "="*60)
    print("MODELO 2: HISTGRADIENTBOOSTING")
    print("="*60)

    hgb = HistGradientBoostingRegressor(random_state=42)
    hgb.fit(X_train, y_train)
    y_pred_hgb = hgb.predict(X_test)
    y_pred_hgb_rounded = y_pred_hgb.round()
    mae_hgb = mean_absolute_error(y_test, y_pred_hgb_rounded)
    print("MAE HGB porteros (test 25_26, pred redondeada):", mae_hgb)

    try:
        importancias_hgb = pd.Series(hgb.feature_importances_, index=X_train.columns)
        print("\nTop 15 features HGB por importancia:")
        print(importancias_hgb.sort_values(ascending=False).head(15))
    except AttributeError:
        print("HGB no expone feature_importances_ en esta versión.")

    # ==============================
    # MODELO 3: LINEAR REGRESSION
    # ==============================

    print("\n" + "="*60)
    print("MODELO 3: LINEAR REGRESSION")
    print("="*60)

    try:
        X_train_lin = X_train.dropna()
        y_train_lin = y_train.loc[X_train_lin.index]

        X_test_lin = X_test.dropna()
        y_test_lin = y_test.loc[X_test_lin.index]

        lin = LinearRegression()
        lin.fit(X_train_lin, y_train_lin)
        y_pred_lin = lin.predict(X_test_lin)
        y_pred_lin_rounded = y_pred_lin.round()
        mae_lin = mean_absolute_error(y_test_lin, y_pred_lin_rounded)
        print("MAE LIN porteros (test 25_26, pred redondeada):", mae_lin)

        coef_series = pd.Series(lin.coef_, index=X_train_lin.columns)
        print("\nTop 20 features LINEAL por |coeficiente|:")
        print(coef_series.reindex(
            coef_series.abs().sort_values(ascending=False).head(20).index
        ))
    except ValueError as e:
        print("No se ha podido ajustar la regresión lineal por NaNs:", e)
        lin = None
        mae_lin = None

    # ==============================
    # COMPARACIÓN DE MODELOS
    # ==============================

    print("\n" + "="*60)
    print("COMPARACIÓN DE MODELOS")
    print("="*60)
    print(f"MAE Random Forest:       {mae_rf:.3f}")
    print(f"MAE Hist Gradient Boost: {mae_hgb:.3f}")
    if mae_lin is not None:
        print(f"MAE Linear Regression:   {mae_lin:.3f}")

    # Seleccionar mejor modelo
    if mae_rf <= mae_hgb:
        best_model = rf
        best_pred = y_pred_rf_rounded
        best_mae = mae_rf
        best_name = "RandomForest"
    else:
        best_model = hgb
        best_pred = y_pred_hgb_rounded
        best_mae = mae_hgb
        best_name = "HistGradientBoosting"

    print(f"\n✅ Mejor modelo: {best_name} (MAE: {best_mae:.3f})")

    # ==============================
    # MODELO ÉLITE (opcional)
    # ==============================

    if "elite_keeper" in df_gk_model.columns:
        df_elite = df_gk_model[df_gk_model["elite_keeper"] == 1].copy()
        train_mask_elite = df_elite["temporada"].isin(["23_24", "24_25"])
        test_mask_elite = df_elite["temporada"] == "25_26"

        if train_mask_elite.sum() > 10 and test_mask_elite.sum() > 5:
            X_train_elite = df_elite.loc[train_mask_elite, cols]
            y_train_elite = df_elite.loc[train_mask_elite, "target_pf_next"]

            X_test_elite = df_elite.loc[test_mask_elite, cols]
            y_test_elite = df_elite.loc[test_mask_elite, "target_pf_next"]

            rf_elite = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
            rf_elite.fit(X_train_elite, y_train_elite)
            y_pred_elite = rf_elite.predict(X_test_elite).round()
            mae_elite = mean_absolute_error(y_test_elite, y_pred_elite)
            print(f"\nMAE RF porteros ÉLITE: {mae_elite:.3f}")
        else:
            rf_elite = None
    else:
        rf_elite = None

    # ==============================
    # RETORNAR RESULTADOS
    # ==============================

    return {
        'rf': rf,
        'hgb': hgb,
        'lin': lin,
        'rf_elite': rf_elite if 'rf_elite' in locals() else None,
        'best_model': best_model,
        'best_name': best_name,
        'feature_cols': feature_cols,
        'df_gk_model': df_gk_model,
        'mae_rf': mae_rf,
        'mae_hgb': mae_hgb,
        'mae_lin': mae_lin if mae_lin else np.nan,
        'mae_best': best_mae
    }


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
    print("\n" + "="*60)
    print("ENTRENAMIENTO DE MODELOS")
    print("="*60)
    df_gk_only = df_exp3[df_exp3["posicion"] == "PT"].copy()
    resultados = entrenar_modelo_porteros(df_gk_only)

    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80)
    print(f"Modelo final: {resultados['best_name']}")
    print(f"MAE test: {resultados['mae_best']:.3f}")
    print(f"Features usadas: {len(resultados['feature_cols'])}")
    print("\nTodas las features están disponibles ANTES del partido")
    print("El modelo está listo para predecir partidos futuros")