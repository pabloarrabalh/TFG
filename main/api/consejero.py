"""DRF API views - Consejero (Advisor)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils.consejero_service import *


class ConsejeroView(APIView):
    """POST /api/consejero/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        jugador_id = request.data.get("jugador_id")
        accion_solicitada = (request.data.get("accion") or "").strip().lower()

        try:
            payload = analizar_consejero(
                jugador_id=jugador_id,
                accion_solicitada=accion_solicitada,
            )
            return Response(payload)
        except ConsejeroValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ConsejeroNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ConsejeroServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:
            return Response(
                {"error": f"Error al analizar jugador: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
