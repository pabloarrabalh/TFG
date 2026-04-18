
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils.jugador_insight_service import analizar_jugador_insight


class JugadorInsightView(APIView):
    """GET /api/jugador-insight/?jugador_id=123&temporada=25/26"""
    permission_classes = [AllowAny]

    def get(self, request):
        payload = analizar_jugador_insight(
            jugador_id=request.GET.get("jugador_id"),
            temporada_display=request.GET.get("temporada", "25/26"),
            jornada=request.GET.get("jornada"),
        )
        return Response(payload)
