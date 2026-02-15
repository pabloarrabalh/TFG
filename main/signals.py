from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

try:
    from .models import Jugador, Equipo
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

try:
    from .elasticsearch_docs import JugadorDocument, EquipoDocument, ELASTICSEARCH_AVAILABLE
except ImportError:
    ELASTICSEARCH_AVAILABLE = False


if MODELS_AVAILABLE and ELASTICSEARCH_AVAILABLE:
    @receiver(post_save, sender=Jugador)
    def indexar_jugador_al_guardar(sender, instance, created, **kwargs):
        """Indexa automáticamente un jugador cuando se guarda"""
        try:
            doc = JugadorDocument(
                meta={'id': instance.id},
                id=instance.id,
                nombre_completo=f"{instance.nombre} {instance.apellido}",
                nombre=instance.nombre,
                apellido=instance.apellido,
                nacionalidad=instance.nacionalidad,
                posicion=instance.get_posicion_mas_frecuente() or 'Desconocida'
            )
            doc.save()
        except Exception as e:
            logger.warning(f"Error indexando jugador {instance.id}: {str(e)}")

    @receiver(post_delete, sender=Jugador)
    def eliminar_jugador_del_indice(sender, instance, **kwargs):
        """Elimina automáticamente un jugador del índice cuando se borra"""
        try:
            JugadorDocument.get(id=instance.id).delete()
        except Exception as e:
            logger.warning(f"Error eliminando jugador {instance.id} del índice: {str(e)}")

    @receiver(post_save, sender=Equipo)
    def indexar_equipo_al_guardar(sender, instance, created, **kwargs):
        """Indexa automáticamente un equipo cuando se guarda"""
        try:
            doc = EquipoDocument(
                meta={'id': instance.id},
                id=instance.id,
                nombre=instance.nombre,
                estadio=instance.estadio
            )
            doc.save()
        except Exception as e:
            logger.warning(f"Error indexando equipo {instance.id}: {str(e)}")

    @receiver(post_delete, sender=Equipo)
    def eliminar_equipo_del_indice(sender, instance, **kwargs):
        """Elimina automáticamente un equipo del índice cuando se borra"""
        try:
            EquipoDocument.get(id=instance.id).delete()
        except Exception as e:
            logger.warning(f"Error eliminando equipo {instance.id} del índice: {str(e)}")
else:
    logger.info("⚠️ Elasticsearch no está disponible, signals de indexación desactivados")
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