import warnings
import pickle
import json
from pathlib import Path
from functools import reduce
import operator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from role_enricher import enriquecer_dataframe_con_roles, crear_features_interaccion_roles
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_gk, seleccionar_features_por_correlacion

warnings.filterwarnings("ignore")

DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/portero")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"
DIRECTORIO_CSVS = DIRECTORIO_SALIDA / "csvs"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS]:
    d.mkdir(parents=True, exist_ok=True)

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features_MINIMO.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'ventana_extra': 7,
    'columna_objetivo': "puntosFantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, ventana_extra=7, 
                              default_value=0, crear_lag=True, crear_std=False, 
                              crear_volatility=False, prefix="", verbose=False):
    if columna not in df.columns:
        if verbose: print(f"⚠️ {columna} no existe")
        return df, []
    
    nombre_base = prefix if prefix else columna
    df[columna] = pd.to_numeric(df[columna], errors='coerce').fillna(default_value)
    features_nuevos = []
    
    for ventana, nombre_ventana in [(ventana_corta, "3"), (ventana_larga, "5"), (ventana_extra, "7")]:
        col_roll = f"{nombre_base}_roll{nombre_ventana}"
        df[col_roll] = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana, min_periods=1).mean()
        ).fillna(default_value)
        features_nuevos.append(col_roll)
        
        col_ewma = f"{nombre_base}_ewma{nombre_ventana}"
        df[col_ewma] = df.groupby("player")[columna].transform(
            lambda x: x.shift().ewm(span=ventana, adjust=False).mean()
        ).fillna(default_value)
        features_nuevos.append(col_ewma)
    
    if crear_lag:
        df[f"{nombre_base}_lag1"] = df.groupby("player")[columna].shift(1).fillna(default_value)
        df[f"{nombre_base}_lag2"] = df.groupby("player")[columna].shift(2).fillna(default_value)
        features_nuevos.extend([f"{nombre_base}_lag1", f"{nombre_base}_lag2"])
    
    if crear_std:
        df[f"{nombre_base}_std3"] = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).std()
        ).fillna(default_value)
        features_nuevos.append(f"{nombre_base}_std3")
    
    if crear_volatility:
        mean_temp = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).mean()
        ).fillna(1)
        std_temp = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).std()
        ).fillna(default_value)
        df[f"{nombre_base}_volatility3"] = (std_temp / (mean_temp + 1e-6)).fillna(default_value).replace([np.inf, -np.inf], default_value)
        features_nuevos.append(f"{nombre_base}_volatility3")
    
    if verbose:
        print(f"  ✅ {nombre_base}: {len(features_nuevos)} features")
    
    return df, features_nuevos


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
        print(f"⚠️ Error: {e}")
        return None


def visualizar_feature_importance(fi, titulo, nombre, top_n=20):
    if fi is None or len(fi) == 0:
        return
    
    df_top = fi.head(top_n)
    fig, ax = plt.subplots(figsize=(12, max(8, top_n * 0.4)))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df_top)))
    ax.barh(range(len(df_top)), df_top['importance'].values, color=colors)
    ax.set_yticks(range(len(df_top)))
    ax.set_yticklabels(df_top['feature'].values, fontsize=9)
    ax.set_xlabel('Importancia', fontsize=11, fontweight='bold')
    ax.set_title(titulo, fontsize=12, fontweight='bold', pad=15)
    ax.invert_yaxis()
    for i, v in enumerate(df_top['importance'].values):
        ax.text(v + 0.001, i, f'{v:.4f}', va='center', fontsize=8)
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / nombre, dpi=150, bbox_inches='tight')
    plt.close()


def convertir_racha_a_numerico(racha):
    if pd.isna(racha) or not isinstance(racha, str):
        return 0, 0, 0, 0.0
    victorias = racha.count("W")
    total = len(racha)
    return victorias, racha.count("D"), racha.count("L"), (victorias / total if total > 0 else 0.0)


def cargar_datos():
    print(f"📂 Cargando: {CONFIG['archivo']}")
    try:
        df = pd.read_csv(CONFIG['archivo'])
    except:
        df = pd.read_csv(CONFIG['archivo'], encoding='latin-1')
    
    print(f"ℹ️ {len(df)} registros, {len(df.columns)} columnas")
    
    posicion_cols = [c for c in df.columns if 'posicion' in c.lower()]
    if posicion_cols:
        df = df[df[posicion_cols[0]].str.upper() == "PT"].copy()
    
    print(f"✅ {len(df)} porteros (GK)\n")
    return df


