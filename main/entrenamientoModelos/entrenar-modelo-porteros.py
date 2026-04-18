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
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_gk, seleccionar_features_por_correlacion
from common_trainer import BaseTrainer, GRID

DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS = BaseTrainer.build_output_dirs("portero")

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
        if hasattr(modelo, 'feature_importances_'):
            importances = modelo.feature_importances_
        elif hasattr(modelo, 'named_steps'):
            modelo_interno = modelo.named_steps.get('regresor', None)
            if modelo_interno and hasattr(modelo_interno, 'coef_'):
                importances = np.abs(modelo_interno.coef_)
            else:
                return None
        else:
            return None

        df_fi = pd.DataFrame({'feature': feature_names, 'importance': importances}).sort_values('importance', ascending=False)
        df_fi['importance'] = df_fi['importance'] / df_fi['importance'].sum()
        return df_fi
    except Exception as e:
        print(f" Error: {e}")
        return None


def visualizar_feature_importance(fi, titulo, nombre, top_n=20):
    BaseTrainer.visualizar_feature_importance(fi, titulo, nombre, DIRECTORIO_IMAGENES, top_n=top_n, text_offset=0.001)


def convertir_racha_a_numerico(racha):
    return BaseTrainer.convertir_racha_a_numerico(racha, mode='tuple')


def cargar_y_procesar_odds(df):
    return BaseTrainer.cargar_y_procesar_odds(df)


def cargar_datos():
    df = BaseTrainer.cargar_datos(CONFIG['archivo'], {'PT'}, low_memory=True)
    print(f" {len(df)} porteros (GK)\n")
    return df


def diagnosticar_y_limpiar(df):
    return BaseTrainer.diagnosticar_y_limpiar(
        df,
        columna_objetivo=CONFIG['columna_objetivo'],
        etiqueta_posicion='porteros',
        outlier_max=40,
        outlier_mode='replace_mode',
        reset_index=True,
    )


def preparar_basicos(df):
    a_eliminar = ["posicion", "Equipo_propio", "Equipo_rival", "TiroFallado_partido", "TiroPuerta_partido",
                  "Regates", "RegatesCompletados", "RegatesFallidos", "Conducciones", "DistanciaConduccion",
                  "MetrosAvanzadosConduccion", "ConduccionesProgresivas", "jornada", "jornada_anterior",
                  "Date", "home", "away", "Gol_partido", "Asist_partido", "xG_partido", "xAG", "Tiros", "target_pf_next"]
    df = df.drop(columns=[c for c in a_eliminar if c in df.columns], errors="ignore")
    
    if "racha5partidos" in df.columns:
        datos = df["racha5partidos"].apply(convertir_racha_a_numerico)
        df["racha_victorias"] = datos.apply(lambda x: x[0])
        df["racha_ratio_victorias"] = datos.apply(lambda x: x[3])
        df = df.drop(columns=["racha5partidos"])
    
    if "racha5partidos_rival" in df.columns:
        datos_rival = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
        df["racha_rival_victorias"] = datos_rival.apply(lambda x: x[0])
        df["racha_rival_ratio_victorias"] = datos_rival.apply(lambda x: x[3])
        df = df.drop(columns=["racha5partidos_rival"])
    
    print(" Limpieza completada\n")
    return df


def crear_features_gk(df):
    print(" Features GK...")
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    gk_specs = [
        ("porcentaje_paradas", 0.5, True, False, False, "save_pct"),
        ("psxg", 0, True, False, False, "psxg"),
        ("goles_en_contra", 0, False, False, False, "goles_contra"),
        ("pases_totales", 0, False, False, False, "passes"),
        ("pases_completados_pct", 0.5, False, False, False, "pass_comp_pct"),
    ]
    
    for col, default, lag, std, vol, prefix in gk_specs:
        df, _ = crear_features_temporales(df, col, vc, vl, None, default, lag, std, vol, prefix, True)
    
    return df


def crear_features_form(df):
    print(" Features Form...")
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df, _ = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, None, 0, True, True, True, "pf", True)
    
    return df


def crear_features_disponibilidad(df):
    print(" Features Disponibilidad...")
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    return BaseTrainer.crear_features_disponibilidad(
        df,
        ventana_corta=vc,
        ventana_larga=vl,
        ventana_extra=None,
        minutos_fill=0,
        titular_col='titular',
        titular_transform='numeric',
        return_feature_list=True,
    )


def crear_features_contexto(df):
    print(" Features Contexto...")
    return BaseTrainer.crear_features_contexto(df, include_fixture_from_p_home=True)


def crear_features_rival(df):
    print(" Features Rival...")
    return BaseTrainer.crear_features_rival(df)


