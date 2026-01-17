"""
===============================================================================
ENTRENAMIENTO MODELOS FANTASY FOOTBALL - PORTEROS (VARIABLES HISTÓRICAS)
===============================================================================
Pipeline: EDA -> Features (TODAS) -> Shift para training -> Validación temporal
Autor: Pablo
Fecha: Enero 2026
Clave: Crear TODAS las features pero usar solo partidos ANTERIORES para entrenar
===============================================================================
"""


import warnings
from itertools import product
from pathlib import Path


import matplotlib
matplotlib.use("Agg")


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
from scipy.stats import kurtosis, skew
from statsmodels.stats.outliers_influence import variance_inflation_factor
from xgboost import XGBRegressor


from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Importar módulo de roles
try:
    from roles_enricher import (
        enriquecer_dataframe_con_roles,
        crear_features_interaccion_roles_v2,
        resumen_roles,
    )
    ROLES_DISPONIBLES = True
except ImportError:
    print("⚠️ Módulo roles_enricher.py no encontrado. Funcionará sin roles.")
    ROLES_DISPONIBLES = False


warnings.filterwarnings("ignore")



# ===========================
# CONFIGURACIÓN GENERAL
# ===========================
DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/portero")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"


for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS]:
    d.mkdir(parents=True, exist_ok=True)


RUTAS_BUSQUEDA = [
    Path.cwd(),
    Path.cwd() / "main" / "pp",
    Path.cwd() / "main",
    Path.cwd() / "data" / "temporada_25_26",
    Path.cwd() / "data",
    Path.cwd().parent,
    Path.cwd().parent / "main" / "pp",
]


ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
TAM_VENTANA = 5

# Usar roles si están disponibles
USAR_ROLES = ROLES_DISPONIBLES



# ===========================
# FUNCIONES AUXILIARES
# ===========================
def buscar_csv(rutas, nombre_csv):
    for ruta in rutas:
        ruta_completa = ruta / nombre_csv
        if ruta_completa.exists():
            return str(ruta_completa)
    return None



def crear_variables_rodantes(df, columna, ventanas=[5], funciones=['mean', 'std', 'min', 'max']):
    """
    Crea variables rodantes ESTÁNDAR (sin shift).
    Estas se usarán LUEGO con shift en la preparación del modelo.
    """
    variables = {}
    for w in ventanas:
        for agg in funciones:
            nombre = f"{columna}_roll{w}_{agg}"
            variables[nombre] = df.groupby("player")[columna].transform(
                lambda s: s.rolling(w, min_periods=1).agg(agg)
            )
    return variables



def entrenar_y_evaluar(modelo, X_entrenamiento, X_prueba, y_entrenamiento, y_prueba, redondear=False):
    modelo.fit(X_entrenamiento, y_entrenamiento)
    pred = modelo.predict(X_prueba)
    if redondear:
        pred = np.round(pred)

    return {
        "mae": mean_absolute_error(y_prueba, pred),
        "rmse": root_mean_squared_error(y_prueba, pred),
        "r2": r2_score(y_prueba, pred),
        "modelo": modelo,
        "predicciones": pred,
    }



def crear_malla_parametros(grid_dict):
    claves = list(grid_dict.keys())
    configuraciones = []
    for valores in product(*grid_dict.values()):
        configuraciones.append(dict(zip(claves, valores)))
    return configuraciones



def convertir_racha_a_numerico(racha):
    if pd.isna(racha) or not isinstance(racha, str):
        return 0, 0, 0, 0.0
    victorias = racha.count("W")
    empates = racha.count("D")
    derrotas = racha.count("L")
    total = victorias + empates + derrotas
    ratio = victorias / total if total > 0 else 0.0
    return victorias, empates, derrotas, ratio



def calcular_vif(df, variables, max_variables=20):
    print("========== MULTICOLINEALIDAD (VIF) ==========")
    print(f"Analizando VIF en {len(variables)} variables numéricas...")

    variables_numericas = df[variables].select_dtypes(include=[np.number]).columns.tolist()
    datos = df[variables_numericas].copy()

    print("Limpieza de datos para VIF...")
    print(f"  Antes: {datos.shape}")

    porcentaje_nan = datos.isnull().sum() / len(datos)
    columnas_utiles = porcentaje_nan[porcentaje_nan < 0.5].index.tolist()
    datos = datos[columnas_utiles]

    datos = datos.fillna(datos.median())
    datos = datos.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="any")

    print(f"  Después: {datos.shape}")

    if len(datos.columns) == 0:
        print("No hay suficientes variables válidas para calcular VIF.")
        return pd.DataFrame()

    if len(datos.columns) > max_variables:
        datos = datos.iloc[:, :max_variables]
        print(f"Limitado a las primeras {max_variables} variables.")

    try:
        vif_df = pd.DataFrame()
        vif_df["variable"] = datos.columns
        vif_df["vif"] = [
            variance_inflation_factor(datos.values, i)
            for i in range(len(datos.columns))
        ]
        vif_df = vif_df.sort_values("vif", ascending=False)

        print("\nTop 10 VIF:")
        print(vif_df.head(10).to_string(index=False))

        variables_altas = vif_df[vif_df["vif"] > 10]["variable"].tolist()
        if variables_altas:
            print(f"\nVariables con VIF > 10: {variables_altas}")
        else:
            print("\nNo se detecta multicolinealidad severa (VIF <= 10).")

        return vif_df
    except Exception as e:
        print(f"Error calculando VIF: {e}")
        return pd.DataFrame()



