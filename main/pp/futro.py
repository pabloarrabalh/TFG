# futro.py v3 - PREDICTOR DE PORTEROS CON CONTEXTO COMPLETO
# Recalcula rachas necesarias directamente sobre players_with_features_exp3_CORREGIDO.csv

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import unicodedata
import os,sys
# === UTILIDADES LOCALES DE TEXTO PARA FUTRO ===

ROOT = Path(__file__).resolve().parents[1]  
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scrapping.commons import normalizar_equipo

def buscar_csv_partido(temporada: str, jornada: int, idx_partido: int, local_html: str, visit_html: str) -> str:
    """
    Devuelve la ruta al CSV del partido, normalizando los nombres de equipo
    usando ALIAS_EQUIPOS (celta vigo -> celta, athletic club -> athletic, rayo vallecano -> rayo, etc.).
    """
    carpeta_csv = os.path.join("data", f"temporada_{temporada}", f"jornada_{jornada}")

    # Nombres tal como están en el CSV: ya usas normalizar_equipo en commons
    local_norm = normalizar_equipo(local_html)      # "celta vigo" -> "celta"; "athletic club" -> "athletic"
    visit_norm = normalizar_equipo(visit_html)      # "rayo vallecano" -> "rayo", etc.

    # Montar filename con los nombres normalizados
    filename = f"p{idx_partido}_{local_norm}-{visit_norm}.csv"
    ruta_csv = os.path.join(carpeta_csv, filename)

    if not os.path.exists(ruta_csv):
        raise FileNotFoundError(f"No se encuentra CSV de partido: {ruta_csv}")

    return ruta_csv


