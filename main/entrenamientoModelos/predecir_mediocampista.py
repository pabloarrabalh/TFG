"""
PREDICCIÓN DE MEDIOCAMPISTAS - v4 CON FEATURE ENGINEERING
==========================================================
Lee datos de la BD de Django en lugar de CSV
Calcula los features que el modelo espera a partir de datos brutos.
Replicando la lógica de entrenar-modelo-mediocampista.py
"""

import pickle
import warnings
import unicodedata
import numpy as np
import pandas as pd
from pathlib import Path
import os
import sys
import django

warnings.filterwarnings("ignore")

# Setup Django
if not django.apps.apps.ready:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from main.models import Jugador, EstadisticasPartidoJugador, Jornada, Temporada
from explicaciones_posiciones import generar_explicaciones_features

DIRECTORIO_MODELOS = Path(__file__).parent.parent.parent / "csv/csvGenerados/entrenamiento/mediocampista/modelos"

CONFIG = {
    'ventana_corta': 3,
    'ventana_larga': 5,
    'ventana_extra': 7,
}


def normalizar_nombre(nombre):
    if not isinstance(nombre, str):
        nombre = str(nombre)
    nfd = unicodedata.normalize('NFD', nombre)
    sin_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return sin_acentos.lower().strip()


def cargar_modelo_rf():
    """Carga el modelo RF de mediocampistas."""
    try:
        for nombre in ["best_model_mc_rf.pkl", "best_model_rf.pkl", "best_model_mediocampista_rf.pkl"]:
            path = DIRECTORIO_MODELOS / nombre
            if path.exists():
                with open(path, 'rb') as f:
                    return pickle.load(f)
        for archivo in DIRECTORIO_MODELOS.glob("*.pkl"):
            with open(archivo, 'rb') as f:
                return pickle.load(f)
        return None
    except Exception as e:
        print(f"[ERROR] Cargando modelo MC: {e}")
        return None


def crear_features_temporales_serie(series, ventana_corta=3, ventana_larga=5, ventana_extra=7):
    """Crea features temporales para una serie única."""
    features = {}
    series = pd.to_numeric(series, errors='coerce').fillna(0)
    
    for ventana, nombre in [(ventana_corta, "3"), (ventana_larga, "5"), (ventana_extra, "7")]:
        if len(series) >= ventana:
            features[f"roll{nombre}"] = float(series.tail(ventana).mean())
            features[f"ewma{nombre}"] = float(series.ewm(span=ventana, adjust=False).mean().iloc[-1])
        else:
            features[f"roll{nombre}"] = float(series.mean()) if len(series) > 0 else 0.0
            if len(series) > 1:
                features[f"ewma{nombre}"] = float(series.ewm(span=ventana, adjust=False).mean().iloc[-1])
            else:
                features[f"ewma{nombre}"] = float(series.mean()) if len(series) > 0 else 0.0
    
    return features


