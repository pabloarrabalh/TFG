import warnings
warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed.*", category=UserWarning)
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
import pickle
from scipy.stats import spearmanr

from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_mediocampista, seleccionar_features_por_correlacion
from common_trainer import BaseTrainer, GRID

DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS = BaseTrainer.build_output_dirs("mediocampista")

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'columna_objetivo': "puntos_fantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, 
                              default_value=0, crear_lag=False, crear_std=False, 
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
    df = BaseTrainer.cargar_datos(CONFIG['archivo'], {'MC'}, low_memory=False, empty_msg="❌ No se encontraron columnas de posición")
    print(f" {df.shape[0]} mediocampistas (MC) cargados\n")
    return df


def diagnosticar_y_limpiar(df):
    return BaseTrainer.diagnosticar_y_limpiar(
        df,
        columna_objetivo=CONFIG['columna_objetivo'],
        etiqueta_posicion='mediocampistas',
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
        racha_col = "racha5partidos_rival" if "racha5partidos_rival" in df.columns else "racha5partidos"
        if racha_col in df.columns:
            df[racha_col] = df[racha_col].apply(convertir_racha_a_numerico)
    
    if "racha5partidos_rival" in df.columns:
        df["racha5partidos_rival"] = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
    
    print("✅ Limpieza completada\n")
    return df


def cargar_y_procesar_odds(df):
    return BaseTrainer.cargar_y_procesar_odds(df)


def crear_features_mediocampistas_basicos(df):
    """Features mediocampistas: Pases, Regates, Conducciones, Creación de Juego"""
    print("=" * 80)
    print("FEATURES MEDIOCAMPISTAS")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    mc_specs = [
        ("pases_totales", 0, "passes"),
        ("pases_completados_pct", 50, "pass_comp_pct"),
        ("conducciones", 0, "dribbles"),
        ("conducciones_progresivas", 0, "prog_dribbles"),
        ("metros_avanzados_conduccion", 0, "prog_dist"),
        ("regates", 0, "dribble_attempts"),
        ("regates_completados", 0, "succ_dribbles"),
        ("regates_fallidos", 0, "failed_dribbles"),
        ("entradas", 0, "tackles"),
        ("intercepciones", 0, "intercepts"),
    ]
    
    for col, default, prefix in mc_specs:
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
        {'name': 'pass_efficiency', 'cols': ['passes_roll5', 'pass_comp_pct_roll5'], 'func': lambda d: d['passes_roll5'] * (d['pass_comp_pct_roll5'] / 100.0)},
        {'name': 'offensive_action', 'cols': ['dribble_attempts_roll5', 'prog_dribbles_roll5'], 'func': lambda d: d['dribble_attempts_roll5'] + d['prog_dribbles_roll5']},
        {'name': 'dribble_success_rate', 'cols': ['succ_dribbles_roll5', 'failed_dribbles_roll5'], 'func': lambda d: d['succ_dribbles_roll5'] / (d['succ_dribbles_roll5'] + d['failed_dribbles_roll5'] + 0.1)},
        {'name': 'defensive_participation', 'cols': ['tackles_roll5', 'intercepts_roll5'], 'func': lambda d: d['tackles_roll5'] + d['intercepts_roll5']},
        {'name': 'distance_per_dribble', 'cols': ['prog_dist_roll5', 'dribbles_roll5'], 'func': lambda d: d['prog_dist_roll5'] / (d['dribbles_roll5'] + 0.1)},
        {'name': 'availability_form', 'cols': ['minutes_pct_roll5', 'pf_roll5'], 'func': lambda d: d['minutes_pct_roll5'] * d['pf_roll5']},
        {'name': 'defensive_intensity', 'cols': ['tackles_roll5', 'pf_roll5'], 'func': lambda d: d['tackles_roll5'] / (d['pf_roll5'] + 0.1)},
        {'name': 'pass_productivity', 'cols': ['passes_roll5', 'pf_roll5'], 'func': lambda d: d['pf_roll5'] / (d['passes_roll5'] + 1)},
        {'name': 'creativity_index', 'cols': ['passes_roll5', 'dribble_success_rate'], 'func': lambda d: d['passes_roll5'] * (d['dribble_success_rate'] + 0.5)},
        {'name': 'offensive_ratio', 'cols': ['passes_roll5', 'defensive_participation'], 'func': lambda d: d['passes_roll5'] / (d['passes_roll5'] + d['defensive_participation'] + 0.1)},
        {'name': 'game_control', 'cols': ['passes_roll5', 'prog_dribbles_roll5', 'minutes_pct_roll5'], 'func': lambda d: (d['passes_roll5'] + d['prog_dribbles_roll5'] * 2) / (d['minutes_pct_roll5'] + 0.1)},
    ]
    return BaseTrainer.crear_features_avanzados_desde_specs(df, "FEATURES AVANZADOS (MEDIOCAMPISTAS)", specs)


