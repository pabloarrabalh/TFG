#!/bin/bash
# Script para generar y aplicar migraciones de PedidoPrediccion

echo "[MIGRATION] Generando migración para PedidoPrediccion..."
python manage.py makemigrations main --name add_pedido_prediccion --verbosity 2

echo "[MIGRATION] Aplicando migraciones..."
python manage.py migrate main --verbosity 2

echo "[MIGRATION] ✓ Completado"
