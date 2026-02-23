"""
JSON API views for the React web frontend.
Base URLs registered in main/urls.py under /api/
"""
import json
import logging
from datetime import datetime

from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db.models import Sum, Q, Avg, Count
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import (
    Temporada, Jornada, Calendario, ClasificacionJornada,
    Equipo, Jugador, EquipoJugadorTemporada, EstadisticasPartidoJugador,
    Partido, HistorialEquiposJugador,
)

from .views import (
    get_maximo_goleador,
    get_partido_anterior_temporada,
    get_h2h_historico,
    get_historico_temporadas,
    get_estadisticas_equipo_temporadas,
    get_jugadores_ultimas_temporadas,
)

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def get_racha_detalles(equipo, temporada, jornada_actual):
    """Obtiene los detalles de los últimos 5 partidos jugados incluyendo la jornada actual si se ha jugado"""
    # Obtener últimos 5 partidos JUGADOS de jornadas <= a la jornada actual (incluye actual si se jugó)
    partidos = Partido.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__lte=jornada_actual.numero_jornada,
        goles_local__isnull=False,
        goles_visitante__isnull=False
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by('-jornada__numero_jornada', '-fecha_partido')[:5]
    
    racha_detalles = []
    
    for partido in partidos:
        # Determinar si el equipo fue local o visitante
        es_local = partido.equipo_local == equipo
        
        if es_local:
            rival = partido.equipo_visitante.nombre
            goles_propios = partido.goles_local
            goles_rival = partido.goles_visitante
        else:
            rival = partido.equipo_local.nombre
            goles_propios = partido.goles_visitante
            goles_rival = partido.goles_local
        
        # Determinar resultado
        if goles_propios > goles_rival:
            resultado = 'V'
            titulo = f"Victoria vs {rival} {goles_propios}-{goles_rival}"
        elif goles_propios < goles_rival:
            resultado = 'D'
            titulo = f"Derrota vs {rival} {goles_propios}-{goles_rival}"
        else:
            resultado = 'E'
            titulo = f"Empate vs {rival} {goles_propios}-{goles_rival}"
        
        racha_detalles.append({
            'resultado': resultado,
            'titulo': titulo,
            'rival': rival,
            'goles_propios': goles_propios,
            'goles_rival': goles_rival
        })
    
    # Verificar si existe un partido de la jornada actual sin resultado en Calendario
    partido_actual_sin_resultado = Calendario.objects.filter(
        jornada=jornada_actual
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).first()
    
    if partido_actual_sin_resultado and len(racha_detalles) < 5:
        # Verificar que no tenga resultado aún
        partido_con_resultado = Partido.objects.filter(
            jornada=jornada_actual,
            equipo_local=partido_actual_sin_resultado.equipo_local,
            equipo_visitante=partido_actual_sin_resultado.equipo_visitante,
            goles_local__isnull=False,
            goles_visitante__isnull=False
        ).exists()
        
        if not partido_con_resultado:
            racha_detalles.append({
                'resultado': '?',
                'titulo': 'Partido por jugar',
                'rival': '',
                'goles_propios': None,
                'goles_rival': None
            })
    
    # Invertir para mostrar del más antiguo al más reciente (de izquierda a derecha)
    racha_detalles.reverse()
    
    return racha_detalles

def shield_name(nombre):
    """Replicates the Django template filter for shield image filenames."""
    import unicodedata, re
    if not nombre:
        return ''
    n = nombre.lower().strip()
    
    # Remover acentos PRIMERO
    n = ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
    
    # Casos específicos para equipos
    special_cases = {
        'atletico': 'atletico',
        'athletic': 'athletic_club',
        'rayo': 'rayo_vallecano',
        'celta': 'celta',
    }
    for key, replacement in special_cases.items():
        if n.startswith(key):
            return replacement
    
    # Remover prefijos comunes
    for p in ['fc ', 'cd ', 'ad ', 'rcd ', 'real ', 'ud ', 'cf ', 'sd ', 'ef ', 'ca ']:
        if n.startswith(p):
            n = n[len(p):]
            break
    
    # Reemplazar espacios con guiones bajos
    n = n.replace(' ', '_')
    n = re.sub(r'[^a-z0-9_]', '', n)
    return n


def _user_info(user):
    profile_photo = None
    nickname = None
    estado = 'active'
    if user.is_authenticated:
        try:
            p = user.profile
            if p.foto:
                profile_photo = p.foto.url
            nickname = p.nickname
            estado = p.estado or 'active'
        except Exception:
            pass
    return {
        'authenticated': user.is_authenticated,
        'id': user.id if user.is_authenticated else None,
        'username': user.username if user.is_authenticated else None,
        'first_name': user.first_name if user.is_authenticated else None,
        'last_name': user.last_name if user.is_authenticated else None,
        'email': user.email if user.is_authenticated else None,
        'nickname': nickname,
        'estado': estado,
        'profile_photo': profile_photo,
        'foto_url': profile_photo,
    }



# ── 1. AUTH STATUS ────────────────────────────────────────────────────────────

@ensure_csrf_cookie
@require_http_methods(['GET'])
def api_me(request):
    """GET /api/me/ – returns current user data + CSRF cookie"""
    return JsonResponse(_user_info(request.user))


# ── 2. AUTH: LOGIN / LOGOUT ───────────────────────────────────────────────────

@require_http_methods(['POST'])
def api_login(request):
    """POST /api/auth/login/"""
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        # try email
        try:
            u = User.objects.get(email=username)
            user = authenticate(request, username=u.username, password=password)
        except Exception:
            pass

    if user is None:
        return JsonResponse({'error': 'Credenciales incorrectas'}, status=401)

    auth_login(request, user)
    return JsonResponse({'status': 'ok', 'user': _user_info(user)})


@require_http_methods(['POST'])
def api_logout(request):
    """POST /api/auth/logout/"""
    auth_logout(request)
    return JsonResponse({'status': 'ok'})


@require_http_methods(['POST'])
def api_register(request):
    """POST /api/auth/register/"""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    password1 = data.get('password1', '')
    password2 = data.get('password2', '')

    errors = {}
    if not first_name:
        errors['first_name'] = 'El nombre es obligatorio'
    if not email:
        errors['email'] = 'El email es obligatorio'
    if not username:
        errors['username'] = 'El nombre de usuario es obligatorio'
    if not password1:
        errors['password1'] = 'La contraseña es obligatoria'
    if password1 != password2:
        errors['password2'] = 'Las contraseñas no coinciden'
    if User.objects.filter(username=username).exists():
        errors['username'] = 'Ese nombre de usuario ya está en uso'
    if User.objects.filter(email=email).exists():
        errors['email'] = 'Ese email ya está registrado'

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password1,
        first_name=first_name,
        last_name=last_name,
    )
    auth_login(request, user)
    return JsonResponse({'status': 'ok', 'user': _user_info(user)})


