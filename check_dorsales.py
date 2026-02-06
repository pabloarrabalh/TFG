#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para verificar y limpiar dorsales en la BD."""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import HistorialEquiposJugador

# Verificar cuántos historiales tienen dorsal inválido
historiales_sin_dorsal = HistorialEquiposJugador.objects.filter(dorsal__lt=1)
print(f"Historiales con dorsal inválido (< 1): {historiales_sin_dorsal.count()}")

if historiales_sin_dorsal.exists():
    print("\nActualizando dorsales inválidos a 1...")
    historiales_sin_dorsal.update(dorsal=1)
    print("✅ Dorsales actualizados")

# Mostrar algunos historiales con dorsal
print(f"\nTotal historiales en BD: {HistorialEquiposJugador.objects.count()}")
print("\nEjemplos de historiales con dorsal:")
for h in HistorialEquiposJugador.objects.all()[:10]:
    print(f"  {h.jugador.nombre:25} - {h.equipo.nombre:20} {h.temporada.nombre}: dorsal {h.dorsal}")
