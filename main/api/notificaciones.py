"""
DRF API views – Notifications
Endpoints:
  GET  /api/notificaciones/
  POST /api/notificaciones/<id>/leer/
  POST /api/notificaciones/leer-todas/
  POST /api/notificaciones/<id>/borrar/
  POST /api/notificaciones/borrar-todas/
"""
import logging

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models import Notificacion

logger = logging.getLogger(__name__)


class NotificacionesView(APIView):
    """GET /api/notificaciones/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            notifs = (
                Notificacion.objects.filter(usuario=request.user)
                .order_by('-fecha_creada')[:50]
            )
            data = [
                {
                    'id': n.id,
                    'tipo': n.tipo,
                    'titulo': n.titulo,
                    'mensaje': n.mensaje,
                    'leida': n.leida,
                    'creada_en': n.fecha_creada.isoformat(),
                    'datos': n.datos,
                }
                for n in notifs
            ]
            no_leidas = Notificacion.objects.filter(
                usuario=request.user, leida=False
            ).count()
            return Response({'notificaciones': data, 'no_leidas': no_leidas})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarcarNotificacionLeidaView(APIView):
    """POST /api/notificaciones/<notif_id>/leer/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, notif_id):
        try:
            Notificacion.objects.filter(id=notif_id, usuario=request.user).update(leida=True)
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MarcarTodasLeidasView(APIView):
    """POST /api/notificaciones/leer-todas/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class BorrarNotificacionView(APIView):
    """POST /api/notificaciones/<notif_id>/borrar/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, notif_id):
        try:
            Notificacion.objects.filter(id=notif_id, usuario=request.user).delete()
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class BorrarTodasNotificacionesView(APIView):
    """POST /api/notificaciones/borrar-todas/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            Notificacion.objects.filter(usuario=request.user).delete()
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
