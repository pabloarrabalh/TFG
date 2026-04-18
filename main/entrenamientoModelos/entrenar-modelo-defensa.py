import warnings
warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed.*", category=UserWarning)
import pickle
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_defensivos, seleccionar_features_por_correlacion
from common_trainer import BaseTrainer, GRID

DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS = BaseTrainer.build_output_dirs("defensa")

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'columna_objetivo': "puntos_fantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, ventana_extra=None, 
                              default_value=0, crear_lag=True, crear_std=False, 
                              crear_volatility=False, prefix="", verbose=False):
    return BaseTrainer.crear_features_temporales(
        df,
        columna,
        ventana_corta,
        ventana_larga,
        ventana_extra=ventana_extra,
        default_value=default_value,
        crear_lag=crear_lag,
        crear_std=crear_std,
        crear_volatility=crear_volatility,
        prefix=prefix,
        verbose=verbose,
        return_feature_list=True,
    )


def extraer_feature_importance(modelo, X_ent, feature_names):
    try:
        importances = modelo.named_steps['regresor'].coef_ if hasattr(modelo, 'named_steps') else modelo.feature_importances_
        if not hasattr(importances, '__iter__'):
            return None
        df_fi = pd.DataFrame({'feature': feature_names, 'importance': np.abs(importances)})
        df_fi = df_fi.sort_values('importance', ascending=False)
        return df_fi.reset_index(drop=True)
    except:
        return None


def convertir_racha_a_numerico(racha):
    return BaseTrainer.convertir_racha_a_numerico(racha, mode='ratio')


def visualizar_feature_importance(fi, titulo, nombre, top_n=20):
    BaseTrainer.visualizar_feature_importance(fi, titulo, nombre, DIRECTORIO_IMAGENES, top_n=top_n, text_offset=0.0)


def cargar_datos():
    df = BaseTrainer.cargar_datos(CONFIG['archivo'], {'DF'}, low_memory=False)
    print(f" {df.shape[0]} defensas (DF) cargadas\n")
    return df


def diagnosticar_y_limpiar(df):
    return BaseTrainer.diagnosticar_y_limpiar(
        df,
        columna_objetivo=CONFIG['columna_objetivo'],
        etiqueta_posicion='defensas',
        outlier_max=30,
        outlier_mode='drop',
        reset_index=False,
    )


def preparar_basicos(df):
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival",
        "TiroFallado_partido", "TiroPuerta_partido",
        "Regates", "RegatesCompletados", "RegatesFallidos",
        "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
        "ConduccionesProgresivas",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "Gol_partido", "Asist_partido", "xG_partido", "xAG", "Tiros", "target_pf_next",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        df["racha_propio_ratio"] = df["racha5partidos"].apply(
            lambda x: x.count("W") / len(x) if isinstance(x, str) and len(x) > 0 else 0.0
        )
    
    if "racha5partidos_rival" in df.columns:
        df["racha_rival_ratio"] = df["racha5partidos_rival"].apply(
            lambda x: x.count("W") / len(x) if isinstance(x, str) and len(x) > 0 else 0.0
        )
    
    print(" Limpieza completada\n")
    return df


def cargar_y_procesar_odds(df):
    return BaseTrainer.cargar_y_procesar_odds(df)


def crear_features_defensivos_basicos(df):
    """Features defensivos: Tackles, Interceptions, Clearances, Duels"""
    print("=" * 80)
    print("FEATURES DEFENSIVOS")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    df_specs = [
        ("entradas", 0, "tackles"),
        ("intercepciones", 0, "intercepts"),
        ("despejes", 0, "clearances"),
        ("duelos", 0, "duels"),
        ("duelos_ganados", 0, "duels_won"),
        ("duelos_perdidos", 0, "duels_lost"),
        ("duelos_aereos", 0, "aerial_duels"),
        ("duelos_aereos_ganados", 0, "aerial_won"),
        ("duelos_aereos_perdidos", 0, "aerial_lost"),
        ("bloques", 0, "blocks"),
    ]
    
    for col, default, prefix in df_specs:
        if col in df.columns:
            df, _ = crear_features_temporales(df, col, vc, vl, None, crear_lag=True, default_value=default, prefix=prefix, verbose=True)
    
    return df


def crear_features_form(df):
    print("=" * 80)
    print("FEATURES FORM (PUNTOS FANTASY)")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df, _ = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, None, crear_lag=True, 
                                          default_value=1.0, prefix="pf", verbose=True)
    
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
        titular_transform='si_no',
        return_feature_list=True,
    )


def crear_features_contexto(df):
    if "local" in df.columns:
        df["local"] = (df["local"].astype(str).str.lower() == "si").astype(int)
    return BaseTrainer.crear_features_contexto(df, include_fixture_from_p_home=False)


def crear_features_rival(df):
    print("=" * 80)
    print("FEATURES RIVAL (HISTÓRICOS CON SHIFT - SIN LEAKAGE)")
    print("=" * 80)
    return BaseTrainer.crear_features_rival(df)


