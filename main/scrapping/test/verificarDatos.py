#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de verificación para asegurar que todos los datos se han asignado correctamente.
Verifica:
1. Roles asignados correctamente
2. Goles en partidos
3. Clasificación jornada
4. Rendimiento histórico
5. Integridad de datos
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import (
    Temporada, Equipo, Jugador, Jornada, Partido,
    EstadisticasPartidoJugador, ClasificacionJornada,
    RendimientoHistoricoJugador
)
from django.db.models import Q, Count, Sum

def verificar_roles():
    """Verifica la asignación de roles."""
    print("\n" + "=" * 70)
    print("VERIFICACION: ROLES EN ESTADISTICAS")
    print("=" * 70)
    
    total_stats = EstadisticasPartidoJugador.objects.count()
    stats_con_roles = EstadisticasPartidoJugador.objects.exclude(roles=[]).count()
    stats_sin_roles = total_stats - stats_con_roles
    
    print(f"\nTotal estadísticas: {total_stats}")
    print(f"  - Con roles: {stats_con_roles} ({100*stats_con_roles/total_stats:.1f}%)")
    print(f"  - Sin roles: {stats_sin_roles} ({100*stats_sin_roles/total_stats:.1f}%)")
    
    # Analizar tipos de roles
    print(f"\nAnálisis de roles encontrados:")
    stats_con_roles_qs = EstadisticasPartidoJugador.objects.exclude(roles=[])
    
    if stats_con_roles > 0:
        # Muestreos
        sample = stats_con_roles_qs.first()
        print(f"  Ejemplo 1:")
        print(f"    Jugador: {sample.jugador.nombre}")
        print(f"    Partido: {sample.partido}")
        print(f"    Roles ({len(sample.roles)} items): {sample.roles[:2]}...")
        
        # Distribucion de cantidad de roles por estadística
        roles_por_stat = {}
        for stat in stats_con_roles_qs[:100]:  # Muestreo de 100
            cantidad = len(stat.roles)
            roles_por_stat[cantidad] = roles_por_stat.get(cantidad, 0) + 1
        
        print(f"\n  Distribución de cantidad de roles por estadística:")
        for cantidad in sorted(roles_por_stat.keys()):
            count = roles_por_stat[cantidad]
            print(f"    - {cantidad} roles: {count} estadísticas")
    
    # Verificar que roles sea siempre una lista válida
    invalid_roles = EstadisticasPartidoJugador.objects.exclude(
        roles__isnull=False
    ).exclude(
        roles=[]
    )
    
    if invalid_roles.count() == 0:
        print(f"\n  OK - Todos los roles son listas válidas")
    else:
        print(f"\n  WARN - {invalid_roles.count()} roles con formato inválido")
    
    return stats_con_roles, total_stats

def verificar_goles():
    """Verifica la asignación de goles en partidos."""
    print("\n" + "=" * 70)
    print("VERIFICACION: GOLES EN PARTIDOS")
    print("=" * 70)
    
    total_partidos = Partido.objects.count()
    partidos_con_goles = Partido.objects.filter(goles_local__isnull=False, goles_visitante__isnull=False).count()
    partidos_sin_goles = total_partidos - partidos_con_goles
    
    print(f"\nTotal partidos: {total_partidos}")
    print(f"  - Con goles: {partidos_con_goles} ({100*partidos_con_goles/total_partidos:.1f}%)")
    print(f"  - Sin goles: {partidos_sin_goles} ({100*partidos_sin_goles/total_partidos:.1f}%)")
    
    # Ejemplos
    partidos_qs = Partido.objects.filter(goles_local__isnull=False, goles_visitante__isnull=False)
    
    if partidos_qs.exists():
        print(f"\nEjemplos de partidos con goles:")
        for partido in partidos_qs[:3]:
            print(f"  - {partido.equipo_local.nombre} {partido.goles_local}-{partido.goles_visitante} {partido.equipo_visitante.nombre}")
            print(f"    (Jornada {partido.jornada.numero_jornada}, {partido.jornada.temporada.nombre})")
    
    # Verificar igualdad de goles: suma de goles_partido debe coincidir con goles_local/visitante
    print(f"\nVerificación de integridad (muestreo de 10 partidos con goles):")
    inconsistencias = 0
    for partido in partidos_qs[:10]:
        goles_local_calculados = EstadisticasPartidoJugador.objects.filter(
            partido=partido,
            jugador__historial_equipos__equipo=partido.equipo_local
        ).aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
        
        goles_visitante_calculados = EstadisticasPartidoJugador.objects.filter(
            partido=partido,
            jugador__historial_equipos__equipo=partido.equipo_visitante
        ).aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
        
        if int(goles_local_calculados) != int(partido.goles_local):
            print(f"  WARN - {partido}: goles local BD={partido.goles_local}, calculados={goles_local_calculados}")
            inconsistencias += 1
    
    if inconsistencias == 0:
        print(f"  OK - Integridad de goles verificada")
    else:
        print(f"  WARN - {inconsistencias} inconsistencias encontradas")
    
    return partidos_con_goles, total_partidos

