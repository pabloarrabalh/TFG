"""Plantilla (fantasy squad) views"""
import json
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum

from ..models import (
    Temporada, Jornada, Equipo, Partido, Calendario,
    EquipoJugadorTemporada, EstadisticasPartidoJugador, Plantilla,
)

logger = logging.getLogger(__name__)


def _get_partidos_por_jornada(jornada_actual):
    """Returns a dict mapping equipo_id → {rival_id, rival_nombre, es_local}."""
    resultado = {}
    if not jornada_actual:
        return resultado

    partidos = Partido.objects.filter(jornada=jornada_actual).select_related('equipo_local', 'equipo_visitante')
    for partido in partidos:
        resultado[partido.equipo_local.id] = {
            'rival_id': partido.equipo_visitante.id,
            'rival_nombre': partido.equipo_visitante.nombre,
            'es_local': True,
        }
        resultado[partido.equipo_visitante.id] = {
            'rival_id': partido.equipo_local.id,
            'rival_nombre': partido.equipo_local.nombre,
            'es_local': False,
        }

    if not resultado:
        # fallback to Calendario
        for cal in Calendario.objects.filter(jornada=jornada_actual).select_related('equipo_local', 'equipo_visitante'):
            resultado[cal.equipo_local.id] = {
                'rival_id': cal.equipo_visitante.id,
                'rival_nombre': cal.equipo_visitante.nombre,
                'es_local': True,
            }
            resultado[cal.equipo_visitante.id] = {
                'rival_id': cal.equipo_local.id,
                'rival_nombre': cal.equipo_local.nombre,
                'es_local': False,
            }

    return resultado


@login_required(login_url='login_register')
def mi_plantilla(request):
    """Vista de Mi Plantilla - Requiere autenticación"""
    temporada_actual = Temporada.objects.last()

    if not temporada_actual:
        context = {
            'active_page': 'mi-plantilla',
            'jugadores_json': json.dumps({'Portero': [], 'Defensa': [], 'Centrocampista': [], 'Delantero': []}),
            'plantilla_guardada': json.dumps({}),
            'equipos_json': json.dumps([]),
            'plantillas': [],
            'plantilla_actual': None,
            'jornadas': [],
            'jornada_actual': None,
        }
        return render(request, 'mi_plantilla.html', context)

    jornadas_qs = Jornada.objects.filter(temporada=temporada_actual).order_by('numero_jornada')
    jornadas = list(jornadas_qs.values('id', 'numero_jornada'))

    jornada_param = request.GET.get('jornada')
    if jornada_param and jornada_param.isdigit():
        jornada_actual = Jornada.objects.filter(
            temporada=temporada_actual,
            numero_jornada=int(jornada_param),
        ).first()
    else:
        jornada_actual = jornadas_qs.last()

    jornada_num = jornada_actual.numero_jornada if jornada_actual else None

    equipos_temporada = Equipo.objects.filter(
        jugadores_temporada__temporada=temporada_actual
    ).distinct().order_by('nombre')
    equipos_list = [{'id': e.id, 'nombre': e.nombre} for e in equipos_temporada]

    partidos_por_jornada = _get_partidos_por_jornada(jornada_actual)

    jugadores_temporada = EquipoJugadorTemporada.objects.filter(
        temporada=temporada_actual
    ).select_related('jugador', 'equipo').order_by('jugador__nombre')

    jugadores_por_posicion = {'Portero': [], 'Defensa': [], 'Centrocampista': [], 'Delantero': []}

    for ejt in jugadores_temporada:
        posicion = ejt.posicion or 'Delantero'
        jugador = ejt.jugador

        stats_puntos = EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada_actual,
            jugador=jugador,
            puntos_fantasy__lte=50,
        ).aggregate(total_puntos=Sum('puntos_fantasy'))

        puntos_fantasy = stats_puntos['total_puntos'] or 0
        rival_jornada = partidos_por_jornada.get(ejt.equipo.id)

        if posicion in jugadores_por_posicion:
            jugadores_por_posicion[posicion].append({
                'id': jugador.id,
                'nombre': jugador.nombre,
                'apellido': jugador.apellido,
                'posicion': posicion,
                'equipo_id': ejt.equipo.id,
                'equipo_nombre': ejt.equipo.nombre,
                'puntos_fantasy_25_26': puntos_fantasy,
                'proximo_rival_id': rival_jornada['rival_id'] if rival_jornada else None,
                'proximo_rival_nombre': rival_jornada['rival_nombre'] if rival_jornada else None,
            })

    plantillas = []
    plantilla_actual = None
    plantilla_actual_id = None
    if request.user.is_authenticated:
        plantillas_qs = Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada')
        plantillas = list(plantillas_qs.values('id', 'nombre', 'formacion', 'alineacion'))
        if plantillas:
            plantilla_actual = plantillas[0]
            plantilla_actual_id = plantilla_actual['id']

    if not plantilla_actual:
        plantilla_actual = {
            'id': None,
            'formacion': '4-3-3',
            'alineacion': {
                'Portero': [], 'Defensa': [], 'Centrocampista': [], 'Delantero': [], 'Suplentes': []
            },
            'nombre': 'Mi Team',
        }
        if (request.user.is_authenticated
                and request.user.profile.plantilla_guardada
                and request.user.profile.plantilla_guardada != '{}'):
            try:
                old_data = json.loads(request.user.profile.plantilla_guardada)
                plantilla_actual.update(old_data)
            except Exception:
                pass

    context = {
        'active_page': 'mi-plantilla',
        'jugadores_json': json.dumps(jugadores_por_posicion),
        'plantilla_guardada': json.dumps(plantilla_actual),
        'equipos_json': json.dumps(equipos_list),
        'plantillas': json.dumps(plantillas),
        'plantilla_actual': plantilla_actual,
        'plantilla_actual_id': plantilla_actual_id,
        'jornadas': json.dumps(jornadas),
        'jornada_actual': jornada_num,
        'temporada_actual': temporada_actual.nombre if temporada_actual else '25/26',
    }

    return render(request, 'mi_plantilla.html', context)