# ===========================
# ETAPA: CARGA Y EDA
# ===========================
def cargar_datos_porteros():
    ruta_csv = buscar_csv(RUTAS_BUSQUEDA, ARCHIVO_CSV)
    if not ruta_csv:
        print(f"No se encontró el archivo {ARCHIVO_CSV}")
        raise FileNotFoundError(ARCHIVO_CSV)

    print(f"📂 Cargando porteros desde: {ruta_csv}")
    df = pd.read_csv(ruta_csv)
    df = df[df["posicion"] == "PT"].copy()
    print(f"✅ Cargado: {df.shape[0]} filas porteros, {df.shape[1]} columnas\n")
    return df



def analizar_target(df, columna_objetivo, directorio_imagenes):
    print("=" * 80)
    print("ANÁLISIS DE LA VARIABLE OBJETIVO")
    print("=" * 80)

    valores = df[columna_objetivo].dropna()
    estadisticas = {
        "mean": valores.mean(),
        "std": valores.std(),
        "min": valores.min(),
        "max": valores.max(),
        "q25": valores.quantile(0.25),
        "q50": valores.quantile(0.50),
        "q75": valores.quantile(0.75),
    }

    for k, v in estadisticas.items():
        print(f"{k:8s}: {v:.3f}")

    plt.figure(figsize=(10, 6))
    plt.hist(valores, bins=30, edgecolor="black", alpha=0.75, color="steelblue")
    plt.axvline(estadisticas["mean"], color="red", linestyle="--", linewidth=2,
                label=f"Media: {estadisticas['mean']:.2f}")
    plt.axvline(estadisticas["q50"], color="green", linestyle="--", linewidth=2,
                label=f"Mediana: {estadisticas['q50']:.2f}")
    plt.title(f"Distribución {columna_objetivo} - Porteros")
    plt.xlabel(columna_objetivo)
    plt.ylabel("Frecuencia")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(directorio_imagenes / f"01_hist_{columna_objetivo}.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("✅ Histograma guardado")

    print(f"\nAsimetría: {skew(valores):.3f}")
    print(f"Curtosis: {kurtosis(valores, fisher=True):.3f}")
    iqr = estadisticas["q75"] - estadisticas["q25"]
    limite_inf = estadisticas["q25"] - 1.5 * iqr
    limite_sup = estadisticas["q75"] + 1.5 * iqr
    atipicos = ((valores < limite_inf) | (valores > limite_sup)).sum()
    print(f"Valores atípicos: {atipicos} ({atipicos / len(valores):.2%})\n")



# ===========================
# ETAPA: INGENIERÍA DE VARIABLES
# ===========================
def ordenar_datos(df):
    columnas_orden = [c for c in ["temporada", "jornada", "fecha_partido"] if c in df.columns]
    df = df.sort_values(columnas_orden).reset_index(drop=True)
    print(f"✅ Datos ordenados por: {columnas_orden}\n")
    return df



def limpiar_variables_irrelevantes(df):
    print("=" * 80)
    print("LIMPIEZA DE VARIABLES POCO RELEVANTES")
    print("=" * 80)

    a_eliminar = [
        "Tiros", "TiroFallado_partiido", "TiroPuerta_partido",
        "Asist_partido", "xAG", "Gol_partido",
        "DistanciaConduccion","MetrosAvanzadosConduccion",
        "Regates","RegatesCompletados","Min_partido","jornada","Duelos",
        "DuelosAereosGanadosPct","pj","jornada_anterior"
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    print(f"Variables eliminadas: {a_eliminar}\n")
    return df



def limpiar_variables_redundantes(df):
    print("=" * 80)
    print("LIMPIEZA DE VARIABLES REDUNDANTES")
    print("=" * 80)

    redundantes = []

    if "Pases_Totales" in df.columns and "Pases_Completados_Pct" in df.columns:
        redundantes.append("Pases_Totales")
        print("Mantener: Pases_Completados_Pct | Eliminar: Pases_Totales")

    regates_detalle = ["RegatesCommpletados", "RegatesFallidos"]
    for c in regates_detalle:
        if c in df.columns:
            redundantes.append(c)
    if "RegatesCommpletados" in df.columns and "RegatesFallidos" in df.columns:
        df["Regates_Pct"] = (
            df["RegatesCommpletados"] /
            (df["RegatesCommpletados"] + df["RegatesFallidos"] + 1)
        ).fillna(0)
        print("Mantener: Regates + Regates_Pct | Eliminar: Regates desagregados")

    duelos_detalle = ["DuelosGanados", "DuelosPerdidos"]
    for c in duelos_detalle:
        if c in df.columns:
            redundantes.append(c)
    if "DuelosGanados" in df.columns:
        print("Mantener: Duelos + DuelosGanadosPct | Eliminar: Duelos desagregados")

    duelos_aereos_detalle = ["DuelosAereosGanados", "DuelosAereosPerdidos"]
    for c in duelos_aereos_detalle:
        if c in df.columns:
            redundantes.append(c)
    print("Mantener: DuelosAereos + DuelosAereosGanadosPct | Eliminar: Duelos aéreos desagregados")

    bloqueos_detalle = ["BloqueoTiros", "BloqueoPase"]
    for c in bloqueos_detalle:
        if c in df.columns:
            redundantes.append(c)
    print("Mantener: Bloqueos | Eliminar: Bloqueos desagregados")

    df = df.drop(columns=redundantes, errors="ignore")
    print(f"\nVariables redundantes eliminadas: {redundantes}\n")
    return df



def convertir_rachas(df):
    print("=" * 80)
    print("CONVERSIÓN DE RACHAS A VARIABLES NUMÉRICAS")
    print("=" * 80)

    if "racha5partidos" in df.columns:
        datos = df["racha5partidos"].apply(convertir_racha_a_numerico)
        df["racha_victorias"] = datos.apply(lambda x: x[0])
        df["racha_empates"] = datos.apply(lambda x: x[1])
        df["racha_derrotas"] = datos.apply(lambda x: x[2])
        df["racha_ratio_victorias"] = datos.apply(lambda x: x[3])
        print("Racha del portero convertida")

    if "racha5partidos_rival" in df.columns:
        datos_rival = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
        df["racha_rival_victorias"] = datos_rival.apply(lambda x: x[0])
        df["racha_rival_empates"] = datos_rival.apply(lambda x: x[1])
        df["racha_rival_derrotas"] = datos_rival.apply(lambda x: x[2])
        df["racha_rival_ratio_victorias"] = datos_rival.apply(lambda x: x[3])
        print("Racha del rival convertida\n")

    return df



def crear_features_temporales(df, columna_objetivo):
    print("=" * 80)
    print("INGENIERÍA DE VARIABLES TEMPORALES (SHIFT / ROLLING)")
    print("=" * 80)

    print(f"Creando variables de ventana móvil (ventana={TAM_VENTANA})...\n")

    if columna_objetivo in df.columns:
        df["pf_media_historica"] = (
            df.groupby("player")[columna_objetivo]
              .transform(lambda s: s.shift().expanding().mean())
        )
        print("pf_media_historica creada")

    df["es_titular_anterior"] = df.groupby("player")["Titular"].shift(1).fillna(0).astype(int)
    df["porteria_cero_anterior"] = (
        df.groupby("player")["Goles_en_contra"]
          .shift(1)
          .apply(lambda x: 1 if x == 0 else 0)
          .fillna(0)
          .astype(int)
    )
    print("Indicadores binarios históricos creados")

    print("\nVariables rodantes portero:")
    vars_portero = ["Goles_en_contra", "Porcentaje_paradas"]
    psxg_cols = [c for c in df.columns if "PSXG" in c.upper()]
    if psxg_cols:
        vars_portero.append(psxg_cols[0])
        print(f"PSxG detectado como: {psxg_cols[0]}")
    if "Despejes" in df.columns:
        vars_portero.append("Despejes")

    for v in vars_portero:
        if v in df.columns:
            rodantes = crear_variables_rodantes(df, v, ventanas=[TAM_VENTANA], funciones=["mean", "std"])
            for nombre, valores in rodantes.items():
                df[nombre] = valores
            print(f"  {v}: media y desviación")

    print("\nVariables rodantes históricas (titularidad y porterías a cero):")
    for v in ["porteria_cero_anterior", "es_titular_anterior"]:
        rodantes = crear_variables_rodantes(df, v, ventanas=[TAM_VENTANA], funciones=["mean"])
        for nombre, valores in rodantes.items():
            df[nombre] = valores
        print(f"  {v}: media")

    print("\nVariables rodantes de equipo:")
    pares_equipo = [
        ("Equipo_propio", ["gf", "gc", "pg"]),
        ("Equipo_rival", ["gf_rival", "gc_rival", "pg_rival"]),
    ]
    for col_equipo, lista in pares_equipo:
        if col_equipo in df.columns:
            for v in lista:
                if v in df.columns:
                    df[f"{v}_roll{TAM_VENTANA}_mean"] = df.groupby(col_equipo)[v].transform(
                        lambda s: s.rolling(TAM_VENTANA, min_periods=1).mean()
                    )
                    print(f"  {v}_roll{TAM_VENTANA}_mean")

    print("\nVariables rodantes de tiros (histórico jugador):")
    vars_tiros = ["HS", "AS", "HST", "AST"]
    for v in vars_tiros:
        if v in df.columns:
            df[f"{v}_roll{TAM_VENTANA}_mean"] = df.groupby("player")[v].transform(
                lambda s: s.rolling(TAM_VENTANA, min_periods=1).mean()
            )
            print(f"  {v}_roll{TAM_VENTANA}_mean")

    return df



def crear_features_derivadas(df, columna_objetivo):
    print("\nVariables derivadas:")

    if "Porcentaje_paradas" in df.columns:
        df["ratio_paradas_hist"] = (
            df.groupby("player")["Porcentaje_paradas"]
              .transform(lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()) / 100
        ).fillna(0.5).clip(0, 1)
        print("  ratio_paradas_hist")

    if "Goles_en_contra" in df.columns:
        df["goles_contra_hist"] = (
            df.groupby("player")["Goles_en_contra"]
              .transform(lambda s: s.shift().expanding().mean())
        ).fillna(1.0)
        print("  goles_contra_hist")

    if "ratio_paradas_hist" in df.columns and "porteria_cero_anterior_roll5_mean" in df.columns:
        df["portero_elite"] = (
            (df["porteria_cero_anterior_roll5_mean"] >= df["porteria_cero_anterior_roll5_mean"].quantile(0.6)) &
            (df["ratio_paradas_hist"] >= df["ratio_paradas_hist"].quantile(0.6))
        ).astype(int)
        print("  portero_elite")

    print("\nVariables específicas para porteros:")

    if "Porcentaje_paradas" in df.columns:
        df["contexto_tiros"] = df.groupby("player")["Porcentaje_paradas"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean() * (1 + df["Goles_en_contra"].fillna(0))
        )
        print("  contexto_tiros")

    df["eficiencia_defensiva"] = (
        df.groupby("player")["porteria_cero_anterior"]
          .transform(lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).sum()) / TAM_VENTANA
    ).fillna(0)
    print("  eficiencia_defensiva")

    if "Porcentaje_paradas" in df.columns:
        df["variabilidad_actuacion"] = (
            df.groupby("player")["Porcentaje_paradas"]
              .transform(lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).std())
        ).fillna(0)
        print("  variabilidad_actuacion")

    if "AST_roll5_mean" in df.columns and "HST_roll5_mean" in df.columns:
        df["presion_tiros"] = (
            (df["AST_roll5_mean"] - df["HST_roll5_mean"]) /
            (df["AST_roll5_mean"] + df["HST_roll5_mean"] + 1)
        ).fillna(0)
        print("  presion_tiros")

    df["racha_porterias_cero"] = df.groupby("player")["porteria_cero_anterior"].transform(
        lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).sum()
    )
    print("  racha_porterias_cero")

    if columna_objetivo in df.columns:
        df["indice_fiabilidad"] = (
            df.groupby("player")[columna_objetivo]
              .transform(lambda s: (s.shift() > 0).astype(int).rolling(TAM_VENTANA, min_periods=1).mean())
        ).fillna(0.5)
        print("  indice_fiabilidad")

    if "gf_roll5_mean" in df.columns and "gc_roll5_mean" in df.columns:
        df["equilibrio_equipo"] = (
            df["gf_roll5_mean"] / (df["gc_roll5_mean"] + 0.5)
        ).fillna(1.0).clip(0.1, 10)
        print("  equilibrio_equipo")

    print("\n✅ Ingeniería de variables completada\n")
    return df



