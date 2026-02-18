"""
MÓDULO DE PREDICCIÓN DE PORTEROS
=================================
Carga el modelo entrenado y predice puntos fantasy para la siguiente jornada.

Uso:
    python predecir_portero.py --jugador_id=123 --jornada=15
    
O desde Django:
    from predecir_portero import predecir_puntos_portero
    puntos = predecir_puntos_portero(jugador_id=123, jornada_actual=15)
"""

import sys
import os
import pickle
import json
import argparse
import warnings
import unicodedata
import numpy as np
import pandas as pd
try:
    import shap
except ImportError:
    shap = None
from pathlib import Path

warnings.filterwarnings("ignore")

# Agregar path para imports
sys.path.insert(0, os.path.dirname(__file__))
from role_enricher import enriquecer_dataframe_con_roles, crear_features_interaccion_roles, calcular_factor_posicion
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_gk, seleccionar_features_por_correlacion
from explicaciones_gk import obtener_explicacion, es_valor_alto, EXPLICACIONES_FEATURES


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DIRECTORIO_MODELOS = Path(__file__).parent.parent.parent / "csv/csvGenerados/entrenamiento/portero/modelos"
CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'ventana_extra': 7,
    'columna_objetivo': "puntos_fantasy",
}


def cargar_modelo(modelo_tipo='RF'):
    """
    Carga el modelo entrenado especificado.
    
    Args:
        modelo_tipo: Tipo de modelo a cargar ('RF', 'XGB', 'Ridge', 'ElasticNet')
                     Default: 'RF' (Random Forest)
    """
    try:
        model_path = DIRECTORIO_MODELOS / f"best_model_{modelo_tipo}.pkl"
        if not model_path.exists():
            print(f"[WARNING] Modelo {modelo_tipo} no encontrado: {model_path}")
            # Fallback a ElasticNet si no existe RF
            if modelo_tipo != 'ElasticNet':
                print(f"[FALLBACK] Intentando cargar ElasticNet...")
                model_path = DIRECTORIO_MODELOS / "best_model_ElasticNet.pkl"
            if not model_path.exists():
                print(f"[ERROR] Ningún modelo disponible")
                return None
        
        with open(model_path, 'rb') as f:
            modelo = pickle.load(f)
        print(f"[OK] Modelo cargado: {model_path}")
        return modelo
    except Exception as e:
        print(f"[ERROR] Error cargando modelo: {e}")
        return None


def cargar_datos_completos():
    """Carga el CSV completo con todos los jugadores. Filtra solo temporada 25/26."""
    try:
        df = pd.read_csv(CONFIG['archivo'])
        print(f"[OK] {len(df)} registros cargados")
        
        # Guardar todos los jugadores de 25/26 para calcular std global
        temporada_cols = [c for c in df.columns if 'temporada' in c.lower()]
        if temporada_cols:
            df = df[df[temporada_cols[0]] == '25_26'].copy()
        
        # Luego filtrar solo a porteros
        posicion_cols = [c for c in df.columns if 'posicion' in c.lower()]
        if posicion_cols:
            df_porteros = df[df[posicion_cols[0]].str.upper() == "PT"].copy()
        else:
            df_porteros = df.copy()
        
        print(f"[OK] {len(df_porteros)} porteros filtrados (temporada 25/26)\n")
        print(f"[INFO] std calculado sobre {len(df)} registros totales (todos los jugadores)\n")
        
        return df_porteros, df  # Retornar porteros + todos para std
    except Exception as e:
        print(f"[ERROR] Error cargando datos: {e}")
        return None, None


def calcular_std_puntos(df_all):
    """
    Calcula la desviación estándar de puntos fantasy de todos los porteros.
    
    Args:
        df_all: DataFrame completo con todos los porteros
    
    Returns:
        float: Desviación estándar de puntos fantasy
    """
    try:
        puntos_col = [c for c in df_all.columns if 'puntos' in c.lower() or 'points' in c.lower()]
        if puntos_col:
            std_puntos = pd.to_numeric(df_all[puntos_col[0]], errors='coerce').std()
            if pd.isna(std_puntos):
                return 2.5
            return float(std_puntos)
        return 2.5
    except Exception as e:
        print(f"[WARNING] Error calculando std: {e}")
        return 2.5


def calcular_margen_confianza(puntos_prediccion, df_all):
    """
    Calcula el margen de confianza (±x) basado en análisis matemático.
    
    Combina:
    - MAE del modelo: 3.22 (del entrenamiento RF)
    - Desviación estándar de puntos fantasy de los porteros
    - Fórmula: margen = sqrt(MAE^2 + std^2/4)
    
    Esto representa un intervalo de confianza robusto que captura:
    - El error del modelo (MAE)
    - La variabilidad natural de los porteros (std)
    
    Args:
        puntos_prediccion: Puntos predichos por el modelo
        df_all: DataFrame completo con todos los porteros
    
    Returns:
        dict: {'margen': float, 'MAE': float, 'std': float}
    """
    try:
        MAE_MODELO = 3.2221159391676863  # Valor real del entrenamiento RF
        
        # Calcular std de puntos fantasy
        std_puntos = calcular_std_puntos(df_all)
        
        # Fórmula: combinar MAE + std en un margen robusto
        # sqrt(MAE^2 + (std/2)^2) captura error del modelo + variabilidad natural
        margen = np.sqrt(MAE_MODELO**2 + (std_puntos/2)**2)
        
        # Redondear a 1 decimal para legibilidad
        margen = round(margen, 1)
        
        return {
            'margen': margen,
            'MAE': round(MAE_MODELO, 4),
            'std': round(std_puntos, 2)
        }
    except Exception as e:
        print(f"[WARNING] Error calculando margen: {e}")
        return {
            'margen': 3.8,
            'MAE': 3.22,
            'std': 2.5
        }