def diagnosticar_y_limpiar(df):
    print("Limpiando datos...")
    filas_inicio = len(df)
    
    cols_necesarias = ['player', CONFIG['columna_objetivo'], 'Min_partido']
    if not all(c in df.columns for c in cols_necesarias):
        print(f"⚠️ Faltan: {[c for c in cols_necesarias if c not in df.columns]}")
    
    if 'jornada' in df.columns:
        df = df.sort_values(['player', 'jornada']).reset_index(drop=True)
    else:
        df = df.sort_values('player').reset_index(drop=True)
    
    df = df[df['Min_partido'] >= 10].copy()
    jugs_validos = df.groupby('player').size() >= 5
    df = df[df['player'].isin(jugs_validos[jugs_validos].index)]
    df = df[df[CONFIG['columna_objetivo']] <= 30].copy()
    
    nan_inicio = df.isnull().sum().sum()
    df = df.fillna(df.median(numeric_only=True))
    df = df.replace([np.inf, -np.inf], np.nan).fillna(df.median(numeric_only=True))
    
    print(f"✅ {filas_inicio} → {len(df)} filas ({100*len(df)/filas_inicio:.1f}%)\n")
    return df


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
    
    print("✅ Limpieza completada\n")
    return df


def crear_features_gk(df):
    print("📊 Features GK...")
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    gk_specs = [
        ("Porcentaje_paradas", 0.5, True, False, False, "save_pct"),
        ("PSxG", 0, True, False, False, "psxg"),
        ("Goles_en_contra", 0, False, False, False, "goles_contra"),
        ("DuelosAereosGanados", 0, False, False, False, "aerial_won"),
        ("Despejes", 0, False, False, False, "clearances"),
        ("Pases_Totales", 0, False, False, False, "passes"),
        ("Pases_Completados_Pct", 0.5, False, False, False, "pass_comp_pct"),
    ]
    
    for col, default, lag, std, vol, prefix in gk_specs:
        df, _ = crear_features_temporales(df, col, vc, vl, ve, default, lag, std, vol, prefix, True)
    
    return df


def crear_features_form(df):
    print("📊 Features Form...")
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df, _ = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, ve, 0, True, True, True, "pf", True)
    
    return df


def crear_features_disponibilidad(df):
    print("📊 Features Disponibilidad...")
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    df["Min_partido"] = pd.to_numeric(df["Min_partido"], errors='coerce').fillna(0)
    df["minutes_pct_temp"] = (df["Min_partido"] / 90).fillna(0).clip(0, 1)
    df, _ = crear_features_temporales(df, "minutes_pct_temp", vc, vl, crear_lag=False, default_value=0, prefix="minutes_pct", verbose=True)
    
    if "Titular" in df.columns:
        df, _ = crear_features_temporales(df, "Titular", vc, vl, crear_lag=False, default_value=0, prefix="starter_pct", verbose=True)
    
    df = df.drop(columns=["minutes_pct_temp"])
    return df


def crear_features_contexto(df):
    print("📊 Features Contexto...")
    if "local" in df.columns:
        df["local"] = pd.to_numeric(df["local"], errors='coerce').fillna(0)
        df["is_home"] = (df["local"] == 1).astype(int)
    else:
        df["is_home"] = 0
    
    if "p_home" in df.columns:
        df["p_home"] = pd.to_numeric(df["p_home"], errors='coerce').fillna(0.5)
        df["fixture_difficulty_home"] = (1 - df["p_home"]).clip(0, 1)
        df["fixture_difficulty_away"] = df["p_home"].clip(0, 1)
    
    return df


def crear_features_rival(df):
    print("📊 Features Rival...")
    vl = CONFIG['ventana_larga']
    
    rival_specs = [
        ("shots_rival_partido", 0, "opp_shots"),
        ("gc", 0, "opp_gc"),
        ("racha_rival_ratio_victorias", 0.5, "opp_form"),
    ]
    
    for col, default, prefix in rival_specs:
        df, _ = crear_features_temporales(df, col, ventana_larga=vl, crear_lag=False, default_value=default, prefix=prefix, verbose=True)
    
    return df


def crear_features_probabilisticas(df):
    print("📊 Features Probabilísticas...")
    prob_specs = [("p_win_propio", 0.5, "p_win"), ("p_loss_propio", 0.5, "p_loss"), ("p_over25", 0.5, "p_over25")]
    
    for col, default, prefix in prob_specs:
        df, _ = crear_features_temporales(df, col, ventana_corta=5, ventana_larga=10, crear_lag=False, 
                                         default_value=default, prefix=prefix, verbose=True)
    
    return df