def construir_features_mediocampista_completos(df_jugador):
    """Construye todos los features que el modelo MC espera."""
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    # Features básicos mediocampistas
    mc_specs = [
        ("pases_totales", "passes"),
        ("pases_completados_pct", "pass_comp_pct"),
        ("conducciones", "dribbles"),
        ("conducciones_progresivas", "prog_dribbles"),
        ("metros_avanzados_conduccion", "prog_dist"),
        ("regates", "dribble_attempts"),
        ("regates_completados", "succ_dribbles"),
        ("regates_fallidos", "failed_dribbles"),
        ("entradas", "tackles"),
        ("intercepciones", "intercepts"),
    ]
    
    for col_csv, col_prefix in mc_specs:
        if col_csv in df_jugador.columns:
            series = df_jugador[col_csv].copy()
            temporal_features = crear_features_temporales_serie(series, vc, vl, ve)
            for temporal_name, valor in temporal_features.items():
                features[f"{col_prefix}_{temporal_name}"] = valor
    
    # Features de forma (puntos fantasy)
    if "puntos_fantasy" in df_jugador.columns:
        series_pf = df_jugador["puntos_fantasy"].copy()
        temporal_features = crear_features_temporales_serie(series_pf, vc, vl, ve)
        for temporal_name, valor in temporal_features.items():
            features[f"pf_{temporal_name}"] = valor
    
    # Features de disponibilidad
    if "min_partido" in df_jugador.columns:
        min_series = pd.to_numeric(df_jugador["min_partido"], errors='coerce').fillna(45)
        min_pct = (min_series / 90.0).clip(0, 1)
        temporal_features = crear_features_temporales_serie(min_pct, vc, vl, ve)
        for temporal_name, valor in temporal_features.items():
            features[f"minutes_pct_{temporal_name}"] = valor
    
    # Features de roles
    num_roles = len(df_jugador.iloc[-1].get('roles', [])) if 'roles' in df_jugador.columns and df_jugador.iloc[-1].get('roles') else 0
    features['num_roles'] = float(num_roles)
    features['score_roles'] = float(num_roles * 0.15) if num_roles > 0 else 0.0
    
    # Features binarios de rol
    features['es_mediocampista_elite'] = 1.0 if num_roles > 2 else 0.0
    features['tiene_rol_mediocampista_core'] = 1.0 if num_roles > 0 else 0.0
    features['tiene_rol_destacado'] = 1.0 if num_roles > 1 else 0.0
    
    # Features avanzados para MC
    # Pass efficiency
    passes_roll5 = features.get('passes_roll5', 0)
    pass_comp = features.get('pass_comp_pct_roll5', 50)
    features['pass_efficiency'] = (passes_roll5 * (pass_comp / 100.0)) if passes_roll5 > 0 else 0.0
    
    # Offensive action
    features['offensive_action'] = features.get('dribble_attempts_roll5', 0) + features.get('prog_dribbles_roll5', 0)
    
    # Dribble success rate
    total_dribbles = features.get('succ_dribbles_roll5', 0) + features.get('failed_dribbles_roll5', 0) + 0.1
    features['dribble_success_rate'] = min(1.0, features.get('succ_dribbles_roll5', 0) / total_dribbles)
    
    # Defensive participation
    features['defensive_participation'] = features.get('tackles_roll5', 0) + features.get('intercepts_roll5', 0)
    
    # Distance per dribble
    dribbles_roll5 = features.get('dribbles_roll5', 0.1)
    features['distance_per_dribble'] = (features.get('prog_dist_roll5', 0) / max(0.1, dribbles_roll5))
    
    # Availability form
    features['availability_form'] = features.get('minutes_pct_roll5', 0) * features.get('pf_roll5', 0)
    
    # Defensive intensity
    pf_roll5 = features.get('pf_roll5', 0.1)
    features['defensive_intensity'] = features.get('tackles_roll5', 0) / max(0.1, pf_roll5)
    
    # Pass productivity
    passes_roll5 = features.get('passes_roll5', 1)
    features['pass_productivity'] = (features.get('pf_roll5', 0) / max(1, passes_roll5))
    
    # Context features
    features['is_home'] = 1.0 if df_jugador.iloc[-1].get('local') == 'Si' else 0.0
    
    # Limpiar
    features = {k: float(0 if (pd.isna(v) or np.isinf(v)) else v) for k, v in features.items()}
    
    return features


