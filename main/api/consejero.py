"""
DRF API views – Consejero (Advisor)
Endpoints:
  POST /api/consejero/
"""
import logging
from django.db.models import Avg, Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models import (
    Jugador, EstadisticasPartidoJugador, EquipoJugadorTemporada,
    ClasificacionJornada, Temporada, Partido, EstadoPartido
)

logger = logging.getLogger(__name__)


class ConsejeroView(APIView):
    """POST /api/consejero/ – Analizar jugador para fichar/vender/mantener"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            jugador_id = request.data.get('jugador_id')
            accion = request.data.get('accion')  # 'fichar', 'vender', 'mantener'

            if not jugador_id or not accion:
                return Response(
                    {'error': 'Faltan parámetros: jugador_id, accion'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                jugador = Jugador.objects.get(id=jugador_id)
            except Jugador.DoesNotExist:
                return Response(
                    {'error': 'Jugador no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Obtener temporada actual — campo correcto: partido__jornada__temporada
            temporada = (
                Temporada.objects.filter(nombre='25_26').first()
                or Temporada.objects.order_by('-nombre').first()
            )
            if not temporada:
                return Response(
                    {'error': 'Temporada no disponible'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Últimos 5 partidos (para rendimiento general)
            ultimos5 = list(
                EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada,
                ).select_related('partido__jornada', 'partido__equipo_local', 'partido__equipo_visitante')
                .order_by('-partido__jornada__numero_jornada')[:5]
            )

            # Últimos 3 partidos (para criterios específicos)
            ultimos3 = ultimos5[:3]

            # Calcular métricas
            posicion = jugador.get_posicion_mas_frecuente() or 'Delantero'
            rendimiento = _calcular_rendimiento(jugador, temporada, ultimos5)
            media_pos = _obtener_media_posicion(posicion, temporada)
            vs_promedio = rendimiento - media_pos

            # Métricas de últimos 3 partidos
            titulares_3 = sum(1 for p in ultimos3 if p.titular)
            minutos_3 = sum(p.min_partido or 0 for p in ultimos3)
            goles_3 = sum(p.gol_partido or 0 for p in ultimos3)

            # Rival débil: obtener posición del próximo rival en clasificación
            rival_debil, pos_rival = _rival_es_debil(jugador, temporada)

            # Titularidad general (últimos 5)
            titularidad_pct = (
                sum(1 for p in ultimos5 if p.titular) / len(ultimos5) * 100
                if ultimos5 else 0
            )

            # Generar veredicto
            veredicto, razon = _generar_veredicto(
                jugador, accion, rendimiento, media_pos, vs_promedio,
                titulares_3, minutos_3, goles_3, titularidad_pct,
                rival_debil, pos_rival
            )

            return Response({
                'veredicto': veredicto,
                'razon': razon,
                'rendimiento': f'{rendimiento:.2f}',
                'vs_promedio': vs_promedio,
                'titularidad_pct': int(titularidad_pct),
                'accion': accion,
            })

        except Exception as e:
            logger.exception(f'ConsejeroView error: {e}')
            return Response(
                {'error': f'Error al analizar jugador: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ─── helpers ────────────────────────────────────────────────────────────────

def _obtener_media_posicion(posicion, temporada):
    return (
        EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada,
            posicion=posicion,
        ).aggregate(Avg('puntos_fantasy'))['puntos_fantasy__avg'] or 0
    )


def _rival_es_debil(jugador, temporada):
    """
    Determina si el próximo rival del equipo del jugador está en la parte baja
    de la clasificación (posición >= 14 = débil).
    Devuelve (bool, int_posicion).
    """
    try:
        rel = (
            EquipoJugadorTemporada.objects.filter(
                jugador=jugador, temporada=temporada,
            ).select_related('equipo').first()
        )
        if not rel:
            return False, None

        equipo = rel.equipo

        # Próximo partido pendiente del equipo
        proximo = (
            Partido.objects.filter(
                jornada__temporada=temporada,
                estado=EstadoPartido.PENDIENTE,
            ).filter(
                equipo_local=equipo
            ) | Partido.objects.filter(
                jornada__temporada=temporada,
                estado=EstadoPartido.PENDIENTE,
            ).filter(
                equipo_visitante=equipo
            )
        ).order_by('jornada__numero_jornada').first()

        if not proximo:
            return False, None

        rival = proximo.equipo_visitante if proximo.equipo_local == equipo else proximo.equipo_local

        # Posición del rival en la última jornada con datos
        clasif = (
            ClasificacionJornada.objects.filter(
                temporada=temporada, equipo=rival,
            ).order_by('-jornada__numero_jornada').first()
        )
        if not clasif:
            return False, None

        return clasif.posicion >= 14, clasif.posicion

    except Exception:
        return False, None


# ─── generador de veredictos ────────────────────────────────────────────────

def _generar_veredicto(jugador, accion, rendimiento, media_pos, vs_promedio, titulares_3, minutos_3):
    nombre = f"{jugador.nombre} {jugador.apellido}"

    # Criterios objetivos
    por_encima_media = rendimiento > media_pos
    titular_100 = titulares_3 == 3
    criterios_fichar = sum([titular_100, por_encima_media])  # recomienda fichar si >= 2
    recomienda_vender = minutos_3 < 50 and rendimiento < media_pos
    recomienda_mantener = rendimiento >= media_pos

    # ─── FICHAR ────────────────────────────────────────────────────────
    if accion == 'fichar':
        if criterios_fichar >= 2:
            return (
                f"Sí, fíchalo ahora. {nombre} cumple los criterios clave.",
                f"Ha sido titular {titulares_3}/3 en los últimos partidos y su media de puntos "
                f"({rendimiento:.1f}) supera la media de su posición ({media_pos:.1f} pts). "
                f"Es el perfil que buscas."
            )
        elif titular_100 and not por_encima_media:
            return (
                f"Casi, te recomendaría no ficharlo ahora. Tiene continuidad pero el rendimiento no acompaña.",
                f"Ha sido titular los 3 últimos partidos, pero su media de puntos ({rendimiento:.1f}) "
                f"está por debajo de la media de su posición ({media_pos:.1f} pts). "
                f"Espera a que mejore sus números antes de hacerte con él."
            )
        elif por_encima_media and not titular_100:
            return (
                f"Casi, te recomendaría no ficharlo ahora. Rinde bien pero la titularidad no es segura.",
                f"Su media ({rendimiento:.1f} pts) supera la de su posición ({media_pos:.1f}), "
                f"pero solo ha sido titular {titulares_3}/3 partidos recientes. "
                f"Sin continuidad garantizada, los puntos no son constantes."
            )
        else:
            return (
                f"No, no lo ficharía ahora. {nombre} no cumple ninguno de los dos criterios.",
                f"Su media ({rendimiento:.1f} pts) está por debajo de la media de su posición ({media_pos:.1f}) "
                f"y solo ha sido titular {titulares_3}/3 partidos. Son los dos criterios que miro antes de fichar."
            )

    # ─── VENDER ────────────────────────────────────────────────────────
    elif accion == 'vender':
        if recomienda_vender:
            return (
                f"Sí, véndelo. La situación es clara.",
                f"{nombre} solo ha acumulado {minutos_3} minutos en los últimos 3 partidos "
                f"y su media de puntos ({rendimiento:.1f}) está {abs(vs_promedio):.1f} pts por debajo "
                f"de la media de su posición ({media_pos:.1f} pts). "
                f"No tiene protagonismo y no está generando puntos suficientes."
            )
        elif recomienda_mantener:
            return (
                f"No lo vendes ahora. Te recomendaría mantenerlo.",
                f"Su rendimiento ({rendimiento:.1f} pts) está por encima de la media de su posición "
                f"({media_pos:.1f} pts, diferencia {vs_promedio:+.1f}). "
                f"Ha sumado {minutos_3} minutos en los últimos 3 partidos, con {titulares_3}/3 titularidades. "
                f"No hay motivo para prescindir de él ahora mismo."
            )
        else:
            return (
                f"Podría tener sentido, pero no es urgente.",
                f"Su rendimiento ({rendimiento:.1f} pts) está algo por debajo de la media ({media_pos:.1f} pts), "
                f"pero ha sumado {minutos_3} minutos en los últimos 3 partidos ({titulares_3}/3 como titular). "
                f"No es un caso claro de venta. Si tienes una alternativa mejor, analiza el cambio."
            )

    # ─── MANTENER ──────────────────────────────────────────────────────
    elif accion == 'mantener':
        if recomienda_mantener:
            return (
                f"Sí, mantenlo. Rinde en la media o por encima.",
                f"Su media de puntos ({rendimiento:.1f}) está {vs_promedio:+.1f} respecto a la media "
                f"de su posición ({media_pos:.1f} pts). "
                f"Ha sido titular {titulares_3}/3 partidos recientes. Es una pieza funcional en tu plantilla."
            )
        else:
            return (
                f"Te recomendaría no mantenerlo. Rinde por debajo de la media.",
                f"Su media de puntos ({rendimiento:.1f}) está {abs(vs_promedio):.1f} pts por debajo "
                f"de la media de su posición ({media_pos:.1f} pts). "
                f"Solo ha sido titular {titulares_3}/3 partidos con {minutos_3} minutos totales. "
                f"Hay opciones más productivas que merece la pena explorar."
            )

    else:
        return "Análisis no disponible", "No se pudo generar un veredicto específico."

    return veredicto, razon
