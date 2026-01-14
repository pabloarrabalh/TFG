"""
PREDICTOR V5 - JORNADA 18 COMPLETA (10 PARTIDOS)
Predice los 2 porteros de cada partido
"""

import pickle
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]  
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scrapping.fbref import obtener_fantasy_jornada 

POS_PORTERO = "PT"

def obtener_partidos_y_porteros_desde_fantasy(jornada: int):
    """
    Devuelve lista:
    [
      ("local-visitante", ["PorteroLocal", "PorteroVisitante"]),
      ...
    ]
    usando obtener_fantasy_jornada(jornada).
    """
    sj = str(jornada)
    fantasy_por_partido = obtener_fantasy_jornada(sj)
    partidos = []

    for clave_partido, jugadores in fantasy_por_partido.items():
        # clave_partido = "local_norm-visit_norm"
        porteros_local = []
        porteros_visit = []

        local_norm, visit_norm = clave_partido.split("-")

        for info in jugadores.values():
            if info.get("posicion") != POS_PORTERO:
                continue
            equipo = info.get("equipo_norm")  # o "equipo" según estés usando
            nombre = info.get("nombre_original")

            if equipo == local_norm:
                porteros_local.append(nombre)
            elif equipo == visit_norm:
                porteros_visit.append(nombre)

        if not porteros_local or not porteros_visit:
            # si falta algún portero, lo saltamos o lo logueamos
            continue

        # coge el primero de cada lista (normalmente habrá 1)
        partidos.append(
            (clave_partido, [porteros_local[0], porteros_visit[0]])
        )
    #
    #print(partidos)
    return partidos


# ============================================================
# BUSCAR ARCHIVO EN MÚLTIPLES UBICACIONES
# ============================================================

def buscar_archivo(filename, search_paths=None):
    if search_paths is None:
        search_paths = [
            Path.cwd(),
            Path.cwd() / "main" / "pp",
            Path.cwd() / "main",
            Path.cwd() / "data" / "temporada_25_26",
            Path.cwd() / "data",
            Path.cwd().parent,
            Path.cwd().parent / "main" / "pp",
            Path.cwd().parent / "data" / "temporada_25_26",
        ]
    
    for path in search_paths:
        full_path = path / filename
        if full_path.exists():
            return str(full_path)
    
    return None


# ============================================================
# CARGAR MODELO LIMPIO
# ============================================================
def cargar_modelo():
    print("\n" + "="*80)
    print("🚀 PREDICTOR DE PUNTOS FANTASY - LA LIGA (JORNADA 18 COMPLETA)")
    print("="*80 + "\n")
    
    # ANTES:
    # modelo_path = buscar_archivo("modelo_porteros_limpio.pkl")
    # features_path = buscar_archivo("feature_cols_limpio.pkl")

    # AHORA:
    modelo_path = buscar_archivo("modelo_porteros.pkl")
    if not modelo_path:
        print("❌ Error: No se encontró modelo_porteros.pkl")
        return None, None

    features_path = buscar_archivo("feature_cols.pkl")
    if not features_path:
        print("❌ Error: No se encontró feature_cols.pkl")
        return None, None

    print(f"📂 Cargando modelo desde: {modelo_path}")

    try:
        with open(modelo_path, "rb") as f:
            modelo = pickle.load(f)
        with open(features_path, "rb") as f:
            feature_cols = pickle.load(f)

        print(f"✅ Modelo cargado. {len(feature_cols)} features\n")
        return modelo, feature_cols

    except Exception as e:
        print(f"❌ Error al cargar: {e}\n")
        return None, None


# ============================================================
# IMPORTAR FUNCIÓN DE PREDICCIÓN
# ============================================================

def importar_predictor():
    try:
        from futro import predecir_partido
        return predecir_partido
    except ImportError:
        print("❌ Error: No se puede importar futro.py")
        return None