# ── 3. MENU ───────────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_menu(request):
    """GET /api/menu/"""
    temporada = Temporada.objects.order_by('-nombre').first()
    if not temporada:
        return JsonResponse({'clasificacion_top': [], 'partidos_proxima_jornada': [],
                             'partidos_favoritos': [], 'jornada_actual': None, 'proxima_jornada': None})

    jornada_actual = (
        Jornada.objects.filter(temporada=temporada, numero_jornada=17).first()
        or Jornada.objects.filter(temporada=temporada, fecha_fin__gte=datetime.now()).order_by('numero_jornada').first()
        or Jornada.objects.filter(temporada=temporada).order_by('-numero_jornada').exclude(numero_jornada=38).first()
    )

    clasificacion_top = []
    if jornada_actual:
        for reg in ClasificacionJornada.objects.filter(temporada=temporada, jornada=jornada_actual).order_by('posicion')[:5].select_related('equipo'):
            clasificacion_top.append({
                'posicion': reg.posicion,
                'equipo': reg.equipo.nombre,
                'equipo_escudo': shield_name(reg.equipo.nombre),
                'puntos': reg.puntos,
            })

    proxima_jornada = None
    partidos_proxima = []
    if jornada_actual:
        proxima_jornada = Jornada.objects.filter(temporada=temporada, numero_jornada=jornada_actual.numero_jornada + 1).first()
        if proxima_jornada:
            for p in Calendario.objects.filter(jornada=proxima_jornada).select_related('equipo_local', 'equipo_visitante').order_by('fecha', 'hora'):
                partidos_proxima.append(_serialize_partido_calendario(p))

    partidos_favoritos = []
    if request.user.is_authenticated and proxima_jornada:
        fav_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
        if fav_ids:
            for p in Calendario.objects.filter(jornada=proxima_jornada).filter(
                Q(equipo_local_id__in=fav_ids) | Q(equipo_visitante_id__in=fav_ids)
            ).select_related('equipo_local', 'equipo_visitante'):
                partidos_favoritos.append(_serialize_partido_calendario(p))

    return JsonResponse({
        'clasificacion_top': clasificacion_top,
        'jornada_actual': {'numero': jornada_actual.numero_jornada} if jornada_actual else None,
        'proxima_jornada': {'numero': proxima_jornada.numero_jornada} if proxima_jornada else None,
        'partidos_proxima_jornada': partidos_proxima,
        'partidos_favoritos': partidos_favoritos,
    })


# ── 4. CLASIFICACION ──────────────────────────────────────────────────────────

def _serialize_partido_calendario(calendario):
    """Serializa un objeto Calendario a dict para la API"""
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


