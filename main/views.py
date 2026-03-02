from django.shortcuts import render, redirect
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .models import (Temporada, Jornada, ClasificacionJornada, Equipo,
                     EquipoJugadorTemporada, Partido, EstadisticasPartidoJugador, Jugador, Calendario, Plantilla)
from django.db.models import Sum, Count, F, Case, When, FloatField, Q, Avg
from datetime import datetime, time
import unicodedata
from main.scrapping.roles import DESCRIPCIONES_ROLES

def normalize_team_name_python(nombre):
    """Normaliza el nombre del equipo para usar en clases CSS (replica del filtro template)"""
    if not nombre:
        return ''
    
    normalized = nombre.lower().strip()
    
    # Remover prefijos comunes
    prefixes = ['fc ', 'cd ', 'ad ', 'rcd ', 'real ', 'ud ', 'cf ', 'sd ', 'ef ', 'ca ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    
    # Remover acentos
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', normalized)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Reemplazar espacios con guiones
    normalized = normalized.replace(' ', '-')
    
    # Remover caracteres especiales
    normalized = ''.join(c if c.isalnum() or c == '-' else '' for c in normalized)
    
    return normalized

def menu(request):
    """Vista principal del menú"""
    from main.models import Temporada, Jornada, Calendario, ClasificacionJornada
    from datetime import datetime
    from django.db.models import Q
    
    context = {'active_page': 'menu'}
    
    # Obtener la temporada actual (la más reciente)
    temporada = Temporada.objects.all().order_by('-nombre').first()
    if not temporada:
        return render(request, 'menu.html', context)
    
    # Obtener la jornada actual: Jornada 17 o la que esté activa
    jornada_actual = Jornada.objects.filter(temporada=temporada, numero_jornada=17).first()
    if not jornada_actual:
        ahora = datetime.now()
        jornada_actual = Jornada.objects.filter(
            temporada=temporada,
            fecha_fin__gte=ahora
        ).order_by('numero_jornada').first()
        
        if not jornada_actual:
            jornada_actual = Jornada.objects.filter(temporada=temporada).order_by('-numero_jornada').exclude(numero_jornada=38).first()
    
    context['jornada_actual'] = jornada_actual
    context['temporada'] = temporada
    
    # Obtener clasificación actual (todos los equipos)
    if jornada_actual:
        try:
            clasificacion_actual = ClasificacionJornada.objects.filter(
                temporada=temporada,
                jornada=jornada_actual
            ).order_by('posicion')[:5].select_related('equipo')
            context['clasificacion_top'] = list(clasificacion_actual)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener clasificación: {str(e)}")
    
    # Obtener todos los partidos de la próxima jornada
    if jornada_actual:
        try:
            proxima_jornada_num = jornada_actual.numero_jornada + 1
            proxima_jornada = Jornada.objects.filter(
                temporada=temporada,
                numero_jornada=proxima_jornada_num
            ).first()
            
            if proxima_jornada:
                partidos_proxima_jornada = Calendario.objects.filter(
                    jornada=proxima_jornada
                ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by('fecha', 'hora')
                
                context['partidos_proxima_jornada'] = list(partidos_proxima_jornada)
                context['proxima_jornada'] = proxima_jornada
                
                # Obtener jugadores destacados de la próxima jornada
                try:
                    from main.models import EstadisticasPartidoJugador
                    jugadores_destacados = EstadisticasPartidoJugador.objects.filter(
                        partido__jornada=proxima_jornada
                    ).select_related('jugador', 'partido').order_by('-goles', '-asistencias')[:5]
                    context['jugadores_destacados_proxima'] = list(jugadores_destacados)
                except Exception as je:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error al obtener jugadores destacados: {str(je)}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener próxima jornada: {str(e)}")
    
    # Si el usuario está autenticado, obtener sus equipos favoritos
    if request.user.is_authenticated:
        try:
            equipos_favoritos = request.user.equipos_favoritos.all().values_list('equipo_id', flat=True)
            
            if equipos_favoritos and jornada_actual:
                # Obtener próximos partidos de la próxima jornada de equipos favoritos
                proxima_jornada_num = jornada_actual.numero_jornada + 1
                proxima_jornada = Jornada.objects.filter(
                    temporada=temporada,
                    numero_jornada=proxima_jornada_num
                ).first()
                
                if proxima_jornada:
                    partidos_favoritos = Calendario.objects.filter(
                        jornada=proxima_jornada
                    ).filter(
                        Q(equipo_local_id__in=equipos_favoritos) | 
                        Q(equipo_visitante_id__in=equipos_favoritos)
                    ).select_related('equipo_local', 'equipo_visitante', 'jornada')
                    
                    context['partidos_favoritos'] = list(partidos_favoritos)
                    context['proxima_jornada'] = proxima_jornada
            
            # Añadir nickname del usuario si existe perfil
            if hasattr(request.user, 'profile') and request.user.profile:
                context['user_nickname'] = request.user.profile.nickname
        except Exception as e:
            # Si hay cualquier error, continuar sin favoritos
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener favoritos: {str(e)}")
    
    return render(request, 'menu.html', context)

@login_required(login_url='login_register')
@xframe_options_sameorigin
def mi_plantilla(request):
    """Vista de Mi Plantilla - Requiere autenticación"""
    import json
    from django.db.models import Sum, Q
    from main.models import EquipoJugadorTemporada, Temporada, Equipo, EstadisticasPartidoJugador, Partido, Jornada
    from datetime import datetime
    
    # Obtener temporada actual (la última disponible)
    temporada_actual = Temporada.objects.last()
    
    if not temporada_actual:
        # Si no hay temporadas, devolver plantilla vacía
        context = {
            'active_page': 'mi-plantilla',
            'jugadores_json': json.dumps({
                'Portero': [],
                'Defensa': [],
                'Centrocampista': [],
                'Delantero': []
            }),
            'plantilla_guardada': json.dumps({}),
            'equipos_json': json.dumps([]),
            'plantillas': [],
            'plantilla_actual': None,
            'jornadas': [],
            'jornada_actual': None,
        }
        return render(request, 'mi_plantilla.html', context)
    
    # Obtener jornadas disponibles de la temporada
    jornadas_qs = Jornada.objects.filter(
        temporada=temporada_actual
    ).order_by('numero_jornada')
    jornadas = list(jornadas_qs.values('id', 'numero_jornada'))
    
    # Obtener jornada seleccionada desde GET, o la última disponible
    jornada_param = request.GET.get('jornada')
    if jornada_param and jornada_param.isdigit():
        jornada_actual = Jornada.objects.filter(
            temporada=temporada_actual,
            numero_jornada=int(jornada_param)
        ).first()
    else:
        # Por defecto la última jornada disponible
        jornada_actual = jornadas_qs.last()
    
    jornada_num = jornada_actual.numero_jornada if jornada_actual else None
    
    # Obtener equipos de la temporada actual
    equipos_temporada = Equipo.objects.filter(
        jugadores_temporada__temporada=temporada_actual
    ).distinct().order_by('nombre')
    
    equipos_list = [{'id': e.id, 'nombre': e.nombre} for e in equipos_temporada]
    
    # Obtener partidos de la jornada seleccionada para cada equipo
    partidos_por_jornada = {}
    if jornada_actual:
        partidos_jornada = Partido.objects.filter(
            jornada=jornada_actual
        ).select_related('equipo_local', 'equipo_visitante')
        
        print(f"[DEBUG] Jornada {jornada_num}: {partidos_jornada.count()} partidos encontrados")
        
        for partido in partidos_jornada:
            print(f"[DEBUG] Partido: {partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre}")
            # Almacenar el rival para cada equipo
            partidos_por_jornada[partido.equipo_local.id] = {
                'rival_id': partido.equipo_visitante.id,
                'rival_nombre': partido.equipo_visitante.nombre,
                'es_local': True
            }
            partidos_por_jornada[partido.equipo_visitante.id] = {
                'rival_id': partido.equipo_local.id,
                'rival_nombre': partido.equipo_local.nombre,
                'es_local': False
            }
        
        # Si no hay partidos en tabla Partido, intentar obtener de Calendario
        if len(partidos_por_jornada) == 0:
            print(f"[DEBUG] Fallback: Buscando en tabla Calendario para jornada {jornada_num}")
            from main.models import Calendario
            
            calendarios = Calendario.objects.filter(
                jornada=jornada_actual
            ).select_related('equipo_local', 'equipo_visitante')
            
            print(f"[DEBUG] Calendario: {calendarios.count()} registros encontrados")
            
            for cal in calendarios:
                equipo_local = cal.equipo_local
                equipo_visitante = cal.equipo_visitante
                
                partidos_por_jornada[equipo_local.id] = {
                    'rival_id': equipo_visitante.id,
                    'rival_nombre': equipo_visitante.nombre,
                    'es_local': True
                }
                partidos_por_jornada[equipo_visitante.id] = {
                    'rival_id': equipo_local.id,
                    'rival_nombre': equipo_local.nombre,
                    'es_local': False
                }
                print(f"[DEBUG] Partido añadido: {equipo_local.nombre} vs {equipo_visitante.nombre}")
    
    print(f"[DEBUG] Total equipos en partidos_por_jornada: {len(partidos_por_jornada)}")
    
    # Obtener los jugadores disponibles en la temporada actual, organizados por posición
    # IMPORTANT: Incluir ALL jugadores (no evitar duplicados) para que aparezcan en el buscador
    jugadores_temporada = EquipoJugadorTemporada.objects.filter(
        temporada=temporada_actual
    ).select_related('jugador', 'equipo').order_by('jugador__nombre')
    
    jugadores_por_posicion = {
        'Portero': [],
        'Defensa': [],
        'Centrocampista': [],
        'Delantero': []
    }
    
    # Agrupar jugadores por posición (SIN evitar duplicados - mostrar todos)
    for ejecucion_temporada in jugadores_temporada:
        posicion = ejecucion_temporada.posicion or 'Delantero'  # Default a Delantero
        jugador = ejecucion_temporada.jugador
        
        # Calcular puntos fantasy totales del jugador en la temporada desde EstadisticasPartidoJugador
        # Filtrar para descartar partidos individuales con más de 50 puntos (anomalía de datos)
        stats_puntos = EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada_actual,
            jugador=jugador,
            puntos_fantasy__lte=50  # Descartar partidos con más de 50 puntos
        ).aggregate(total_puntos=Sum('puntos_fantasy'))
        
        puntos_fantasy = stats_puntos['total_puntos'] or 0
        
        # Obtener información del rival en la jornada seleccionada
        rival_jornada = partidos_por_jornada.get(ejecucion_temporada.equipo.id)
        
        if jugador.nombre in ['Aarón Escandell', 'Unai Simón']:  # DEBUG: primeros porteros
            print(f"[DEBUG] Jugador: {jugador.nombre} (Equipo ID: {ejecucion_temporada.equipo.id}, Equipo: {ejecucion_temporada.equipo.nombre})")
            print(f"[DEBUG]   -> rival_jornada = {rival_jornada}")
        
        if posicion in jugadores_por_posicion:
            jugadores_por_posicion[posicion].append({
                'id': jugador.id,
                'nombre': jugador.nombre,
                'apellido': jugador.apellido,
                'posicion': posicion,
                'equipo_id': ejecucion_temporada.equipo.id,
                'equipo_nombre': ejecucion_temporada.equipo.nombre,
                'puntos_fantasy_25_26': puntos_fantasy,
                'proximo_rival_id': rival_jornada['rival_id'] if rival_jornada else None,
                'proximo_rival_nombre': rival_jornada['rival_nombre'] if rival_jornada else None
            })
    
    # Cargar plantillas del usuario autenticado
    plantillas = []
    plantilla_actual = None
    plantilla_actual_id = None
    if request.user.is_authenticated:
        plantillas_qs = Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada')
        plantillas = list(plantillas_qs.values('id', 'nombre', 'formacion', 'alineacion'))
        
        # Si hay plantillas, usar la primera (más reciente)
        if plantillas:
            plantilla_actual = plantillas[0]
            plantilla_actual_id = plantilla_actual['id']
    
    # Fallback a la plantilla guardada antigua si existe
    if not plantilla_actual:
        plantilla_actual = {
            'id': None,
            'formacion': '4-3-3',
            'alineacion': {
                'Portero': [],
                'Defensa': [],
                'Centrocampista': [],
                'Delantero': [],
                'Suplentes': []
            },
            'nombre': 'Mi Team'
        }
        
        # Intentar cargar la antigua si existe
        if request.user.is_authenticated and request.user.profile.plantilla_guardada and request.user.profile.plantilla_guardada != '{}':
            try:
                old_data = json.loads(request.user.profile.plantilla_guardada)
                plantilla_actual.update(old_data)
            except:
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
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            plantilla_id = data.get('plantilla_id')
            nombre = data.get('nombre', 'Mi Team')
            formacion = data.get('formacion', '4-3-3')
            alineacion = data.get('alineacion', {})
            
            # Si se proporciona ID, actualizar; si no, crear nueva
            if plantilla_id:
                # Actualizar plantilla existente
                plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
                plantilla.nombre = nombre
                plantilla.formacion = formacion
                plantilla.alineacion = alineacion
                plantilla.save()
                mensaje = 'Plantilla actualizada correctamente'
            else:
                # Crear nueva plantilla
                # Asegurar que el nombre sea único para este usuario
                contador = 1
                nombre_original = nombre
                while Plantilla.objects.filter(usuario=request.user, nombre=nombre).exists():
                    nombre = f"{nombre_original} ({contador})"
                    contador += 1
                
                plantilla = Plantilla.objects.create(
                    usuario=request.user,
                    nombre=nombre,
                    formacion=formacion,
                    alineacion=alineacion
                )
                mensaje = f'Plantilla "{nombre}" guardada correctamente'
            
            return JsonResponse({
                'status': 'success',
                'message': mensaje,
                'plantilla_id': plantilla.id,
                'plantilla_nombre': plantilla.nombre
            })
        except Plantilla.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Plantilla no encontrada'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required(login_url='login_register')
def listar_plantillas(request):
    """Obtener todas las plantillas del usuario"""
    if request.method == 'GET':
        try:
            plantillas = Plantilla.objects.filter(usuario=request.user).order_by('-fecha_modificada').values(
                'id', 'nombre', 'formacion', 'alineacion', 'fecha_creada', 'fecha_modificada'
            )
            return JsonResponse({
                'status': 'success',
                'plantillas': list(plantillas)
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required(login_url='login_register')
def obtener_plantilla(request, plantilla_id):
    """Obtener una plantilla específica del usuario"""
    if request.method == 'GET':
        try:
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            return JsonResponse({
                'status': 'success',
                'plantilla': {
                    'id': plantilla.id,
                    'nombre': plantilla.nombre,
                    'formacion': plantilla.formacion,
                    'alineacion': plantilla.alineacion,
                }
            })
        except Plantilla.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Plantilla no encontrada'
            }, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required(login_url='login_register')
def eliminar_plantilla(request, plantilla_id):
    """Eliminar una plantilla del usuario"""
    if request.method == 'DELETE':
        try:
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            nombre = plantilla.nombre
            plantilla.delete()
            return JsonResponse({
                'status': 'success',
                'message': f'Plantilla "{nombre}" eliminada correctamente'
            })
        except Plantilla.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Plantilla no encontrada'
            }, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required(login_url='login_register')
def renombrar_plantilla(request, plantilla_id):
    """Renombrar una plantilla del usuario"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            nuevo_nombre = data.get('nombre', '').strip()
            
            if not nuevo_nombre:
                return JsonResponse({
                    'status': 'error',
                    'message': 'El nombre no puede estar vacío'
                }, status=400)
            
            plantilla = Plantilla.objects.get(id=plantilla_id, usuario=request.user)
            
            # Verificar que el nuevo nombre sea único
            if Plantilla.objects.filter(usuario=request.user, nombre=nuevo_nombre).exclude(id=plantilla_id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Ya existe una plantilla con ese nombre'
                }, status=400)
            
            plantilla.nombre = nuevo_nombre
            plantilla.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Plantilla renombrada a "{nuevo_nombre}"',
                'nuevo_nombre': nuevo_nombre
            })
        except Plantilla.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Plantilla no encontrada'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

def equipos(request):
    """Vista de lista de equipos con información agregada"""
    from main.models import Equipo, EquipoFavorito
    
    equipos_list = Equipo.objects.all().order_by('nombre')
    
    # Obtener favoritos del usuario si está autenticado
    favoritos_ids = set()
    if request.user.is_authenticated:
        favoritos_ids = set(
            EquipoFavorito.objects.filter(usuario=request.user)
            .values_list('equipo_id', flat=True)
        )
    
    equipos_info = []
    for eq in equipos_list:
        info = get_informacion_equipo(eq)
        equipos_info.append({
            'equipo': eq,
            'info': info,
            'es_favorito': eq.id in favoritos_ids
        })
    
    context = {
        'active_page': 'equipos',
        'equipos_info': equipos_info,
        'favoritos_ids': favoritos_ids
    }
    
    return render(request, 'equipos.html', context)

def get_racha_detalles(equipo, temporada, jornada_actual):
    """Obtiene los detalles de los últimos 5 partidos jugados incluyendo la jornada actual si se ha jugado"""
    from main.models import Partido, Calendario
    
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

def get_racha_futura(equipo, temporada, jornada_actual):
    """Obtiene los próximos 5 partidos sin resultado (futuros) incluyendo jornada actual si no se ha jugado"""
    from main.models import Partido, Calendario
    
    # Obtener próximos 5 partidos SIN resultado de jornadas >= a la jornada actual
    partidos = Calendario.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__gte=jornada_actual.numero_jornada
    ).filter(
        Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
    ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by('jornada__numero_jornada', 'fecha', 'hora')[:5]
    
    racha_futura = []
    
    for partido_cal in partidos:
        # Determinar si es local o visitante
        es_local = partido_cal.equipo_local == equipo
        
        if es_local:
            rival = partido_cal.equipo_visitante.nombre
        else:
            rival = partido_cal.equipo_local.nombre
        
        # Verificar si ya tiene resultado
        partido_con_resultado = Partido.objects.filter(
            jornada=partido_cal.jornada,
            equipo_local=partido_cal.equipo_local,
            equipo_visitante=partido_cal.equipo_visitante,
            goles_local__isnull=False,
            goles_visitante__isnull=False
        ).first()
        
        if partido_con_resultado:
            # El partido ya se jugó, mostrar resultado
            goles_propios = partido_con_resultado.goles_local if es_local else partido_con_resultado.goles_visitante
            goles_rival = partido_con_resultado.goles_visitante if es_local else partido_con_resultado.goles_local
            
            if goles_propios > goles_rival:
                resultado = 'V'
            elif goles_propios < goles_rival:
                resultado = 'L'
            else:
                resultado = 'D'
            
            titulo = f"Jornada {partido_cal.jornada.numero_jornada} vs {rival} {goles_propios}-{goles_rival}"
        else:
            # No tiene resultado aún
            resultado = '?'
            goles_propios = None
            goles_rival = None
            titulo = f"Jornada {partido_cal.jornada.numero_jornada} - vs {rival}"
        
        racha_futura.append({
            'resultado': resultado,
            'titulo': titulo,
            'rival': rival,
            'goles_propios': goles_propios,
            'goles_rival': goles_rival,
            'jornada': partido_cal.jornada.numero_jornada
        })
    
    return racha_futura

def get_historico_temporadas(equipo):
    """Obtiene las estadísticas de cada temporada (V/E/P, GF, GC, DF, Posición)"""
    from main.models import Partido, ClasificacionJornada
    from django.db.models import Q
    
    temporadas = Temporada.objects.all().order_by('-nombre')
    historico = []
    
    for temporada in temporadas:
        # Obtener la última jornada disponible de la temporada
        ultima_jornada = Jornada.objects.filter(
            temporada=temporada
        ).order_by('-numero_jornada').first()
        
        if ultima_jornada:
            # Contar partidos y goles
            partidos = Partido.objects.filter(
                jornada__temporada=temporada,
                goles_local__isnull=False,
                goles_visitante__isnull=False
            ).filter(
                Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
            )
            
            victorias = 0
            derrotas = 0
            empates = 0
            goles_favor = 0
            goles_contra = 0
            
            for partido in partidos:
                es_local = partido.equipo_local == equipo
                goles_propios = partido.goles_local if es_local else partido.goles_visitante
                goles_rival = partido.goles_visitante if es_local else partido.goles_local
                
                goles_favor += goles_propios
                goles_contra += goles_rival
                
                if goles_propios > goles_rival:
                    victorias += 1
                elif goles_propios < goles_rival:
                    derrotas += 1
                else:
                    empates += 1
            
            # Obtener la posición: buscar en la última jornada con clasificación para este equipo
            clasificacion = ClasificacionJornada.objects.filter(
                equipo=equipo,
                jornada__temporada=temporada
            ).order_by('-jornada__numero_jornada').first()
            
            if clasificacion or (victorias + derrotas + empates > 0):
                display_name = temporada.nombre.replace('_', '/')
                diferencia_goles = goles_favor - goles_contra
                
                historico.append({
                    'temporada': display_name,
                    'posicion': clasificacion.posicion if clasificacion else 21,
                    'victorias': victorias,
                    'empates': empates,
                    'derrotas': derrotas,
                    'goles_favor': goles_favor,
                    'goles_contra': goles_contra,
                    'diferencia_goles': diferencia_goles
                })
    
    return historico

def get_maximo_goleador(equipo, temporada, jornada_actual):
    """Obtiene el máximo goleador de un equipo hasta una jornada específica en una temporada"""
    from main.models import EstadisticasPartidoJugador, Partido
    from django.db.models import Sum, Q
    
    # Filtrar estadísticas del equipo hasta la jornada actual
    estadisticas = EstadisticasPartidoJugador.objects.filter(
        partido__jornada__temporada=temporada,
        partido__jornada__numero_jornada__lte=jornada_actual.numero_jornada,
        partido__goles_local__isnull=False  # Solo partidos jugados
    ).filter(
        # Jugadores del equipo (local o visitante)
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo)
    ).values('jugador', 'jugador__nombre', 'jugador__apellido').annotate(
        total_goles=Sum('gol_partido')
    ).order_by('-total_goles').first()
    
    if estadisticas:
        return {
            'nombre': estadisticas['jugador__nombre'],
            'apellido': estadisticas['jugador__apellido'],
            'goles': estadisticas['total_goles']
        }
    return None

def get_partido_anterior_temporada(equipo1, equipo2, temporada, jornada_actual):
    """Busca si ya se jugó un partido entre dos equipos en la temporada actual (antes de la jornada actual)"""
    from main.models import Partido
    from django.db.models import Q
    
    # Buscar partidos anteriores en la misma temporada
    partido = Partido.objects.filter(
        jornada__temporada=temporada,
        jornada__numero_jornada__lt=jornada_actual.numero_jornada,
        goles_local__isnull=False  # Solo partidos jugados
    ).filter(
        Q(
            Q(equipo_local=equipo1) & Q(equipo_visitante=equipo2)
        ) | Q(
            Q(equipo_local=equipo2) & Q(equipo_visitante=equipo1)
        )
    ).first()
    
    if partido:
        # Determinar perspectiva del equipo1
        es_local = partido.equipo_local == equipo1
        goles_eq1 = partido.goles_local if es_local else partido.goles_visitante
        goles_eq2 = partido.goles_visitante if es_local else partido.goles_local
        
        return {
            'jornada': partido.jornada.numero_jornada,
            'goles_equipo1': goles_eq1,
            'goles_equipo2': goles_eq2,
            'es_local': es_local,
            'resultado': 'V' if goles_eq1 > goles_eq2 else ('E' if goles_eq1 == goles_eq2 else 'P')
        }
    return None

def get_h2h_historico(equipo1, equipo2, temporada=None):
    """Obtiene el histórico H2H entre dos equipos. Si se especifica temporada, incluye esa y todas las anteriores (no futuro)"""
    from main.models import Partido
    from django.db.models import Q
    
    # Construir filtro de partidos
    partidos_filter = Partido.objects.filter(
        goles_local__isnull=False,
        goles_visitante__isnull=False
    ).filter(
        Q(
            Q(equipo_local=equipo1) & Q(equipo_visitante=equipo2)
        ) | Q(
            Q(equipo_local=equipo2) & Q(equipo_visitante=equipo1)
        )
    )
    
    # Si se especifica temporada, filtrar solo esa temporada y anteriores
    if temporada:
        partidos_filter = partidos_filter.filter(
            jornada__temporada__nombre__lte=temporada.nombre
        )
    
    partidos = partidos_filter.select_related('equipo_local', 'equipo_visitante', 'jornada__temporada').order_by('-jornada__temporada__nombre', '-jornada__numero_jornada')

def get_estadisticas_equipo_temporadas(equipo, num_temporadas=3):
    """Obtiene estadísticas agregadas de un equipo para las últimas N temporadas"""
    from main.models import EstadisticasPartidoJugador, Temporada, EquipoJugadorTemporada
    from django.db.models import Sum, Q, Count
    
    # Obtener últimas temporadas
    temporadas = Temporada.objects.all().order_by('-nombre')[:num_temporadas]
    
    # Obtener jugadores del equipo en esas temporadas
    eq_jug_temp = EquipoJugadorTemporada.objects.filter(
        equipo=equipo,
        temporada__in=temporadas
    ).values_list('jugador_id', flat=True)
    
    # Obtener estadísticas SOLO de jugadores que pertenecen al equipo en esas temporadas
    # Y que el partido sea del equipo específico (no contar goles de otros equipos)
    stats = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=eq_jug_temp,
        partido__jornada__temporada__in=temporadas,
        partido__goles_local__isnull=False
    )
    
    # Contar partidos únicos (donde min_partido > 0)
    partidos_jugados = stats.filter(min_partido__gt=0).values('partido').distinct().count()
    
    return {
        'temporadas': [t.nombre.replace('_', '/') for t in temporadas],
        'total_goles': stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0,
        'total_asistencias': stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0,
        'partidos_jugados': partidos_jugados
    }

def get_jugadores_ultimas_temporadas(equipo, num_temporadas=3):
    """Obtiene jugadores y sus estadísticas agregadas para las últimas N temporadas.
    Incluye posición (más reciente), nacionalidad y puntos fantasy acumulados.
    """
    from main.models import EstadisticasPartidoJugador, Temporada, EquipoJugadorTemporada
    from django.db.models import Sum, Q, Count

    temporadas = Temporada.objects.all().order_by('-nombre')[:num_temporadas]

    # Mapa jugador_id -> posición/nacionalidad a partir de EquipoJugadorTemporada
    # Ordenamos ascendente por temporada para que la más reciente quede al final (overwrites)
    ejt_qs = (EquipoJugadorTemporada.objects
              .filter(equipo=equipo, temporada__in=temporadas)
              .select_related('jugador', 'temporada')
              .order_by('temporada__nombre'))

    posicion_map = {}
    nac_map = {}
    dorsal_map = {}  # most recent season overwrites (ascending order)
    for ejt in ejt_qs:
        jid = ejt.jugador_id
        posicion_map[jid] = ejt.posicion or ''
        nac_map[jid] = ejt.jugador.nacionalidad or ''
        dorsal_map[jid] = ejt.dorsal

    jugadores_ids = list(posicion_map.keys())

    jugadores_stats = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        partido__jornada__temporada__in=temporadas,
        partido__goles_local__isnull=False,
    ).values(
        'jugador', 'jugador__nombre', 'jugador__apellido',
    ).annotate(
        total_goles=Sum('gol_partido'),
        total_asistencias=Sum('asist_partido'),
        total_minutos=Sum('min_partido'),
        total_puntos_fantasy=Sum('puntos_fantasy'),
        partidos_count=Count('id'),
    ).order_by('-total_goles', '-total_asistencias')

    result = []
    for js in jugadores_stats:
        jid = js['jugador']
        result.append({
            **js,
            'posicion': posicion_map.get(jid, ''),
            'jugador__nacionalidad': nac_map.get(jid, ''),
            'dorsal': dorsal_map.get(jid),
            'total_puntos_fantasy': js.get('total_puntos_fantasy') or 0,
        })
    return result

def get_informacion_equipo(equipo):
    """Obtiene información completa de un equipo: máximo goleador, asistente, máximos partidos jugados"""
    from main.models import EstadisticasPartidoJugador, EquipoJugadorTemporada
    from django.db.models import Sum, Q, Count
    
    # Obtener jugadores que han pertenecido al equipo en ALGUNA temporada
    jugadores_ids = EquipoJugadorTemporada.objects.filter(
        equipo=equipo
    ).values_list('jugador_id', flat=True).distinct()
    
    # Máximo goleador - SOLO de jugadores del equipo EN PARTIDOS de ese equipo
    max_goleador = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        partido__goles_local__isnull=False
    ).values('jugador', 'jugador__nombre', 'jugador__apellido').annotate(
        total_goles=Sum('gol_partido')
    ).order_by('-total_goles').first()
    
    # Máximo asistente - SOLO de jugadores del equipo EN PARTIDOS de ese equipo
    max_asistente = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        partido__goles_local__isnull=False
    ).values('jugador', 'jugador__nombre', 'jugador__apellido').annotate(
        total_asistencias=Sum('asist_partido')
    ).order_by('-total_asistencias').first()
    
    # Máximos partidos jugados - SOLO de jugadores del equipo EN PARTIDOS de ese equipo
    max_partidos = EstadisticasPartidoJugador.objects.filter(
        Q(partido__equipo_local=equipo) | Q(partido__equipo_visitante=equipo),
        jugador_id__in=jugadores_ids,
        min_partido__gt=0,
        partido__goles_local__isnull=False
    ).values('jugador', 'jugador__nombre', 'jugador__apellido').annotate(
        total_partidos=Count('id')
    ).order_by('-total_partidos').first()
    
    return {
        'max_goleador': {
            'nombre': max_goleador['jugador__nombre'] if max_goleador else '',
            'apellido': max_goleador['jugador__apellido'] if max_goleador else '',
            'goles': max_goleador['total_goles'] if max_goleador else 0
        } if max_goleador else None,
        'max_asistente': {
            'nombre': max_asistente['jugador__nombre'] if max_asistente else '',
            'apellido': max_asistente['jugador__apellido'] if max_asistente else '',
            'asistencias': max_asistente['total_asistencias'] if max_asistente else 0
        } if max_asistente else None,
        'max_partidos': {
            'nombre': max_partidos['jugador__nombre'] if max_partidos else '',
            'apellido': max_partidos['jugador__apellido'] if max_partidos else '',
            'partidos': max_partidos['total_partidos'] if max_partidos else 0
        } if max_partidos else None
    }

def get_h2h_historico(equipo1, equipo2, temporada=None):
    """Obtiene el histórico H2H entre dos equipos. Si se especifica temporada, incluye esa y todas las anteriores (no futuro)"""
    from main.models import Partido
    from django.db.models import Q
    
    # Construir filtro de partidos
    partidos_filter = Partido.objects.filter(
        goles_local__isnull=False,
        goles_visitante__isnull=False
    ).filter(
        Q(
            Q(equipo_local=equipo1) & Q(equipo_visitante=equipo2)
        ) | Q(
            Q(equipo_local=equipo2) & Q(equipo_visitante=equipo1)
        )
    )
    
    # Si se especifica temporada, filtrar solo esa temporada y anteriores
    if temporada:
        partidos_filter = partidos_filter.filter(
            jornada__temporada__nombre__lte=temporada.nombre
        )
    
    partidos = partidos_filter.select_related('equipo_local', 'equipo_visitante', 'jornada__temporada').order_by('-jornada__temporada__nombre', '-jornada__numero_jornada')
    
    # Contar resultados para equipo1
    victorias_eq1 = 0
    derrotas_eq1 = 0
    empates_eq1 = 0
    ultimos_5 = []
    
    for partido in partidos:
        es_local = partido.equipo_local == equipo1
        goles_propios = partido.goles_local if es_local else partido.goles_visitante
        goles_rival = partido.goles_visitante if es_local else partido.goles_local
        rival = partido.equipo_visitante if es_local else partido.equipo_local
        
        if goles_propios > goles_rival:
            victorias_eq1 += 1
            resultado = 'V'
        elif goles_propios < goles_rival:
            derrotas_eq1 += 1
            resultado = 'P'
        else:
            empates_eq1 += 1
            resultado = 'E'
        
        # Guardar últimos 5
        if len(ultimos_5) < 5:
            ultimos_5.append({
                'resultado': resultado,
                'contra': rival.nombre,
                'goles_propios': goles_propios,
                'goles_rival': goles_rival,
                'temporada': partido.jornada.temporada.nombre.replace('_', '/')
            })
    
    return {
        'victorias': victorias_eq1,
        'derrotas': derrotas_eq1,
        'empates': empates_eq1,
        'total': victorias_eq1 + derrotas_eq1 + empates_eq1,
        'ultimos_5': ultimos_5
    }

    return historico

def clasificacion(request):
    """Vista de Clasificación de la liga con filtros por temporada y jornada"""
    from main.models import Calendario, Partido
    
    # Obtener parámetros del GET
    temporada_display = request.GET.get('temporada', '25/26')
    jornada_num = request.GET.get('jornada', '1')
    equipo_seleccionado = request.GET.get('equipo', '')
    
    # Convertir formato 23/24 → 23_24 para búsqueda en BD
    temporada_nombre = temporada_display.replace('/', '_')
    
    # Obtener todas las temporadas disponibles
    temporadas = Temporada.objects.all().order_by('-nombre')
    
    # Preparar lista de temporadas con formato display (23/24)
    temporadas_display = []
    for temp in temporadas:
        display_name = temp.nombre.replace('_', '/')
        temporadas_display.append({
            'obj': temp,
            'nombre': temp.nombre,
            'display': display_name
        })
    
    # Obtener la temporada seleccionada
    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        temporada = temporadas.first()
        temporada_nombre = temporada.nombre if temporada else '23_24'
        temporada_display = temporada_nombre.replace('_', '/')
    
    # Obtener TODAS las jornadas (1-38) para ver calendario completo
    jornadas = Jornada.objects.filter(
        temporada=temporada
    ).order_by('numero_jornada')
    
    # Obtener lista de equipos disponibles para el dropdown
    equipos_disponibles = Equipo.objects.all().order_by('nombre')
    
    # Obtener la clasificación para la temporada y jornada
    clasificacion_datos = []
    jornada_obj = None
    partidos_jornada = []
    mostrar_clasificacion = True
    clasificacion_jornada_num = None
    
    # Si hay equipo seleccionado, filtrar todos sus partidos de la temporada
    if equipo_seleccionado:
        try:
            equipo_obj = Equipo.objects.get(nombre=equipo_seleccionado)
            # Obtener TODOS los partidos de este equipo en la temporada
            partidos_calendario = Calendario.objects.filter(
                jornada__temporada=temporada
            ).filter(
                Q(equipo_local=equipo_obj) | Q(equipo_visitante=equipo_obj)
            ).select_related('equipo_local', 'equipo_visitante', 'jornada').order_by('jornada__numero_jornada', 'fecha', 'hora')
            
            # Obtener la última jornada con clasificación para mostrar junto con los partidos del equipo
            ultima_jornada_con_clasificacion = Jornada.objects.filter(
                temporada=temporada,
                clasificacionjornada__isnull=False
            ).order_by('numero_jornada').last()
            
            if ultima_jornada_con_clasificacion:
                # Obtener clasificación de la jornada más actual
                clasificacion_datos = ClasificacionJornada.objects.filter(
                    temporada=temporada,
                    jornada=ultima_jornada_con_clasificacion
                ).order_by('posicion', 'equipo__nombre').select_related('equipo')
                
                # Agregar iniciales y diferencia de jornadas a cada registro para el template
                for reg in clasificacion_datos:
                    palabras = reg.equipo.nombre.split()
                    reg.iniciales = ''.join([palabra[0].upper() for palabra in palabras])
                    
                    # Calcular diferencia de partidos jugados
                    total_pj = reg.partidos_ganados + reg.partidos_empatados + reg.partidos_perdidos
                    reg.diferencia_jornada = total_pj - ultima_jornada_con_clasificacion.numero_jornada
                    
                    # Obtener detalles de la racha
                    reg.racha_detalles = get_racha_detalles(reg.equipo, temporada, ultima_jornada_con_clasificacion)
                
                clasificacion_jornada_num = ultima_jornada_con_clasificacion.numero_jornada
                mostrar_clasificacion = True
            else:
                mostrar_clasificacion = False
            
        except Equipo.DoesNotExist:
            equipo_seleccionado = ''
            mostrar_clasificacion = True
            partidos_calendario = []
    
    # Si no hay equipo seleccionado, usar el filtro de jornada estándar
    if not equipo_seleccionado:
        if jornadas.exists():
            try:
                jornada_obj = jornadas.get(numero_jornada=int(jornada_num))
            except (Jornada.DoesNotExist, ValueError):
                jornada_obj = jornadas.first()
                jornada_num = jornada_obj.numero_jornada if jornada_obj else 1
            
            if jornada_obj:
                # Obtener clasificación
                clasificacion_datos = ClasificacionJornada.objects.filter(
                    temporada=temporada,
                    jornada=jornada_obj
                ).order_by('posicion', 'equipo__nombre').select_related('equipo')
                
                # Guardar el número de jornada de clasificación
                clasificacion_jornada_num = jornada_obj.numero_jornada
                
                # Agregar iniciales y diferencia de jornadas a cada registro para el template
                for reg in clasificacion_datos:
                    palabras = reg.equipo.nombre.split()
                    reg.iniciales = ''.join([palabra[0].upper() for palabra in palabras])
                    
                    # Calcular diferencia de partidos jugados
                    total_pj = reg.partidos_ganados + reg.partidos_empatados + reg.partidos_perdidos
                    reg.diferencia_jornada = total_pj - jornada_obj.numero_jornada
                    
                    # Obtener detalles de la racha
                    reg.racha_detalles = get_racha_detalles(reg.equipo, temporada, jornada_obj)
                
                # Obtener partidos de la jornada desde Calendario
                partidos_calendario = Calendario.objects.filter(
                    jornada=jornada_obj
                ).select_related('equipo_local', 'equipo_visitante').order_by('fecha', 'hora')
        else:
            partidos_calendario = []
    else:
        # Ya se obtuvieron arriba
        pass
    
    # Enriquecer con resultados si el partido ya se jugó
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
                'goles_local': [],
                'goles_visitante': [],
                'amarillas_local': [],
                'amarillas_visitante': [],
                'rojas_local': [],
                'rojas_visitante': []
            }
        }
        
        # Verificar si el partido ya se jugó (buscar en tabla Partido)
        partido_jugado = Partido.objects.filter(
            jornada=partido_cal.jornada,
            equipo_local=partido_cal.equipo_local,
            equipo_visitante=partido_cal.equipo_visitante
        ).first()
        
        # Solo mostrar goles si están en tabla Partido (datos oficiales verificados)
        if partido_jugado and partido_jugado.goles_local is not None and partido_jugado.goles_visitante is not None:
            partido_info['goles_local'] = partido_jugado.goles_local
            partido_info['goles_visitante'] = partido_jugado.goles_visitante
            partido_info['jugado'] = True
            
            # Obtener sucesos del partido (goles y tarjetas)
            estadisticas = EstadisticasPartidoJugador.objects.filter(
                partido=partido_jugado
            ).select_related('jugador')
            
            for stat in estadisticas:
                # Determinar si el jugador juega en equipo local o visitante
                es_local = EquipoJugadorTemporada.objects.filter(
                    jugador=stat.jugador,
                    equipo=partido_cal.equipo_local,
                    temporada=temporada
                ).exists()
                
                # Goles
                if stat.gol_partido > 0:
                    nombres = f"{stat.jugador.nombre} {stat.jugador.apellido}".strip()
                    if es_local:
                        for _ in range(stat.gol_partido):
                            partido_info['sucesos']['goles_local'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
                    else:
                        for _ in range(stat.gol_partido):
                            partido_info['sucesos']['goles_visitante'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
                
                # Amarillas
                if stat.amarillas > 0:
                    nombres = f"{stat.jugador.nombre} {stat.jugador.apellido}".strip()
                    if es_local:
                        for _ in range(stat.amarillas):
                            partido_info['sucesos']['amarillas_local'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
                    else:
                        for _ in range(stat.amarillas):
                            partido_info['sucesos']['amarillas_visitante'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
                
                # Rojas
                if stat.rojas > 0:
                    nombres = f"{stat.jugador.nombre} {stat.jugador.apellido}".strip()
                    if es_local:
                        for _ in range(stat.rojas):
                            partido_info['sucesos']['rojas_local'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
                    else:
                        for _ in range(stat.rojas):
                            partido_info['sucesos']['rojas_visitante'].append({
                                'nombre': nombres,
                                'minuto': stat.min_partido
                            })
        
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

def equipo(request, equipo_nombre=None, temporada=None):
    """Vista de detalles de equipo con plantilla de jugadores que jugaron"""
    # Obtener temporada: GET parameter tiene prioridad, luego URL parameter, luego default
    temporada_display = request.GET.get('temporada') or temporada or '25/26'
    temporada_nombre = temporada_display.replace('/', '_')
    
    # Obtener todas las temporadas disponibles
    temporadas = Temporada.objects.all().order_by('-nombre')
    temporadas_display = []
    for temp in temporadas:
        display_name = temp.nombre.replace('_', '/')
        temporadas_display.append({
            'nombre': temp.nombre,
            'display': display_name
        })
    
    # Obtener el equipo
    equipo = None
    jugadores = []
    equipo_display_nombre = equipo_nombre or 'FC Barcelona'
    jornadas_disponibles = []
    jornada_actual = None
    
    try:
        equipo = Equipo.objects.get(nombre=equipo_display_nombre)
        
        # Obtener la temporada
        try:
            temp_obj = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temp_obj = temporadas.first()
            temporada_nombre = temp_obj.nombre if temp_obj else '24_25'
            temporada_display = temporada_nombre.replace('_', '/')
        
        # Obtener TODAS las jornadas (1-38) para ver calendario completo
        jornadas_temp = Jornada.objects.filter(
            temporada=temp_obj
        ).order_by('numero_jornada')
        jornadas_disponibles = [{'numero': j.numero_jornada} for j in jornadas_temp]
        jornada_min = 1
        # Obtener la última jornada que tiene clasificación (para default)
        ultima_jornada_clasificacion = Jornada.objects.filter(
            temporada=temp_obj,
            clasificacionjornada__isnull=False
        ).order_by('numero_jornada').last()
        ultima_jornada_clasificacion = ultima_jornada_clasificacion.numero_jornada if ultima_jornada_clasificacion else 1
        
        # jornada_max es SIEMPRE 38 para búsqueda de próximos partidos (aunque no tengan clasificación aún)
        jornada_max = 38
        
        # Obtener jornada seleccionada del GET parameter
        jornada_num = request.GET.get('jornada')
        if jornada_num:
            try:
                jornada_actual = int(jornada_num)
                # Validar que la jornada tenga clasificación
                if not jornadas_temp.filter(numero_jornada=jornada_actual).exists():
                    jornada_actual = None
            except (ValueError, TypeError):
                jornada_actual = None
        else:
            jornada_actual = None
        
        # Default: usar la última jornada con clasificación
        if jornada_actual is None:
            jornada_actual = ultima_jornada_clasificacion
        
        # Obtener plantilla del equipo SOLO para la temporada seleccionada
        # Agrupar por jugador para consolidar dorsal 0 (suplentes) con el mismo jugador
        jugadores_equipo_temp = EquipoJugadorTemporada.objects.filter(
            equipo=equipo,
            temporada=temp_obj
        ).select_related('jugador').order_by('dorsal')
        
        # Diccionario para agrupar por jugador
        jugadores_agrupados = {}
        puntos_dorsal_cero = {}  # Guardar puntos negativos de dorsal 0 para restar después
        
        # Calcular estadísticas de Fantasy para cada jugador EN ESA TEMPORADA Y JORNADA
        for eq_jug_temp in jugadores_equipo_temp:
            # Obtener estadísticas del jugador SOLO en esta temporada y hasta esta jornada
            stats_query = EstadisticasPartidoJugador.objects.filter(
                jugador=eq_jug_temp.jugador,
                partido__jornada__temporada=temp_obj
            )
            
            # Filtrar por jornada si está especificada
            if jornada_actual:
                stats_query = stats_query.filter(partido__jornada__numero_jornada__lte=jornada_actual)
            
            stats = stats_query
            
            # Calcular totales (filtrando puntos anómalos > 40 que indican errores de matching)
            valid_stats = stats.exclude(puntos_fantasy__gt=40)  # Excluir valores como 6767
            total_puntos = valid_stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
            partidos_jugados = valid_stats.count()
            total_minutos = valid_stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0
            
            # FILTRO: Si es dorsal 0 con puntos negativos, guardar para matching posterior
            if eq_jug_temp.dorsal == 0 and total_puntos <= 0:
                # Guardar el nombre/apellido y puntos para matching después
                nombre_completo = f"{eq_jug_temp.jugador.nombre} {eq_jug_temp.jugador.apellido}".strip()
                puntos_dorsal_cero[nombre_completo] = {
                    'puntos': total_puntos,
                    'nombre': eq_jug_temp.jugador.nombre,
                    'apellido': eq_jug_temp.jugador.apellido
                }
                continue
            
            # Obtener posición más frecuente en esta temporada
            posicion_frecuente = stats.values('posicion').annotate(
                count=Count('id')
            ).order_by('-count').first()
            
            # Agrupar por jugador
            jugador_id = eq_jug_temp.jugador.id
            
            if jugador_id not in jugadores_agrupados:
                # Primera vez que vemos este jugador
                jugadores_agrupados[jugador_id] = {
                    'obj': eq_jug_temp,
                    'total_puntos': total_puntos,
                    'partidos_stats': partidos_jugados,
                    'total_minutos': total_minutos,
                    'posicion': posicion_frecuente['posicion'] if posicion_frecuente else None,
                    'nombre': eq_jug_temp.jugador.nombre,
                    'apellido': eq_jug_temp.jugador.apellido
                }
            else:
                # Ya existe este jugador (dorsal 0), consolidar puntos
                jugadores_agrupados[jugador_id]['total_puntos'] += total_puntos
        
        # Matching: Buscar coincidencias entre puntos de dorsal 0 y jugadores principales
        from difflib import SequenceMatcher
        
        def similitud_nombres(nombre1, nombre2):
            """Calcula similitud entre dos nombres (0-1)"""
            return SequenceMatcher(None, nombre1.lower(), nombre2.lower()).ratio()
        
        for nombre_dorsal_cero, datos_dorsal_cero in puntos_dorsal_cero.items():
            mejor_coincidencia = None
            mejor_similitud = 0.6  # Umbral mínimo de similitud (60%)
            
            # Buscar el jugador principal con nombre más similar
            for jugador_id, datos_principal in jugadores_agrupados.items():
                nombre_principal = f"{datos_principal['nombre']} {datos_principal['apellido']}".strip()
                
                # Calcular similitud
                similitud = similitud_nombres(nombre_dorsal_cero, nombre_principal)
                
                if similitud > mejor_similitud:
                    mejor_similitud = similitud
                    mejor_coincidencia = jugador_id
            
            # Si encontramos una coincidencia, restar los puntos
            if mejor_coincidencia:
                jugadores_agrupados[mejor_coincidencia]['total_puntos'] += datos_dorsal_cero['puntos']
        
        # Crear lista final con jugadores agrupados
        for jugador_id, datos in jugadores_agrupados.items():
            eq_jug_temp = datos['obj']
            total_puntos = datos['total_puntos']
            partidos_jugados = datos['partidos_stats']
            total_minutos = datos['total_minutos']
            
            # Calcular promedio
            promedio_puntos = total_puntos / partidos_jugados if partidos_jugados > 0 else 0
            
            # Añadir atributos al objeto
            eq_jug_temp.total_puntos_fantasy = total_puntos
            eq_jug_temp.partidos_stats = partidos_jugados
            eq_jug_temp.total_minutos = total_minutos
            eq_jug_temp.promedio_puntos_fantasy = round(promedio_puntos, 2)
            eq_jug_temp.posicion = datos['posicion']
            
            jugadores.append(eq_jug_temp)
        
        # Calcular top 3 por puntos y minutos
        top_3_puntos = sorted(jugadores, key=lambda x: x.total_puntos_fantasy, reverse=True)[:3]
        top_3_minutos = sorted(jugadores, key=lambda x: x.total_minutos, reverse=True)[:3]
        
        # Obtener estadísticas del equipo actual hasta la jornada actual para la comparativa
        goles_equipo_favor = 0
        goles_equipo_contra = 0
        racha_actual = []
        clasificacion_actual = ClasificacionJornada.objects.filter(
            equipo=equipo,
            temporada=temp_obj,
            jornada__numero_jornada__lte=jornada_actual if jornada_actual else jornada_max
        ).order_by('-jornada__numero_jornada').first()
        
        if clasificacion_actual:
            goles_equipo_favor = clasificacion_actual.goles_favor
            goles_equipo_contra = clasificacion_actual.goles_contra
            if clasificacion_actual.racha_reciente:
                # Convertir racha de W/D/L a V/E/P (español)
                racha_raw = list(clasificacion_actual.racha_reciente)
                racha_actual = []
                for resultado in racha_raw:
                    if resultado == 'W':
                        racha_actual.append('V')  # Victoria
                    elif resultado == 'D':
                        racha_actual.append('E')  # Empate
                    elif resultado == 'L':
                        racha_actual.append('P')  # Pérdida
                    else:
                        racha_actual.append(resultado)
        
        # Obtener información del próximo partido desde Calendario
        # Busca la próxima jornada que exista (puede haber jornadas sin jugar)
        proximo_partido = None
        rival_info = None
        racha_rival = []
        goles_rival_favor = 0
        goles_rival_contra = 0
        
        # Obtener objeto Jornada para jornada_actual
        jornada_actual_obj = None
        if jornada_actual:
            try:
                jornada_actual_obj = Jornada.objects.get(
                    temporada=temp_obj,
                    numero_jornada=jornada_actual
                )
            except Jornada.DoesNotExist:
                jornada_actual_obj = None
        
        from main.models import Calendario
        
        if jornada_actual and jornada_actual < jornada_max:
            # Buscar el próximo partido ordenado por número de jornada
            # Intenta jornada +1, +2, +3, etc. hasta encontrar
            proximo_encontrado = None
            
            for offset in range(1, (jornada_max - jornada_actual) + 1):
                intento_jornada = jornada_actual + offset
                partidos_intentar = Calendario.objects.filter(
                    jornada__temporada=temp_obj,
                    jornada__numero_jornada=intento_jornada
                ).filter(
                    Q(equipo_local=equipo) | Q(equipo_visitante=equipo)
                ).first()
                
                if partidos_intentar:
                    proximo_encontrado = partidos_intentar
                    break
            
            if proximo_encontrado:
                partido_calendario = proximo_encontrado
                
                # Determinar rival y si es local o visitante
                if partido_calendario.equipo_local == equipo:
                    rival = partido_calendario.equipo_visitante
                    es_local = True
                    estadio_partido = equipo.estadio or 'Estadio desconocido'
                else:
                    rival = partido_calendario.equipo_local
                    es_local = False
                    estadio_partido = rival.estadio or 'Estadio desconocido'
                
                # Crear un objeto partido_info con fecha del calendario
                class PartidoInfo:
                    pass
                
                proximo_partido = PartidoInfo()
                proximo_partido.equipo_local = partido_calendario.equipo_local
                proximo_partido.equipo_visitante = partido_calendario.equipo_visitante
                proximo_partido.fecha_partido = datetime.combine(partido_calendario.fecha, partido_calendario.hora or time(18, 0))
                proximo_partido.goles_local = None
                proximo_partido.goles_visitante = None
                
                # Obtener estadísticas del rival hasta la jornada actual
                clasificacion_rival = ClasificacionJornada.objects.filter(
                    equipo=rival,
                    temporada=temp_obj,
                    jornada__numero_jornada__lte=jornada_actual
                ).order_by('-jornada__numero_jornada').first()
                
                racha_rival_detalles = []
                if clasificacion_rival:
                    goles_rival_favor = clasificacion_rival.goles_favor
                    goles_rival_contra = clasificacion_rival.goles_contra
                    
                    # Obtener racha detallada del rival
                    jornada_rival_obj = clasificacion_rival.jornada
                    racha_rival_detalles = get_racha_detalles(rival, temp_obj, jornada_rival_obj)
                    
                    # Obtener máximos goleadores de ambos equipos
                    max_goleador_equipo = get_maximo_goleador(equipo, temp_obj, jornada_actual_obj) if jornada_actual_obj else None
                    max_goleador_rival = get_maximo_goleador(rival, temp_obj, jornada_actual_obj) if jornada_actual_obj else None
                    
                    # Obtener partido anterior en la temporada si existe
                    partido_anterior = get_partido_anterior_temporada(equipo, rival, temp_obj, jornada_actual_obj) if jornada_actual_obj else None
                    
                    rival_info = {
                        'nombre': rival.nombre,
                        'iniciales': ''.join([palabra[0].upper() for palabra in rival.nombre.split()]),
                        'nombre_normalizado': normalize_team_name_python(rival.nombre),
                        'es_local': es_local,
                        'estadio_rival': rival.estadio or 'Estadio desconocido',
                        'estadio_partido': estadio_partido,
                        'racha': racha_rival_detalles,
                        'goles_favor': goles_rival_favor,
                        'goles_contra': goles_rival_contra,
                        'h2h': get_h2h_historico(equipo, rival, temp_obj),
                        'max_goleador_equipo': max_goleador_equipo,
                        'max_goleador_rival': max_goleador_rival,
                        'partido_anterior': partido_anterior
                    }
    
    except Equipo.DoesNotExist:
        equipo = None
        jugadores = []
        top_3_puntos = []
        top_3_minutos = []
        jornadas_disponibles = []
        jornada_actual = None
        jornada_min = 1
        jornada_max = 38
        racha_actual = []
        proximo_partido = None
        rival_info = None
    
    # Calcular iniciales del equipo
    iniciales = ''
    racha_actual_detalles = []
    racha_futura_detalles = []
    historico_temporadas = []
    
    if equipo:
        palabras = equipo.nombre.split()
        iniciales = ''.join([palabra[0].upper() for palabra in palabras])
        
        # Obtener detalles de racha actual (últimos 5 partidos jugados)
        if jornada_actual_obj:
            racha_actual_detalles = get_racha_detalles(equipo, temp_obj, jornada_actual_obj)
            racha_futura_detalles = get_racha_futura(equipo, temp_obj, jornada_actual_obj)
        
        # Obtener histórico de todas las temporadas
        historico_temporadas = get_historico_temporadas(equipo)
        
        # Obtener estadísticas agregadas de las últimas 3 temporadas
        ultimas_3_stats = get_estadisticas_equipo_temporadas(equipo, num_temporadas=3) if equipo else None
        ultimas_3_jugadores = get_jugadores_ultimas_temporadas(equipo, num_temporadas=3) if equipo else None
    
    context = {
        'active_page': 'equipos',
        'equipo': equipo,
        'equipo_nombre': equipo_display_nombre,
        'iniciales': iniciales,
        'jugadores': jugadores,
        'top_3_puntos': top_3_puntos,
        'top_3_minutos': top_3_minutos,
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_nombre,  # Formato URL con underscore: 25_26
        'temporada_actual_url': temporada_nombre,  # Formato URL: 25_26
        'temporada_actual_db': temporada_nombre,  # Formato con guion (23_24) para URLs
        'jornadas_disponibles': jornadas_disponibles,
        'jornada_actual': jornada_actual,
        'jornada_min': jornada_min,
        'jornada_max': jornada_max,
        'proximo_partido': proximo_partido,
        'rival_info': rival_info,
        'goles_equipo_favor': goles_equipo_favor,
        'goles_equipo_contra': goles_equipo_contra,
        'racha_actual': racha_actual,
        'racha_actual_detalles': racha_actual_detalles,
        'racha_futura_detalles': racha_futura_detalles,
        'historico_temporadas': historico_temporadas,
        'ultimas_3_stats': ultimas_3_stats,
        'ultimas_3_jugadores': ultimas_3_jugadores,
        'desde_clasificacion': equipo_nombre is not None
    }
    
    return render(request, 'equipo.html', context)

def calcular_percentil(jugador_obj, temporada_obj, posicion, stat_field, es_carrera=False):
    """
    Calcula el percentil de un jugador para un stat específico dentro de su posición y temporada.
    Retorna un número entre 0 y 100. Usa caché para evitar recálculos.
    """
    from django.core.cache import cache
    from django.db.models import Sum
    from scipy import stats as scipy_stats
    
    # Crear clave de caché única
    temp_name = temporada_obj.nombre if temporada_obj else 'all'
    cache_key = f"percentil_{jugador_obj.id}_{temp_name}_{posicion}_{stat_field}"
    
    # Intentar obtener del caché
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value
    
    try:
        # Seleccionar jugadores de la misma posición
        if es_carrera:
            # Para carrera, agrupar por jugador de todas las temporadas
            misma_posicion = EstadisticasPartidoJugador.objects.filter(
                posicion=posicion
            ).values('jugador').distinct()
        else:
            # Solo de la temporada específica
            misma_posicion = EstadisticasPartidoJugador.objects.filter(
                posicion=posicion,
                partido__jornada__temporada=temporada_obj
            ).values('jugador').distinct()
        
        # Obtener lista de jugadores
        jugadores_posicion = [jug['jugador'] for jug in misma_posicion]
        
        if not jugadores_posicion:
            return 50  # Por defecto 50 percentil
        
        # Calcular el stat para cada jugador de la posición
        valores = []
        for jug_id in jugadores_posicion:
            if es_carrera:
                query = EstadisticasPartidoJugador.objects.filter(jugador_id=jug_id)
            else:
                query = EstadisticasPartidoJugador.objects.filter(
                    jugador_id=jug_id,
                    partido__jornada__temporada=temporada_obj
                )
            
            agg = query.aggregate(stat_value=Sum(stat_field))
            valor = agg['stat_value'] or 0
            valores.append(float(valor))
        
        # Si no hay valores, retornar 50
        if not valores:
            return 50
        
        # Obtener el valor del jugador consultado
        if es_carrera:
            jugador_value = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador_obj
            ).aggregate(suma=Sum(stat_field))['suma'] or 0
        else:
            jugador_value = EstadisticasPartidoJugador.objects.filter(
                jugador=jugador_obj,
                partido__jornada__temporada=temporada_obj
            ).aggregate(suma=Sum(stat_field))['suma'] or 0
        
        jugador_value = float(jugador_value)
        
        # Calcular percentil usando scipy
        percentil = int(scipy_stats.percentileofscore(valores, jugador_value))
        
        # Guardar en caché por 1 hora
        cache.set(cache_key, percentil, 3600)
        
        return percentil
    
    except Exception as e:
        # Si hay error, retornar 50 (default)
        return 50

def jugador(request, jugador_id=None, temporada=None):
    """Vista de estadísticas de jugador"""
    from django.db.models import Sum, Q, Avg, Case, When, IntegerField
    
    if not jugador_id:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Jugador no encontrado'})
    
    try:
        jugador_obj = Jugador.objects.get(id=jugador_id)
    except Jugador.DoesNotExist:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Jugador no encontrado'})
    
    # Obtener temporadas disponibles para este jugador
    temporadas_jugador = EquipoJugadorTemporada.objects.filter(
        jugador=jugador_obj
    ).values_list('temporada__nombre', flat=True).distinct().order_by('-temporada__nombre')
    
    # Detectar si es "Carrera" (todas las temporadas)
    es_carrera = temporada == "carrera"
    
    # Usar temporada actual o la proporcionada
    if not temporada and temporadas_jugador:
        temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0])
    elif temporada and not es_carrera:
        try:
            temporada_obj = Temporada.objects.get(nombre=temporada)
        except:
            temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0]) if temporadas_jugador else None
    elif es_carrera:
        # Para carrera, usar la primera temporada como ref (solo para display)
        temporada_obj = Temporada.objects.get(nombre=temporadas_jugador[0]) if temporadas_jugador else None
    else:
        temporada_obj = None
    
    if not temporada_obj:
        return render(request, 'jugador.html', {'active_page': 'estadisticas', 'error': 'Temporada no encontrada'})
    
    # Obtener datos del jugador en esta temporada (o carrera)
    if es_carrera:
        # Para carrera, verificar que tiene datos en al menos una temporada
        equipo_temporada = EquipoJugadorTemporada.objects.filter(
            jugador=jugador_obj
        ).first()
    else:
        equipo_temporada = EquipoJugadorTemporada.objects.filter(
            jugador=jugador_obj,
            temporada=temporada_obj
        ).first()
    
    if not equipo_temporada:
        return render(request, 'jugador.html', {
            'active_page': 'estadisticas',
            'jugador': jugador_obj,
            'temporada_obj': temporada_obj,
            'temporadas_disponibles': [{'nombre': t, 'display': t.replace('_', '/')} for t in temporadas_jugador],
            'error': 'Jugador no jugó en esta temporada'
        })
    
    # Estadísticas de la temporada (o carrera)
    if es_carrera:
        # Sumar estadísticas de TODAS las temporadas
        filter_query = Q(jugador=jugador_obj)
    else:
        # Solo de esta temporada
        filter_query = Q(jugador=jugador_obj, partido__jornada__temporada=temporada_obj)
    
    # Filtrar puntos anómalos (>40) que indican errores de matching
    stats = EstadisticasPartidoJugador.objects.filter(filter_query).exclude(puntos_fantasy__gt=40).aggregate(
        # Estadísticas básicas
        total_goles=Sum('gol_partido'),
        total_asistencias=Sum('asist_partido'),
        total_minutos=Sum('min_partido'),
        total_partidos=Count('id', filter=Q(min_partido__gt=0)),
        promedio_puntos=Avg('puntos_fantasy'),
        
        # BLOQUE ORGANIZACIÓN
        total_pases=Sum('pases_totales'),
        pases_accuracy=Avg('pases_completados_pct'),
        total_xag=Sum('xag'),
        
        # BLOQUE REGATES
        total_regates=Sum('regates'),
        regates_completados=Sum('regates_completados'),
        regates_fallidos=Sum('regates_fallidos'),
        conducciones_progresivas=Sum('conducciones_progresivas'),
        total_conducciones=Sum('conducciones'),
        distancia_conduccion=Sum('distancia_conduccion'),
        metros_avanzados_conduccion=Sum('metros_avanzados_conduccion'),
        
        # BLOQUE DEFENSA
        total_despejes=Sum('despejes'),
        total_entradas=Sum('entradas'),
        duelos_ganados=Sum('duelos_ganados'),
        duelos_perdidos=Sum('duelos_perdidos'),
        total_duelos=Sum('duelos'),
        total_amarillas=Sum('amarillas'),
        total_rojas=Sum('rojas'),
        bloqueo_pase=Sum('bloqueo_pase'),
        bloqueo_tiros=Sum('bloqueo_tiros'),
        total_bloqueos=Sum('bloqueos'),
        duelos_aereos_ganados=Sum('duelos_aereos_ganados'),
        duelos_aereos_perdidos=Sum('duelos_aereos_perdidos'),
        duelos_aereos_pct=Avg('duelos_aereos_ganados_pct'),
        
        # BLOQUE ATAQUE
        total_tiros=Sum('tiros'),
        tiros_puerta=Sum('tiro_puerta_partido'),
        tiros_fallados=Sum('tiro_fallado_partido'),
        total_xg=Sum('xg_partido'),
        
        # ESTADÍSTICAS DE PORTERO
        goles_en_contra=Sum('goles_en_contra'),
        porcentaje_paradas=Avg('porcentaje_paradas'),
        psxg=Sum('psxg'),
    )
    
    # Últimos 12 partidos (también sin puntos anómalos)
    if es_carrera:
        ultimos_12 = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj
        ).exclude(puntos_fantasy__gt=40).select_related('partido', 'partido__jornada').order_by('-partido__jornada__temporada', '-partido__jornada__numero_jornada')[:12]
    else:
        ultimos_12 = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj,
            partido__jornada__temporada=temporada_obj
        ).exclude(puntos_fantasy__gt=40).select_related('partido', 'partido__jornada').order_by('-partido__jornada__numero_jornada')[:12]
    
    ultimos_12_ordenados = list(reversed(ultimos_12))
    
    # Obtener roles de los partidos y formatearlos correctamente (sin puntos anómalos)
    roles = []
    if es_carrera:
        stats_con_roles = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj,
            roles__isnull=False
        ).exclude(puntos_fantasy__gt=40).exclude(roles__exact=[]).values_list('roles', flat=True)
    else:
        stats_con_roles = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj,
            partido__jornada__temporada=temporada_obj,
            roles__isnull=False
        ).exclude(puntos_fantasy__gt=40).exclude(roles__exact=[]).values_list('roles', flat=True)
    
    # Mergear todos los roles, manteniendo la mejor posición para cada campo
    roles_dict = {}
    for stats_roles in stats_con_roles:
        if stats_roles and isinstance(stats_roles, list):
            # Cada elemento es un diccionario como {"goles": [1, 35]}
            for role_obj in stats_roles:
                if isinstance(role_obj, dict):
                    for field_name, values in role_obj.items():
                        # Mantener el de menor posición (mejor ranking)
                        if field_name not in roles_dict or values[0] < roles_dict[field_name][0]:
                            roles_dict[field_name] = values
    
    # Convertir a lista de diccionarios como espera el template
    if roles_dict:
        roles = [roles_dict]
    
    # Histórico de carrera
    historico = EquipoJugadorTemporada.objects.filter(
        jugador=jugador_obj
    ).select_related('equipo', 'temporada').order_by('-temporada')
    
    historico_data = []
    for hist in historico:
        # Filtrar puntos anómalos (>40) para cada temporada
        stats_hist = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador_obj,
            partido__jornada__temporada=hist.temporada
        ).exclude(puntos_fantasy__gt=40).aggregate(
            goles=Sum('gol_partido'),
            asistencias=Sum('asist_partido'),
            minutos=Sum('min_partido'),
            partidos=Count('id', filter=Q(min_partido__gt=0)),
            promedio_puntos=Avg('puntos_fantasy'),
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
            bloqueo_tiros=Sum('bloqueo_tiros'),
            bloqueo_pase=Sum('bloqueo_pase'),
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
            'temporada_numero': hist.temporada.nombre,
            'equipo': hist.equipo.nombre,
            'dorsal': hist.dorsal or '-',
            'puntos_totales': puntos_totales,
            'puntos_por_partido': puntos_por_partido,
            'goles': stats_hist['goles'] or 0,
            'asistencias': stats_hist['asistencias'] or 0,
            'pj': partidos,
            'minutos': stats_hist['minutos'] or 0,
            'promedio_puntos': round(stats_hist['promedio_puntos'] or 0, 1),
            # Organización
            'pases': stats_hist['pases'] or 0,
            'pases_accuracy': round(stats_hist['pases_accuracy'] or 0, 1),
            'xag': round(stats_hist['xag'] or 0, 2),
            # Defensa
            'despejes': stats_hist['despejes'] or 0,
            'entradas': stats_hist['entradas'] or 0,
            'duelos_ganados': stats_hist['duelos_ganados'] or 0,
            'duelos_perdidos': stats_hist['duelos_perdidos'] or 0,
            'duelos_totales': (stats_hist['duelos_ganados'] or 0) + (stats_hist['duelos_perdidos'] or 0),
            'amarillas': stats_hist['amarillas'] or 0,
            'rojas': stats_hist['rojas'] or 0,
            'bloqueos': stats_hist['bloqueos'] or 0,
            'bloqueo_tiros': stats_hist['bloqueo_tiros'] or 0,
            'bloqueo_pase': stats_hist['bloqueo_pase'] or 0,
            'duelos_aereos_ganados': stats_hist['duelos_aereos_ganados'] or 0,
            'duelos_aereos_perdidos': stats_hist['duelos_aereos_perdidos'] or 0,
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
    
    # Obtener posición más frecuente (agregando de las estadísticas)
    posicion = jugador_obj.get_posicion_mas_frecuente()
    
    # Percentiles: LEER de EquipoJugadorTemporada (ya precalculados)
    # No calcular aquí, está almacenado en el modelo
    percentiles = equipo_temporada.percentiles if equipo_temporada.percentiles else {}
    
    # Radar chart: se calcula ON-DEMAND en el API endpoint, no al cargar la página
    # Esto permite que la página cargue rápido sin hacer cálculos innecesarios
    radar_values = []
    media_general = 0
    
    posicion_map = {
        'Portero': 'PT',
        'Defensa': 'DF',
        'Centrocampista': 'MC',
        'Delantero': 'DT'
    }
    
    posicion_color_map = {
        'Portero': '59, 130, 246',  # Azul
        'Defensa': '34, 197, 94',    # Verde
        'Centrocampista': '234, 179, 8',  # Amarillo
        'Delantero': '239, 68, 68',   # Rojo
    }
    
    context = {
        'active_page': 'estadisticas',
        'jugador': jugador_obj,
        'equipo_temporada': equipo_temporada,
        'temporada_obj': temporada_obj,
        'temporada_display': 'Carrera' if es_carrera else temporada_obj.nombre.replace('_', '/'),
        'es_carrera': es_carrera,
        'temporadas_disponibles': [{'nombre': t, 'display': t.replace('_', '/')} for t in temporadas_jugador],
        'stats': {
            # Básicas
            'goles': stats['total_goles'] or 0,
            'asistencias': stats['total_asistencias'] or 0,
            'minutos': stats['total_minutos'] or 0,
            'partidos': stats['total_partidos'] or 0,
            'promedio_puntos': round(stats['promedio_puntos'] or 0, 1),
            
            # BLOQUE ORGANIZACIÓN
            'organizacion': {
                'pases': stats['total_pases'] or 0,
                'pases_accuracy': round(stats['pases_accuracy'] or 0, 1),
                'xag': round(stats['total_xag'] or 0, 2),
            },
            
            # BLOQUE REGATES
            'regates_block': {
                'regates_completados': stats['regates_completados'] or 0,
                'regates_fallidos': stats['regates_fallidos'] or 0,
                'conducciones_progresivas': stats['conducciones_progresivas'] or 0,
                'conducciones': stats['total_conducciones'] or 0,
                'distancia_conduccion': round(stats['distancia_conduccion'] or 0, 1),
                'metros_avanzados': round(stats['metros_avanzados_conduccion'] or 0, 1),
            },
            
            # BLOQUE DEFENSA
            'defensa': {
                'despejes': stats['total_despejes'] or 0,
                'entradas': stats['total_entradas'] or 0,
                'duelos_ganados': stats['duelos_ganados'] or 0,
                'duelos_perdidos': stats['duelos_perdidos'] or 0,
                'duelos': (stats['duelos_ganados'] or 0) + (stats['duelos_perdidos'] or 0),
                'amarillas': stats['total_amarillas'] or 0,
                'rojas': stats['total_rojas'] or 0,
                'bloqueo_pase': stats['bloqueo_pase'] or 0,
                'bloqueo_tiros': stats['bloqueo_tiros'] or 0,
                'bloqueos': stats['total_bloqueos'] or 0,
                'duelos_aereos_ganados': stats['duelos_aereos_ganados'] or 0,
                'duelos_aereos_perdidos': stats['duelos_aereos_perdidos'] or 0,
                'duelos_aereos_pct': round(stats['duelos_aereos_pct'] or 0, 1),
            },
            
            # BLOQUE ATAQUE
            'ataque': {
                'goles': stats['total_goles'] or 0,
                'tiros_puerta': stats['tiros_puerta'] or 0,
                'tiros_fallados': stats['tiros_fallados'] or 0,
                'tiros': stats['total_tiros'] or 0,
                'xg': round(stats['total_xg'] or 0, 2),
            },
            
            # ESTADÍSTICAS DE PORTERO
            'portero': {
                'goles_en_contra': stats['goles_en_contra'] or 0,
                'porcentaje_paradas': round(stats['porcentaje_paradas'] or 0, 1),
                'pases': stats['total_pases'] or 0,
                'psxg': round(stats['psxg'] or 0, 2),
            },
        },
        'ultimos_8': ultimos_12_ordenados,
        'historico': historico_data,
        'posicion': posicion,
        'posicion_corta': posicion_map.get(posicion, 'N/A'),
        'posicion_color': posicion_color_map.get(posicion, '156, 163, 175'),
        'edad': equipo_temporada.edad or 0,
        'roles': roles,
        'descripciones_roles': DESCRIPCIONES_ROLES,
        'percentiles': percentiles,
        'radar_values': radar_values,
        'media_general': round(media_general, 2),
    }
    
    return render(request, 'jugador.html', context)

def amigos(request):
    """Vista de amigos y comparaciones"""
    return render(request, 'amigos.html', {'active_page': 'amigos'})

def login_register(request):
    """Vista de login y registro"""
    return render(request, 'login_register.html', {'active_page': 'login'})

def login_view(request):
    """Maneja el login del usuario"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirigir a 'next' si existe, sino al menú
            if next_url:
                return redirect(next_url)
            return redirect('menu')
        else:
            next_param = f"?next={next_url}" if next_url else ""
            return render(request, 'login_register.html', {
                'login_error': 'Usuario o contraseña incorrectos',
                'active_page': 'login',
                'next': next_url
            })
    
    # GET request - pasar el parámetro 'next' si existe
    next_url = request.GET.get('next', '')
    return render(request, 'login_register.html', {
        'active_page': 'login',
        'next': next_url
    })

def register_view(request):
    """Maneja el registro de nuevos usuarios"""
    import sys
    
    if request.method == 'POST':
        sys.stderr.write("\n=== REGISTER POST REQUEST ===\n")
        sys.stderr.flush()
        
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        next_url = request.POST.get('next', '')
        
        sys.stderr.write(f"Email: {email}, Nombre: {first_name}\n")
        sys.stderr.flush()
        
        # Validar campos vacíos
        if not all([email, first_name, last_name, nickname, password1, password2]):
            sys.stderr.write("ERROR: Campos vacíos\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'Todos los campos son obligatorios',
                'active_page': 'register',
                'next': next_url
            })
        
        # Si llegamos aquí, todos los campos están presentes
        sys.stderr.write("✓ Todos los campos presentes\n")
        sys.stderr.flush()
        
        # Validar email
        if '@' not in email:
            sys.stderr.write("ERROR: Email inválido\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'Email inválido',
                'active_page': 'register',
                'next': next_url
            })
        
        # Validaciones
        if password1 != password2:
            sys.stderr.write("ERROR: Contraseñas no coinciden\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'Las contraseñas no coinciden',
                'active_page': 'register',
                'next': next_url
            })
        
        if len(password1) < 8:
            sys.stderr.write("ERROR: Contraseña muy corta\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'La contraseña debe tener al menos 8 caracteres',
                'active_page': 'register',
                'next': next_url
            })
        
        # Usar email como username (es único en nuestro caso)
        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            sys.stderr.write("ERROR: Email ya registrado\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'Este email ya está registrado',
                'active_page': 'register',
                'next': next_url
            })
        
        # Validar que el nickname sea único
        from main.models import UserProfile
        if UserProfile.objects.filter(nickname=nickname).exists():
            sys.stderr.write("ERROR: Nickname ya está en uso\n")
            sys.stderr.flush()
            return render(request, 'login_register.html', {
                'register_error': 'Este nickname ya está en uso',
                'active_page': 'register',
                'next': next_url
            })
        
        try:
            sys.stderr.write("Creando usuario...\n")
            sys.stderr.flush()
            
            # Crear usuario con email como username
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password1
            )
            sys.stderr.write("✓ Usuario creado: " + str(user) + "\n")
            sys.stderr.flush()
            
            # Crear o actualizar UserProfile con el nickname
            from main.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.nickname = nickname
            profile.save()
            sys.stderr.write(f"✓ UserProfile {'creado' if created else 'actualizado'}: {profile}\n")
            sys.stderr.flush()
            
            # Login automático después del registro
            login(request, user)
            sys.stderr.write(f"✓ Usuario logueado: {request.user}\n")
            sys.stderr.flush()
            
            # Redirigir a selección de equipos favoritos
            sys.stderr.write("✓ Redirigiendo a select_favorite_teams\n")
            sys.stderr.flush()
            return redirect('select_favorite_teams')
            
        except Exception as e:
            sys.stderr.write(f"❌ EXCEPTION: {str(e)}\n")
            sys.stderr.write(f"Exception type: {type(e).__name__}\n")
            import traceback
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            
            return render(request, 'login_register.html', {
                'register_error': f'Error al crear la cuenta: {str(e)}',
                'active_page': 'register',
                'next': next_url
            })
    
    # GET request - pasar el parámetro 'next' si existe
    next_url = request.GET.get('next', '')
    return render(request, 'login_register.html', {
        'active_page': 'login',
        'next': next_url
    })

