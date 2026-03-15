from __future__ import annotations

from abc import ABC, abstractmethod
from functools import reduce
import operator
from pathlib import Path
import re
import warnings
from typing import Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import GridSearchCV

from role_enricher import enriquecer_dataframe_con_roles, crear_features_interaccion_roles


GRID = {
    'RF': {
        'n_estimators': [200, 300, 400],
        'max_depth': [10, 20, 30],
        'min_samples_split': [2, 3, 5, 7],
        'min_samples_leaf': [2, 3, 4, 5],
        'max_features': ['sqrt', 'log2'],
    },
    'XGB': {
        'max_depth': [5, 7],
        'learning_rate': [0.1, 0.15],
        'n_estimators': [300, 500],
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9],
        'gamma': [0.25, 0.5],
        'min_child_weight': [1, 3, 5],
        'reg_alpha': [0.05, 0.1],
        'reg_lambda': [1.0, 2.0],
    },
    'Ridge': {
        'regresor__alpha': [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0],
    },
    'ElasticNet': {
        'regresor__alpha': [0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
        'regresor__l1_ratio': [0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
        'regresor__max_iter': [5000, 10000, 15000],
        'regresor__tol': [1e-3, 1e-4, 1e-5],
    },
}


class BaseTrainer(ABC):
    """Base class for position trainers.

    It centralizes small reusable runtime utilities while each concrete trainer
    keeps its position-specific pipeline unchanged.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @staticmethod
    def ensure_directories(paths: Iterable[Path]) -> None:
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def temporal_split(X, y, test_size: float):
        split_idx = int(len(X) * (1 - test_size))
        return X.iloc[:split_idx], X.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]

    @staticmethod
    def print_banner(title):
        print("\n" + "=" * 80)
        print(title)
        print("=" * 80 + "\n")

    @staticmethod
    def print_section(title):
        print("=" * 80)
        print(title)
        print("=" * 80 + "\n")

    @staticmethod
    def print_split_summary(X_train, X_test, y_train=None, y_test=None):
        print(f"Train: {len(X_train)} muestras")
        print(f"Test: {len(X_test)} muestras")
        if y_train is not None and y_test is not None:
            print(f"Ratio puntos: train u={y_train.mean():.2f}, test u={y_test.mean():.2f}")

    @staticmethod
    def build_output_dirs(subdir: str):
        directorio_salida = Path(f"csv/csvGenerados/entrenamiento/{subdir}")
        directorio_imagenes = directorio_salida / "imagenes"
        directorio_modelos = directorio_salida / "modelos"
        directorio_csvs = directorio_salida / "csvs"
        BaseTrainer.ensure_directories([directorio_salida, directorio_imagenes, directorio_modelos, directorio_csvs])
        return directorio_salida, directorio_imagenes, directorio_modelos, directorio_csvs

    @staticmethod
    def convertir_racha_a_numerico(racha, mode='ratio'):
        if pd.isna(racha) or not isinstance(racha, str):
            return (0, 0, 0, 0.0) if mode == 'tuple' else 0.0
        victorias = racha.count("W")
        total = len(racha)
        ratio = (victorias / total if total > 0 else 0.0)
        if mode == 'tuple':
            return victorias, racha.count("D"), racha.count("L"), ratio
        return ratio

    @staticmethod
    def visualizar_feature_importance(fi, titulo, nombre, output_dir, top_n=20, text_offset=0.0):
        if fi is None or len(fi) == 0:
            return
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        # Sanitize file names defensively for Windows filesystems.
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', str(nombre)).strip(' .')
        if not safe_name:
            safe_name = "feature_importance.png"

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
            ax.text(v + text_offset, i, f' {v:.4f}', va='center', fontsize=8)
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        out_file = output_path / safe_name
        try:
            plt.savefig(out_file, dpi=150, bbox_inches='tight')
        except OSError as e:
            fallback = output_path / "feature_importance_fallback.png"
            print(f"WARN Error guardando imagen en {out_file}: {e}. Reintentando en {fallback}")
            plt.savefig(fallback, dpi=150, bbox_inches='tight')
        plt.close()

    @staticmethod
    def crear_features_temporales(
        df,
        columna,
        ventana_corta=3,
        ventana_larga=5,
        ventana_extra=None,
        default_value=0,
        crear_lag=True,
        crear_std=False,
        crear_volatility=False,
        prefix="",
        verbose=False,
        return_feature_list=False,
    ):
        if columna not in df.columns:
            if verbose:
                print(f"[WARN] {columna} no existe")
            return (df, []) if return_feature_list else df

        nombre_base = prefix if prefix else columna
        df[columna] = pd.to_numeric(df[columna], errors='coerce').fillna(default_value)
        features_nuevos = []
        nuevas_cols = {}

        ventanas = [(ventana_corta, str(ventana_corta)), (ventana_larga, str(ventana_larga))]
        if ventana_extra is not None:
            ventanas.append((ventana_extra, str(ventana_extra)))

        for ventana, nombre_ventana in ventanas:
            col_roll = f"{nombre_base}_roll{nombre_ventana}"
            col_ewma = f"{nombre_base}_ewma{nombre_ventana}"
            nuevas_cols[col_roll] = df.groupby("player")[columna].transform(
                lambda x: x.shift().rolling(ventana, min_periods=1).mean()
            ).fillna(default_value)
            nuevas_cols[col_ewma] = df.groupby("player")[columna].transform(
                lambda x: x.shift().ewm(span=ventana, adjust=False).mean()
            ).fillna(default_value)
            features_nuevos.extend([col_roll, col_ewma])

        if crear_lag:
            nuevas_cols[f"{nombre_base}_lag1"] = df.groupby("player")[columna].shift(1).fillna(default_value)
            if ventana_extra is not None:
                nuevas_cols[f"{nombre_base}_lag2"] = df.groupby("player")[columna].shift(2).fillna(default_value)
                features_nuevos.extend([f"{nombre_base}_lag1", f"{nombre_base}_lag2"])
            else:
                features_nuevos.append(f"{nombre_base}_lag1")

        if crear_std:
            suffix = "3" if ventana_extra is not None else "5"
            col_std = f"{nombre_base}_std{suffix}"
            nuevas_cols[col_std] = df.groupby("player")[columna].transform(
                lambda x: x.shift().rolling(ventana_corta if ventana_extra is not None else ventana_larga, min_periods=1).std()
            ).fillna(default_value)
            features_nuevos.append(col_std)

        if crear_volatility:
            suffix = "3" if ventana_extra is not None else "5"
            col_vol = f"{nombre_base}_volatility{suffix}"
            mean_temp = df.groupby("player")[columna].transform(
                lambda x: x.shift().rolling(ventana_corta if ventana_extra is not None else ventana_larga, min_periods=1).mean()
            ).fillna(1)
            std_temp = df.groupby("player")[columna].transform(
                lambda x: x.shift().rolling(ventana_corta if ventana_extra is not None else ventana_larga, min_periods=1).std()
            ).fillna(default_value)
            nuevas_cols[col_vol] = (std_temp / (mean_temp + 1e-6)).fillna(default_value).replace([np.inf, -np.inf], default_value)
            features_nuevos.append(col_vol)

        if nuevas_cols:
            df = pd.concat([df, pd.DataFrame(nuevas_cols, index=df.index)], axis=1)

        if verbose:
            if return_feature_list:
                print(f"   {nombre_base}: {len(features_nuevos)} features")
            else:
                print(f"   OK {nombre_base}: features temporales creadas")

        return (df, features_nuevos) if return_feature_list else df

    @staticmethod
    def cargar_datos(config_archivo, position_values, low_memory=False, empty_msg="WARN: No hay columnas de posicion, usando todo el dataset"):
        print(f"Cargando: {config_archivo}")
        try:
            df = pd.read_csv(config_archivo, low_memory=low_memory)
        except Exception:
            df = pd.read_csv(config_archivo, encoding='latin-1', low_memory=low_memory)

        print(f"INFO Total registros: {len(df)}")
        print(f"INFO Total columnas: {len(df.columns)}")
        posicion_cols = [col for col in df.columns if 'posicion' in col.lower()]
        print(f"INFO Columnas de posicion encontradas: {posicion_cols}")

        if len(posicion_cols) == 0:
            print(empty_msg)
            return df.copy()

        col = posicion_cols[0]
        values_upper = {v.upper() for v in position_values}
        if col == 'posicion':
            mask = df[col].astype(str).str.upper().isin(values_upper)
        else:
            mask = df[col].astype(str).str.upper().isin(values_upper)
        return df[mask].copy()

    @staticmethod
    def diagnosticar_y_limpiar(df, columna_objetivo, etiqueta_posicion, outlier_max=30, outlier_mode='drop', reset_index=False):
        filas_inicio = len(df)
        print("\n1) Verificando columnas necesarias...")
        cols_necesarias = ['player', columna_objetivo, 'min_partido']
        cols_faltantes = [c for c in cols_necesarias if c not in df.columns]
        if cols_faltantes:
            print(f"   WARN Columnas faltantes: {cols_faltantes}")
        else:
            print("   OK Todas las columnas necesarias presentes")

        print("\n2) Ordenando por jugador + jornada...")
        if 'jornada' in df.columns:
            df = df.sort_values(['player', 'jornada'])
        else:
            df = df.sort_values('player')
        if reset_index:
            df = df.reset_index(drop=True)
        print("   OK Datos ordenados temporalmente")

        print("\n3) Eliminando registros con <10 minutos...")
        muy_poco_antes = (df['min_partido'] < 10).sum()
        df = df[df['min_partido'] >= 10].copy()
        print(f"   OK Eliminados {muy_poco_antes} registros")

        print(f"\n4) Filtrando {etiqueta_posicion} con <5 partidos...")
        jugs_validos = df.groupby('player').size() >= 5
        jugs_validos = jugs_validos[jugs_validos].index
        antes_jugs = len(df)
        df = df[df['player'].isin(jugs_validos)]
        print(f"   OK Eliminados {antes_jugs - len(df)} registros")

        print("\n5) Eliminando outliers extremos...")
        target_vals = pd.to_numeric(df[columna_objetivo], errors='coerce')
        outliers_pf = (target_vals > outlier_max).sum()
        if outlier_mode == 'replace_mode' and outliers_pf > 0:
            moda = target_vals[target_vals <= outlier_max].mode()
            valor_moda = float(moda.iloc[0]) if len(moda) else outlier_max
            df.loc[target_vals > outlier_max, columna_objetivo] = valor_moda
            print(f"   OK Reemplazados {outliers_pf} outliers por moda={valor_moda:.2f}")
        else:
            df = df[target_vals <= outlier_max].copy()
            print(f"   OK Eliminados {outliers_pf} registros")

        print("\n6) Limpiando valores NaN e infinitos...")
        nan_inicio = df.isnull().sum().sum()
        df = df.fillna(df.median(numeric_only=True))
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(df.median(numeric_only=True))
        print(f"   OK Procesados {nan_inicio} valores NaN")

        print(f"\nTotal: {filas_inicio} -> {len(df)} filas ({100*len(df)/filas_inicio:.1f}%)\n")
        return df

    @staticmethod
    def cargar_y_procesar_odds(df):
        print("[CHART] Integrando ODDS de mercado...")

        df['odds_prob_win'] = 0.33
        df['odds_prob_loss'] = 0.33
        df['odds_expected_goals_against'] = 0.33
        df['odds_is_favored'] = 0
        df['odds_market_confidence'] = 0.33

        try:
            odds_df = pd.read_csv('csv/csvDescargados/live_odds_cache.csv')
            print(f"  [OK] live_odds_cache.csv: {odds_df.shape}")

            if 'jornada' not in odds_df.columns or 'jornada' not in df.columns:
                print("  [WARN] No existe columna 'jornada'")
                return df
            if 'local' not in df.columns:
                print("  [WARN] No existe columna 'local'")
                return df
            if 'equipo_propio' not in df.columns or 'equipo_rival' not in df.columns:
                print("  [WARN] No existen columnas de equipos")
                return df

            def normalizar_equipo(nombre):
                if pd.isna(nombre):
                    return None
                nombre = str(nombre).lower().strip()
                mapeos = {
                    'ath bilbao': 'athletic bilbao',
                    'ath madrid': 'atletico madrid',
                    'vallecano': 'rayo',
                    'ca osasuna': 'osasuna',
                }
                return mapeos.get(nombre, nombre)

            df['equipo_propio_norm'] = df['equipo_propio'].apply(normalizar_equipo)
            df['equipo_rival_norm'] = df['equipo_rival'].apply(normalizar_equipo)
            odds_df['home_norm'] = odds_df['home'].apply(normalizar_equipo)
            odds_df['away_norm'] = odds_df['away'].apply(normalizar_equipo)

            local_df = df[df['local'] == 1].copy()
            local_df['_src_idx'] = local_df.index
            local_merged = local_df.merge(
                odds_df[['jornada', 'home_norm', 'p_home', 'p_away', 'p_draw']],
                left_on=['jornada', 'equipo_propio_norm'],
                right_on=['jornada', 'home_norm'],
                how='left',
            )
            mask_local = local_merged['p_home'].notna()
            local_idx = local_merged.loc[mask_local, '_src_idx'].values
            df.loc[local_idx, 'odds_prob_win'] = local_merged.loc[mask_local, 'p_home'].values
            df.loc[local_idx, 'odds_prob_loss'] = local_merged.loc[mask_local, 'p_away'].values
            df.loc[local_idx, 'odds_expected_goals_against'] = (local_merged.loc[mask_local, 'p_away'].values * 2.5)
            df.loc[local_idx, 'odds_is_favored'] = (local_merged.loc[mask_local, 'p_home'] > local_merged.loc[mask_local, 'p_away']).astype(int).values
            local_probs = local_merged.loc[mask_local, ['p_home', 'p_draw', 'p_away']]
            df.loc[local_idx, 'odds_market_confidence'] = (local_probs.max(axis=1) - local_probs.min(axis=1)).values

            away_df = df[df['local'] == 0].copy()
            away_df['_src_idx'] = away_df.index
            away_merged = away_df.merge(
                odds_df[['jornada', 'away_norm', 'p_home', 'p_away', 'p_draw']],
                left_on=['jornada', 'equipo_rival_norm'],
                right_on=['jornada', 'away_norm'],
                how='left',
            )
            mask_away = away_merged['p_away'].notna()
            away_idx = away_merged.loc[mask_away, '_src_idx'].values
            df.loc[away_idx, 'odds_prob_win'] = away_merged.loc[mask_away, 'p_away'].values
            df.loc[away_idx, 'odds_prob_loss'] = away_merged.loc[mask_away, 'p_home'].values
            df.loc[away_idx, 'odds_expected_goals_against'] = (away_merged.loc[mask_away, 'p_home'].values * 2.5)
            df.loc[away_idx, 'odds_is_favored'] = (away_merged.loc[mask_away, 'p_away'] > away_merged.loc[mask_away, 'p_home']).astype(int).values
            away_probs = away_merged.loc[mask_away, ['p_home', 'p_draw', 'p_away']]
            df.loc[away_idx, 'odds_market_confidence'] = (away_probs.max(axis=1) - away_probs.min(axis=1)).values

            local_count = mask_local.sum()
            away_count = mask_away.sum()
            print(f"  [OK] Matched {local_count} local + {away_count} away = {local_count + away_count} records\n")
            return df.drop(columns=['equipo_propio_norm', 'equipo_rival_norm'], errors='ignore')
        except Exception as e:
            print(f"  [ERROR] {e}")
            return df

    @staticmethod
    def crear_features_contexto(df, include_fixture_from_p_home=False):
        print("=" * 80)
        print("FEATURES CONTEXTO")
        print("=" * 80)

        if "local" in df.columns:
            local_num = pd.to_numeric(df["local"], errors='coerce').fillna(0)
            df["is_home"] = (local_num == 1).astype(int)
            if include_fixture_from_p_home:
                df["local"] = local_num
        else:
            df["is_home"] = 0

        if include_fixture_from_p_home and "p_home" in df.columns:
            p_home = pd.to_numeric(df["p_home"], errors='coerce').fillna(0.5)
            df["p_home"] = p_home
            df["fixture_difficulty_home"] = (1 - p_home).clip(0, 1)
            df["fixture_difficulty_away"] = p_home.clip(0, 1)

        print("OK Home/Away (is_home)\n")
        return df

    @staticmethod
    def crear_features_avanzados_desde_specs(df, titulo, specs):
        print("=" * 80)
        print(titulo)
        print("=" * 80)

        df = df.copy()
        nuevos_features = []

        for spec in specs:
            name = spec['name']
            required_cols = spec.get('cols', [])
            if required_cols and not all(c in df.columns for c in required_cols):
                continue

            values = spec['func'](df)
            values = pd.to_numeric(values, errors='coerce').replace([np.inf, -np.inf], np.nan).fillna(0)

            clip_bounds = spec.get('clip', None)
            if clip_bounds is not None:
                values = values.clip(clip_bounds[0], clip_bounds[1])

            df[name] = values
            nuevos_features.append(name)

        df = df.fillna(0).replace([np.inf, -np.inf], 0)
        print(f"   {len(nuevos_features)} features avanzados agregados\n")
        return df

    @staticmethod
    def crear_features_disponibilidad(
        df,
        ventana_corta,
        ventana_larga,
        ventana_extra=None,
        minutos_fill=45,
        titular_col='titular',
        titular_transform='float',
        return_feature_list=False,
    ):
        df = df.copy()
        df["min_partido"] = pd.to_numeric(df["min_partido"], errors='coerce').fillna(minutos_fill)
        df["minutes_pct_temp"] = (df["min_partido"] / 90).fillna(0).clip(0, 1)

        tmp = BaseTrainer.crear_features_temporales(
            df,
            "minutes_pct_temp",
            ventana_corta,
            ventana_larga,
            ventana_extra,
            crear_lag=False,
            default_value=0,
            prefix="minutes_pct",
            verbose=True,
            return_feature_list=return_feature_list,
        )
        df = tmp[0] if return_feature_list else tmp

        if titular_col in df.columns:
            if titular_transform == 'si_no':
                df["starter_temp"] = (df[titular_col] == "Si").astype(int)
                starter_col = "starter_temp"
            elif titular_transform == 'identity':
                starter_col = titular_col
            else:
                df["starter_temp"] = df[titular_col].astype(float)
                starter_col = "starter_temp"

            tmp = BaseTrainer.crear_features_temporales(
                df,
                starter_col,
                ventana_corta,
                ventana_larga,
                ventana_extra,
                crear_lag=False,
                default_value=0,
                prefix="starter_pct",
                verbose=True,
                return_feature_list=return_feature_list,
            )
            df = tmp[0] if return_feature_list else tmp

        return df.drop(columns=["minutes_pct_temp"], errors='ignore')

    @staticmethod
    def crear_features_rival(df):
        print("FEATURES RIVAL (HISTÓRICOS CON SHIFT - SIN LEAKAGE)")
        if "gf_rival" in df.columns and "gc_rival" in df.columns:
            gf = pd.to_numeric(df["gf_rival"], errors='coerce').fillna(0)
            gc = pd.to_numeric(df["gc_rival"], errors='coerce').fillna(0)
            total = (gf + gc).clip(lower=1)
            df["opp_form_raw"] = np.clip(((gf - gc) / total + 1) / 2, 0.0, 1.0)
            print("   Calculando opp_form desde GF/GC reales del rival")
        else:
            print("   ERROR: sin columnas gf_rival/gc_rival en el CSV")
            df["opp_form_raw"] = 0.5

        rival_specs = [
            ("gf_rival", 0.0, "opp_gf"),
            ("gc_rival", 0.0, "opp_gc"),
            ("opp_form_raw", 0.5, "opp_form"),
        ]
        for col, default, prefix in rival_specs:
            if col not in df.columns:
                continue
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)
            if df[col].nunique() <= 1:
                print(f"   AVISO: {col} es constante ({df[col].iloc[0]:.3f})")

            if "equipo_propio" in df.columns:
                df[f'{col}_shifted'] = df.groupby('equipo_propio')[col].shift(1)
            else:
                df[f'{col}_shifted'] = df[col].shift(1)
            df[f'{col}_shifted'] = df[f'{col}_shifted'].fillna(default)

            df[f'{prefix}_roll3'] = df[f'{col}_shifted'].rolling(3, min_periods=1).mean()
            df[f'{prefix}_ewma3'] = df[f'{col}_shifted'].ewm(span=3, adjust=False).mean()
            df[f'{prefix}_roll5'] = df[f'{col}_shifted'].rolling(5, min_periods=1).mean()
            df[f'{prefix}_ewma5'] = df[f'{col}_shifted'].ewm(span=5, adjust=False).mean()

            df = df.drop(columns=[f'{col}_shifted'], errors='ignore')
            print(f"   OK {col} -> {prefix}_roll3/5 + ewma3/5 (shift por equipo, sin leakage)")
        print()
        return df

    @staticmethod
    def integrar_roles(df, position, columna_objetivo):
        print("ROLES FBREF")
        df = enriquecer_dataframe_con_roles(df, position=position, columna_roles="roles")
        df = crear_features_interaccion_roles(df, position=position, columna_objetivo=columna_objetivo)
        print(" Roles OK\n")
        return df

    @staticmethod
    def aplicar_mejoras(df, position, eliminar_features_fn, crear_features_fantasy_fn, titulo="MEJORAS"):
        print("=" * 80)
        print(titulo)
        print("=" * 80)

        antes = len(df.columns)
        df = eliminar_features_fn(df, position=position, verbose=True)
        print(f"Sin ruido: {antes} -> {len(df.columns)}")

        antes = len(df.columns)
        df = crear_features_fantasy_fn(df, verbose=True)
        print(f"Finales: {antes} -> {len(df.columns)}\n")
        return df

    @staticmethod
    def definir_variables_finales(df, variables_candidatas, titulo="VARIABLES FINALES"):
        print("=" * 80)
        print(titulo)
        print("=" * 80 + "\n")
        variables = [v for v in variables_candidatas if v in df.columns]
        print(f"Total variables finales: {len(variables)}\n")
        return variables

    @staticmethod
    def grid_size(param_grid: dict) -> int:
        return reduce(operator.mul, [len(v) for v in param_grid.values()]) if param_grid else 0

    @staticmethod
    def run_gridsearch(model_name, estimator, param_grid, X_train, y_train, X_test, y_test):
        gs = GridSearchCV(
            estimator,
            param_grid,
            cv=5,
            scoring='neg_mean_absolute_error',
            n_jobs=-1,
            verbose=1,
        )
        gs.fit(X_train, y_train)
        best_model = gs.best_estimator_
        preds = best_model.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        rmse = root_mean_squared_error(y_test, preds)
        spearman = spearmanr(y_test, preds)[0]

        result = {
            'mae': mae,
            'rmse': rmse,
            'spearman': spearman,
            'modelo': best_model,
            'params': gs.best_params_,
            'cv_score': gs.best_score_,
        }
        row = {
            'Model': model_name,
            'MAE': mae,
            'RMSE': rmse,
            'Spearman': spearman,
            'Best_Params': str(gs.best_params_),
        }
        return result, row, gs

    @staticmethod
    def persist_feature_importance(fi, directorio_csvs, csv_name, plotter, titulo, image_name, top_n=20):
        if fi is None:
            return
        fi.to_csv(directorio_csvs / csv_name, index=False)
        plotter(fi, titulo, image_name, top_n)

    @staticmethod
    def entrenar_modelos_gridsearch(
        X_train,
        X_test,
        y_train,
        y_test,
        variables,
        directorio_csvs,
        directorio_modelos,
        extraer_feature_importance_fn,
        visualizar_feature_importance_fn,
        resultados_csv_name,
        model_prefix="",
        elasticnet_estimator=None,
    ):
        resultados_finales = {}
        lista_resultados = []

        print(" Random Forest...")
        rf_params = {**GRID['RF']}
        print(f"   {BaseTrainer.grid_size(rf_params)} configs")
        rf_result, rf_row, rf_gs = BaseTrainer.run_gridsearch(
            'RF',
            __import__('sklearn.ensemble', fromlist=['RandomForestRegressor']).RandomForestRegressor(random_state=42, n_jobs=-1),
            rf_params,
            X_train,
            y_train,
            X_test,
            y_test,
        )
        print(f"   MAE: {rf_result['mae']:.4f}, RMSE: {rf_result['rmse']:.4f}, Spearman: {rf_result['spearman']:.4f}\n")
        resultados_finales['RF'] = rf_result
        lista_resultados.append(rf_row)
        fi_rf = extraer_feature_importance_fn(rf_result['modelo'], X_train, variables)
        BaseTrainer.persist_feature_importance(fi_rf, directorio_csvs, "feature_importance_rf.csv", visualizar_feature_importance_fn, "Random Forest - Top 20", "01_feature_importance_rf.png", 20)

        print(" XGBoost...")
        xgb_params = {**GRID['XGB']}
        print(f"   {BaseTrainer.grid_size(xgb_params)} configs")
        rf_cls = __import__('xgboost', fromlist=['XGBRegressor']).XGBRegressor
        xgb_result, xgb_row, xgb_gs = BaseTrainer.run_gridsearch(
            'XGB',
            rf_cls(random_state=42, n_jobs=-1),
            xgb_params,
            X_train,
            y_train,
            X_test,
            y_test,
        )
        print(f"   MAE: {xgb_result['mae']:.4f}, RMSE: {xgb_result['rmse']:.4f}, Spearman: {xgb_result['spearman']:.4f}\n")
        resultados_finales['XGB'] = xgb_result
        lista_resultados.append(xgb_row)
        fi_xgb = extraer_feature_importance_fn(xgb_result['modelo'], X_train, variables)
        BaseTrainer.persist_feature_importance(fi_xgb, directorio_csvs, "feature_importance_xgb.csv", visualizar_feature_importance_fn, "XGBoost - Top 20", "02_feature_importance_xgb.png", 20)

        print(" Ridge...")
        ridge_pipeline = __import__('sklearn.pipeline', fromlist=['Pipeline']).Pipeline([
            ('scaler', __import__('sklearn.preprocessing', fromlist=['StandardScaler']).StandardScaler()),
            ('regresor', __import__('sklearn.linear_model', fromlist=['Ridge']).Ridge()),
        ])
        ridge_params = {**GRID['Ridge']}
        print(f"   {len(ridge_params['regresor__alpha'])} configs")
        ridge_result, ridge_row, ridge_gs = BaseTrainer.run_gridsearch(
            'Ridge', ridge_pipeline, ridge_params, X_train, y_train, X_test, y_test
        )
        print(f"   MAE: {ridge_result['mae']:.4f}, RMSE: {ridge_result['rmse']:.4f}, Spearman: {ridge_result['spearman']:.4f}\n")
        resultados_finales['Ridge'] = ridge_result
        lista_resultados.append(ridge_row)
        fi_ridge = extraer_feature_importance_fn(ridge_result['modelo'], X_train, variables)
        BaseTrainer.persist_feature_importance(fi_ridge, directorio_csvs, "feature_importance_ridge.csv", visualizar_feature_importance_fn, "Ridge - Top 20", "03_feature_importance_ridge.png", 20)

        print(" ElasticNet...")
        if elasticnet_estimator is None:
            elasticnet_estimator = __import__('sklearn.linear_model', fromlist=['ElasticNet']).ElasticNet(random_state=42)
        elastic_pipeline = __import__('sklearn.pipeline', fromlist=['Pipeline']).Pipeline([
            ('scaler', __import__('sklearn.preprocessing', fromlist=['StandardScaler']).StandardScaler()),
            ('regresor', elasticnet_estimator),
        ])
        elastic_params = {**GRID['ElasticNet']}
        print(f"   {BaseTrainer.grid_size(elastic_params)} configs")
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=ConvergenceWarning,
                module=r"sklearn\.linear_model\._coordinate_descent",
            )
            elastic_result, elastic_row, elastic_gs = BaseTrainer.run_gridsearch(
                'ElasticNet', elastic_pipeline, elastic_params, X_train, y_train, X_test, y_test
            )
        print(f"   MAE: {elastic_result['mae']:.4f}, RMSE: {elastic_result['rmse']:.4f}, Spearman: {elastic_result['spearman']:.4f}\n")
        resultados_finales['ElasticNet'] = elastic_result
        lista_resultados.append(elastic_row)
        fi_elastic = extraer_feature_importance_fn(elastic_result['modelo'], X_train, variables)
        BaseTrainer.persist_feature_importance(fi_elastic, directorio_csvs, "feature_importance_elastic.csv", visualizar_feature_importance_fn, "ElasticNet - Top 20", "04_feature_importance_elastic.png", 20)

        df_resultados = pd.DataFrame(lista_resultados).sort_values('MAE')
        df_resultados.to_csv(directorio_csvs / resultados_csv_name, index=False)

        models_dict = {k: v['modelo'] for k, v in resultados_finales.items()}
        prefix = f"{model_prefix}_" if model_prefix else ""
        for name, model in models_dict.items():
            with open(directorio_modelos / f"best_model_{prefix}{name.lower()}.pkl", "wb") as f:
                import pickle
                pickle.dump(model, f)

        with open(directorio_modelos / "best_model_RF.pkl", "wb") as f:
            import pickle
            pickle.dump(models_dict['RF'], f)

        for name in ('RF', 'XGB', 'Ridge', 'ElasticNet'):
            with open(directorio_modelos / f"best_model_params_{name}.json", 'w') as f:
                import json
                json.dump(resultados_finales[name]['params'], f, indent=2)

        return resultados_finales, df_resultados

    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError
