"""
DRF API views – Friends / Social
Endpoints:
  GET  /api/amigos/
  POST /api/amigos/solicitud/
  POST /api/amigos/aceptar/<id>/
  POST /api/amigos/rechazar/<id>/
  POST /api/amigos/eliminar/<id>/
  GET  /api/amigos/<user_id>/plantillas/
"""
import logging

from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .api_auth import _user_info
from .models import Amistad, Notificacion, Plantilla, SolicitudAmistad

logger = logging.getLogger(__name__)


class AmigosView(APIView):
    """GET /api/amigos/"""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            amigos = []
            for a in (
                Amistad.objects.filter(
                    Q(usuario1=request.user) | Q(usuario2=request.user)
                ).select_related('usuario1', 'usuario2')
            ):
                amigo = a.usuario2 if a.usuario1 == request.user else a.usuario1
                info = _user_info(amigo)
                amigos.append({
                    'id': info['id'],
                    'username': info['username'],
                    'first_name': info['first_name'],
                    'profile_photo': info['profile_photo'],
                })

            solicitudes_recibidas = [
                {'id': s.id, 'username': s.emisor.username, 'first_name': s.emisor.first_name}
                for s in SolicitudAmistad.objects.filter(
                    receptor=request.user, estado='pendiente'
                ).select_related('emisor')
            ]
            solicitudes_enviadas = [
                {'id': s.id, 'username': s.receptor.username}
                for s in SolicitudAmistad.objects.filter(
                    emisor=request.user, estado='pendiente'
                ).select_related('receptor')
            ]

            return Response({
                'amigos': amigos,
                'solicitudes_pendientes': solicitudes_recibidas,
                'solicitudes_enviadas': solicitudes_enviadas,
            })
        except Exception as exc:
            logger.error('api_amigos error: %s', exc)
            return Response({
                'amigos': [], 'solicitudes_pendientes': [], 'solicitudes_enviadas': []
            })


