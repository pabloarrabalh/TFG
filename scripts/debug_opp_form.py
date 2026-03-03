#!/usr/bin/env python
"""DEBUG: Verificar cálculo de opp_form"""

import os
import sys
import numpy as np
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(Path(__file__).parent))

import django
django.setup()

from main.models import EstadisticasPartidoJugador, Partido

print("=" * 80)
print("DEBUG: Cálculo de opp_form (forma del rival)")
print("=" * 80)

# Obtener últimos 50 partidos
partidos = Partido.objects.all().select_related(
    'equipo_local', 'equipo_visitante', 'jornada'
).order_by('-jornada__numero_jornada')[:50]

jugador_ids = set()
for p in partidos:
    stats = EstadisticasPartidoJugador.objects.filter(
        partido=p
    ).values_list('jugador_id', flat=True)[:1]
    if stats:
        jugador_ids.add(stats[0])
    if len(jugador_ids) >= 3:
        break

print(f"\nEncontrados {len(jugador_ids)} jugadores para testear")

from main.models import Jugador
for jug_id in list(jugador_ids)[:2]:
    jug = Jugador.objects.get(id=jug_id)
    print(f"\n{'='*80}")
    print(f"JUGADOR: {jug.nombre} {jug.apellido} (ID: {jug.id})")
    print(f"{'='*80}")
    
    # Obtener sus stats
    stats_jug = (EstadisticasPartidoJugador.objects
                 .filter(jugador=jug)
                 .select_related('partido__jornada', 'partido__equipo_local', 'partido__equipo_visitante')
                 .order_by('partido__jornada__numero_jornada'))
    
    total = stats_jug.count()
    if total < 5:
        print(f"  ({total} partidos - muy pocos)")
        continue
    
    stats_list = list(stats_jug[max(0, total-10):])
    
    print(f"\n[ÚLTIMOS 5 PARTIDOS DEL JUGADOR]")
    print(f"{'Jornada':<8} {'Local':<15} {'Visitante':<15} {'Goles':<8} {'Puntos':<8}")
    print("-" * 60)
    
    for stat in stats_list[-5:]:
        p = stat.partido
        print(f"{p.jornada.numero_jornada:<8} {p.equipo_local.nombre[:14]:<15} {p.equipo_visitante.nombre[:14]:<15} {p.goles_local}-{p.goles_visitante:<5} {stat.puntos_fantasy:<8}")
    
    # Simular siguiente jornada
    ultima_j = stats_list[-1].partido.jornada.numero_jornada
    sgte_j = ultima_j + 1
    
    print(f"\n[PRÓXIMOS PARTIDOS JORNADA {sgte_j}]")
    prox_partidos = Partido.objects.filter(
        jornada__numero_jornada=sgte_j
    ).select_related('equipo_local', 'equipo_visitante')[:3]
    
    for pp in prox_partidos:
        print(f"  {pp.equipo_local.nombre} vs {pp.equipo_visitante.nombre}")
        
        if pp.equipo_visitante.nombre.lower() in ['barcelona', 'real madrid', 'sevilla']:
            rival = pp.equipo_visitante
            
            print(f"\n    [ANALIZANDO {rival.nombre}]")
            
            # Obtener todos los partidos de este rival
            rival_home = Partido.objects.filter(
                equipo_local=rival,
                jornada__numero_jornada__lt=sgte_j
            ).select_related('equipo_visitante', 'jornada').order_by('-jornada__numero_jornada')[:5]
            
            rival_away = Partido.objects.filter(
                equipo_visitante=rival,
                jornada__numero_jornada__lt=sgte_j
            ).select_related('equipo_local', 'jornada').order_by('-jornada__numero_jornada')[:5]
            
            print(f"    {'Jornada':<8} {'Vs':<15} {'GF':<5} {'GC':<5} {'Resultado':<10}")
            print(f"    {'-' * 50}")
            
            data = []
            for rh in rival_home:
                print(f"    J{rh.jornada.numero_jornada:<6} {rh.equipo_visitante.nombre[:13]:<15} {rh.goles_local:<5} {rh.goles_visitante:<5} {rh.goles_local}-{rh.goles_visitante}")
                data.append({'gf': rh.goles_local, 'gc': rh.goles_visitante})
            
            for ra in rival_away:
                print(f"    J{ra.jornada.numero_jornada:<6} {ra.equipo_local.nombre[:13]:<15} {ra.goles_visitante:<5} {ra.goles_local:<5} {ra.goles_visitante}-{ra.goles_local}")
                data.append({'gf': ra.goles_visitante, 'gc': ra.goles_local})
            
            if len(data) >= 3:
                gf_tot = sum([d['gf'] for d in data[:5]])
                gc_tot = sum([d['gc'] for d in data[:5]])
                form_raw = (gf_tot - gc_tot) / min(5, len(data))
                opp_form = np.clip(0.5 + (form_raw / 5.0), 0.0, 1.0)
                
                print(f"\n    [CÁLCULO]")
                print(f"      GF total: {gf_tot}")
                print(f"      GC total: {gc_tot}")
                print(f"      Form raw: {form_raw:.3f}")
                print(f"      opp_form_roll5: {opp_form:.3f}")
                
                if opp_form > 0.55:
                    print(f"      ✓ Rival en BUENA FORMA")
                elif opp_form < 0.45:
                    print(f"      ✓ Rival en MALA FORMA")
                else:
                    print(f"      ✓ Rival en forma NEUTRA")

print("\n" + "=" * 80)
print("DEBUG COMPLETADO")
print("=" * 80)