# ===========================
# ETAPA: DEFINICIÓN VARIABLES
# ===========================
def definir_variables_finales(df, columna_objetivo):
    print("=" * 80)
    print("DEFINICIÓN DE VARIABLES FINALES PARA EL MODELO")
    print("=" * 80)

    variables = [
        "local", "Titular",

        "Goles_en_contra_roll5_mean", "Goles_en_contra_roll5_std",
        "Porcentaje_paradas_roll5_mean", "Porcentaje_paradas_roll5_std",
        "Despejes_roll5_mean",

        "porteria_cero_anterior_roll5_mean", "es_titular_anterior_roll5_mean",
        "pf_media_historica", "ratio_paradas_hist", "goles_contra_hist",

        "racha_victorias", "racha_empates", "racha_derrotas", "racha_ratio_victorias",
        "racha_rival_victorias", "racha_rival_empates", "racha_rival_derrotas",
        "racha_rival_ratio_victorias",

        "gf_roll5_mean", "gc_roll5_mean", "pg_roll5_mean",
        "gf_rival_roll5_mean", "gc_rival_roll5_mean", "pg_rival_roll5_mean",

        "HST_roll5_mean", "AST_roll5_mean",

        "portero_elite",

        "contexto_tiros", "eficiencia_defensiva", "variabilidad_actuacion",
        "presion_tiros", "racha_porterias_cero", "indice_fiabilidad", "equilibrio_equipo",
    ]
    
    # Agregar variables de roles si están disponibles
    if USAR_ROLES:
        variables.extend([
            "tiene_rol_destacado", "num_roles", "score_roles", "es_portero_elite",
            "rol_paradas_valor", "rol_paradas_posicion",
            "rol_porterias_cero_valor", "rol_porterias_cero_posicion",
            "rol_save_pct_valor", "rol_save_pct_posicion",
            "rol_minutos_valor", "rol_minutos_posicion",
            "rol_despejes_valor", "rol_despejes_posicion",
            "elite_paradas_interact", "porterias_cero_eficiencia",
            "score_roles_normalizado", "num_roles_criticos", "ratio_roles_criticos",
            "tiene_rol_defensivo",
        ])

    variables = [v for v in variables if v in df.columns]
    print(f"✅ Variables finales disponibles: {len(variables)}\n")
    for i, v in enumerate(variables, 1):
        print(f"{i:2d}. {v}")
    print()
    return variables



