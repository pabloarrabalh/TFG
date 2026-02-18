#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obtener jugador_id real de la BD para hacer tests
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, r'C:\Users\pablo\Desktop\TFG')

django.setup()

from main.models import Jugador

# Obtener unos jugadores de la BD
jugadores = Jugador.objects.all()[:10]

print('Primeros 10 jugadores en BD:')
print('-'*50)
for jugador in jugadores:
    print(f'ID: {jugador.id}, Nombre: {jugador.nombre}')

if jugadores.exists():
    jugador_test = jugadores.first()
    print()
    print(f'[USAR ESTE]: ID={jugador_test.id}, Nombre={jugador_test.nombre}')