@require_http_methods(['GET'])
def api_clasificacion(request):
    """GET /api/clasificacion/?temporada=25/26&jornada=17&equipo=&favoritos=true"""
    try:
        temporada_display = request.GET.get('temporada', '25/26')
        jornada_num = request.GET.get('jornada')
        equipo_seleccionado = request.GET.get('equipo', '')
        mostrar_favoritos = request.GET.get('favoritos', '').lower() == 'true'

        temporada_nombre = temporada_display.replace('/', '_')
        try:
            temporada = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temporada = Temporada.objects.order_by('-nombre').first()

        if not temporada:
            return JsonResponse({'error': 'No hay temporadas'}, status=404)

        temporadas = [{'nombre': t.nombre, 'display': t.nombre.replace('_', '/')}
                      for t in Temporada.objects.order_by('-nombre')]

        jornadas = [{'numero': j.numero_jornada} for j in Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')]
        equipos_disponibles = [{'nombre': e.nombre} for e in Equipo.objects.order_by('nombre')]

        # Determine which jornada to show
        jornada_obj = None
        if jornada_num:
            try:
                jornada_obj = Jornada.objects.get(temporada=temporada, numero_jornada=int(jornada_num))
            except (Jornada.DoesNotExist, ValueError):
                jornada_obj = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada').first()
        else:
            jornada_obj = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada').first()

        clasificacion = []
        if jornada_obj:
            for reg in ClasificacionJornada.objects.filter(temporada=temporada, jornada=jornada_obj).order_by('posicion').select_related('equipo'):
                try:
                    palabras = reg.equipo.nombre.split()
                    iniciales = ''.join([p[0].upper() for p in palabras])
                    clasificacion.append({
                        'posicion': reg.posicion,
                        'equipo': reg.equipo.nombre,
                        'equipo_escudo': shield_name(reg.equipo.nombre),
                        'iniciales': iniciales,
                        'puntos': reg.puntos,
                        'partidos_ganados': reg.partidos_ganados,
                        'partidos_empatados': reg.partidos_empatados,
                        'partidos_perdidos': reg.partidos_perdidos,
                        'goles_favor': reg.goles_favor,
                        'goles_contra': reg.goles_contra,
                        'diferencia_goles': reg.goles_favor - reg.goles_contra,
                        'racha_detalles': get_racha_detalles(reg.equipo, temporada, jornada_obj),
                    })
                except Exception as e:
                    logger.error(f"Error processing clasificacion: {e}")
                    continue

        # Filtrar clasificación por favoritos o por equipo específico
        if mostrar_favoritos and request.user.is_authenticated:
            try:
                favoritos_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
                clasificacion = [c for c in clasificacion if any(eq.id in favoritos_ids for eq in Equipo.objects.filter(nombre=c['equipo']))]
            except Exception:
                pass  # Si hay error, mostrar clasificación completa
        elif equipo_seleccionado:
            # Filtrar por equipo específico
            clasificacion = [c for c in clasificacion if c['equipo'].lower() == equipo_seleccionado.lower()]

        # Partidos de la jornada
        partidos_jornada = []
        if jornada_obj:
            for p in Calendario.objects.filter(jornada=jornada_obj).select_related('equipo_local', 'equipo_visitante').order_by('fecha', 'hora'):
                try:
                    entry = _serialize_partido_calendario(p)
                    try:
                        partido_jugado = Partido.objects.get(
                            Q(equipo_local=p.equipo_local, equipo_visitante=p.equipo_visitante) |
                            Q(equipo_local=p.equipo_visitante, equipo_visitante=p.equipo_local),
                            jornada=jornada_obj,
                            goles_local__isnull=False,
                        )
                        entry['jugado'] = True
                        entry['goles_local'] = partido_jugado.goles_local
                        entry['goles_visitante'] = partido_jugado.goles_visitante
                        
                        # Build sucesos (events) from EstadisticasPartidoJugador
                        goles_local = []
                        goles_visitante = []
                        amarillas_local = []
                        amarillas_visitante = []
                        rojas_local = []
                        rojas_visitante = []
                        
                        for stats in EstadisticasPartidoJugador.objects.filter(partido=partido_jugado).select_related('jugador'):
                            try:
                                nombre = f"{stats.jugador.nombre} {stats.jugador.apellido}".strip()
                                minuto = stats.min_partido
                                
                                # Determine which team this player belongs to
                                try:
                                    hist = HistorialEquiposJugador.objects.filter(
                                        jugador=stats.jugador,
                                        temporada=temporada
                                    ).first()
                                    if not hist:
                                        # Try EquipoJugadorTemporada as fallback
                                        ejt = EquipoJugadorTemporada.objects.filter(
                                            jugador=stats.jugador,
                                            temporada=temporada
                                        ).first()
                                        if not ejt:
                                            continue
                                        equipo_jugador = ejt.equipo
                                    else:
                                        equipo_jugador = hist.equipo
                                except Exception:
                                    continue
                                
                                # Goles
                                if stats.gol_partido and stats.gol_partido > 0:
                                    for _ in range(stats.gol_partido):
                                        if equipo_jugador == partido_jugado.equipo_local:
                                            goles_local.append({'nombre': nombre, 'minuto': minuto})
                                        elif equipo_jugador == partido_jugado.equipo_visitante:
                                            goles_visitante.append({'nombre': nombre, 'minuto': minuto})
                                
                                # Amarillas
                                if stats.amarillas and stats.amarillas > 0:
                                    for _ in range(stats.amarillas):
                                        if equipo_jugador == partido_jugado.equipo_local:
                                            amarillas_local.append({'nombre': nombre, 'minuto': minuto})
                                        elif equipo_jugador == partido_jugado.equipo_visitante:
                                            amarillas_visitante.append({'nombre': nombre, 'minuto': minuto})
                                
                                # Rojas
                                if stats.rojas and stats.rojas > 0:
                                    for _ in range(stats.rojas):
                                        if equipo_jugador == partido_jugado.equipo_local:
                                            rojas_local.append({'nombre': nombre, 'minuto': minuto})
                                        elif equipo_jugador == partido_jugado.equipo_visitante:
                                            rojas_visitante.append({'nombre': nombre, 'minuto': minuto})
                            except Exception as e:
                                logger.error(f"Error processing stat: {e}")
                                continue
                        
                        entry['sucesos'] = {
                            'goles_local': goles_local,
                            'goles_visitante': goles_visitante,
                            'amarillas_local': amarillas_local,
                            'amarillas_visitante': amarillas_visitante,
                            'rojas_local': rojas_local,
                            'rojas_visitante': rojas_visitante,
                        }
                    except Partido.DoesNotExist:
                        entry['jugado'] = False
                        entry['goles_local'] = None
                        entry['goles_visitante'] = None
                        entry['sucesos'] = {
                            'goles_local': [],
                            'goles_visitante': [],
                            'amarillas_local': [],
                            'amarillas_visitante': [],
                            'rojas_local': [],
                            'rojas_visitante': [],
                        }
                    partidos_jornada.append(entry)
                except Exception as e:
                    logger.error(f"Error processing partido: {e}")
                    continue

        # Filtrar partidos por favoritos o por equipo específico
        if mostrar_favoritos and request.user.is_authenticated:
            try:
                favoritos_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
                favoritos_nombres = set(Equipo.objects.filter(id__in=favoritos_ids).values_list('nombre', flat=True))
                partidos_jornada = [p for p in partidos_jornada if p['local'] in favoritos_nombres or p['visitante'] in favoritos_nombres]
            except Exception:
                pass  # Si hay error, mostrar todos los partidos
        elif equipo_seleccionado:
            # Filtrar por equipo específico
            partidos_jornada = [p for p in partidos_jornada if p['local'].lower() == equipo_seleccionado.lower() or p['visitante'].lower() == equipo_seleccionado.lower()]

        # Obtener equipos favoritos del usuario si está autenticado
        favoritos_equipos = []
        if request.user.is_authenticated:
            try:
                favoritos_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
                favoritos_equipos = [{'nombre': e.nombre} for e in Equipo.objects.filter(id__in=favoritos_ids)]
            except Exception:
                favoritos_equipos = []

        return JsonResponse({
            'temporada': temporada_display,
            'temporadas': temporadas,
            'jornada_actual': jornada_obj.numero_jornada if jornada_obj else 1,
            'jornadas': jornadas,
            'clasificacion': clasificacion,
            'partidos_jornada': partidos_jornada,
            'equipos_disponibles': equipos_disponibles,
            'equipo_seleccionado': equipo_seleccionado,
            'favoritos_equipos': favoritos_equipos,
        })
    except Exception as e:
        logger.error(f"Error in api_clasificacion: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# ── 5. EQUIPOS ────────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_equipos(request):
    """GET /api/equipos/"""
    favoritos_ids = set()
    if request.user.is_authenticated:
        try:
            favoritos_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
        except Exception:
            pass

    result = []
    temporada = Temporada.objects.order_by('-nombre').first()
    for eq in Equipo.objects.order_by('nombre'):
        jugadores_count = 0
        if temporada:
            jugadores_count = EquipoJugadorTemporada.objects.filter(equipo=eq, temporada=temporada).count()
        result.append({
            'id': eq.id,
            'nombre': eq.nombre,
            'escudo': shield_name(eq.nombre),
            'estadio': eq.estadio or '',
            'jugadores_count': jugadores_count,
            'es_favorito': eq.id in favoritos_ids,
        })

    return JsonResponse({'equipos': result})


# ── 6. EQUIPO DETALLE ─────────────────────────────────────────────────────────

@require_http_methods(['GET'])
@require_http_methods(['GET'])
def api_equipo(request, equipo_nombre):
    """GET /api/equipo/<nombre>/?temporada=25/26&jornada=N"""
    from datetime import datetime, time
    from difflib import SequenceMatcher
    
    temporada_display = request.GET.get('temporada', '25/26')
    temporada_nombre = temporada_display.replace('/', '_')
    jornada_param = request.GET.get('jornada')

    try:
        equipo = Equipo.objects.get(nombre=equipo_nombre)
    except Equipo.DoesNotExist:
        return JsonResponse({'error': 'Equipo no encontrado'}, status=404)

    # Obtener todas las temporadas disponibles
    temporadas = Temporada.objects.all().order_by('-nombre')
    temporadas_display = [{'nombre': t.nombre, 'display': t.nombre.replace('_', '/')} for t in temporadas]

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = temporadas.first()
        if temporada:
            temporada_nombre = temporada.nombre
            temporada_display = temporada_nombre.replace('_', '/')

    # Jornadas disponibles
    jornadas_temp = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    jornadas_disponibles = [{'numero': j.numero_jornada} for j in jornadas_temp]
    
    # Determinar jornada actual
    ultima_jornada_clasificacion = Jornada.objects.filter(
        temporada=temporada,
        clasificacionjornada__isnull=False
    ).order_by('numero_jornada').last()
    
    jornada_actual = None
    if jornada_param:
        try:
            jornada_actual = int(jornada_param)
        except (ValueError, TypeError):
            pass
    
    if jornada_actual is None:
        jornada_actual = ultima_jornada_clasificacion.numero_jornada if ultima_jornada_clasificacion else 1
    
    jornada_min = 1
    jornada_max = 38
    
    # Obtener objeto Jornada
    try:
        jornada_actual_obj = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_actual)
    except Jornada.DoesNotExist:
        jornada_actual_obj = ultima_jornada_clasificacion

    # ── PLANTILLA CON ESTADÍSTICAS ──
    jugadores_equipo_temp = EquipoJugadorTemporada.objects.filter(
        equipo=equipo, temporada=temporada
    ).select_related('jugador').order_by('dorsal')
    
    jugadores_agrupados = {}
    puntos_dorsal_cero = {}
    
    for eq_jug_temp in jugadores_equipo_temp:
        stats_query = EstadisticasPartidoJugador.objects.filter(
            jugador=eq_jug_temp.jugador,
            partido__jornada__temporada=temporada
        )
        
        if jornada_actual:
            stats_query = stats_query.filter(partido__jornada__numero_jornada__lte=jornada_actual)
        
        valid_stats = stats_query.exclude(puntos_fantasy__gt=40)
        
        total_goles = valid_stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
        total_asistencias = valid_stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0
        total_puntos = valid_stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
        partidos_jugados = valid_stats.count()
        total_minutos = valid_stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0
        
        if eq_jug_temp.dorsal == 0 and total_puntos <= 0:
            nombre_completo = f"{eq_jug_temp.jugador.nombre} {eq_jug_temp.jugador.apellido}".strip()
            puntos_dorsal_cero[nombre_completo] = {'puntos': total_puntos}
            continue
        
        posicion_frecuente = valid_stats.values('posicion').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        jugador_id = eq_jug_temp.jugador.id
        
        if jugador_id not in jugadores_agrupados:
            jugadores_agrupados[jugador_id] = {
                'obj': eq_jug_temp,
                'total_goles': total_goles,
                'total_asistencias': total_asistencias,
                'total_puntos': total_puntos,
                'partidos_stats': partidos_jugados,
                'total_minutos': total_minutos,
                'posicion': posicion_frecuente['posicion'] if posicion_frecuente else None,
                'nombre': eq_jug_temp.jugador.nombre,
                'apellido': eq_jug_temp.jugador.apellido
            }
        else:
            jugadores_agrupados[jugador_id]['total_puntos'] += total_puntos
            jugadores_agrupados[jugador_id]['total_goles'] += total_goles
            jugadores_agrupados[jugador_id]['total_asistencias'] += total_asistencias
    
    # Si no hay suficientes jugadores, también buscar en HistorialEquiposJugador
    if len(jugadores_agrupados) < 10:
        jugadores_historico = HistorialEquiposJugador.objects.filter(
            equipo=equipo,
            temporada=temporada
        ).select_related('jugador')
        
        # Deduplicar manualmente
        jugadores_ids_historico = set()
        for jugador_hist in jugadores_historico:
            jugador = jugador_hist.jugador
            if jugador.id not in jugadores_agrupados and jugador.id not in jugadores_ids_historico:
                jugadores_ids_historico.add(jugador.id)
                # Obtener stats de este jugador en esa temporada
                stats_query = EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada
                )
                
                if jornada_actual:
                    stats_query = stats_query.filter(partido__jornada__numero_jornada__lte=jornada_actual)
                
                valid_stats = stats_query.exclude(puntos_fantasy__gt=40)
                
                total_goles = valid_stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
                total_asistencias = valid_stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0
                total_puntos = valid_stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
                partidos_jugados = valid_stats.count()
                total_minutos = valid_stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0
                
                if total_puntos > 0 or partidos_jugados > 0:
                    posicion_frecuente = valid_stats.values('posicion').annotate(
                        count=Count('id')
                    ).order_by('-count').first()
                    
                    jugadores_agrupados[jugador.id] = {
                        'obj': None,
                        'total_goles': total_goles,
                        'total_asistencias': total_asistencias,
                        'total_puntos': total_puntos,
                        'partidos_stats': partidos_jugados,
                        'total_minutos': total_minutos,
                        'posicion': posicion_frecuente['posicion'] if posicion_frecuente else None,
                        'nombre': jugador.nombre,
                        'apellido': jugador.apellido
                    }
    
    # Matching dorsal 0
    def similitud_nombres(n1, n2):
        return SequenceMatcher(None, n1.lower(), n2.lower()).ratio()
    
    for nombre_d0, datos_d0 in puntos_dorsal_cero.items():
        mejor_coincidencia = None
        mejor_similitud = 0.6
        for jug_id, datos_prin in jugadores_agrupados.items():
            nombre_prin = f"{datos_prin['nombre']} {datos_prin['apellido']}".strip()
            sim = similitud_nombres(nombre_d0, nombre_prin)
            if sim > mejor_similitud:
                mejor_similitud = sim
                mejor_coincidencia = jug_id
        if mejor_coincidencia:
            jugadores_agrupados[mejor_coincidencia]['total_puntos'] += datos_d0['puntos']
    
    jugadores = []
    for jug_id, datos in jugadores_agrupados.items():
        eq_jug_temp = datos['obj']
        jugadores.append({
            'jugador_id': eq_jug_temp.jugador.id,
            'id': eq_jug_temp.jugador.id,
            'nombre': eq_jug_temp.jugador.nombre,
            'apellido': eq_jug_temp.jugador.apellido,
            'dorsal': eq_jug_temp.dorsal,
            'posicion': datos['posicion'] or eq_jug_temp.posicion or '',
            'nacionalidad': eq_jug_temp.jugador.nacionalidad or '',
            'goles': datos['total_goles'],
            'asistencias': datos['total_asistencias'],
            'puntos_fantasy': datos['total_puntos'],
            'partidos': datos['partidos_stats'],
            'minutos': datos['total_minutos'],
        })
    
    top_3_puntos = sorted(jugadores, key=lambda x: x['puntos_fantasy'], reverse=True)[:3]
    top_3_minutos = sorted(jugadores, key=lambda x: x['minutos'], reverse=True)[:3]
    
    # ── CLASIFICACIÓN Y RACHA ──
    goles_equipo_favor = 0
    goles_equipo_contra = 0
    clasificacion_actual = ClasificacionJornada.objects.filter(
        equipo=equipo, temporada=temporada, jornada__numero_jornada__lte=jornada_actual
    ).order_by('-jornada__numero_jornada').first()
    
    if clasificacion_actual:
        goles_equipo_favor = clasificacion_actual.goles_favor
        goles_equipo_contra = clasificacion_actual.goles_contra
    
    racha_actual_detalles = get_racha_detalles(equipo, temporada, jornada_actual_obj) if jornada_actual_obj else []
    
    # ── PRÓXIMO PARTIDO ──
    proximo_partido = None
    rival_info = None
    
    if jornada_actual and jornada_actual < jornada_max:
        proximo_encontrado = None
        for offset in range(1, (jornada_max - jornada_actual) + 1):
            intento_jornada = jornada_actual + offset
            partidos_intentar = Calendario.objects.filter(
                jornada__temporada=temporada,
                jornada__numero_jornada=intento_jornada
            ).filter(Q(equipo_local=equipo) | Q(equipo_visitante=equipo)).first()
            
            if partidos_intentar:
                proximo_encontrado = partidos_intentar
                break
        
        if proximo_encontrado:
            partido_cal = proximo_encontrado
            if partido_cal.equipo_local == equipo:
                rival = partido_cal.equipo_visitante
                es_local = True
            else:
                rival = partido_cal.equipo_local
                es_local = False
            
            clasificacion_rival = ClasificacionJornada.objects.filter(
                equipo=rival, temporada=temporada, jornada__numero_jornada__lte=jornada_actual
            ).order_by('-jornada__numero_jornada').first()
            
            goles_rival_favor = 0
            goles_rival_contra = 0
            racha_rival_detalles = []
            
            if clasificacion_rival:
                goles_rival_favor = clasificacion_rival.goles_favor
                goles_rival_contra = clasificacion_rival.goles_contra
                jornada_rival_obj = clasificacion_rival.jornada
                racha_rival_detalles = get_racha_detalles(rival, temporada, jornada_rival_obj)
            
            max_goleador_equipo = get_maximo_goleador(equipo, temporada, jornada_actual_obj) if jornada_actual_obj else None
            max_goleador_rival = get_maximo_goleador(rival, temporada, jornada_actual_obj) if jornada_actual_obj else None
            partido_anterior = get_partido_anterior_temporada(equipo, rival, temporada, jornada_actual_obj) if jornada_actual_obj else None
            
            proximo_partido = {
                'equipo_local': partido_cal.equipo_local.nombre,
                'equipo_visitante': partido_cal.equipo_visitante.nombre,
                'fecha_partido': datetime.combine(partido_cal.fecha, partido_cal.hora or time(18, 0)).isoformat() if partido_cal.fecha else None,
            }
            
            rival_info = {
                'nombre': rival.nombre,
                'escudo': shield_name(rival.nombre),
                'es_local': es_local,
                'racha': racha_rival_detalles,
                'goles_favor': goles_rival_favor,
                'goles_contra': goles_rival_contra,
                'h2h': get_h2h_historico(equipo, rival, temporada),
                'max_goleador_equipo': max_goleador_equipo,
                'max_goleador_rival': max_goleador_rival,
                'partido_anterior': partido_anterior
            }
    
    # ── HISTÓRICO TEMPORADAS ──
    historico_temporadas = get_historico_temporadas(equipo)
    
    # ── ÚLTIMAS 3 TEMPORADAS ──
    try:
        ultimas_3_stats = get_estadisticas_equipo_temporadas(equipo, num_temporadas=3)
        ultimas_3_jugadores = get_jugadores_ultimas_temporadas(equipo, num_temporadas=3)
    except Exception as e:
        logger.error(f"Error getting ultimas 3 temporadas for {equipo.nombre}: {e}")
        ultimas_3_stats = {'temporadas': [], 'total_goles': 0, 'total_asistencias': 0, 'partidos_jugados': 0}
        ultimas_3_jugadores = []

    return JsonResponse({
        'equipo': {
            'id': equipo.id,
            'nombre': equipo.nombre,
            'escudo': shield_name(equipo.nombre),
            'estadio': equipo.estadio or '',
        },
        'jugadores': jugadores,
        'clasificacion': {
            'posicion': clasificacion_actual.posicion if clasificacion_actual else None,
            'puntos': clasificacion_actual.puntos if clasificacion_actual else 0,
        } if clasificacion_actual else {},
        'racha_actual_detalles': racha_actual_detalles,
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_display,
        'temporada_actual_db': temporada_nombre,
        'jornadas_disponibles': jornadas_disponibles,
        'jornada_actual': jornada_actual,
        'jornada_min': jornada_min,
        'jornada_max': jornada_max,
        'proximo_partido': proximo_partido,
        'rival_info': rival_info,
        'top_3_puntos': top_3_puntos,
        'top_3_minutos': top_3_minutos,
        'ultimas_3_jugadores': ultimas_3_jugadores,
        'ultimas_3_stats': ultimas_3_stats,
        'historico_temporadas': historico_temporadas,
        'goles_equipo_favor': goles_equipo_favor,
        'goles_equipo_contra': goles_equipo_contra,
    })