def integrar_roles(df):
    print("📊 Roles...")
    df = enriquecer_dataframe_con_roles(df, position="PT", columna_roles="roles")
    df = crear_features_interaccion_roles(df, position="PT", columna_objetivo=CONFIG['columna_objetivo'])
    print("✅ Roles OK\n")
    return df


def aplicar_mejoras(df):
    print("📊 Mejoras...")
    antes = len(df.columns)
    df = eliminar_features_ruido(df, position="PT", verbose=True)
    print(f"Sin ruido: {antes} → {len(df.columns)}")
    
    antes = len(df.columns)
    df = crear_features_fantasy_gk(df, verbose=True)
    print(f"Finales: {antes} → {len(df.columns)}\n")
    return df


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print("📊 SELECCIÓN FEATURES")
    print("=" * 80 + "\n")
    
    features_validos, df_corr = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.03, verbose=True)
    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f"✅ Correlaciones guardadas\n")
    return X[features_validos], df_corr


def definir_variables_finales(df):
    print("=" * 80)
    print("VARIABLES FINALES")
    print("=" * 80)
    
    variables = [
        "save_pct_ewma3", "save_pct_ewma5", "save_pct_roll5", "save_pct_lag1",
        "psxg_ewma3", "psxg_ewma5", "psxg_roll5", "psxg_lag1",
        "goles_contra_ewma3", "goles_contra_ewma5", "goles_contra_roll5",
        "aerial_won_ewma5", "aerial_won_roll5",
        "clearances_ewma3", "clearances_ewma5", "clearances_roll5",
        "passes_ewma5", "pass_comp_pct_ewma5",
        "pf_roll3", "pf_ewma3", "pf_roll5", "pf_ewma5", "pf_roll7", "pf_volatility3", "pf_lag1", "pf_lag2",
        "minutes_pct_roll3", "minutes_pct_roll5", "minutes_pct_ewma3", "minutes_pct_ewma5",
        "starter_pct_roll5", "starter_pct_ewma5",
        "is_home", "fixture_difficulty_home", "fixture_difficulty_away",
        "opp_shots_roll5", "opp_shots_ewma5", "opp_gc_ewma5", "opp_gc_roll5", "opp_form_roll5",
        "p_win_propio_ewma5", "p_loss_propio_ewma5", "p_over25_ewma5",
    ]
    
    fantasy_gk_vars = ["cs_probability", "cs_rate_recent", "cs_expected_points", "save_per_90", 
                       "save_per_90_ewma5", "psxg_per_90", "psxg_per_90_ewma5", "expected_gk_core_points"]
    variables.extend([v for v in fantasy_gk_vars if v in df.columns])
    
    roles_vars = ["elite_saves_interact", "elite_distribution_interact", "elite_handling_interact",
                  "score_roles_normalizado", "num_roles_criticos", "tiene_rol_gk_core", "score_gk"]
    variables.extend([v for v in roles_vars if v in df.columns])
    
    variables = list(set(v for v in variables if v in df.columns))
    
    print(f"✅ {len(variables)} variables\n")
    return variables


