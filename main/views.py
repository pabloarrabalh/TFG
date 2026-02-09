from django.shortcuts import render
from .models import (Temporada, Jornada, ClasificacionJornada, Equipo, HistorialEquiposJugador, 
                     EquipoJugadorTemporada, Partido, EstadisticasPartidoJugador, Jugador, Calendario)
from django.db.models import Sum, Count, F, Case, When, FloatField, Q
from datetime import datetime, time
import unicodedata

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
    return render(request, 'menu.html', {'active_page': 'menu'})

def mi_plantilla(request):
    """Vista de Mi Plantilla"""
    return render(request, 'mi_plantilla.html', {'active_page': 'mi-plantilla'})

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
            resultado = 'L'
            titulo = f"Derrota vs {rival} {goles_propios}-{goles_rival}"
        else:
            resultado = 'D'
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
                es_local = stat.jugador.historial_equipos.filter(
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
            
            # Calcular totales
            total_puntos = stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
            partidos_jugados = stats.count()
            total_minutos = stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0
            
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
                
                if clasificacion_rival:
                    goles_rival_favor = clasificacion_rival.goles_favor
                    goles_rival_contra = clasificacion_rival.goles_contra
                    if clasificacion_rival.racha_reciente:
                        # Convertir racha de W/D/L a V/E/P (español)
                        racha_raw = list(clasificacion_rival.racha_reciente)
                        racha_rival = []
                        for resultado in racha_raw:
                            if resultado == 'W':
                                racha_rival.append('V')  # Victoria
                            elif resultado == 'D':
                                racha_rival.append('E')  # Empate
                            elif resultado == 'L':
                                racha_rival.append('P')  # Pérdida
                            else:
                                racha_rival.append(resultado)
                    
                    rival_info = {
                        'nombre': rival.nombre,
                        'iniciales': ''.join([palabra[0].upper() for palabra in rival.nombre.split()]),
                        'nombre_normalizado': normalize_team_name_python(rival.nombre),
                        'es_local': es_local,
                        'estadio_rival': rival.estadio or 'Estadio desconocido',
                        'estadio_partido': estadio_partido,
                        'racha': racha_rival,
                        'goles_favor': goles_rival_favor,
                        'goles_contra': goles_rival_contra
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
    if equipo:
        palabras = equipo.nombre.split()
        iniciales = ''.join([palabra[0].upper() for palabra in palabras])
    
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
        'desde_clasificacion': equipo_nombre is not None
    }
    
    return render(request, 'equipo.html', context)

def jugador(request, jugador_id=None, temporada=None):
    """Vista de estadísticas de jugador"""
    # Por ahora, redirigir a template placeholder
    # Cuando definas el contenido exacto, actualiza esta vista
    return render(request, 'jugador.html', {
        'active_page': 'estadisticas',
        'jugador_id': jugador_id,
        'temporada': temporada
    })

def amigos(request):
    """Vista de amigos y comparaciones"""
    return render(request, 'amigos.html', {'active_page': 'amigos'})

def login_register(request):
    """Vista de login y registro"""
    return render(request, 'login_register.html', {'active_page': 'login'})