def integrar_roles(df):
    print("=" * 80)
    print("ROLES FBREF")
    print("=" * 80)
    return BaseTrainer.integrar_roles(df, position="MC", columna_objetivo=CONFIG['columna_objetivo'])


def aplicar_mejoras(df):
    return BaseTrainer.aplicar_mejoras(
        df,
        position="MC",
        eliminar_features_fn=eliminar_features_ruido,
        crear_features_fantasy_fn=crear_features_fantasy_mediocampista,
        titulo="MEJORAS (MEDIOCAMPISTA)",
    )


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.05 - SELECTIVO)")
    print("=" * 80 + "\n")
    # Llamada defensiva a la función de selección: algunos entornos pueden
    # devolver directamente un DataFrame en lugar de (features, df_corr).
    resultado = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.05, verbose=True)
    print(f"[DEBUG] seleccionar_features_por_correlacion returned type: {type(resultado)}")

    if isinstance(resultado, tuple) and len(resultado) == 2:
        features_validos, df_corr = resultado
    else:
        try:
            df_corr = resultado if isinstance(resultado, pd.DataFrame) else pd.DataFrame(resultado)
        except Exception:
            df_corr = pd.DataFrame(columns=['feature', 'spearman', 'p_value', 'abs_spearman'])

        if 'abs_spearman' in df_corr.columns:
            features_validos = df_corr[df_corr['abs_spearman'] >= 0.05]['feature'].tolist()
        elif 'feature' in df_corr.columns:
            features_validos = df_corr['feature'].tolist()
        else:
            features_validos = []

    features_validos = [f for f in features_validos if f in X.columns]
    
    if len(features_validos) == 0:
        print(f"   WARNING: Sin features válidos! Usando todos los features")
        features_validos = list(X.columns)
    
    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f"\n {len(features_validos)} features seleccionados por correlación\n")
    return features_validos


