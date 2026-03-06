"""
Módulo ÚNICO de Predicción Fantasy para todas las posiciones
============================================================
Unifica: predecir_portero.py, predecir_defensa.py,
         predecir_mediocampista.py, predecir_delantero.py

Uso principal:
    from predecir import predecir_puntos
    resultado = predecir_puntos(jugador_id=123, posicion='MC', jornada_actual=18)

Posiciones aceptadas:
    PT / Portero / GK  →  Portero
    DF / Defensa       →  Defensor
    MC / Centrocampista→  Mediocampista
    DT / Delantero     →  Delantero
"""

import sys, os, pickle, warnings, unicodedata
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))

from explicaciones import (
    obtener_explicacion, es_valor_alto, generar_explicaciones_shap,
    formatear_explicaciones_texto
)

# ─── Django setup (solo si es necesario) ─────────────────────────────────────
def _django_setup():
    try:
        import django
        if not django.apps.apps.ready:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
            django.setup()
    except Exception:
        pass

# =============================================================================
# CONFIGURACIÓN POR POSICIÓN
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.parent / "csv/csvGenerados/entrenamiento"

DIRECTORIOS_MODELOS = {
    'PT': BASE_DIR / "portero/modelos",
    'DF': BASE_DIR / "defensa/modelos",
    'MC': BASE_DIR / "mediocampista/modelos",
    'DT': BASE_DIR / "delantero/modelos",
}

CONFIG = {
    'archivo_csv':   "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'ventana_extra': 7,
}


# =============================================================================
# UTILIDADES COMUNES
# =============================================================================

def normalizar_nombre(nombre):
    if not isinstance(nombre, str):
        nombre = str(nombre)
    nfd = unicodedata.normalize('NFD', nombre)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').lower().strip()


# Modelo elegido por posición según resultados de entrenamiento:
#   PT → Random Forest  (mejor MAE en porteros)
#   DF → Random Forest  (mejor MAE en defensas)
#   MC → Ridge          (mejor MAE en mediocampistas)
#   DT → Ridge          (mejor MAE en delanteros)
MODELO_POR_POSICION = {
    'PT': 'RF',
    'DF': 'RF',
    'MC': 'Ridge',
    'DT': 'Ridge',
}

NOMBRE_MODELO_LEGIBLE = {
    'RF':    'Random Forest',
    'Ridge': 'Ridge Regression',
}


def cargar_modelo(posicion, modelo_tipo=None):
    """Carga el modelo óptimo para una posición.
    Si modelo_tipo es None, usa MODELO_POR_POSICION.
    """
    if modelo_tipo is None:
        modelo_tipo = MODELO_POR_POSICION.get(posicion, 'RF')

    directorio = DIRECTORIOS_MODELOS.get(posicion)
    if directorio is None:
        return None, modelo_tipo

    # Candidatos ordenados por prioridad según posición y tipo
    candidatos = {
        ('PT', 'RF'):    ['best_model_RF.pkl', 'best_model_rf.pkl', 'best_model_portero_rf.pkl'],
        ('DF', 'RF'):    ['best_model_RF.pkl', 'best_model_rf.pkl', 'best_model_defensa_rf.pkl'],
        ('MC', 'Ridge'): ['best_model_mc_ridge.pkl', 'best_model_Ridge.pkl', 'best_model_ridge.pkl'],
        ('MC', 'RF'):    ['best_model_mc_rf.pkl', 'best_model_RF.pkl'],
        ('DT', 'Ridge'): ['best_model_delantero_ridge.pkl', 'best_model_Ridge.pkl', 'best_model_ridge.pkl'],
        ('DT', 'RF'):    ['best_model_delantero_rf.pkl', 'best_model_RF.pkl'],
    }
    key = (posicion, modelo_tipo)
    lista = candidatos.get(key, ['best_model_RF.pkl'])
    for nombre in lista:
        path = directorio / nombre
        if path.exists():
            try:
                with open(path, 'rb') as f:
                    return pickle.load(f), modelo_tipo
            except Exception:
                continue
    # Fallback: primer .pkl disponible
    for archivo in sorted(directorio.glob('*.pkl')):
        try:
            with open(archivo, 'rb') as f:
                return pickle.load(f), modelo_tipo
        except Exception:
            continue
    return None, modelo_tipo


def crear_features_temporales_serie(series, vc=3, vl=5, ve=7):
    """Crea features rolling + EWMA para una serie temporal."""
    features = {}
    series = pd.to_numeric(series, errors='coerce').fillna(0)
    for ventana, nombre in [(vc, "3"), (vl, "5"), (ve, "7")]:
        if len(series) >= ventana:
            features[f"roll{nombre}"] = float(series.tail(ventana).mean())
            features[f"ewma{nombre}"] = float(series.ewm(span=ventana, adjust=False).mean().iloc[-1])
        else:
            val = float(series.mean()) if len(series) > 0 else 0.0
            features[f"roll{nombre}"] = val
            features[f"ewma{nombre}"] = val
    return features