# ============================================================
# PREDECIR PARTIDOS (AMBOS PORTEROS)
# ============================================================
def predecir_partidos(modelo, feature_cols, jornada=None):
    print("\n" + "="*60)
    if jornada:
        print(f"🎯 PREDICCIONES - JORNADA {jornada} (10 PARTIDOS - 20 PORTEROS)")
    else:
        print("🎯 PREDICCIONES (jornada automática)")
    print("="*60 + "\n")

    predecir_partido = importar_predictor()
    if not predecir_partido:
        return []

    if jornada is None:
        raise ValueError("Para usar el calendario automático, pasa una jornada concreta")

    partidos = obtener_partidos_y_porteros_desde_fantasy(jornada)
    resultados = []

    # idx_partido empieza en 1 para alinearse con p1, p2, ... de los CSV reales
    for idx_partido, (partido, porteros) in enumerate(partidos, start=1):
        #print(f"\n{'='*80}")
        #print(f"🏟️  PARTIDO: {partido.upper()}")
        #print(f"{'='*80}")

        # 🔹 Cargar puntos reales (si existe CSV para este partido)
        df_real = cargar_reales_partido(jornada, idx_partido, partido)
        reales_map = {}
        if df_real is not None:
            # df_real tiene columnas: Portero_norm, Real
            reales_map = dict(df_real.values)  # {portero_norm: Real}

        for portero in porteros:
            #print(f"\n📊 Prediciendo: {portero}")
            #print("-" * 60)

            try:
                if jornada:
                    pred = predecir_partido(
                        partido,
                        portero,
                        modelo,
                        feature_cols,
                        jornada=jornada
                    )
                else:
                    pred = predecir_partido(
                        partido,
                        portero,
                        modelo,
                        feature_cols
                    )

                if pred.get("error"):
                    print(f"  ❌ Error: {pred['error']}")
                else:
                    # === usar alias también para el real ===
                    temporada_pred = pred.get("temporada", "25_26")
                    equipo_norm = pred.get("equipo_portero", "").lower().strip()

                    portero_norm_aliased = aplicar_alias_real_25_26(
                        portero,
                        equipo_norm,
                        temporada_pred,
                    )

                    pf_real = None
                    if reales_map:
                        for nombre_csv, real_val in reales_map.items():
                            nombre_csv_norm = _norm_text_pred(nombre_csv)
                            if portero_norm_aliased in nombre_csv_norm:
                                pf_real = real_val
                                break

                    if pf_real is not None and not pd.isna(pf_real):
                        dif = int(pred["prediccion_redondeada"] - pf_real)
                    else:
                        pf_real = None
                        dif = None

                    # guardar comparación dentro del dict
                    pred["pf_real"] = pf_real
                    pred["dif_pred_real"] = dif

                    # guardar info rival (para top errores)
                    row_orig = pred.get("row_original")
                    if row_orig is not None:
                        pred["equipo_rival"] = row_orig.get("Equipo_rival")
                        pred["goles_rival"] = row_orig.get("gf_rival")
                    else:
                        pred["equipo_rival"] = None
                        pred["goles_rival"] = None

                    resultados.append(pred)

            except Exception as e:
                print(f"  ❌ Error: {str(e)}")

    return resultados

# ============================================================
# TABLA RESUMEN POR PARTIDO
# ============================================================
def mostrar_tabla_por_partido(resultados):
    if not resultados:
        print("\n⚠️ No hay resultados para mostrar")
        return

    print("\n" + "="*80)
    print("📋 TABLA RESUMEN - JORNADA (PRED vs REAL)")
    print("="*80 + "\n")

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

    # === Error absoluto medio (MAE) ===
    df_valid = df_resumen.dropna(subset=["Real"])
    if not df_valid.empty:
        mae = (df_valid["Pred"] - df_valid["Real"]).abs().mean()
        print(f"\nMAE (Error absoluto medio): {mae:.3f}")
    else:
        print("\nMAE: no hay valores reales disponibles")

    print("\n" + "="*80)

# ============================================================
# TABLA COMPARATIVA
# ============================================================