def preparar_datos_modelo_con_shift(df, variables_finales, columna_objetivo):
    """
    CRÍTICO: Aquí es donde aplicamos SHIFT para evitar leakage.
    - Usamos df con TODAS las features calculadas
    - Shifteamos las variables para usar solo partidos anteriores
    """
    print("=" * 80)
    print("PREPARACIÓN DE MATRIZ DE ENTRENAMIENTO (CON SHIFT)")
    print("=" * 80)

    # Crear copia para no modificar original
    df_modelo = df.copy()
    
    # Variables que necesitan shift (las que dependen del partido actual)
    variables_con_shift = [
        "Goles_en_contra_roll5_mean", "Goles_en_contra_roll5_std",
        "Porcentaje_paradas_roll5_mean", "Porcentaje_paradas_roll5_std",
        "Despejes_roll5_mean",
        "ratio_paradas_hist", "goles_contra_hist",
        "contexto_tiros", "eficiencia_defensiva", "variabilidad_actuacion",
        "presion_tiros", "racha_porterias_cero",
        "portero_elite", "equilibrio_equipo",
        "gf_roll5_mean", "gc_roll5_mean", "pg_roll5_mean",
        "gf_rival_roll5_mean", "gc_rival_roll5_mean", "pg_rival_roll5_mean",
        "HST_roll5_mean", "AST_roll5_mean",
    ]
    
    print(f"\nAplicando SHIFT a variables con dependencia del partido actual:")
    print(f"Variables a shiftearse: {len([v for v in variables_con_shift if v in df_modelo.columns])}\n")
    
    for var in variables_con_shift:
        if var in df_modelo.columns:
            # Groupby player para mantener series independientes por jugador
            df_modelo[var] = df_modelo.groupby("player")[var].shift(1)
    
    print("✅ SHIFT aplicado exitosamente\n")
    
    # Eliminar NaN resultantes del shift (primera fila de cada jugador)
    df_modelo = df_modelo[[c for c in variables_finales if c in df_modelo.columns] + [columna_objetivo]].dropna()
    
    print(f"Filas después de dropna: {len(df_modelo)} (de {len(df)})")
    print(f"Número de variables: {len([v for v in variables_finales if v in df_modelo.columns])}")
    print(f"Rango objetivo {columna_objetivo}: [{df_modelo[columna_objetivo].min():.2f}, "
          f"{df_modelo[columna_objetivo].max():.2f}]\n")

    X = df_modelo[[v for v in variables_finales if v in df_modelo.columns]]
    y = df_modelo[columna_objetivo]
    return X, y, df_modelo



