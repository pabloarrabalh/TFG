import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.utils.parallel")
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
import pickle

from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_delantero, seleccionar_features_por_correlacion
from common_trainer import BaseTrainer, GRID

DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS = BaseTrainer.build_output_dirs("delantero")

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'columna_objetivo': "puntos_fantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, 
                              default_value=0, crear_lag=True, crear_std=False, 
                              crear_volatility=False, prefix="", verbose=False):
    return BaseTrainer.crear_features_temporales(
        df,
        columna,
        ventana_corta,
        ventana_larga,
        ventana_extra=None,
        default_value=default_value,
        crear_lag=crear_lag,
        crear_std=crear_std,
        crear_volatility=crear_volatility,
        prefix=prefix,
        verbose=verbose,
        return_feature_list=False,
    )


def extraer_feature_importance(modelo, X_ent, feature_names):
    try:
        if hasattr(modelo, 'feature_importances_'):
            fi = pd.DataFrame({
                'feature': feature_names,
                'importance': modelo.feature_importances_
            }).sort_values('importance', ascending=False)
            return fi
        else:
            return None
    except:
        return None


def convertir_racha_a_numerico(racha):
    return BaseTrainer.convertir_racha_a_numerico(racha, mode='ratio')


def visualizar_feature_importance(fi, titulo, nombre, top_n=20):
    BaseTrainer.visualizar_feature_importance(fi, titulo, nombre, DIRECTORIO_IMAGENES, top_n=top_n, text_offset=0.0)


def cargar_datos():
    df = BaseTrainer.cargar_datos(CONFIG['archivo'], {'DT', 'ST'}, low_memory=False, empty_msg="❌ No se encontraron columnas de posición")
    print(f" {df.shape[0]} delanteros (ST) cargados\n")
    return df


def diagnosticar_y_limpiar(df):
    return BaseTrainer.diagnosticar_y_limpiar(
        df,
        columna_objetivo=CONFIG['columna_objetivo'],
        etiqueta_posicion='delanteros',
        outlier_max=30,
        outlier_mode='drop',
        reset_index=True,
    )


def preparar_basicos(df):
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival",
        "TiroFallado_partido", "TiroPuerta_partido",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "target_pf_next",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        df["racha5partidos"] = df["racha5partidos"].apply(convertir_racha_a_numerico)
    
    if "racha5partidos_rival" in df.columns:
        df["racha5partidos_rival"] = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
    
    print("✅ Limpieza completada\n")
    return df


def cargar_y_procesar_odds(df):
    return BaseTrainer.cargar_y_procesar_odds(df)


def crear_features_delanteros_basicos(df):
    """Features delanteros: Goles, xG, Tiros, Regates, Pases clave"""
    print("=" * 80)
    print("FEATURES DELANTEROS (OFENSIVOS)")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    st_specs = [
        ("gol_partido", 0, "goals"),
        ("xg_partido", 0, "xg"),
        ("tiros", 0, "shots"),
        ("tiro_puerta_partido", 0, "shots_on_target"),
        ("regates", 0, "dribbles"),
        ("regates_completados", 0, "succ_dribbles"),
        ("conducciones_progresivas", 0, "prog_dribbles"),
        ("metros_avanzados_conduccion", 0, "prog_dist"),
        ("pases_clave", 0, "key_passes"),
        ("entradas", 0, "tackles"),
    ]
    
    for col, default, prefix in st_specs:
        df = crear_features_temporales(df, col, vc, vl, default_value=default, prefix=prefix, verbose=True)
    
    return df


def crear_features_form(df):
    print("=" * 80)
    print("FEATURES FORM (PUNTOS FANTASY)")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, crear_lag=True, prefix="pf", verbose=True)
    
    return df


def crear_features_disponibilidad(df):
    print("=" * 80)
    print("FEATURES DISPONIBILIDAD")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    return BaseTrainer.crear_features_disponibilidad(
        df,
        ventana_corta=vc,
        ventana_larga=vl,
        ventana_extra=None,
        minutos_fill=45,
        titular_col='titular',
        titular_transform='float',
        return_feature_list=False,
    )


def crear_features_contexto(df):
    return BaseTrainer.crear_features_contexto(df, include_fixture_from_p_home=False)


def crear_features_rival(df):
    print("=" * 80)
    print("FEATURES RIVAL (HISTÓRICOS CON SHIFT - SIN LEAKAGE)")
    print("=" * 80)
    return BaseTrainer.crear_features_rival(df)


def crear_features_avanzados(df):
    specs = [
        {'name': 'shot_efficiency', 'cols': ['xg_roll5', 'goals_roll5'], 'func': lambda d: d['goals_roll5'] / (d['xg_roll5'] + 0.1)},
        {'name': 'shot_accuracy', 'cols': ['shots_on_target_roll5', 'shots_roll5'], 'func': lambda d: d['shots_on_target_roll5'] / (d['shots_roll5'] + 0.1)},
        {'name': 'offensive_threat', 'cols': ['shots_roll5', 'succ_dribbles_roll5'], 'func': lambda d: d['shots_roll5'] + d['succ_dribbles_roll5']},
        {'name': 'creativity_index', 'cols': ['key_passes_roll5'], 'func': lambda d: d['key_passes_roll5']},
        {'name': 'availability_threat', 'cols': ['minutes_pct_roll5', 'shots_roll5'], 'func': lambda d: d['minutes_pct_roll5'] * d['shots_roll5']},
        {'name': 'offensive_form', 'cols': ['goals_roll5', 'xg_roll5'], 'func': lambda d: d['goals_roll5'] + d['xg_roll5']},
        {'name': 'progressive_pressure', 'cols': ['prog_dribbles_roll5'], 'func': lambda d: d['prog_dribbles_roll5']},
        {'name': 'goal_productivity', 'cols': ['goals_roll5', 'shots_roll5'], 'func': lambda d: d['goals_roll5'] / (d['shots_roll5'] + 0.1)},
    ]
    return BaseTrainer.crear_features_avanzados_desde_specs(df, "FEATURES AVANZADOS (DELANTEROS)", specs)