def mostrar_tabla_comparativa(resultados):
    if not resultados:
        return
    
    print("\n" + "="*160)
    print("⚖️  COMPARATIVA: LOCAL vs VISITANTE (10 PARTIDOS)")
    print("="*160 + "\n")
    
    partidos_dict = {}
    for r in resultados:
        partido = r['partido']
        if partido not in partidos_dict:
            partidos_dict[partido] = {}
        
        posicion = 'LOCAL' if r['es_local'] else 'VISIT'
        partidos_dict[partido][posicion] = r
    
    comparativa = []
    for partido, porteros in sorted(partidos_dict.items()):
        if 'LOCAL' in porteros and 'VISIT' in porteros:
            local = porteros['LOCAL']
            visit = porteros['VISIT']
            
            comparativa.append({
                'Partido': partido.upper(),
                'Portero Local': local['portero'],
                'Pred L': local['prediccion_redondeada'],
                'vs': '  VS  ',
                'Portero Visit': visit['portero'],
                'Pred V': visit['prediccion_redondeada'],
                'Dif': local['prediccion_redondeada'] - visit['prediccion_redondeada']
            })
    
    if comparativa:
        df_comp = pd.DataFrame(comparativa)
        print(df_comp.to_string(index=False))
        print("\n" + "="*160)


# ============================================================
# TOP PREDICCIONES
# ============================================================

def mostrar_top_predicciones(resultados):
    if not resultados:
        return
    
    print("\n" + "="*80)
    print("🏆 TOP 5 PORTEROS (PUNTOS ESPERADOS)")
    print("="*80 + "\n")
    
    top5 = sorted(resultados, key=lambda x: x['prediccion_redondeada'], reverse=True)[:5]
    
    for i, r in enumerate(top5, 1):
        print(f"{i}. {r['portero']:25s} ({r['equipo_portero'].upper():20s}) - {r['prediccion_redondeada']} pts")
    
    print("\n" + "="*80)
    print("⚠️  BAJO RIESGO (PUNTOS ESPERADOS)")
    print("="*80 + "\n")
    
    bottom5 = sorted(resultados, key=lambda x: x['prediccion_redondeada'])[:5]
    
    for i, r in enumerate(bottom5, 1):
        print(f"{i}. {r['portero']:25s} ({r['equipo_portero'].upper():20s}) - {r['prediccion_redondeada']} pts")
    
    print("\n" + "="*80)


# ============================================================
# GUARDAR RESULTADOS
# ============================================================

def guardar_resultados_csv(resultados, filename="predicciones_j18_completa.csv"):
    if not resultados:
        print("\n⚠️ No hay resultados para guardar")
        return
    
    filas = []
    for r in resultados:
        ctx = r['contexto']
        pf5 = ctx.get('pf_last5_mean')
        pos_prop = ctx.get('posicion_propia')
        pos_riv = ctx.get('posicion_rival')
        pwin = ctx.get('p_win')
        
        filas.append({
            'Partido': r['partido'],
            'Portero': r['portero'],
            'Equipo': r['equipo_portero'],
            'Posición': 'LOCAL' if r['es_local'] else 'VISITANTE',
            'Jornada': r['jornada'],
            'Predicción': r['prediccion_redondeada'],
            'Raw': round(r['prediccion_raw'], 2),
            'PF_Última5': round(pf5, 2) if pf5 is not None else None,
            'Posición_Propia': pos_prop,
            'Posición_Rival': pos_riv,
            'P_Win': round(pwin, 3) if pwin is not None else None,
        })
    
    df_resultados = pd.DataFrame(filas)
    df_resultados.to_csv(filename, index=False)
    print(f"\n✅ Resultados guardados en: {filename}")



from pathlib import Path

TEMPORADA_ACTUAL = "25_26"

def ruta_csv_partido_real(jornada: int, idx_partido: int, partido: str) -> Path:
    # partido viene como "celta-betis"
    carpeta = Path("data") / f"temporada_{TEMPORADA_ACTUAL}" / f"jornada_{jornada}"
    eq_loc_norm, eq_vis_norm = partido.split("-")  # ya están normalizados
    nombre_csv = f"p{idx_partido}_{eq_loc_norm}-{eq_vis_norm}.csv"
    return carpeta / nombre_csv