def definir_variables_finales(df):
    variables = [
        "passes_roll5", "passes_ewma5",
        "pass_comp_pct_roll5", "pass_comp_pct_ewma5",
        "dribble_attempts_roll5", "dribble_attempts_ewma5",
        "succ_dribbles_roll5", "succ_dribbles_ewma5",
        "prog_dribbles_roll5", "prog_dribbles_ewma5",
        "prog_dist_roll5", "prog_dist_ewma5",
        "tackles_roll5", "tackles_ewma5",
        "intercepts_roll5", "intercepts_ewma5",
        "pf_roll5", "pf_ewma5",
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll3", "starter_pct_ewma3",
        "is_home",
        "odds_prob_win", "odds_prob_loss", "odds_expected_goals_against",
        "odds_is_favored", "odds_market_confidence",
        "opp_gf_roll5", "opp_gf_ewma5",
        "opp_gc_roll5", "opp_gc_ewma5",
        "opp_form_roll5", "opp_form_ewma5",
        "es_mediocampista_elite",
        "tiene_rol_mediocampista_core", "num_roles_criticos",
        "pass_efficiency", "offensive_action", "dribble_success_rate",
        "defensive_participation", "distance_per_dribble",
        "availability_form", "defensive_intensity", "pass_productivity",
    ]
    
    return BaseTrainer.definir_variables_finales(df, variables, titulo="VARIABLES FINALES (MEDIOCAMPISTA)")


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
        resultados_csv_name="resultados_gridsearch_mediocampista.csv",
        model_prefix="mc",
        elasticnet_estimator=ElasticNet(random_state=42, warm_start=True),
    )

    print("\n" + "=" * 80)
    print("RANKING MODELOS POR MAE")
    print("=" * 80)
    print(df_resultados.to_string(index=False))
    
    print("\n" + "=" * 80)
    print(" ENSEMBLE: Ridge + ElasticNet (Promedio ponderado)")
    print("=" * 80)
    
    pred_ridge_test = resultados_finales['Ridge']['modelo'].predict(X_test)
    pred_elastic_test = resultados_finales['ElasticNet']['modelo'].predict(X_test)
    
    mae_ridge = df_resultados[df_resultados['Model'] == 'Ridge']['MAE'].values[0]
    mae_elastic = df_resultados[df_resultados['Model'] == 'ElasticNet']['MAE'].values[0]
    
    peso_ridge = 1.0 / mae_ridge
    peso_elastic = 1.0 / mae_elastic
    total_peso = peso_ridge + peso_elastic
    peso_ridge /= total_peso
    peso_elastic /= total_peso
    
    pred_ensemble = (pred_ridge_test * peso_ridge + pred_elastic_test * peso_elastic)
    mae_ensemble = mean_absolute_error(y_test, pred_ensemble)
    rmse_ensemble = root_mean_squared_error(y_test, pred_ensemble)
    spearman_ensemble = spearmanr(y_test, pred_ensemble)[0]
    
    print(f"  Ridge weight:     {peso_ridge:.4f}")
    print(f"  ElasticNet weight: {peso_elastic:.4f}")
    print(f"  Ensemble MAE:  {mae_ensemble:.4f}, RMSE: {rmse_ensemble:.4f}, Spearman: {spearman_ensemble:.4f}\n")
    
    # Mejor modelo: compare ensemble vs individual
    best_mae = df_resultados.iloc[0]['MAE']
    ensemble_improvement = ((best_mae - mae_ensemble) / best_mae * 100)
    
    if mae_ensemble < best_mae:
        print(f" ENSEMBLE MEJORÓ +{ensemble_improvement:.2f}% vs mejor modelo individual!\n")
        # Guardar ensemble
        ridge_best = resultados_finales['Ridge']['modelo']
        elastic_best = resultados_finales['ElasticNet']['modelo']
        ensemble_data = {
            'ridge_model': ridge_best,
            'elastic_model': elastic_best,
            'ridge_weight': peso_ridge,
            'elastic_weight': peso_elastic,
            'mae': mae_ensemble
        }
        with open(DIRECTORIO_MODELOS / "ensemble_mc_ridge_elastic.pkl", "wb") as f:
            pickle.dump(ensemble_data, f)
    
    print(f"Modelos guardados en {DIRECTORIO_MODELOS}")
    print(f"Mejor modelo: {df_resultados.iloc[0]['Model']} (MAE: {df_resultados.iloc[0]['MAE']:.4f})\n")
    
    return df_resultados


class MediocampistaTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("mediocampista")

    def run(self):
        BaseTrainer.print_banner("ENTRENA MODELO DE PREDICCIÓN: MEDIOCAMPISTAS (MC)")
        
        df = cargar_datos()
        df = diagnosticar_y_limpiar(df)
        df = cargar_y_procesar_odds(df)
        df = preparar_basicos(df)
        df = crear_features_mediocampistas_basicos(df)
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
        
        BaseTrainer.print_section("SPLIT TRAIN/TEST (ESTRATIFICADO POR JUGADOR)")
        
        X = df[variables_finales].fillna(0).reset_index(drop=True)
        y = df[CONFIG['columna_objetivo']].fillna(0).reset_index(drop=True)
        
        split_idx = int(len(X) * (1 - CONFIG['test_size']))
        X_train, X_test = X[:split_idx].copy(), X[split_idx:].copy()
        y_train, y_test = y[:split_idx].copy(), y[split_idx:].copy()
        
        BaseTrainer.print_split_summary(X_train, X_test, y_train, y_test)
        print(f"  Features: {len(variables_finales)}\n")
        
        variables_finales = aplicar_feature_selection(X_train, y_train)
        X_train = X_train[variables_finales]
        X_test = X_test[variables_finales]
        
        print("=" * 80)
        print(" DIAGNÓSTICO ANTES DE ENTRENAR")
        print("=" * 80 + "\n")
        
        correlations = pd.DataFrame({
            'feature': variables_finales,
            'corr_with_target': [X_train[f].corr(y_train) for f in variables_finales]
        }).sort_values('corr_with_target', key=abs, ascending=False)
        
        print("Top 10 features por correlación con target:")
        print(correlations.head(10).to_string(index=False))
        print(f"\nPromedio correlación en valor absoluto: {correlations['corr_with_target'].abs().mean():.4f}")
        print(f"Std de correlación: {correlations['corr_with_target'].std():.4f}\n")
        
        print(f"Varianza de y_train: {y_train.var():.4f}")
        print(f"Varianza de y_test: {y_test.var():.4f}\n")
        
        entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables_finales)
        
        BaseTrainer.print_banner("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")


def main():
    MediocampistaTrainer().run()


if __name__ == "__main__":
    main()