def _predecir_desde_db(jugador_id, posicion_code, jornada_actual=None, verbose=False, modelo_tipo=None):
    """
    Pipeline común para DF, MC, DT:
    1. Carga datos históricos desde BD
    2. Construye features
    3. Predice con modelo RF o devuelve baseline
    4. Genera explicaciones SHAP
    
    Args:
        modelo_tipo: str - 'RF', 'Ridge', 'ElasticNet', 'Baseline' (MC solo), None (usa default)
    """
    _django_setup()
    try:
        from main.models import Jugador, EstadisticasPartidoJugador
    except Exception as e:
        return {'error': f'Django no disponible: {e}', 'jugador_id': jugador_id, 'prediccion': None}

    # Si es baseline para MC, calcular media y retornar
    if modelo_tipo == 'Baseline' and posicion_code == 'MC':
        try:
            if isinstance(jugador_id, int):
                jugador = Jugador.objects.get(id=jugador_id)
                nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
            else:
                nombre_norm = normalizar_nombre(str(jugador_id))
                jugador = None
                for j in Jugador.objects.all():
                    if nombre_norm in normalizar_nombre(f"{j.nombre} {j.apellido}"):
                        jugador = j
                        nombre_jugador = f"{j.nombre} {j.apellido}".strip()
                        break
                if not jugador:
                    return {'error': f'Jugador no encontrado: {jugador_id}', 'jugador_id': jugador_id, 'prediccion': None}
            
            stats_qs = (EstadisticasPartidoJugador.objects
                        .filter(jugador=jugador)
                        .select_related('partido__jornada'))
            
            if not stats_qs.exists():
                return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos históricos'}
            
            if jornada_actual is None:
                jornada_actual = stats_qs.last().partido.jornada.numero_jornada + 1
            jornada_actual = int(jornada_actual)
            
            stats_hist = stats_qs.filter(partido__jornada__numero_jornada__lt=jornada_actual)
            if not stats_hist.exists():
                return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos anteriores'}
            
            media_pts = float(stats_hist.aggregate(media=Avg('puntos_fantasy'))['media'] or 0.0)
            
            puntos_reales = None
            try:
                stat_j = stats_qs.filter(partido__jornada__numero_jornada=jornada_actual).first()
                if stat_j:
                    puntos_reales = stat_j.puntos_fantasy
            except Exception:
                pass
            
            return {
                'status': 'success',
                'jugador_id': jugador_id,
                'posicion': posicion_code,
                'prediccion': round(media_pts, 2),
                'puntos_reales': round(float(puntos_reales), 2) if puntos_reales is not None else None,
                'puntos_reales_texto': f"{round(float(puntos_reales), 2)}" if puntos_reales is not None else "Aún no jugado",
                'jornada': jornada_actual,
                'modelo': 'Baseline (Media)',
                'features_impacto': [],
                'explicacion_texto': f'Media histórica de {media_pts:.2f} pts basada en {stats_hist.count()} partidos anteriores',
                'error': None,
            }
        except Exception as e:
            return {'error': f'Error calculando baseline: {e}', 'jugador_id': jugador_id, 'prediccion': None}

    modelo, tipo_modelo = cargar_modelo(posicion_code, modelo_tipo)
    if modelo is None:
        return {'error': f'Modelo {posicion_code} no disponible', 'jugador_id': jugador_id, 'prediccion': None}
    nombre_modelo_legible = NOMBRE_MODELO_LEGIBLE.get(tipo_modelo, tipo_modelo)

    try:
        # Resolver jugador
        if isinstance(jugador_id, int):
            jugador = Jugador.objects.get(id=jugador_id)
            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        else:
            nombre_norm = normalizar_nombre(str(jugador_id))
            jugador = None
            for j in Jugador.objects.all():
                if nombre_norm in normalizar_nombre(f"{j.nombre} {j.apellido}"):
                    jugador = j
                    nombre_jugador = f"{j.nombre} {j.apellido}".strip()
                    break
            if not jugador:
                return {'error': f'Jugador no encontrado: {jugador_id}', 'jugador_id': jugador_id, 'prediccion': None}

        # Cargar estadísticas
        stats_qs = (EstadisticasPartidoJugador.objects
                    .filter(jugador=jugador)
                    .select_related('partido__jornada', 'partido__equipo_local', 'partido__equipo_visitante')
                    .order_by('partido__jornada__numero_jornada'))

        if not stats_qs.exists():
            return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos históricos'}

        if jornada_actual is None:
            jornada_actual = stats_qs.last().partido.jornada.numero_jornada + 1
        jornada_actual = int(jornada_actual)

        stats_hist = stats_qs.filter(partido__jornada__numero_jornada__lt=jornada_actual)
        if not stats_hist.exists():
            return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos anteriores a esta jornada'}

        # Construir DataFrame
        data = _stats_a_dataframe(stats_hist, nombre_jugador, jugador, posicion_code)
        if not data:
            return {'error': 'Sin datos procesables', 'jugador_id': jugador_id, 'prediccion': None}
        df_hist = pd.DataFrame(data).sort_values('jornada')

    except Exception as e:
        return {'error': f'Error cargando datos BD: {e}', 'jugador_id': jugador_id, 'prediccion': None}

    # Construir features
    try:
        if posicion_code == 'DF':
            features = _construir_features_df(df_hist)
        elif posicion_code == 'MC':
            features = _construir_features_mc(df_hist)
        else:  # DT
            features = _construir_features_dt(df_hist)
    except Exception as e:
        return {'error': f'Error construyendo features: {e}', 'jugador_id': jugador_id, 'prediccion': None}

    # Alinear con el modelo
    try:
        feature_names = list(modelo.feature_names_in_) if hasattr(modelo, 'feature_names_in_') else list(features.keys())
        X_vals = [features.get(fn, 0.0) for fn in feature_names]
        X_df = pd.DataFrame([X_vals], columns=feature_names)

        prediccion = float(modelo.predict(X_df)[0])
        prediccion = max(0.0, prediccion)

        # Puntos reales (si ya se jugó)
        puntos_reales = None
        try:
            stat_j = stats_qs.filter(partido__jornada__numero_jornada=jornada_actual).first()
            if stat_j:
                puntos_reales = stat_j.puntos_fantasy
        except Exception:
            pass

        # Explicaciones SHAP / feature importance
        impacts = generar_explicaciones_shap(modelo, X_df, feature_names, verbose=verbose)
        explicacion_texto = formatear_explicaciones_texto(impacts, prediccion)

        if verbose:
            print(f"✓ {posicion_code} ({nombre_modelo_legible}) {jugador_id} J{jornada_actual}: {prediccion:.2f}pt")

        return {
            'status': 'success',
            'jugador_id': jugador_id,
            'posicion': posicion_code,
            'prediccion': round(prediccion, 2),
            'puntos_reales': round(float(puntos_reales), 2) if puntos_reales is not None else None,
            'puntos_reales_texto': f"{round(float(puntos_reales), 2)}" if puntos_reales is not None else "Aún no jugado",
            'jornada': jornada_actual,
            'modelo': nombre_modelo_legible,
            'features_impacto': impacts[:7],
            'explicacion_texto': explicacion_texto,
            'error': None,
        }

    except Exception as e:
        return {'error': f'Error predicción: {e}', 'jugador_id': jugador_id, 'prediccion': None}


