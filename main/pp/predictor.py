"""
PREDICTOR V6 - PORTEROS SIN DATA LEAKAGE
Solo features conocidas ANTES del partido
Alias robusto para mapeo fantasy <-> CSV
FEATURES COMPLETAS IGUAL QUE ENTRENAMIENTO
"""
from frases import generar_texto_xai
import shap
import pickle
import pandas as pd
from pathlib import Path
import sys
import unicodedata
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scrapping.fbref import obtener_fantasy_jornada
from scrapping.commons import normalizar_equipo

POS_PORTERO = "PT"
TEMPORADA_ACTUAL = "25_26"


# ============================================================
# NORMALIZACIONES Y ALIAS
# ============================================================

def _norm_text(s: str) -> str:
    """Normaliza texto: minúsculas, sin tildes, espacios simples"""
    if s is None:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("-", " ").replace(".", " ")
    return " ".join(s.split())


# ALIAS PORTEROS 25_26: fantasy_norm -> nombre_largo_csv_norm
ALIAS_PORTEROS_25_26 = {
    "betis": {
        "valles": "alvaro valles",
        "pau lopez": "pau lopez",
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
        "cunat campos": "pablo cunat",
        "cuñat campos": "pablo cunat",
    },
    "mallorca": {
        "bergstrom": "lucas bergstrom",
    },
    "atletico madrid": {
        "oblak": "jan oblak",
    },
    "real madrid": {
        "courtois": "thibaut courtois",
    },
    "real sociedad": {
        "remiro": "alex remiro",
    },
    "athletic": {
        "unai simon": "unai simon",
    },
}


def obtener_nombre_largo_portero(nombre_fantasy: str, equipo_norm: str) -> str:
    """
    Convierte nombre fantasy (ej 'Valles') al nombre largo CSV (ej 'Alvaro Valles')
    usando equipo_norm ya normalizado ('betis', 'espanyol', etc.)
    """
    nombre_norm = _norm_text(nombre_fantasy)
    equipo_norm_n = _norm_text(equipo_norm)

    mapa_equipo = ALIAS_PORTEROS_25_26.get(equipo_norm_n, {})
    nombre_largo_norm = mapa_equipo.get(nombre_norm, nombre_norm)

    return nombre_largo_norm


# ============================================================
# OBTENER PARTIDOS Y PORTEROS
# ============================================================

def obtener_partidos_y_porteros_desde_fantasy(jornada: int):
    """
    Devuelve lista de (partido, [portero_local, portero_visitante])
    """
    sj = str(jornada)
    fantasy_por_partido = obtener_fantasy_jornada(sj)

    partidos = []
    for clave_partido, jugadores in fantasy_por_partido.items():
        porteros_local = []
        porteros_visit = []

        local_norm, visit_norm = clave_partido.split("-")

        for info in jugadores.values():
            if info.get("posicion") != POS_PORTERO:
                continue
            equipo = info.get("equipo_norm")
            nombre = info.get("nombre_original")

            if equipo == local_norm:
                porteros_local.append(nombre)
            elif equipo == visit_norm:
                porteros_visit.append(nombre)

        if not porteros_local or not porteros_visit:
            continue

        partidos.append((clave_partido, [porteros_local[0], porteros_visit[0]]))

    return partidos


# ============================================================
# CARGAR DATOS HISTÓRICOS
# ============================================================