@login_required(login_url='login_register')
def select_favorite_teams(request):
    """Vista para seleccionar equipos favoritos después del registro"""
    equipos = Equipo.objects.all().order_by('nombre')
    equipos_favoritos = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
    
    context = {
        'active_page': 'favoritos',
        'equipos': equipos,
        'equipos_favoritos': equipos_favoritos
    }
    
    return render(request, 'select_favorite_teams.html', context)

@login_required(login_url='login_register')
@require_http_methods(["POST"])
def toggle_favorite_team(request):
    """Toggle un equipo como favorito para el usuario autenticado"""
    from django.http import JsonResponse
    
    team_id = request.POST.get('team_id')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if not team_id:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Team ID requerido'}, status=400)
        return redirect('equipos')
    
    try:
        equipo = Equipo.objects.get(id=team_id)
        from .models import EquipoFavorito
        
        # Check if already favorite
        favorito = EquipoFavorito.objects.filter(
            usuario=request.user,
            equipo=equipo
        ).first()
        
        is_favorite = False
        if favorito:
            # Remove from favorites
            favorito.delete()
        else:
            # Add to favorites
            EquipoFavorito.objects.create(
                usuario=request.user,
                equipo=equipo
            )
            is_favorite = True
        
        # Si es AJAX, devolver JSON
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'is_favorite': is_favorite
            })
            
    except Equipo.DoesNotExist:
        if is_ajax:
            return JsonResponse({
                'status': 'error',
                'message': 'Equipo no encontrado'
            }, status=404)
    
    # Si no es AJAX, redirect back to equipos page
    return redirect('equipos')

