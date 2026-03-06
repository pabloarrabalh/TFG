"""
views/__init__.py  façade for the views subpackage.

Importing from `main.views` still works transparently for all url patterns.
All logic lives in the sibling modules (utils, menu, auth, ).
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

from .menu import menu  # noqa: F401
from .plantilla import (  # noqa: F401
    mi_plantilla,
    guardar_plantilla,
    listar_plantillas,
    obtener_plantilla,
    eliminar_plantilla,
    renombrar_plantilla,
)
from .equipo import equipos, equipo  # noqa: F401
from .clasificacion import clasificacion  # noqa: F401
from .jugador import jugador  # noqa: F401
from .auth import (  # noqa: F401
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
from .predicciones import (  # noqa: F401
    predecir_portero_api,
    cambiar_jornada_api,
    explicar_prediccion_portero_api,
    predecir_jugador_api,
)
