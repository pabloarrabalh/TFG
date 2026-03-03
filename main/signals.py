from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
import logging
import threading

logger = logging.getLogger(__name__)

try:
    from .models import Jugador, Equipo
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

try:
    from .elasticsearch_docs import opensearch_client, ELASTICSEARCH_AVAILABLE
except ImportError:
    opensearch_client = None
    ELASTICSEARCH_AVAILABLE = False


if MODELS_AVAILABLE and ELASTICSEARCH_AVAILABLE and opensearch_client:
    import json
    
    @receiver(post_save, sender=Jugador)
    def indexar_jugador_al_guardar(sender, instance, created, **kwargs):
        """Indexa automáticamente un jugador cuando se guarda en OpenSearch"""
        try:
            doc = {
                'id': instance.id,
                'nombre_completo': f"{instance.nombre} {instance.apellido}",
                'nombre': instance.nombre,
                'apellido': instance.apellido,
                'nacionalidad': instance.nacionalidad,
                'posicion': instance.get_posicion_mas_frecuente() or 'Desconocida'
            }
            opensearch_client.index(
                index='jugadores',
                id=instance.id,
                body=doc
            )
        except Exception as e:
            logger.warning(f"Error indexando jugador {instance.id}: {str(e)}")

    @receiver(post_delete, sender=Jugador)
    def eliminar_jugador_del_indice(sender, instance, **kwargs):
        """Elimina automáticamente un jugador del índice OpenSearch cuando se borra"""
        try:
            opensearch_client.delete(
                index='jugadores',
                id=instance.id,
                ignore=404
            )
        except Exception as e:
            logger.warning(f"Error eliminando jugador {instance.id} del índice: {str(e)}")

    @receiver(post_save, sender=Equipo)
    def indexar_equipo_al_guardar(sender, instance, created, **kwargs):
        """Indexa automáticamente un equipo cuando se guarda en OpenSearch"""
        try:
            doc = {
                'id': instance.id,
                'nombre': instance.nombre,
                'estadio': instance.estadio or 'Desconocido'
            }
            opensearch_client.index(
                index='equipos',
                id=instance.id,
                body=doc
            )
        except Exception as e:
            logger.warning(f"Error indexando equipo {instance.id}: {str(e)}")

    @receiver(post_delete, sender=Equipo)
    def eliminar_equipo_del_indice(sender, instance, **kwargs):
        """Elimina automáticamente un equipo del índice OpenSearch cuando se borra"""
        try:
            opensearch_client.delete(
                index='equipos',
                id=instance.id,
                ignore=404
            )
        except Exception as e:
            logger.warning(f"Error eliminando equipo {instance.id} del índice: {str(e)}")
else:
    logger.info("⚠️ OpenSearch no está disponible, signals de indexación desactivados")
# Signals para UserProfile
from django.contrib.auth.models import User
from main.models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crea automáticamente un UserProfile cuando se crea un nuevo usuario"""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Guarda el UserProfile cuando se guarda el usuario"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-PREDICCIÓN: cuando se guardan stats de un jugador, genera predicción
# en segundo plano si todavía no existe para esa jornada.
# ─────────────────────────────────────────────────────────────────────────────

def _generar_prediccion_background(jugador_id, jornada_id, posicion):
    """Ejecuta en un hilo demonio: predice puntos y guarda en PrediccionJugador."""
    import sys
    from pathlib import Path

    try:
        from main.models import PrediccionJugador, Jornada

        jornada = Jornada.objects.get(pk=jornada_id)

        # Saltar si ya existe
        if PrediccionJugador.objects.filter(
            jugador_id=jugador_id, jornada=jornada, modelo='rf'
        ).exists():
            return

        # Cargar predictor según posición
        entrenamientos_path = Path(__file__).resolve().parent / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))

        import importlib
        mod = importlib.import_module('predecir')
        func = getattr(mod, 'predecir_puntos')

        pos_code_map = {
            'Portero': 'PT', 'Defensa': 'DF',
            'Centrocampista': 'MC', 'Delantero': 'DT',
        }
        pos_code = pos_code_map.get(posicion, 'DT')

        resultado = func(jugador_id, pos_code, jornada.numero_jornada, verbose=False)
        if not isinstance(resultado, dict) or resultado.get('error'):
            return

        pts = resultado.get('prediccion', resultado.get('puntos_predichos'))
        if pts is None:
            return

        PrediccionJugador.objects.update_or_create(
            jugador_id=jugador_id,
            jornada=jornada,
            modelo='rf',
            defaults={'prediccion': float(pts)},
        )
        logger.debug(f"[AutoPredicción] J{jugador_id} J{jornada.numero_jornada}: {pts:.2f} pts guardados")

    except Exception as exc:
        logger.debug(f"[AutoPredicción] error para jugador {jugador_id}: {exc}")


try:
    from main.models import EstadisticasPartidoJugador

    @receiver(post_save, sender=EstadisticasPartidoJugador)
    def auto_generar_prediccion(sender, instance, created, **kwargs):
        """
        Cuando se guarda una estadística de partido, lanza en segundo plano
        la predicción para ese jugador+jornada si todavía no existe.
        Solo actúa en registros nuevos para no ralentizar updates masivos.
        """
        if not created:
            return

        jugador_id = instance.jugador_id
        jornada_id = instance.partido.jornada_id
        posicion = instance.posicion or ''

        # Esperar a que la transacción termine antes de lanzar el hilo
        def _lanzar():
            t = threading.Thread(
                target=_generar_prediccion_background,
                args=(jugador_id, jornada_id, posicion),
                daemon=True,
            )
            t.start()

        transaction.on_commit(_lanzar)

except Exception:
    logger.info("AutoPredicción: EstadisticasPartidoJugador no disponible aún")