def logout_view(request):
    """Cierra sesión del usuario"""
    logout(request)
    return redirect('menu')

def terms_conditions(request):
    """Vista de términos y condiciones"""
    return render(request, 'terms_conditions.html', {'active_page': 'terms'})

@login_required(login_url='login_register')
def perfil_usuario(request):
    """Vista del perfil del usuario con datos personales, equipos favoritos, etc."""
    from .models import EquipoFavorito
    
    # Obtener equipos favoritos del usuario
    equipos_favoritos = EquipoFavorito.objects.filter(
        usuario=request.user
    ).select_related('equipo').order_by('-fecha_agregado')
    
    # Procesar nombres de escudos
    for fav in equipos_favoritos:
        fav.equipo_nombre_escudo = normalize_team_name_python(fav.equipo.nombre)
    
    context = {
        'active_page': 'perfil',
        'equipos_favoritos': equipos_favoritos,
    }
    
    return render(request, 'perfil_usuario.html', context)

@login_required(login_url='login_register')
@login_required(login_url='login_register')
def upload_profile_photo(request):
    """Subir foto de perfil o escudo"""
    if request.method == 'POST':
        from .models import UserProfile
        from django.http import JsonResponse
        from django.conf import settings
        
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        
        # Mapeo de equipos a nombres de archivo de escudo
        shield_map = {
            'Barcelona': 'barcelona.png',
            'Real Madrid': 'madrid.png',
            'Atlético Madrid': 'atletico_madrid.png',
            'Valencia': 'valencia.png',
            'Sevilla': 'sevilla.png',
        }
        
        # Si se envía un escudo de equipo
        if request.POST.get('shield_team'):
            shield_team = request.POST.get('shield_team')
            shield_filename = shield_map.get(shield_team)
            
            if not shield_filename:
                return JsonResponse({'status': 'error', 'message': 'Equipo no encontrado'}, status=400)
            
            try:
                from django.core.files.base import ContentFile
                import os
                
                # Construir ruta correcta desde BASE_DIR
                static_path = os.path.join(settings.BASE_DIR, 'static', 'escudos', shield_filename)
                
                print(f"Buscando escudo en: {static_path}")
                print(f"¿Existe? {os.path.exists(static_path)}")
                
                # Si el archivo existe, copiarlo a la carpeta de media
                if os.path.exists(static_path):
                    with open(static_path, 'rb') as f:
                        profile.foto.save(f'shield_{shield_team.lower().replace(" ", "_")}.png', ContentFile(f.read()), save=True)
                    
                    photo_url = profile.foto.url if profile.foto else ''
                    return JsonResponse({'status': 'success', 'photo_url': photo_url})
                else:
                    return JsonResponse({'status': 'error', 'message': f'Archivo no encontrado: {static_path}'}, status=400)
            except Exception as e:
                print(f"Error guardando escudo: {e}")
                import traceback
                traceback.print_exc()
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
        # Si se envía una foto subida
        elif request.FILES.get('foto'):
            try:
                profile.foto = request.FILES['foto']
                profile.save()
                photo_url = profile.foto.url
                return JsonResponse({'status': 'success', 'photo_url': photo_url})
            except Exception as e:
                print(f"Error guardando foto: {e}")
                import traceback
                traceback.print_exc()
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
        # Si se envía un avatar por defecto
        elif request.POST.get('default_avatar'):
            default_avatar = request.POST.get('default_avatar')
            avatar_filename = f'{default_avatar}.png'
            
            try:
                from django.core.files.base import ContentFile
                import os
                
                # Intentar desde carpeta 'logos'
                static_path = os.path.join(settings.BASE_DIR, 'static', 'logos', avatar_filename)
                
                # Si no existe, intentar desde carpeta 'escudos'
                if not os.path.exists(static_path):
                    static_path = os.path.join(settings.BASE_DIR, 'static', 'escudos', avatar_filename)
                
                print(f"Buscando avatar en: {static_path}")
                print(f"¿Existe? {os.path.exists(static_path)}")
                
                # Si el archivo existe, copiarlo a la carpeta de media
                if os.path.exists(static_path):
                    with open(static_path, 'rb') as f:
                        profile.foto.save(f'{default_avatar}.png', ContentFile(f.read()), save=True)
                    
                    photo_url = profile.foto.url if profile.foto else ''
                    return JsonResponse({'status': 'success', 'photo_url': photo_url})
                else:
                    return JsonResponse({'status': 'error', 'message': f'Archivo no encontrado: {static_path}'}, status=400)
            except Exception as e:
                print(f"Error guardando avatar: {e}")
                import traceback
                traceback.print_exc()
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
        return JsonResponse({'status': 'error', 'message': 'No se proporcionó foto'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required(login_url='login_register')
def update_profile(request):
    """Actualizar datos del perfil"""
    if request.method == 'POST':
        from main.models import UserProfile
        
        user = request.user
        new_email = request.POST.get('email', user.email).strip()
        new_nickname = request.POST.get('nickname', user.profile.nickname).strip()
        
        # Validar que el email sea único (excepto si es el mismo del usuario)
        if new_email != user.email and User.objects.filter(email=new_email).exists():
            return render(request, 'perfil_usuario.html', {
                'equipos_favoritos': user.profile.equipos_favoritos.all(),
                'edit_error': 'Este email ya está registrado',
            })
        
        # Validar que el nickname sea único (excepto si es el mismo del usuario)
        if new_nickname != user.profile.nickname and UserProfile.objects.filter(nickname=new_nickname).exists():
            return render(request, 'perfil_usuario.html', {
                'equipos_favoritos': user.profile.equipos_favoritos.all(),
                'edit_error': 'Este nickname ya está en uso',
            })
        
        # Si todas las validaciones pasan, actualizar
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = new_email
        user.save()
        
        profile = user.profile
        profile.nickname = new_nickname
        profile.save()
        
        return redirect('perfil')
    return redirect('perfil')

@login_required(login_url='login_register')
def update_user_status(request):
    """Actualizar estado del usuario"""
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['active', 'away', 'dnd']:
            request.user.profile.estado = nuevo_estado
            request.user.profile.save()
        return redirect('perfil')
    return redirect('perfil')

@login_required(login_url='login_register')
def delete_favorite_team(request, fav_id):
    """Eliminar equipo favorito"""
    from .models import EquipoFavorito
    try:
        fav = EquipoFavorito.objects.get(id=fav_id, usuario=request.user)
        fav.delete()
    except EquipoFavorito.DoesNotExist:
        pass
    return redirect('perfil')


@require_http_methods(["POST"])
def predecir_portero_api(request):
    """
    API para predecir puntos fantasy de un portero para la siguiente jornada.
    
    Recibe JSON:
    {
        "jugador_id": 123 (ID de Jugador en BD),
        "jornada": 15 (opcional),
        "modelo": "RF" (opcional, default: 'RF')
    }
    
    Retorna JSON:
    {
        "status": "success" o "error",
        "jugador_id": id,
        "prediccion": float,
        "jornada": int,
        "modelo": str,
        "confianza": float,
        "error": "descripción si hay error"
    }
    """
    import json
    import sys
    import logging
    from pathlib import Path
    from main.models import Jugador
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parsear JSON del request
        body_data = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
        logger.info(f"[API] Body recibido: {body_data}")
        
        data = json.loads(body_data)
        jugador_id = data.get('jugador_id')
        jornada = data.get('jornada', None)
        modelo_tipo = data.get('modelo', 'RF')  # Aceptar modelo del request, default RF
        
        logger.info(f"[API] Pidiendo predicción para jugador_id {jugador_id}, jornada {jornada}")
        
        if not jugador_id:
            logger.error("[API] jugador_id requerido pero no proporcionado")
            return JsonResponse({
                'status': 'error',
                'error': 'jugador_id es requerido'
            }, status=400)
        
        # Obtener jugador de BD (para convertir ID a nombre)
        try:
            jugador = Jugador.objects.get(id=jugador_id)
            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
            logger.info(f"[API] Jugador en BD: {nombre_jugador}")
        except Jugador.DoesNotExist:
            logger.error(f"[API] Jugador no encontrado en BD: {jugador_id}")
            return JsonResponse({
                'status': 'error',
                'error': f'Jugador con ID {jugador_id} no encontrado'
            }, status=404)
        
        # Agregar path para imports
        entrenamientos_path = Path(__file__).parent / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))
        
        # Importar función de predicción
        logger.info(f"[API] Importando módulo desde: {entrenamientos_path}")
        from predecir_portero import predecir_puntos_portero
        
        # Llamar función de predicción usando NOMBRE (no ID)
        logger.info(f"[API] Llamando predecir_puntos_portero('{nombre_jugador}', jornada={jornada}, modelo={modelo_tipo})")
        resultado = predecir_puntos_portero(nombre_jugador, jornada, verbose=False, modelo_tipo=modelo_tipo)
        
        logger.info(f"[API] Resultado: {resultado}")
        
        # Validar resultado
        if not isinstance(resultado, dict):
            logger.error(f"[API] Resultado no es dict: {type(resultado)}")
            return JsonResponse({
                'status': 'error',
                'error': f'Resultado inválido: {resultado}'
            }, status=500)
        
        # Formatear respuesta
        if resultado.get('error'):
            logger.warning(f"[API] Error en predicción: {resultado.get('error')}")
            return JsonResponse({
                'status': 'error',
                'error': resultado['error'],
                'jugador_id': jugador_id
            }, status=400)
        else:
            logger.info(f"[API] Predicción exitosa: {resultado.get('prediccion')} pts")
            
            # Preparar predicción para JSON
            prediccion = resultado.get('prediccion')
            prediccion_json = float(prediccion) if prediccion is not None else None
            
            return JsonResponse({
                'status': 'success',
                'jugador_id': jugador_id,
                'jugador_nombre': nombre_jugador,
                'prediccion': prediccion_json,
                'puntos_reales': float(resultado['puntos_reales']) if resultado['puntos_reales'] is not None else None,
                'puntos_reales_texto': resultado.get('puntos_reales_texto', 'Aún no jugado'),
                'margen': float(resultado.get('margen', 0)),
                'rango_min': float(resultado.get('rango_min')) if resultado.get('rango_min') is not None else None,
                'rango_max': float(resultado.get('rango_max')) if resultado.get('rango_max') is not None else None,
                'jornada': int(resultado['jornada']),
                'modelo': resultado.get('modelo', 'Random Forest')
            })
    
    except json.JSONDecodeError as e:
        logger.error(f"[API] Error parseando JSON: {e}")
        return JsonResponse({
            'status': 'error',
            'error': f'JSON inválido: {str(e)}'
        }, status=400)
    
    except ImportError as e:
        logger.error(f"[API] Error importando módulo: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': f'Error de módulo: {str(e)}'
        }, status=500)
    
    except Exception as e:
        import traceback
        logger.error(f"[API] Error inesperado: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=500)


@csrf_exempt
def cambiar_jornada_api(request):
    """
    API para cambiar de jornada dinámicamente y obtener nuevos datos de jugadores.
    
    Recibe JSON:
    {
        "jornada": 15
    }
    
    Retorna JSON:
    {
        "status": "success" o "error",
        "jugadores_por_posicion": { ... },
        "jornada": int
    }
    """
    import json
    from main.models import Jugador, EquipoJugadorTemporada, Temporada, Equipo, EstadisticasPartidoJugador, Partido, Jornada
    from django.db.models import Sum
    
    try:
        # Parsear JSON
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
        nueva_jornada = data.get('jornada')
        
        if not nueva_jornada or not isinstance(nueva_jornada, int):
            return JsonResponse({
                'status': 'error',
                'error': 'jornada debe ser un entero'
            }, status=400)
        
        # Obtener temporada actual
        temporada_actual = Temporada.objects.last()
        if not temporada_actual:
            return JsonResponse({
                'status': 'error',
                'error': 'No hay temporada disponible'
            }, status=404)
        
        # Validar que la jornada existe
        jornada_actual = Jornada.objects.filter(
            temporada=temporada_actual,
            numero_jornada=nueva_jornada
        ).first()
        
        if not jornada_actual:
            return JsonResponse({
                'status': 'error',
                'error': f'Jornada {nueva_jornada} no existe'
            }, status=404)
        
        # Obtener partidos de la nueva jornada
        partidos_por_jornada = {}
        partidos_jornada = Partido.objects.filter(
            jornada=jornada_actual
        ).select_related('equipo_local', 'equipo_visitante')
        
        print(f"[API] Jornada {nueva_jornada}: {partidos_jornada.count()} partidos encontrados en tabla Partido")
        
        for partido in partidos_jornada:
            partidos_por_jornada[partido.equipo_local.id] = {
                'rival_id': partido.equipo_visitante.id,
                'rival_nombre': partido.equipo_visitante.nombre,
                'es_local': True
            }
            partidos_por_jornada[partido.equipo_visitante.id] = {
                'rival_id': partido.equipo_local.id,
                'rival_nombre': partido.equipo_local.nombre,
                'es_local': False
            }
        
        # Si no hay partidos en tabla Partido, intentar obtener de Calendario
        if len(partidos_por_jornada) == 0:
            print(f"[API] Fallback: Buscando en tabla Calendario para jornada {nueva_jornada}")
            from main.models import Calendario
            
            calendarios = Calendario.objects.filter(
                jornada=jornada_actual
            ).select_related('equipo_local', 'equipo_visitante')
            
            print(f"[API] Calendario: {calendarios.count()} registros encontrados")
            
            for cal in calendarios:
                equipo_local = cal.equipo_local
                equipo_visitante = cal.equipo_visitante
                
                partidos_por_jornada[equipo_local.id] = {
                    'rival_id': equipo_visitante.id,
                    'rival_nombre': equipo_visitante.nombre,
                    'es_local': True
                }
                partidos_por_jornada[equipo_visitante.id] = {
                    'rival_id': equipo_local.id,
                    'rival_nombre': equipo_local.nombre,
                    'es_local': False
                }
                print(f"[API] Partido añadido: {equipo_local.nombre} vs {equipo_visitante.nombre}")
        
        print(f"[API] Total: {len(partidos_por_jornada)} equipos con rival asignado")
        
        # Obtener jugadores actualizados de la temporada
        jugadores_temporada = EquipoJugadorTemporada.objects.filter(
            temporada=temporada_actual
        ).select_related('jugador', 'equipo').order_by('jugador__nombre')
        
        jugadores_por_posicion = {
            'Portero': [],
            'Defensa': [],
            'Centrocampista': [],
            'Delantero': []
        }
        
        for ejecucion_temporada in jugadores_temporada:
            posicion = ejecucion_temporada.posicion or 'Delantero'
            jugador = ejecucion_temporada.jugador
            
            stats_puntos = EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada=temporada_actual,
                jugador=jugador,
                puntos_fantasy__lte=50
            ).aggregate(total_puntos=Sum('puntos_fantasy'))
            
            puntos_fantasy = stats_puntos['total_puntos'] or 0
            
            # Obtener rival de la NUEVA jornada
            rival_jornada = partidos_por_jornada.get(ejecucion_temporada.equipo.id)
            
            if posicion in jugadores_por_posicion:
                jugadores_por_posicion[posicion].append({
                    'id': jugador.id,
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'posicion': posicion,
                    'equipo_id': ejecucion_temporada.equipo.id,
                    'equipo_nombre': ejecucion_temporada.equipo.nombre,
                    'puntos_fantasy_25_26': puntos_fantasy,
                    'proximo_rival_id': rival_jornada['rival_id'] if rival_jornada else None,
                    'proximo_rival_nombre': rival_jornada['rival_nombre'] if rival_jornada else None
                })
        
        return JsonResponse({
            'status': 'success',
            'jornada': nueva_jornada,
            'jugadores_por_posicion': jugadores_por_posicion
        })
    
    except Exception as e:
        import traceback
        print(f"[API] Error en cambiar_jornada: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)



@csrf_exempt
def explicar_prediccion_portero_api(request):
    """
    API para obtener explicabilidad (XAI) de predicciones de porteros usando SHAP.
    
    Recibe JSON:
    {
        "jugador_id": 123 (ID de Jugador en BD),
        "jornada": 15 (opcional),
        "modelo": "RF" (opcional, default: 'RF')
    }
    
    Retorna JSON:
    {
        "status": "success" o "error",
        "prediccion": float,
        "features_impacto": [
            {"feature": str, "impacto": float, "valor": float, "direccion": str},
            ...
        ],
        "explicacion_texto": str,
        "error": str (si hay error)
    }
    """
    import json
    import sys
    import logging
    from pathlib import Path
    from main.models import Jugador
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parsear JSON del request
        body_data = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
        data = json.loads(body_data)
        jugador_id = data.get('jugador_id')
        jornada = data.get('jornada', None)
        modelo_tipo = data.get('modelo', 'RF')  # Aceptar modelo del request, default RF
        
        logger.info(f"[XAI API] Pidiendo explicación para jugador_id {jugador_id}, jornada {jornada}, modelo {modelo_tipo}")
        
        if not jugador_id:
            return JsonResponse({
                'status': 'error',
                'error': 'jugador_id es requerido'
            }, status=400)
        
        # Obtener jugador de BD (para convertir ID a nombre)
        try:
            jugador = Jugador.objects.get(id=jugador_id)
            nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        except Jugador.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'error': f'Jugador con ID {jugador_id} no encontrado'
            }, status=404)
        
        # Agregar path para imports
        entrenamientos_path = Path(__file__).parent / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))
        
        # Importar función de explicación
        from predecir_portero import explicar_prediccion_portero
        
        # Llamar función de explicación usando NOMBRE
        logger.info(f"[XAI API] Llamando explicar_prediccion_portero('{nombre_jugador}', jornada={jornada}, modelo={modelo_tipo})")
        resultado = explicar_prediccion_portero(nombre_jugador, jornada, modelo_tipo=modelo_tipo)
        
        logger.info(f"[XAI API] Resultado: {resultado}")
        
        # Validar resultado
        if resultado.get('error'):
            logger.warning(f"[XAI API] Error en explicación: {resultado.get('error')}")
            return JsonResponse({
                'status': 'error',
                'error': resultado['error'],
                'jugador_id': jugador_id
            }, status=400)
        else:
            logger.info(f"[XAI API] Explicación exitosa para predicción: {resultado.get('prediccion')} pts")
            
            # Preparar predicción para JSON (puede ser None)
            prediccion = resultado.get('prediccion')
            prediccion_json = float(prediccion) if prediccion is not None else None
            
            return JsonResponse({
                'status': 'success',
                'jugador_id': jugador_id,
                'jugador_nombre': nombre_jugador,
                'prediccion': prediccion_json,
                'puntos_reales': float(resultado['puntos_reales']) if resultado.get('puntos_reales') is not None else None,
                'puntos_reales_texto': resultado.get('puntos_reales_texto', 'Aún no jugado'),
                'margen': float(resultado.get('margen', 0)),
                'mae_value': float(resultado.get('mae_value', 3.22)),
                'std_value': float(resultado.get('std_value', 2.5)),
                'rango_min': float(resultado.get('rango_min')) if resultado.get('rango_min') is not None else None,
                'rango_max': float(resultado.get('rango_max')) if resultado.get('rango_max') is not None else None,
                'jornada': int(resultado.get('jornada', jornada)),
                'features_impacto': resultado.get('explicaciones', resultado.get('features_impacto', [])),
                'explicacion_texto': resultado.get('explicacion_texto', ''),
                'error': None
            })
    
    except json.JSONDecodeError as e:
        logger.error(f"[XAI API] Error parseando JSON: {e}")
        return JsonResponse({
            'status': 'error',
            'error': f'JSON inválido: {str(e)}'
        }, status=400)
    
    except ImportError as e:
        logger.error(f"[XAI API] Error importando módulo: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': f'Error de módulo: {str(e)}'
        }, status=500)
    
    except Exception as e:
        logger.error(f"[XAI API] Error general: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def predecir_jugador_api(request):
    """
    API para obtener PREDICCIÓN o MEDIA de puntos fantasy.
    
    Recibe JSON:
    {
        "jugador_id": 123,
        "jornada": 15,
        "posicion": "Delantero" (opcional),
        "modelo": "RF" (opcional, default: 'RF')
    }
    
    Lógica:
    1. Intenta obtener predicción existente de BD (PrediccionJugador)
    2. Si no existe:
       - Jornadas 1-5 (sin datos): devuelve media histórica con type='media'
       - Jornadas > 5: devuelve error (debería haber predicción)
    """
    import json
    import logging
    from main.models import Jugador, PrediccionJugador, Jornada, Temporada, RendimientoHistoricoJugador
    from django.db.models import Avg
    
    logger = logging.getLogger(__name__)
    
    try:
        body_data = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
        data = json.loads(body_data)
        
        jugador_id = data.get('jugador_id')
        jornada_num = data.get('jornada')
        posicion_param = data.get('posicion')
        modelo_tipo = data.get('modelo', 'RF')
        
        if not jugador_id or not jornada_num:
            return JsonResponse({
                'status': 'error',
                'error': 'Se requieren jugador_id y jornada'
            }, status=400)
        
        # Obtener jugador
        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'error': 'Jugador no encontrado'
            }, status=404)
        
        # Obtener temporada actual
        temporada_actual = Temporada.objects.last()
        if not temporada_actual:
            return JsonResponse({
                'status': 'error',
                'error': 'Temporada no encontrada'
            }, status=500)
        
        # Obtener jornada (de la temporada actual)
        try:
            jornada = Jornada.objects.filter(
                numero_jornada=jornada_num,
                temporada=temporada_actual
            ).first()
            if not jornada:
                return JsonResponse({
                    'status': 'error',
                    'error': f'Jornada {jornada_num} no encontrada en la temporada actual'
                }, status=404)
        except Exception as e:
            logger.error(f"Error obteniendo jornada: {e}")
            return JsonResponse({'status': 'error', 'error': 'Error obteniendo jornada'}, status=500)
        
        nombre_jugador = f"{jugador.nombre} {jugador.apellido}".strip()
        
        # ── OPCIÓN 1: Buscar predicción en BD ──────────────────────────────────
        prediccion_obj = PrediccionJugador.objects.filter(
            jugador=jugador,
            jornada=jornada,
            modelo=modelo_tipo.lower()
        ).first()
        
        if prediccion_obj:
            # ✓ Predicción encontrada en BD
            return JsonResponse({
                'status': 'success',
                'type': 'prediccion',  # Indica que es una predicción real
                'jugador_id': jugador_id,
                'jugador_nombre': nombre_jugador,
                'prediccion': round(float(prediccion_obj.prediccion), 2),
                'jornada': jornada_num,
                'posicion': posicion_param or jugador.get_posicion_mas_frecuente() or 'Desconocida',
                'modelo': modelo_tipo,
                'fuente': 'prediccion_bd'
            })
        
        # ── OPCIÓN 2: Para jornadas 1-5, devolver MEDIA HISTÓRICA ───────────────
        if jornada_num <= 5:
            # Obtener media histórica del jugador
            media_puntos = (
                jugador.estadisticas_partidos
                .aggregate(media=Avg('puntos_fantasy'))['media'] or 0.0
            )
            
            return JsonResponse({
                'status': 'success',
                'type': 'media',  # Indica que es una media, NO una predicción
                'jugador_id': jugador_id,
                'jugador_nombre': nombre_jugador,
                'prediccion': round(float(media_puntos), 2),
                'jornada': jornada_num,
                'posicion': posicion_param or jugador.get_posicion_mas_frecuente() or 'Desconocida',
                'modelo': 'Media Histórica',
                'fuente': 'media_historica',
                'aviso': f'Jornada {jornada_num}: Sin datos suficientes para predicción. Mostrando media histórica.'
            })
        
        # ── OPCIÓN 3: Jornada > 5 sin predicción → Error ──────────────────────
        return JsonResponse({
            'status': 'error',
            'error': f'No hay predicción para jornada {jornada_num} y es demasiado tarde para media',
            'jugador_id': jugador_id,
            'jornada': jornada_num
        }, status=404)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error en predecir_jugador_api: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