def verificar_clasificacion():
    """Verifica la asignación de clasificación jornada."""
    print("\n" + "=" * 70)
    print("VERIFICACION: CLASIFICACION JORNADA")
    print("=" * 70)
    
    total_clasificaciones = ClasificacionJornada.objects.count()
    
    print(f"\nTotal clasificaciones: {total_clasificaciones}")
    
    # Por temporada
    por_temporada = ClasificacionJornada.objects.values('temporada__nombre').annotate(count=Count('id'))
    print(f"\nPor temporada:")
    for item in por_temporada:
        print(f"  - {item['temporada__nombre']}: {item['count']}")
    
    # Ejemplos
    print(f"\nEjemplos de clasificaciones:")
    for clasificacion in ClasificacionJornada.objects.select_related('equipo', 'temporada', 'jornada')[:3]:
        print(f"  - {clasificacion.equipo.nombre} (Pos {clasificacion.posicion}) - " +
              f"{clasificacion.temporada.nombre} Jornada {clasificacion.jornada.numero_jornada}: " +
              f"{clasificacion.puntos} pts")
    
    # Verificar integridad: posiciones consecutivas por jornada
    print(f"\nVerificación de integridad (posiciones por jornada):")
    problemas = 0
    for jornada in Jornada.objects.all()[:5]:  # Verificar primeras 5 jornadas
        clasificaciones = ClasificacionJornada.objects.filter(jornada=jornada).order_by('posicion')
        if clasificaciones.count() > 0:
            posiciones = [c.posicion for c in clasificaciones]
            no_consecutivas = any(posiciones[i] != i+1 for i in range(len(posiciones)))
            if no_consecutivas:
                print(f"  WARN - {jornada}: posiciones no consecutivas: {sorted(posiciones)}")
                problemas += 1
    
    if problemas == 0:
        print(f"  OK - Posiciones válidas en jornadas")
    
    return total_clasificaciones

def verificar_rendimiento():
    """Verifica la asignación de rendimiento histórico."""
    print("\n" + "=" * 70)
    print("VERIFICACION: RENDIMIENTO HISTORICO JUGADOR")
    print("=" * 70)
    
    total_rendimientos = RendimientoHistoricoJugador.objects.count()
    
    print(f"\nTotal rendimientos: {total_rendimientos}")
    
    # Por temporada
    por_temporada = RendimientoHistoricoJugador.objects.values('temporada__nombre').annotate(count=Count('id'))
    print(f"\nPor temporada:")
    for item in por_temporada:
        print(f"  - {item['temporada__nombre']}: {item['count']}")
    
    # Ejemplos
    print(f"\nEjemplos de rendimientos (top goleadores):")
    top_goleadores = RendimientoHistoricoJugador.objects.select_related('jugador', 'equipo', 'temporada').order_by('-goles_temporada')[:3]
    for rendimiento in top_goleadores:
        print(f"  - {rendimiento.jugador.nombre} ({rendimiento.equipo.nombre}, {rendimiento.temporada.nombre}): " +
              f"{rendimiento.goles_temporada} goles en {rendimiento.partidos_jugados} partidos")
    
    # Verificar integridad: goles_temporada debe coincidir con suma de gol_partido
    print(f"\nVerificación de integridad (integridad de goles agregados):")
    inconsistencias = 0
    for rendimiento in RendimientoHistoricoJugador.objects.all()[:20]:  # Muestreo de 20
        stats = EstadisticasPartidoJugador.objects.filter(
            jugador=rendimiento.jugador,
            partido__jornada__temporada=rendimiento.temporada
        ).filter(
            Q(partido__equipo_local=rendimiento.equipo) | Q(partido__equipo_visitante=rendimiento.equipo)
        )
        
        goles_calculados = stats.aggregate(Sum('gol_partido'))['gol_partido__sum'] or 0
        
        if int(goles_calculados) != int(rendimiento.goles_temporada):
            print(f"  WARN - {rendimiento.jugador.nombre} en {rendimiento.temporada.nombre}: " +
                  f"BD={rendimiento.goles_temporada}, calculados={goles_calculados}")
            inconsistencias += 1
    
    if inconsistencias == 0:
        print(f"  OK - Integridad de rendimiento verificada")
    else:
        print(f"  WARN - {inconsistencias} inconsistencias encontradas")
    
    return total_rendimientos

