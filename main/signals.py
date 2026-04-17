import threading

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .entrenamientoModelos.predecir import predecir_puntos
from .models import *

POS_CODE_MAP = {
    'Portero': 'PT',
    'Defensa': 'DF',
    'Centrocampista': 'MC',
    'Delantero': 'DT',
}

try:
    from .meilisearch_docs import MEILISEARCH_AVAILABLE, meilisearch_client
except ImportError:
    meilisearch_client = None
    MEILISEARCH_AVAILABLE = False

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


if MEILISEARCH_AVAILABLE and meilisearch_client:
    @receiver(post_save, sender=Jugador)
    def indexar_jugador_al_guardar(sender, instance, created, **kwargs):
        try:
            doc = {
                'id': instance.id,
                'nombre_completo': f"{instance.nombre} {instance.apellido}",
                'nombre': instance.nombre,
                'apellido': instance.apellido,
                'nacionalidad': instance.nacionalidad,
                'posicion': instance.get_posicion_mas_frecuente() or 'Desconocida'
            }
            meilisearch_client.index(
                index='jugadores',
                id=instance.id,
                body=doc
            )
        except Exception:
            return

    @receiver(post_delete, sender=Jugador)
    def eliminar_jugador_del_indice(sender, instance, **kwargs):
        try:
            meilisearch_client.delete(
                index='jugadores',
                id=instance.id,
                ignore=404
            )
        except Exception:
            return

    @receiver(post_save, sender=Equipo)
    def indexar_equipo_al_guardar(sender, instance, created, **kwargs):
        try:
            doc = {
                'id': instance.id,
                'nombre': instance.nombre,
                'estadio': instance.estadio or 'Desconocido'
            }
            meilisearch_client.index(
                index='equipos',
                id=instance.id,
                body=doc
            )
        except Exception:
            return

    @receiver(post_delete, sender=Equipo)
    def eliminar_equipo_del_indice(sender, instance, **kwargs):
        try:
            meilisearch_client.delete(
                index='equipos',
                id=instance.id,
                ignore=404
            )
        except Exception:
            return


# Generación de predicciones en seugndo plano al arrancar
def _generar_prediccion_background(jugador_id, jornada_id, posicion):
    try:
        jornada = Jornada.objects.get(pk=jornada_id)

        # Saltar si ya existe
        if PrediccionJugador.objects.filter(jugador_id=jugador_id, jornada=jornada, modelo='rf').exists():
            return

        pos_code = POS_CODE_MAP.get(posicion, 'DT')

        resultado = predecir_puntos(jugador_id, pos_code, jornada.numero_jornada, verbose=False)
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
    except Exception:
        return


@receiver(post_save, sender=EstadisticasPartidoJugador)
def auto_generar_prediccion(sender, instance, created, **kwargs):
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


# WebSocket cuando se crea una nueva notificacion
@receiver(post_save, sender=Notificacion)
def notificacion_creada_ws(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        no_leidas = Notificacion.objects.filter(
            usuario=instance.usuario, leida=False
        ).count()
        async_to_sync(channel_layer.group_send)(
            f'notificaciones_{instance.usuario_id}',
            {
                'type': 'notificacion_nueva',
                'notificacion': {
                    'id': instance.id,
                    'tipo': instance.tipo,
                    'titulo': instance.titulo,
                    'mensaje': instance.mensaje,
                    'leida': instance.leida,
                    'creada_en': instance.fecha_creada.isoformat(),
                    'datos': instance.datos,
                },
                'no_leidas': no_leidas,
            },
        )
    except Exception:
        return