def obtener_puntos_reales_ultimo_partido(df, jugador_id, jornada_a_predecir):
    """
    Obtiene los puntos reales (fantasy points) del jugador en la jornada seleccionada.
    
    Args:
        df: DataFrame completo
        jugador_id: ID o nombre del jugador
        jornada_a_predecir: Jornada que se quiere predecir (y de la que se obtienen puntos reales)
    
    Returns:
        float: Puntos reales de esa jornada, None si no existe
    """
    try:
        # Buscar por nombre exact match primero
        mask = df['player'] == jugador_id
        
        # Si no encuentra, intenta búsqueda flexible (substring)
        if not mask.any():
            mask = df['player'].str.contains(jugador_id, case=False, na=False, regex=False)
        
        # Si aún no encuentra, intenta con normalización de acentos
        if not mask.any():
            jugador_normalizado = normalizar_nombre(jugador_id)
            df_copy = df.copy()
            df_copy['player_normalizado'] = df_copy['player'].apply(normalizar_nombre)
            mask = df_copy['player_normalizado'].str.contains(jugador_normalizado, case=False, na=False, regex=False)
            if mask.any():
                df = df_copy
        
        registros = df[mask].sort_values('jornada')
        
        if len(registros) == 0:
            return None
        
        # Buscar registro para la jornada seleccionada
        registro_jornada = registros[registros['jornada'] == int(jornada_a_predecir)]
        
        if len(registro_jornada) == 0:
            # Jornada sin datos
            return None
        
        # Obtener puntos fantasy
        puntos_cols = [c for c in df.columns if 'puntos' in c.lower() or 'points' in c.lower()]
        if puntos_cols:
            puntos_reales = pd.to_numeric(registro_jornada.iloc[0][puntos_cols[0]], errors='coerce')
            return float(puntos_reales) if not pd.isna(puntos_reales) else None
        return None
    except Exception as e:
        print(f"[WARNING] Error obteniendo puntos reales: {e}")
        return None


def normalizar_nombre(nombre):
    """
    Normaliza un nombre removiendo acentos y convirtiendo a minúsculas.
    Permite buscar "Aaron" y encontrar "Aarón".
    """
    if not isinstance(nombre, str):
        return str(nombre).lower()
    # Normalizar acentos: descomponer caracteres acentuados
    nfd = unicodedata.normalize('NFD', nombre)
    # Remover marcas diacríticas (acentos)
    sin_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return sin_acentos.lower()


def obtener_partido_siguiente(df, jugador_id, jornada_a_predecir):
    """
    Obtiene los datos del portero para predecir una jornada específica.
    Evita data leakage usando solo datos de jornadas anteriores a jornada_a_predecir.
    
    Args:
        df: DataFrame completo
        jugador_id: ID o nombre del jugador
        jornada_a_predecir: Jornada a predecir (se usan datos < jornada_a_predecir)
    
    Returns:
        dict: Datos del jugador o None si no existe
    """
    # Buscar por ID o nombre (case-insensitive, flexible matching)
    mask = df['player'] == jugador_id
    
    # Si no encuentra match exacto, intenta búsqueda flexible (substring, case-insensitive)
    if not mask.any():
        mask = df['player'].str.contains(jugador_id, case=False, na=False, regex=False)
    
    # Si aún no encuentra, intenta búsqueda con normalización de acentos
    if not mask.any():
        jugador_normalizado = normalizar_nombre(jugador_id)
        df['player_normalizado'] = df['player'].apply(normalizar_nombre)
        mask = df['player_normalizado'].str.contains(jugador_normalizado, case=False, na=False, regex=False)
        # Limpiar columna temporal
        if 'player_normalizado' in df.columns:
            df = df.drop('player_normalizado', axis=1)
    
    if not mask.any():
        print(f"[ERROR] Jugador no encontrado: {jugador_id}")
        return None
    
    # IMPORTANTE: Filtrar SOLO datos de jornadas < jornada_a_predecir para evitar data leakage
    registros_completos = df[mask].sort_values('jornada')
    registros = registros_completos[registros_completos['jornada'] < jornada_a_predecir].sort_values('jornada')
    
    if len(registros) == 0:
        # Caso especial: Si es jornada 1, usar datos de jornada 1 como referencia (sin data leakage)
        if jornada_a_predecir == 1:
            print(f"[WARNING] Jornada 1: Usando datos de jornada 1 como referencia")
            registros = registros_completos[registros_completos['jornada'] <= 1]
        
        if len(registros) == 0:
            print(f"[ERROR] Sin registros para {jugador_id} anteriores a jornada {jornada_a_predecir}")
            return None
    
    # Obtener último registro ANTERIOR a jornada_a_predecir
    ultimo_registro = registros.iloc[-1].to_dict()
    
    # CRÍTICO: Obtener el rival CORRECTO de la jornada_a_predecir (no del registro anterior)
    equipo_propio = ultimo_registro['equipo_propio']
    
    # Buscar un registro del equipo propio en la jornada a predecir para obtener el rival correcto
    fixture_jornada = df[
        (df['equipo_propio'] == equipo_propio) & 
        (df['jornada'] == jornada_a_predecir)
    ]
    
    if len(fixture_jornada) > 0:
        equipo_rival_correcto = fixture_jornada.iloc[0]['equipo_rival']
        ultimo_registro['equipo_rival'] = equipo_rival_correcto
        print(f"[INFO] Fixture jornada {jornada_a_predecir}: {equipo_propio} vs {equipo_rival_correcto}")
    else:
        print(f"[WARNING] No se encontró fixture para {equipo_propio} en jornada {jornada_a_predecir}")
    
    print(f"[INFO] Jugador: {ultimo_registro['player']}")
    print(f"[INFO] Equipo: {ultimo_registro['equipo_propio']}")
    print(f"[INFO] Rival: {ultimo_registro['equipo_rival']}")
    print(f"[INFO] Prediciendo para Jornada: {jornada_a_predecir} (usando datos hasta jornada {jornada_a_predecir - 1})\n")
    
    return {
        'jugador_id': jugador_id,
        'jornada_prediccion': jornada_a_predecir,
        'datos': ultimo_registro,
        'registros_historicos': registros  # Para calcular ventanas (ya filtrados)
    }


