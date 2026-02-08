#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SCRIPT UNIFICADO COMPLETO DE CARGA DE DATOS

Carga todos los datos en un único script:
1. Crea Temporadas, Equipos, Jornadas
2. Carga EstadisticasPartidoJugador desde CSVs (45 campos)
3. Carga Roles con fuzzy matching
4. Calcula y carga Goles en Partidos
5. Carga ClasificacionJornada desde CSVs
6. Genera RendimientoHistoricoJugador por agregación

Uso: python cargarTodoUnificado.py
"""

import os
import sys
import django
import pandas as pd
import json
import glob
import ast
from datetime import datetime

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import (
    Temporada, Equipo, EquipoTemporada, Jugador,
    HistorialEquiposJugador, Jornada, Partido, EstadisticasPartidoJugador,
    ClasificacionJornada, RendimientoHistoricoJugador, EquipoJugadorTemporada
)
from django.db.models import Sum, Count, Q

# Intentar importar rapidfuzz para fuzzy matching
try:
    from rapidfuzz import process as rf_process, fuzz as rf_fuzz
    RAPIDFUZZ_DISPONIBLE = True
except ImportError:
    RAPIDFUZZ_DISPONIBLE = False

# Mapeo de posiciones CSV -> DB
MAPEO_POSICIONES = {
    'PT': 'Portero',
    'DF': 'Defensa',
    'MC': 'Centrocampista',
    'DT': 'Delantero',
}

# Alias de equipos (normalización)
EQUIPOS_ALIAS = {
    'rayo vallecano': 'Rayo Vallecano', 'rayo': 'Rayo Vallecano',
    'sevilla': 'Sevilla', 'sevilla fc': 'Sevilla',
    'valencia': 'Valencia', 'valencia cf': 'Valencia',
    'real sociedad': 'Real Sociedad', 
    'girona': 'Girona', 'girona fc': 'Girona',
    'villarreal': 'Villarreal', 
    'real betis': 'Real Betis', 'betis': 'Real Betis',
    'athletic': 'Athletic Club', 'athletic club': 'Athletic Club',
    'barcelona': 'Barcelona', 'fc barcelona': 'Barcelona', 
    'real madrid': 'Real Madrid',
    'getafe': 'Getafe', 'getafe cf': 'Getafe',
    'celta vigo': 'Celta Vigo', 'celta': 'Celta Vigo', 'rc celta': 'Celta Vigo',
    'alaves': 'Alavés', 'alavés': 'Alavés', 
    'osasuna': 'Osasuna', 'ca osasuna': 'Osasuna',
    'levante': 'Levante',
    'mallorca': 'Real Mallorca', 'real mallorca': 'Real Mallorca', 'rcd mallorca': 'Real Mallorca',
    'las palmas': 'Las Palmas', 'ud las palmas': 'Las Palmas',
    'cadiz': 'Cádiz', 'cádiz': 'Cádiz', 'cadiz cf': 'Cádiz',
    'oviedo': 'Real Oviedo', 'real oviedo': 'Real Oviedo',
    'elche': 'Elche', 
    'almeria': 'Almería', 'almería': 'Almería', 'ud almeria': 'Almería',
    'granada': 'Granada', 'granada cf': 'Granada',
    'atletico madrid': 'Atlético Madrid', 'atletico': 'Atlético Madrid',
    'espanyol': 'RCD Espanyol', 'rcd espanyol': 'RCD Espanyol',
    'leganes': 'Leganés', 'leganés': 'Leganés', 'cd leganes': 'Leganés',
    'valladolid': 'Real Valladolid', 'real valladolid': 'Real Valladolid',
}

def normalizar_equipo(nombre):
    """Normaliza el nombre del equipo."""
    nombre_norm = nombre.lower().strip()
    return EQUIPOS_ALIAS.get(nombre_norm, nombre)

def normalizar_nombre(nombre):
    """Normaliza un nombre para matching."""
    return nombre.lower().strip()

def parsear_roles(roles_str):
    """Parsea roles del CSV (JSON array o Python literal)."""
    if pd.isna(roles_str) or roles_str is None:
        return []
    
    roles_str = str(roles_str).strip()
    if roles_str in ('[]', '', 'nan', 'NaN'):
        return []
    
    # Intento 1: JSON
    try:
        roles = json.loads(roles_str)
        return roles if isinstance(roles, list) else []
    except:
        pass
    
    # Intento 2: Python literal
    try:
        roles = ast.literal_eval(roles_str)
        return roles if isinstance(roles, list) else []
    except:
        return []

def parsear_fecha(fecha_str):
    """Parsea fecha en formato dd/mm/yyyy."""
    if pd.isna(fecha_str) or not fecha_str:
        return datetime.now()
    try:
        return datetime.strptime(str(fecha_str).strip(), '%d/%m/%Y')
    except:
        return datetime.now()

def obtener_o_crear_temporada(codigo):
    """Obtiene o crea una Temporada."""
    temporada, created = Temporada.objects.get_or_create(nombre=codigo)
    return temporada

def obtener_o_crear_equipo(nombre_csv):
    """Obtiene o crea un Equipo."""
    nombre_normalizado = normalizar_equipo(nombre_csv)
    equipo, created = Equipo.objects.get_or_create(
        nombre=nombre_normalizado,
        defaults={'estadio': ''}
    )
    return equipo

def obtener_o_crear_equipo_temporada(equipo, temporada):
    """Obtiene o crea EquipoTemporada."""
    eq_temp, created = EquipoTemporada.objects.get_or_create(
        equipo=equipo, temporada=temporada
    )
    return eq_temp

def obtener_o_crear_jornada(temporada, numero_jornada):
    """Obtiene o crea una Jornada."""
    jornada, created = Jornada.objects.get_or_create(
        temporada=temporada,
        numero_jornada=numero_jornada,
        defaults={'fecha_inicio': None, 'fecha_fin': None}
    )
    return jornada

def obtener_o_crear_jugador(nombre_completo, posicion_csv):
    """Obtiene o crea un Jugador."""
    partes = nombre_completo.strip().split()
    if len(partes) >= 2:
        nombre = ' '.join(partes[:-1])
        apellido = partes[-1]
    else:
        nombre = nombre_completo
        apellido = ''
    
    posicion_db = MAPEO_POSICIONES.get(posicion_csv, 'Centrocampista')
    
    jugador, created = Jugador.objects.get_or_create(
        nombre=nombre,
        apellido=apellido,
        defaults={'posicion': posicion_db, 'nacionalidad': ''}
    )
    return jugador

def obtener_o_crear_historial(jugador, equipo, temporada, dorsal):
    """Obtiene o crea HistorialEquiposJugador y actualiza el dorsal."""
    # Limpiar dorsal: convertir a int, aceptar 0-99
    dorsal_limpio = 0  # Por defecto suplente/banquillo
    if pd.notna(dorsal):
        try:
            dorsal_int = int(dorsal)
            if 0 <= dorsal_int <= 99:
                dorsal_limpio = dorsal_int
        except (ValueError, TypeError):
            pass
    
    historial, created = HistorialEquiposJugador.objects.get_or_create(
        jugador=jugador,
        equipo=equipo,
        temporada=temporada,
        defaults={
            'dorsal': dorsal_limpio,
            'edad': 25
        }
    )
    
    # Actualizar dorsal si ya existía y es diferente
    if not created and historial.dorsal != dorsal_limpio:
        historial.dorsal = dorsal_limpio
        historial.save(update_fields=['dorsal'])
    
    return historial

def obtener_o_crear_partido(jornada, equipo_local, equipo_visitante, fecha_partido):
    """Obtiene o crea un Partido."""
    partido, created = Partido.objects.get_or_create(
        jornada=jornada,
        equipo_local=equipo_local,
        equipo_visitante=equipo_visitante,
        defaults={'fecha_partido': fecha_partido, 'estado': 'JUGADO'}
    )
    return partido

def cargar_estadisticas_partido(row, jugador, equipo, partido):
    """Crea EstadisticasPartidoJugador desde una fila del CSV."""
    stats = EstadisticasPartidoJugador(
        partido=partido, jugador=jugador,
        min_partido=int(row['min_partido']) if pd.notna(row['min_partido']) else 0,
        titular=bool(row['titular']) if pd.notna(row['titular']) else False,
        gol_partido=int(row['gol_partido']) if pd.notna(row['gol_partido']) else 0,
        asist_partido=int(row['asist_partido']) if pd.notna(row['asist_partido']) else 0,
        xg_partido=float(row['xg_partido']) if pd.notna(row['xg_partido']) else 0.0,
        xag=float(row['xag']) if pd.notna(row['xag']) else 0.0,
        tiros=int(row['tiros']) if pd.notna(row['tiros']) else 0,
        tiro_fallado_partido=int(row['tiro_fallado_partido']) if pd.notna(row['tiro_fallado_partido']) else 0,
        tiro_puerta_partido=int(row['tiro_puerta_partido']) if pd.notna(row['tiro_puerta_partido']) else 0,
        pases_totales=int(row['pases_totales']) if pd.notna(row['pases_totales']) else 0,
        pases_completados_pct=float(row['pases_completados_pct']) if pd.notna(row['pases_completados_pct']) else 0.0,
        amarillas=int(row['amarillas']) if pd.notna(row['amarillas']) else 0,
        rojas=int(row['rojas']) if pd.notna(row['rojas']) else 0,
        goles_en_contra=int(row['goles_en_contra']) if pd.notna(row['goles_en_contra']) else 0,
        porcentaje_paradas=float(row['porcentaje_paradas']) if pd.notna(row['porcentaje_paradas']) else 0.0,
        psxg=float(row['psxg']) if pd.notna(row['psxg']) else 0.0,
        puntos_fantasy=int(row['puntos_fantasy']) if pd.notna(row['puntos_fantasy']) else 0,
        entradas=int(row['entradas']) if pd.notna(row['entradas']) else 0,
        duelos=int(row['duelos']) if pd.notna(row['duelos']) else 0,
        duelos_ganados=int(row['duelos_ganados']) if pd.notna(row['duelos_ganados']) else 0,
        duelos_perdidos=int(row['duelos_perdidos']) if pd.notna(row['duelos_perdidos']) else 0,
        bloqueos=int(row['bloqueos']) if pd.notna(row['bloqueos']) else 0,
        bloqueo_tiros=int(row['bloqueo_tiros']) if pd.notna(row['bloqueo_tiros']) else 0,
        bloqueo_pase=int(row['bloqueo_pase']) if pd.notna(row['bloqueo_pase']) else 0,
        despejes=int(row['despejes']) if pd.notna(row['despejes']) else 0,
        regates=int(row['regates']) if pd.notna(row['regates']) else 0,
        regates_completados=int(row['regates_completados']) if pd.notna(row['regates_completados']) else 0,
        regates_fallidos=int(row['regates_fallidos']) if pd.notna(row['regates_fallidos']) else 0,
        conducciones=int(row['conducciones']) if pd.notna(row['conducciones']) else 0,
        distancia_conduccion=float(row['distancia_conduccion']) if pd.notna(row['distancia_conduccion']) else 0.0,
        metros_avanzados_conduccion=float(row['metros_avanzados_conduccion']) if pd.notna(row['metros_avanzados_conduccion']) else 0.0,
        conducciones_progresivas=int(row['conducciones_progresivas']) if pd.notna(row['conducciones_progresivas']) else 0,
        duelos_aereos_ganados=int(row['duelos_aereos_ganados']) if pd.notna(row['duelos_aereos_ganados']) else 0,
        duelos_aereos_perdidos=int(row['duelos_aereos_perdidos']) if pd.notna(row['duelos_aereos_perdidos']) else 0,
        duelos_aereos_ganados_pct=float(row['duelos_aereos_ganados_pct']) if pd.notna(row['duelos_aereos_ganados_pct']) else 0.0,
        roles=[]  # Se llena después con fuzzy matching
    )
    return stats

def hacer_fuzzy_match(nombre_csv, candidatos_db, umbral=75):
    """Fuzzy matching entre nombre CSV y candidatos BD."""
    if not RAPIDFUZZ_DISPONIBLE or not candidatos_db:
        return None, 0
    
    nombres_db = [j.nombre for j in candidatos_db]
    mejor_match = rf_process.extractOne(
        nombre_csv, nombres_db,
        scorer=rf_fuzz.token_sort_ratio,
        score_cutoff=umbral
    )
    
    if mejor_match:
        nombre_match, score, idx = mejor_match
        return candidatos_db[idx], score
    return None, 0

def hacer_fuzzy_match_simple(nombre_csv, candidatos_db):
    """Fuzzy matching simple sin rapidfuzz."""
    nombre_csv_norm = normalizar_nombre(nombre_csv)
    
    for jugador in candidatos_db:
        if normalizar_nombre(jugador.nombre) == nombre_csv_norm:
            return jugador, 100
    
    primer_nombre_csv = nombre_csv_norm.split()[0]
    for jugador in candidatos_db:
        if normalizar_nombre(jugador.nombre).startswith(primer_nombre_csv):
            return jugador, 90
    
    ultimo_nombre_csv = nombre_csv_norm.split()[-1]
    for jugador in candidatos_db:
        if normalizar_nombre(jugador.nombre).endswith(ultimo_nombre_csv):
            return jugador, 85
    
    for palabra in nombre_csv_norm.split():
        for jugador in candidatos_db:
            if palabra in normalizar_nombre(jugador.nombre):
                return jugador, 70
    
    return None, 0

def buscar_jugador_partido(nombre_csv, equipo, partido):
    """Busca EstadisticasPartidoJugador con fuzzy matching."""
    stats_equipo = EstadisticasPartidoJugador.objects.filter(
        partido=partido
    ).select_related('jugador')
    
    if partido.equipo_local == equipo:
        stats_equipo = stats_equipo.filter(
            Q(partido__equipo_local=equipo) | 
            Q(jugador__historial_equipos__equipo=equipo, jugador__historial_equipos__temporada=partido.jornada.temporada)
        )
    else:
        stats_equipo = stats_equipo.filter(
            Q(partido__equipo_visitante=equipo) |
            Q(jugador__historial_equipos__equipo=equipo, jugador__historial_equipos__temporada=partido.jornada.temporada)
        )
    
    if not stats_equipo.exists():
        return None
    
    for stat in stats_equipo:
        if normalizar_nombre(stat.jugador.nombre) == normalizar_nombre(nombre_csv):
            return stat
    
    candidatos = [stat.jugador for stat in stats_equipo]
    
    if RAPIDFUZZ_DISPONIBLE:
        jugador_match, score = hacer_fuzzy_match(nombre_csv, candidatos, umbral=75)
    else:
        jugador_match, score = hacer_fuzzy_match_simple(nombre_csv, candidatos)
    
    if jugador_match:
        return stats_equipo.filter(jugador=jugador_match).first()
    
    return None

# ============================================================================
# FUNCIONES DE CARGA (FASE 1: Partidos y Estadísticas)
# ============================================================================

def procesar_csv_partido(ruta_csv, temporada):
    """Procesa un CSV de partido y carga los datos."""
    try:
        df = pd.read_csv(ruta_csv, encoding='utf-8-sig')
    except Exception as e:
        return False
    
    if df.empty:
        return False
    
    try:
        primera_fila = df.iloc[0]
        jornada_num = int(primera_fila['jornada'])
        fecha_partido = parsear_fecha(primera_fila['fecha_partido'])
        equipo_local_nombre = normalizar_equipo(primera_fila['equipo_propio'] if bool(primera_fila['local']) else primera_fila['equipo_rival'])
        equipo_visitante_nombre = normalizar_equipo(primera_fila['equipo_rival'] if bool(primera_fila['local']) else primera_fila['equipo_propio'])
        
        jornada = obtener_o_crear_jornada(temporada, jornada_num)
        equipo_local = obtener_o_crear_equipo(equipo_local_nombre)
        equipo_visitante = obtener_o_crear_equipo(equipo_visitante_nombre)
        obtener_o_crear_equipo_temporada(equipo_local, temporada)
        obtener_o_crear_equipo_temporada(equipo_visitante, temporada)
        
        partido = obtener_o_crear_partido(jornada, equipo_local, equipo_visitante, fecha_partido)
        
        for idx, row in df.iterrows():
            try:
                nombre_jugador = row['player']
                posicion = row['posicion']
                equipo_nombre = row['equipo_propio']
                dorsal = row['dorsal']
                
                equipo = obtener_o_crear_equipo(equipo_nombre)
                obtener_o_crear_equipo_temporada(equipo, temporada)
                jugador = obtener_o_crear_jugador(nombre_jugador, posicion)
                obtener_o_crear_historial(jugador, equipo, temporada, dorsal)
                
                stats = cargar_estadisticas_partido(row, jugador, equipo, partido)
                stats.save()
            except Exception as e:
                continue
        
        return True
    except Exception as e:
        return False

def fase_1_cargar_partidos_y_estadisticas():
    """FASE 1: Carga partidos y estadísticas iniciales."""
    print("\n" + "=" * 70)
    print("FASE 1: CARGAR PARTIDOS Y ESTADISTICAS")
    print("=" * 70)
    
    temporadas_map = {
        'temporada_23_24': '23_24',
        'temporada_24_25': '24_25',
        'temporada_25_26': '25_26',
    }
    
    # Crear temporadas
    print("\n[TEMPORADAS] Creando...")
    temp_23_24 = obtener_o_crear_temporada('23_24')
    temp_24_25 = obtener_o_crear_temporada('24_25')
    temp_25_26 = obtener_o_crear_temporada('25_26')
    
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(cwd, 'data')
    
    temporadas_obj_map = {
        'temporada_23_24': temp_23_24,
        'temporada_24_25': temp_24_25,
        'temporada_25_26': temp_25_26,
    }
    
    total_csvs = 0
    for temp_dir, temp_obj in temporadas_obj_map.items():
        print(f"\n[{temp_dir.replace('temporada_', '')}] Procesando CSVs...")
        
        pattern = os.path.join(data_dir, temp_dir, 'jornada_*', 'p*.csv')
        csvs = sorted(glob.glob(pattern))
        
        for csv_path in csvs:
            if procesar_csv_partido(csv_path, temp_obj):
                total_csvs += 1
    
    print(f"\n[OK] FASE 1 completada: {total_csvs} CSVs procesados")
    print(f"  - Partidos: {Partido.objects.count()}")
    print(f"  - Estadísticas: {EstadisticasPartidoJugador.objects.count()}")
    
    # Actualizar fechas de jornadas después de cargar partidos
    actualizar_fechas_jornadas()

# ============================================================================
# ACTUALIZACIÓN DE FECHAS DE JORNADAS
# ============================================================================

def actualizar_fechas_jornadas():
    """
    Calcula y actualiza fecha_inicio y fecha_fin para cada jornada.
    
    fecha_inicio = mínimo de fecha_partido de todos los partidos de la jornada
    fecha_fin = máximo de fecha_partido de todos los partidos de la jornada
    """
    print("\n[FECHAS] Actualizando fechas_inicio/fin de jornadas...")
    
    jornadas = Jornada.objects.all()
    jornadas_actualizadas = 0
    
    for jornada in jornadas:
        partidos = Partido.objects.filter(jornada=jornada).filter(fecha_partido__isnull=False)
        
        if not partidos.exists():
            continue
        
        # Calcular mín y máx
        fecha_inicio = partidos.aggregate(min_fecha=Count('fecha_partido', distinct=True))
        
        # Usar valores manuales para evitar agregaciones complicadas
        fechas = []
        for p in partidos:
            if p.fecha_partido:
                fechas.append(p.fecha_partido)
        
        if fechas:
            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)
            
            jornada.fecha_inicio = fecha_inicio
            jornada.fecha_fin = fecha_fin
            jornada.save()
            jornadas_actualizadas += 1
    
    print(f"  ✅ {jornadas_actualizadas} jornadas actualizadas")

# ============================================================================
# FUNCIONES DE CARGA (FASE 2: Roles, Goles, Clasificación, Rendimiento)
# ============================================================================

def fase_2_cargar_roles():
    """FASE 2a: Carga roles con fuzzy matching."""
    print("\n" + "=" * 70)
    print("FASE 2a: CARGAR ROLES (CON FUZZY MATCHING)")
    print("=" * 70)
    
    if RAPIDFUZZ_DISPONIBLE:
        print("[OK] Usando rapidfuzz para fuzzy matching")
    else:
        print("[INFO] Usando fuzzy matching simple")
    
    temporadas_map = {
        'temporada_23_24': '23_24',
        'temporada_24_25': '24_25',
        'temporada_25_26': '25_26',
    }
    
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(cwd, 'data')
    
    actualizadas = 0
    
    for temp_dir, temp_codigo in temporadas_map.items():
        pattern = os.path.join(data_dir, temp_dir, 'jornada_*', 'p*.csv')
        csvs = sorted(glob.glob(pattern))
        
        for csv_path in csvs:
            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
                
                if df.empty:
                    continue
                
                primera_fila = df.iloc[0]
                jornada_num = int(primera_fila['jornada'])
                equipo_local_nombre = normalizar_equipo(primera_fila['equipo_propio'] if bool(primera_fila['local']) else primera_fila['equipo_rival'])
                equipo_visitante_nombre = normalizar_equipo(primera_fila['equipo_rival'] if bool(primera_fila['local']) else primera_fila['equipo_propio'])
                
                try:
                    temporada = Temporada.objects.get(nombre=temp_codigo)
                    jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
                    equipo_local = Equipo.objects.get(nombre=equipo_local_nombre)
                    equipo_visitante = Equipo.objects.get(nombre=equipo_visitante_nombre)
                    partido = Partido.objects.get(
                        jornada=jornada,
                        equipo_local=equipo_local,
                        equipo_visitante=equipo_visitante
                    )
                except Exception:
                    continue
                
                for idx, row in df.iterrows():
                    try:
                        roles = parsear_roles(row['roles'])
                        if not roles:
                            continue
                        
                        nombre_jugador = row['player']
                        es_local = bool(row['local'])
                        equipo = equipo_local if es_local else equipo_visitante
                        
                        stat = buscar_jugador_partido(nombre_jugador, equipo, partido)
                        
                        if stat:
                            stat.roles = roles
                            stat.save()
                            actualizadas += 1
                    except Exception:
                        continue
            except Exception:
                continue
    
    con_roles = EstadisticasPartidoJugador.objects.exclude(roles=[]).count()
    print(f"\n[OK] Roles cargados: {con_roles} estadísticas")

def fase_2b_cargar_goles():
    """FASE 2b: Carga goles en partidos."""
    print("\n" + "=" * 70)
    print("FASE 2b: CARGAR GOLES EN PARTIDOS")
    print("=" * 70)
    
    partidos_sin_goles = Partido.objects.filter(goles_local__isnull=True, goles_visitante__isnull=True)
    actualizados = 0
    
    for partido in partidos_sin_goles:
        try:
            goles_local = EstadisticasPartidoJugador.objects.filter(
                partido=partido,
                jugador__historial_equipos__equipo=partido.equipo_local
            ).aggregate(total=Sum('gol_partido'))['total'] or 0
            
            goles_visitante = EstadisticasPartidoJugador.objects.filter(
                partido=partido,
                jugador__historial_equipos__equipo=partido.equipo_visitante
            ).aggregate(total=Sum('gol_partido'))['total'] or 0
            
            if goles_local > 0 or goles_visitante > 0:
                partido.goles_local = int(goles_local)
                partido.goles_visitante = int(goles_visitante)
                partido.save()
                actualizados += 1
        except Exception:
            continue
    
    con_goles = Partido.objects.filter(goles_local__isnull=False).count()
    print(f"[OK] Goles cargados: {con_goles} partidos")

def fase_2c_cargar_clasificacion():
    """FASE 2c: Carga clasificación jornada."""
    print("\n" + "=" * 70)
    print("FASE 2c: CARGAR CLASIFICACION JORNADA")
    print("=" * 70)
    
    temporadas_map = {
        'temporada_23_24': '23_24',
        'temporada_24_25': '24_25',
        'temporada_25_26': '25_26',
    }
    
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(cwd, 'data')
    
    creadas = 0
    
    for temp_dir, temp_codigo in temporadas_map.items():
        csv_path = os.path.join(data_dir, temp_dir, 'clasificacion_temporada.csv')
        
        if not os.path.exists(csv_path):
            continue
        
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            temporada = Temporada.objects.get(nombre=temp_codigo)
            
            for idx, row in df.iterrows():
                try:
                    jornada_num = int(row['jornada'])
                    equipo_nombre = normalizar_equipo(row['equipo'])
                    
                    jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
                    equipo = Equipo.objects.get(nombre=equipo_nombre)
                    
                    clasificacion, created = ClasificacionJornada.objects.update_or_create(
                        temporada=temporada,
                        jornada=jornada,
                        equipo=equipo,
                        defaults={
                            'posicion': int(row['posicion']),
                            'puntos': int(row['pts']),
                            'goles_favor': int(row['gf']),
                            'goles_contra': int(row['gc']),
                            'diferencia_goles': int(row['dg']),
                            'partidos_ganados': int(row['pg']),
                            'partidos_empatados': int(row['pe']),
                            'partidos_perdidos': int(row['pp']),
                            'racha_reciente': str(row.get('racha5partidos', '')),
                        }
                    )
                    
                    if created:
                        creadas += 1
                except Exception:
                    continue
        except Exception:
            continue
    
    total = ClasificacionJornada.objects.count()
    print(f"[OK] Clasificación cargada: {total} registros")

def fase_2d_cargar_rendimiento():
    """FASE 2d: Carga rendimiento histórico."""
    print("\n" + "=" * 70)
    print("FASE 2d: CARGAR RENDIMIENTO HISTORICO")
    print("=" * 70)
    
    creados = 0
    
    jugadores = Jugador.objects.all()
    
    for jugador in jugadores:
        historiales = jugador.historial_equipos.all()
        
        for historial in historiales:
            try:
                temporada = historial.temporada
                equipo = historial.equipo
                
                stats = EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada,
                    partido__equipo_local=equipo
                ) | EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada,
                    partido__equipo_visitante=equipo
                )
                
                if not stats.exists():
                    continue
                
                rendimiento, created = RendimientoHistoricoJugador.objects.update_or_create(
                    jugador=jugador,
                    temporada=temporada,
                    equipo=equipo,
                    defaults={
                        'partidos_jugados': stats.filter(min_partido__gt=0).count(),
                        'partidos_como_titular': stats.filter(titular=True).count(),
                        'minutos_totales': int(stats.aggregate(Sum('min_partido'))['min_partido__sum'] or 0),
                        'goles_temporada': int(stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0),
                        'asistencias_temporada': int(stats.aggregate(Sum('asist_partido'))['asist_partido__sum'] or 0),
                        'tarjetas_amarillas_total': int(stats.aggregate(Sum('amarillas'))['amarillas__sum'] or 0),
                        'tarjetas_rojas_total': int(stats.aggregate(Sum('rojas'))['rojas__sum'] or 0),
                        'pases_completados_total': int(stats.aggregate(Sum('pases_totales'))['pases_totales__sum'] or 0),
                    }
                )
                
                if created:
                    creados += 1
            except Exception:
                continue
    
    total = RendimientoHistoricoJugador.objects.count()
    print(f"[OK] Rendimiento cargado: {total} registros")

def fase_2e_poblar_equipo_jugador_temporada():
    """FASE 2e: Puebla EquipoJugadorTemporada con jugadores por temporada."""
    print("\n" + "=" * 70)
    print("FASE 2e: POBLAR EQUIPO-JUGADOR-TEMPORADA")
    print("=" * 70)
    
    temporadas = Temporada.objects.all()
    total_creados = 0
    
    for temporada in temporadas:
        print(f"\n[{temporada.nombre}] Procesando...")
        
        # Obtener todos los jugadores que jugaron al menos un partido
        jugadores_stats = (
            EstadisticasPartidoJugador.objects
            .filter(partido__jornada__temporada=temporada)
            .values('jugador_id', 'jugador__nombre', 'jugador__apellido')
            .annotate(count=Count('id'))
            .filter(count__gt=0)
            .distinct()
        )
        
        created_count = 0
        updated_count = 0
        
        for stat in jugadores_stats:
            jugador_id = stat['jugador_id']
            partidos_count = stat['count']
            
            # Obtener del historial para sacar equipo, dorsal, edad
            historial = (
                HistorialEquiposJugador.objects
                .filter(jugador_id=jugador_id, temporada=temporada)
                .first()
            )
            
            if historial:
                # Crear o actualizar en EquipoJugadorTemporada
                obj, created = EquipoJugadorTemporada.objects.update_or_create(
                    equipo=historial.equipo,
                    jugador_id=jugador_id,
                    temporada=temporada,
                    defaults={
                        'dorsal': historial.dorsal,
                        'edad': historial.edad,
                        'partidos_jugados': partidos_count,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Si no hay historial, obtener equipo de las estadísticas
                try:
                    first_stat = (
                        EstadisticasPartidoJugador.objects
                        .filter(jugador_id=jugador_id, partido__jornada__temporada=temporada)
                        .select_related('partido__equipo_local', 'partido__equipo_visitante')
                        .first()
                    )
                    
                    if first_stat:
                        # Determinar en qué equipo jugó (asumiendo equipo_local por defecto)
                        equipo = first_stat.partido.equipo_local
                        
                        obj, created = EquipoJugadorTemporada.objects.update_or_create(
                            equipo=equipo,
                            jugador_id=jugador_id,
                            temporada=temporada,
                            defaults={
                                'dorsal': 0,
                                'edad': 0,
                                'partidos_jugados': partidos_count,
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                except Exception as e:
                    print(f"  ⚠ Error procesando jugador {jugador_id}: {str(e)}")
        
        print(f"  ✓ Creados: {created_count} | Actualizados: {updated_count}")
        total_creados += created_count
    
    total = EquipoJugadorTemporada.objects.count()
    print(f"\n[OK] Plantillas por temporada cargadas: {total} registros")
    return total


def main():
    """Función principal: ejecuta todas las fases."""
    
    print("\n" + "=" * 70)
    print("CARGA COMPLETA UNIFICADA DE TODOS LOS DATOS")
    print("=" * 70)
    print("\nEste script carga TODO en una sola ejecución:")
    print("1. Partidos y Estadísticas (45 campos)")
    print("2. Roles con fuzzy matching")
    print("3. Goles en Partidos")
    print("4. Clasificación Jornada")
    print("5. Rendimiento Histórico de Jugadores")
    print("6. Equipo-Jugador-Temporada (Plantillas por temporada)")
    
    # FASE 1: Partidos y Estadísticas
    fase_1_cargar_partidos_y_estadisticas()
    
    # FASE 2: Datos complementarios
    fase_2_cargar_roles()
    fase_2b_cargar_goles()
    fase_2c_cargar_clasificacion()
    fase_2d_cargar_rendimiento()
    fase_2e_poblar_equipo_jugador_temporada()
    
    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"\nTemporadas: {Temporada.objects.count()}")
    print(f"Equipos: {Equipo.objects.count()}")
    print(f"Jugadores: {Jugador.objects.count()}")
    print(f"Jornadas: {Jornada.objects.count()}")
    print(f"Partidos: {Partido.objects.count()}")
    print(f"Estadísticas: {EstadisticasPartidoJugador.objects.count()}")
    
    roles_count = EstadisticasPartidoJugador.objects.exclude(roles=[]).count()
    goles_count = Partido.objects.filter(goles_local__isnull=False).count()
    clasificacion_count = ClasificacionJornada.objects.count()
    rendimiento_count = RendimientoHistoricoJugador.objects.count()
    equipo_jugador_temp = EquipoJugadorTemporada.objects.count()
    
    print(f"\nDatos complementarios:")
    print(f"  - Roles: {roles_count} estadísticas")
    print(f"  - Goles: {goles_count} partidos")
    print(f"  - Clasificación: {clasificacion_count} registros")
    print(f"  - Rendimiento: {rendimiento_count} registros")
    print(f"  - Plantillas por Temporada: {equipo_jugador_temp} registros")
    
    print("\n" + "=" * 70)
    print("[OK] CARGA COMPLETADA - TODO LISTO EN LA BASE DE DATOS")
    print("=" * 70)

if __name__ == '__main__':
    main()