def crear_features_avanzados(df):
    specs = [
        {'name': 'defensive_efficiency', 'cols': ['tackles_roll5', 'duels_roll5'], 'func': lambda d: (d['tackles_roll5'] + d.get('intercepts_roll5', 0)) / (d['duels_roll5'] + 1)},
        {'name': 'defensive_activity', 'cols': ['tackles_roll5'], 'func': lambda d: d.get('tackles_roll5', 0) + d.get('intercepts_roll5', 0) + (d.get('clearances_roll5', 0) * 0.7)},
        {'name': 'duel_win_rate', 'cols': ['duels_won_roll5', 'duels_roll5'], 'func': lambda d: d['duels_won_roll5'] / (d['duels_roll5'] + 1e-6), 'clip': (0, 1)},
        {'name': 'aerial_duel_win_rate', 'cols': ['aerial_won_roll5', 'aerial_duels_roll5'], 'func': lambda d: d['aerial_won_roll5'] / (d['aerial_duels_roll5'] + 1e-6), 'clip': (0, 1)},
        {'name': 'form_ratio', 'cols': ['pf_roll5', 'pf_roll3'], 'func': lambda d: (d['pf_roll3'] + 0.1) / (d['pf_roll5'] + 0.1), 'clip': (0.5, 2.0)},
        {'name': 'minutes_form_combo', 'cols': ['minutes_pct_ewma5', 'pf_roll5'], 'func': lambda d: d['minutes_pct_ewma5'] * d['pf_roll5'] / 10},
        {'name': 'defensive_pressure', 'cols': ['tackles_roll5'], 'func': lambda d: (d['tackles_roll5'] + d.get('blocks_roll5', 0) * 0.8) / 5},
        {'name': 'duel_balance', 'cols': ['duels_won_roll5', 'duels_lost_roll5'], 'func': lambda d: d['duels_won_roll5'] - d.get('duels_lost_roll5', 0)},
        {'name': 'aerial_balance', 'cols': ['aerial_won_roll5', 'aerial_lost_roll5'], 'func': lambda d: d['aerial_won_roll5'] - d.get('aerial_lost_roll5', 0)},
        {'name': 'defensive_form_power', 'cols': ['defensive_activity', 'pf_roll5'], 'func': lambda d: (d['defensive_activity'] / 10) * (d['pf_roll5'] / 10)},
        {'name': 'defensive_consistency', 'cols': ['tackles_roll5', 'tackles_ewma5'], 'func': lambda d: 1 / ((d['tackles_roll5'] - d['tackles_ewma5']).abs() + 1)},
        {'name': 'availability_momentum', 'cols': ['minutes_pct_roll5', 'minutes_pct_roll3'], 'func': lambda d: d['minutes_pct_roll3'] / (d['minutes_pct_roll5'] + 0.1), 'clip': (0.5, 2.0)},
    ]
    return BaseTrainer.crear_features_avanzados_desde_specs(df, "FEATURES AVANZADOS (DEFENSIVOS)", specs)


def integrar_roles(df):
    print("=" * 80)
    print("ROLES (FBRef)")
    print("=" * 80)
    
    return BaseTrainer.integrar_roles(df, position="DF", columna_objetivo=CONFIG['columna_objetivo'])


def aplicar_mejoras(df):
    return BaseTrainer.aplicar_mejoras(
        df,
        position="DF",
        eliminar_features_fn=eliminar_features_ruido,
        crear_features_fantasy_fn=crear_features_fantasy_defensivos,
        titulo="MEJORAS DE FEATURES (DEFENSA)",
    )


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.02)")
    print("=" * 80 + "\n")
    
    features_validos, df_corr = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.02, verbose=True)
    
    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f" Features seleccionados: {len(features_validos)}\n")
    return X[features_validos], df_corr


def definir_variables_finales(df):
    variables = [
        "tackles_roll5", "tackles_ewma5",
        "intercepts_roll5", "intercepts_ewma5",
        "clearances_roll5", "clearances_ewma5",
        "duels_roll5", "duels_ewma5",
        "duels_won_roll5", "duels_won_ewma5",
        "duels_lost_roll5", "duels_lost_ewma5",
        "aerial_duels_roll5", "aerial_duels_ewma5",
        "aerial_won_roll5", "aerial_won_ewma5",
        "aerial_lost_roll5", "aerial_lost_ewma5",
        "blocks_roll5", "blocks_ewma5",
        "pf_roll5", "pf_ewma5",
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll5", "starter_pct_ewma5",
        "is_home",
        "odds_prob_win",
        "odds_prob_loss",
        "odds_expected_goals_against",
        "odds_is_favored",
        "odds_market_confidence",
        "opp_gf_roll5", "opp_gf_ewma5",      
        "opp_gc_roll5", "opp_gc_ewma5",        
        "opp_form_roll5", "opp_form_ewma5",     
        "elite_entradas_interact", 
        "elite_intercepciones_interact", 
        "elite_despejes_interact",
        "num_roles_criticos",     
        "def_actions_ewma5",
        "defensive_efficiency", 
        "defensive_activity", 
        "duel_win_rate",
        "aerial_duel_win_rate",
        "form_ratio", 
        "minutes_form_combo",
        "defensive_pressure",
        "duel_balance",
        "aerial_balance",
        "defensive_form_power",
        "defensive_consistency",
        "availability_momentum",
    ]
    
    return BaseTrainer.definir_variables_finales(df, variables, titulo="VARIABLES FINALES (DEFENSA)")


