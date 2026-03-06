"""Clasificacion (standings) view"""
from django.shortcuts import render
from django.db.models import Q

from ..models import (
    Temporada, Jornada, ClasificacionJornada, Equipo,
    Partido, Calendario, EstadisticasPartidoJugador, EquipoJugadorTemporada,
)
from .utils import get_racha_detalles


def clasificacion(request):
    """Vista de Clasificación de la liga con filtros por temporada y jornada"""
    temporada_display = request.GET.get('temporada', '25/26')
    jornada_num = request.GET.get('jornada', '1')
    equipo_seleccionado = request.GET.get('equipo', '')

    temporada_nombre = temporada_display.replace('/', '_')

    temporadas = Temporada.objects.all().order_by('-nombre')
    temporadas_display = [
        {'obj': temp, 'nombre': temp.nombre, 'display': temp.nombre.replace('_', '/')}
        for temp in temporadas
    ]

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = temporadas.first()
        temporada_nombre = temporada.nombre if temporada else '23_24'
        temporada_display = temporada_nombre.replace('_', '/')

    jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    equipos_disponibles = Equipo.objects.all().order_by('nombre')

    clasificacion_datos = []
    jornada_obj = None
    partidos_jornada = []
    mostrar_clasificacion = True
    clasificacion_jornada_num = None
    partidos_calendario = []

    if equipo_seleccionado:
        try:
            equipo_obj = Equipo.objects.get(nombre=equipo_seleccionado)
            partidos_calendario = Calendario.objects.filter(
                jornada__temporada=temporada
            ).filter(
                Q(equipo_local=equipo_obj) | Q(equipo_visitante=equipo_obj)
            ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by(
                'jornada__numero_jornada', 'fecha', 'hora'
            )

            ultima_jornada_con_clasificacion = Jornada.objects.filter(
                temporada=temporada,
                clasificacionjornada__isnull=False,
            ).order_by('numero_jornada').last()

            if ultima_jornada_con_clasificacion:
                clasificacion_datos = ClasificacionJornada.objects.filter(
                    temporada=temporada,
                    jornada=ultima_jornada_con_clasificacion,
                ).order_by('posicion', 'equipo__nombre').select_related('equipo')

                for reg in clasificacion_datos:
                    palabras = reg.equipo.nombre.split()
                    reg.iniciales = ''.join([p[0].upper() for p in palabras])
                    total_pj = reg.partidos_ganados + reg.partidos_empatados + reg.partidos_perdidos
                    reg.diferencia_jornada = total_pj - ultima_jornada_con_clasificacion.numero_jornada
                    reg.racha_detalles = get_racha_detalles(reg.equipo, temporada, ultima_jornada_con_clasificacion)

                clasificacion_jornada_num = ultima_jornada_con_clasificacion.numero_jornada
                mostrar_clasificacion = True
            else:
                mostrar_clasificacion = False

        except Equipo.DoesNotExist:
            equipo_seleccionado = ''
            mostrar_clasificacion = True
            partidos_calendario = []

    if not equipo_seleccionado:
        if jornadas.exists():
            try:
                jornada_obj = jornadas.get(numero_jornada=int(jornada_num))
            except (Jornada.DoesNotExist, ValueError):
                jornada_obj = jornadas.first()
                jornada_num = jornada_obj.numero_jornada if jornada_obj else 1

            if jornada_obj:
                clasificacion_datos = ClasificacionJornada.objects.filter(
                    temporada=temporada,
                    jornada=jornada_obj,
                ).order_by('posicion', 'equipo__nombre').select_related('equipo')

                clasificacion_jornada_num = jornada_obj.numero_jornada

                for reg in clasificacion_datos:
                    palabras = reg.equipo.nombre.split()
                    reg.iniciales = ''.join([p[0].upper() for p in palabras])
                    total_pj = reg.partidos_ganados + reg.partidos_empatados + reg.partidos_perdidos
                    reg.diferencia_jornada = total_pj - jornada_obj.numero_jornada
                    reg.racha_detalles = get_racha_detalles(reg.equipo, temporada, jornada_obj)

                partidos_calendario = Calendario.objects.filter(
                    jornada=jornada_obj
                ).select_related('equipo_local', 'equipo_visitante').order_by('fecha', 'hora')
        else:
            partidos_calendario = []

    # Enriquecer con resultados y sucesos
    for partido_cal in partidos_calendario:
        partido_info = {
            'local': partido_cal.equipo_local.nombre,
            'visitante': partido_cal.equipo_visitante.nombre,
            'estadio': partido_cal.equipo_local.estadio or 'Estadio desconocido',
            'fecha': partido_cal.fecha,
            'hora': partido_cal.hora,
            'goles_local': None,
            'goles_visitante': None,
            'jugado': False,
            'sucesos': {
                'goles_local': [], 'goles_visitante': [],
                'amarillas_local': [], 'amarillas_visitante': [],
                'rojas_local': [], 'rojas_visitante': [],
            },
        }

        partido_jugado = Partido.objects.filter(
            jornada=partido_cal.jornada,
            equipo_local=partido_cal.equipo_local,
            equipo_visitante=partido_cal.equipo_visitante,
        ).first()

        if partido_jugado and partido_jugado.goles_local is not None and partido_jugado.goles_visitante is not None:
            partido_info['goles_local'] = partido_jugado.goles_local
            partido_info['goles_visitante'] = partido_jugado.goles_visitante
            partido_info['jugado'] = True

            for stat in EstadisticasPartidoJugador.objects.filter(
                partido=partido_jugado
            ).select_related('jugador'):
                es_local = EquipoJugadorTemporada.objects.filter(
                    jugador=stat.jugador,
                    equipo=partido_cal.equipo_local,
                    temporada=temporada,
                ).exists()
                nombres = f"{stat.jugador.nombre} {stat.jugador.apellido}".strip()

                for _ in range(stat.gol_partido or 0):
                    key = 'goles_local' if es_local else 'goles_visitante'
                    partido_info['sucesos'][key].append({'nombre': nombres, 'minuto': stat.min_partido})
                for _ in range(stat.amarillas or 0):
                    key = 'amarillas_local' if es_local else 'amarillas_visitante'
                    partido_info['sucesos'][key].append({'nombre': nombres, 'minuto': stat.min_partido})
                for _ in range(stat.rojas or 0):
                    key = 'rojas_local' if es_local else 'rojas_visitante'
                    partido_info['sucesos'][key].append({'nombre': nombres, 'minuto': stat.min_partido})

        partidos_jornada.append(partido_info)

    context = {
        'active_page': 'liga',
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_display,
        'temporada_nombre': temporada_nombre,
        'jornadas': jornadas,
        'jornada_actual': int(jornada_num) if jornadas.exists() else 1,
        'clasificacion': clasificacion_datos,
        'partidos_jornada': partidos_jornada,
        'equipos_disponibles': equipos_disponibles,
        'equipo_seleccionado': equipo_seleccionado,
        'clasificacion_jornada': clasificacion_jornada_num,
    }

    return render(request, 'clasificacion.html', context)
