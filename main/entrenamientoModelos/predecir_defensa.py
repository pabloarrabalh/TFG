"""
PREDICCIÓN DE DEFENSAS - v4 CON FEATURE ENGINEERING
=====================================================
Lee datos de la BD de Django en lugar de CSV
Calcula los features que el modelo espera a partir de datos brutos.
Replicando la lógica de entrenar-modelo-defensa.py
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
from explicaciones_unificadas import generar_explicaciones_features, preparar_features_para_explicaciones

DIRECTORIO_MODELOS = Path(__file__).parent.parent.parent / "csv/csvGenerados/entrenamiento/defensa/modelos"

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
    """Carga el modelo RF de defensas."""
    try:
        for nombre in ["best_model_RF.pkl", "best_model_rf.pkl", "best_model_defensa_rf.pkl"]:
            path = DIRECTORIO_MODELOS / nombre
            if path.exists():
                with open(path, 'rb') as f:
                    return pickle.load(f)
        for archivo in DIRECTORIO_MODELOS.glob("*.pkl"):
            with open(archivo, 'rb') as f:
                return pickle.load(f)
        return None
    except Exception as e:
        print(f"[ERROR] Cargando modelo DF: {e}")
        return None


def crear_features_temporales_serie(series, ventana_corta=3, ventana_larga=5, ventana_extra=7):
    """
    Crea features temporales (rolling + EWMA) para una SERIE DE DATOS ÚNICA.
    Replicado de crear_features_temporales() en entrenar-modelo-defensa.py
    
    Args:
        series: pandas Series con valores históricos del jugador
        
    Returns:
        dict con features calculados (ej: {'roll3': ..., 'roll5': ..., 'ewma5': ..., })
    """
    features = {}
    
    # Rellenar NaN
    series = pd.to_numeric(series, errors='coerce').fillna(0)
    
    # Ventanas de rolling + EWMA
    for ventana, nombre in [(ventana_corta, "3"), (ventana_larga, "5"), (ventana_extra, "7")]:
        # Rolling window
        if len(series) >= ventana:
            features[f"roll{nombre}"] = float(series.tail(ventana).mean())
            features[f"ewma{nombre}"] = float(series.ewm(span=ventana, adjust=False).mean().iloc[-1])
        else:
            # Si no hay suficientes datos, usar lo disponible
            features[f"roll{nombre}"] = float(series.mean()) if len(series) > 0 else 0.0
            if len(series) > 1:
                features[f"ewma{nombre}"] = float(series.ewm(span=ventana, adjust=False).mean().iloc[-1])
            else:
                features[f"ewma{nombre}"] = float(series.mean()) if len(series) > 0 else 0.0
    
    return features


def construir_features_defensa_completos(df_jugador):
    """
    Construye TODOS los features que el modelo DF espera.
    Sacados de la lista: defensive_actions_total, def_actions_per_90, minutes_form_combo, etc.
    """
    features = {}
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    # Features básicos defensivos (rolling/EWMA)
    df_specs = [
        ("entradas", "tackles"),
        ("intercepciones", "intercepts"),
        ("despejes", "clearances"),
        ("duelos", "duels"),
        ("duelos_ganados", "duels_won"),
        ("duelos_perdidos", "duels_lost"),
        ("duelos_aereos", "aerial_duels"),
        ("duelos_aereos_ganados", "aerial_won"),
        ("duelos_aereos_perdidos", "aerial_lost"),
        ("bloques", "blocks"),
    ]
    
    # Crear ventanas temporales para cada feature
    for col_csv, col_prefix in df_specs:
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
    
    # Features de disponibilidad (minutos)
    if "min_partido" in df_jugador.columns:
        min_series = pd.to_numeric(df_jugador["min_partido"], errors='coerce').fillna(45)
        min_pct = (min_series / 90.0).clip(0, 1)
        temporal_features = crear_features_temporales_serie(min_pct, vc, vl, ve)
        for temporal_name, valor in temporal_features.items():
            features[f"minutes_pct_{temporal_name}"] = valor
    
    # Features de roles (si existen)
    num_roles = len(df_jugador.iloc[-1].get('roles', [])) if 'roles' in df_jugador.columns and df_jugador.iloc[-1].get('roles') else 0
    features['num_roles'] = float(num_roles)
    features['score_roles_normalizado'] = float(num_roles * 0.1) if num_roles > 0 else 0.0
    
    # Features avanzados (basados en las combinaciones que el modelo usa)
    # Defensive efficiency
    if features.get('duels_roll5', 0) > 0:
        features['defensive_efficiency'] = (features.get('tackles_roll5', 0) + features.get('intercepts_roll5', 0)) / features.get('duels_roll5', 1)
    else:
        features['defensive_efficiency'] = 0.0
    
    # Actividad defensiva
    features['defensive_activity'] = features.get('tackles_roll5', 0) + features.get('intercepts_roll5', 0) + (features.get('clearances_roll5', 0) * 0.7)
    
    # Duel win rate
    duels_roll5 = features.get('duels_roll5', 0)
    if duels_roll5 > 0:
        features['duel_win_rate'] = min(1.0, features.get('duels_won_roll5', 0) / duels_roll5)
    else:
        features['duel_win_rate'] = 0.0
    
    # Aerial duel win rate
    aerial_roll5 = features.get('aerial_duels_roll5', 0)
    if aerial_roll5 > 0:
        features['aerial_duel_win_rate'] = min(1.0, features.get('aerial_won_roll5', 0) / aerial_roll5)
    else:
        features['aerial_duel_win_rate'] = 0.0
    
    # Form ratio
    pf_roll5 = features.get('pf_roll5', 1.0)
    pf_roll3 = features.get('pf_roll3', 1.0)
    features['form_ratio'] = (pf_roll3 + 0.1) / (pf_roll5 + 0.1)
    features['form_ratio'] = np.clip(features['form_ratio'], 0.5, 2.0)
    
    # Minutes form combo
    features['minutes_form_combo'] = max(0, features.get('minutes_pct_ewma5', 0) * features.get('pf_roll5', 0) / 10)
    
    # Defensive pressure
    features['defensive_pressure'] = (features.get('tackles_roll5', 0) + features.get('blocks_roll5', 0) * 0.8) / max(1, 5)
    
    # Duel balance
    features['duel_balance'] = features.get('duels_won_roll5', 0) - features.get('duels_lost_roll5', 0)
    
    # Aerial balance
    features['aerial_balance'] = features.get('aerial_won_roll5', 0) - features.get('aerial_lost_roll5', 0)
    
    # Defensive form power
    features['defensive_form_power'] = max(0, (features.get('defensive_activity', 0) / max(1, 10)) * (features.get('pf_roll5', 0) / max(1, 10)))
    
    # Defensive consistency
    tackles_diff = abs(features.get('tackles_roll5', 0) - features.get('tackles_ewma5', 0))
    features['defensive_consistency'] = 1.0 / (tackles_diff + 1.0)
    
    # Availability momentum
    min_pct_roll5 = features.get('minutes_pct_roll5', 0.1)
    min_pct_roll3 = features.get('minutes_pct_roll3', 0.1)
    if min_pct_roll5 > 0:
        features['availability_momentum'] = min(2.0, min_pct_roll3 / (min_pct_roll5 + 0.1))
        features['availability_momentum'] = max(0.5, features['availability_momentum'])
    else:
        features['availability_momentum'] = 1.0
    
    # Defensive actions total (clave)
    features['defensive_actions_total'] = features.get('tackles_roll5', 0) + features.get('intercepts_roll5', 0)
    
    # Def actions per 90
    min_pct_roll5 = features.get('minutes_pct_roll5', 0.01)
    if min_pct_roll5 > 0:
        features['def_actions_per_90'] = features.get('defensive_actions_total', 0) / min_pct_roll5
    else:
        features['def_actions_per_90'] = 0.0
    
    # Def actions EWMA per 90
    def_actions_ewma = features.get('tackles_ewma5', 0) + features.get('intercepts_ewma5', 0)
    if min_pct_roll5 > 0:
        features['def_actions_ewma5'] = def_actions_ewma / min_pct_roll5
    else:
        features['def_actions_ewma5'] = 0.0
    
    # Context features
    features['is_home'] = 1.0 if df_jugador.iloc[-1].get('local') == 'Si' else 0.0
    
    # Limpiar infinitos y NaN
    features = {k: float(0 if (pd.isna(v) or np.isinf(v)) else v) for k, v in features.items()}
    
    return features


def predecir_puntos_defensa(jugador_id, jornada_actual=None, verbose=False):
    """Predice puntos fantasy para un defensa desde datos de BD."""
    
    # Cargar modelo
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
        ).select_related('partido__jornada', 'partido__equipo_local', 'partido__equipo_visitante').order_by('partido__jornada__numero_jornada')
        
        if not stats_query.exists():
            return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos históricos'}
        
        # Determinar jornada
        if jornada_actual is None:
            jornada_actual = stats_query.last().partido.jornada.numero_jornada + 1
        jornada_actual = int(jornada_actual)
        
        # Filtrar registros ANTES de la jornada actual
        registros_hist = stats_query.filter(
            partido__jornada__numero_jornada__lt=jornada_actual
        )
        
        if not registros_hist.exists():
            return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos históricos para esta jornada'}
        
        # Construir DataFrame desde BD
        data = []
        for stat in registros_hist:
            data.append({
                'player': nombre_jugador,
                'posicion': stat.posicion if stat.posicion else 'DF',
                'jornada': stat.partido.jornada.numero_jornada,
                'min_partido': stat.min_partido or 0,
                'puntos_fantasy': stat.puntos_fantasy or 0,
                'tackles': stat.entradas or 0,
                'intercepts': 0,  # No está en modelo actual, se calcula
                'duels': stat.duelos or 0,
                'duels_won': stat.duelos_ganados or 0,
                'duels_lost': stat.duelos_perdidos or 0,
                'clearances': stat.despejes or 0,
                'aerial_duels': stat.duelos_aereos_ganados + stat.duelos_aereos_perdidos if (stat.duelos_aereos_ganados or stat.duelos_aereos_perdidos) else 0,
                'aerial_won': stat.duelos_aereos_ganados or 0,
                'aerial_lost': stat.duelos_aereos_perdidos or 0,
                'blocks': stat.bloqueos or 0,
                'local': 'Si' if stat.partido.equipo_local_id == jugador.historial_equipos.all().values_list('equipo_id', flat=True).last() else 'No'
            })
        
        if not data:
            return {'error': 'No hay datos para procesar', 'jugador_id': jugador_id, 'prediccion': None}
        
        df_defensas = pd.DataFrame(data)
    
    except Exception as e:
        return {'error': f'Error cargando datos: {e}', 'jugador_id': jugador_id, 'prediccion': None}
    
    # Buscar jugador en el DataFrame
    mask = df_defensas['player'] == nombre_jugador
    
    if not mask.any():
        return {'error': f'Jugador no encontrado en datos', 'jugador_id': jugador_id, 'prediccion': None}
    
    registros = df_defensas[mask].sort_values('jornada')
    registros_hist = registros[registros['jornada'] < jornada_actual]
    
    if len(registros_hist) == 0:
        return {'jugador_id': jugador_id, 'prediccion': None, 'explicacion_texto': 'Sin datos históricos'}
    
    # Construir features
    try:
        features = construir_features_defensa_completos(registros_hist)
        
        # Obtener feature names del modelo
        if not hasattr(modelo, 'feature_names_in_'):
            return {'error': 'Modelo sin feature_names', 'jugador_id': jugador_id, 'prediccion': None}
        
        feature_names = list(modelo.feature_names_in_)
        
        # Extraer features en orden
        X = []
        features_encontrados = 0
        for feat_name in feature_names:
            if feat_name in features:
                X.append(float(features[feat_name]))
                features_encontrados += 1
            else:
                X.append(0.0)
        
        if features_encontrados < len(feature_names) * 0.3:  # Al menos 30% de features
            if verbose:
                print(f"[WARNING] Solo {features_encontrados}/{len(feature_names)} features encontrados")
        
        # Predicción
        X_array = np.array(X).reshape(1, -1)
        prediccion = float(modelo.predict(X_array)[0])
        prediccion = max(0, prediccion)
        
        # Obtener puntos reales de la jornada a predecir
        puntos_reales = None
        try:
            partido_jornada = stats_query.filter(partido__jornada__numero_jornada=jornada_actual).first()
            if partido_jornada:
                puntos_reales = partido_jornada.puntos_fantasy
        except:
            pass
        
        # Generar explicaciones con SHAP para obtener impactos con signo real
        try:
            import shap
            from explicaciones_unificadas import obtener_explicacion
            explainer = shap.TreeExplainer(modelo)
            shap_values = explainer.shap_values(X_array)
            shap_flat = shap_values.flatten()

            feature_impacts = []
            for i, feat_name in enumerate(feature_names):
                if i < len(shap_flat):
                    impacto = float(shap_flat[i])
                    es_positivo = impacto > 0
                    try:
                        explicacion_txt = obtener_explicacion(feat_name, es_positivo)
                    except Exception:
                        explicacion_txt = feat_name
                    feature_impacts.append({
                        'feature': feat_name,
                        'impacto': impacto,
                        'impacto_pts': impacto,
                        'direccion': 'positivo' if es_positivo else 'negativo',
                        'explicacion': explicacion_txt,
                    })

            pos_feats = sorted([f for f in feature_impacts if f['impacto'] > 0], key=lambda x: x['impacto'], reverse=True)
            neg_feats = sorted([f for f in feature_impacts if f['impacto'] < 0], key=lambda x: x['impacto'])
            top_feats = pos_feats[:3] + neg_feats[:3]
            top_feats.sort(key=lambda x: abs(x['impacto']), reverse=True)

            explicacion_lines = ["Factores principales:", ""]
            for idx_f, feat in enumerate(top_feats, 1):
                signo = '+' if feat['impacto'] > 0 else '-'
                linea = f"{idx_f}. {feat['explicacion']} (impacto: {signo}{abs(feat['impacto']):.2f}pts)"
                explicacion_lines.append(linea)
            explicacion_texto = "\n".join(explicacion_lines)

            features_impacto_result = top_feats
            explicacion_texto_result = explicacion_texto
        except Exception:
            # Fallback: usar explicaciones basadas en thresholds
            features_para_explicacion = preparar_features_para_explicaciones(features)
            explicaciones_dict = generar_explicaciones_features(features_para_explicacion)
            features_impacto_result = explicaciones_dict.get('features_impacto', [])
            explicacion_texto_result = explicaciones_dict.get('explicacion_texto', '')
        
        if verbose:
            print(f"✓ DF {jugador_id} J{jornada_actual}: {prediccion:.2f}pt ({features_encontrados} features)")
        
        return {
            'status': 'success',
            'jugador_id': jugador_id,
            'posicion': 'DF',
            'prediccion': round(prediccion, 2),
            'puntos_reales': puntos_reales,
            'puntos_reales_texto': f"{round(puntos_reales, 2)}" if puntos_reales is not None else "Aún no jugado",
            'jornada': jornada_actual,
            'modelo': 'Random Forest',
            'features_usados': features_encontrados,
            'features_impacto': features_impacto_result,
            'explicacion_texto': explicacion_texto_result,
            'error': None
        }
    
    except Exception as e:
        if verbose:
            print(f"[ERROR] {str(e)}")
        return {'error': f'Error: {str(e)}', 'jugador_id': jugador_id, 'prediccion': None}


if __name__ == '__main__':
    resultado = predecir_puntos_defensa('Abde Rebbach', jornada_actual=8, verbose=True)
    print(resultado)
