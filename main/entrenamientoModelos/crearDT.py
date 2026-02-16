import pandas as pd
import ast
from pathlib import Path
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


def cargar_jugadores_temporada(base_folder: str, temporada_tag: str) -> pd.DataFrame:
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
    full = pd.concat(frames, ignore_index=True)
    return full.sort_values(["player", "temporada", "jornada", "fecha_partido"]).reset_index(drop=True)


def enriquecer_roles(df):
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


def cargar_clasificacion(path: str, temporada_tag: str) -> pd.DataFrame:
    standings = pd.read_csv(path)
    standings["temporada"] = temporada_tag
    standings["jornada"] = standings["jornada"].astype(int)
    if "equipo" in standings.columns:
        standings["equipo"] = normalizar_equipo_series(standings["equipo"])
    return standings


def construir_dataset_completo():
    df_players_23_24 = cargar_jugadores_temporada("data/temporada_23_24", "23_24")
    standings_23_24 = cargar_clasificacion("data/temporada_23_24/clasificacion_temporada.csv", "23_24")

    df_players_24_25 = cargar_jugadores_temporada("data/temporada_24_25", "24_25")
    standings_24_25 = cargar_clasificacion("data/temporada_24_25/clasificacion_temporada.csv", "24_25")

    df_players_25_26 = cargar_jugadores_temporada("data/temporada_25_26", "25_26")
    standings_25_26 = cargar_clasificacion("data/temporada_25_26/clasificacion_temporada.csv", "25_26")

    df_players = pd.concat([df_players_23_24, df_players_24_25, df_players_25_26], ignore_index=True)
    
    # Normalizar nombres de columnas de equipo (caso-insensitivo)
    equipo_cols = [col for col in df_players.columns if 'equipo' in col.lower()]
    for col in equipo_cols:
        if df_players[col].dtype == 'object':  # Solo si es string
            df_players[col] = normalizar_equipo_series(df_players[col])
    
    df_players = enriquecer_roles(df_players)
    
    # Limpiar outliers de puntos > 30 (reemplazar por mediana)
    # Detectar columna de puntos (case-insensitive)
    puntos_col = next((col for col in df_players.columns if 'puntos' in col.lower()), None)
    if puntos_col:
        mediana_puntos = df_players[df_players[puntos_col] <= 30][puntos_col].median()
        df_players.loc[df_players[puntos_col] > 30, puntos_col] = mediana_puntos
        print(f"✅ Outliers en {puntos_col} limpiados (mediana: {mediana_puntos:.2f})")
    else:
        print("⚠️ No se encontró columna de puntos")

    standings = pd.concat([standings_23_24, standings_24_25, standings_25_26], ignore_index=True)

    df_players.to_csv("csv/csvGenerados/players_matches_all_seasons.csv", index=False)
    standings.to_csv("csv/csvGenerados/standings_all_seasons.csv", index=False)
    
    print(f"📊 Columnas en df_players: {df_players.columns.tolist()[:10]}...")

    return df_players, standings


def agregar_standings_lagged_y_crear_target(df_players: pd.DataFrame, standings: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece datos de jugadores con standings de la jornada anterior (lagged)
    y crea el target (puntos fantasy de la próxima jornada).
    
    Usado para TRAINING: proporciona features + targets históricos.
    
    Args:
        df_players: DataFrame con datos de jugadores (todas las jornadas)
        standings: DataFrame con clasificación por jornada
    
    Returns:
        DataFrame enriquecido con:
        - jornada_anterior: referencia a jornada previa
        - Columnas standings del equipo propio (jornada anterior) con sufijo "_equipo"
        - Columnas standings del rival (jornada anterior) con sufijo "_rival"
        - target_pf_next: puntos fantasy que sacará en la próxima jornada (LABEL para ML)
    """
    df = df_players.copy()
    df["jornada_anterior"] = df["jornada"] - 1

    # Detectar nombres de columnas de equipo (case-insensitive)
    equipo_propio_col = next((col for col in df.columns if 'equipo' in col.lower() and 'propio' in col.lower()), None)
    equipo_rival_col = next((col for col in df.columns if 'equipo' in col.lower() and 'rival' in col.lower()), None)
    
    # Si no encuentra, usar nombres estándar
    if not equipo_propio_col:
        equipo_propio_col = "equipo_propio"
    if not equipo_rival_col:
        equipo_rival_col = "equipo_rival"

    equipo_col_standings = next((col for col in standings.columns if col.lower() == 'equipo'), 'equipo')
    
    # Detectar columna de puntos
    puntos_col = next((col for col in df.columns if 'puntos' in col.lower()), 'puntos')
    
    print(f"\n📋 Detectadas columnas:")
    print(f"   - Equipo propio: {equipo_propio_col}")
    print(f"   - Equipo rival: {equipo_rival_col}")
    print(f"   - Puntos: {puntos_col}")
    print(f"   - Equipo en standings: {equipo_col_standings}")
    
    try:
        st_own = standings.rename(columns={equipo_col_standings: equipo_propio_col, "jornada": "jornada_anterior"})
        df = df.merge(st_own, on=["temporada", "jornada_anterior", equipo_propio_col], how="left", suffixes=("", "_equipo"))

        st_rival = standings.rename(columns={equipo_col_standings: equipo_rival_col, "jornada": "jornada_anterior"})
        df = df.merge(st_rival, on=["temporada", "jornada_anterior", equipo_rival_col], how="left", suffixes=("", "_rival"))
        print(f"✅ Merge con standings completado")
    except Exception as e:
        print(f"⚠️ Warning en merge de clasificación: {e}")
        print(f"   Columnas en df: {df.columns.tolist()[:15]}")

    df = df.sort_values(["player", "temporada", "jornada", "fecha_partido"])
    
    # Crear target usando la columna detectada
    if puntos_col in df.columns:
        df["target_pf_next"] = df.groupby(["player", "temporada"])[puntos_col].shift(-1)
        print(f"✅ Target creado desde columna '{puntos_col}'")
    else:
        print(f"⚠️ Columna '{puntos_col}' no encontrada")

    return df


if __name__ == "__main__":
    print("="*80)
    print("GENERADOR DE FEATURES - MODELO PORTEROS")
    print("="*80)

    try:
        df_players = pd.read_csv("csv/csvGenerados/players_matches_all_seasons.csv")
        standings = pd.read_csv("csv/csvGenerados/standings_all_seasons.csv")
        print("\n✅ Datos cargados desde CSV")
    except FileNotFoundError:
        print("\n⚠️ CSV no encontrados, construyendo desde carpetas...")
        df_players, standings = construir_dataset_completo()

    print("\n" + "="*60)
    print("Preparando datos con clasificación lagged y target")
    print("="*60)
    df = agregar_standings_lagged_y_crear_target(df_players, standings)
    print(f"✅ Shape: {df.shape}")

    df.to_csv("csv/csvGenerados/players_with_features.csv", index=False)
    print(f"\n✅ Dataset guardado: csv/csvGenerados/players_with_features.csv")
    print("\n✅ PROCESO COMPLETADO")