def calcular_ventanas_temporales(df_jugador, config):
    """
    Calcula ventanas temporales (3, 5, 7) para features.
    
    Args:
        df_jugador: DataFrame con registros del jugador ordenados por jornada
        config: Configuración con ventanas
    
    Returns:
        dict: Features calculadas
    """
    features = {}
    
    # Stats GK principales
    for col in ['porcentaje_paradas', 'psxg', 'goles_en_contra', 'duelos_aereos_ganados', 
                'despejes', 'pases_totales', 'pases_completados_pct']:
        if col not in df_jugador.columns:
            continue
        
        valores = pd.to_numeric(df_jugador[col], errors='coerce').fillna(0).values
        
        # Ventana 5 (últimos 5 partidos)
        if len(valores) >= 5:
            features[f"{col}_roll5"] = valores[-5:].mean()
            features[f"{col}_ewma5"] = pd.Series(valores[-5:]).ewm(span=5, adjust=False).mean().iloc[-1]
        else:
            features[f"{col}_roll5"] = valores.mean() if len(valores) > 0 else 0
            features[f"{col}_ewma5"] = valores.mean() if len(valores) > 0 else 0
    
    # Forma (puntos fantasy)
    if 'puntos_fantasy' in df_jugador.columns:
        valores_pf = pd.to_numeric(df_jugador['puntos_fantasy'], errors='coerce').fillna(0).values
        
        if len(valores_pf) >= 5:
            features['pf_roll5'] = valores_pf[-5:].mean()
            features['pf_ewma5'] = pd.Series(valores_pf[-5:]).ewm(span=5, adjust=False).mean().iloc[-1]
        else:
            features['pf_roll5'] = valores_pf.mean() if len(valores_pf) > 0 else 0
            features['pf_ewma5'] = valores_pf.mean() if len(valores_pf) > 0 else 0
    
    # Disponibilidad
    if 'min_partido' in df_jugador.columns:
        valores_min = pd.to_numeric(df_jugador['min_partido'], errors='coerce').fillna(0).values
        min_pct = (valores_min / 90).clip(0, 1)
        
        if len(min_pct) >= 5:
            features['minutes_pct_roll5'] = min_pct[-5:].mean()
            features['minutes_pct_ewma5'] = pd.Series(min_pct[-5:]).ewm(span=5, adjust=False).mean().iloc[-1]
        else:
            features['minutes_pct_roll5'] = min_pct.mean() if len(min_pct) > 0 else 0
            features['minutes_pct_ewma5'] = min_pct.mean() if len(min_pct) > 0 else 0
        
        if 'titular' in df_jugador.columns:
            valores_titular = pd.to_numeric(df_jugador['titular'], errors='coerce').fillna(0).values
            if len(valores_titular) >= 5:
                features['starter_pct_roll5'] = valores_titular[-5:].mean()
            else:
                features['starter_pct_roll5'] = valores_titular.mean() if len(valores_titular) > 0 else 0
    
    return features