def cargar_datos_temporada() -> pd.DataFrame:
    """
    Carga CSV de características (SIN DATA LEAKAGE)
    Recalcula rachas 3 y 5 partidos excluyendo el actual
    TODAS LAS FEATURES igual que en entrenar-modelo-limpio.py
    """
    search_paths = [
        Path.cwd(),
        Path.cwd() / "main" / "pp",
        Path.cwd() / "data",
        Path.cwd().parent,
        Path.cwd().parent / "main" / "pp",
    ]

    csv_path = None
    for p in search_paths:
        candidate = p / "players_with_features_exp3_CORREGIDO.csv"
        if candidate.exists():
            csv_path = candidate
            break

    if csv_path is None:
        print("❌ Error: No se encontró players_with_features_exp3_CORREGIDO.csv")
        return None

    df = pd.read_csv(csv_path)
    df = df[df["posicion"] == "PT"].copy()

    # Ordenar temporalmente
    sort_cols = []
    for c in ["temporada", "jornada", "fecha_partido"]:
        if c in df.columns:
            sort_cols.append(c)

    df = df.sort_values(sort_cols).reset_index(drop=True)

    # MEDIA HISTÓRICA PF
    if "puntosFantasy" in df.columns:
        df["pf_media_historica"] = (
            df.groupby("player")["puntosFantasy"]
              .transform(lambda s: s.shift().expanding().mean())
        )

    # FEATURES PARTIDO (match el entrenamiento actual)
    if "p_win_propio" in df.columns:
        df["p_win_minus_loss"] = (
            df["p_win_propio"].clip(0, 1) - df["p_loss_propio"].clip(0, 1)
        )
    else:
        df["p_win_minus_loss"] = 0.0

    df["bombardeo_partido"] = (
        df["shots_on_target_rival_partido"].clip(lower=0) *
        (1 - df["Goles_en_contra"].clip(lower=0))
    )

    df["saves_partido"] = (
        df["shots_on_target_rival_partido"].clip(lower=0) -
        df["Goles_en_contra"].clip(lower=0)
    ).clip(lower=0)

    df["clean_sheet_flag"] = (df["Goles_en_contra"] == 0).astype(int)
    df["partido_muy_desequilibrado"] = (df["ah_line_match"].abs() >= 1.5).astype(int)

    df["goles_ev_prt"] = (df["PSxG"] - df["Goles_en_contra"]).clip(lower=0)
    df["ratio_paradas_dificiles"] = np.where(
        df["shots_on_target_rival_partido"] > 0,
        df["goles_ev_prt"] / df["shots_on_target_rival_partido"],
        0
    )

    # SAVE% HISTÓRICO (sin leakage)
    df["paradas_partido"] = df["saves_partido"]

    df["shots_on_target_hist"] = (
        df.groupby("player")["shots_on_target_rival_partido"]
          .transform(lambda s: s.shift().expanding().sum())
    )

    df["paradas_hist"] = (
        df.groupby("player")["paradas_partido"]
          .transform(lambda s: s.shift().expanding().sum())
    )

    df["savepct_hist"] = np.where(
        df["shots_on_target_hist"] > 0,
        df["paradas_hist"] / df["shots_on_target_hist"],
        np.nan
    )

    # Mezclas portero x rival
    df["xg_rival_x_savepct"] = df["xg_last5_mean_rival"] * df["savepct_hist"]
    df["xg_rival_x_gc_per90"] = df["xg_last5_mean_rival"] * df["gc_per90_last5"]
    df["gf_rival_last5_x_gc_per90"] = df["gf_last5_mean_rival"] * df["gc_per90_last5"]

    # ROLES / CALIDAD PORTERO
    df["score_porterias_cero"] = (1 - df["gc_per90_last5"]).clip(lower=0)
    df["score_save_pct"] = df["savepct_hist"]

    q_pc = df["score_porterias_cero"].quantile(0.8)
    q_sp = df["score_save_pct"].quantile(0.8)

    df["elite_keeper"] = (
        (df["score_porterias_cero"] >= q_pc) &
        (df["score_save_pct"] >= q_sp)
    ).astype(int)

    df["is_top5_porterias_cero"] = (df["score_porterias_cero"] >= q_pc).astype(int)
    df["is_top5_save_pct"] = (df["score_save_pct"] >= q_sp).astype(int)
    df["is_top5_en_algo"] = (
        (df["is_top5_porterias_cero"] == 1) |
        (df["is_top5_save_pct"] == 1)
    ).astype(int)

    df["score_pc_boost"] = df["score_porterias_cero"] * (df["ataque_top_rival"].fillna(0) + 1)
    df["score_sp_boost"] = df["score_save_pct"] * (df["ataque_top_rival"].fillna(0) + 1)
    df["rol_x_xg_rival"] = (
        df[["score_porterias_cero", "score_save_pct"]].mean(axis=1) *
        df["xg_last5_mean_rival"]
    )
    df["rol_x_xg_rival_boost"] = df["rol_x_xg_rival"] * (df["ataque_top_rival"].fillna(0) + 1)
    df["ataque_top_rival_x_elite"] = df["ataque_top_rival"].fillna(0) * df["elite_keeper"]

    # RACHAS SIN LEAKAGE
    def rolling_feat(col, window, agg, new_name):
        df[new_name] = (
            df.groupby("player")[col]
              .transform(lambda s: getattr(s.shift().rolling(window, min_periods=1), agg)())
        )

    # Window 3
    rolling_feat("puntosFantasy", 3, "mean", "pf_last3_mean")
    rolling_feat("savepct_hist", 3, "mean", "savepct_last3_mean")
    rolling_feat("clean_sheet_flag", 3, "mean", "clean_last3_ratio")
    rolling_feat("clean_sheet_flag", 3, "mean", "clean_last3_ratio_extra")
    rolling_feat("bombardeo_partido", 3, "mean", "bombardeo_last3_mean")
    rolling_feat("saves_partido", 3, "mean", "saves_last3_mean_extra")

    df["es_titular_partido"] = (df["Min_partido"] > 0).astype(int)
    rolling_feat("es_titular_partido", 3, "mean", "titular_last3_ratio")

    df["psxg_gc_diff"] = df["PSxG"] - df["Goles_en_contra"]
    rolling_feat("psxg_gc_diff", 3, "mean", "psxg_gc_diff_last3_mean")
    rolling_feat("saves_partido", 3, "mean", "saves_last3_mean")

    df["form_vs_class_keeper_3"] = df["pf_last3_mean"] - df["pf_media_historica"]

    # Window 5
    rolling_feat("puntosFantasy", 5, "mean", "pf_last5_mean")
    rolling_feat("savepct_hist", 5, "mean", "savepct_last5_mean")
    rolling_feat("clean_sheet_flag", 5, "mean", "clean_last5_ratio")
    rolling_feat("clean_sheet_flag", 5, "mean", "clean_last5_ratio_extra")
    rolling_feat("bombardeo_partido", 5, "mean", "bombardeo_last5_mean")
    rolling_feat("saves_partido", 5, "mean", "saves_last5_mean_extra")
    rolling_feat("es_titular_partido", 5, "mean", "titular_last5_ratio")
    rolling_feat("psxg_gc_diff", 5, "mean", "psxg_gc_diff_last5_mean")
    rolling_feat("saves_partido", 5, "mean", "saves_last5_mean")

    df["form_vs_class_keeper"] = df["pf_last5_mean"] - df["pf_media_historica"]

    return df