def _norm_text_futro(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("-", " ").replace(".", " ")
    return " ".join(s.split())


# Mapeo SOLO PORTEROS 25_26 (todo local a futro):


def aplicar_alias_portero_futro(nombre_portero: str, equipo_norm: str, temporada: str) -> str:
    """
    Convierte el nombre que viene de Fantasy (ej. 'Valles', 'Dmitrovic', 'Joan Garcia')
    al nombre largo que hay en el CSV (ej. 'Alvaro Valles', 'Marko Dmitrovic', 'Joan Garcia'),
    usando equipo_norm ya normalizado ('betis', 'espanyol', 'barcelona').
    Solo actúa en temporada 25_26.
    """
    if temporada != "25_26":
        return nombre_portero

    equipo_norm_n = _norm_text_futro(equipo_norm or "")
    nombre_norm = _norm_text_futro(nombre_portero or "")

    mapa_equipo = ALIAS_PORTEROS_25_26.get(equipo_norm_n, {})
    nombre_largo_norm = mapa_equipo.get(nombre_norm)

    if nombre_largo_norm:
        # capitalizar tipo "Alvaro Valles"
        partes = nombre_largo_norm.split()
        return " ".join(p.capitalize() for p in partes)

    return nombre_portero

ALIAS_PORTEROS_25_26 = {
    "betis": {
        "valles": "alvaro valles",
        "pau lópez": "pau lopez",
    },
    "espanyol": {
        "dmitrovic": "marko dmitrovic",
    },
    "barcelona": {
        "joan garcia": "joan garcia",
        "szczesny": "wojciech szczesny",
    },
    "villarreal": {
        "luiz junior": "luiz lucio reis junior",
    },
    "levante": {
        "cunat campos": "pablo cuñat",
        "cuñat campos": "pablo cuñat",
    },
    "mallorca": {
        # fantasy: "Bergstrom"  -> CSV: "Lucas Bergström"
        "bergstrom": "lucas bergstrom",
    },
}

def normalizar_nombre_portero(nombre_raw: str, equipo_norm: str, temporada: str) -> str:
    """
    Normaliza el nombre del portero a una forma sin tildes/minúsculas
    y aplica alias por equipo/temporada si existe.

    Ejemplos 25_26:
      'Valles'    + 'betis'    -> 'álvaro vallés'
      'Bergstrom' + 'mallorca' -> 'lucas bergström'
    """
    nombre_norm = _norm_text_futro(nombre_raw or "")
    equipo_norm_n = _norm_text_futro(equipo_norm or "")

    if temporada == "25_26":
        alias_equipo = ALIAS_PORTEROS_25_26.get(equipo_norm_n, {})
        # alias_equipo debe tener las claves ya normalizadas con _norm_text_futro
        return alias_equipo.get(nombre_norm, nombre_norm)

    return nombre_norm



CSV_NAME = "players_with_features_exp3_CORREGIDO.csv"
pd.set_option('future.no_silent_downcasting', True)

def cargar_datos_temporada(temporada: str = "25_26") -> pd.DataFrame:
    """
    Carga datos históricos de porteros y recalcula rachas necesarias
    sobre el CSV players_with_features_exp3_CORREGIDO.csv.
    """
    search_paths = [
        Path.cwd(),
        Path.cwd() / "main" / "pp",
        Path.cwd() / "data" / "temporada2526",
        Path.cwd().parent,
        Path.cwd().parent / "main" / "pp",
        Path.cwd().parent / "data" / "temporada2526",
    ]

    csv_path = None
    for p in search_paths:
        candidate = p / CSV_NAME
        if candidate.exists():
            csv_path = candidate
            break

    if csv_path is None:
        print(f"❌ Error: No se encontró {CSV_NAME}")
        return None

    df = pd.read_csv(csv_path)

    # Filtrar temporada
    if "temporada" in df.columns:
        df = df[df["temporada"] == temporada].copy()

    if df.empty:
        print(f"❌ Error: No hay datos para la temporada {temporada} en {CSV_NAME}")
        return None

    # Asegurar columnas básicas mínimas
    # Notas: tomamos nombres que sí existen en tu CSV actual según el listado.
    # - puntosFantasy, pts, pts_rival, pts_diff, posicion_equipo, posicion_rival
    # - racha5partidos, racha5partidos_rival
    # - xg_last5_mean_team, xg_last5_mean_rival
    # - xg_contra_last5_mean_team, xg_contra_last5_mean_rival
    # - shots_last5_mean_rival, shots_on_target_last5_mean_rival, shots_on_target_ratio_rival
    # - pf_last5_std (ya existe), psxg_last5_std, psxg_per90_last5, psxg_last5_sum

    # Recalcular rachas de portero si no existen
    # (necesitamos jornada para ordenar; si no está, asumimos que ya está ordenado)
    if "jornada" not in df.columns:
        # Si no tienes jornada en este CSV, simplemente ordena por Date
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.sort_values(["player", "Date"])
        else:
            df = df.sort_values(["player"])
    else:
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.sort_values(["player", "temporada", "jornada", "Date"])
        else:
            df = df.sort_values(["player", "temporada", "jornada"])

    gk_group = df.groupby(["player", "temporada"])

    # pf_last5_mean (promedio PF últimos 5, sin jornada actual)
    if "pf_last5_mean" not in df.columns and "puntosFantasy" in df.columns:
        df["pf_last5_mean"] = gk_group["puntosFantasy"].transform(
            lambda s: s.shift(1).rolling(5, min_periods=1).mean()
        )

    # gc_last5_mean / psxg_last5_mean etc. solo si existen columnas base
    if "Goles_en_contra" in df.columns:
        if "gc_last5_mean" not in df.columns:
            df["gc_last5_mean"] = gk_group["Goles_en_contra"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "gc_last5_sum" not in df.columns:
            df["gc_last5_sum"] = gk_group["Goles_en_contra"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).sum()
            )

    if "PSxG" in df.columns:
        if "psxg_last5_mean" not in df.columns:
            df["psxg_last5_mean"] = gk_group["PSxG"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "psxg_last5_sum" not in df.columns:
            df["psxg_last5_sum"] = gk_group["PSxG"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).sum()
            )

    # Clean sheets y rachas
    if "Goles_en_contra" in df.columns:
        if "clean_last5_sum" not in df.columns:
            df["clean_sheet"] = (df["Goles_en_contra"] == 0).astype(int)
            df["clean_last5_sum"] = gk_group["clean_sheet"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).sum()
            )
        if "clean_last5_ratio" not in df.columns:
            if "clean_sheet" not in df.columns:
                df["clean_sheet"] = (df["Goles_en_contra"] == 0).astype(int)
            df["clean_last5_ratio"] = gk_group["clean_sheet"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )

    # Tarjetas y titularidad si existen
    if "Amarillas" in df.columns:
        if "yellow_last5_sum" not in df.columns:
            df["yellow_last5_sum"] = gk_group["Amarillas"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).sum()
            )
    if "Rojas" in df.columns:
        if "red_last5_sum" not in df.columns:
            df["red_last5_sum"] = gk_group["Rojas"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).sum()
            )
    if "Titular" in df.columns:
        if "titular_last5_ratio" not in df.columns:
            df["titular_last5_ratio"] = gk_group["Titular"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )

    # Rachas de equipo (si tienes GF/GC y xG de equipos)
    # Ojo: en tu CSV final quizá no tienes gf/gc por equipo; estas partes solo se calculan si existen.
    if {"gf", "gc", "Equipo_propio"}.issubset(df.columns):
        df = df.sort_values(["temporada", "jornada", "Equipo_propio"])
        team_group = df.groupby(["Equipo_propio", "temporada"])
        if "gf_last5_mean_team" not in df.columns:
            df["gf_last5_mean_team"] = team_group["gf"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "gc_last5_mean_team" not in df.columns:
            df["gc_last5_mean_team"] = team_group["gc"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "goal_diff_last5_team" not in df.columns:
            df["goal_diff_last5_team"] = (
                df["gf_last5_mean_team"] - df["gc_last5_mean_team"]
            )

    if {"gf_rival", "gc_rival", "Equipo_rival"}.issubset(df.columns):
        df = df.sort_values(["temporada", "jornada", "Equipo_rival"])
        r_group = df.groupby(["Equipo_rival", "temporada"])
        if "gf_last5_mean_rival" not in df.columns:
            df["gf_last5_mean_rival"] = r_group["gf_rival"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "gc_last5_mean_rival" not in df.columns:
            df["gc_last5_mean_rival"] = r_group["gc_rival"].transform(
                lambda s: s.shift(1).rolling(5, min_periods=1).mean()
            )
        if "goal_diff_last5_rival" not in df.columns:
            df["goal_diff_last5_rival"] = (
                df["gf_last5_mean_rival"] - df["gc_last5_mean_rival"]
            )

    # Ya tienes en el CSV:
    # xg_last5_mean_team, xg_contra_last5_mean_team,
    # xg_last5_mean_rival, xg_contra_last5_mean_rival,
    # shots_last5_mean_rival, shots_on_target_last5_mean_rival, shots_on_target_ratio_rival,
    # pf_last5_std, psxg_last5_std, psxg_per90_last5, etc.
        # Asegurar columnas de roles que el modelo espera
    role_cols = [
        "rol_pos_porterias_cero",
        "rol_val_porterias_cero",
        "rol_pos_paradas",
        "rol_val_paradas",
        "rol_pos_save_pct",
        "rol_val_save_pct",
        "is_top5_en_algo",
    ]
    for col in role_cols:
        if col not in df.columns:
            df[col] = 0

    return df



def predecir_partido(
    partido: str,
    portero: str,
    modelo,
    feature_cols: list,
    jornada: int | None = None,
    verbose: bool = True,
):
    """
    Predice los puntos fantasy de un portero para un partido.
    Usa siempre la última fila disponible de ese portero en la temporada (jornada máxima).
    """
    temporada = "25_26"

    df = cargar_datos_temporada(temporada)
    if df is None or len(df) == 0:
        return {
            "error": f"No se encontraron datos históricos de la temporada {temporada}",
            "partido": partido,
            "portero": portero,
        }

    # ============================
    # 1) MATCH ESTRICTO EQUIPO+ALIAS
    # ============================
    row = None
    try:
        local_norm, visit_norm = partido.split("-")  # ej: "celta-betis"
        equipos_posibles = [local_norm, visit_norm]
    except ValueError:
        equipos_posibles = []

    if equipos_posibles:
        for equipo_norm in equipos_posibles:
            nombre_alias = aplicar_alias_portero_futro(portero, equipo_norm, temporada)
            nombre_busqueda_norm = _norm_text_futro(nombre_alias)

            mask_equipo = (
                (df["temporada"] == temporada)
                & (df["Equipo_propio"].str.lower() == equipo_norm)
                & (df["posicion"] == "PT")
            )

            mask = (
                (df["temporada"] == temporada)
                & (df["Equipo_propio"].str.lower() == equipo_norm)
                & (df["player"].apply(_norm_text_futro) == nombre_busqueda_norm)
                & (df["posicion"] == "PT")
            )

            if mask.sum() > 0:
                df_portero = df[mask].sort_values("jornada", ascending=False)
                row = df_portero.iloc[0]
                break

    # ============================
    # 2) FALLBACK: CONTAINS POR NOMBRE
    # ============================
    if row is None:
        porterolower = portero.lower().strip()

        mask = (
            df["player"].str.lower().str.contains(porterolower, na=False)
            & (df["posicion"] == "PT")
        )

        if mask.sum() == 0:
            return {
                "error": f"Portero '{portero}' no encontrado en la temporada {temporada}",
                "partido": partido,
                "portero": portero,
            }

        df_portero = df[mask].sort_values("jornada", ascending=False)
        row = df_portero.iloc[0]

    # ============================
    # 3) CONSTRUIR CONTEXTO (igual que tenías)
    # ============================
    info_portero = {
        "nombre": row["player"],
        "equipo": row["Equipo_propio"],
        "rival": row["Equipo_rival"],
        "es_local": bool(row.get("local", True)),
        "jornada_base": int(row.get("jornada", 0)),
        "jornada_predicha": int(jornada) if jornada is not None else None,
        "temporada": row.get("temporada"),
        "posicion": row.get("posicion"),
        "pf_last5_mean": float(row["pf_last5_mean"]) if "pf_last5_mean" in row and pd.notna(row["pf_last5_mean"]) else None,
        "gc_last5_mean": float(row["gc_last5_mean"]) if "gc_last5_mean" in row and pd.notna(row["gc_last5_mean"]) else None,
        "psxg_last5_mean": float(row["psxg_last5_mean"]) if "psxg_last5_mean" in row and pd.notna(row["psxg_last5_mean"]) else None,
        "clean_last5_sum": int(row["clean_last5_sum"]) if "clean_last5_sum" in row and pd.notna(row["clean_last5_sum"]) else None,
    }

    info_equipo_propio = {
        "nombre": row["Equipo_propio"],
        "posicion": int(row["posicion_equipo"]) if pd.notna(row.get("posicion_equipo")) else None,
        "puntos": int(row["pts"]) if pd.notna(row.get("pts")) else None,
        "racha5": row.get("racha5partidos"),
        "xg_last5_mean_team": row.get("xg_last5_mean_team"),
        "xg_contra_last5_mean_team": row.get("xg_contra_last5_mean_team"),
    }

    info_rival = {
        "nombre": row["Equipo_rival"],
        "posicion": int(row["posicion_rival"]) if pd.notna(row.get("posicion_rival")) else None,
        "puntos": int(row["pts_rival"]) if pd.notna(row.get("pts_rival")) else None,
        "racha5": row.get("racha5partidos_rival"),
        "xg_last5_mean_rival": row.get("xg_last5_mean_rival"),
        "xg_contra_last5_mean_rival": row.get("xg_contra_last5_mean_rival"),
        "shots_last5_mean_rival": row.get("shots_last5_mean_rival"),
        "shots_on_target_last5_mean_rival": row.get("shots_on_target_last5_mean_rival"),
        "shots_on_target_ratio_rival": row.get("shots_on_target_ratio_rival"),
    }

    info_partido = {
        "local": row["Equipo_propio"],
        "visitante": row["Equipo_rival"],
        "portero_predice": portero,
        "es_local": bool(row.get("local", True)),
        "probabilidad_victoria": float(row["p_win_propio"]) if pd.notna(row.get("p_win_propio")) else None,
        "probabilidad_empate": float(row["p_draw_match"]) if pd.notna(row.get("p_draw_match")) else None,
        "probabilidad_derrota": float(row["p_loss_propio"]) if pd.notna(row.get("p_loss_propio")) else None,
        "probabilidad_over25": float(row["p_over25_match"]) if pd.notna(row.get("p_over25_match")) else None,
    }

    contexto = {
        "pf_last5_mean": float(row["pf_last5_mean"]) if "pf_last5_mean" in row and pd.notna(row["pf_last5_mean"]) else None,
        "pf_last5_std": float(row["pf_last5_std"]) if "pf_last5_std" in row and pd.notna(row["pf_last5_std"]) else None,
        "posicion_propia": int(row["posicion_equipo"]) if pd.notna(row.get("posicion_equipo")) else None,
        "posicion_rival": int(row["posicion_rival"]) if pd.notna(row.get("posicion_rival")) else None,
        "pts_diff": int(row["pts_diff"]) if pd.notna(row.get("pts_diff")) else None,
        "xg_last5_mean_team": row.get("xg_last5_mean_team"),
        "xg_last5_mean_rival": row.get("xg_last5_mean_rival"),
        "shots_last5_mean_rival": row.get("shots_last5_mean_rival"),
        "shots_on_target_ratio_rival": row.get("shots_on_target_ratio_rival"),
        "p_win": float(row["p_win_propio"]) if pd.notna(row.get("p_win_propio")) else None,
    }

    # ============================
    # 4) FEATURES -> X (aquí va el cambio para XGB)
    # ============================
    try:
        X = preparar_X_para_modelo(row, feature_cols)
    except KeyError as e:
        return {
            "error": f"Falta la columna {str(e)} en los datos de predicción",
            "partido": partido,
            "portero": portero,
        }

    # ============================
    # 5) PREDICCIÓN
    # ============================
    try:
        pred_raw = float(modelo.predict(X)[0])
        pred_redondeada = int(round(pred_raw))
    except Exception as e:
        return {
            "error": f"Error en predicción: {e}",
            "partido": partido,
            "portero": portero,
        }

    return {
        "error": None,
        "partido": partido,
        "portero": portero,
        "equipo_portero": row["Equipo_propio"],
        "es_local": bool(row.get("local", True)),
        "jornada": int(jornada) if jornada is not None else int(row.get("jornada", 0)),
        "temporada": row.get("temporada"),
        "prediccion_raw": pred_raw,
        "prediccion_redondeada": pred_redondeada,
        "info_portero": info_portero,
        "info_equipo_propio": info_equipo_propio,
        "info_rival": info_rival,
        "info_partido": info_partido,
        "contexto": contexto,
        "row_original": row,
        "features_usadas": X.to_dict(orient="records")[0],
    }

def mostrar_prediccion_detallada(pred: dict, verbose: bool = True):
    if pred.get("error"):
        print(f"❌ ERROR: {pred['error']}")
        return

    print("=" * 100)
    print("PREDICCIÓN DE PARTIDO")
    print("=" * 100)
    print(f"Partido: {pred['partido'].upper()}")
    print(f"Portero: {pred['portero']}")
    print(f"Puntos Fantasy esperados: {pred['prediccion_redondeada']} (raw: {pred['prediccion_raw']:.2f})")
    print("-" * 100)

    gk = pred["info_portero"]
    ctx = pred["contexto"]
    print("Rachas portero (últimos 5, excluyendo el partido a predecir):")
    if gk.get("pf_last5_mean") is not None:
        print(f"  - PF promedio: {gk['pf_last5_mean']:.2f}")
    if gk.get("gc_last5_mean") is not None:
        print(f"  - Goles contra promedio: {gk['gc_last5_mean']:.2f}")
    if gk.get("psxg_last5_mean") is not None:
        print(f"  - PSxG promedio: {gk['psxg_last5_mean']:.2f}")
    if gk.get("clean_last5_sum") is not None:
        print(f"  - Clean sheets: {gk['clean_last5_sum']}/5")

    print("-" * 100)
    print("Contexto partido:")
    if ctx.get("pf_last5_mean") is not None:
        print(f"  - PF últimos 5: {ctx['pf_last5_mean']:.2f}")
    if ctx.get("posicion_propia") is not None:
        print(f"  - Posición propia: {ctx['posicion_propia']}")
    if ctx.get("posicion_rival") is not None:
        print(f"  - Posición rival: {ctx['posicion_rival']}")
    if ctx.get("p_win") is not None:
        print(f"  - Prob. victoria: {ctx['p_win']:.2f}")

    print("=" * 100)


def preparar_X_para_modelo(df_row, feature_cols):
    """
    Deja las features en formato numérico (float) para modelos como XGBoost.
    Es independiente del resto de la lógica; se puede borrar sin romper nada.
    """
    X = pd.DataFrame(df_row[feature_cols]).T
    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return X

if __name__ == "__main__":
    print("futro.py v3 - Módulo de predicción con rachas recalculadas")
    print("Usar desde predictor.py: from futro import predecir_partido, mostrar_prediccion_detallada")
