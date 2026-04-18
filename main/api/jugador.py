import json
from django.db.models import Q, Sum, Avg, Count
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from .common import safe_float, sanitize_payload
from ..models import *
from ..utils.jugador_service import (
    build_historico,
    build_roles,
    generar_predicciones_faltantes,
    get_datos_temporada_completa,
    get_ultimos_8_temporada_completa,
)
from ..views.utils import shield_name

try:
    from main.scrapping.roles import DESCRIPCIONES_ROLES
except Exception:
    DESCRIPCIONES_ROLES = {}

class JugadorDetailView(APIView):
    """GET /api/jugador/<jugador_id>/?temporada=25/26"""
    permission_classes = [AllowAny]

    def get(self, request, jugador_id):
        temporada_display = request.GET.get('temporada', '25/26')
        temporada_nombre = temporada_display.replace('/', '_')
        es_carrera = temporada_display == 'carrera'

        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return Response({'error': 'Jugador no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        temporada = None
        if not es_carrera:
            try:
                temporada = Temporada.objects.get(nombre=temporada_nombre)
                if not EstadisticasPartidoJugador.objects.filter( jugador=jugador, partido__jornada__temporada=temporada).exists():
                    temporada = None
            except Temporada.DoesNotExist:
                temporada = None
        
        if temporada is None:
            for t in Temporada.objects.order_by('-nombre'):
                if EstadisticasPartidoJugador.objects.filter(jugador=jugador, partido__jornada__temporada=t).exists():
                    temporada = t
                    break
        
        if temporada is None:
            temporada = Temporada.objects.order_by('-nombre').first()

        if temporada and not es_carrera:
            try:
                generar_predicciones_faltantes(jugador, temporada)
            except Exception:
                pass

        posicion = jugador.get_posicion_mas_frecuente() or ''

        equipo_temporada = None
        edad = 0
        ejt = None
        try:
            if es_carrera:
                ejt = (
                    EquipoJugadorTemporada.objects.filter(jugador=jugador)
                    .select_related('equipo', 'temporada')
                    .order_by('-temporada__nombre')
                    .first()
                )
            else:
                ejt = EquipoJugadorTemporada.objects.filter(
                    jugador=jugador, temporada=temporada
                ).select_related('equipo').first()

            if ejt:
                equipo_temporada = {
                    'equipo': {
                        'nombre': ejt.equipo.nombre,
                        'escudo': f'/static/escudos/{shield_name(ejt.equipo.nombre)}.png',
                    },
                    'dorsal': ejt.dorsal or '-',
                }
                edad = ejt.edad or 0
        except Exception:
            pass

        filter_query = (Q(jugador=jugador) if es_carrera else Q(jugador=jugador, partido__jornada__temporada=temporada))

        stats_totales = (
            EstadisticasPartidoJugador.objects.filter(filter_query)
            .exclude(puntos_fantasy__gt=40)
            .aggregate(
                goles=Sum('gol_partido'),
                asistencias=Sum('asist_partido'),
                minutos=Sum('min_partido'),
                partidos=Count('id', filter=Q(min_partido__gt=0)),
                promedio_puntos=Avg('puntos_fantasy'),
                pases_totales=Sum('pases_totales'),
                pases_accuracy=Avg('pases_completados_pct'),
                xag=Sum('xag'),
                regates_completados=Sum('regates_completados'),
                regates_fallidos=Sum('regates_fallidos'),
                conducciones=Sum('conducciones'),
                conducciones_progresivas=Sum('conducciones_progresivas'),
                distancia_conduccion=Sum('distancia_conduccion'),
                despejes=Sum('despejes'),
                entradas=Sum('entradas'),
                duelos_ganados=Sum('duelos_ganados'),
                duelos_perdidos=Sum('duelos_perdidos'),
                amarillas=Sum('amarillas'),
                rojas=Sum('rojas'),
                bloqueos=Sum('bloqueos'),
                duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
                duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
                tiros=Sum('tiros'),
                tiros_puerta=Sum('tiro_puerta_partido'),
                xg=Sum('xg_partido'),
                goles_en_contra=Sum('goles_en_contra'),
                porcentaje_paradas=Avg('porcentaje_paradas'),
            )
        )

        if es_carrera:
            ultimos_qs = (
                EstadisticasPartidoJugador.objects.filter(jugador=jugador)
                .exclude(puntos_fantasy__gt=40)
                .select_related('partido__jornada')
                .order_by(
                    '-partido__jornada__temporada__nombre',
                    '-partido__jornada__numero_jornada',
                )
            )
        else:
            ultimos_qs = (
                EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador, partido__jornada__temporada=temporada
                )
                .exclude(puntos_fantasy__gt=40)
                .select_related('partido__jornada')
                .order_by('-partido__jornada__numero_jornada')
            )

        if es_carrera:
            ultimos_12_data = [
                {
                    'puntos_fantasy': float(s.puntos_fantasy or 0),
                    'partido': {
                        'jornada': {'numero_jornada': s.partido.jornada.numero_jornada}
                    },
                }
                for s in reversed(list(ultimos_qs))
            ]
        else:
            ultimos_12_data = get_ultimos_8_temporada_completa(jugador, temporada)

        roles = build_roles(jugador, temporada, es_carrera)
        historico_data = build_historico(jugador)
        temporadas_disponibles = []
        for t in Temporada.objects.order_by('-nombre'):
            if EstadisticasPartidoJugador.objects.filter(
                jugador=jugador, partido__jornada__temporada=t
            ).exists():
                temporadas_disponibles.append(
                    {'nombre': t.nombre, 'display': t.nombre.replace('_', '/')}
                )

        percentiles = {}
        if not es_carrera and ejt:
            percentiles = ejt.percentiles if ejt.percentiles else {}

        st = stats_totales

        response_data = {
            'jugador': {
                'id': jugador.id,
                'nombre': jugador.nombre,
                'apellido': jugador.apellido,
                'nacionalidad': jugador.nacionalidad,
            },
            'equipo_temporada': equipo_temporada,
            'posicion': posicion,
            'edad': edad,
            'temporada_obj': {'nombre': temporada.nombre} if temporada else {},
            'temporada_display': 'Carrera' if es_carrera else temporada.nombre.replace('_', '/'),
            'es_carrera': es_carrera,
            'temporadas_disponibles': temporadas_disponibles,
            'stats': {
                'goles': st['goles'] or 0,
                'asistencias': st['asistencias'] or 0,
                'minutos': st['minutos'] or 0,
                'partidos': st['partidos'] or 0,
                'promedio_puntos': round(safe_float(st['promedio_puntos']), 1),
                'ataque': {
                    'goles': st['goles'] or 0,
                    'xg': round(safe_float(st['xg']), 2),
                    'tiros': st['tiros'] or 0,
                    'tiros_puerta': st['tiros_puerta'] or 0,
                },
                'organizacion': {
                    'asistencias': st['asistencias'] or 0,
                    'xag': round(safe_float(st['xag']), 2),
                    'pases': st['pases_totales'] or 0,
                    'pases_accuracy': round(safe_float(st['pases_accuracy']), 1),
                },
                'regates': {
                    'regates_completados': st['regates_completados'] or 0,
                    'regates_fallidos': st['regates_fallidos'] or 0,
                    'conducciones': st['conducciones'] or 0,
                    'conducciones_progresivas': st['conducciones_progresivas'] or 0,
                },
                'defensa': {
                    'entradas': st['entradas'] or 0,
                    'despejes': st['despejes'] or 0,
                    'duelos_totales': (st['duelos_ganados'] or 0) + (st['duelos_perdidos'] or 0),
                    'duelos_ganados': st['duelos_ganados'] or 0,
                    'duelos_perdidos': st['duelos_perdidos'] or 0,
                    'duelos_aereos_totales': (
                        (st['duelos_aereos_ganados'] or 0)
                        + (st['duelos_aereos_perdidos'] or 0)
                    ),
                    'duelos_aereos_ganados': st['duelos_aereos_ganados'] or 0,
                    'duelos_aereos_perdidos': st['duelos_aereos_perdidos'] or 0,
                },
                'comportamiento': {
                    'amarillas': st.get('amarillas', 0) or 0,
                    'rojas': st.get('rojas', 0) or 0,
                },
                'portero': {
                    'paradas': 0,
                    'goles_encajados': st.get('goles_en_contra', 0) or 0,
                    'porterias_cero': 0,
                    'porcentaje_paradas': round(safe_float(st.get('porcentaje_paradas')), 1),
                },
            },
            'ultimos_8': ultimos_12_data,
            'roles': roles,
            'es_roles_por_temporada': es_carrera,
            'historico': historico_data,
            'radar_values': [],
            'media_general': 0,
            'percentiles': percentiles,
            'descripciones_roles': DESCRIPCIONES_ROLES,
            'predicciones': get_datos_temporada_completa(
                jugador, temporada if not es_carrera else None
            ) if not es_carrera else [],
        }
        
        response_data = sanitize_payload(response_data)
        try:
            json.dumps(response_data)
        except ValueError:
            response_data['stats'] = {}
        
        return Response(response_data)

class TopJugadoresPorPosicionView(APIView):
    """GET /api/top-jugadores-por-posicion/?temporada=25/26"""
    permission_classes = [AllowAny]

    def get(self, request):
        temporada_display = request.GET.get('temporada', '25/26')
        temporada_nombre = temporada_display.replace('/', '_')

        try:
            temporada = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temporada = Temporada.objects.order_by('-nombre').first()

        if not temporada:
            return Response({
                'status': 'error',
                'message': 'No hay temporadas disponibles',
                'jugadores_por_posicion': {},
            })

        ultima_jornada_pred = (
            PrediccionJugador.objects.filter(jornada__temporada=temporada)
            .values_list('jornada', flat=True)
            .distinct()
            .order_by('-jornada__numero_jornada')
            .first()
        )

        if not ultima_jornada_pred:
            return Response({
                'status': 'no_predictions',
                'message': 'Aún no hay predicciones para esta temporada',
                'jugadores_por_posicion': {},
            })

        jornada = Jornada.objects.get(pk=ultima_jornada_pred)
        posiciones = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
        resultado = {}

        for posicion in posiciones:
            top_preds = (
                PrediccionJugador.objects.filter(
                    jornada=jornada,
                    jugador__equipos_temporada__posicion=posicion,
                    jugador__equipos_temporada__temporada=temporada,
                )
                .values('jugador_id', 'jugador__nombre', 'jugador__apellido')
                .annotate(pred_promedio=Avg('prediccion'))
                .order_by('-pred_promedio')
                .distinct()[:3]
            )

            jugadores_list = []
            for j in top_preds:
                try:
                    jugador = Jugador.objects.get(pk=j['jugador_id'])
                    ejt = EquipoJugadorTemporada.objects.filter(
                        jugador=jugador, temporada=temporada
                    ).first()
                    jugadores_list.append({
                        'id': jugador.id,
                        'nombre': jugador.nombre,
                        'apellido': jugador.apellido,
                        'posicion': posicion,
                        'prediccion': round(float(j['pred_promedio']), 2),
                        'equipo': ejt.equipo.nombre if ejt else '—',
                        'dorsal': str(ejt.dorsal) if ejt and ejt.dorsal else '—',
                    })
                except Exception:
                    continue

            resultado[posicion] = jugadores_list

        return Response({
            'status': 'ok',
            'temporada': temporada_display,
            'jornada': jornada.numero_jornada,
            'jugadores_por_posicion': resultado,
        })