def construir_fila_prediccion(partido_data, ventanas, df_completo):
    """
    Construye una fila con todas las features para pasar al modelo.
    
    Args:
        partido_data: dict con datos del partido
        ventanas: dict con features de ventana temporal
        df_completo: DataFrame original para contexto de equipo rival
    
    Returns:
        pd.Series: Fila con todas las features necesarias
    """
    fila = pd.Series({
        'player': partido_data['datos'].get('player', ''),
        'jornada': partido_data['jornada_prediccion'],
        'equipo_propio': partido_data['datos'].get('equipo_propio', ''),
        'equipo_rival': partido_data['datos'].get('equipo_rival', ''),
        'local': partido_data['datos'].get('local', 1),
        'temporada': partido_data['datos'].get('temporada', '25_26'),
    })
    
    # Agregar ventanas
    fila = pd.concat([fila, pd.Series(ventanas)])
    
    # Contexto del partido
    fila['is_home'] = int(fila.get('local', 1) == 1)
    
    # Fixture difficulty (si existe p_home)
    if 'p_home' in partido_data['datos']:
        p_home = float(partido_data['datos']['p_home'])
        fila['fixture_difficulty_home'] = 1 - p_home
        fila['fixture_difficulty_away'] = p_home
    else:
        fila['fixture_difficulty_home'] = 0.5
        fila['fixture_difficulty_away'] = 0.5
    
    # Stats rival (últimas 5 jornadas ANTERIORES - sin data leakage)
    equipo_rival = fila.get('equipo_rival', '')
    jornada_actual = partido_data['jornada_prediccion'] - 1
    if equipo_rival:
        # Filtrar solo datos anteriores a la jornada siguiente
        duelos_rival = df_completo[
            (df_completo['equipo_propio'] == equipo_rival) & 
            (df_completo['jornada'] <= jornada_actual)
        ].sort_values('jornada')
        if len(duelos_rival) > 0:
            gf_rival = pd.to_numeric(duelos_rival['gf'].tail(5), errors='coerce').fillna(0).mean()
            gc_rival = pd.to_numeric(duelos_rival['gc'].tail(5), errors='coerce').fillna(0).mean()
        else:
            gf_rival = 0
            gc_rival = 0
    else:
        gf_rival = 0
        gc_rival = 0
    
    fila['opp_gf_roll5'] = gf_rival
    fila['opp_gf_ewma5'] = gf_rival
    fila['opp_gc_roll5'] = gc_rival
    fila['opp_gc_ewma5'] = gc_rival
    fila['opp_form_roll5'] = 0.5
    fila['opp_form_ewma5'] = 0.5
    
    # IMPORTANTE: NO usar datos del partido actual (sería data leakage)
    # Solo usar estadísticas generales del rival basadas en jornadas ANTERIORES
    
    # Odds GENERALES del rival (no específicos del fixture actual)
    # Estos se basan en forma general, no en el partido específico
    fila['odds_prob_win'] = 0.33  # Neutro: sin saber del oponente específico
    fila['odds_prob_loss'] = 0.33  # Neutro
    fila['odds_expected_goals_against'] = gf_rival / 3.0  # Basado en goles históricos del rival
    fila['odds_is_favored'] = 0  # Neutro: asumimos que no sabemos de antemano
    fila['odds_market_confidence'] = 0.33  # Neutro
    
    # Features fantasy GK (calcular basado en ventanas HISTÓRICAS, sin data leakage)
    if 'opp_gc_roll5' in fila:
        fila['cs_probability'] = max(0, 1 - (fila['opp_gc_roll5'] / 3.0))
    else:
        fila['cs_probability'] = 0.5
    
    fila['cs_rate_recent'] = fila.get('pf_roll5', 0) / 5
    fila['cs_expected_points'] = fila.get('cs_probability', 0.5) * 6  # Clean sheet = ~6 puntos
    
    # IMPORTANTE: NO usar min_partido del fixture actual (sería data leakage)
    # Solo usar promedios históricos
    if 'minutes_pct_roll5' in fila:
        # minutes_pct_roll5 es el porcentaje promedio histórico
        fila['save_per_90_ewma5'] = fila.get('psxg_ewma5', 0) * fila.get('minutes_pct_roll5', 1)
    else:
        fila['save_per_90_ewma5'] = fila.get('psxg_ewma5', 0)
    
    fila['psxg_per_90_ewma5'] = fila.get('psxg_ewma5', 0)  # EWMA5 ya está en términos por partido
    
    fila['expected_gk_core_points'] = (
        fila.get('psxg_ewma5', 0) * 0.5 +
        fila.get('cs_expected_points', 0) * 0.7 +
        fila.get('pf_ewma5', 0) * 0.1
    )
    
    # Features avanzados
    if 'save_pct_roll5' in fila and 'aerial_won_roll5' in fila:
        save_pct = fila.get('save_pct_roll5', 0) / 100
        aerial = fila.get('aerial_won_roll5', 0) / 5
        fila['defensive_combo'] = save_pct * aerial
    else:
        fila['defensive_combo'] = 0
    
    if 'pf_roll5' in fila and 'pf_ewma5' in fila:
        ratio = fila['pf_ewma5'] / (fila['pf_roll5'] + 0.1)
        fila['form_ratio'] = np.clip(ratio, 0.5, 2.0)
    else:
        fila['form_ratio'] = 1.0
    
    if 'save_pct_roll5' in fila:
        fila['save_pct_power2'] = (fila['save_pct_roll5'] ** 2 / 10000)
    else:
        fila['save_pct_power2'] = 0
    
    if 'minutes_pct_ewma5' in fila and 'pf_roll5' in fila:
        fila['minutes_form_combo'] = fila['minutes_pct_ewma5'] * fila['pf_roll5'] / 10
    else:
        fila['minutes_form_combo'] = 0
    
    if 'opp_gc_roll5' in fila:
        fila['weak_opponent'] = fila['opp_gc_roll5'] / 2
    else:
        fila['weak_opponent'] = 0
    
    if 'pf_roll5' in fila and 'pf_ewma5' in fila:
        momentum = fila['pf_ewma5'] / (fila['pf_roll5'] + 1)
        fila['momentum_factor'] = np.clip(momentum, 0.5, 2.0)
    else:
        fila['momentum_factor'] = 1.0
    
    if 'save_pct_roll5' in fila and 'psxg_roll5' in fila:
        save_pct = fila['save_pct_roll5'] / 100
        psxg_inv = 1 / (fila['psxg_roll5'] + 0.5) if fila['psxg_roll5'] > 0 else 1.0
        fila['total_strength'] = np.clip(save_pct + psxg_inv, 0, 5)
    else:
        fila['total_strength'] = 0
    
    if 'psxg_roll5' in fila:
        save_adv = 1 / (fila['psxg_roll5'] + 0.5)
        fila['save_advantage'] = np.clip(save_adv, 0, 5)
    else:
        fila['save_advantage'] = 1.0
    
    if 'minutes_pct_roll5' in fila and 'pf_ewma5' in fila:
        fila['availability_form'] = fila['minutes_pct_roll5'] * fila['pf_ewma5'] / 10
    else:
        fila['availability_form'] = 0
    
    # AGREGAR FEATURES CON NOMBRES MAPEADOS 
    # Mapeos de nombres (si existen con otros nombres en el CSV)
    if 'goles_en_contra_roll5' in fila:
        fila['goles_contra_roll5'] = fila['goles_en_contra_roll5']
    else:
        fila['goles_contra_roll5'] = 0
    
    if 'pases_completados_pct_ewma5' in fila:
        fila['pass_comp_pct_ewma5'] = fila['pases_completados_pct_ewma5']
    else:
        fila['pass_comp_pct_ewma5'] = 0
    
    if 'pases_completados_pct_roll5' in fila:
        fila['pass_comp_pct_roll5'] = fila['pases_completados_pct_roll5']
    else:
        fila['pass_comp_pct_roll5'] = 0
    
    # num_roles_criticos - contar roles en el JSON 'roles'
    if isinstance(fila.get('roles'), list):
        fila['num_roles_criticos'] = len(fila.get('roles', []))
    else:
        fila['num_roles_criticos'] = 0
    
    # VARIABLES DE ROLES DERIVADAS
    # num_roles_positivos: roles beneficiosos (paradas, portería en blanco)
    # Usar como aproximación roles que suman puntos
    if fila.get('num_roles_criticos', 0) > 0:
        fila['num_roles_positivos'] = max(0, fila.get('num_roles_criticos', 0) // 2)
        fila['num_roles_negativos'] = max(0, fila.get('num_roles_criticos', 0) // 3)
    else:
        fila['num_roles_positivos'] = 0
        fila['num_roles_negativos'] = 0
    
    # ratio_roles_positivos: proporción de roles positivos
    if fila.get('num_roles_criticos', 0) > 0:
        fila['ratio_roles_positivos'] = fila.get('num_roles_positivos', 0) / fila.get('num_roles_criticos', 1)
    else:
        fila['ratio_roles_positivos'] = 0
    
    # score_roles_normalizado: score ponderado normalizado
    # Basado en save_pct y disponibilidad
    if 'save_pct_roll5' in fila and 'minutes_pct_roll5' in fila:
        save_pct_norm = fila.get('save_pct_roll5', 0) / 100
        minutes_norm = fila.get('minutes_pct_roll5', 0)
        fila['score_roles_normalizado'] = (save_pct_norm * minutes_norm * fila.get('num_roles_criticos', 1)) / 10
    else:
        fila['score_roles_normalizado'] = 0
    
    return fila


def predecir_puntos_portero(jugador_id, jornada_actual=None, verbose=True, modelo_tipo='RF'):
    """
    Función principal para predecir puntos fantasy de un portero.
    
    Args:
        jugador_id: ID o nombre del jugador
        jornada_actual: Jornada actual (si None, usa la última)
        verbose: Imprimir información detallada
        modelo_tipo: Tipo de modelo a usar ('RF', 'XGB', 'Ridge', 'ElasticNet'). Default: 'RF'
    
    Returns:
        dict: {
            'jugador_id': str,
            'prediccion': float,
            'jornada': int,
            'modelo': str,
            'confianza': float,
            'error': str (si aplica)
        }
    """
    
    # Cargar modelo especificado
    modelo = cargar_modelo(modelo_tipo)
    if modelo is None:
        return {
            'error': f'Modelo {modelo_tipo} no disponible',
            'jugador_id': jugador_id,
            'prediccion': None,
            'jornada': None
        }
    
    # Cargar datos
    df_porteros, df_todos = cargar_datos_completos()
    if df_porteros is None or df_todos is None:
        return {
            'error': 'Datos no disponibles',
            'jugador_id': jugador_id,
            'prediccion': None,
            'jornada': None
        }
    
    df = df_porteros  # Usar porteros para predicción
    
    # Si no se especifica jornada, usar la última + 1 (próxima jornada a predecir)
    if jornada_actual is None:
        jornada_actual = df['jornada'].max()
    
    # Convertir jornada_actual a int (puede llegar como string desde API)
    jornada_actual = int(jornada_actual)
    
    # Obtener datos del jugador para predecir esa jornada
    partido = obtener_partido_siguiente(df, jugador_id, jornada_actual)
    if partido is None:
        return {
            'error': f'Jugador no encontrado: {jugador_id}',
            'jugador_id': jugador_id,
            'prediccion': None,
            'jornada': None
        }
    
    # Calcular ventanas temporales
    registros_jugador = partido['registros_historicos'].sort_values('jornada')
    
    # FALLBACK: Si el jugador tiene muy pocos registros históricos, NO hacer predicción
    if len(registros_jugador) < 3:
        if verbose:
            print(f"[WARNING] Datos insuficientes ({len(registros_jugador)} registros). No hacer predicción.")
        
        puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, partido['jornada_prediccion'])
        
        return {
            'jugador_id': jugador_id,
            'prediccion': None,  # Sin predicción
            'puntos_reales': round(puntos_reales, 2) if puntos_reales is not None else None,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'margen': 0,  # Sin margen
            'rango_min': None,
            'rango_max': None,
            'jornada': partido['jornada_prediccion'],
            'modelo': 'Sin datos (insuficientes registros)',
            'error': None
        }
    
    ventanas = calcular_ventanas_temporales(registros_jugador, CONFIG)
    
    # Construir fila para predicción
    fila = construir_fila_prediccion(partido, ventanas, df)
    
    # Seleccionar EXACTAMENTE los 27 features que el modelo RF espera
    # Orden exacto del Feature Importance del RF entrenado
    variables_modelo = [
        "pass_comp_pct_ewma5",
        "total_strength",
        "pf_ewma5",
        "psxg_ewma5",
        "availability_form",
        "pass_comp_pct_roll5",
        "weak_opponent",
        "defensive_combo",
        "save_advantage",
        "momentum_factor",
        "minutes_form_combo",
        "psxg_roll5",
        "score_roles_normalizado",
        "pf_roll5",
        "odds_expected_goals_against",
        "odds_market_confidence",
        "goles_contra_roll5",
        "num_roles_criticos",
        "minutes_pct_ewma5",
        "ratio_roles_positivos",
        "num_roles_positivos",
        "is_home",
        "minutes_pct_roll5",
        "starter_pct_roll5",
        "cs_probability",
        "expected_gk_core_points",
        "cs_expected_points"
    ]
    
    # Filtrar solo las columnas que existen
    features_disponibles = [v for v in variables_modelo if v in fila.index]
    if len(features_disponibles) < 19:  # Menos del 70% de features (27 total)
        promedio_historico = pd.to_numeric(registros_jugador['puntos_fantasy'], errors='coerce').mean()
        if pd.isna(promedio_historico) or promedio_historico <= 0:
            promedio_historico = 8
        
        if verbose:
            print(f"[WARNING] Faltan features ({len(features_disponibles)}/27). Usando promedio histórico: {promedio_historico:.2f}")
        
        margen_dict = calcular_margen_confianza(promedio_historico, df)
        margen = margen_dict['margen']
        puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, partido['jornada_prediccion'])
        
        return {
            'jugador_id': jugador_id,
            'prediccion': round(promedio_historico, 2),
            'puntos_reales': round(puntos_reales, 2) if puntos_reales is not None else None,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'margen': margen,
            'mae_value': margen_dict['MAE'],
            'std_value': margen_dict['std'],
            'rango_min': round(max(0, promedio_historico - margen), 2),
            'rango_max': round(promedio_historico + margen, 2),
            'jornada': partido['jornada_prediccion'],
            'modelo': 'Promedio Histórico (features incompletas)',
            'error': None
        }
    
    X_pred = fila[features_disponibles].values.reshape(1, -1)
    
    # Hacer predicción
    try:
        prediccion = modelo.predict(X_pred)[0]
        prediccion = max(0, prediccion)  # No negativos
        
        # Obtener puntos reales de la jornada a predecir
        puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, partido['jornada_prediccion'])
        
        # Calcular margen de confianza matemáticamente (usando todos los jugadores para std)
        margen_dict = calcular_margen_confianza(prediccion, df_todos)
        margen = margen_dict['margen']
        
        if verbose:
            print(f"[OK] Predicción: {prediccion:.2f} puntos")
            print(f"[OK] Puntos reales (jornada {partido['jornada_prediccion']}): {puntos_reales}")
            print(f"[OK] Margen de confianza: ±{margen}\n")
        
        return {
            'jugador_id': jugador_id,
            'prediccion': round(prediccion, 2),
            'puntos_reales': round(puntos_reales, 2) if puntos_reales is not None else None,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'margen': margen,
            'mae_value': margen_dict['MAE'],
            'std_value': margen_dict['std'],
            'rango_min': round(max(0, prediccion - margen), 2),
            'rango_max': round(prediccion + margen, 2),
            'jornada': partido['jornada_prediccion'],
            'modelo': 'Random Forest',
            'error': None
        }
    except Exception as e:
        print(f"[ERROR] Error en predicción: {e}")
        return {
            'error': str(e),
            'jugador_id': jugador_id,
            'prediccion': None,
            'jornada': None
        }