def generar_splits_temporales(X, n_splits=5):
    print("=" * 80)
    print("VALIDACIÓN CRUZADA TEMPORAL")
    print("=" * 80)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    folds = []
    for i, (idx_ent, idx_pru) in enumerate(tscv.split(X), 1):
        print(f"Fold {i}: Train {len(idx_ent)} | Test {len(idx_pru)}")
        folds.append({
            "fold": i,
            "idx_entrenamiento": idx_ent,
            "idx_prueba": idx_pru,
        })
    print()
    return folds



# ===========================
# ETAPA: ENTRENAMIENTO MODELOS
# ===========================
def definir_grids():
    print("=" * 80)
    print("CONFIGURACIÓN DE MALLAS DE PARÁMETROS")
    print("=" * 80)

    grid_rf = crear_malla_parametros({
        "n_estimators": [200, 400, 600],
        "max_depth": [8, 10, 12, 15],
        "min_samples_leaf": [3, 5, 7],
        "max_features": [0.3, 0.5, 0.7],
    })

    grid_xgb = crear_malla_parametros({
        "max_depth": [3, 4, 5, 6],
        "n_estimators": [200, 400, 600, 800],
        "learning_rate": [0.01, 0.02, 0.03],
    })

    grid_elastic = crear_malla_parametros({
        "alpha": [0.001, 0.005, 0.01, 0.05],
        "l1_ratio": [0.0, 0.3, 0.5, 0.7, 1.0],
    })

    print(f"Configuraciones RF: {len(grid_rf)}")
    print(f"Configuraciones XGBoost: {len(grid_xgb)}")
    print(f"Configuraciones ElasticNet: {len(grid_elastic)}\n")

    return grid_rf, grid_xgb, grid_elastic



def entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic):
    print("=" * 80)
    print("ENTRENAMIENTO DE MODELOS (VALIDACIÓN TEMPORAL)")
    print("=" * 80)

    resultados = []

    for info_fold in folds:
        fold = info_fold["fold"]
        idx_ent = info_fold["idx_entrenamiento"]
        idx_pru = info_fold["idx_prueba"]

        X_ent, X_pru = X.iloc[idx_ent], X.iloc[idx_pru]
        y_ent, y_pru = y.iloc[idx_ent], y.iloc[idx_pru]

        print(f"\n{'=' * 80}")
        print(f"FOLD {fold} / {len(folds)}")
        print("=" * 80)

        # BOSQUE ALEATORIO
        print("\n🔵 BOSQUE ALEATORIO")
        print("-" * 80)
        mejor_rf = None
        mejor_mae_rf = float("inf")

        for i, cfg in enumerate(grid_rf, 1):
            modelo = RandomForestRegressor(
                **cfg,
                random_state=42,
                n_jobs=-1,
            )
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru, redondear=False)
            res = {
                "fold": fold,
                "ventana": TAM_VENTANA,
                "tipo": "bosque",
                "config": cfg,
                "mae": m["mae"],
                "rmse": m["rmse"],
                "r2": m["r2"],
                "modelo": m["modelo"],
            }
            resultados.append(res)
            if m["mae"] < mejor_mae_rf:
                mejor_mae_rf = m["mae"]
                mejor_rf = res

            if i % 10 == 0:
                print(f"  [{i:3d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")

        if mejor_rf:
            print(f"\n  Mejor BOSQUE (Fold {fold}): MAE {mejor_rf['mae']:.4f} | R2 {mejor_rf['r2']:.4f}")
            print(f"  Config: {mejor_rf['config']}")

        # XGBOOST
        print("\n🟢 XGBOOST")
        print("-" * 80)
        mejor_xgb = None
        mejor_mae_xgb = float("inf")

        for i, cfg in enumerate(grid_xgb, 1):
            modelo = XGBRegressor(
                **cfg,
                subsample=0.9,
                colsample_bytree=0.9,
                min_child_weight=3,
                reg_lambda=1.0,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=-1,
            )
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru, redondear=False)
            res = {
                "fold": fold,
                "ventana": TAM_VENTANA,
                "tipo": "xgb",
                "config": cfg,
                "mae": m["mae"],
                "rmse": m["rmse"],
                "r2": m["r2"],
                "modelo": m["modelo"],
            }
            resultados.append(res)
            if m["mae"] < mejor_mae_xgb:
                mejor_mae_xgb = m["mae"]
                mejor_xgb = res

            if i % 10 == 0:
                print(f"  [{i:3d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")

        if mejor_xgb:
            print(f"\n  Mejor XGB (Fold {fold}): MAE {mejor_xgb['mae']:.4f} | R2 {mejor_xgb['r2']:.4f}")
            print(f"  Config: {mejor_xgb['config']}")

        # ELASTICNET
        print("\n🟡 ELASTICNET")
        print("-" * 80)
        mejor_elastic = None
        mejor_mae_elastic = float("inf")

        for i, cfg in enumerate(grid_elastic, 1):
            modelo = Pipeline([
                ("escalador", StandardScaler()),
                ("regresor", ElasticNet(
                    alpha=cfg["alpha"],
                    l1_ratio=cfg["l1_ratio"],
                    random_state=42,
                    max_iter=10000,
                )),
            ])
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru, redondear=False)
            res = {
                "fold": fold,
                "ventana": TAM_VENTANA,
                "tipo": "elastic",
                "config": cfg,
                "mae": m["mae"],
                "rmse": m["rmse"],
                "r2": m["r2"],
                "modelo": m["modelo"],
            }
            resultados.append(res)
            if m["mae"] < mejor_mae_elastic:
                mejor_mae_elastic = m["mae"]
                mejor_elastic = res

            if i % 5 == 0:
                print(f"  [{i:2d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")

        if mejor_elastic:
            print(f"\n  Mejor ELASTIC (Fold {fold}): MAE {mejor_elastic['mae']:.4f} | R2 {mejor_elastic['r2']:.4f}")
            print(f"  Config: {mejor_elastic['config']}")

    return resultados



def seleccionar_mejores_modelos(resultados):
    mejor_mae = min(resultados, key=lambda x: x["mae"])
    mejor_r2 = max(resultados, key=lambda x: x["r2"])

    print("\n" + "=" * 80)
    print("MEJORES MODELOS GLOBALES")
    print("=" * 80 + "\n")

    print(f"🥇 Mejor MAE (Fold {mejor_mae['fold']}, {mejor_mae['tipo'].upper()}):")
    print(f"   MAE: {mejor_mae['mae']:.4f} | RMSE: {mejor_mae['rmse']:.4f} | R2: {mejor_mae['r2']:.4f}")
    print("\n   Hiperparámetros:")
    for k, v in mejor_mae["config"].items():
        print(f"      {k}: {v}")

    print(f"\n{'=' * 80}\n")

    print(f"🥇 Mejor R2 (Fold {mejor_r2['fold']}, {mejor_r2['tipo'].upper()}):")
    print(f"   MAE: {mejor_r2['mae']:.4f} | RMSE: {mejor_r2['rmse']:.4f} | R2: {mejor_r2['r2']:.4f}")
    print("\n   Hiperparámetros:")
    for k, v in mejor_r2["config"].items():
        print(f"      {k}: {v}")

    return mejor_mae, mejor_r2



def guardar_resultados_csv(resultados):
    df_res = pd.DataFrame([
        {
            "fold": r["fold"],
            "tipo": r["tipo"],
            "mae": r["mae"],
            "rmse": r["rmse"],
            "r2": r["r2"],
            "config": str(r["config"]),
        }
        for r in resultados
    ])
    ruta = DIRECTORIO_SALIDA / "resultados_entrenamiento.csv"
    df_res.to_csv(ruta, index=False)
    print(f"\n✅ Resultados guardados en: {ruta}\n")