# ── 7. JUGADOR DETALLE ────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_jugador(request, jugador_id):
    """GET /api/jugador/<id>/?temporada=25/26"""
    from django.db.models import Q, Avg
    from main.scrapping.roles import DESCRIPCIONES_ROLES
    
    temporada_display = request.GET.get('temporada', '25/26')
    temporada_nombre = temporada_display.replace('/', '_')
    es_carrera = temporada_display == 'carrera'

    try:
        jugador = Jugador.objects.get(id=jugador_id)
    except Jugador.DoesNotExist:
        return JsonResponse({'error': 'Jugador no encontrado'}, status=404)

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = Temporada.objects.order_by('-nombre').first()

    posicion = jugador.get_posicion_mas_frecuente() or ''

    # Equipo actual en esta temporada - Si es carrera, tomar la más reciente
    equipo_temporada = None
    edad = 0
    try:
        if es_carrera:
            # Para carrera, obtener la temporada más reciente para edad
            ejt = EquipoJugadorTemporada.objects.filter(jugador=jugador).select_related('equipo', 'temporada').order_by('-temporada__nombre').first()
        else:
            ejt = EquipoJugadorTemporada.objects.filter(jugador=jugador, temporada=temporada).select_related('equipo').first()
        
        if ejt:
            equipo_temporada = {
                'equipo': {
                    'nombre': ejt.equipo.nombre,
                    'escudo': f'/static/escudos/{shield_name(ejt.equipo.nombre)}.png'
                },
                'dorsal': ejt.dorsal or '-'
            }
            # Para carrera, edad de la última temporada
            edad = ejt.edad or 0
    except Exception:
        pass

    # Filtro para las estadísticas
    if es_carrera:
        filter_query = Q(jugador=jugador)
    else:
        filter_query = Q(jugador=jugador, partido__jornada__temporada=temporada)

    # Estadísticas detalladas por bloques (excluyendo puntos anómalos >40)
    stats_totales = EstadisticasPartidoJugador.objects.filter(filter_query).exclude(puntos_fantasy__gt=40).aggregate(
        # Básicas
        goles=Sum('gol_partido'),
        asistencias=Sum('asist_partido'),
        minutos=Sum('min_partido'),
        partidos=Count('id', filter=Q(min_partido__gt=0)),
        promedio_puntos=Avg('puntos_fantasy'),
        
        # BLOQUE ORGANIZACIÓN
        pases_totales=Sum('pases_totales'),
        pases_accuracy=Avg('pases_completados_pct'),
        xag=Sum('xag'),
        
        # BLOQUE REGATES
        regates_completados=Sum('regates_completados'),
        regates_fallidos=Sum('regates_fallidos'),
        conducciones=Sum('conducciones'),
        conducciones_progresivas=Sum('conducciones_progresivas'),
        distancia_conduccion=Sum('distancia_conduccion'),
        
        # BLOQUE DEFENSA
        despejes=Sum('despejes'),
        entradas=Sum('entradas'),
        duelos_ganados=Sum('duelos_ganados'),
        duelos_perdidos=Sum('duelos_perdidos'),
        amarillas=Sum('amarillas'),
        rojas=Sum('rojas'),
        bloqueos=Sum('bloqueos'),
        duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
        duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
        
        # BLOQUE ATAQUE
        tiros=Sum('tiros'),
        tiros_puerta=Sum('tiro_puerta_partido'),
        xg=Sum('xg_partido'),
        
        # PORTERO
        goles_en_contra=Sum('goles_en_contra'),
        porcentaje_paradas=Avg('porcentaje_paradas'),
    )

    # Últimos 12 partidos
    if es_carrera:
        ultimos_12 = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador
        ).exclude(puntos_fantasy__gt=40).select_related('partido__jornada').order_by('-partido__jornada__temporada__nombre', '-partido__jornada__numero_jornada')[:12]
    else:
        ultimos_12 = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=temporada
        ).exclude(puntos_fantasy__gt=40).select_related('partido__jornada').order_by('-partido__jornada__numero_jornada')[:12]
    
    ultimos_12_data = []
    for s in reversed(list(ultimos_12)):
        ultimos_12_data.append({
            'puntos_fantasy': float(s.puntos_fantasy or 0),
            'partido': {
                'jornada': {
                    'numero_jornada': s.partido.jornada.numero_jornada
                }
            }
        })

    # Roles destacados - Si es carrera, dividir por temporada
    if es_carrera:
        # Obtener roles por temporada
        roles_por_temporada = []
        temporadas_jugador_q = EquipoJugadorTemporada.objects.filter(
            jugador=jugador
        ).select_related('temporada').order_by('-temporada__nombre')[:3]  # Últimas 3 temporadas
        
        for ejt in temporadas_jugador_q:
            stats_con_roles = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador,
                partido__jornada__temporada=ejt.temporada,
                roles__isnull=False
            ).exclude(puntos_fantasy__gt=40).exclude(roles__exact=[]).values_list('roles', flat=True)
            
            roles_dict = {}
            for stats_roles in stats_con_roles:
                if stats_roles and isinstance(stats_roles, list):
                    for role_obj in stats_roles:
                        if isinstance(role_obj, dict):
                            for field_name, values in role_obj.items():
                                if field_name not in roles_dict or values[0] < roles_dict[field_name][0]:
                                    roles_dict[field_name] = values
            
            if roles_dict:
                roles_por_temporada.append({
                    'temporada': ejt.temporada.nombre.replace('_', '/'),
                    'roles': [{k: v} for k, v in roles_dict.items()]
                })
        
        roles = roles_por_temporada
    else:
        stats_con_roles = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=temporada,
            roles__isnull=False
        ).exclude(puntos_fantasy__gt=40).exclude(roles__exact=[]).values_list('roles', flat=True)
        
        roles_dict = {}
        for stats_roles in stats_con_roles:
            if stats_roles and isinstance(stats_roles, list):
                for role_obj in stats_roles:
                    if isinstance(role_obj, dict):
                        for field_name, values in role_obj.items():
                            if field_name not in roles_dict or values[0] < roles_dict[field_name][0]:
                                roles_dict[field_name] = values
        
        roles = [{k: v} for k, v in roles_dict.items()] if roles_dict else []

    # Histórico de carrera
    historico_data = []
    historico_qs = EquipoJugadorTemporada.objects.filter(
        jugador=jugador
    ).select_related('equipo', 'temporada').order_by('-temporada__nombre')
    
    for hist in historico_qs:
        stats_hist = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=hist.temporada
        ).exclude(puntos_fantasy__gt=40).aggregate(
            goles=Sum('gol_partido'),
            asistencias=Sum('asist_partido'),
            minutos=Sum('min_partido'),
            partidos=Count('id', filter=Q(min_partido__gt=0)),
            puntos_totales=Sum('puntos_fantasy'),
            # Organización
            pases=Sum('pases_totales'),
            pases_accuracy=Avg('pases_completados_pct'),
            xag=Sum('xag'),
            # Defensa
            despejes=Sum('despejes'),
            entradas=Sum('entradas'),
            duelos_ganados=Sum('duelos_ganados'),
            duelos_perdidos=Sum('duelos_perdidos'),
            amarillas=Sum('amarillas'),
            rojas=Sum('rojas'),
            bloqueos=Sum('bloqueos'),
            duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
            duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
            # Ataque
            tiros=Sum('tiros'),
            tiros_puerta=Sum('tiro_puerta_partido'),
            xg=Sum('xg_partido'),
            # Regates
            regates_completados=Sum('regates_completados'),
            regates_fallidos=Sum('regates_fallidos'),
            conducciones=Sum('conducciones'),
            conducciones_progresivas=Sum('conducciones_progresivas'),
            distancia_conduccion=Sum('distancia_conduccion'),
        )
        
        partidos = stats_hist['partidos'] or 0
        puntos_totales = stats_hist['puntos_totales'] or 0
        puntos_por_partido = round(puntos_totales / partidos, 1) if partidos > 0 else 0
        
        historico_data.append({
            'temporada': hist.temporada.nombre.replace('_', '/'),
            'equipo': hist.equipo.nombre,
            'dorsal': hist.dorsal or '-',
            'puntos_totales': puntos_totales,
            'puntos_por_partido': puntos_por_partido,
            'goles': stats_hist['goles'] or 0,
            'asistencias': stats_hist['asistencias'] or 0,
            'pj': partidos,
            'minutos': stats_hist['minutos'] or 0,
            # Organización
            'pases': stats_hist['pases'] or 0,
            'pases_accuracy': round(stats_hist['pases_accuracy'] or 0, 1),
            'xag': round(stats_hist['xag'] or 0, 2),
            # Defensa
            'despejes': stats_hist['despejes'] or 0,
            'entradas': stats_hist['entradas'] or 0,
            'duelos_totales': (stats_hist['duelos_ganados'] or 0) + (stats_hist['duelos_perdidos'] or 0),
            'amarillas': stats_hist['amarillas'] or 0,
            'rojas': stats_hist['rojas'] or 0,
            'bloqueos': stats_hist['bloqueos'] or 0,
            'duelos_aereos_totales': (stats_hist['duelos_aereos_ganados'] or 0) + (stats_hist['duelos_aereos_perdidos'] or 0),
            # Ataque
            'tiros': stats_hist['tiros'] or 0,
            'tiros_puerta': stats_hist['tiros_puerta'] or 0,
            'xg': round(stats_hist['xg'] or 0, 2),
            # Regates
            'regates_completados': stats_hist['regates_completados'] or 0,
            'regates_fallidos': stats_hist['regates_fallidos'] or 0,
            'conducciones': stats_hist['conducciones'] or 0,
            'conducciones_progresivas': stats_hist['conducciones_progresivas'] or 0,
            'distancia_conduccion': round(stats_hist['distancia_conduccion'] or 0, 1),
        })

    # Temporadas disponibles
    temporadas_disponibles = []
    for t in Temporada.objects.order_by('-nombre'):
        if EstadisticasPartidoJugador.objects.filter(jugador=jugador, partido__jornada__temporada=t).exists():
            temporadas_disponibles.append({'nombre': t.nombre, 'display': t.nombre.replace('_', '/')})

    # Obtener percentiles del equipo_jugador_temporada
    percentiles = {}
    if not es_carrera and ejt:
        percentiles = ejt.percentiles if ejt.percentiles else {}
    
    return JsonResponse({
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
            # Básicas
            'goles': stats_totales['goles'] or 0,
            'asistencias': stats_totales['asistencias'] or 0,
            'minutos': stats_totales['minutos'] or 0,
            'partidos': stats_totales['partidos'] or 0,
            'promedio_puntos': round(stats_totales['promedio_puntos'] or 0, 1),
            
            # BLOQUE ATAQUE
            'ataque': {
                'goles': stats_totales['goles'] or 0,
                'xg': round(stats_totales['xg'] or 0, 2),
                'tiros': stats_totales['tiros'] or 0,
                'tiros_puerta': stats_totales['tiros_puerta'] or 0,
            },
            
            # BLOQUE ORGANIZACIÓN
            'organizacion': {
                'asistencias': stats_totales['asistencias'] or 0,
                'xag': round(stats_totales['xag'] or 0, 2),
                'pases': stats_totales['pases_totales'] or 0,
                'pases_accuracy': round(stats_totales['pases_accuracy'] or 0, 1),
            },
            
            # BLOQUE REGATES
            'regates': {
                'regates_completados': stats_totales['regates_completados'] or 0,
                'regates_fallidos': stats_totales['regates_fallidos'] or 0,
                'conducciones': stats_totales['conducciones'] or 0,
                'conducciones_progresivas': stats_totales['conducciones_progresivas'] or 0,
            },
            
            # BLOQUE DEFENSA
            'defensa': {
                'entradas': stats_totales['entradas'] or 0,
                'despejes': stats_totales['despejes'] or 0,
                'duelos_totales': (stats_totales['duelos_ganados'] or 0) + (stats_totales['duelos_perdidos'] or 0),
                'duelos_aereos_totales': (stats_totales['duelos_aereos_ganados'] or 0) + (stats_totales['duelos_aereos_perdidos'] or 0),
            },
            
            # COMPORTAMIENTO
            'comportamiento': {
                'amarillas': stats_totales.get('amarillas', 0) or 0,
                'rojas': stats_totales.get('rojas', 0) or 0,
            },
            
            # PORTERO
            'portero': {
                'paradas': 0,  # No disponible en el modelo
                'goles_encajados': stats_totales.get('goles_en_contra', 0) or 0,
                'porterias_cero': 0,  # Se calcula de otra forma
                'porcentaje_paradas': round(stats_totales.get('porcentaje_paradas', 0) or 0, 1),
            },
        },
        'ultimos_8': ultimos_12_data,
        'roles': roles,
        'es_roles_por_temporada': es_carrera,  # Flag para saber si roles están divididos por temporada
        'historico': historico_data,
        'radar_values': [],
        'media_general': 0,
        'percentiles': percentiles,
        'descripciones_roles': DESCRIPCIONES_ROLES,
    })