def _stats_a_dataframe(stats_hist, nombre_jugador, jugador, posicion_code):
    """Convierte queryset de EstadisticasPartidoJugador a lista de dicts."""
    data = []
    # Obtener el equipo del último partido del jugador
    last_stat = stats_hist.last()
    ultimo_equipo_id = None
    if last_stat:
        # Determinar si fue local o visitante
        if last_stat.partido.equipo_local.jugadores_temporada.filter(jugador=jugador).exists():
            ultimo_equipo_id = last_stat.partido.equipo_local_id
        elif last_stat.partido.equipo_visitante.jugadores_temporada.filter(jugador=jugador).exists():
            ultimo_equipo_id = last_stat.partido.equipo_visitante_id
        else:
            # Fallback: asumir local
            ultimo_equipo_id = last_stat.partido.equipo_local_id

    for stat in stats_hist:
        partido = stat.partido
        es_local = (partido.equipo_local_id == ultimo_equipo_id)
        row = {
            'player': nombre_jugador,
            'jornada': partido.jornada.numero_jornada,
            'min_partido': stat.min_partido or 0,
            'puntos_fantasy': stat.puntos_fantasy or 0,
            'local': 'Si' if es_local else 'No',
            # Comunes
            'entradas': stat.entradas or 0,
            'intercepciones': 0,
            'despejes': stat.despejes or 0,
            'duelos': stat.duelos or 0,
            'duelos_ganados': stat.duelos_ganados or 0,
            'duelos_perdidos': stat.duelos_perdidos or 0,
            'duelos_aereos_ganados': stat.duelos_aereos_ganados or 0,
            'duelos_aereos_perdidos': stat.duelos_aereos_perdidos or 0,
            'bloqueos': stat.bloqueos or 0,
            # Ofensivos
            'gol_partido': stat.gol_partido or 0,
            'xg_partido': stat.xg_partido or 0,
            'tiros': stat.tiros or 0,
            'tiro_puerta_partido': stat.tiro_puerta_partido or 0,
            'regates': stat.regates or 0,
            'regates_completados': stat.regates_completados or 0,
            'conducciones_progresivas': stat.conducciones_progresivas or 0,
            'metros_avanzados_conduccion': stat.metros_avanzados_conduccion or 0,
            # MC / Comunes
            'pases_totales': stat.pases_totales or 0,
            'pases_completados_pct': stat.pases_completados_pct or 0,
            'conducciones': stat.conducciones or 0,
            'regates_fallidos': stat.regates_fallidos or 0,
            # Portero
            'goles_en_contra': stat.goles_en_contra or 0,
            'porcentaje_paradas': stat.porcentaje_paradas or 0,
            'psxg': stat.psxg or 0,
            # Tarjetas
            'amarillas': stat.amarillas or 0,
            'rojas': stat.rojas or 0,
            # Roles
            'roles': stat.roles if hasattr(stat, 'roles') and stat.roles else [],
        }
        data.append(row)
    return data


# =============================================================================
# FEATURE BUILDERS POR POSICIÓN (DB-based)
# =============================================================================

def _construir_features_df(df_jugador):
    """Construye features para DEFENSA."""
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']

    df_specs = [
        ("entradas", "tackles"), ("despejes", "clearances"),
        ("duelos", "duels"), ("duelos_ganados", "duels_won"),
        ("duelos_perdidos", "duels_lost"), ("bloqueos", "blocks"),
        ("duelos_aereos_ganados", "aerial_won"), ("duelos_aereos_perdidos", "aerial_lost"),
    ]
    for col_csv, prefix in df_specs:
        if col_csv in df_jugador.columns:
            tf = crear_features_temporales_serie(df_jugador[col_csv], vc, vl, ve)
            for k, v in tf.items():
                features[f"{prefix}_{k}"] = v

    if "puntos_fantasy" in df_jugador.columns:
        for k, v in crear_features_temporales_serie(df_jugador["puntos_fantasy"], vc, vl, ve).items():
            features[f"pf_{k}"] = v

    if "min_partido" in df_jugador.columns:
        min_pct = (pd.to_numeric(df_jugador["min_partido"], errors='coerce').fillna(45) / 90).clip(0, 1)
        for k, v in crear_features_temporales_serie(min_pct, vc, vl, ve).items():
            features[f"minutes_pct_{k}"] = v

    num_roles = _get_num_roles(df_jugador)
    features['num_roles'] = float(num_roles)
    features['score_roles_normalizado'] = float(num_roles * 0.1)

    # Features avanzados
    features['defensive_actions_total'] = features.get('tackles_roll5', 0) + features.get('clearances_roll5', 0)
    duel_r5 = features.get('duels_roll5', 0.01)
    features['duel_win_rate'] = min(1.0, features.get('duels_won_roll5', 0) / max(0.01, duel_r5))
    features['defensive_activity'] = (features.get('tackles_roll5', 0)
                                       + features.get('clearances_roll5', 0) * 0.7)
    features['minutes_form_combo'] = features.get('minutes_pct_ewma5', 0) * features.get('pf_roll5', 0) / 10
    features['def_actions_per_90'] = features['defensive_actions_total'] / max(0.01, features.get('minutes_pct_roll5', 0.01))
    features['defensive_consistency'] = 1.0 / (abs(features.get('tackles_roll5', 0) - features.get('tackles_ewma5', 0)) + 1.0)
    features['availability_form'] = features.get('minutes_pct_ewma5', 0) * features.get('pf_roll5', 0) / 10
    features['is_home'] = float(df_jugador.iloc[-1].get('local', 'No') == 'Si')

    return {k: float(0 if (np.isnan(v) or np.isinf(v)) else v) for k, v in features.items()}