def predecir_puntos_mediocampista(jugador_id, jornada_actual=None, verbose=False):
    """Predice puntos fantasy para un mediocampista desde datos de BD."""
    
    modelo = cargar_modelo_rf()
    if modelo is None:
        return {'error': 'Modelo no disponible', 'jugador_id': jugador_id, 'prediccion': None}
    
    try:
        # Obtener jugador (por ID o por nombre)
        if isinstance(jugador_id, int):
            jugador = Jugador.objects.get(id=jugador_id)
            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        else:
            # Búsqueda por nombre aproximada
            nombre_norm = normalizar_nombre(str(jugador_id))
            jugadores = Jugador.objects.all()
            jugador = None
            for j in jugadores:
                j_norm = normalizar_nombre(f"{j.nombre} {j.apellido}")
                if nombre_norm in j_norm or j_norm in nombre_norm:
                    jugador = j
                    nombre_jugador = f"{j.nombre} {j.apellido}".strip()
                    break
            if not jugador:
                return {'error': f'Jugador no encontrado: {jugador_id}', 'jugador_id': jugador_id, 'prediccion': None}
        
        # Obtener estadísticas del jugador desde BD
        stats_query = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador
        ).select_related('partido__jornada').order_by('partido__jornada__numero_jornada')
        
        if not stats_query.exists():
            return {'error': 'Sin datos históricos', 'jugador_id': jugador_id, 'prediccion': None}
        
        # Determinar jornada
        if jornada_actual is None:
            jornada_actual = stats_query.last().partido.jornada.numero_jornada + 1
        jornada_actual = int(jornada_actual)
        
        # Filtrar registros ANTES de la jornada actual
        registros_hist = stats_query.filter(
            partido__jornada__numero_jornada__lt=jornada_actual
        )
        
        if not registros_hist.exists():
            return {'error': 'Sin datos históricos para esta jornada', 'jugador_id': jugador_id, 'prediccion': None}
        
        # Construir DataFrame desde BD
        data = []
        for stat in registros_hist:
            data.append({
                'player': nombre_jugador,
                'posicion': stat.posicion if stat.posicion else 'MC',
                'jornada': stat.partido.jornada.numero_jornada,
                'min_partido': stat.min_partido or 0,
                'puntos_fantasy': stat.puntos_fantasy or 0,
                'pases': stat.pases_totales or 0,
                'prog_dribbles': stat.conducciones_progresivas or 0,
                'prog_dist': stat.metros_avanzados_conduccion or 0,
                'dribbles': stat.regates_completados or 0,
                'tackles': stat.entradas or 0,
                'intercepts': 0,  # No está en modelo
                'duels': stat.duelos or 0,
            })
        
        if not data:
            return {'error': 'No hay datos para procesar', 'jugador_id': jugador_id, 'prediccion': None}
        
        df_mcs = pd.DataFrame(data)
    
    except Exception as e:
        return {'error': f'Error cargando datos: {e}', 'jugador_id': jugador_id, 'prediccion': None}
    
    # Buscar jugador en el DataFrame
    mask = df_mcs['player'] == nombre_jugador
    
    if not mask.any():
        return {'error': f'Jugador no encontrado en datos', 'jugador_id': jugador_id, 'prediccion': None}
    
    registros = df_mcs[mask].sort_values('jornada')
    registros_hist = registros[registros['jornada'] < jornada_actual]
    
    if len(registros_hist) == 0:
        return {'error': 'Sin datos históricos', 'jugador_id': jugador_id, 'prediccion': None}
    
    try:
        features = construir_features_mediocampista_completos(registros_hist)
        
        if not hasattr(modelo, 'feature_names_in_'):
            return {'error': 'Modelo sin feature_names', 'jugador_id': jugador_id, 'prediccion': None}
        
        feature_names = list(modelo.feature_names_in_)
        
        X = []
        features_encontrados = 0
        for feat_name in feature_names:
            if feat_name in features:
                X.append(float(features[feat_name]))
                features_encontrados += 1
            else:
                X.append(0.0)
        
        if features_encontrados < len(feature_names) * 0.3:
            if verbose:
                print(f"[WARNING] Solo {features_encontrados}/{len(feature_names)} features encontrados")
        
        X_array = np.array(X).reshape(1, -1)
        prediccion = float(modelo.predict(X_array)[0])
        prediccion = max(0, prediccion)
        
        # Obtener puntos reales de la jornada a predecir
        puntos_reales = None
        try:
            registros_jornada = registros[registros['jornada'] == jornada_actual]
            if len(registros_jornada) > 0:
                puntos_reales = float(registros_jornada.iloc[0]['puntos_fantasy'])
        except:
            pass
        
        # Generar explicaciones basadas en features usados con impacto numérico
        explicaciones_dict = generar_explicaciones_features(
            features, 
            feature_names,  # Todos los features
            posicion='MC',
            modelo=modelo,
            prediccion_base=prediccion
        )
        
        if verbose:
            print(f"✓ MC {jugador_id} J{jornada_actual}: {prediccion:.2f}pt ({features_encontrados} features)")
        
        return {
            'status': 'success',
            'jugador_id': jugador_id,
            'posicion': 'MC',
            'prediccion': round(prediccion, 2),
            'puntos_reales': puntos_reales,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'jornada': jornada_actual,
            'modelo': 'Random Forest',
            'features_usados': features_encontrados,
            'features_impacto': explicaciones_dict.get('features_impacto', []),
            'explicacion_texto': explicaciones_dict.get('explicacion_texto', ''),
            'error': None
        }
    
    except Exception as e:
        if verbose:
            print(f"[ERROR] {str(e)}")
        return {'error': f'Error: {str(e)}', 'jugador_id': jugador_id, 'prediccion': None}


if __name__ == '__main__':
    resultado = predecir_puntos_mediocampista('Aaron', jornada_actual=8, verbose=True)
    print(resultado)