def explicar_prediccion_portero(jugador_id, jornada_actual=None, modelo_tipo='RF'):
    """
    Explica la predicción de un portero usando SHAP (SHapley Additive exPlanations).
    
    Retorna las features más importantes y su impacto en la predicción.
    
    Args:
        jugador_id: ID o nombre del jugador
        jornada_actual: Jornada a predecir (si None, usa la última + 1)
        modelo_tipo: Tipo de modelo a usar ('RF', 'XGB', 'Ridge', 'ElasticNet'). Default: 'RF'
    
    Returns:
        dict: {
            'prediccion': float,
            'features_impacto': [
                {'feature': str, 'impacto': float, 'valor': float, 'direccion': 'positivo'|'negativo'},
                ...
            ],
            'explicacion_texto': str,
            'error': str (si aplica)
        }
    """
    
    try:
        # Cargar modelo especificado
        modelo = cargar_modelo(modelo_tipo)
        if modelo is None:
            return {
                'error': f'Modelo {modelo_tipo} no disponible',
                'prediccion': None,
                'features_impacto': []
            }
        
        # Cargar datos
        df = cargar_datos_completos()
        if df is None:
            return {
                'error': 'Datos no disponibles',
                'prediccion': None,
                'features_impacto': []
            }
        
        # Si no se especifica jornada, usar la última + 1 (próxima jornada a predecir)
        if jornada_actual is None:
            jornada_actual = df['jornada'].max()
        
        # Obtener datos del jugador para predecir esa jornada
        partido = obtener_partido_siguiente(df, jugador_id, jornada_actual)
        if partido is None:
            return {
                'error': f'Jugador no encontrado: {jugador_id}',
                'prediccion': None,
                'features_impacto': []
            }
        
        # Calcular ventanas temporales
        registros_jugador = partido['registros_historicos'].sort_values('jornada')
        
        # FALLBACK: Si el jugador tiene muy pocos registros históricos
        if len(registros_jugador) < 3:
            puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, jornada_actual)
            puntos_reales_texto = str(puntos_reales) if puntos_reales is not None else "Aún no jugado"
            
            return {
                'prediccion': None,
                'puntos_reales': round(puntos_reales, 2) if puntos_reales is not None else None,
                'puntos_reales_texto': puntos_reales_texto,
                'margen': 0,
                'rango_min': None,
                'rango_max': None,
                'jornada': jornada_actual,
                'modelo': modelo_tipo,
                'features_impacto': [],
                'explicaciones': [],
                'explicacion_texto': f"Sin predicción: Datos insuficientes ({len(registros_jugador)} partidos). Se necesitan al menos 3 partidos para hacer una predicción confiable.",
                'error': None
            }
        
        ventanas = calcular_ventanas_temporales(registros_jugador, CONFIG)
        
        # Construir fila para predicción
        fila = construir_fila_prediccion(partido, ventanas, df)
        
        # Variables del modelo (27 exactamente - IDÉNTICAS a predecir_puntos_portero)
        # Orden exacto del Feature Importance del RF entrenado
        variables_modelo = [
            "pass_comp_pct_ewma5",
            "total_strength",
            "pf_ewma5",
            "psxg_ewma5",
            "availability_form",
            "pass_comp_pct_roll5",
            "weak_opponent",
            "defensive_combo",
            "save_advantage",
            "momentum_factor",
            "minutes_form_combo",
            "psxg_roll5",
            "score_roles_normalizado",
            "pf_roll5",
            "odds_expected_goals_against",
            "odds_market_confidence",
            "goles_contra_roll5",
            "num_roles_criticos",
            "minutes_pct_ewma5",
            "ratio_roles_positivos",
            "num_roles_positivos",
            "is_home",
            "minutes_pct_roll5",
            "starter_pct_roll5",
            "cs_probability",
            "expected_gk_core_points",
            "cs_expected_points"
        ]
        
        # Filtrar solo las columnas que existen
        features_disponibles = [v for v in variables_modelo if v in fila.index]
        X_pred = fila[features_disponibles].values.reshape(1, -1)
        
        # Hacer predicción base
        prediccion = modelo.predict(X_pred)[0]
        prediccion = max(0, prediccion)
        
        # SHAP Explanation
        try:
            # Crear explainer (TreeExplainer para Random Forest es rápido)
            if hasattr(modelo, 'estimators_'):  # Random Forest
                explainer = shap.TreeExplainer(modelo)
                shap_values = explainer.shap_values(X_pred)
                
                # Para regresión, shap_values es simple array
                if isinstance(shap_values, list):
                    shap_impacts = shap_values[0][0]  # Primera predicción
                else:
                    shap_impacts = shap_values[0]
            else:
                # Fallback: usar permutation explainer
                explainer = shap.PermutationExplainer(modelo.predict, X_pred)
                shap_values = explainer.shap_values(X_pred)
                shap_impacts = shap_values[0]
            
            # Extraer top 10 features más influyentes
            feature_impacts = []
            for i, feature_name in enumerate(features_disponibles):
                if i < len(shap_impacts):
                    impacto = float(shap_impacts[i])
                    valor = float(fila[feature_name])
                    
                    feature_impacts.append({
                        'feature': feature_name,
                        'impacto': abs(impacto),
                        'impacto_signed': impacto,
                        'valor': valor,
                        'direccion': 'positivo' if impacto > 0 else 'negativo'
                    })
            
            # Ordenar por impacto absoluto y tomar top 10
            feature_impacts.sort(key=lambda x: x['impacto'], reverse=True)
            top_features = feature_impacts[:10]
            
            # ═══════════════════════════════════════════════════════════════════════
            # GENERAR EXPLICACIONES EN TEXTO NATURAL (Top 5-7 features)
            # ═══════════════════════════════════════════════════════════════════════
            
            explicaciones_array = []
            explicacion_lines = []
            explicacion_lines.append(f"Predicción: {prediccion:.1f} puntos\n")
            explicacion_lines.append("Factores principales:\n")
            
            for idx, feat in enumerate(top_features[:7], 1):
                feature_name = feat['feature']
                valor = feat['valor']
                impacto_signed = feat['impacto_signed']
                direccion = feat['direccion']
                
                # Usar función del módulo para obtener explicación con emoji
                # La dirección es POSITIVO si SHAP value > 0, NEGATIVO si SHAP value < 0
                explicacion_texto_expr = obtener_explicacion(feature_name, es_positivo=(direccion == 'positivo'))
                
                # Formato de impacto
                impacto_abs = abs(impacto_signed)
                linea = f"{idx}. {explicacion_texto_expr} {'+' if impacto_signed > 0 else '-'}{impacto_abs:.2f}pts"
                
                explicacion_lines.append(linea)
                
                # Agregar a array de explicaciones
                explicaciones_array.append({
                    'feature': feature_name,
                    'valor': float(valor),
                    'impacto': float(impacto_abs),
                    'direccion': direccion,
                    'explicacion': explicacion_texto_expr
                })
            
            explicacion_texto = "\n".join(explicacion_lines)
            
            # Obtener puntos reales de esa jornada
            puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, jornada_actual)
            puntos_reales_texto = str(puntos_reales) if puntos_reales is not None else "Aún no jugado"
            
            # Calcular margen de confianza (usando todos los jugadores para std)
            margen_dict = calcular_margen_confianza(prediccion, df_todos)
            margen = margen_dict['margen']
            rango_min = max(0, prediccion - margen)
            rango_max = prediccion + margen
            
            return {
                'prediccion': round(prediccion, 2),
                'puntos_reales': puntos_reales,
                'puntos_reales_texto': puntos_reales_texto,
                'margen': round(margen, 1),
                'mae_value': margen_dict['MAE'],
                'std_value': margen_dict['std'],
                'rango_min': round(rango_min, 2),
                'rango_max': round(rango_max, 2),
                'jornada': partido['jornada_prediccion'],
                'modelo': modelo_tipo,
                'features_impacto': top_features,
                'explicaciones': explicaciones_array,
                'explicacion_texto': explicacion_texto,
                'error': None
            }
        
        except Exception as e:
            # Si SHAP falla, retornar predicción sin explicaciones
            print(f"[WARNING] SHAP explanation failed: {e}")
            
            # Aún así retornar todos los campos necesarios
            puntos_reales = obtener_puntos_reales_ultimo_partido(df, jugador_id, jornada_actual) if 'df' in locals() else None
            puntos_reales_texto = str(puntos_reales) if puntos_reales is not None else "Aún no jugado"
            margen_dict = calcular_margen_confianza(prediccion, df) if 'df' in locals() else {'margen': 3.8, 'MAE': 3.22, 'std': 2.5}
            margen = margen_dict['margen']
            rango_min = max(0, prediccion - margen)
            rango_max = prediccion + margen
            jornada_pred = partido['jornada_prediccion'] if 'partido' in locals() else jornada_actual
            
            return {
                'prediccion': round(prediccion, 2),
                'puntos_reales': puntos_reales,
                'puntos_reales_texto': puntos_reales_texto,
                'margen': round(margen, 1),
                'mae_value': margen_dict['MAE'],
                'std_value': margen_dict['std'],
                'rango_min': round(rango_min, 2),
                'rango_max': round(rango_max, 2),
                'jornada': jornada_pred,
                'modelo': modelo_tipo,
                'features_impacto': [],
                'explicaciones': [],
                'explicacion_texto': f"Predicción: {prediccion:.1f} puntos",
                'error': None
            }
    
    except Exception as e:
        print(f"[ERROR] Error en explicación: {e}")
        return {
            'error': str(e),
            'prediccion': None,
            'features_impacto': []
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Predecir puntos fantasy de portero')
    parser.add_argument('--jugador_id', required=True, help='ID o nombre del jugador')
    parser.add_argument('--jornada', type=int, default=None, help='Jornada actual (default: última)')
    args = parser.parse_args()
    
    resultado = predecir_puntos_portero(args.jugador_id, args.jornada)
    print("\nRESULTADO:")
    print(json.dumps(resultado, indent=2))
