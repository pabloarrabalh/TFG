"""
Generación de predicciones on-demand (cuando se accede a un jugador o se añade a plantilla).
Usa cache para evitar regenerar.
"""

import logging
import sys
from pathlib import Path

from django.core.cache import cache
from django.db import transaction
from main.models import *

_log = logging.getLogger(__name__)


def obtener_prediccion_jugador(jugador_id, jornada_id, timeout=3600):
    """
    Obtiene predicción de un jugador para una jornada.
    Si no existe, intenta generarla on-demand.
    
    Usa cache para evitar queries repetidas.
    """
    # Intentar desde cache primero
    cache_key = f"pred_{jugador_id}_{jornada_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        jornada = Jornada.objects.get(pk=jornada_id)
        temporada = jornada.temporada
    except Jornada.DoesNotExist:
        return None
    
    # Buscar predicción existente
    try:
        prediccion = PrediccionJugador.objects.get(
            jugador_id=jugador_id,
            jornada_id=jornada_id
        )
        cache.set(cache_key, prediccion.prediccion, timeout)
        return prediccion.prediccion
    except PrediccionJugador.DoesNotExist:
        pass
    
    # No existe - marcar como pedido pendiente para generar en background
    _marcar_prediccion_pendiente(jugador_id, jornada_id, temporada.pk)
    
    return None


def _marcar_prediccion_pendiente(jugador_id, jornada_id, temporada_id):
    """Marca una predicción como pendiente de generar en background."""
    try:
        PedidoPrediccion.objects.get_or_create(
            jugador_id=jugador_id,
            jornada_id=jornada_id,
            temporada_id=temporada_id,
            defaults={'estado': 'pending'}
        )
    except Exception as e:
        _log.warning(f"Error marcando predicción pendiente: {e}")


def generar_predicciones_pendientes(batch_size=50, tempo_name='25_26'):
    """
    Genera predicciones pendientes en background.
    Llamar periódicamente desde celery task o cron job.
    
    Returns: (generadas, errores)
    """
    # Cargar módulo de predicción
    entrenamientos_path = Path(__file__).resolve().parents[2] / 'main' / 'entrenamientoModelos'
    if str(entrenamientos_path) not in sys.path:
        sys.path.insert(0, str(entrenamientos_path))
    
    try:
        import importlib
        _predecir_mod = importlib.import_module('predecir')
        _predecir_puntos = getattr(_predecir_mod, 'predecir_puntos')
    except Exception as e:
        _log.error(f"No se pudo cargar módulo de predicción: {e}")
        return 0, 0
    
    temporada = Temporada.objects.filter(nombre=tempo_name).first()
    if not temporada:
        _log.warning(f"Temporada {tempo_name} no encontrada")
        return 0, 0
    
    # Obtener pedidos pendientes
    pedidos = PedidoPrediccion.objects.filter(
        estado='pending',
        temporada=temporada,
        intentos__lt=3  # Máximo 3 intentos
    ).select_related('jugador', 'jornada')[:batch_size]
    
    generadas = 0
    errores = 0
    
    for pedido in pedidos:
        try:
            jugador = pedido.jugador
            jornada = pedido.jornada
            
            # Obtener posición
            ejt = EquipoJugadorTemporada.objects.filter(
                jugador=jugador,
                temporada=temporada
            ).first()
            posicion = ejt.posicion if ejt else jugador.get_posicion_mas_frecuente() or 'Delantero'
            
            # Generar predicción
            # predecir_puntos(jugador_id, posicion, jornada_actual=None, verbose=False, modelo_tipo=None)
            try:
                resultado = _predecir_puntos(
                    jugador.pk,
                    posicion,
                    jornada_actual=jornada.numero_jornada,
                )
                
                prediction = None
                if isinstance(resultado, dict) and not resultado.get('error'):
                    prediction = resultado.get('prediccion')
                
                if prediction is not None:
                    # Guardar predicción
                    PrediccionJugador.objects.update_or_create(
                        jugador=jugador,
                        jornada=jornada,
                        modelo='rf',
                        defaults={'prediccion': float(prediction)}
                    )
                    
                    # Marcar como generada
                    pedido.estado = 'generated'
                    pedido.save()
                    
                    # Limpiar cache
                    cache_key = f"pred_{jugador.pk}_{jornada.pk}"
                    cache.delete(cache_key)
                    
                    generadas += 1
                    _log.info(f"✓ Predicción generada: {jugador} J{jornada.numero_jornada}")
                else:
                    raise ValueError("Predicción None")
            
            except Exception as e:
                pedido.intentos += 1
                pedido.motivo_error = str(e)
                if pedido.intentos >= 3:
                    pedido.estado = 'failed'
                pedido.save()
                errores += 1
                _log.warning(f"✗ Error generando predicción {jugador} J{jornada.numero_jornada}: {e}")
        
        except Exception as e:
            _log.error(f"Error procesando pedido: {e}")
            errores += 1
    
    return generadas, errores


def limpiar_predicciones_generadas():
    """Limpia los PedidoPrediccion ya generados después de 24h."""
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = PedidoPrediccion.objects.filter(
        estado='generated',
        actualizado_en__lt=cutoff
    ).delete()
    
    _log.info(f"Limpiados {deleted} pedidos predicción generados")
    return deleted