# ── 8. PERFIL ─────────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_perfil(request):
    """GET /api/perfil/"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    user = request.user
    profile_data = _user_info(user)

    # Favoritos
    favoritos = []
    try:
        for fav in user.equipos_favoritos.select_related('equipo').all():
            favoritos.append({
                'id': fav.id,
                'equipo_nombre': fav.equipo.nombre,
                'equipo_escudo': shield_name(fav.equipo.nombre),
            })
    except Exception:
        pass

    # Estadísticas de plantillas
    plantillas_count = 0
    try:
        from .models import Plantilla
        plantillas_count = user.plantillas.count()
    except Exception:
        pass

    return JsonResponse({
        **profile_data,
        'favoritos': favoritos,
        'plantillas_count': plantillas_count,
    })


@require_http_methods(['POST'])
def api_update_perfil(request):
    """POST /api/perfil/update/"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        data = json.loads(request.body)
        user = request.user
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        user.save()
        try:
            if 'nickname' in data:
                user.profile.nickname = data['nickname']
                user.profile.save()
        except Exception:
            pass
        return JsonResponse({'status': 'ok', 'user': _user_info(user)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['POST'])
def api_update_status(request):
    """POST /api/perfil/status/"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        data = json.loads(request.body)
        user = request.user
        nuevo_estado = data.get('estado', data.get('status', 'active'))
        # Validar que es un valor permitido
        if nuevo_estado not in ('active', 'away', 'dnd'):
            nuevo_estado = 'active'
        user.profile.estado = nuevo_estado
        user.profile.save()
        return JsonResponse({'status': 'ok', 'estado': nuevo_estado})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['POST'])
def api_upload_photo(request):
    """POST /api/perfil/foto/ – handles file upload OR JSON {default_avatar: 'default1'}"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    content_type = request.content_type or ''

    # Case 1: File upload
    if 'foto' in request.FILES:
        try:
            request.user.profile.foto = request.FILES['foto']
            request.user.profile.save()
            return JsonResponse({'status': 'ok', 'foto_url': request.user.profile.foto.url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # Case 2: JSON body with default_avatar key
    if 'application/json' in content_type or 'default_avatar' in (request.POST or {}):
        try:
            if 'application/json' in content_type:
                import json as _json
                data = _json.loads(request.body)
            else:
                data = request.POST
            default_avatar = data.get('default_avatar') or data.get('avatar_index')
            if not default_avatar:
                return JsonResponse({'error': 'No se proporcionó foto'}, status=400)
            # If avatar_index is provided as number, convert to name
            if str(default_avatar).isdigit():
                default_avatar = f'default{default_avatar}'
            import os
            from django.conf import settings
            from django.core.files.base import ContentFile
            avatar_filename = f'{default_avatar}.png'
            static_path = os.path.join(settings.BASE_DIR, 'static', 'logos', avatar_filename)
            if not os.path.exists(static_path):
                return JsonResponse({'error': f'Avatar no encontrado: {avatar_filename}'}, status=400)
            with open(static_path, 'rb') as f:
                request.user.profile.foto.save(avatar_filename, ContentFile(f.read()), save=True)
            return JsonResponse({'status': 'ok', 'foto_url': request.user.profile.foto.url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'No se proporcionó foto'}, status=400)


# ── 9. FAVORITOS ─────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_favoritos(request):
    """GET /api/favoritos/"""
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False, 'favoritos': []})

    favoritos = []
    equipos_todos = list(Equipo.objects.order_by('nombre'))
    fav_ids = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))

    for eq in equipos_todos:
        favoritos.append({
            'id': eq.id,
            'nombre': eq.nombre,
            'escudo': shield_name(eq.nombre),
            'es_favorito': eq.id in fav_ids,
        })

    return JsonResponse({'authenticated': True, 'favoritos': favoritos})