def diagnostico_modelos(mejor_mae, mejor_r2, folds, X, y):
    print("=" * 80)
    print("DIAGNÓSTICO DETALLADO")
    print("=" * 80)

    for res in [mejor_mae, mejor_r2]:
        print(f"\n🔍 {res['tipo'].upper()} - Fold {res['fold']}")
        fold_info = [f for f in folds if f["fold"] == res["fold"]][0]
        idx_pru = fold_info["idx_prueba"]
        y_pru = y.iloc[idx_pru]
        X_pru = X.iloc[idx_pru]

        pred = res["modelo"].predict(X_pru)
        media_baseline = y_pru.mean()
        mae_modelo = mean_absolute_error(y_pru, pred)
        mae_baseline = mean_absolute_error(y_pru, [media_baseline] * len(y_pru))

        print(f"  Objetivo: media={y_pru.mean():.2f} ± {y_pru.std():.2f}")
        print(f"  Predicciones: media={pred.mean():.2f} ± {pred.std():.2f}")
        print(f"  MAE modelo: {mae_modelo:.3f}")
        print(f"  MAE baseline (media): {mae_baseline:.3f}")
        print(f"  ΔMAE: {mae_modelo - mae_baseline:+.3f}")

    print("\nDistribución global de la variable objetivo:")
    print(f"  Media: {y.mean():.2f} | Std: {y.std():.2f}")
    print(f"  Min: {y.min():.1f} | Max: {y.max():.1f}")
    print(f"  Rango 95%: [{y.quantile(0.025):.1f}, {y.quantile(0.975):.1f}]\n")