def integrar_roles(df):
    print("=" * 80)
    print("ROLES FBREF")
    print("=" * 80)
    return BaseTrainer.integrar_roles(df, position="DT", columna_objetivo=CONFIG['columna_objetivo'])


def aplicar_mejoras(df):
    return BaseTrainer.aplicar_mejoras(
        df,
        position="DT",
        eliminar_features_fn=eliminar_features_ruido,
        crear_features_fantasy_fn=crear_features_fantasy_delantero,
        titulo="MEJORAS (DELANTERO)",
    )


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.02 - MAS AGRESIVO)")
    print("=" * 80 + "\n")
    
    resultado = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.02, verbose=True)
    print(f"[DEBUG] seleccionar_features_por_correlacion returned type: {type(resultado)}")

    if isinstance(resultado, tuple) and len(resultado) == 2:
        features_validos, df_corr = resultado
    else:
        try:
            df_corr = resultado if isinstance(resultado, pd.DataFrame) else pd.DataFrame(resultado)
        except Exception:
            df_corr = pd.DataFrame(columns=['feature', 'spearman', 'p_value', 'abs_spearman'])

        if 'abs_spearman' in df_corr.columns:
            features_validos = df_corr[df_corr['abs_spearman'] >= 0.02]['feature'].tolist()
        else:
            features_validos = []

    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f"\n✅ {len(features_validos)} features seleccionados por correlación\n")
    return features_validos


def definir_variables_finales(df):
    variables = [
        "goals_roll5", "goals_ewma5",
        "xg_roll5", "xg_ewma5",
        "shots_roll5", "shots_ewma5",
        "shots_on_target_roll5", "shots_on_target_ewma5",
        "dribbles_roll5", "dribbles_ewma5",
        "succ_dribbles_roll5", "succ_dribbles_ewma5",
        "prog_dribbles_roll5", "prog_dribbles_ewma5",
        "prog_dist_roll5", "prog_dist_ewma5",
        "key_passes_roll5", "key_passes_ewma5",
        "pf_roll5", "pf_ewma5",
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll3", "starter_pct_ewma3",
        "is_home",
        "odds_prob_win", "odds_prob_loss", "odds_expected_goals_against",
        "odds_is_favored", "odds_market_confidence",
        "opp_gf_roll5", "opp_gf_ewma5",
        "opp_gc_roll5", "opp_gc_ewma5",
        "opp_form_roll5", "opp_form_ewma5",
        "tiene_rol_delantero_core",  
        "shot_efficiency", "shot_accuracy", "offensive_threat",
        "creativity_index", "availability_threat", "offensive_form",
        "progressive_pressure", "goal_productivity",
    ]
    
    return BaseTrainer.definir_variables_finales(df, variables, titulo="VARIABLES FINALES (DELANTERO)")


def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    resultados_finales, df_resultados = BaseTrainer.entrenar_modelos_gridsearch(
        X_train,
        X_test,
        y_train,
        y_test,
        variables,
        DIRECTORIO_CSVS,
        DIRECTORIO_MODELOS,
        extraer_feature_importance,
        visualizar_feature_importance,
        resultados_csv_name="resultados_gridsearch_delantero.csv",
        model_prefix="delantero",
        elasticnet_estimator=ElasticNet(random_state=42),
    )

    print("\n" + "=" * 80)
    print("RANKING MODELOS POR MAE")
    print("=" * 80)
    print(df_resultados.to_string(index=False))
    print(f"\n✅ Modelos guardados en {DIRECTORIO_MODELOS}")
    print(f"✅ Mejor modelo: {df_resultados.iloc[0]['Model']} (MAE: {df_resultados.iloc[0]['MAE']:.4f})\n")

    return df_resultados


class DelanteroTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("delantero")

    def run(self):
        BaseTrainer.print_banner("ENTRENA MODELO DE PREDICCIÓN: DELANTEROS (ST)")
        
        df = cargar_datos()
        df = diagnosticar_y_limpiar(df)
        df = cargar_y_procesar_odds(df)
        df = preparar_basicos(df)
        df = crear_features_delanteros_basicos(df)
        df = crear_features_form(df)
        df = crear_features_disponibilidad(df)
        df = crear_features_contexto(df)
        df = crear_features_rival(df)
        df = crear_features_avanzados(df)
        df = integrar_roles(df)
        df = aplicar_mejoras(df)
        variables_finales = definir_variables_finales(df)
        
        variables_finales = [v for v in variables_finales if v in df.columns]
        print(f"Variables finales disponibles: {len(variables_finales)}\n")
        
        BaseTrainer.print_section("SPLIT TRAIN/TEST")
        
        X = df[variables_finales].fillna(0)
        y = df[CONFIG['columna_objetivo']].fillna(0)
        
        split_idx = int(len(X) * (1 - CONFIG['test_size']))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        BaseTrainer.print_split_summary(X_train, X_test)
        print(f"Features: {len(variables_finales)}\n")
        
        variables_finales = aplicar_feature_selection(X_train, y_train)
        X_train = X_train[variables_finales]
        X_test = X_test[variables_finales]
        
        entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables_finales)
        
        BaseTrainer.print_banner(" ENTRENAMIENTO COMPLETADO EXITOSAMENTE")


def main():
    DelanteroTrainer().run()


if __name__ == "__main__":
    main()