def crear_features_avanzados(df):
    specs = [
        {'name': 'defensive_combo', 'cols': ['save_pct_roll5', 'psxg_roll5'], 'func': lambda d: d['save_pct_roll5'] / 100 * (1 / (d['psxg_roll5'] + 0.5)), 'clip': (0, 10)},
        {'name': 'form_ratio', 'cols': ['pf_roll5', 'pf_roll3'], 'func': lambda d: d['pf_roll3'] / (d['pf_roll5'] + 0.1), 'clip': (0.5, 2.0)},
        {'name': 'save_pct_power2', 'cols': ['save_pct_roll5'], 'func': lambda d: (d['save_pct_roll5'] ** 2) / 10000},
        {'name': 'minutes_form_combo', 'cols': ['minutes_pct_ewma5', 'pf_roll5'], 'func': lambda d: d['minutes_pct_ewma5'] * d['pf_roll5'] / 10},
        {'name': 'weak_opponent', 'cols': ['opp_gc_roll5'], 'func': lambda d: d['opp_gc_roll5'] / 2},
        {'name': 'momentum_factor', 'cols': ['pf_lag1', 'pf_roll5'], 'func': lambda d: d['pf_lag1'] / (d['pf_roll5'] + 1), 'clip': (0.5, 2.0)},
        {'name': 'total_strength', 'cols': ['save_pct_roll5', 'psxg_roll5'], 'func': lambda d: np.log1p(d['save_pct_roll5'] / 100 + (1 / (d['psxg_roll5'] + 0.5))), 'clip': (0, 5)},
        {'name': 'save_advantage', 'cols': ['psxg_roll5'], 'func': lambda d: 1 / (d['psxg_roll5'] + 0.5), 'clip': (0, 5)},
        {'name': 'availability_form', 'cols': ['minutes_pct_roll5', 'pf_ewma5'], 'func': lambda d: d['minutes_pct_roll5'] * d['pf_ewma5'] / 10},
    ]
    return BaseTrainer.crear_features_avanzados_desde_specs(df, "FEATURES AVANZADOS (PORTERO)", specs)


def integrar_roles(df):
    print(" Roles...")
    df = BaseTrainer.integrar_roles(df, position="PT", columna_objetivo=CONFIG['columna_objetivo'])
    print(" Roles OK\n")
    return df


def aplicar_mejoras(df):
    print(" Mejoras...")
    return BaseTrainer.aplicar_mejoras(
        df,
        position="PT",
        eliminar_features_fn=eliminar_features_ruido,
        crear_features_fantasy_fn=crear_features_fantasy_gk,
        titulo="MEJORAS (PORTERO)",
    )


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.02 - MAS AGRESIVO)")
    print("=" * 80 + "\n")
    
    features_validos, df_corr = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.02, verbose=True)
    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f" Features seleccionados: {len(features_validos)} (threshold: 0.02)\n")
    return X[features_validos], df_corr


def definir_variables_finales(df):
    variables = [
        "save_pct_roll5", "save_pct_ewma5",
        "psxg_roll5", "psxg_ewma5",
        "goles_contra_roll5",
        "pass_comp_pct_roll5", "pass_comp_pct_ewma5",
        "pf_roll5", "pf_ewma5",
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll5",
        "is_home",
        "opp_gf_roll5", "opp_gf_ewma5",
        "opp_gc_roll5", "opp_gc_ewma5",
        "opp_form_roll5", "opp_form_ewma5",
        "odds_prob_win",
        "odds_prob_loss",
        "odds_expected_goals_against",
        "odds_is_favored",
        "odds_market_confidence",
        "elite_paradas_interact", "porterias_cero_eficiencia",
        "num_roles_criticos",      
        "cs_probability", "cs_rate_recent", "cs_expected_points",
        "save_per_90_ewma5", "psxg_per_90_ewma5",
        "expected_gk_core_points",
        "defensive_combo", "form_ratio", "save_pct_power2", "minutes_form_combo",
        "weak_opponent", "momentum_factor", "total_strength", "save_advantage", "availability_form",
    ]
    
    return BaseTrainer.definir_variables_finales(df, variables, titulo="VARIABLES FINALES (PORTERO)")


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


class PorteroTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("portero")

    def run(self):
        BaseTrainer.print_banner("ENTRENAMIENTO PORTEROS V4 - REFACTORIZADO")
        
        df = cargar_datos()
        df = diagnosticar_y_limpiar(df)
        df = cargar_y_procesar_odds(df)
        df = preparar_basicos(df)
        
        BaseTrainer.print_section("INGENIERÍA DE FEATURES")
        df = crear_features_gk(df)
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
       
        if 'RF' in resultados:
            rf_metrics = resultados['RF']
            with open(DIRECTORIO_MODELOS / "best_model_RF.pkl", 'wb') as f:
                pickle.dump(rf_metrics['modelo'], f)
            
            with open(DIRECTORIO_MODELOS / "best_model_params_RF.json", 'w') as f:
                json.dump(rf_metrics['params'], f, indent=2)
            
            print(f"\n[RF] Modelo Random Forest guardado: {DIRECTORIO_MODELOS / 'best_model_RF.pkl'}")
            print(f"[RF] MAE: {rf_metrics['mae']:.4f}, RMSE: {rf_metrics['rmse']:.4f}, Spearman: {rf_metrics['spearman']:.4f}")

        BaseTrainer.print_banner("ENTRENAMIENTO PORTERO COMPLETADO")


def main():
    PorteroTrainer().run()


if __name__ == "__main__":
    main()
