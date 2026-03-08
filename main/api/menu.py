"""
DRF API views – Menu / Home page data
Endpoints:
  GET /api/menu/
"""
import importlib
import logging
import sys as _sys
import threading as _th
from pathlib import Path

from django.core.cache import cache
from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from ..models import (
    Temporada, Jornada, Calendario, ClasificacionJornada,
    EquipoJugadorTemporada, EstadisticasPartidoJugador, PrediccionJugador,
    Partido,
)
from ..views.utils import shield_name
from ..cache_utils import cache_api_response
import math

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _serialize_partido_calendario(calendario):
    """Serializa un objeto Calendario a dict para la API."""
    return {
        'id': calendario.id,
        'equipo_local': calendario.equipo_local.nombre,
        'equipo_visitante': calendario.equipo_visitante.nombre,
        'equipo_local_escudo': shield_name(calendario.equipo_local.nombre),
        'equipo_visitante_escudo': shield_name(calendario.equipo_visitante.nombre),
        'fecha': calendario.fecha.strftime('%Y-%m-%d') if calendario.fecha else None,
        'hora': str(calendario.hora) if calendario.hora else None,
        'jornada': calendario.jornada.numero_jornada if calendario.jornada else None,
    }


def _get_jugadores_destacados_con_predicciones(temporada, proxima_jornada, jornada_actual=None):
    """
    Top 3 jugadores por posición según la predicción de puntos fantasy más reciente para
    la próxima jornada. Carga TODAS las predicciones disponibles de cualquier modelo y
    toma la más reciente por jugador; luego agrupa por posición y devuelve el top 3.
    """
    resultado = {}
    if not proxima_jornada or not temporada:
        return resultado

    posiciones = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']

    # 1) Todos los jugadores de la temporada con equipo y posición
    ejt_map = {
        e['jugador_id']: e
        for e in EquipoJugadorTemporada.objects
        .filter(temporada=temporada)
        .values('jugador_id', 'jugador__nombre', 'jugador__apellido',
                'equipo_id', 'equipo__nombre', 'posicion', 'dorsal')
    }

    # Skip players with < 60 total minutes in the last 3 PLAYED jornadas.
    # Use jornada number ordering; only consider actually-played matches.
    # Edge case: if fewer than 3 jornadas have been played, skip the filter.
    _played_nums = list(
        Partido.objects
        .filter(jornada__temporada=temporada, goles_local__isnull=False)
        .values_list('jornada__numero_jornada', flat=True)
        .distinct()
        .order_by('-jornada__numero_jornada')[:3]
    )
    if len(_played_nums) < 3:
        skip_pocos_minutos = set()
    else:
        _min_sum_fast: dict = {}
        for _row in (
            EstadisticasPartidoJugador.objects
            .filter(
                partido__jornada__temporada=temporada,
                partido__jornada__numero_jornada__in=_played_nums,
            )
            .values('jugador_id', 'min_partido')
        ):
            _jid = _row['jugador_id']
            _min_sum_fast[_jid] = _min_sum_fast.get(_jid, 0) + (_row['min_partido'] or 0)
        skip_pocos_minutos = {
            jid for jid in ejt_map
            if _min_sum_fast.get(jid, 0) < 60
        }

    # 2) Todas las predicciones para la próxima jornada (cualquier modelo, sin filtro de fecha)
    #    Ordenadas por fecha desc para que dedup tome la más reciente por jugador
    pred_rows = (
        PrediccionJugador.objects
        .filter(jornada=proxima_jornada)
        .values('jugador_id', 'jugador__nombre', 'jugador__apellido', 'prediccion', 'modelo')
        .order_by('-creada_en')
    )

    # Dedup por jugador_id: queda la predicción más reciente (skip NaN)
    pred_map = {}
    for row in pred_rows:
        jid = row['jugador_id']
        if jid not in pred_map:
            try:
                val = float(row['prediccion'])
                # Skip NaN and infinite values which break JSON encoding
                if not math.isfinite(val):
                    continue
                if val != val:  # NaN check (redundant but safe)
                    continue
            except (TypeError, ValueError):
                continue
            pred_map[jid] = row

    # 3) Próximo rival de cada equipo
    rival_map = {}
    for cal in (
        Calendario.objects
        .filter(jornada=proxima_jornada)
        .values('equipo_local_id', 'equipo_visitante_id',
                'equipo_local__nombre', 'equipo_visitante__nombre')
    ):
        rival_map[cal['equipo_local_id']] = cal['equipo_visitante__nombre']
        rival_map[cal['equipo_visitante_id']] = cal['equipo_local__nombre']

    # 4) Por posición: todos los candidatos con predicción → top 3
    candidatos_pos = {pos: [] for pos in posiciones}
    for jugador_id, pred in pred_map.items():
        ejt = ejt_map.get(jugador_id)
        if not ejt:
            continue
        if jugador_id in skip_pocos_minutos:
            continue
        posicion = ejt['posicion'] or 'Delantero'
        if posicion not in posiciones:
            continue
        candidatos_pos[posicion].append({
            'id': jugador_id,
            'nombre': pred['jugador__nombre'],
            'apellido': pred['jugador__apellido'],
            'posicion': posicion,
            'equipo': ejt['equipo__nombre'],
            'equipo_escudo': shield_name(ejt['equipo__nombre']),
            'dorsal': str(ejt['dorsal']) if ejt['dorsal'] else '—',
            'prediccion': round(float(pred['prediccion']), 2),
            'proximo_rival': rival_map.get(ejt['equipo_id'], '—'),
        })

    for posicion in posiciones:
        candidatos_pos[posicion].sort(key=lambda x: x['prediccion'], reverse=True)
        resultado[posicion] = candidatos_pos[posicion][:3]

    return resultado


