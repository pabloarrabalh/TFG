"""
DRF API views – Favourite Teams
Endpoints:
  GET    /api/favoritos/
  POST   /api/favoritos/toggle-v2/
  DELETE /api/favoritos/<fav_id>/
  GET    /api/favoritos/seleccionar/
"""
import logging

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from ..models import Equipo, EquipoFavorito
from ..views.utils import shield_name

logger = logging.getLogger(__name__)


class FavoritosView(APIView):
    """GET /api/favoritos/  —  also used by /api/favoritos/seleccionar/"""
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'authenticated': False, 'favoritos': []})

        fav_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
        favoritos = [
            {
                'id': eq.id,
                'nombre': eq.nombre,
                'escudo': shield_name(eq.nombre),
                'es_favorito': eq.id in fav_ids,
            }
            for eq in Equipo.objects.order_by('nombre')
        ]
        return Response({'authenticated': True, 'favoritos': favoritos})


class ToggleFavoritoView(APIView):
    """POST /api/favoritos/toggle-v2/ {equipo_id: N}"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            equipo_id = request.data.get('equipo_id')
            equipo = Equipo.objects.get(id=equipo_id)
        except (Equipo.DoesNotExist, Exception):
            return Response({'error': 'Equipo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fav, created = EquipoFavorito.objects.get_or_create(
                usuario=request.user, equipo=equipo
            )
            if not created:
                fav.delete()
                return Response({'status': 'removed', 'es_favorito': False})
            return Response({'status': 'added', 'es_favorito': True})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DeleteFavoritoView(APIView):
    """DELETE /api/favoritos/<fav_id>/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, fav_id):
        try:
            fav = EquipoFavorito.objects.get(id=fav_id, usuario=request.user)
            fav.delete()
            return Response({'status': 'ok'})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
