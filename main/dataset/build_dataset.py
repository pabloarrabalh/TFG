import pandas as pd
import ast
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
import matplotlib.pyplot as plt

EQUIV_EQUIPOS = {
    # Las Palmas
    "las palmas": "las palmas",
    "ud las palmas": "las palmas",

    # Athletic
    "athletic": "athletic",
    "ath bilbao": "athletic",
    "athletic club": "athletic",

    # Atlético de Madrid
    "atletico madrid": "atletico madrid",
    "ath madrid": "atletico madrid",
    "atl madrid": "atletico madrid",

    # Barcelona
    "barcelona": "barcelona",
    "fc barcelona": "barcelona",

    # Real Madrid
    "real madrid": "real madrid",
    "rm": "real madrid",

    # Real Sociedad
    "real sociedad": "real sociedad",
    "sociedad": "real sociedad",
    "real sociedad de futbol": "real sociedad",

    # Rayo Vallecano
    "rayo vallecano": "rayo vallecano",
    "rayo": "rayo vallecano",
    "vallecano": "rayo vallecano",

    # Valencia
    "valencia": "valencia",
    "valencia cf": "valencia",

    # Mallorca
    "mallorca": "mallorca",
    "rcd mallorca": "mallorca",

    # Celta
    "celta": "celta",
    "rc celta": "celta",
    "rc celta de vigo": "celta",

    # Cádiz
    "cadiz": "cadiz",
    "cadiz cf": "cadiz",

    # Girona
    "girona": "girona",
    "girona fc": "girona",

    # Granada
    "granada": "granada",
    "granada cf": "granada",

    # Osasuna
    "osasuna": "osasuna",
    "ca osasuna": "osasuna",

    # Almería
    "almeria": "almeria",
    "ud almeria": "almeria",

    # Villarreal
    "villarreal": "villarreal",
    "villarreal cf": "villarreal",

    # Getafe
    "getafe": "getafe",
    "getafe cf": "getafe",

    # Betis
    "betis": "betis",
    "real betis": "betis",
    "real betis balompie": "betis",

    # Espanyol (SP1 usa 'espanol')
    "espanyol": "espanyol",
    "rcd espanyol": "espanyol",
    "espanol": "espanyol",

    # Leganés
    "leganes": "leganes",
    "cd leganes": "leganes",

    # Valladolid
    "valladolid": "valladolid",
    "real valladolid": "valladolid",
    "real valladolid cf": "valladolid",
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

def add_role_ranks(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def get_rank(lst, key):
        for d in lst:
            if key in d:
                return d[key][0]   # posición en ranking
        return None

    # rankings brutos
    df["rank_porterias_cero"] = df["roles"].apply(
        lambda lst: get_rank(lst, "porterias_cero")
    )
    df["rank_save_pct"] = df["roles"].apply(
        lambda lst: get_rank(lst, "save_pct")
    )

    # scores en [0,1] solo donde haya ranking; el resto quedará NaN
    max_rank_pc = df["rank_porterias_cero"].max()
    max_rank_sp = df["rank_save_pct"].max()

    df["score_porterias_cero"] = 1 - (df["rank_porterias_cero"] - 1) / (max_rank_pc - 1)
    df["score_save_pct"] = 1 - (df["rank_save_pct"] - 1) / (max_rank_sp - 1)

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
    #print("Nombres en SP1:", sorted(set(odds["HomeTeam"]) | set(odds["AwayTeam"])))
    return odds

def build_all_data():
    df_players_23_24 = load_player_matches_temporada(
        "data/temporada_23_24", "23_24"
    )
    standings_23_24 = load_standings(
        "data/temporada_23_24/clasificacion_temporada.csv", "23_24"
    )
    odds_23_24 = load_odds_temporada(
        "data/temporada_23_24/SP1.csv", "23_24"
    )

    df_players_24_25 = load_player_matches_temporada(
        "data/temporada_24_25", "24_25"
    )
    standings_24_25 = load_standings(
        "data/temporada_24_25/clasificacion_temporada.csv", "24_25"
    )
    odds_24_25 = load_odds_temporada(
        "data/temporada_24_25/SP1.csv", "24_25"
    )

    df_players_25_26 = load_player_matches_temporada(
        "data/temporada_25_26", "25_26"
    )
    standings_25_26 = load_standings(
        "data/temporada_25_26/clasificacion_temporada.csv", "25_26"
    )
    odds_25_26 = load_odds_temporada(
        "data/temporada_25_26/SP1.csv", "25_26"
    )

    df_players = pd.concat(
        [df_players_23_24, df_players_24_25, df_players_25_26],
        ignore_index=True
    )

    for col in ["Equipo_propio", "Equipo_rival"]:
        df_players[col] = normalizar_equipo_series(df_players[col])

    # NUEVO: añadir scores de roles (rankings)
    df_players = add_role_ranks(df_players)

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
# FEATURES A NIVEL JUGADOR
# ==============================
def experimento_1(
    df_players: pd.DataFrame,
    standings: pd.DataFrame,
    odds: pd.DataFrame
) -> pd.DataFrame:
    # ==========================
    # MERGE CON CLASIFICACIÓN
    # ==========================
    st_own = standings.rename(columns={"equipo": "Equipo_propio"})
    df = df_players.merge(
        st_own,
        on=["temporada", "jornada", "Equipo_propio"],
        how="left",
        suffixes=("", "_equipo"),
    )

    st_rival = standings.rename(columns={"equipo": "Equipo_rival"})
    df = df.merge(
        st_rival,
        on=["temporada", "jornada", "Equipo_rival"],
        how="left",
        suffixes=("", "_rival"),
    )

    # ==========================
    # PREPARAR ODDS
    # ==========================
    o = odds.copy()
    o = o.rename(columns={"HomeTeam": "home", "AwayTeam": "away"})

    # Cuotas medias 1X2 -> probabilidades implícitas
    for c in ["AvgH", "AvgD", "AvgA"]:
        o[c] = pd.to_numeric(o[c], errors="coerce")

    o["inv_H"] = 1 / o["AvgH"]
    o["inv_D"] = 1 / o["AvgD"]
    o["inv_A"] = 1 / o["AvgA"]
    o["sum_inv"] = o[["inv_H", "inv_D", "inv_A"]].sum(axis=1)

    o["p_home"] = o["inv_H"] / o["sum_inv"]
    o["p_draw"] = o["inv_D"] / o["sum_inv"]
    o["p_away"] = o["inv_A"] / o["sum_inv"]

    # Over/Under 2.5
    o["Avg>2.5"] = pd.to_numeric(o["Avg>2.5"], errors="coerce")
    o["Avg<2.5"] = pd.to_numeric(o["Avg<2.5"], errors="coerce")

    o["inv_over"] = 1 / o["Avg>2.5"]
    o["inv_under"] = 1 / o["Avg<2.5"]
    o["sum_ou"] = o["inv_over"] + o["inv_under"]

    o["p_over25"] = o["inv_over"] / o["sum_ou"]

    # Hándicap asiático
    o["ah_line"] = pd.to_numeric(o["AHh"], errors="coerce")

    # Nos quedamos con lo necesario
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

    # ==========================
    # DOBLE MERGE JUGADORES + ODDS
    # ==========================
    # 1) Equipo_propio como local
    merge_home = df.merge(
        o_small,
        left_on=["temporada", "Equipo_propio", "Equipo_rival"],
        right_on=["temporada", "home", "away"],
        how="left",
    )

    # 2) Equipo_propio como visitante (invertimos home/away)
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

    # DEBUG: ver que el partido Oviedo–RM tiene bien las odds/tiros
    '''mask_debug = (
        (df["temporada"] == "25_26")
        & (df["Equipo_propio"] == "oviedo")
        & (df["Equipo_rival"] == "real madrid")
    )
    print("DEBUG experimento_1 - filas ejemplo tras merge odds:")
    print(
        df.loc[mask_debug, [
            "player", "posicion", "temporada", "jornada",
            "Equipo_propio", "Equipo_rival",
            "home", "away",
            "p_home", "p_away", "p_draw",
            "HS", "AS", "HST", "AST"
        ]].head(10)
    )'''

    # ==========================
    # FEATURES DE APUESTAS
    # ==========================
    df["p_win_propio"] = df["p_home"] * df["local"] + df["p_away"] * (1 - df["local"])
    df["p_loss_propio"] = df["p_away"] * df["local"] + df["p_home"] * (1 - df["local"])
    df["p_draw_match"] = df["p_draw"]
    df["p_over25_match"] = df["p_over25"]
    df["ah_line_match"] = df["ah_line"]

    df["shots_propio"] = df["HS"] * df["local"] + df["AS"] * (1 - df["local"])
    df["shots_rival"] = df["AS"] * df["local"] + df["HS"] * (1 - df["local"])
    df["shots_on_target_propio"] = df["HST"] * df["local"] + df["AST"] * (1 - df["local"])
    df["shots_on_target_rival"] = df["AST"] * df["local"] + df["HST"] * (1 - df["local"])

    # ==========================
    # TARGET: PF SIGUIENTE PARTIDO
    # ==========================
    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    df["target_pf_next"] = (
        df.groupby(["player", "temporada"])["puntosFantasy"].shift(-1)
    )

    return df


def experimento_2(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    group = df.groupby(["player", "temporada"])

    df["pf_last3_mean"] = group["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    df["min_last3_mean"] = group["Min_partido"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    df["goles_last3_sum"] = group["Gol_partido"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).sum()
    )
    return df


def experimento_3(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade features de:
    - xG equipo/rival por partido y racha (ventana 5)
    - racha ofensiva/defensiva de equipos (goles, propio y rival, ventana 5)
    - fuerza relativa en tabla
    - flags de posición en la tabla
    - varianza y ratios por 90 del portero (ventana 5)
    - flags ataque top / defensa floja
    """
    # Orden básico
    df = df.sort_values(["temporada", "jornada", "fecha_partido"])

    # ==========================
    # xG EQUIPO Y RIVAL POR PARTIDO
    # ==========================
    xg_team = (
        df.groupby(["temporada", "jornada", "Equipo_propio"])["xG_partido"]
        .sum()
        .reset_index()
        .rename(columns={"xG_partido": "xg_team"})
    )
    df = df.merge(
        xg_team,
        on=["temporada", "jornada", "Equipo_propio"],
        how="left"
    )

    xg_rival = (
        df.groupby(["temporada", "jornada", "Equipo_rival"])["xG_partido"]
        .sum()
        .reset_index()
        .rename(columns={"xG_partido": "xg_rival"})
    )
    df = df.merge(
        xg_rival,
        on=["temporada", "jornada", "Equipo_rival"],
        how="left"
    )

    # ==========================
    # RACHA EQUIPO PROPIO (GOLES + xG)
    # ==========================
    g_team = df.groupby(["Equipo_propio", "temporada"])

    df["gf_last5_mean_team"] = g_team["gf"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["gc_last5_mean_team"] = g_team["gc"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["goal_diff_last5_team"] = (
        df["gf_last5_mean_team"] - df["gc_last5_mean_team"]
    )

    df["xg_last5_mean_team"] = g_team["xg_team"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["xg_contra_last5_mean_team"] = g_team["xg_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # ==========================
    # RACHA EQUIPO RIVAL (GOLES + xG)
    # ==========================
    g_rival = df.groupby(["Equipo_rival", "temporada"])

    df["gf_last5_mean_rival"] = g_rival["gf_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["gc_last5_mean_rival"] = g_rival["gc_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["goal_diff_last5_rival"] = (
        df["gf_last5_mean_rival"] - df["gc_last5_mean_rival"]
    )

    # cuidado: xg_team/xg_rival vistos desde el rival
    df["xg_last5_mean_rival"] = g_rival["xg_team"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df["xg_contra_last5_mean_rival"] = g_rival["xg_rival"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # ==========================
    # FUERZA RELATIVA TABLA
    # ==========================
    df["pts_diff"] = df["pts"] - df["pts_rival"]
    df["gf_diff"] = df["gf"] - df["gf_rival"]
    df["gc_diff"] = df["gc"] - df["gc_rival"]

    # ==========================
    # FLAGS POSICIÓN EN TABLA
    # ==========================
    df["is_top4_propio"] = (df["posicion_equipo"] <= 4).astype(int)
    df["is_top4_rival"] = (df["posicion_rival"] <= 4).astype(int)
    df["is_bottom3_propio"] = (df["posicion_equipo"] >= 18).astype(int)
    df["is_bottom3_rival"] = (df["posicion_rival"] >= 18).astype(int)

    # ==========================
    # VARIANZA + RATIOS 90 DEL PORTERO
    # ==========================
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

    # ==========================
    # FLAGS ATAQUE TOP / DEFENSA FLOJA
    # ==========================
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
# MODELO PORTEROS VENTANA 5
# ==============================
def entrenar_modelo_porteros(df: pd.DataFrame):
    print("=== ENTRENAR MODELO PORTEROS ===")
    df_gk = df[df["posicion"] == "PT"].copy()
    print("Porteros totales (todas las filas):", len(df_gk))

    df_gk = df_gk[df_gk["puntosFantasy"].between(-10, 30)].copy()
    print("Porteros tras filtro PF [-10,30]:", len(df_gk))

    df_gk["psxg_gc_diff"] = df_gk["PSxG"] - df_gk["Goles_en_contra"]

    df_gk = df_gk.sort_values(
        ["player", "temporada", "jornada", "fecha_partido"]
    )
    g = df_gk.groupby(["player", "temporada"])

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

    df_gk["clean_sheet"] = (df_gk["Goles_en_contra"] == 0).astype(int)
    df_gk["clean_last5_sum"] = g["clean_sheet"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).sum()
    )

    # Picos de puntos recientes (NUEVO)
    df_gk["pf_last5_max"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).max()
    )
    df_gk["pf_last5_min"] = g["puntosFantasy"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).min()
    )
    df_gk["pf_spike_last5"] = (
        df_gk["pf_last5_max"] >= 12
    ).astype(int)

    feature_cols = [
        "pf_last5_mean",
        "pf_last5_sum",
        "min_last5_mean",
        "gc_last5_mean",
        "psxg_last5_mean",
        "psxg_gc_diff_last5_mean",
        "savepct_last5_mean",
        "clean_last5_sum",
        "yellow_last5_sum",
        "red_last5_sum",
        "titular_last5_ratio",
        "local",
        "pts", "gf", "gc",
        "pts_rival", "gf_rival", "gc_rival",
        "pts_diff", "gf_diff", "gc_diff",
        "is_top4_propio", "is_top4_rival",
        "is_bottom3_propio", "is_bottom3_rival",
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
        "pf_last5_std",
        "gc_last5_std",
        "psxg_last5_std",
        "psxg_per90_last5",
        "gc_per90_last5",
        "ataque_top_rival",
        "defensa_floja_propia",
        "ataque_top_y_defensa_floja",
        "p_win_propio",
        "p_loss_propio",
        "p_draw_match",
        "p_over25_match",
        "ah_line_match",
        "shots_propio",
        "shots_rival",
        "shots_on_target_propio",
        "shots_on_target_rival",
        "score_porterias_cero",
        "score_save_pct",
        "score_porterias_cero_strong",
        "score_save_pct_strong",
        "rol_x_xg_rival",
        "elite_keeper",
        "pf_last5_max",
        "pf_last5_min",
        "pf_spike_last5",
    ]

    feature_cols_base = [
        c for c in feature_cols
        if c not in [
            "score_porterias_cero", "score_save_pct",
            "score_porterias_cero_strong", "score_save_pct_strong",
            "rol_x_xg_rival", "elite_keeper",
            "pf_last5_max", "pf_last5_min", "pf_spike_last5",
        ]
    ]
    subset_cols = ["target_pf_next", *feature_cols_base]
    df_sub = df_gk[subset_cols].copy()
    mask_ok = df_sub.notna().all(axis=1)

    print("Filas con todas las features base sin NaN:", mask_ok.sum())
    print("Filas descartadas por NaN en features base:", (~mask_ok).sum())

    df_gk_model = df_gk.loc[mask_ok].copy()

    # Rellenar scores de ranking faltantes con 0 (valor neutro)
    for col in ["score_porterias_cero", "score_save_pct"]:
        if col in df_gk_model.columns:
            df_gk_model[col] = df_gk_model[col].fillna(0.0)

    # Features de roles potenciados e interacción
    df_gk_model["score_porterias_cero_strong"] = df_gk_model["score_porterias_cero"] ** 2
    df_gk_model["score_save_pct_strong"] = df_gk_model["score_save_pct"] ** 2
    df_gk_model["rol_x_xg_rival"] = (
        df_gk_model["score_save_pct"] * df_gk_model["xg_last5_mean_rival"]
    )
    df_gk_model["elite_keeper"] = (
        (df_gk_model["score_porterias_cero"] > 0.8) &
        (df_gk_model["score_save_pct"] > 0.8)
    ).astype(int)

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

    print("Tamaño X_train:", X_train.shape)
    print("Tamaño X_test :", X_test.shape)

    rf = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    mae_rf = mean_absolute_error(y_test, y_pred_rf)
    print("MAE RF porteros ventana5 (test 25_26):", mae_rf)

    importancias_rf = pd.Series(rf.feature_importances_, index=X_train.columns)
    print("\nTop 15 features RF por importancia:")
    print(importancias_rf.sort_values(ascending=False).head(15))

    hgb = HistGradientBoostingRegressor(random_state=42)
    hgb.fit(X_train, y_train)
    y_pred_hgb = hgb.predict(X_test)
    mae_hgb = mean_absolute_error(y_test, y_pred_hgb)
    print("MAE HGB porteros ventana5 (test 25_26):", mae_hgb)

    try:
        importancias_hgb = pd.Series(hgb.feature_importances_, index=X_train.columns)
        print("\nTop 15 features HGB por importancia:")
        print(importancias_hgb.sort_values(ascending=False).head(15))
    except AttributeError:
        print("HGB no expone feature_importances_ en esta versión.")

    lin = LinearRegression()
    lin.fit(X_train, y_train)
    y_pred_lin = lin.predict(X_test)
    mae_lin = mean_absolute_error(y_test, y_pred_lin)
    print("MAE LIN porteros ventana5 (test 25_26):", mae_lin)

    coef_series = pd.Series(lin.coef_, index=X_train.columns)
    print("\nTop 20 features LINEAL por |coeficiente|:")
    print(coef_series.reindex(
        coef_series.abs().sort_values(ascending=False).head(20).index
    ))

    model = rf
    y_pred = y_pred_rf
    mae = mae_rf

    df_test = df_gk_model.loc[test_mask].copy()
    df_test = df_test.assign(pred_pf_next=y_pred)
    df_test = df_test.sort_values(["player", "jornada"])

    print("\n=== FIN ENTRENAR MODELO PORTEROS ===")
    return model, df_gk_model, df_test, mae

if __name__ == "__main__":
    # 1) Leer datasets base desde CSV ya existentes
    df_players = pd.read_csv("players_matches_all_seasons.csv")
    standings = pd.read_csv("standings_all_seasons.csv")
    odds = pd.read_csv("odds_all_seasons.csv")

    # 2) Experimento 1: standings + cuotas
    df = experimento_1(df_players, standings, odds)

    # FILTRAR SOLO PORTEROS YA AQUÍ
    df = df[df["posicion"] == "PT"].copy()

    # 3) Experimento 2
    df_exp2 = experimento_2(df)

    # 4) Experimento 3
    df_exp3 = experimento_3(df_exp2)

    # ============ INFO SHAPES ============
    print("Shape exp1:", df.shape)
    print("Shape exp2:", df_exp2.shape)
    print("Shape exp3:", df_exp3.shape)

    # 5) Guardar dataset final
    df_exp3.to_csv("players_with_features_exp3.csv", index=False)

    # 6) Entrenar modelo porteros
    model_gk, df_gk_model, df_test_25_26, mae_gk = entrenar_modelo_porteros(df_exp3)

    # 7) Tabla de errores por partido en test
    cols = ["player", "Equipo_rival", "puntosFantasy", "pred_pf_next"]
    tabla_gk = df_test_25_26[cols].copy()
    tabla_gk["abs_error"] = (tabla_gk["pred_pf_next"] - tabla_gk["puntosFantasy"]).abs()
    tabla_gk = tabla_gk.sort_values("abs_error", ascending=False)
    print(tabla_gk.head(50))

    # 8) MAE por jugador, solo con porteros con ≥ 5 predicciones
    from sklearn.metrics import mean_absolute_error

    df_eval = df_test_25_26.copy()
    counts = df_eval["player"].value_counts()
    valid_players = counts[counts >= 5].index
    df_eval = df_eval[df_eval["player"].isin(valid_players)].copy()

    mae_por_jugador = (
        df_eval.groupby("player", group_keys=False)
               .apply(lambda g: mean_absolute_error(g["puntosFantasy"], g["pred_pf_next"]))
               .reset_index(name="mae")
               .sort_values("mae")
    )

    print(mae_por_jugador)

    # 9) Gráficas por portero (solo los con ≥ 5 partidos si quieres)
    import os
    output_dir = "graficas_porteros"
    os.makedirs(output_dir, exist_ok=True)

    for nombre in df_eval["player"].unique():
        df_gk_plot = df_eval[df_eval["player"] == nombre].copy()
        df_gk_plot = df_gk_plot.sort_values("jornada")

        x = df_gk_plot["jornada"]

        plt.figure(figsize=(8, 4))
        plt.scatter(x, df_gk_plot["pred_pf_next"], color="blue", marker="o", label="Predicho")
        plt.scatter(x, df_gk_plot["puntosFantasy"], color="red", marker="x", label="Real")

        for j, y in zip(x, df_gk_plot["pred_pf_next"]):
            plt.text(j + 0.05, y, f"{y:.1f}", color="blue", fontsize=7, va="bottom")
        for j, y in zip(x, df_gk_plot["puntosFantasy"]):
            plt.text(j - 0.05, y, f"{y:.1f}", color="red", fontsize=7, ha="right", va="top")

        plt.xticks(x, [f"J{int(j)}" for j in x])
        plt.xlabel(f"Jornadas de {nombre}")
        plt.ylabel("Puntos Fantasy")
        plt.title(f"{nombre}: predicho (azul) vs real (rojo)")
        plt.legend()
        plt.tight_layout()

        fname = f"{nombre.replace(' ', '_')}.png"
        plt.savefig(os.path.join(output_dir, fname))
        plt.close()
  # mejores