# ── view ──────────────────────────────────────────────────────────────────────

class MenuView(APIView):
    """GET /api/menu/?jornada=6"""
    permission_classes = [AllowAny]

    def get(self, request):
        temporada = Temporada.objects.order_by('-nombre').first()
        empty = {
            'clasificacion_top': [],
            'partidos_proxima_jornada': [],
            'partidos_favoritos': [],
            'jornada_actual': None,
            'proxima_jornada': None,
            'jugadores_destacados_por_posicion': {},
        }
        if not temporada:
            return Response(empty)

        # Obtener jornada - puede venir como parámetro
        jornada_param = request.query_params.get('jornada')
        
        if jornada_param:
            # Si se proporciona un número de jornada específico
            try:
                jornada_num = int(jornada_param)
                jornada_actual = Jornada.objects.filter(
                    temporada=temporada, 
                    numero_jornada=jornada_num
                ).first()
            except (ValueError, TypeError):
                jornada_actual = None
        else:
            # Detect the last actually-played jornada from Partido results.
            # This avoids hard-coding any jornada number.
            _last_played_num = (
                Partido.objects
                .filter(jornada__temporada=temporada, goles_local__isnull=False)
                .order_by('-jornada__numero_jornada')
                .values_list('jornada__numero_jornada', flat=True)
                .first()
            )
            if _last_played_num:
                jornada_actual = Jornada.objects.filter(
                    temporada=temporada, numero_jornada=_last_played_num
                ).first()
            else:
                jornada_actual = (
                    Jornada.objects.filter(temporada=temporada)
                    .order_by('numero_jornada')
                    .first()
                )

        clasificacion_top = []
        if jornada_actual:
            qs = (
                ClasificacionJornada.objects
                .filter(temporada=temporada, jornada=jornada_actual)
                .order_by('posicion')[:5]
                .select_related('equipo')
            )
            for reg in qs:
                clasificacion_top.append({
                    'posicion': reg.posicion,
                    'equipo': reg.equipo.nombre,
                    'equipo_escudo': shield_name(reg.equipo.nombre),
                    'puntos': reg.puntos,
                })

        proxima_jornada = None
        partidos_proxima = []
        if jornada_actual:
            proxima_jornada = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada=jornada_actual.numero_jornada + 1,
            ).first()
            if proxima_jornada:
                for p in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .select_related('equipo_local', 'equipo_visitante')
                    .order_by('fecha', 'hora')
                ):
                    partidos_proxima.append(_serialize_partido_calendario(p))

        partidos_favoritos = []
        if request.user.is_authenticated and proxima_jornada:
            fav_ids = set(
                request.user.equipos_favoritos.values_list('equipo_id', flat=True)
            )
            if fav_ids:
                for p in (
                    Calendario.objects.filter(jornada=proxima_jornada)
                    .filter(
                        Q(equipo_local_id__in=fav_ids)
                        | Q(equipo_visitante_id__in=fav_ids)
                    )
                    .select_related('equipo_local', 'equipo_visitante')
                ):
                    partidos_favoritos.append(_serialize_partido_calendario(p))

        jugadores_destacados = _get_jugadores_destacados_con_predicciones(
            temporada, proxima_jornada
        )

        return Response({
            'clasificacion_top': clasificacion_top,
            'jornada_actual': {'numero': jornada_actual.numero_jornada} if jornada_actual else None,
            'proxima_jornada': {'numero': proxima_jornada.numero_jornada} if proxima_jornada else None,
            'partidos_proxima_jornada': partidos_proxima,
            'partidos_favoritos': partidos_favoritos,
            'jugadores_destacados_por_posicion': jugadores_destacados,
        })