@login_required(login_url='login_register')
def guardar_plantilla(request):
    """Guardar o actualizar una plantilla del usuario"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        plantilla_id = data.get('plantilla_id')
        nombre = data.get('nombre', 'Mi Team')
        formacion = data.get('formacion', '4-3-3')
        alineacion = data.get('alineacion', {})

        if plantilla_id:
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            plantilla.nombre = nombre
            plantilla.formacion = formacion
            plantilla.alineacion = alineacion
            plantilla.save()
            mensaje = 'Plantilla actualizada correctamente'
        else:
            contador = 1
            nombre_original = nombre
            while Plantilla.objects.filter(usuario=request.user, nombre=nombre).exists():
                nombre = f"{nombre_original} ({contador})"
                contador += 1
            plantilla = Plantilla.objects.create(
                usuario=request.user, nombre=nombre, formacion=formacion, alineacion=alineacion
            )
            mensaje = f'Plantilla "{nombre}" guardada correctamente'

        return JsonResponse({'status': 'success', 'message': mensaje,
                             'plantilla_id': plantilla.id, 'plantilla_nombre': plantilla.nombre})
    except Plantilla.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Plantilla no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login_register')
def listar_plantillas(request):
    """Obtener todas las plantillas del usuario"""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        plantillas = Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada').values(
            'id', 'nombre', 'formacion', 'alineacion', 'predeterminada', 'fecha_creada', 'fecha_modificada'
        )
        return JsonResponse({'status': 'success', 'plantillas': list(plantillas)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login_register')
def obtener_plantilla(request, plantilla_id):
    """Obtener una plantilla específica del usuario"""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
        return JsonResponse({'status': 'success', 'plantilla': {
            'id': plantilla.id,
            'nombre': plantilla.nombre,
            'formacion': plantilla.formacion,
            'alineacion': plantilla.alineacion,
        }})
    except Plantilla.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Plantilla no encontrada'}, status=404)


@login_required(login_url='login_register')
def eliminar_plantilla(request, plantilla_id):
    """Eliminar una plantilla del usuario"""
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
        nombre = plantilla.nombre
        plantilla.delete()
        return JsonResponse({'status': 'success', 'message': f'Plantilla "{nombre}" eliminada correctamente'})
    except Plantilla.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Plantilla no encontrada'}, status=404)


@login_required(login_url='login_register')
def renombrar_plantilla(request, plantilla_id):
    """Renombrar una plantilla del usuario"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        nuevo_nombre = data.get('nombre', '').strip()

        if not nuevo_nombre:
            return JsonResponse({'status': 'error', 'message': 'El nombre no puede estar vacío'}, status=400)

        plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)

        if Plantilla.objects.filter(usuario=request.user, nombre=nuevo_nombre).exclude(id=plantilla_id).exists():
            return JsonResponse({'status': 'error', 'message': 'Ya existe una plantilla con ese nombre'}, status=400)

        plantilla.nombre = nuevo_nombre
        plantilla.save()

        return JsonResponse({'status': 'success',
                             'message': f'Plantilla renombrada a "{nuevo_nombre}"',
                             'nuevo_nombre': nuevo_nombre})
    except Plantilla.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Plantilla no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
