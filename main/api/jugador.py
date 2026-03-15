"""
DRF API views – Player Detail & Top Players
Endpoints:
  GET /api/jugador/<id>/?temporada=25/26
  GET /api/top-jugadores-por-posicion/?temporada=25/26
"""
import math
import json
import logging

from django.db.models import Q, Sum, Avg, Count
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny

from ..models import *
from ..views.utils import shield_name

try:
    from main.scrapping.roles import DESCRIPCIONES_ROLES
except Exception:
    DESCRIPCIONES_ROLES = {}

logger = logging.getLogger(__name__)


# ── Custom JSON encoder for NaN/Inf handling ────────────────────────────────

class NaNInfEncoder(json.JSONEncoder):
    """Custom JSON encoder that replaces NaN/Inf with null or 0"""
    def encode(self, o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return '0'
        return super().encode(o)
    
    def iterencode(self, o, _one_shot=False):
        """Yield JSON string chunks while sanitizing NaN/Inf"""
        for chunk in super().iterencode(o, _one_shot):
            # Replace any NaN/Inf that might have slipped through
            chunk = chunk.replace('NaN', '0').replace('Infinity', '0').replace('-Infinity', '0')
            yield chunk


# ── Global sanitizer for JSON serialization ─────────────────────────────────────

def _safe_float(val, default=0):
    """Safely convert to float, replacing NaN/Inf with default value."""
    if val is None:
        return default
    try:
        if math.isnan(val) or math.isinf(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _sanitize_dict(d, default=0):
    """Recursively sanitize a dict, replacing any NaN/Inf floats with default."""
    if d is None:
        return None
    if not isinstance(d, dict):
        # Handle primitive types
        if isinstance(d, float):
            if math.isnan(d) or math.isinf(d):
                return default
            return d
        elif isinstance(d, (int, str, bool)):
            return d
        return d
    
    result = {}
    for k, v in d.items():
        if v is None:
            result[k] = None
        elif isinstance(v, dict):
            result[k] = _sanitize_dict(v, default)
        elif isinstance(v, (list, tuple)):
            # Sanitize each item in list
            sanitized_list = []
            for item in v:
                if isinstance(item, dict):
                    sanitized_list.append(_sanitize_dict(item, default))
                elif isinstance(item, float):
                    if math.isnan(item) or math.isinf(item):
                        sanitized_list.append(default)
                    else:
                        sanitized_list.append(item)
                else:
                    sanitized_list.append(item)
            result[k] = sanitized_list if isinstance(v, list) else tuple(sanitized_list)
        elif isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                result[k] = default
            else:
                result[k] = v
        else:
            result[k] = v
    return result


# ── helper ────────────────────────────────────────────────────────────────────

def _get_datos_temporada_completa(jugador, temporada):
    """
    Returns array with ALL jornadas of the season, including:
    - predictions (real or null)
    - partido stats (real or null) 
    - structured for frontend to display all jornadas even without data
    """
    # Get all jornadas sorted
    todas_jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    if not todas_jornadas.exists():
        return []
    
    # Fetch predictions (if exist)
    pred_qs = PrediccionJugador.objects.filter(jugador=jugador, jornada__temporada=temporada)
    pred_by_jornada = {p.jornada_id: p for p in pred_qs}
    
    # Fetch real stats
    stats_qs = EstadisticasPartidoJugador.objects.filter(
        jugador=jugador, partido__jornada__temporada=temporada
    ).select_related('partido__jornada')
    stats_by_jornada = {}
    for stat in stats_qs:
        j = stat.partido.jornada
        if j.pk not in stats_by_jornada:
            stats_by_jornada[j.pk] = []
        stats_by_jornada[j.pk].append(stat)
    
    # Build result for EVERY jornada
    result = []
    for jornada in todas_jornadas:
        pred = pred_by_jornada.get(jornada.pk)
        stats = stats_by_jornada.get(jornada.pk, [])
        
        # Real points (sum if multiple matches)
        real_pts = None
        if stats:
            real_pts = sum(s.puntos_fantasy or 0 for s in stats)
        
        # Prediction value
        pred_value = None
        if pred:
            pred_value = round(pred.prediccion, 2) if pred.prediccion is not None else None
        
        result.append({
            'jornada': jornada.numero_jornada,
            'temporada': jornada.temporada.nombre.replace('_', '/'),
            'prediccion': pred_value,
            'real': real_pts,
            'modelo': pred.modelo if pred else None,
            'is_early_jornada': jornada.numero_jornada <= 5,
        })
    
    return result


def _get_ultimos_8_temporada_completa(jugador, temporada):
    """
    Returns array with ALL jornadas for histogram, even without partido data.
    Frontend shows empty bars for jornadas without matches.
    """
    todas_jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    if not todas_jornadas.exists():
        return []
    
    stats_qs = EstadisticasPartidoJugador.objects.filter(
        jugador=jugador, partido__jornada__temporada=temporada
    ).exclude(puntos_fantasy__gt=40).select_related('partido__jornada')
    
    stats_by_jornada = {}
    for stat in stats_qs:
        j = stat.partido.jornada
        if j.pk not in stats_by_jornada:
            stats_by_jornada[j.pk] = stat
    
    result = []
    for jornada in todas_jornadas:
        stat = stats_by_jornada.get(jornada.pk)
        if stat:
            result.append({
                'puntos_fantasy': float(stat.puntos_fantasy or 0),
                'partido': {
                    'jornada': {'numero_jornada': stat.partido.jornada.numero_jornada}
                },
            })
        else:
            # No data for this jornada - include empty structure
            result.append({
                'puntos_fantasy': None,
                'partido': {
                    'jornada': {'numero_jornada': jornada.numero_jornada}
                },
            })
    
    return result


def _get_predicciones_jugador(jugador, temporada):
    """Returns predictions paired with real points.
    Includes ALL jornadas with predictions (even if no real data yet).
    Also includes all played jornadas (even without predictions) so the real bar renders.
    """
    def _sanitize_float(value):
        """Convert inf/nan to None for JSON serialization"""
        if value is None:
            return None
        try:
            if math.isnan(value) or math.isinf(value):
                return None
            return value
        except (TypeError, ValueError):
            return None
    
    # 1. Fetch all predictions (evaluating queryset into a list avoids re-querying)
    pred_qs = PrediccionJugador.objects.filter(jugador=jugador)
    if temporada:
        pred_qs = pred_qs.filter(jornada__temporada=temporada)
    predictions = list(pred_qs.select_related('jornada__temporada'))

    pred_by_jornada_id = {p.jornada_id: p for p in predictions}
    jornada_by_id = {p.jornada_id: p.jornada for p in predictions}  # ALL jornadas with predictions

    # 2. Fetch real stats in a single query (avoids N+1)
    stats_qs = EstadisticasPartidoJugador.objects.filter(jugador=jugador)
    if temporada:
        stats_qs = stats_qs.filter(partido__jornada__temporada=temporada)

    real_by_jornada_id = {}
    for stat in stats_qs.select_related('partido__jornada__temporada'):
        j = stat.partido.jornada
        real_by_jornada_id[j.pk] = real_by_jornada_id.get(j.pk, 0) + (stat.puntos_fantasy or 0)
        # Register jornada so played jornadas without predictions are also included
        jornada_by_id[j.pk] = j

    # 3. Build result for every jornada (predictions + any played jornada + future jornadas with predictions)
    result = []
    for jornada_id, j in jornada_by_id.items():
        pred = pred_by_jornada_id.get(jornada_id)
        real = real_by_jornada_id.get(jornada_id)
        
        pred_value = None
        if pred:
            sanitized_pred = _sanitize_float(pred.prediccion)
            pred_value = round(sanitized_pred, 2) if sanitized_pred is not None else None
        
        real_value = None
        if real is not None:
            sanitized_real = _sanitize_float(real)
            real_value = float(sanitized_real) if sanitized_real is not None else None
        
        result.append({
            'jornada': j.numero_jornada,
            'temporada': j.temporada.nombre.replace('_', '/'),
            'prediccion': pred_value,
            'real': real_value,
            'modelo': pred.modelo if pred else None,
            'is_early_jornada': j.numero_jornada <= 5,
        })

    result.sort(key=lambda x: x['jornada'])
    return result


def _generar_predicciones_faltantes(jugador, temporada):
    """
    Genera predicciones faltantes para un jugador en una temporada.
    Se ejecuta on-demand cuando se accede a la página del jugador.
    """
    if not jugador or not temporada:
        return
    
    try:
        import sys
        from pathlib import Path
        entrenamientos_path = Path(__file__).resolve().parents[2] / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))
        
        from predecir import predecir_puntos
        
        # Obtener posición del jugador
        ejt = EquipoJugadorTemporada.objects.filter(
            jugador=jugador, temporada=temporada
        ).first()
        posicion = ejt.posicion if ejt else jugador.get_posicion_mas_frecuente() or 'Delantero'
        
        # Obtener todas las jornadas de la temporada
        jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
        
        # Para cada jornada, generar predicción si no existe
        for jornada in jornadas:
            # Chequear si ya existe
            if PrediccionJugador.objects.filter(jugador=jugador, jornada=jornada).exists():
                continue
            
            # Generar predicción bajo demanda
            try:
                # Para jornadas 1-5, usar Baseline (media histórica); para jornadas 6+, usar modelo ML
                modelo_para_pred = 'Baseline' if jornada.numero_jornada <= 5 else None
                
                resultado = predecir_puntos(
                    jugador.pk,
                    posicion,
                    jornada_actual=jornada.numero_jornada,
                    verbose=False,
                    modelo_tipo=modelo_para_pred
                )
                
                if resultado and isinstance(resultado, dict) and not resultado.get('error'):
                    prediction = resultado.get('prediccion')
                    if prediction is not None:
                        # Determinar qué modelo se usó (según jornada)
                        modelo_usado = 'baseline' if jornada.numero_jornada <= 5 else 'rf'
                        PrediccionJugador.objects.update_or_create(
                            jugador=jugador,
                            jornada=jornada,
                            modelo=modelo_usado,
                            defaults={'prediccion': float(prediction)}
                        )
            except Exception as e:
                logger.debug(f"Error generando predicción para {jugador} J{jornada.numero_jornada}: {e}")
                continue
    except Exception as e:
        logger.debug(f"Error en _generar_predicciones_faltantes: {e}")