# ── Top jugadores en vivo ─────────────────────────────────────────────────────

# Background computation state (prevent duplicate simultaneous runs)
_BG_LOCK = _th.Lock()
_BG_RUNNING: set = set()  # set of (temporada_id, jornada_num)


def _bg_compute_predictions(temporada_id, jornada_num, cache_key):
    """
    Runs in a daemon background thread.
    Computes ML predictions for ALL players of the season and saves them to
    PrediccionJugador so future DB-backed reads are fast.
    """
    try:
        temporada = Temporada.objects.get(pk=temporada_id)
        jornada_obj = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
    except Exception:
        return

    # predecir should already be in sys.modules (pre-imported at startup)
    entren_path = Path(__file__).resolve().parents[2] / 'entrenamientoModelos'
    if str(entren_path) not in _sys.path:
        _sys.path.insert(0, str(entren_path))
    try:
        mod = importlib.import_module('predecir')
        predecir_puntos = getattr(mod, 'predecir_puntos')
    except Exception as e:
        logger.error('[BG predictions] Cannot import predecir: %s', e)
        return

    _POS_CODE  = {'Portero': 'PT', 'Defensa': 'DF', 'Centrocampista': 'MC', 'Delantero': 'DT'}
    _POS_MODEL = {'PT': 'rf', 'DF': 'rf', 'MC': 'ridge', 'DT': 'ridge'}
    posiciones_validas = set(_POS_CODE.keys())

    # Position fallback from stats (for NULL ejt.posicion)
    pos_fallback = {}
    for row in (
        EstadisticasPartidoJugador.objects
        .filter(partido__jornada__temporada=temporada, posicion__isnull=False)
        .exclude(posicion='')
        .values('jugador_id', 'posicion')
        .annotate(cnt=Count('id'))
        .order_by('jugador_id', '-cnt')
    ):
        if row['jugador_id'] not in pos_fallback:
            pos_fallback[row['jugador_id']] = row['posicion']

    ejt_list = list(
        EquipoJugadorTemporada.objects
        .filter(temporada=temporada)
        .values('jugador_id', 'jugador__nombre', 'jugador__apellido',
                'equipo_id', 'equipo__nombre', 'posicion', 'dorsal')
    )

    # Skip players with < 60 total minutes in the last 3 PLAYED jornadas.
    _played_nums_bg = list(
        Partido.objects
        .filter(jornada__temporada=temporada, goles_local__isnull=False)
        .values_list('jornada__numero_jornada', flat=True)
        .distinct()
        .order_by('-jornada__numero_jornada')[:3]
    )
    if len(_played_nums_bg) < 3:
        skip_pocos_minutos_bg = set()
    else:
        _min_sum_bg: dict = {}
        for _row in (
            EstadisticasPartidoJugador.objects
            .filter(
                partido__jornada__temporada=temporada,
                partido__jornada__numero_jornada__in=_played_nums_bg,
            )
            .values('jugador_id', 'min_partido')
        ):
            _jid = _row['jugador_id']
            _min_sum_bg[_jid] = _min_sum_bg.get(_jid, 0) + (_row['min_partido'] or 0)
        all_player_ids_bg = set(ejt['jugador_id'] for ejt in ejt_list)
        skip_pocos_minutos_bg = {
            jid for jid in all_player_ids_bg
            if _min_sum_bg.get(jid, 0) < 60
        }

    rival_map = {}
    for cal in (
        Calendario.objects.filter(jornada=jornada_obj)
        .values('equipo_local_id', 'equipo_visitante_id',
                'equipo_local__nombre', 'equipo_visitante__nombre')
    ):
        rival_map[cal['equipo_local_id']] = cal['equipo_visitante__nombre']
        rival_map[cal['equipo_visitante_id']] = cal['equipo_local__nombre']

    candidatos = {pos: [] for pos in posiciones_validas}
    seen = set()

    for ejt in ejt_list:
        jid = ejt['jugador_id']
        if jid in seen:
            continue
        seen.add(jid)
        if jid in skip_pocos_minutos_bg:
            continue
        posicion = ejt.get('posicion') or pos_fallback.get(jid)
        if posicion not in posiciones_validas:
            continue
        pos_code = _POS_CODE[posicion]
        try:
            result = predecir_puntos(jid, pos_code, jornada_num, verbose=False)
            if not isinstance(result, dict) or result.get('error'):
                continue
            pts = result.get('prediccion') or result.get('puntos_predichos')
            if pts is None:
                continue
            try:
                pts_f = float(pts)
                if not math.isfinite(pts_f):
                    continue
            except (TypeError, ValueError):
                continue
            # Persist to DB so the fast path picks it up next time
            PrediccionJugador.objects.update_or_create(
                jugador_id=jid,
                jornada=jornada_obj,
                modelo=_POS_MODEL.get(pos_code, 'rf'),
                defaults={'prediccion': float(pts_f)},
            )
            candidatos[posicion].append({
                'id': jid,
                'nombre': ejt['jugador__nombre'],
                'apellido': ejt['jugador__apellido'],
                'posicion': posicion,
                'equipo': ejt['equipo__nombre'],
                'equipo_escudo': shield_name(ejt['equipo__nombre']),
                'dorsal': str(ejt['dorsal']) if ejt['dorsal'] else '-',
                'prediccion': round(float(pts_f), 2),
                'proximo_rival': rival_map.get(ejt['equipo_id'], '-'),
            })
        except Exception:
            pass

    resultado = {}
    for pos in posiciones_validas:
        candidatos[pos].sort(key=lambda x: x['prediccion'], reverse=True)
        resultado[pos] = candidatos[pos][:3]

    if any(len(v) > 0 for v in resultado.values()):
        cache.set(cache_key, resultado, 1800)
        logger.info('[BG predictions] jornada %d done, %d positions cached', jornada_num, len(resultado))