from scrapping.commons import normalizar_equipo

TEMPORADA_ACTUAL = "25_26"

from scrapping.commons import normalizar_equipo

import unicodedata

def _norm_text_pred(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

ALIAS_PORTEROS_REALES_25_26 = {
    # equipo_norm -> {fantasy_norm -> csv_norm}
    "betis": {
        "valles": "alvaro valles",
    },
    "espanyol": {
        "dmitrovic": "marko dmitrovic",
    },
    "barcelona": {
        "joan garcia": "joan garcia",
    },
}

def aplicar_alias_real_25_26(nombre_portero: str, equipo_norm: str, temporada: str) -> str:
    if temporada != "25_26":
        return _norm_text_pred(nombre_portero)
    equipo_norm_n = _norm_text_pred(equipo_norm)
    nombre_norm = _norm_text_pred(nombre_portero)
    mapa_equipo = ALIAS_PORTEROS_REALES_25_26.get(equipo_norm_n, {})
    return mapa_equipo.get(nombre_norm, nombre_norm)

TEMPORADA_ACTUAL = "25_26"

from pathlib import Path

TEMPORADA_ACTUAL = "25_26"

def _normalizar_equipo_csv(nombre: str) -> str:
    """
    Convierte el slug corto ('celta', 'athletic', 'rayo') al nombre largo
    que usas en los nombres de archivo de los CSV reales.
    """
    s = nombre.lower().strip()
    if s == "celta":
        return "celta vigo"
    if s == "athletic":
        return "athletic club"
    if s == "rayo":
        return "rayo vallecano"
    if s == "betis":
        return "real betis"
    # resto: betis, girona, levante, real madrid, real sociedad, mallorca, etc.
    return s

def cargar_reales_partido(jornada: int, idx_partido: int, partido: str) -> pd.DataFrame | None:
    """
    Busca el CSV real en la carpeta de la jornada IGNORANDO el prefijo pX_.
    Solo mira la parte 'local-visitante' del nombre de archivo, con nombres largos.

    Ejemplos jornada 6:
      partido = 'celta-betis'      -> patron '*celta vigo-real betis.csv'
      partido = 'athletic-girona'  -> patron '*athletic club-girona.csv'
      partido = 'atletico madrid-rayo' -> patron '*atletico madrid-rayo vallecano.csv'
    """
    carpeta = Path("data") / f"temporada_{TEMPORADA_ACTUAL}" / f"jornada_{jornada}"
    if not carpeta.exists():
        print(f"[REAL] Jornada {jornada} ❌ Carpeta no existe: {carpeta}")
        return None

    loc_slug, vis_slug = partido.split("-")

    loc_csv = _normalizar_equipo_csv(loc_slug)
    vis_csv = _normalizar_equipo_csv(vis_slug)

    patron = f"*{loc_csv}-{vis_csv}.csv"
    candidatos = list(carpeta.glob(patron))

    #print(f"[REAL] Jornada {jornada} P{idx_partido} {partido} -> patrón búsqueda: {patron}")

    if not candidatos:
        print(f"[REAL]   ❌ No se encontró ningún CSV que matchee {patron}")
        return None

    path_csv = candidatos[0]
    #print(f"[REAL]   ✅ Usando CSV: {path_csv}")

    try:
        df = pd.read_csv(path_csv)
    except Exception as e:
        print(f"[REAL]   ❌ Error leyendo CSV: {e}")
        return None

    #print(f"[REAL]   ✅ CSV cargado: {len(df)} filas, columnas: {list(df.columns)}")

    if "posicion" not in df.columns or "player" not in df.columns or "puntosFantasy" not in df.columns:
        print("[REAL]   ❌ Faltan columnas obligatorias (posicion/player/puntosFantasy)")
        return None

    df = df[df["posicion"] == "PT"].copy()
    #print(f"[REAL]   🔎 Filtrado porteros: {len(df)} filas")

    if df.empty:
        print("[REAL]   ⚠️ No hay porteros en este CSV")
        return None

    df["Portero_norm"] = df["player"].str.lower().str.strip()
    #print("[REAL]   👤 Porteros en CSV:", df["Portero_norm"].tolist())

    df = df[["Portero_norm", "puntosFantasy"]].rename(columns={"puntosFantasy": "Real"})
    return df


def cargar_reales_partido(jornada: int, idx_partido: int, partido: str) -> pd.DataFrame | None:
    """
    Busca el CSV real en la carpeta de la jornada IGNORANDO el prefijo pX_.
    Solo mira la parte 'local-visitante' del nombre de archivo.

    Ej:
      jornada_6 tiene:
        p1_celta vigo-betis.csv
        p2_athletic club-girona.csv
        p5_levante-real madrid.csv
        p8_real sociedad-mallorca.csv
        p10_oviedo-barcelona.csv
      Si partido = 'celta-betis', matchea con '*celta vigo-betis.csv' sin importar pX.
    """
    carpeta = Path("data") / f"temporada_{TEMPORADA_ACTUAL}" / f"jornada_{jornada}"

    if not carpeta.exists():
        print(f"[REAL] Jornada {jornada} ❌ Carpeta no existe: {carpeta}")
        return None

    loc_slug, vis_slug = partido.split("-")  # ej. 'celta-betis'

    loc_csv = _normalizar_equipo_csv(loc_slug)
    vis_csv = _normalizar_equipo_csv(vis_slug)

    patron = f"*{loc_csv}-{vis_csv}.csv"
    candidatos = list(carpeta.glob(patron))

    #print(f"[REAL] Jornada {jornada} P{idx_partido} {partido} -> patrón búsqueda: {patron}")

    if not candidatos:
        print(f"[REAL]   ❌ No se encontró ningún CSV que matchee {patron}")
        return None

    # Si hay varios (no debería), coge el primero
    path_csv = candidatos[0]
    #print(f"[REAL]   ✅ Usando CSV: {path_csv}")

    try:
        df = pd.read_csv(path_csv)
    except Exception as e:
        print(f"[REAL]   ❌ Error leyendo CSV: {e}")
        return None

    #print(f"[REAL]   ✅ CSV cargado: {len(df)} filas, columnas: {list(df.columns)}")

    if "posicion" not in df.columns or "player" not in df.columns or "puntosFantasy" not in df.columns:
        print("[REAL]   ❌ Faltan columnas obligatorias (posicion/player/puntosFantasy)")
        return None

    df = df[df["posicion"] == "PT"].copy()
    #print(f"[REAL]   🔎 Filtrado porteros: {len(df)} filas")

    if df.empty:
        print("[REAL]   ⚠️ No hay porteros en este CSV")
        return None

    df["Portero_norm"] = df["player"].str.lower().str.strip()
    #print("[REAL]   👤 Porteros en CSV:", df["Portero_norm"].tolist())

    df = df[["Portero_norm", "puntosFantasy"]].rename(columns={"puntosFantasy": "Real"})
    return df


def calcular_mae_jornada(resultados):
    """
    Devuelve el MAE de Pred vs Real para una jornada y
    muestra el TOP 10 casos con más error absoluto:
    nombre, equipo rival, goles equipo rival.
    """
    if not resultados:
        return None

    filas = []
    for r in resultados:
        pf_real = r.get("pf_real")
        if pf_real is None:
            continue
        filas.append({
            "Partido": r["partido"].upper(),
            "Portero": r["portero"],
            "Equipo_rival": r.get("equipo_rival"),
            #"Goles_rival": r.get("goles_rival"),
            "Pred": r["prediccion_redondeada"],
            "Real": pf_real,
        })

    if not filas:
        return None

    df = pd.DataFrame(filas)
    df["abs_err"] = (df["Pred"] - df["Real"]).abs()

    mae = df["abs_err"].mean()

    # Top 10 errores
    top10 = df.sort_values("abs_err", ascending=False).head(10)
    '''
    print("\nTOP 10 ERRORES (abs(Pred-Real))")
    print(
        top10[
            ["Partido", "Portero", "Equipo_rival",
             "Pred", "Real", "abs_err"]
        ].to_string(index=False)
    )'''

    return mae

def mostrar_top_errores(resultados, top_n=10):
    df = pd.DataFrame(resultados)

    # LOG 1: filas con Real NaN (no se encontró CSV / portero)
    mask_nan = df["Real"].isna()
    if mask_nan.any():
        print("\n⚠️ LOG PORTEROS SIN REAL (NaN):")
        print(df.loc[mask_nan, ["Partido", "Portero", "Equipo_propio", "Equipo_rival"]].head(20))

    # LOG 2: posibles problemas de mapeo (apellidos raros, contains, etc.)
    print("\n🔍 LOG NOMBRES DE PORTERO (primeras 20 filas):")
    print(df[["Partido", "Portero", "Equipo_propio", "Equipo_rival", "Pred", "Real"]].head(20))

    # LOG 3: errores gordos (por si hay outliers tipo 10 vs -1)
    df["abs_err"] = (df["Pred"] - df["Real"]).abs()
    df_valid = df.dropna(subset=["Real"]).copy()
    df_top = df_valid.sort_values("abs_err", ascending=False).head(top_n)

    print("\nTOP 10 ERRORES (abs(Pred-Real))")
    print(df_top[["Partido", "Portero", "Equipo_rival", "Pred", "Real", "abs_err"]])
    print(f"\nMAE jornada {df_valid['jornada'].iloc[0]}: {df_top['abs_err'].mean():.3f}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    

    modelos_a_probar = [
        "modelos/best_mae_win3_rf_win3_rf_ne400_d8_l15_mf6_mae1.6421_rmse2.2088_r20.7049.pkl",
        "modelos/best_mae_win3_rf_win3_rf_ne400_d14_l20_mf6_mae1.6474_rmse2.2219_r20.7014.pkl",
        "modelos/best_mae_win3_rf_win3_rf_ne400_d12_l20_mf6_mae1.6474_rmse2.2219_r20.7014.pkl",
        "modelos/best_r2_win5_rf_win5_rf_ne400_d10_l15_mf6_mae1.6842_rmse2.1920_r20.7094.pkl",
        "modelos/best_r2_win5_rf_win5_rf_ne400_d12_l15_mf6_mae1.6737_rmse2.1915_r20.7095.pkl",
        "modelos/best_r2_win5_rf_win5_rf_ne400_d14_l15_mf6_mae1.6737_rmse2.1915_r20.7095.pkl",
    ]

    jornadas_a_probar = [18]  # puedes cambiar las jornadas aquí

    for modelo_path in modelos_a_probar:
        print("\n" + "#"*100)
        print(f"Probando modelo: {modelo_path}")
        print("#"*100)
        try:
            with open(modelo_path, "rb") as f:
                modelo = pickle.load(f)
        except Exception as e:
            print(f"❌ Error cargando modelo {modelo_path}: {e}")
            continue

        # Intentar cargar las features asociadas (puedes ajustar el nombre si cada modelo tiene su propio features)
        features_path = "feature_cols.pkl"
        try:
            with open(features_path, "rb") as f:
                feature_cols = pickle.load(f)
        except Exception as e:
            print(f"❌ Error cargando features: {e}")
            continue

        for j in jornadas_a_probar:
            print(f"\n===== JORNADA {j} =====\n")
            resultados = predecir_partidos(modelo, feature_cols, jornada=j)
            mostrar_tabla_por_partido(resultados)
            mae_j = calcular_mae_jornada(resultados)
            if mae_j is not None:
                print(f"\nMAE jornada {j}: {mae_j:.3f}")
            else:
                print(f"\nMAE jornada {j}: no hay datos reales")