def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    resultados_finales = {}
    lista_resultados = []
    
    print("🌲 Random Forest...")
    rf_params = {
        'n_estimators': [200, 300, 400, 500],
        'max_depth': [10, 20, 30, None],
        'min_samples_split': [2, 3, 5, 7],
        'min_samples_leaf': [1, 2, 3, 4, 5],
        'max_features': ['sqrt', 'log2', None]
    }
    rf_num_configs = reduce(operator.mul, [len(v) for v in rf_params.values()])
    print(f"  🔢 {rf_num_configs} configs")
    
    rf_gs = GridSearchCV(RandomForestRegressor(random_state=42, n_jobs=-1), rf_params, cv=3, 
                         scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    rf_gs.fit(X_train, y_train)
    rf_best = rf_gs.best_estimator_
    pred_rf = rf_best.predict(X_test)
    mae_rf, rmse_rf, spearman_rf = mean_absolute_error(y_test, pred_rf), root_mean_squared_error(y_test, pred_rf), spearmanr(y_test, pred_rf)[0]
    
    print(f"  ✅ MAE: {mae_rf:.4f}, RMSE: {rmse_rf:.4f}, Spearman: {spearman_rf:.4f}\n")
    resultados_finales['RF'] = {'mae': mae_rf, 'rmse': rmse_rf, 'spearman': spearman_rf, 'modelo': rf_best, 'params': rf_gs.best_params_, 'cv_score': rf_gs.best_score_}
    lista_resultados.append({'Model': 'RF', 'MAE': mae_rf, 'RMSE': rmse_rf, 'Spearman': spearman_rf, 'Best_Params': str(rf_gs.best_params_)})
    
    fi_rf = extraer_feature_importance(rf_best, X_train, variables)
    if fi_rf is not None:
        fi_rf.to_csv(DIRECTORIO_CSVS / "feature_importance_rf.csv", index=False)
        visualizar_feature_importance(fi_rf, "Random Forest - Top 20", "01_feature_importance_rf.png", 20)
    
    print("🚀 XGBoost...")
    xgb_params = {
        'max_depth': [5, 7],
        'learning_rate': [0.1, 0.15],
        'n_estimators': [300, 500],
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9],
        'gamma': [0.25, 0.5],
        'min_child_weight': [1, 3, 5],
        'reg_alpha': [0.05, 0.1],
        'reg_lambda': [1.0, 2.0]
    }
    xgb_num_configs = reduce(operator.mul, [len(v) for v in xgb_params.values()])
    print(f"  🔢 {xgb_num_configs} configs")
    
    xgb_gs = GridSearchCV(XGBRegressor(random_state=42, n_jobs=-1), xgb_params, cv=3, 
                          scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    xgb_gs.fit(X_train, y_train)
    xgb_best = xgb_gs.best_estimator_
    pred_xgb = xgb_best.predict(X_test)
    mae_xgb, rmse_xgb, spearman_xgb = mean_absolute_error(y_test, pred_xgb), root_mean_squared_error(y_test, pred_xgb), spearmanr(y_test, pred_xgb)[0]
    
    print(f"  ✅ MAE: {mae_xgb:.4f}, RMSE: {rmse_xgb:.4f}, Spearman: {spearman_xgb:.4f}\n")
    resultados_finales['XGB'] = {'mae': mae_xgb, 'rmse': rmse_xgb, 'spearman': spearman_xgb, 'modelo': xgb_best, 'params': xgb_gs.best_params_, 'cv_score': xgb_gs.best_score_}
    lista_resultados.append({'Model': 'XGB', 'MAE': mae_xgb, 'RMSE': rmse_xgb, 'Spearman': spearman_xgb, 'Best_Params': str(xgb_gs.best_params_)})
    
    fi_xgb = extraer_feature_importance(xgb_best, X_train, variables)
    if fi_xgb is not None:
        fi_xgb.to_csv(DIRECTORIO_CSVS / "feature_importance_xgb.csv", index=False)
        visualizar_feature_importance(fi_xgb, "XGBoost - Top 20", "02_feature_importance_xgb.png", 20)
    
    print("📏 Ridge...")
    ridge_pipeline = Pipeline([('scaler', StandardScaler()), ('regresor', Ridge())])
    ridge_params = {'regresor__alpha': [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0]}
    ridge_num_configs = len(ridge_params['regresor__alpha'])
    print(f"  🔢 {ridge_num_configs} configs")
    
    ridge_gs = GridSearchCV(ridge_pipeline, ridge_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    ridge_gs.fit(X_train, y_train)
    ridge_best = ridge_gs.best_estimator_
    pred_ridge = ridge_best.predict(X_test)
    mae_ridge, rmse_ridge, spearman_ridge = mean_absolute_error(y_test, pred_ridge), root_mean_squared_error(y_test, pred_ridge), spearmanr(y_test, pred_ridge)[0]
    
    print(f"  ✅ MAE: {mae_ridge:.4f}, RMSE: {rmse_ridge:.4f}, Spearman: {spearman_ridge:.4f}\n")
    resultados_finales['Ridge'] = {'mae': mae_ridge, 'rmse': rmse_ridge, 'spearman': spearman_ridge, 'modelo': ridge_best, 'params': ridge_gs.best_params_, 'cv_score': ridge_gs.best_score_}
    lista_resultados.append({'Model': 'Ridge', 'MAE': mae_ridge, 'RMSE': rmse_ridge, 'Spearman': spearman_ridge, 'Best_Params': str(ridge_gs.best_params_)})
    
    fi_ridge = extraer_feature_importance(ridge_best, X_train, variables)
    if fi_ridge is not None:
        fi_ridge.to_csv(DIRECTORIO_CSVS / "feature_importance_ridge.csv", index=False)
        visualizar_feature_importance(fi_ridge, "Ridge - Top 20", "03_feature_importance_ridge.png", 20)
    
    print("🔗 ElasticNet...")
    elastic_pipeline = Pipeline([('scaler', StandardScaler()), ('regresor', ElasticNet(random_state=42))])
    elastic_params = {
        'regresor__alpha': [0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
        'regresor__l1_ratio': [0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
        'regresor__max_iter': [5000, 10000, 15000],
        'regresor__tol': [1e-3, 1e-4, 1e-5]
    }
    elastic_num_configs = reduce(operator.mul, [len(v) for v in elastic_params.values()])
    print(f"  🔢 {elastic_num_configs} configs")
    
    elastic_gs = GridSearchCV(elastic_pipeline, elastic_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    elastic_gs.fit(X_train, y_train)
    elastic_best = elastic_gs.best_estimator_
    pred_elastic = elastic_best.predict(X_test)
    mae_elastic, rmse_elastic, spearman_elastic = mean_absolute_error(y_test, pred_elastic), root_mean_squared_error(y_test, pred_elastic), spearmanr(y_test, pred_elastic)[0]
    
    print(f"  ✅ MAE: {mae_elastic:.4f}, RMSE: {rmse_elastic:.4f}, Spearman: {spearman_elastic:.4f}\n")
    resultados_finales['ElasticNet'] = {'mae': mae_elastic, 'rmse': rmse_elastic, 'spearman': spearman_elastic, 'modelo': elastic_best, 'params': elastic_gs.best_params_, 'cv_score': elastic_gs.best_score_}
    lista_resultados.append({'Model': 'ElasticNet', 'MAE': mae_elastic, 'RMSE': rmse_elastic, 'Spearman': spearman_elastic, 'Best_Params': str(elastic_gs.best_params_)})
    
    fi_elastic = extraer_feature_importance(elastic_best, X_train, variables)
    if fi_elastic is not None:
        fi_elastic.to_csv(DIRECTORIO_CSVS / "feature_importance_elastic.csv", index=False)
        visualizar_feature_importance(fi_elastic, "ElasticNet - Top 20", "04_feature_importance_elastic.png", 20)
    
    pd.DataFrame(lista_resultados).to_csv(DIRECTORIO_CSVS / "resultados_gridsearch_mejorado.csv", index=False)
    print(f"✅ Resultados guardados\n")
    return resultados_finales


def main():
    print("\n" + "=" * 80)
    print("🚀 ENTRENAMIENTO PORTEROS V4 - REFACTORIZADO")
    print("=" * 80 + "\n")
    
    df = cargar_datos()
    df = diagnosticar_y_limpiar(df)
    df = preparar_basicos(df)
    
    print("=" * 80)
    print("📊 INGENIERÍA DE FEATURES")
    print("=" * 80 + "\n")
    df = crear_features_gk(df)
    df = crear_features_form(df)
    df = crear_features_disponibilidad(df)
    df = crear_features_contexto(df)
    df = crear_features_rival(df)
    df = crear_features_probabilisticas(df)
    
    print("=" * 80)
    print("📊 MEJORAS ADICIONALES")
    print("=" * 80 + "\n")
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
    
    split_idx = int(len(X) * (1 - CONFIG['test_size']))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}\n")
    
    print("=" * 80)
    print("📊 ENTRENAMIENTO GRIDSEARCH")
    print("=" * 80 + "\n")
    
    resultados = entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables)
    
    mejor_modelo = min(resultados.items(), key=lambda x: x[1]['mae'])
    mejor_nombre = mejor_modelo[0]
    mejor_metrics = mejor_modelo[1]
    
    print("RANKING MODELOS:\n")
    for i, (nombre, metrics) in enumerate(sorted(resultados.items(), key=lambda x: x[1]['mae']), 1):
        print(f"{i}. {nombre:12s} MAE: {metrics['mae']:.4f} RMSE: {metrics['rmse']:.4f} Spearman: {metrics['spearman']:.4f}")
    
    print("\n" + "=" * 80)
    print(f"🏆 MEJOR: {mejor_nombre}")
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
    
    print(f"\n✅ Modelo guardado: {DIRECTORIO_MODELOS / f'best_model_{mejor_nombre}.pkl'}")
    print(f"✅ Parámetros: {DIRECTORIO_MODELOS / f'best_model_params_{mejor_nombre}.json'}")


if __name__ == "__main__":
    main()