def explicabilidad_shap(mejor_mae, folds, X, variables_finales):
    if mejor_mae["tipo"] not in ("bosque", "xgb"):
        print("SHAP solo se aplica al mejor modelo tipo árbol (bosque o xgb).")
        return

    print("=" * 80)
    print("EXPLICABILIDAD SHAP (MEJOR MODELO MAE)")
    print("=" * 80)

    try:
        fold_info = [f for f in folds if f["fold"] == mejor_mae["fold"]][0]
        idx_pru = fold_info["idx_prueba"]
        X_pru = X.iloc[idx_pru]

        print("Calculando valores SHAP...")
        explicador = shap.TreeExplainer(mejor_mae["modelo"])
        valores_shap = explicador.shap_values(X_pru)

        importancias = np.abs(valores_shap).mean(axis=0)
        df_imp = pd.DataFrame({"variable": X_pru.columns, "importancia": importancias}) \
                 .sort_values("importancia", ascending=False)

        print("\nTop 15 variables más importantes (SHAP):")
        print(df_imp.head(15).to_string(index=False))

        ruta_imp = DIRECTORIO_SALIDA / "importancias_shap.csv"
        df_imp.to_csv(ruta_imp, index=False)
        print(f"\n✅ Importancias SHAP guardadas en: {ruta_imp}")

        plt.figure(figsize=(12, 10))
        shap.summary_plot(valores_shap, X_pru, show=False, max_display=15)
        plt.tight_layout()
        plt.savefig(DIRECTORIO_IMAGENES / "02_shap_summary.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("✅ Gráfico resumen SHAP guardado")

        for i, var in enumerate(df_imp["variable"].head(3), 1):
            try:
                plt.figure(figsize=(8, 6))
                shap.dependence_plot(var, valores_shap, X_pru, show=False)
                plt.tight_layout()
                plt.savefig(DIRECTORIO_IMAGENES / f"03_shap_dependencia_{i:02d}_{var}.png",
                            dpi=150, bbox_inches="tight")
                plt.close()
                print(f"✅ Gráfico de dependencia {i}: {var}")
            except Exception as e:
                print(f"Error en gráfico de dependencia {var}: {e}")
    except Exception as e:
        print(f"Error en análisis SHAP: {e}")



def visualizar_resultados(resultados):
    print("=" * 80)
    print("VISUALIZACIONES COMPARATIVAS")
    print("=" * 80)

    fig, ejes = plt.subplots(1, 3, figsize=(16, 5))
    for idx, metrica in enumerate(["mae", "rmse", "r2"]):
        valores_por_tipo = {}
        for r in resultados:
            tipo = r["tipo"].upper()
            valores_por_tipo.setdefault(tipo, []).append(r[metrica])

        ax = ejes[idx]
        tipos = list(valores_por_tipo.keys())
        valores = [valores_por_tipo[t] for t in tipos]

        cajas = ax.boxplot(valores, labels=tipos, patch_artist=True)
        for c in cajas["boxes"]:
            c.set_facecolor("lightblue")

        ax.set_ylabel(metrica.upper())
        ax.set_title(f"Distribución {metrica.upper()} por modelo")
        ax.grid(alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "04_comparacion_modelos.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("✅ Gráfico comparativo de modelos guardado")

    fig, ax = plt.subplots(figsize=(10, 6))
    mae_por_fold = {}
    for r in resultados:
        clave = f"{r['tipo'].upper()}_F{r['fold']}"
        mae_por_fold[clave] = r["mae"]

    ax.bar(range(len(mae_por_fold)), mae_por_fold.values(), color="steelblue", alpha=0.7, edgecolor="black")
    ax.set_xticks(range(len(mae_por_fold)))
    ax.set_xticklabels(mae_por_fold.keys(), rotation=45, ha="right")
    ax.set_ylabel("MAE")
    ax.set_title("MAE por modelo y fold")
    ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "05_mae_por_fold.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("✅ Gráfico MAE por fold guardado\n")



def resumen_entrenamiento(resultados, variables_finales, df_modelo):
    print("=" * 80)
    print("RESUMEN GLOBAL DEL ENTRENAMIENTO")
    print("=" * 80 + "\n")

    estadisticas_tipo = {}
    for r in resultados:
        t = r["tipo"]
        estadisticas_tipo.setdefault(t, {"mae": [], "rmse": [], "r2": []})
        estadisticas_tipo[t]["mae"].append(r["mae"])
        estadisticas_tipo[t]["rmse"].append(r["rmse"])
        estadisticas_tipo[t]["r2"].append(r["r2"])

    print("Promedio por tipo de modelo (5 folds):\n")
    nombres_modelos = {
        "bosque": "Bosque aleatorio",
        "xgb": "XGBoost",
        "elastic": "ElasticNet",
    }

    for tipo, nombre in nombres_modelos.items():
        if tipo in estadisticas_tipo:
            mae_med = np.mean(estadisticas_tipo[tipo]["mae"])
            mae_std = np.std(estadisticas_tipo[tipo]["mae"])
            rmse_med = np.mean(estadisticas_tipo[tipo]["rmse"])
            rmse_std = np.std(estadisticas_tipo[tipo]["rmse"])
            r2_med = np.mean(estadisticas_tipo[tipo]["r2"])
            r2_std = np.std(estadisticas_tipo[tipo]["r2"])

            print(f"{nombre:15s}:")
            print(f"  MAE : {mae_med:.4f} ± {mae_std:.4f}")
            print(f"  RMSE: {rmse_med:.4f} ± {rmse_std:.4f}")
            print(f"  R2  : {r2_med:.4f} ± {r2_std:.4f}\n")

    print("Información general:")
    print(f"  Directorio salida : {DIRECTORIO_SALIDA}")
    print(f"  Directorio imágenes: {DIRECTORIO_IMAGENES}")
    print(f"  Directorio modelos : {DIRECTORIO_MODELOS}")
    print(f"  Total configuraciones evaluadas: {len(resultados)}")
    print(f"  Variables usadas: {len(variables_finales)}")
    print(f"  Filas de datos: {len(df_modelo)}")
    print(f"  Roles integrados: {'SÍ' if USAR_ROLES else 'NO'}")
    print(f"  ✅ Data Leakage: CONTROLADO (shift aplicado)")
    print("✅ Entrenamiento completado\n")



# ===========================
# FUNCIÓN PRINCIPAL
# ===========================
def main():
    print(f"\n{'=' * 80}")
    print(f"✅ MODO: TODAS LAS VARIABLES + SHIFT EN TRAINING")
    print(f"{'=' * 80}\n")
    
    # Cargar y analizar
    df = cargar_datos_porteros()

    columna_objetivo = "target_pf_next" if "target_pf_next" in df.columns else "puntosFantasy"
    analizar_target(df, columna_objetivo, DIRECTORIO_IMAGENES)

    # Enriquecer con roles si está disponible
    if USAR_ROLES:
        df = enriquecer_dataframe_con_roles(df, columna_roles="roles")
        resumen_roles(df)

    # Limpieza y preparación
    df = ordenar_datos(df)
    df = limpiar_variables_irrelevantes(df)
    df = limpiar_variables_redundantes(df)
    df = convertir_rachas(df)

    # Ingeniería de características COMPLETA
    df = crear_features_temporales(df, columna_objetivo)
    df = crear_features_derivadas(df, columna_objetivo)
    
    if USAR_ROLES:
        df = crear_features_interaccion_roles_v2(df, columna_objetivo)

    # VIF y variables finales
    variables_numericas = df.select_dtypes(include=[np.number]).columns.tolist()
    variables_numericas = [v for v in variables_numericas if v != columna_objetivo]
    calcular_vif(df, variables_numericas)

    variables_finales = definir_variables_finales(df, columna_objetivo)
    
    # ✅ CRÍTICO: Aplicar SHIFT aquí
    X, y, df_modelo = preparar_datos_modelo_con_shift(df, variables_finales, columna_objetivo)
    folds = generar_splits_temporales(X, n_splits=5)

    # Entrenamiento
    grid_rf, grid_xgb, grid_elastic = definir_grids()
    resultados = entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic)

    # Análisis final
    mejor_mae, mejor_r2 = seleccionar_mejores_modelos(resultados)
    guardar_resultados_csv(resultados)
    diagnostico_modelos(mejor_mae, mejor_r2, folds, X, y)
    explicabilidad_shap(mejor_mae, folds, X, [c for c in variables_finales if c in X.columns])
    visualizar_resultados(resultados)
    resumen_entrenamiento(resultados, variables_finales, df_modelo)


if __name__ == "__main__":
    main()