# ============================================================
# PREDICCIÓN
# ============================================================

def predecir_partido(
    partido: str,
    portero: str,
    modelo,
    feature_cols: list,
    jornada: int | None = None,
):
    """
    Predice puntos fantasy de un portero
    Usa la última fila (jornada máxima) de ese portero
    """
    temporada = TEMPORADA_ACTUAL
    df = cargar_datos_temporada()

    if df is None or len(df) == 0:
        return {
            "error": f"No hay datos para {temporada}",
            "partido": partido,
            "portero": portero,
        }

    # 1) BUSCAR PORTERO CON ALIAS
    row = None

    try:
        local_norm, visit_norm = partido.split("-")
        equipos_posibles = [local_norm, visit_norm]
    except ValueError:
        equipos_posibles = []

    if equipos_posibles:
        for equipo_norm in equipos_posibles:
            nombre_largo = obtener_nombre_largo_portero(portero, equipo_norm)
            nombre_busqueda_norm = _norm_text(nombre_largo)

            mask = (
                (df["temporada"] == temporada)
                & (df["Equipo_propio"].apply(_norm_text).str.lower() == equipo_norm.lower())
                & (df["player"].apply(_norm_text) == nombre_busqueda_norm)
                & (df["posicion"] == "PT")
            )

            if mask.sum() > 0:
                df_portero = df[mask].sort_values("jornada", ascending=False)
                row = df_portero.iloc[0]
                break

    # Fallback: búsqueda por contains
    if row is None:
        portero_lower = portero.lower().strip()
        mask = (
            df["player"].str.lower().str.contains(portero_lower, na=False)
            & (df["posicion"] == "PT")
        )

        if mask.sum() == 0:
            return {
                "error": f"Portero '{portero}' no encontrado",
                "partido": partido,
                "portero": portero,
            }

        df_portero = df[mask].sort_values("jornada", ascending=False)
        row = df_portero.iloc[0]

    # 2) PREPARAR FEATURES
    try:
        X = pd.DataFrame(row[feature_cols]).T
        X = X.apply(pd.to_numeric, errors="coerce")
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    except KeyError as e:
        return {
            "error": f"Falta columna {str(e)}",
            "partido": partido,
            "portero": portero,
        }

    # 3) PREDICCIÓN
    try:
        pred_raw = float(modelo.predict(X)[0])
        pred_redondeada = int(round(pred_raw))
    except Exception as e:
        return {
            "error": f"Error en predicción: {e}",
            "partido": partido,
            "portero": portero,
        }

    # 3bis) EXPLICACIÓN SHAP LOCAL
    try:
        explainer = shap.TreeExplainer(modelo)
        shap_vals = explainer.shap_values(X)
        shap_vals = np.array(shap_vals).flatten()

        pares = list(zip(feature_cols, shap_vals))

        top_pos = sorted(
            [p for p in pares if p[1] > 0],
            key=lambda x: x[1],
            reverse=True
        )[:3]

        top_neg = sorted(
            [p for p in pares if p[1] < 0],
            key=lambda x: x[1]
        )[:1]

        explicacion_shap = {
            "top_pos": [{"feature": f, "shap": float(v)} for f, v in top_pos],
            "top_neg": [{"feature": f, "shap": float(v)} for f, v in top_neg],
            "base_value": float(explainer.expected_value),
        }

    except Exception as e:
        explicacion_shap = {"error": str(e)}

    # 4) CONTEXTO
    contexto = {
        "pf_last5_mean": float(row.get("pf_last5_mean", np.nan)) if pd.notna(row.get("pf_last5_mean")) else None,
        "posicion_propia": int(row.get("posicion_equipo")) if pd.notna(row.get("posicion_equipo")) else None,
        "posicion_rival": int(row.get("posicion_rival")) if pd.notna(row.get("posicion_rival")) else None,
        "p_win": float(row.get("p_win_propio")) if pd.notna(row.get("p_win_propio")) else None,
        "xg_last5_mean_rival": row.get("xg_last5_mean_rival"),
        "shots_on_target_ratio_rival": row.get("shots_on_target_ratio_rival"),
    }

    return {
        "error": None,
        "partido": partido,
        "portero": row.get("player", portero),
        "equipo_portero": row.get("Equipo_propio", ""),
        "es_local": bool(row.get("local", True)),
        "jornada": int(jornada) if jornada is not None else int(row.get("jornada", 0)),
        "temporada": row.get("temporada"),
        "prediccion_raw": pred_raw,
        "prediccion_redondeada": pred_redondeada,
        "contexto": contexto,
        "row_original": row,
        "explicacion_shap": explicacion_shap,
    }


