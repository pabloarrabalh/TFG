"""
Sistema de generación lazy de predicciones bajo demanda.
- Intenta obtener predicción existente
- Si no existe, la genera on-demand (rápido, single jugador)
- Evita regenear todas las predicciones en startup
"""
import logging
from django.core.cache import cache
from main.models import PrediccionJugador, Jornada, EquipoJugadorTemporada
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

def get_or_create_prediccion(jugador_id, jornada_id, modelo='rf', timeout=5):
    """
    Obtiene predicción existente o la genera bajo demanda.
    
    Args:
        jugador_id: ID del jugador
        jornada_id: ID de la jornada
        modelo: Modelo a usar ('rf', 'xgb', 'lgbm', etc.)
        timeout: Timeout en segundos para generación
        
    Returns:
        PrediccionJugador object o None
    """
    # 1. Intentar obtener predicción existente (rápido)
    try:
        pred = PrediccionJugador.objects.get(
            jugador_id=jugador_id,
            jornada_id=jornada_id,
            modelo=modelo
        )
        return pred
    except PrediccionJugador.DoesNotExist:
        pass
    
    # 2. Generar bajo demanda (lazy)
    try:
        return _generar_prediccion_lazy(jugador_id, jornada_id, modelo)
    except Exception as e:
        logger.warning(f"No se pudo generar predicción lazy para jugador {jugador_id}, jornada {jornada_id}: {e}")
        return None


def _generar_prediccion_lazy(jugador_id, jornada_id, modelo='rf'):
    """Genera UNA predicción bajo demanda (muy rápido)."""
    from main.entrenamientoModelos.predecir import predecir_puntos
    
    try:
        jornada = Jornada.objects.get(pk=jornada_id)
        temporada = jornada.temporada
        
        # Obtener posición del jugador
        ejt = EquipoJugadorTemporada.objects.filter(
            jugador_id=jugador_id,
            temporada=temporada
        ).first()
        
        if not ejt:
            logger.warning(f"Jugador {jugador_id} no encontrado en {temporada.nombre}")
            return None
        
        posicion = ejt.posicion or 'Delantero'
        
        # Predecir
        # predecir_puntos(jugador_id, posicion, jornada_actual=None, verbose=False, modelo_tipo=None)
        resultado = predecir_puntos(
            jugador_id,
            posicion,
            jornada_actual=jornada.numero_jornada,
        )
        
        if not isinstance(resultado, dict) or resultado.get('error'):
            return None
        
        prediccion_valor = resultado.get('prediccion')
        if prediccion_valor is None:
            return None
        
        # Guardar
        pred, created = PrediccionJugador.objects.get_or_create(
            jugador_id=jugador_id,
            jornada=jornada,
            modelo=modelo,
            defaults={'prediccion': prediccion_valor}
        )
        
        if not created:
            pred.prediccion = prediccion_valor
            pred.save(update_fields=['prediccion'])
        
        return pred
        
    except Exception as e:
        logger.error(f"Error generando predicción lazy: {e}", exc_info=True)
        return None


def get_predicciones_jugador_with_lazy(jugador_id, temporada_id=None, modelo='rf'):
    """
    Obtiene todas las predicciones de un jugador, generando lazy las faltantes.
    Útil para vistas de jugador individual.
    """
    from main.models import Temporada, Jornada
    
    if not temporada_id:
        temporada = Temporada.objects.order_by('-nombre').first()
    else:
        temporada = Temporada.objects.get(pk=temporada_id)
    
    if not temporada:
        return []
    
    jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    predicciones = []
    
    for jornada in jornadas:
        pred = get_or_create_prediccion(jugador_id, jornada.id, modelo)
        if pred:
            predicciones.append(pred)
    
    return predicciones


def ensure_predicciones_activos(temporada, jornada_target, modelo='rf', min_minutes=60):
    """
    Asegura que existan predicciones para todos los jugadores activos de una jornada.
    Se usa al iniciar la aplicación con --active-only para generar las predicciones
    faltantes en background sin bloquear.
    """
    from main.models import EstadisticasPartidoJugador, EquipoJugadorTemporada, Jornada
    import threading
    
    def generate_batch():
        # Obtener jugadores activos
        jornada_min = max(1, jornada_target - 10)
        jugadores_activos = set()
        
        for jornada_num in range(jornada_min, jornada_target):
            try:
                jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
                jugadores_con_minutos = EstadisticasPartidoJugador.objects.filter(
                    partido__jornada=jornada,
                    minutos_jugados__gte=min_minutes
                ).values_list('jugador_id', flat=True).distinct()
                jugadores_activos.update(jugadores_con_minutos)
            except Jornada.DoesNotExist:
                continue
        
        # Generar predicciones para activos en jornada target
        for jugador_id in jugadores_activos:
            try:
                jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_target)
                get_or_create_prediccion(jugador_id, jornada.id, modelo)
            except Exception:
                pass
    
    # Ejecutar en background para no bloquear
    thread = threading.Thread(target=generate_batch, daemon=True)
    thread.start()