@require_http_methods(['POST'])
def api_toggle_favorito_v2(request):
    """POST /api/favoritos/toggle/ {equipo_id: N}"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        data = json.loads(request.body)
        equipo_id = data.get('equipo_id')
        equipo = Equipo.objects.get(id=equipo_id)
    except (json.JSONDecodeError, Equipo.DoesNotExist):
        return JsonResponse({'error': 'Equipo no encontrado'}, status=404)

    try:
        from .models import EquipoFavorito
        fav, created = EquipoFavorito.objects.get_or_create(usuario=request.user, equipo=equipo)
        if not created:
            fav.delete()
            return JsonResponse({'status': 'removed', 'es_favorito': False})
        return JsonResponse({'status': 'added', 'es_favorito': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['DELETE'])
def api_delete_favorito(request, fav_id):
    """DELETE /api/favoritos/<fav_id>/"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        from .models import EquipoFavorito
        fav = EquipoFavorito.objects.get(id=fav_id, usuario=request.user)
        fav.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)


# ── 10. SELECT FAVORITE TEAMS ─────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_select_favorites(request):
    """GET /api/favoritos/seleccionar/ – all teams + user favorites"""
    return api_favoritos(request)


# ── 11. AMIGOS ────────────────────────────────────────────────────────────────

@require_http_methods(['GET'])
def api_amigos(request):
    """GET /api/amigos/"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        from .models import SolicitudAmistad, Amistad
    except ImportError:
        return JsonResponse({'amigos': [], 'solicitudes_pendientes': [], 'solicitudes_enviadas': []})

    try:
        amigos = []
        for a in Amistad.objects.filter(
            Q(usuario1=request.user) | Q(usuario2=request.user)
        ).select_related('usuario1', 'usuario2'):
            amigo = a.usuario2 if a.usuario1 == request.user else a.usuario1
            info = _user_info(amigo)
            amigos.append({'id': info['id'], 'username': info['username'],
                           'first_name': info['first_name'], 'profile_photo': info['profile_photo']})

        solicitudes_recibidas = []
        for s in SolicitudAmistad.objects.filter(receptor=request.user, estado='pendiente').select_related('emisor'):
            solicitudes_recibidas.append({'id': s.id, 'username': s.emisor.username,
                                          'first_name': s.emisor.first_name})

        solicitudes_enviadas = []
        for s in SolicitudAmistad.objects.filter(emisor=request.user, estado='pendiente').select_related('receptor'):
            solicitudes_enviadas.append({'id': s.id, 'username': s.receptor.username})

        return JsonResponse({
            'amigos': amigos,
            'solicitudes_pendientes': solicitudes_recibidas,
            'solicitudes_enviadas': solicitudes_enviadas,
        })
    except Exception as e:
        logger.error(f'api_amigos error: {e}')
        return JsonResponse({'amigos': [], 'solicitudes_pendientes': [], 'solicitudes_enviadas': []})


@require_http_methods(['POST'])
def api_enviar_solicitud(request):
    """POST /api/amigos/solicitud/ {username: '...'}"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        from .models import SolicitudAmistad
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        receptor = User.objects.get(username=username)
        if receptor == request.user:
            return JsonResponse({'error': 'No puedes enviarte una solicitud a ti mismo'}, status=400)
        sol, created = SolicitudAmistad.objects.get_or_create(emisor=request.user, receptor=receptor,
                                                               defaults={'estado': 'pendiente'})
        if not created:
            return JsonResponse({'error': 'Ya existe una solicitud pendiente'}, status=400)
        return JsonResponse({'status': 'ok'})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['POST'])