# ============================================================
# CARGAR REALES PARA COMPARACIÓN
# ============================================================

def cargar_reales_partido(jornada: int, partido: str) -> pd.DataFrame | None:
    carpeta = Path("data") / f"temporada_{TEMPORADA_ACTUAL}" / f"jornada_{jornada}"

    if not carpeta.exists():
        return None

    loc_slug, vis_slug = partido.split("-")

    mapping_largo = {
        "celta": "celta vigo",
        "athletic": "athletic club",
        "rayo": "rayo vallecano",
        "betis": "real betis",
    }

    loc_csv = mapping_largo.get(loc_slug, loc_slug)
    vis_csv = mapping_largo.get(vis_slug, vis_slug)

    patron = f"*{loc_csv}-{vis_csv}.csv"
    candidatos = list(carpeta.glob(patron))

    if not candidatos:
        return None

    try:
        df = pd.read_csv(candidatos[0])
    except:
        return None

    if "posicion" not in df.columns or "player" not in df.columns or "puntosFantasy" not in df.columns:
        return None

    df = df[df["posicion"] == "PT"].copy()
    if df.empty:
        return None

    df["Portero_norm"] = df["player"].apply(_norm_text)
    df = df[["Portero_norm", "puntosFantasy"]].rename(columns={"puntosFantasy": "Real"})

    return df


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

