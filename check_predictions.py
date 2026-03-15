#!/usr/bin/env python
"""Check prediction statistics in database"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import PrediccionJugador, PedidoPrediccion

total_preds = PrediccionJugador.objects.count()
print(f'✓ Predicciones generadas: {total_preds}')

try:
    pending = PedidoPrediccion.objects.filter(estado='pending').count()
    generated = PedidoPrediccion.objects.filter(estado='generated').count()
    failed = PedidoPrediccion.objects.filter(estado='failed').count()
    total_pedidos = PedidoPrediccion.objects.count()
    
    print(f'\n📋 Pedidos predicción:')
    print(f'  Pendientes: {pending}')
    print(f'  Generadas: {generated}')
    print(f'  Fallidas: {failed}')
    print(f'  Total pedidos: {total_pedidos}')
    
    if total_pedidos > 0:
        porcentaje = (generated / total_pedidos * 100)
        print(f'\n  📊 Progreso: {porcentaje:.1f}%')
        print(f'  ⏳ Estimado: {pending} predicciones restantes')
except Exception as e:
    print(f'\n⚠️  PedidoPrediccion no existe aún (necesitas aplicar migraciones): {e}')