def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    resultados_finales, _ = BaseTrainer.entrenar_modelos_gridsearch(
        X_train,
        X_test,
        y_train,
        y_test,
        variables,
        DIRECTORIO_CSVS,
        DIRECTORIO_MODELOS,
        extraer_feature_importance,
        visualizar_feature_importance,
        resultados_csv_name="resultados_gridsearch_mejorado.csv",
        model_prefix="",
        elasticnet_estimator=ElasticNet(random_state=42),
    )
    print("Resultados guardados\n")
    return resultados_finales


class DefensaTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("defensa")

    def run(self):
        BaseTrainer.print_banner("ENTRENAMIENTO DEFENSAS - VERSIÓN MEJORADA")
        
        df = cargar_datos()
        df = diagnosticar_y_limpiar(df)
        df = cargar_y_procesar_odds(df)
        df = preparar_basicos(df)
        
        BaseTrainer.print_section("INGENIERÍA DE FEATURES")
        df = crear_features_defensivos_basicos(df)
        df = crear_features_form(df)
        df = crear_features_disponibilidad(df)
        df = crear_features_contexto(df)
        df = crear_features_rival(df)
        
        BaseTrainer.print_section("MEJORAS ADICIONALES")
        df = crear_features_avanzados(df)
        df = integrar_roles(df)
        df = aplicar_mejoras(df)
        
        variables = definir_variables_finales(df)
        df_train = df.dropna(subset=[CONFIG['columna_objetivo']])
        df_train = df_train[df_train[CONFIG['columna_objetivo']] > 0]
        X = df_train[variables].fillna(0)
        y = df_train[CONFIG['columna_objetivo']]
        
        print(f"Antes: {X.shape[1]} features")
        X, corr_analysis = aplicar_feature_selection(X, y)
        variables = X.columns.tolist()
        print(f"Después: {X.shape[1]} features\n")
        
        X_train, X_test, y_train, y_test = self.temporal_split(X, y, CONFIG['test_size'])
        
        BaseTrainer.print_split_summary(X_train, X_test)
        print()
        
        print("=" * 80)
        print("ENTRENAMIENTO GRIDSEARCH")
        print("=" * 80 + "\n")
        
        resultados = entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables)
        
        mejor_modelo = min(resultados.items(), key=lambda x: x[1]['mae'])
        mejor_nombre = mejor_modelo[0]
        mejor_metrics = mejor_modelo[1]
        
        print("RANKING MODELOS:\n")
        for i, (nombre, metrics) in enumerate(sorted(resultados.items(), key=lambda x: x[1]['mae']), 1):
            print(f"{i}. {nombre:12s} MAE: {metrics['mae']:.4f} RMSE: {metrics['rmse']:.4f} Spearman: {metrics['spearman']:.4f}")
        
        print("\n" + "=" * 80)
        print(f" MEJOR: {mejor_nombre}")
        print("=" * 80)
        print(f"MAE: {mejor_metrics['mae']:.4f}")
        print(f"RMSE: {mejor_metrics['rmse']:.4f}")
        print(f"Spearman: {mejor_metrics['spearman']:.4f}")
        print(f"CV Score: {mejor_metrics['cv_score']:.4f}")
        print("\nHiperparámetros:")
        for k, v in mejor_metrics['params'].items():
            print(f"  {k}: {v}")
        
        with open(DIRECTORIO_MODELOS / f"best_model_{mejor_nombre}.pkl", 'wb') as f:
            pickle.dump(mejor_metrics['modelo'], f)
        
        with open(DIRECTORIO_MODELOS / f"best_model_params_{mejor_nombre}.json", 'w') as f:
            json.dump(mejor_metrics['params'], f, indent=2)
        
        print(f"\n Modelo guardado: {DIRECTORIO_MODELOS / f'best_model_{mejor_nombre}.pkl'}")
        print(f" Parámetros: {DIRECTORIO_MODELOS / f'best_model_params_{mejor_nombre}.json'}")
        
        # Guardar Random Forest si existe
        if 'RF' in resultados:
            rf_metrics = resultados['RF']
            with open(DIRECTORIO_MODELOS / "best_model_RF.pkl", 'wb') as f:
                pickle.dump(rf_metrics['modelo'], f)
            
            with open(DIRECTORIO_MODELOS / "best_model_params_RF.json", 'w') as f:
                json.dump(rf_metrics['params'], f, indent=2)
            
            print(f"\n[RF] Modelo Random Forest guardado: {DIRECTORIO_MODELOS / 'best_model_RF.pkl'}")
            print(f"[RF] MAE: {rf_metrics['mae']:.4f}, RMSE: {rf_metrics['rmse']:.4f}, Spearman: {rf_metrics['spearman']:.4f}")

        BaseTrainer.print_banner("ENTRENAMIENTO DEFENSA COMPLETADO")


def main():
    DefensaTrainer().run()


if __name__ == "__main__":
    main()
