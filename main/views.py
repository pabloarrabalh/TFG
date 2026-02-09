from django.shortcuts import render
from .models import (Temporada, Jornada, ClasificacionJornada, Equipo, HistorialEquiposJugador, 
                     EquipoJugadorTemporada, Partido, EstadisticasPartidoJugador, Jugador)
from django.db.models import Sum, Count, F, Case, When, FloatField, Q

def menu(request):
    """Vista principal del menú"""
    return render(request, 'menu.html', {'active_page': 'menu'})

def mi_plantilla(request):
    """Vista de Mi Plantilla"""
    return render(request, 'mi_plantilla.html', {'active_page': 'mi-plantilla'})

def clasificacion(request):
    """Vista de Clasificación de la liga con filtros por temporada y jornada"""
    # Obtener parámetros del GET
    temporada_display = request.GET.get('temporada', '25/26')
    jornada_num = request.GET.get('jornada', '1')
    
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
    
    # Obtener jornadas disponibles para la temporada
    jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    
    # Obtener la clasificación para la temporada y jornada
    clasificacion_datos = []
    jornada_obj = None
    if jornadas.exists():
        try:
            jornada_obj = jornadas.get(numero_jornada=int(jornada_num))
        except (Jornada.DoesNotExist, ValueError):
            jornada_obj = jornadas.first()
            jornada_num = jornada_obj.numero_jornada if jornada_obj else 1
        
        if jornada_obj:
            clasificacion_datos = ClasificacionJornada.objects.filter(
                temporada=temporada,
                jornada=jornada_obj
            ).order_by('posicion', 'equipo__nombre').select_related('equipo')
            
            # Agregar iniciales a cada registro para el template
            for reg in clasificacion_datos:
                palabras = reg.equipo.nombre.split()
                reg.iniciales = ''.join([palabra[0].upper() for palabra in palabras])
    
    context = {
        'active_page': 'liga',
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_display,
        'temporada_nombre': temporada_nombre,
        'jornadas': jornadas,
        'jornada_actual': int(jornada_num) if jornadas.exists() else 1,
        'clasificacion': clasificacion_datos,
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
    
    try:
        equipo = Equipo.objects.get(nombre=equipo_display_nombre)
        
        # Obtener la temporada
        try:
            temp_obj = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temp_obj = temporadas.first()
            temporada_nombre = temp_obj.nombre if temp_obj else '24_25'
            temporada_display = temporada_nombre.replace('_', '/')
        
        # Obtener plantilla del equipo SOLO para la temporada seleccionada
        # Agrupar por jugador para consolidar dorsal 0 (suplentes) con el mismo jugador
        jugadores_equipo_temp = EquipoJugadorTemporada.objects.filter(
            equipo=equipo,
            temporada=temp_obj
        ).select_related('jugador').order_by('dorsal')
        
        # Diccionario para agrupar por jugador
        jugadores_agrupados = {}
        puntos_dorsal_cero = {}  # Guardar puntos negativos de dorsal 0 para restar después
        
        # Calcular estadísticas de Fantasy para cada jugador EN ESA TEMPORADA
        for eq_jug_temp in jugadores_equipo_temp:
            # Obtener estadísticas del jugador SOLO en esta temporada
            stats = EstadisticasPartidoJugador.objects.filter(
                jugador=eq_jug_temp.jugador,
                partido__jornada__temporada=temp_obj
            )
            
            # Calcular totales
            total_puntos = stats.aggregate(Sum('puntos_fantasy'))['puntos_fantasy__sum'] or 0
            partidos_jugados = stats.count()
            
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
            
            # Calcular promedio
            promedio_puntos = total_puntos / partidos_jugados if partidos_jugados > 0 else 0
            
            # Añadir atributos al objeto
            eq_jug_temp.total_puntos_fantasy = total_puntos
            eq_jug_temp.partidos_stats = partidos_jugados
            eq_jug_temp.promedio_puntos_fantasy = round(promedio_puntos, 2)
            eq_jug_temp.posicion = datos['posicion']
            
            jugadores.append(eq_jug_temp)
    
    except Equipo.DoesNotExist:
        equipo = None
        jugadores = []
    
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
        'temporadas_display': temporadas_display,
        'temporada_actual': temporada_display,  # Formato visual: 25/26
        'temporada_actual_url': temporada_nombre,  # Formato URL: 25_26
        'temporada_actual_db': temporada_nombre,  # Formato con guion (23_24) para URLs
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