def api_aceptar_solicitud(request, solicitud_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        from .models import SolicitudAmistad, Amistad
        sol = SolicitudAmistad.objects.get(id=solicitud_id, receptor=request.user, estado='pendiente')
        sol.estado = 'aceptada'
        sol.save()
        Amistad.objects.get_or_create(usuario1=sol.emisor, usuario2=request.user)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['POST'])
def api_rechazar_solicitud(request, solicitud_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        from .models import SolicitudAmistad
        sol = SolicitudAmistad.objects.get(id=solicitud_id, receptor=request.user, estado='pendiente')
        sol.estado = 'rechazada'
        sol.save()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(['POST'])
def api_eliminar_amigo(request, user_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        from .models import Amistad
        amigo = User.objects.get(id=user_id)
        Amistad.objects.filter(
            Q(usuario1=request.user, usuario2=amigo) |
            Q(usuario1=amigo, usuario2=request.user)
        ).delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ── 11b. MI PLANTILLA (main data for fantasy team builder) ───────────────────

@require_http_methods(['GET'])
def api_mi_plantilla(request):
    """GET /api/mi-plantilla/?temporada=25/26&jornada=1"""
    temporada_display = request.GET.get('temporada', '25/26')
    jornada_num = request.GET.get('jornada', '1')
    temporada_nombre = temporada_display.replace('/', '_')

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = Temporada.objects.order_by('-nombre').first()

    if not temporada:
        return JsonResponse({'error': 'No hay temporadas disponibles'}, status=404)

    # Get all jornadas for this temporada
    jornadas_qs = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    jornadas = [j.numero_jornada for j in jornadas_qs]

    # Get all temporadas
    temporadas_list = [t.nombre.replace('_', '/') for t in Temporada.objects.order_by('-nombre')]

    # Get current jornada
    try:
        jornada_obj = Jornada.objects.get(temporada=temporada, numero_jornada=int(jornada_num))
    except (Jornada.DoesNotExist, ValueError):
        jornada_obj = jornadas_qs.first()
        jornada_num = jornada_obj.numero_jornada if jornada_obj else 1

    # Get all available players for this temporada
    jugadores_disponibles = []
    for ejt in EquipoJugadorTemporada.objects.filter(temporada=temporada).select_related('jugador', 'equipo'):
        stats = EstadisticasPartidoJugador.objects.filter(
            jugador=ejt.jugador, partido__jornada__temporada=temporada
        ).aggregate(pts=Sum('puntos_fantasy'))
        jugadores_disponibles.append({
            'id': ejt.jugador.id,
            'nombre': ejt.jugador.nombre,
            'apellido': ejt.jugador.apellido,
            'posicion': ejt.posicion or ejt.jugador.get_posicion_mas_frecuente() or '',
            'equipo': ejt.equipo.nombre,
            'dorsal': ejt.dorsal,
            'puntos_fantasy': float(stats['pts'] or 0),
        })

    # Get próximo partido for current jornada
    proximoPartido = None
    if jornada_obj:
        next_jornada = Jornada.objects.filter(temporada=temporada, numero_jornada__gt=jornada_obj.numero_jornada).order_by('numero_jornada').first()
        if next_jornada:
            next_partido = Calendario.objects.filter(jornada=next_jornada).order_by('fecha', 'hora').first()
            if next_partido:
                proximoPartido = {
                    'jornada': next_jornada.numero_jornada,
                    'rival': next_partido.equipo_visitante.nombre if next_partido.equipo_local.nombre == 'Tu Equipo' else next_partido.equipo_local.nombre,
                    'es_local': next_partido.equipo_local.nombre == 'Tu Equipo',
                    'fecha': next_partido.fecha.strftime('%Y-%m-%d') if next_partido.fecha else None,
                    'hora': str(next_partido.hora) if next_partido.hora else None,
                }

    return JsonResponse({
        'temporada': temporada_display,
        'temporadas': temporadas_list,
        'jornada': jornada_num,
        'jornadas': jornadas,
        'jugadores_disponibles': jugadores_disponibles,
        'proximoPartido': proximoPartido,
        'plantilla': [],
    })


# ── 12. PLANTILLA JUGADORES (search for fantasy team builder) ─────────────────

@require_http_methods(['GET'])
def api_mi_plantilla_jugadores(request):
    """GET /api/mi-plantilla/jugadores/?pos=&q=&temporada="""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    pos = request.GET.get('pos', '')
    q = request.GET.get('q', '').strip()
    temporada_display = request.GET.get('temporada', '25/26')
    temporada_nombre = temporada_display.replace('/', '_')

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = Temporada.objects.order_by('-nombre').first()

    qs = EquipoJugadorTemporada.objects.filter(temporada=temporada).select_related('jugador', 'equipo')

    if pos:
        qs = qs.filter(posicion__icontains=pos)
    if q:
        qs = qs.filter(
            Q(jugador__nombre__icontains=q) | Q(jugador__apellido__icontains=q)
        )

    result = []
    for ejt in qs.order_by('jugador__apellido')[:50]:
        stats = EstadisticasPartidoJugador.objects.filter(
            jugador=ejt.jugador, partido__jornada__temporada=temporada
        ).aggregate(pts=Sum('puntos_fantasy'))
        result.append({
            'id': ejt.jugador.id,
            'nombre': ejt.jugador.nombre,
            'apellido': ejt.jugador.apellido,
            'posicion': ejt.posicion or '',
            'equipo': ejt.equipo.nombre,
            'equipo_escudo': shield_name(ejt.equipo.nombre),
            'dorsal': ejt.dorsal,
            'puntos_fantasy': float(stats['pts'] or 0),
        })

    return JsonResponse({'jugadores': result})
