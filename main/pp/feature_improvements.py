"""
MÓDULO: MEJORAS DE FEATURES PARA REDUCIR MAE
Autor: AI Assistant para Fantasy Football Analytics
Fecha: Enero 2026

Propósito: Eliminar features ruido y crear nuevas features defensivas
específicas para Fantasy Football que mejoren la correlación de Spearman
y reduzcan el MAE.

Uso: 
    from feature_improvements import (
        eliminar_features_ruido,
        crear_features_fantasy_defensivos,
        seleccionar_features_por_correlacion
    )
    
    df = eliminar_features_ruido(df)
    df = crear_features_fantasy_defensivos(df)
    features_seleccionadas = seleccionar_features_por_correlacion(X_train, y_train)
"""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from typing import List, Tuple

# ============================================================================
# PARTE 1: ELIMINAR FEATURES RUIDO
# ============================================================================

def eliminar_features_ruido(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Elimina features con importancia = 0 en múltiples modelos.
    Estos features son colineales o ruido puro.
    
    Args:
        df: DataFrame con features
        verbose: Print de características eliminadas
        
    Returns:
        DataFrame sin features ruido
    """
    
    # Features identificadas como 0.0000 en 2+ modelos en GridSearch results
    FEATURES_RUIDO = [
        'duels_won_pct_ewma5',      # 0 en Random Forest
        'duels_won_roll5',           # 0 en Random Forest, XGBoost, Ridge
        'duels_won_ewma5',           # 0 en Random Forest, XGBoost, Ridge  
        'elite_entradas_interact',   # 0 en ElasticNet
        'ratio_roles_criticos',      # 0 en ElasticNet
    ]
    
    features_a_eliminar = [f for f in FEATURES_RUIDO if f in df.columns]
    
    if verbose:
        print("="*80)
        print("ELIMINACIÓN DE FEATURES RUIDO")
        print("="*80)
        print(f"\n{len(features_a_eliminar)} features a eliminar:\n")
        for f in features_a_eliminar:
            print(f"  ❌ {f} (colinealidad/redundancia)")
        print()
    
    df = df.drop(columns=features_a_eliminar, errors='ignore')
    
    if verbose:
        print(f"✅ Eliminadas {len(features_a_eliminar)} features ruido\n")
    
    return df


# ============================================================================
# PARTE 2: CREAR FEATURES NUEVAS DEFENSIVAS ESPECÍFICAS
# ============================================================================

def crear_features_fantasy_defensivos(df: pd.DataFrame, 
                                      verbose: bool = True) -> pd.DataFrame:
    """
    Crea features específicas para Fantasy Football - Defensas.
    Basado en la puntuación real de FPL:
    - Clean sheet: -10 pts
    - Entrada: +1 pt
    - Intercepción: +1 pt
    - Despeje: +0.5 pts
    - Falta: -0.5 pts
    - Amarilla: -1 pt
    
    Args:
        df: DataFrame con datos básicos
        verbose: Print de features creadas
        
    Returns:
        DataFrame enriquecido
    """
    
    if verbose:
        print("="*80)
        print("INGENIERÍA DE FEATURES DEFENSIVAS ESPECÍFICAS (FANTASY FOOTBALL)")
        print("="*80)
        print()
    
    # Copiar para no modificar original
    df = df.copy()
    
    # ========================================================================
    # 1. CLEAN SHEET PROBABILITY & RATE
    # ========================================================================
    
    if 'opp_shots_ewma5' in df.columns:
        # Probabilidad de clean sheet = inversamente proporcional a tiros recibidos
        df['cs_probability'] = 1.0 / (1.0 + df['opp_shots_ewma5'].fillna(0) + 0.1)
        
        # Rate de clean sheets en últimos 3 partidos
        # (Clean sheet = puntosFantasy entre -10 y 10, aproximadamente)
        if 'puntosFantasy' in df.columns:
            df['cs_in_last_3'] = df.groupby('player')['puntosFantasy'].transform(
                lambda x: ((x >= -10) & (x <= 10)).shift().rolling(3, min_periods=1).sum()
            ).fillna(0)
            
            df['cs_rate_recent'] = df['cs_in_last_3'] / 3.0
        
        if verbose:
            print(" ✓ cs_probability (tiros rival inverso)")
            print(" ✓ cs_rate_recent (últimos 3 partidos)")
    
    # ========================================================================
    # 2. EFFICIENCY METRICS (por 90 minutos)
    # ========================================================================
    
    if 'Entradas' in df.columns and 'Min_partido' in df.columns:
        # Tackling per 90
        df['Entradas'] = pd.to_numeric(df['Entradas'], errors='coerce').fillna(0)
        df['Min_partido'] = pd.to_numeric(df['Min_partido'], errors='coerce').fillna(1)
        
        df['tackles_per_90'] = (
            df['Entradas'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        # Media móvil exponencial de tackles per 90
        df['tackles_per_90_ewma5'] = df.groupby('player')['tackles_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print(" ✓ tackles_per_90 (normalizadas a 90 min)")
            print(" ✓ tackles_per_90_ewma5 (media móvil)")
    
    if 'Intercepciones' in df.columns and 'Min_partido' in df.columns:
        df['Intercepciones'] = pd.to_numeric(df['Intercepciones'], errors='coerce').fillna(0)
        
        df['int_per_90'] = (
            df['Intercepciones'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['int_per_90_ewma5'] = df.groupby('player')['int_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print(" ✓ int_per_90 (normalizadas a 90 min)")
            print(" ✓ int_per_90_ewma5 (media móvil)")
    
    if 'Despejes' in df.columns and 'Min_partido' in df.columns:
        df['Despejes'] = pd.to_numeric(df['Despejes'], errors='coerce').fillna(0)
        
        df['clearances_per_90'] = (
            df['Despejes'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        if verbose:
            print(" ✓ clearances_per_90 (normalizadas a 90 min)")
    
    # ========================================================================
    # 3. COMBINED DEFENSIVE ACTION INDEX
    # ========================================================================
    
    df['defensive_actions_total'] = (
        df.get('Entradas', 0) + 
        df.get('Intercepciones', 0) + 
        df.get('Despejes', 0) * 0.5  # Despejes menos valorados
    )
    
    df['def_actions_per_90'] = (
        df['defensive_actions_total'] / (df['Min_partido'] / 90.0 + 0.1)
    ).fillna(0)
    
    df['def_actions_ewma5'] = df.groupby('player')['defensive_actions_total'].transform(
        lambda x: x.shift().ewm(span=5, adjust=False).mean()
    ).fillna(0)
    
    if verbose:
        print(" ✓ defensive_actions_total (tackles + int + clearances*0.5)")
        print(" ✓ def_actions_per_90 (normalizadas)")
        print(" ✓ def_actions_ewma5 (media móvil)")
    
    # ========================================================================
    # 4. CONSISTENCY / VOLATILITY (clave para predecir puntos estables)
    # ========================================================================
    
    if 'puntosFantasy' in df.columns:
        # Consistencia reciente: 1 / (1 + desviación)
        df['consistency_5games'] = df.groupby('player')['puntosFantasy'].transform(
            lambda x: 1.0 / (1.0 + x.shift().rolling(5, min_periods=2).std().fillna(0))
        ).fillna(0.5)
        
        # Desviación de acciones defensivas (¿muy variable?)
        df['def_actions_volatility'] = df.groupby('player')['defensive_actions_total'].transform(
            lambda x: x.shift().rolling(5, min_periods=2).std()
        ).fillna(0)
        
        if verbose:
            print(" ✓ consistency_5games (inversa a volatilidad)")
            print(" ✓ def_actions_volatility (desviación acciones)")
    
    # ========================================================================
    # 5. MOMENTUM / TREND DETECTION (¿mejorando o empeorando?)
    # ========================================================================
    
    if 'tackles_ewma3' in df.columns and 'tackles_ewma5' in df.columns:
        # Si ewma3 > ewma5, está mejorando
        df['tackles_momentum'] = (
            df['tackles_ewma3'] - df['tackles_ewma5']
        ).fillna(0)
        
        if verbose:
            print(" ✓ tackles_momentum (ewma3 - ewma5)")
    
    if 'Intercepciones' in df.columns:
        df['int_momentum'] = df.groupby('player')['Intercepciones'].transform(
            lambda x: (x.shift().ewm(3, adjust=False).mean() - 
                      x.shift().ewm(5, adjust=False).mean())
        ).fillna(0)
        
        if verbose:
            print(" ✓ int_momentum (trend de intercepciones)")
    
    # ========================================================================
    # 6. CONTEXT INTERACTIONS (Criteriosa para XGBoost)
    # ========================================================================
    
    if 'fixture_difficulty_home' in df.columns and 'is_home' in df.columns:
        # Si está en casa contra rival débil, probablemente:
        # - Ataque más, defiende menos
        # - Menos puntos defensivos esperados
        df['defensive_context'] = (
            df['is_home'].fillna(0) * df['fixture_difficulty_home'].fillna(0.5)
        )
        
        if verbose:
            print(" ✓ defensive_context (is_home × fixture_difficulty)")
    
    # Clean sheet esperado × actividad real
    if 'cs_probability' in df.columns and 'def_actions_per_90' in df.columns:
        df['cs_activity_alignment'] = (
            df['cs_probability'] * df['def_actions_per_90']
        ).fillna(0)
        
        if verbose:
            print(" ✓ cs_activity_alignment (CS prob × activity)")
    
    # ========================================================================
    # 7. USAGE & STATUS
    # ========================================================================
    
    if 'minutes_pct_roll5' in df.columns:
        # ¿Cambió recientemente el uso?
        df['usage_change_recent'] = df.groupby('player')['minutes_pct_roll5'].transform(
            lambda x: x - x.shift(1)
        ).fillna(0)
        
        if verbose:
            print(" ✓ usage_change_recent (cambio en minutos %)")
    
    print()
    print(f"✅ {df.shape[1]} features totales después de ingeniería defensiva\n")
    
    return df


# ============================================================================
# PARTE 3: SELECCIÓN DE FEATURES POR CORRELACIÓN
# ============================================================================

def seleccionar_features_por_correlacion(
    X: pd.DataFrame, 
    y: pd.Series,
    target_name: str = 'puntosFantasy',
    threshold: float = 0.03,
    verbose: bool = True
) -> Tuple[List[str], pd.DataFrame]:
    """
    Selecciona features con Spearman >= threshold con el target.
    Evita features con ruido puro (correlación = 0).
    
    Args:
        X: Features dataframe
        y: Target series
        target_name: Nombre del target para logs
        threshold: Correlación mínima |Spearman|
        verbose: Print detallado
        
    Returns:
        (lista_features_validas, dataframe_correlaciones)
    """
    
    if verbose:
        print("="*80)
        print(f"SELECCIÓN DE FEATURES POR CORRELACIÓN ({target_name})")
        print("="*80)
        print()
    
    correlaciones = {}
    pvalues = {}
    
    for col in X.columns:
        # Ignorar features con demasiados NaN
        mask = (~X[col].isna()) & (~y.isna())
        if mask.sum() < 10:
            correlaciones[col] = 0.0
            pvalues[col] = 1.0
            continue
        
        try:
            corr, pval = spearmanr(X.loc[mask, col], y[mask])
            correlaciones[col] = abs(corr) if not np.isnan(corr) else 0.0
            pvalues[col] = pval if not np.isnan(pval) else 1.0
        except:
            correlaciones[col] = 0.0
            pvalues[col] = 1.0
    
    # DataFrame de resultados
    df_correlaciones = pd.DataFrame({
        'feature': list(correlaciones.keys()),
        'spearman_abs': list(correlaciones.values()),
        'pvalue': list(pvalues.values())
    }).sort_values('spearman_abs', ascending=False)
    
    # Features válidas
    features_validas = df_correlaciones[
        df_correlaciones['spearman_abs'] >= threshold
    ]['feature'].tolist()
    
    if verbose:
        print(f"\nTop 20 features por correlación:\n")
        print(df_correlaciones.head(20).to_string(index=False))
        print(f"\n{'-'*80}\n")
        print(f"✅ Features VÁLIDAS (|Spearman| >= {threshold}): {len(features_validas)}")
        print(f"❌ Features REMOVIDAS (|Spearman| < {threshold}): {len(correlaciones) - len(features_validas)}")
        print()
        
        # Features muertos (correlación = 0)
        dead_features = df_correlaciones[df_correlaciones['spearman_abs'] == 0.0]
        if len(dead_features) > 0:
            print(f"\n⚠️  FEATURES MUERTOS (Spearman = 0.0):\n")
            for _, row in dead_features.head(10).iterrows():
                print(f"   - {row['feature']}")
        print()
    
    return features_validas, df_correlaciones


# ============================================================================
# SCRIPT DE USO COMPLETO
# ============================================================================

if __name__ == "__main__":
    """
    Ejemplo de uso integrado
    """
    
    print("\n" + "="*80)
    print("EJEMPLO DE INTEGRACIÓN EN PIPELINE")
    print("="*80 + "\n")
    
    print("""
    # En tu entrenar-modelo-df.py:
    
    from feature_improvements import (
        eliminar_features_ruido,
        crear_features_fantasy_defensivos,
        seleccionar_features_por_correlacion
    )
    
    # Después de cargar datos y antes de train/test split:
    
    # 1. Eliminar ruido
    df = eliminar_features_ruido(df)
    
    # 2. Crear features defensivas nuevas
    df = crear_features_fantasy_defensivos(df)
    
    # 3. Separar features y target
    X = df.drop(columns=['player', 'puntosFantasy'], errors='ignore')
    y = df['puntosFantasy']
    
    # 4. Seleccionar features válidas
    features_seleccionadas, df_corr = seleccionar_features_por_correlacion(
        X, y, threshold=0.03
    )
    
    # 5. Filtrar dataset
    X_final = X[features_seleccionadas]
    
    # 6. Train/test split y modelo (como antes)
    X_train, X_test, y_train, y_test = train_test_split(
        X_final, y, test_size=0.2, random_state=42
    )
    
    # GridSearchCV con nuevas features y parámetros mejorados...
    """)
