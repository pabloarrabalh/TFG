"""
DRF API views – User Profile
Endpoints:
  GET  /api/perfil/
  POST /api/perfil/update/
  POST /api/perfil/status/
  POST /api/perfil/foto/
  POST /api/perfil/preferencias-notificaciones/
  POST /api/perfil/cambiar-jornada/
"""
import logging
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .auth import _user_info
from ..models import Plantilla
from ..views.utils import shield_name

logger = logging.getLogger(__name__)


class PerfilView(APIView):
    """GET /api/perfil/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        profile_data = _user_info(user)

        favoritos = []
        try:
            for fav in user.equipos_favoritos.select_related('equipo').all():
                favoritos.append({
                    'id': fav.id,
                    'equipo_nombre': fav.equipo.nombre,
                    'equipo_escudo': shield_name(fav.equipo.nombre),
                })
        except Exception:
            pass

        plantillas_count = 0
        try:
            plantillas_count = user.plantillas.count()
        except Exception:
            pass

        return Response({
            **profile_data,
            'favoritos': favoritos,
            'plantillas_count': plantillas_count,
            'preferencias_notificaciones': (
                user.profile.preferencias_notificaciones
                if hasattr(user, 'profile')
                else 'all'
            ),
        })


class UpdatePerfilView(APIView):
    """POST /api/perfil/update/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            user = request.user
            old_username = user.username
            username_changed = False

            for field in ('first_name', 'last_name', 'email'):
                if field in data:
                    setattr(user, field, data[field])

            if 'username' in data:
                new_username = (data.get('username') or '').strip()
                if new_username and new_username.lower() != user.username.lower():
                    if User.objects.filter(username__iexact=new_username).exclude(id=user.id).exists():
                        return Response(
                            {'error': 'Nombre de usuario ya en uso'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    user.username = new_username
                    username_changed = True

            user.save()
            try:
                if 'nickname' in data:
                    user.profile.nickname = data['nickname']
                    user.profile.save()
            except Exception:
                pass

            if username_changed:
                self._update_notification_refs(user, old_username)

            return Response({'status': 'ok', 'user': _user_info(user)})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _update_notification_refs(user, old_username):
        try:
            from ..models import Notificacion
            qs = Notificacion.objects.filter(
                Q(datos__emisor_id=user.id) | Q(datos__amigo_id=user.id)
                | Q(datos__emisor_username__iexact=old_username)
                | Q(datos__amigo_username__iexact=old_username)
            )
            for n in qs:
                d = n.datos or {}
                changed = False
                if d.get('emisor_id') == user.id:
                    d['emisor_username'] = user.username
                    d['emisor_nombre'] = user.first_name or user.username
                    changed = True
                if d.get('amigo_id') == user.id:
                    d['amigo_username'] = user.username
                    d['amigo_nombre'] = user.first_name or user.username
                    changed = True
                if d.get('amigo_username') == old_username:
                    d['amigo_username'] = user.username
                    changed = True
                if d.get('emisor_username') == old_username:
                    d['emisor_username'] = user.username
                    changed = True
                if n.mensaje and ('@' + old_username) in n.mensaje:
                    n.mensaje = n.mensaje.replace('@' + old_username, '@' + user.username)
                    changed = True
                if changed:
                    n.datos = d
                    n.save()
        except Exception:
            pass


class UpdateStatusView(APIView):
    """POST /api/perfil/status/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            nuevo_estado = data.get('estado', data.get('status', 'active'))
            if nuevo_estado not in ('active', 'away', 'dnd'):
                nuevo_estado = 'active'
            request.user.profile.estado = nuevo_estado
            request.user.profile.save()
            return Response({'status': 'ok', 'estado': nuevo_estado})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UploadPhotoView(APIView):
    """POST /api/perfil/foto/ – file upload OR JSON {default_avatar: '...'}"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Case 1: File upload
        if 'foto' in request.FILES:
            try:
                request.user.profile.foto = request.FILES['foto']
                request.user.profile.save()
                return Response({'status': 'ok', 'foto_url': request.user.profile.foto.url})
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Case 2: Default avatar by name/index
        try:
            data = request.data
            default_avatar = data.get('default_avatar') or data.get('avatar_index')
            if not default_avatar:
                return Response({'error': 'No se proporcionó foto'}, status=status.HTTP_400_BAD_REQUEST)
            if str(default_avatar).isdigit():
                default_avatar = f'default{default_avatar}'
            avatar_filename = f'{default_avatar}.png'
            static_path = os.path.join(settings.BASE_DIR, 'static', 'logos', avatar_filename)
            if not os.path.exists(static_path):
                return Response(
                    {'error': f'Avatar no encontrado: {avatar_filename}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            with open(static_path, 'rb') as f:
                request.user.profile.foto.save(
                    avatar_filename, ContentFile(f.read()), save=True
                )
            return Response({'status': 'ok', 'foto_url': request.user.profile.foto.url})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UpdatePreferenciasNotificacionesView(APIView):
    """POST /api/perfil/preferencias-notificaciones/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            pref = request.data.get('preferencia', 'all')
            if pref not in ('all', 'friends', 'events', 'none'):
                return Response({'error': 'Preferencia inválida'}, status=status.HTTP_400_BAD_REQUEST)
            request.user.profile.preferencias_notificaciones = pref
            request.user.profile.save()
            return Response({'status': 'ok', 'preferencia': pref})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CambiarJornadaView(APIView):
    """POST /api/perfil/cambiar-jornada/ {jornada: 5}"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from datetime import datetime
            from ..models import Jornada, Temporada
            
            jornada_num = request.data.get('jornada')
            if jornada_num is None:
                return Response(
                    {'error': 'Se requiere número de jornada'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Obtener la temporada actual
            temporada = Temporada.objects.order_by('-nombre').first()
            if not temporada:
                return Response({'error': 'No hay temporada disponible'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar que la jornada está en rango válido (1-38)
            if jornada_num < 1 or jornada_num > 38:
                return Response(
                    {'error': 'Jornada debe estar entre 1 y 38'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            jornada = Jornada.objects.filter(
                temporada=temporada, numero_jornada=jornada_num
            ).first()
            
            if not jornada:
                return Response(
                    {'error': 'Jornada no encontrada'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Obtener jornada anterior del usuario (si la tiene)
            jornada_anterior_num = request.user.profile.jornada_pref or 0
            es_avance = jornada_num > jornada_anterior_num
            
            # Actualizar jornada del usuario
            request.user.profile.jornada_pref = jornada_num
            request.user.profile.save()
            
            return Response({
                'status': 'ok',
                'jornada': jornada_num,
                'es_avance': es_avance,
                'jornada_anterior': jornada_anterior_num,
            })
        except Exception as exc:
            logger.error(f'CambiarJornada error: {exc}')
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