# ── views ─────────────────────────────────────────────────────────────────────

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

        # FALLBACK: Si la temporada solicitada no tiene datos, usar la primera disponible
        temporada = None
        if not es_carrera:
            try:
                temporada = Temporada.objects.get(nombre=temporada_nombre)
                # Verificar que tiene datos
                if not EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador, partido__jornada__temporada=temporada
                ).exists():
                    temporada = None
            except Temporada.DoesNotExist:
                temporada = None
        
        # Si no se encontró temporada, usar la primera con datos
        if temporada is None:
            for t in Temporada.objects.order_by('-nombre'):
                if EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador, partido__jornada__temporada=t
                ).exists():
                    temporada = t
                    break
        
        # Si aún no hay temporada, usar la última de todas
        if temporada is None:
            temporada = Temporada.objects.order_by('-nombre').first()

        # Generar predicciones faltantes under-demand (no bloquea, se ejecuta rápido si ya existen)
        if temporada and not es_carrera:
            try:
                _generar_predicciones_faltantes(jugador, temporada)
            except Exception as e:
                logger.debug(f"Error generando predicciones para {jugador}: {e}")

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

        filter_query = (
            Q(jugador=jugador)
            if es_carrera
            else Q(jugador=jugador, partido__jornada__temporada=temporada)
        )

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

        # Use new function that includes ALL jornadas, even without data
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
            ultimos_12_data = _get_ultimos_8_temporada_completa(jugador, temporada)

        # Roles
        roles = self._build_roles(jugador, temporada, es_carrera)

        # Histórico de carrera
        historico_data = self._build_historico(jugador)

        # Temporadas disponibles
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
        
        # Sanitize float values to prevent JSON serialization errors
        import math
        def _safe_float(val, default=0):
            if val is None:
                return default
            try:
                if math.isnan(val) or math.isinf(val):
                    return default
                return val
            except (TypeError, ValueError):
                return default
        
        # Build response with all floats sanitized
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
                'promedio_puntos': round(_safe_float(st['promedio_puntos']), 1),
                'ataque': {
                    'goles': st['goles'] or 0,
                    'xg': round(_safe_float(st['xg']), 2),
                    'tiros': st['tiros'] or 0,
                    'tiros_puerta': st['tiros_puerta'] or 0,
                },
                'organizacion': {
                    'asistencias': st['asistencias'] or 0,
                    'xag': round(_safe_float(st['xag']), 2),
                    'pases': st['pases_totales'] or 0,
                    'pases_accuracy': round(_safe_float(st['pases_accuracy']), 1),
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
                    'porcentaje_paradas': round(_safe_float(st.get('porcentaje_paradas')), 1),
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
            'predicciones': _get_datos_temporada_completa(
                jugador, temporada if not es_carrera else None
            ) if not es_carrera else [],
        }
        
        # Sanitize the dict deeply to remove NaN/Inf
        response_data = _sanitize_dict(response_data)
        
        # Try to serialize to JSON to catch any NaN/Inf failures
        try:
            test_json = json.dumps(response_data)
            logger.debug(f"Response JSON serialization OK for jugador {jugador_id}")
        except ValueError as e:
            logger.error(f"JSON serialization error for jugador {jugador_id}: {e}")
            # Try to identify the problematic field
            for key in ['stats', 'ultimos_8', 'historico', 'predicciones']:
                if key in response_data:
                    try:
                        json.dumps(response_data[key])
                    except ValueError as field_error:
                        logger.error(f"Problem in field '{key}': {field_error}")
            # Fallback: return empty stats
            response_data['stats'] = {}
        
        return Response(response_data)

    @staticmethod
    def _build_roles(jugador, temporada, es_carrera):
        if es_carrera:
            roles_por_temporada = []
            for ejt in (
                EquipoJugadorTemporada.objects.filter(jugador=jugador)
                .select_related('temporada')
                .order_by('-temporada__nombre')[:3]
            ):
                stats_con_roles = (
                    EstadisticasPartidoJugador.objects.filter(
                        jugador=jugador,
                        partido__jornada__temporada=ejt.temporada,
                        roles__isnull=False,
                    )
                    .exclude(puntos_fantasy__gt=40)
                    .exclude(roles__exact=[])
                    .values_list('roles', flat=True)
                )
                roles_dict = {}
                for stats_roles in stats_con_roles:
                    if stats_roles and isinstance(stats_roles, list):
                        for role_obj in stats_roles:
                            if isinstance(role_obj, dict):
                                for fn, values in role_obj.items():
                                    if fn not in roles_dict or values[0] < roles_dict[fn][0]:
                                        roles_dict[fn] = values
                if roles_dict:
                    roles_por_temporada.append({
                        'temporada': ejt.temporada.nombre.replace('_', '/'),
                        'roles': [{k: v} for k, v in roles_dict.items()],
                    })
            return roles_por_temporada

        stats_con_roles = (
            EstadisticasPartidoJugador.objects.filter(
                jugador=jugador,
                partido__jornada__temporada=temporada,
                roles__isnull=False,
            )
            .exclude(puntos_fantasy__gt=40)
            .exclude(roles__exact=[])
            .values_list('roles', flat=True)
        )
        roles_dict = {}
        for stats_roles in stats_con_roles:
            if stats_roles and isinstance(stats_roles, list):
                for role_obj in stats_roles:
                    if isinstance(role_obj, dict):
                        for fn, values in role_obj.items():
                            if fn not in roles_dict or values[0] < roles_dict[fn][0]:
                                roles_dict[fn] = values
        return [{k: v} for k, v in roles_dict.items()] if roles_dict else []

    @staticmethod
    def _build_historico(jugador):
        historico_data = []
        for hist in (
            EquipoJugadorTemporada.objects.filter(jugador=jugador)
            .select_related('equipo', 'temporada')
            .order_by('-temporada__nombre')
        ):
            sh = (
                EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador, partido__jornada__temporada=hist.temporada
                )
                .exclude(puntos_fantasy__gt=40)
                .aggregate(
                    goles=Sum('gol_partido'),
                    asistencias=Sum('asist_partido'),
                    minutos=Sum('min_partido'),
                    partidos=Count('id', filter=Q(min_partido__gt=0)),
                    puntos_totales=Sum('puntos_fantasy'),
                    pases=Sum('pases_totales'),
                    pases_accuracy=Avg('pases_completados_pct'),
                    xag=Sum('xag'),
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
                    regates_completados=Sum('regates_completados'),
                    regates_fallidos=Sum('regates_fallidos'),
                    conducciones=Sum('conducciones'),
                    conducciones_progresivas=Sum('conducciones_progresivas'),
                    distancia_conduccion=Sum('distancia_conduccion'),
                )
            )
            partidos = sh['partidos'] or 0
            puntos_totales = sh['puntos_totales'] or 0
            ppp = round(puntos_totales / partidos, 1) if partidos > 0 else 0
            historico_data.append({
                'temporada': hist.temporada.nombre.replace('_', '/'),
                'equipo': hist.equipo.nombre,
                'dorsal': hist.dorsal or '-',
                'puntos_totales': puntos_totales,
                'puntos_por_partido': ppp,
                'goles': sh['goles'] or 0,
                'asistencias': sh['asistencias'] or 0,
                'pj': partidos,
                'minutos': sh['minutos'] or 0,
                'pases': sh['pases'] or 0,
                'pases_accuracy': round(_safe_float(sh['pases_accuracy']), 1),
                'xag': round(_safe_float(sh['xag']), 2),
                'despejes': sh['despejes'] or 0,
                'entradas': sh['entradas'] or 0,
                'duelos_totales': (sh['duelos_ganados'] or 0) + (sh['duelos_perdidos'] or 0),
                'amarillas': sh['amarillas'] or 0,
                'rojas': sh['rojas'] or 0,
                'bloqueos': sh['bloqueos'] or 0,
                'duelos_aereos_totales': (
                    (sh['duelos_aereos_ganados'] or 0) + (sh['duelos_aereos_perdidos'] or 0)
                ),
                'tiros': sh['tiros'] or 0,
                'tiros_puerta': sh['tiros_puerta'] or 0,
                'xg': round(_safe_float(sh['xg']), 2),
                'regates_completados': sh['regates_completados'] or 0,
                'regates_fallidos': sh['regates_fallidos'] or 0,
                'conducciones': sh['conducciones'] or 0,
                'conducciones_progresivas': sh['conducciones_progresivas'] or 0,
                'distancia_conduccion': round(_safe_float(sh['distancia_conduccion']), 1),
            })
        return historico_data


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
                except Exception as exc:
                    logger.debug('Error procesando jugador %s: %s', j.get('jugador_id'), exc)

            resultado[posicion] = jugadores_list

        return Response({
            'status': 'ok',
            'temporada': temporada_display,
            'jornada': jornada.numero_jornada,
            'jugadores_por_posicion': resultado,
        })