def mostrar_tabla_por_partido(resultados):
    if not resultados:
        print("\n⚠️ No hay resultados")
        return

    print("\n" + "="*100)
    print("📋 TABLA RESUMEN - JORNADA (PRED vs REAL)")
    print("="*100 + "\n")

    filas = []
    for r in resultados:
        filas.append({
            "Partido": r["partido"].upper(),
            "Portero": r["portero"],
            "Pred": r["prediccion_redondeada"],
            "Real": r.get("pf_real"),
        })

    df_resumen = pd.DataFrame(filas)
    print(df_resumen.to_string(index=False))

    df_valid = df_resumen.dropna(subset=["Real"])
    if not df_valid.empty:
        mae = (df_valid["Pred"] - df_valid["Real"]).abs().mean()
        print(f"\n✅ MAE (Error absoluto medio): {mae:.3f}")
    else:
        print("\n⚠️ MAE: no hay valores reales")

    print("\n" + "="*100)


# ============================================================
# MAIN
# ============================================================

def predecir_partidos(modelo, feature_cols, jornada=None):
    print("\n" + "="*60)
    if jornada:
        print(f"🎯 PREDICCIONES - JORNADA {jornada}")
    print("="*60 + "\n")

    if jornada is None:
        raise ValueError("Pasa una jornada concreta")

    partidos = obtener_partidos_y_porteros_desde_fantasy(jornada)
    resultados = []

    for partido, porteros in partidos:
        df_real = cargar_reales_partido(jornada, partido)
        for portero in porteros:
            print(f"📊 Prediciendo: {portero}")
            try:
                pred = predecir_partido(
                    partido,
                    portero,
                    modelo,
                    feature_cols,
                    jornada=jornada
                )
                if pred.get("error"):
                    print(f"  ❌ {pred['error']}")
                else:
                    equipo_norm = pred.get("equipo_portero", "").lower().strip()
                    portero_norm_aliased = obtener_nombre_largo_portero(portero, equipo_norm)

                    pf_real = None
                    if df_real is not None:
                        mask = df_real["Portero_norm"].apply(lambda x: portero_norm_aliased in x)
                        df_match = df_real[mask]
                        if not df_match.empty:
                            pf_real = df_match.iloc[0]["Real"]

                    if pf_real is not None and not pd.isna(pf_real):
                        dif = int(pred["prediccion_redondeada"] - pf_real)
                    else:
                        pf_real = None
                        dif = None

                    pred["pf_real"] = pf_real
                    pred["dif_pred_real"] = dif

                    row_orig = pred.get("row_original")
                    if row_orig is not None:
                        pred["equipo_rival"] = row_orig.get("Equipo_rival")
                        pred["goles_rival"] = row_orig.get("gf_rival")
                    else:
                        pred["equipo_rival"] = None
                        pred["goles_rival"] = None

                    resultados.append(pred)

                    exp = pred.get("explicacion_shap", {})
                    if exp and not exp.get("error"):
                        texto_xai = generar_texto_xai(exp)
                        print(texto_xai)

            except Exception as e:
                print(f"  ❌ Error: {str(e)}")

    return resultados


if __name__ == "__main__":

    modelos_a_probar = [
        # Actualiza esta ruta al mejor modelo del último entrenamiento
        #"modelos/best_mae_win3_xgb_d4_ne200_lr40_mae3.2789_rmse4.0699_r2-0.0172.pkl",
        "modelos/best_mae_win3_xgb_win3_xgb_d3_ne400_lr25_mae3.2842_rmse4.0272_r20.0041.pkl"
        ]

    for modelo_path in modelos_a_probar:
        print("\n" + "#"*100)
        print(f"Probando: {modelo_path}")
        print("#"*100)

        try:
            with open(modelo_path, "rb") as f:
                modelo = pickle.load(f)
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            continue

        if "win3" in modelo_path:
            features_path = "feature_cols_win3.pkl"
        elif "win5" in modelo_path:
            features_path = "feature_cols_win5.pkl"
        else:
            print("❌ No se puede inferir ventana")
            continue

        try:
            with open(features_path, "rb") as f:
                feature_cols = pickle.load(f)
        except:
            print(f"❌ Error cargando {features_path}")
            continue

        for j in range(1, 10):
            print(f"\n===== JORNADA {j} =====\n")
            resultados = predecir_partidos(modelo, feature_cols, jornada=j)
            mostrar_tabla_por_partido(resultados)