def _construir_features_mc(df_jugador):
    """Construye features para MEDIOCAMPISTA."""
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']

    mc_specs = [
        ("pases_totales", "passes"), ("conducciones", "dribbles"),
        ("conducciones_progresivas", "prog_dribbles"),
        ("metros_avanzados_conduccion", "prog_dist"),
        ("regates", "dribble_attempts"), ("regates_completados", "succ_dribbles"),
        ("regates_fallidos", "failed_dribbles"), ("entradas", "tackles"),
        ("pases_clave", "key_passes"),
    ]
    for col_csv, prefix in mc_specs:
        if col_csv in df_jugador.columns:
            for k, v in crear_features_temporales_serie(df_jugador[col_csv], vc, vl, ve).items():
                features[f"{prefix}_{k}"] = v

    if "puntos_fantasy" in df_jugador.columns:
        for k, v in crear_features_temporales_serie(df_jugador["puntos_fantasy"], vc, vl, ve).items():
            features[f"pf_{k}"] = v

    if "min_partido" in df_jugador.columns:
        min_pct = (pd.to_numeric(df_jugador["min_partido"], errors='coerce').fillna(45) / 90).clip(0, 1)
        for k, v in crear_features_temporales_serie(min_pct, vc, vl, ve).items():
            features[f"minutes_pct_{k}"] = v

    num_roles = _get_num_roles(df_jugador)
    features['num_roles'] = float(num_roles)
    features['score_roles_normalizado'] = float(num_roles * 0.15)
    features['es_mediocampista_elite'] = 1.0 if num_roles > 2 else 0.0
    features['tiene_rol_mediocampista_core'] = 1.0 if num_roles > 0 else 0.0
    features['tiene_rol_destacado'] = 1.0 if num_roles > 1 else 0.0

    # Features avanzados MC
    passes_r5 = features.get('passes_roll5', 0)
    pass_comp = features.get('pases_completados_pct_roll5', 50) if 'pases_completados_pct_roll5' in features else 70
    features['pass_efficiency'] = passes_r5 * (pass_comp / 100.0)
    features['offensive_action'] = features.get('dribble_attempts_roll5', 0) + features.get('prog_dribbles_roll5', 0)
    total_drb = features.get('succ_dribbles_roll5', 0) + features.get('failed_dribbles_roll5', 0) + 0.1
    features['dribble_success_rate'] = min(1.0, features.get('succ_dribbles_roll5', 0) / total_drb)
    features['defensive_participation'] = features.get('tackles_roll5', 0)
    features['distance_per_dribble'] = features.get('prog_dist_roll5', 0) / max(0.1, features.get('dribbles_roll5', 0.1))
    features['availability_form'] = features.get('minutes_pct_roll5', 0) * features.get('pf_roll5', 0)
    features['defensive_intensity'] = features.get('tackles_roll5', 0) / max(0.1, features.get('pf_roll5', 0.1))
    features['pass_productivity'] = features.get('pf_roll5', 0) / max(1, features.get('passes_roll5', 1))
    features['is_home'] = float(df_jugador.iloc[-1].get('local', 'No') == 'Si')

    # Features avanzados de feature_improvements (nuevas features del modelo actualizado)
    pf_ser = pd.to_numeric(df_jugador.get('puntos_fantasy', pd.Series([0])), errors='coerce').fillna(0)
    if len(pf_ser) >= 3:
        pf_ewma3 = float(pf_ser.ewm(span=3, adjust=False).mean().iloc[-1])
        pf_ewma5 = float(pf_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        pf_roll5 = float(pf_ser.tail(5).mean())
        features['pf_volatility_mc'] = abs(pf_ewma3 - pf_ewma5) / max(0.1, pf_roll5)
        features['pf_consistency_mc'] = 1.0 / (abs(pf_roll5 - pf_ewma5) + 0.1)
        features['scoring_momentum_mc'] = pf_ewma3 - pf_ewma5  # positivo = tendencia ascendente

    return {k: float(0 if (np.isnan(v) or np.isinf(v)) else v) for k, v in features.items()}


def _construir_features_dt(df_jugador):
    """Construye features para DELANTERO (incluye nuevas features del modelo actualizado)."""
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']

    dt_specs = [
        ("gol_partido", "goals"), ("xg_partido", "xg"),
        ("tiros", "shots"), ("tiro_puerta_partido", "shots_on_target"),
        ("regates", "dribbles"), ("regates_completados", "succ_dribbles"),
        ("conducciones_progresivas", "prog_dribbles"),
        ("metros_avanzados_conduccion", "prog_dist"),
        ("pases_clave", "key_passes"), ("entradas", "tackles"),
    ]
    for col_csv, prefix in dt_specs:
        if col_csv in df_jugador.columns:
            for k, v in crear_features_temporales_serie(df_jugador[col_csv], vc, vl, ve).items():
                features[f"{prefix}_{k}"] = v

    if "puntos_fantasy" in df_jugador.columns:
        for k, v in crear_features_temporales_serie(df_jugador["puntos_fantasy"], vc, vl, ve).items():
            features[f"pf_{k}"] = v

    if "min_partido" in df_jugador.columns:
        min_pct = (pd.to_numeric(df_jugador["min_partido"], errors='coerce').fillna(45) / 90).clip(0, 1)
        for k, v in crear_features_temporales_serie(min_pct, vc, vl, ve).items():
            features[f"minutes_pct_{k}"] = v

    num_roles = _get_num_roles(df_jugador)
    features['num_roles'] = float(num_roles)
    features['score_roles_normalizado'] = float(num_roles * 0.2)
    features['es_delantero_elite'] = 1.0 if num_roles > 2 else 0.0
    features['tiene_rol_delantero_core'] = 1.0 if num_roles > 0 else 0.0

    # Features avanzados básicos (del modelo anterior)
    xg_r5 = features.get('xg_roll5', 0.01)
    goals_r5 = features.get('goals_roll5', 0)
    shots_r5 = features.get('shots_roll5', 0.1)
    shots_ot = features.get('shots_on_target_roll5', 0)
    min_pct_r5 = features.get('minutes_pct_roll5', 0.1)
    pf_r5 = features.get('pf_roll5', 1)

    features['shot_efficiency'] = max(0, goals_r5 / max(0.01, xg_r5))
    features['shot_accuracy'] = min(1.0, shots_ot / max(0.1, shots_r5))
    features['offensive_threat'] = shots_r5 + features.get('succ_dribbles_roll5', 0) * 0.5
    features['offensive_form'] = goals_r5 + xg_r5
    features['progressive_pressure'] = max(0, features.get('prog_dribbles_roll5', 0)
                                            + features.get('prog_dist_roll5', 0) / 10)
    features['goal_productivity'] = goals_r5 / max(1, pf_r5)
    features['availability_form'] = min_pct_r5 * pf_r5
    features['availability_threat'] = min_pct_r5 * shots_r5
    features['creativity'] = features.get('key_passes_roll5', 0) / max(1, len(df_jugador))
    features['is_home'] = float(df_jugador.iloc[-1].get('local', 'No') == 'Si')

    # ── NUEVAS FEATURES del modelo actualizado (crear_features_fantasy_delantero) ──
    goals_ser = pd.to_numeric(df_jugador.get('gol_partido', pd.Series([0])), errors='coerce').fillna(0)
    xg_ser    = pd.to_numeric(df_jugador.get('xg_partido',  pd.Series([0])), errors='coerce').fillna(0)
    shots_ser = pd.to_numeric(df_jugador.get('tiros',       pd.Series([0])), errors='coerce').fillna(0)
    min_ser   = pd.to_numeric(df_jugador.get('min_partido', pd.Series([45])), errors='coerce').fillna(45)
    pf_ser    = pd.to_numeric(df_jugador.get('puntos_fantasy', pd.Series([0])), errors='coerce').fillna(0)
    prog_drb  = pd.to_numeric(df_jugador.get('conducciones_progresivas', pd.Series([0])), errors='coerce').fillna(0)
    prog_dist = pd.to_numeric(df_jugador.get('metros_avanzados_conduccion', pd.Series([0])), errors='coerce').fillna(0)

    if len(goals_ser) >= 1:
        # xg_overperformance: goles - xG (ratio sobre/bajo rendimiento)
        goals_r5_s = float(goals_ser.tail(5).mean())
        xg_r5_s    = float(xg_ser.tail(5).mean())
        features['xg_overperformance'] = goals_r5_s - xg_r5_s

        # shot_conversion_ewma5
        shots_e5 = float(shots_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        goals_e5 = float(goals_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        features['shot_conversion_ewma5'] = goals_e5 / max(0.1, shots_e5)

        # offensive_pressure_score
        features['offensive_pressure_score'] = shots_r5 * 0.4 + xg_r5 * 0.6

        # scoring_stability (roll5 vs ewma5 consistency)
        goals_e5_val = float(goals_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        goals_r5_val = float(goals_ser.tail(5).mean())
        features['scoring_stability'] = 1.0 / (abs(goals_r5_val - goals_e5_val) + 0.1)

        # xg_per_minute_ewma
        min_e5 = float(min_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        xg_e5  = float(xg_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        features['xg_per_minute_ewma'] = xg_e5 / max(1.0, min_e5)

        # goals_per_minute_ewma
        features['goals_per_minute_ewma'] = goals_e5 / max(1.0, min_e5)

        # progressive_threat (prog_dribbles + prog_dist)
        prog_drb_e5 = float(prog_drb.ewm(span=5, adjust=False).mean().iloc[-1])
        prog_dist_e5 = float(prog_dist.ewm(span=5, adjust=False).mean().iloc[-1])
        features['progressive_threat'] = prog_drb_e5 + prog_dist_e5 / 10

        # scoring_momentum (ewma3 vs ewma5 para goles)
        goals_e3 = float(goals_ser.ewm(span=3, adjust=False).mean().iloc[-1]) if len(goals_ser) >= 3 else goals_e5
        features['scoring_momentum'] = goals_e3 - goals_e5

        # xg_momentum
        xg_e3 = float(xg_ser.ewm(span=3, adjust=False).mean().iloc[-1]) if len(xg_ser) >= 3 else xg_e5
        features['xg_momentum'] = xg_e3 - xg_e5

        # pf_volatility_fw y pf_consistency_fw
        pf_r5_val = float(pf_ser.tail(5).mean())
        pf_e5_val = float(pf_ser.ewm(span=5, adjust=False).mean().iloc[-1])
        pf_std    = float(pf_ser.tail(5).std()) if len(pf_ser) >= 3 else 0.0
        features['pf_volatility_fw'] = pf_std / max(0.1, pf_r5_val)
        features['pf_consistency_fw'] = 1.0 / (abs(pf_r5_val - pf_e5_val) + 0.1)

    return {k: float(0 if (np.isnan(v) or np.isinf(v)) else v) for k, v in features.items()}


def _get_num_roles(df_jugador):
    """Obtiene el número de roles del último registro."""
    try:
        roles_val = df_jugador.iloc[-1].get('roles', [])
        if isinstance(roles_val, list):
            return len(roles_val)
        if isinstance(roles_val, str) and roles_val:
            import json
            return len(json.loads(roles_val))
    except Exception:
        pass
    return 0


# =============================================================================
# PORTERO: Lógica CSV-based (mantenida por complejidad)
# =============================================================================

_CSV_PORTERO_CACHE = None  # cache simple

def _cargar_csv_portero():
    """Carga y filtra porteros del CSV."""
    global _CSV_PORTERO_CACHE
    if _CSV_PORTERO_CACHE is not None:
        return _CSV_PORTERO_CACHE
    try:
        df = pd.read_csv(CONFIG['archivo_csv'], encoding='utf-8-sig', on_bad_lines='skip')
        temp_cols = [c for c in df.columns if 'temporada' in c.lower()]
        if temp_cols:
            df = df[df[temp_cols[0]] == '25_26'].copy()
        pos_cols = [c for c in df.columns if 'posicion' in c.lower()]
        if pos_cols:
            df_pt = df[df[pos_cols[0]].str.upper().isin(['PT', 'GK'])].copy()
        else:
            df_pt = df.copy()
        _CSV_PORTERO_CACHE = (df_pt, df)
        return df_pt, df
    except Exception as e:
        print(f"[WARNING] No se pudo cargar CSV portero: {e}")
        return None, None


def _predecir_portero(jugador_id, jornada_actual=None, verbose=False):
    """
    Predicción de portero usando CSV (lógica extraída de predecir_portero.py).
    """
    modelo, tipo_modelo_pt = cargar_modelo('PT')
    if modelo is None:
        return {'error': 'Modelo PT no disponible', 'jugador_id': jugador_id, 'prediccion': None}
    nombre_modelo_pt = NOMBRE_MODELO_LEGIBLE.get(tipo_modelo_pt, tipo_modelo_pt)

    df_pt, df_todos = _cargar_csv_portero()
    if df_pt is None:
        return {'error': 'CSV portero no disponible', 'jugador_id': jugador_id, 'prediccion': None}

    # Resolver nombre del jugador
    if isinstance(jugador_id, int):
        _django_setup()
        try:
            from main.models import Jugador
            jug = Jugador.objects.get(id=jugador_id)
            nombre = f"{jug.nombre} {jug.apellido}".strip()
        except Exception as e:
            return {'error': f'Jugador ID no encontrado: {e}', 'jugador_id': jugador_id, 'prediccion': None}
    else:
        nombre = str(jugador_id)

    # Buscar en CSV
    mask = df_pt['player'] == nombre
    if not mask.any():
        mask = df_pt['player'].str.contains(nombre, case=False, na=False, regex=False)
    if not mask.any():
        norm = normalizar_nombre(nombre)
        df_copia = df_pt.copy()
        df_copia['_norm'] = df_copia['player'].apply(normalizar_nombre)
        mask = df_copia['_norm'].str.contains(norm, na=False, regex=False)
        if mask.any():
            df_pt = df_copia

    if not mask.any():
        return {'error': f'Portero no encontrado en CSV: {nombre}', 'jugador_id': jugador_id, 'prediccion': None}

    registros = df_pt[mask].sort_values('jornada')

    if jornada_actual is None:
        jornada_actual = int(registros['jornada'].max()) + 1
    jornada_actual = int(jornada_actual)

    hist = registros[registros['jornada'] < jornada_actual]
    if len(hist) < 3:
        media = float(pd.to_numeric(hist['puntos_fantasy'], errors='coerce').mean() or 8.0)
        return {
            'jugador_id': jugador_id, 'posicion': 'PT',
            'prediccion': round(media, 2), 'jornada': jornada_actual,
            'modelo': 'Media (sin datos suficientes)', 'error': None,
            'features_impacto': [], 'explicacion_texto': 'Datos insuficientes'
        }

    # Construir features portero desde CSV
    features = _construir_features_pt_csv(hist, df_pt, jornada_actual)

    try:
        feature_names = list(modelo.feature_names_in_) if hasattr(modelo, 'feature_names_in_') else list(features.keys())
        X_vals = [features.get(fn, 0.0) for fn in feature_names]
        X_df = pd.DataFrame([X_vals], columns=feature_names)

        prediccion = float(modelo.predict(X_df)[0])
        prediccion = max(0.0, prediccion)

        # Puntos reales
        puntos_reales = None
        reg_j = registros[registros['jornada'] == jornada_actual]
        if len(reg_j) > 0:
            pts_col = [c for c in df_pt.columns if 'puntos' in c.lower()]
            if pts_col:
                puntos_reales = pd.to_numeric(reg_j.iloc[0][pts_col[0]], errors='coerce')
                puntos_reales = float(puntos_reales) if not pd.isna(puntos_reales) else None

        impacts = generar_explicaciones_shap(modelo, X_df, feature_names, verbose=verbose)
        explicacion_texto = formatear_explicaciones_texto(impacts, prediccion)

        if verbose:
            print(f"✓ PT ({nombre_modelo_pt}) {jugador_id} J{jornada_actual}: {prediccion:.2f}pt")

        return {
            'status': 'success',
            'jugador_id': jugador_id,
            'posicion': 'PT',
            'prediccion': round(prediccion, 2),
            'puntos_reales': round(puntos_reales, 2) if puntos_reales is not None else None,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'jornada': jornada_actual,
            'modelo': nombre_modelo_pt,
            'features_impacto': impacts[:7],
            'explicacion_texto': explicacion_texto,
            'error': None,
        }
    except Exception as e:
        return {'error': f'Error predicción PT: {e}', 'jugador_id': jugador_id, 'prediccion': None}


def _construir_features_pt_csv(hist, df_pt, jornada_actual):
    """Construye features para portero desde CSV histórico."""
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']

    cols_pt = [
        ('porcentaje_paradas', 'save_pct'), ('psxg', 'psxg'),
        ('goles_en_contra', 'goles_contra'), ('pases_completados_pct', 'pass_comp_pct'),
    ]
    for col_csv, prefix in cols_pt:
        if col_csv in hist.columns:
            for k, v in crear_features_temporales_serie(hist[col_csv], vc, vl, ve).items():
                features[f"{prefix}_{k}"] = v

    if 'puntos_fantasy' in hist.columns:
        for k, v in crear_features_temporales_serie(hist['puntos_fantasy'], vc, vl, ve).items():
            features[f"pf_{k}"] = v

    if 'min_partido' in hist.columns:
        min_pct = (pd.to_numeric(hist['min_partido'], errors='coerce').fillna(45) / 90).clip(0, 1)
        for k, v in crear_features_temporales_serie(min_pct, vc, vl, ve).items():
            features[f"minutes_pct_{k}"] = v

    # Features compuestos portero
    save_pct_r5 = features.get('save_pct_roll5', 0)
    psxg_r5 = features.get('psxg_roll5', 0)
    psxg_e5 = features.get('psxg_ewma5', 0)
    pf_r5 = features.get('pf_roll5', 0)
    pf_e5 = features.get('pf_ewma5', 0)
    min_pct_r5 = features.get('minutes_pct_roll5', 1)
    min_pct_e5 = features.get('minutes_pct_ewma5', 1)

    features['total_strength'] = np.clip((save_pct_r5 / 100) + 1 / (psxg_r5 + 0.5), 0, 5)
    features['defensive_combo'] = (save_pct_r5 / 100) * (1 / (psxg_r5 + 0.5))
    features['save_advantage'] = np.clip(1 / (psxg_r5 + 0.5), 0, 5)
    features['weak_opponent'] = features.get('goles_contra_roll5', 0) / 2.0
    features['momentum_factor'] = np.clip(pf_e5 / (pf_r5 + 0.1), 0.5, 2.0)
    features['minutes_form_combo'] = min_pct_e5 * pf_r5 / 10
    features['availability_form'] = min_pct_r5 * pf_e5 / 10

    # Rival features (calcula correctamente sin caer en 0.5 de fallback)
    equipo = hist.iloc[-1].get('equipo_propio', '')
    rival_data = df_pt[
        (df_pt['equipo_propio'] == equipo) &
        (df_pt['jornada'] == jornada_actual)
    ]
    rival = rival_data.iloc[0]['equipo_rival'] if len(rival_data) > 0 else ''
    
    # Valores por defecto
    opp_gf_vals = []
    opp_gc_vals = []
    
    if rival:
        rival_hist = df_pt[(df_pt['equipo_propio'] == rival) & (df_pt['jornada'] < jornada_actual)].tail(10)
        if len(rival_hist) > 0:
            # Extraer goles anotados y encajados del rival
            gf_col = [c for c in rival_hist.columns if 'gf' in c.lower()]
            gc_col = [c for c in rival_hist.columns if 'gc' in c.lower()]
            
            if gf_col:
                opp_gf_vals = pd.to_numeric(rival_hist[gf_col[0]], errors='coerce').fillna(0).tolist()
            if gc_col:
                opp_gc_vals = pd.to_numeric(rival_hist[gc_col[0]], errors='coerce').fillna(0).tolist()
    
    # Fallback a valores neutros si no hay datos
    if not opp_gf_vals:
        opp_gf_vals = [1.2] * 5
    if not opp_gc_vals:
        opp_gc_vals = [1.2] * 5
    
    features['opp_gf_roll5'] = float(np.mean(opp_gf_vals[-5:]) if len(opp_gf_vals) > 0 else 1.2)
    features['opp_gc_roll5'] = float(np.mean(opp_gc_vals[-5:]) if len(opp_gc_vals) > 0 else 1.2)
    
    # Calcular opp_form real desde data (no 0.5 fallback)
    # Form = (goles_a - goles_c) / partidos, normalizado a [0, 1] rango
    if len(opp_gf_vals) >= 5 and len(opp_gc_vals) >= 5:
        # Últimos 5 partidos del rival
        gf_5 = sum(opp_gf_vals[-5:])
        gc_5 = sum(opp_gc_vals[-5:])
        # Form como diferencia de goles normalizada
        form_roll5_raw = (gf_5 - gc_5) / len(opp_gf_vals[-5:])
        # Normalizar a rango [0, 1] con media 0.5
        features['opp_form_roll5'] = np.clip(0.5 + (form_roll5_raw / 5.0), 0.0, 1.0)
        
        # Últimos 3 partidos para ewma5 (aproximado)
        gf_3 = sum(opp_gf_vals[-3:]) if len(opp_gf_vals) >= 3 else gf_5
        gc_3 = sum(opp_gc_vals[-3:]) if len(opp_gc_vals) >= 3 else gc_5
        form_ewma5_raw = (gf_3 - gc_3) / len(opp_gf_vals[-3:])
        features['opp_form_ewma5'] = np.clip(0.5 + (form_ewma5_raw / 5.0), 0.0, 1.0)
    else:
        # Fallback mínimo pero informado
        features['opp_form_roll5'] = 0.5
        features['opp_form_ewma5'] = 0.5

    # CS features
    features['cs_probability'] = max(0.0, 1.0 - (features['opp_gc_roll5'] / 3.0))
    features['cs_expected_points'] = features['cs_probability'] * 6.0
    features['expected_gk_core_points'] = psxg_e5 * 0.5 + features['cs_expected_points'] * 0.7 + pf_e5 * 0.1

    # Odds (neutros)
    features['odds_prob_win'] = 0.33
    features['odds_prob_loss'] = 0.33
    features['odds_expected_goals_against'] = features['opp_gf_roll5'] / 3.0
    features['odds_is_favored'] = 0
    features['odds_market_confidence'] = 0.33

    # Roles
    num_roles = _get_num_roles(hist)
    features['num_roles_criticos'] = float(num_roles)
    features['num_roles_positivos'] = float(num_roles // 2)
    features['num_roles_negativos'] = float(num_roles // 3)
    features['ratio_roles_positivos'] = features['num_roles_positivos'] / max(1, num_roles)
    features['score_roles_normalizado'] = (save_pct_r5 / 100) * min_pct_r5 * max(1, num_roles) / 10

    # Misceláneos
    features['is_home'] = float(hist.iloc[-1].get('local', 1) == 1 or hist.iloc[-1].get('local', 'No') == 'Si')
    features['starter_pct_roll5'] = min_pct_r5
    features['save_pct_power2'] = (save_pct_r5 ** 2) / 10000
    features['form_ratio'] = np.clip(pf_e5 / (pf_r5 + 0.1), 0.5, 2.0)
    features['save_per_90_ewma5'] = psxg_e5 * min_pct_e5
    features['psxg_per_90_ewma5'] = psxg_e5

    return {k: float(0 if (np.isnan(v) or np.isinf(v)) else v) for k, v in features.items()}


# =============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# =============================================================================

_POSICION_MAP = {
    'PT': 'PT', 'PORTERO': 'PT', 'GK': 'PT', 'GOALKEEPER': 'PT',
    'DF': 'DF', 'DEFENSA': 'DF', 'DEFENSOR': 'DF', 'DEFENDER': 'DF',
    'MC': 'MC', 'CENTROCAMPISTA': 'MC', 'MEDIOCAMPISTA': 'MC', 'MF': 'MC',
    'DT': 'DT', 'DELANTERO': 'DT', 'FW': 'DT', 'ST': 'DT', 'FORWARD': 'DT',
}


def predecir_puntos(jugador_id, posicion, jornada_actual=None, verbose=False, modelo_tipo=None):
    """
    Punto de entrada unificado para predecir puntos fantasy.

    Args:
        jugador_id: int (ID BD) o str (nombre del jugador)
        posicion: str - 'PT','DF','MC','DT' o nombres completos españoles/ingleses
        jornada_actual: int (opcional; si None usa la última disponible + 1)
        verbose: bool - mostrar info detallada
        modelo_tipo: str - 'RF', 'Ridge', 'ElasticNet', 'Baseline' (MC solo), None (usa default)

    Returns:
        dict con keys:
            status, jugador_id, posicion, prediccion, puntos_reales,
            puntos_reales_texto, jornada, modelo,
            features_impacto, explicacion_texto, error
    """
    pos_code = _POSICION_MAP.get(posicion.upper(), posicion.upper())

    if pos_code == 'PT':
        return _predecir_portero(jugador_id, jornada_actual, verbose)
    elif pos_code == 'DF':
        return _predecir_desde_db(jugador_id, 'DF', jornada_actual, verbose, modelo_tipo)
    elif pos_code == 'MC':
        return _predecir_desde_db(jugador_id, 'MC', jornada_actual, verbose, modelo_tipo)
    elif pos_code == 'DT':
        return _predecir_desde_db(jugador_id, 'DT', jornada_actual, verbose, modelo_tipo)
    else:
        return {
            'error': f'Posición no reconocida: {posicion}',
            'jugador_id': jugador_id,
            'prediccion': None,
        }


# Backward-compatible aliases
def predecir_puntos_portero(jugador_id, jornada_actual=None, verbose=False, modelo_tipo='RF'):
    return predecir_puntos(jugador_id, 'PT', jornada_actual, verbose)

def predecir_puntos_defensa(jugador_id, jornada_actual=None, verbose=False):
    return predecir_puntos(jugador_id, 'DF', jornada_actual, verbose)

def predecir_puntos_mediocampista(jugador_id, jornada_actual=None, verbose=False):
    return predecir_puntos(jugador_id, 'MC', jornada_actual, verbose)

def predecir_puntos_delantero(jugador_id, jornada_actual=None, verbose=False):
    return predecir_puntos(jugador_id, 'DT', jornada_actual, verbose)

def explicar_prediccion_portero(jugador_id, jornada_actual=None, modelo_tipo='RF'):
    return predecir_puntos(jugador_id, 'PT', jornada_actual, verbose=True)


# =============================================================================
# EJECUCIÓN DIRECTA
# =============================================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Predictor Fantasy unificado')
    parser.add_argument('--jugador', required=True, help='Nombre o ID del jugador')
    parser.add_argument('--posicion', required=True, help='PT/DF/MC/DT')
    parser.add_argument('--jornada', type=int, default=None)
    args = parser.parse_args()

    resultado = predecir_puntos(args.jugador, args.posicion, args.jornada, verbose=True)
    print(f"\nPredicción: {resultado.get('prediccion')} pts")
    print(f"Explicación:\n{resultado.get('explicacion_texto', '')}")