def _schedule_bg_predictions(temporada, jornada_obj, jornada_num, cache_key):
    """Spawn a daemon thread to (re)compute predictions unless one is already running."""
    key = (temporada.id, jornada_num)
    with _BG_LOCK:
        if key in _BG_RUNNING:
            return
        _BG_RUNNING.add(key)

    def _run():
        try:
            _bg_compute_predictions(temporada.id, jornada_num, cache_key)
        finally:
            with _BG_LOCK:
                _BG_RUNNING.discard(key)

    t = _th.Thread(target=_run, daemon=True, name=f'PredBG-j{jornada_num}')
    t.start()


class MenuTopJugadoresView(APIView):
    """
    GET /api/menu/top-jugadores/?jornada=18

    Fast path: serves top-3 per position from PrediccionJugador DB (instant).
    Background: always spawns a daemon thread that re-runs ML for all players
    and saves results back to DB so the next request is already up to date.
    Cache: 30 min per jornada.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        jornada_param = request.query_params.get('jornada')
        if not jornada_param:
            return Response({'jugadores_destacados_por_posicion': {}})

        _cache_key = f'menu_top_jug:{jornada_param}'
        cached = cache.get(_cache_key)
        if cached is not None:
            return Response({'jugadores_destacados_por_posicion': cached})

        try:
            jornada_num = int(jornada_param)
        except (ValueError, TypeError):
            return Response({'error': 'jornada invalida'}, status=400)

        temporada = Temporada.objects.order_by('-nombre').first()
        if not temporada:
            return Response({'jugadores_destacados_por_posicion': {}})

        jornada_obj = Jornada.objects.filter(
            temporada=temporada, numero_jornada=jornada_num
        ).first()
        if not jornada_obj:
            return Response({'jugadores_destacados_por_posicion': {}})

        # Fast path: serve whatever is already in PrediccionJugador DB
        resultado = _get_jugadores_destacados_con_predicciones(temporada, jornada_obj)

        # Always trigger background refresh so results stay up to date
        _schedule_bg_predictions(temporada, jornada_obj, jornada_num, _cache_key)

        if any(len(v) > 0 for v in resultado.values()):
            cache.set(_cache_key, resultado, 1800)

        return Response({'jugadores_destacados_por_posicion': resultado})