def verificar_integridad_general():
    """Verifica integridad general de las relaciones."""
    print("\n" + "=" * 70)
    print("VERIFICACION: INTEGRIDAD GENERAL")
    print("=" * 70)
    
    # Contar entidades
    print(f"\nConteos de entidades:")
    print(f"  - Temporadas: {Temporada.objects.count()}")
    print(f"  - Equipos: {Equipo.objects.count()}")
    print(f"  - Jugadores: {Jugador.objects.count()}")
    print(f"  - Jornadas: {Jornada.objects.count()}")
    print(f"  - Partidos: {Partido.objects.count()}")
    print(f"  - EstadísticasPartidoJugador: {EstadisticasPartidoJugador.objects.count()}")
    print(f"  - ClasificacionJornada: {ClasificacionJornada.objects.count()}")
    print(f"  - RendimientoHistoricoJugador: {RendimientoHistoricoJugador.objects.count()}")
    
    # Verificar que no haya orfandad de datos
    print(f"\nVerificación de relaciones:")
    
    # Partidos sin jornada
    partidos_sin_jornada = Partido.objects.filter(jornada__isnull=True).count()
    print(f"  - Partidos sin jornada: {partidos_sin_jornada}")
    
    # Jornadas sin temporada
    jornadas_sin_temporada = Jornada.objects.filter(temporada__isnull=True).count()
    print(f"  - Jornadas sin temporada: {jornadas_sin_temporada}")
    
    # EstadisticasPartidoJugador huérfanas
    stats_sin_partido = EstadisticasPartidoJugador.objects.filter(partido__isnull=True).count()
    print(f"  - Estadísticas sin partido: {stats_sin_partido}")
    
    stats_sin_jugador = EstadisticasPartidoJugador.objects.filter(jugador__isnull=True).count()
    print(f"  - Estadísticas sin jugador: {stats_sin_jugador}")
    
    # Clacificaciones sin relaciones
    clasificacion_sin_jornada = ClasificacionJornada.objects.filter(jornada__isnull=True).count()
    print(f"  - Clasificaciones sin jornada: {clasificacion_sin_jornada}")
    
    # Rendimientos sin relaciones
    rendimiento_sin_jugador = RendimientoHistoricoJugador.objects.filter(jugador__isnull=True).count()
    print(f"  - Rendimientos sin jugador: {rendimiento_sin_jugador}")
    
    problemas = (partidos_sin_jornada + jornadas_sin_temporada + stats_sin_partido + 
                 stats_sin_jugador + clasificacion_sin_jornada + rendimiento_sin_jugador)
    
    if problemas == 0:
        print(f"\n  OK - Integridad general verificada")
    else:
        print(f"\n  WARN - {problemas} problemas de integridad encontrados")

def main():
    """Función principal."""
    
    print("\n" + "=" * 70)
    print("VERIFICACION COMPLETA DE DATOS")
    print("=" * 70)
    
    # 1. Verificar roles
    roles_ok, roles_total = verificar_roles()
    
    # 2. Verificar goles
    goles_ok, goles_total = verificar_goles()
    
    # 3. Verificar clasificación
    clasificacion_ok = verificar_clasificacion()
    
    # 4. Verificar rendimiento
    rendimiento_ok = verificar_rendimiento()
    
    # 5. Verificar integridad general
    verificar_integridad_general()
    
    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"\nDatos cargados:")
    print(f"  - Roles: {roles_ok}/{roles_total} stats ({100*roles_ok/roles_total:.1f}%)")
    print(f"  - Goles: {goles_ok}/{goles_total} partidos ({100*goles_ok/goles_total:.1f}%)")
    print(f"  - Clasificación: {clasificacion_ok} registros")
    print(f"  - Rendimiento: {rendimiento_ok} registros")
    
    print(f"\n[OK] Verificación completada")

if __name__ == '__main__':
    main()
