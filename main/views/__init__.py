"""
views/__init__.py – re-exports shared utility helpers used by main/api/*.py modules.
All HTML template views have been removed; the frontend is a React SPA.
"""

from .utils import (  # noqa: F401
    normalize_team_name_python,
    shield_name,
    similitud_nombres,
    get_racha_detalles,
    get_racha_futura,
    get_historico_temporadas,
    get_maximo_goleador,
    get_partido_anterior_temporada,
    get_h2h_historico,
    get_estadisticas_equipo_temporadas,
    get_jugadores_ultimas_temporadas,
    get_informacion_equipo,
    calcular_percentil,
)
