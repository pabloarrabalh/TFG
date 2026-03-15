"""
Utilities para operaciones comunes en main app.
"""
from .lazy_predictions import (
    get_or_create_prediccion,
    get_predicciones_jugador_with_lazy,
    ensure_predicciones_activos,
)

__all__ = [
    'get_or_create_prediccion',
    'get_predicciones_jugador_with_lazy',
    'ensure_predicciones_activos',
]
