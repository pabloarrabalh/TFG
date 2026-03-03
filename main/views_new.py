"""
views.py – thin re-export proxy.

All logic lives in views_*.py modules.
This file is kept so that existing url patterns that import from `main.views`
continue to work without changes.
"""
from .views_utils import (  # noqa: F401 – available for api_views imports
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

from .views_menu import menu  # noqa: F401
from .views_plantilla import (  # noqa: F401
    mi_plantilla,
    guardar_plantilla,
    listar_plantillas,
    obtener_plantilla,
    eliminar_plantilla,
    renombrar_plantilla,
)
from .views_equipo import equipos, equipo  # noqa: F401
from .views_clasificacion import clasificacion  # noqa: F401
from .views_jugador import jugador  # noqa: F401
from .views_auth import (  # noqa: F401
    amigos,
    login_register,
    login_view,
    register_view,
    select_favorite_teams,
    toggle_favorite_team,
    logout_view,
    terms_conditions,
    perfil_usuario,
    upload_profile_photo,
    update_profile,
    update_user_status,
    delete_favorite_team,
)
from .views_predicciones import (  # noqa: F401
    predecir_portero_api,
    cambiar_jornada_api,
    explicar_prediccion_portero_api,
    predecir_jugador_api,
)
