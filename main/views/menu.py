"""Menu view"""
import logging
from datetime import datetime

from django.shortcuts import render
from django.db.models import Q

from ..models import Temporada, Jornada, Calendario, ClasificacionJornada, EstadisticasPartidoJugador

logger = logging.getLogger(__name__)


def menu(request):
    """Vista principal del menú"""
    context = {'active_page': 'menu'}

    temporada = Temporada.objects.all().order_by('-nombre').first()
    if not temporada:
        return render(request, 'menu.html', context)

    jornada_actual = Jornada.objects.filter(temporada=temporada, numero_jornada=17).first()
    if not jornada_actual:
        ahora = datetime.now()
        jornada_actual = (
            Jornada.objects.filter(temporada=temporada, fecha_fin__gte=ahora)
            .order_by('numero_jornada').first()
        )
        if not jornada_actual:
            jornada_actual = (
                Jornada.objects.filter(temporada=temporada)
                .order_by('-numero_jornada')
                .exclude(numero_jornada=38)
                .first()
            )

    context['jornada_actual'] = jornada_actual
    context['temporada'] = temporada

    if jornada_actual:
        try:
            clasificacion_actual = (
                ClasificacionJornada.objects
                .filter(temporada=temporada, jornada=jornada_actual)
                .order_by('posicion')[:5]
                .select_related('equipo')
            )
            context['clasificacion_top'] = list(clasificacion_actual)
        except Exception as e:
            logger.error(f"Error al obtener clasificación: {e}")

    if jornada_actual:
        try:
            proxima_jornada_num = jornada_actual.numero_jornada + 1
            proxima_jornada = Jornada.objects.filter(
                temporada=temporada, numero_jornada=proxima_jornada_num
            ).first()

            if proxima_jornada:
                partidos_proxima_jornada = (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .select_related('equipo_local', 'equipo_visitante', 'jornada')
                    .order_by('fecha', 'hora')
                )
                context['partidos_proxima_jornada'] = list(partidos_proxima_jornada)
                context['proxima_jornada'] = proxima_jornada

                try:
                    jugadores_destacados = (
                        EstadisticasPartidoJugador.objects
                        .filter(partido__jornada=proxima_jornada)
                        .select_related('jugador', 'partido')
                        .order_by('-goles', '-asistencias')[:5]
                    )
                    context['jugadores_destacados_proxima'] = list(jugadores_destacados)
                except Exception as je:
                    logger.error(f"Error al obtener jugadores destacados: {je}")
        except Exception as e:
            logger.error(f"Error al obtener próxima jornada: {e}")

    if request.user.is_authenticated:
        try:
            equipos_favoritos = request.user.equipos_favoritos.all().values_list('equipo_id', flat=True)

            if equipos_favoritos and jornada_actual:
                proxima_jornada_num = jornada_actual.numero_jornada + 1
                proxima_jornada = Jornada.objects.filter(
                    temporada=temporada, numero_jornada=proxima_jornada_num
                ).first()

                if proxima_jornada:
                    partidos_favoritos = Calendario.objects.filter(
                        jornada=proxima_jornada
                    ).filter(
                        Q(equipo_local_id__in=equipos_favoritos)
                        | Q(equipo_visitante_id__in=equipos_favoritos)
                    ).select_related('equipo_local', 'equipo_visitante', 'jornada')

                    context['partidos_favoritos'] = list(partidos_favoritos)
                    context['proxima_jornada'] = proxima_jornada

            if hasattr(request.user, 'profile') and request.user.profile:
                context['user_nickname'] = request.user.profile.nickname
        except Exception as e:
            logger.error(f"Error al obtener favoritos: {e}")

    return render(request, 'menu.html', context)