class EnviarSolicitudView(APIView):
    """POST /api/amigos/solicitud/ {username: '...'}"""

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            username_raw = (request.data.get('username') or '').strip().lstrip('@').strip()
            receptor = None
            try:
                receptor = User.objects.get(username__iexact=username_raw)
            except User.DoesNotExist:
                receptor = User.objects.filter(
                    profile__nickname__iexact=username_raw
                ).first()
                if receptor is None:
                    receptor = User.objects.filter(
                        username__icontains=username_raw
                    ).first()
            if receptor is None:
                return Response(
                    {'error': 'Usuario no encontrado. Usa el nombre de usuario exacto (sin @).'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if receptor == request.user:
                return Response(
                    {'error': 'No puedes enviarte una solicitud a ti mismo'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sol, created = SolicitudAmistad.objects.get_or_create(
                emisor=request.user, receptor=receptor, defaults={'estado': 'pendiente'}
            )
            if not created:
                return Response(
                    {'error': 'Ya existe una solicitud pendiente'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pref = 'all'
            try:
                pref = receptor.profile.preferencias_notificaciones
            except Exception:
                pass
            if pref in ('all', 'friends'):
                Notificacion.objects.create(
                    usuario=receptor,
                    tipo='solicitud_amistad',
                    titulo=(
                        f'{request.user.first_name or request.user.username}'
                        ' te ha enviado una solicitud de amistad'
                    ),
                    mensaje=f'@{request.user.username} quiere ser tu amigo/a.',
                    datos={
                        'solicitud_id': sol.id,
                        'emisor_id': request.user.id,
                        'emisor_username': request.user.username,
                        'emisor_nombre': request.user.first_name or request.user.username,
                        'estado': 'pendiente',
                    },
                )
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AceptarSolicitudView(APIView):
    """POST /api/amigos/aceptar/<solicitud_id>/"""

    def post(self, request, solicitud_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            sol = SolicitudAmistad.objects.get(
                id=solicitud_id, receptor=request.user, estado='pendiente'
            )
            sol.estado = 'aceptada'
            sol.save()
            Amistad.objects.get_or_create(usuario1=sol.emisor, usuario2=request.user)
            for rn in Notificacion.objects.filter(
                usuario=request.user, tipo='solicitud_amistad', datos__solicitud_id=sol.id
            ):
                try:
                    d = rn.datos or {}
                    d['estado'] = 'aceptada'
                    rn.datos = d
                    rn.leida = True
                    rn.save()
                except Exception:
                    rn.leida = True
                    rn.save()
            pref = 'all'
            try:
                pref = sol.emisor.profile.preferencias_notificaciones
            except Exception:
                pass
            if pref in ('all', 'friends'):
                Notificacion.objects.create(
                    usuario=sol.emisor,
                    tipo='solicitud_amistad',
                    titulo=(
                        f'{request.user.first_name or request.user.username}'
                        ' aceptó tu solicitud de amistad'
                    ),
                    mensaje='Ya sois amigos. ¡Ahora puedes ver su plantilla!',
                    datos={
                        'amigo_id': request.user.id,
                        'amigo_username': request.user.username,
                        'estado': 'aceptada',
                    },
                )
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RechazarSolicitudView(APIView):
    """POST /api/amigos/rechazar/<solicitud_id>/"""

    def post(self, request, solicitud_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            sol = SolicitudAmistad.objects.get(
                id=solicitud_id, receptor=request.user, estado='pendiente'
            )
            sol.estado = 'rechazada'
            sol.save()
            for rn in Notificacion.objects.filter(
                usuario=request.user, tipo='solicitud_amistad', datos__solicitud_id=sol.id
            ):
                try:
                    d = rn.datos or {}
                    d['estado'] = 'rechazada'
                    rn.datos = d
                    rn.leida = True
                    rn.save()
                except Exception:
                    rn.leida = True
                    rn.save()
            pref = 'all'
            try:
                pref = sol.emisor.profile.preferencias_notificaciones
            except Exception:
                pass
            if pref in ('all', 'friends'):
                Notificacion.objects.create(
                    usuario=sol.emisor,
                    tipo='solicitud_amistad',
                    titulo=(
                        f'{request.user.first_name or request.user.username}'
                        ' rechazó tu solicitud de amistad'
                    ),
                    mensaje=f'@{request.user.username} ha rechazado tu solicitud.',
                    datos={
                        'solicitud_id': sol.id,
                        'amigo_id': request.user.id,
                        'amigo_username': request.user.username,
                        'estado': 'rechazada',
                    },
                )
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class EliminarAmigoView(APIView):
    """POST /api/amigos/eliminar/<user_id>/"""

    def post(self, request, user_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            amigo = User.objects.get(id=user_id)
            Amistad.objects.filter(
                Q(usuario1=request.user, usuario2=amigo)
                | Q(usuario1=amigo, usuario2=request.user)
            ).delete()
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PlantillasAmigoView(APIView):
    """GET /api/amigos/<user_id>/plantillas/"""

    def get(self, request, user_id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            amigo = User.objects.get(id=user_id)
            is_friend = Amistad.objects.filter(
                Q(usuario1=request.user, usuario2=amigo)
                | Q(usuario1=amigo, usuario2=request.user)
            ).exists()
            if not is_friend:
                return Response({'error': 'No sois amigos'}, status=status.HTTP_403_FORBIDDEN)

            plantillas = Plantilla.objects.filter(usuario=amigo, privacidad='publica')
            data = [
                {
                    'id': p.id,
                    'nombre': p.nombre,
                    'formacion': p.formacion,
                    'alineacion': p.alineacion,
                    'fecha_modificada': p.fecha_modificada.isoformat(),
                    'privacidad': p.privacidad,
                }
                for p in plantillas
            ]
            amigo_info = _user_info(amigo)
            return Response({
                'amigo': {
                    'id': amigo.id,
                    'username': amigo.username,
                    'nombre': amigo.first_name,
                    'profile_photo': amigo_info.get('profile_photo'),
                },
                'plantillas': data,
            })
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
