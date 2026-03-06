"""
api_views.py  thin re-export façade.

All logic lives in the api/ subpackage.
This file is kept so that any legacy code importing from `main.api_views`
continues to work without changes.
"""

#  auth 
from .api.auth import (  # noqa: F401
    _user_info,
    MeView,
    LoginView,
    LogoutView,
    RegisterView,
)

#  menu 
from .api.menu import (  # noqa: F401
    _serialize_partido_calendario,
    _get_jugadores_destacados_con_predicciones,
    MenuView,
)

#  clasificacion 
from .api.clasificacion import ClasificacionView  # noqa: F401

#  equipos 
from .api.equipo import EquipoListView, EquipoDetailView  # noqa: F401

#  jugadores 
from .api.jugador import (  # noqa: F401
    _get_predicciones_jugador,
    JugadorDetailView,
    TopJugadoresPorPosicionView,
)

#  perfil 
from .api.perfil import (  # noqa: F401
    PerfilView,
    UpdatePerfilView,
    UpdateStatusView,
    UploadPhotoView,
    UpdatePreferenciasNotificacionesView,
)

#  favoritos 
from .api.favoritos import (  # noqa: F401
    FavoritosView,
    ToggleFavoritoView,
    DeleteFavoritoView,
)

#  amigos 
from .api.amigos import (  # noqa: F401
    AmigosView,
    EnviarSolicitudView,
    AceptarSolicitudView,
    RechazarSolicitudView,
    EliminarAmigoView,
    PlantillasAmigoView,
)

#  plantilla 
from .api.plantilla import (  # noqa: F401
    MiPlantillaView,
    MiPlantillaJugadoresView,
    TogglePrivacidadPlantillaView,
    SetPlantillaPredeterminadaView,
    MisPlantillasPrivacidadView,
)

#  notificaciones 
from .api.notificaciones import (  # noqa: F401
    NotificacionesView,
    MarcarNotificacionLeidaView,
    MarcarTodasLeidasView,
    BorrarNotificacionView,
    BorrarTodasNotificacionesView,
)

#  consejero 
from .api.consejero import (  # noqa: F401
    ConsejeroView,
)
