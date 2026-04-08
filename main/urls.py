from django.urls import path
from . import drf_views
from .api.predicciones import *
from .api.auth import MeView, LoginView, LogoutView, RegisterView
from .api.menu import MenuView, MenuTopJugadoresView
from .api.clasificacion import ClasificacionView
from .api.equipo import EquipoListView, EquipoDetailView
from .api.jugador import JugadorDetailView, TopJugadoresPorPosicionView
from .api.jugador_partidos import JugadorPartidosView
from .api.jugador_insight import JugadorInsightView
from .api.buscar import RadarJugadorView, BuscarView
from .api.perfil import *
from .api.favoritos import FavoritosView, ToggleFavoritoView, DeleteFavoritoView
from .api.amigos import *
from .api.plantilla import *
from .api.plantilla_notificaciones import PlantillaNotificacionesView
from .api.notificaciones import *
from .api.estadisticas import EstadisticasView, ComparacionJugadoresView
from .api.consejero import ConsejeroView

urlpatterns = [
    path('api/radar/<int:jugador_id>/<str:temporada>/', RadarJugadorView.as_view(), name='api_radar_jugador'),
    path('api/buscar/', BuscarView.as_view(), name='api_buscar'),
    path('api/favoritos/toggle/', ToggleFavoritoView.as_view(), name='api_toggle_favorito'),
    path('api/predecir-portero/', PredecirPorteroView.as_view(), name='predecir_portero_api'),
    path('api/predecir-jugador/', PredecirJugadorView.as_view(), name='predecir_jugador_api'),
    path('api/explicar-prediccion/', ExplicarPrediccionView.as_view(), name='explicar_prediccion_portero_api'),
    path('api/cambiar-jornada/', CambiarJornadaLegacyView.as_view(), name='cambiar_jornada_api'),
    path('api/me/', MeView.as_view(), name='api_me'),
    path('api/auth/login/', LoginView.as_view(), name='api_auth_login'),
    path('api/auth/logout/', LogoutView.as_view(), name='api_auth_logout'),
    path('api/auth/register/', RegisterView.as_view(), name='api_auth_register'),
    path('api/menu/', MenuView.as_view(), name='api_menu'),
    path('api/menu/top-jugadores/', MenuTopJugadoresView.as_view(), name='api_menu_top_jugadores'),
    path('api/clasificacion/', ClasificacionView.as_view(), name='api_clasificacion'),
    path('api/top-jugadores-por-posicion/', TopJugadoresPorPosicionView.as_view(), name='api_top_jugadores_por_posicion'),
    path('api/equipos/', EquipoListView.as_view(), name='api_equipos'),
    path('api/equipo/<str:equipo_nombre>/', EquipoDetailView.as_view(), name='api_equipo'),
    path('api/jugador/<int:jugador_id>/', JugadorDetailView.as_view(), name='api_jugador'),
    path('api/jugador-partidos/', JugadorPartidosView.as_view(), name='api_jugador_partidos'),
    path('api/jugador-insight/', JugadorInsightView.as_view(), name='api_jugador_insight'),
    path('api/perfil/', PerfilView.as_view(), name='api_perfil'),
    path('api/perfil/update/', UpdatePerfilView.as_view(), name='api_update_perfil'),
    path('api/perfil/status/', UpdateStatusView.as_view(), name='api_update_status'),
    path('api/perfil/foto/', UploadPhotoView.as_view(), name='api_upload_photo'),
    path('api/perfil/preferencias-notificaciones/', UpdatePreferenciasNotificacionesView.as_view(), name='api_update_preferencias_notificaciones'),
    path('api/perfil/cambiar-jornada/', CambiarJornadaView.as_view(), name='api_cambiar_jornada'),
    path('api/favoritos/', FavoritosView.as_view(), name='api_favoritos'),
    path('api/favoritos/toggle-v2/', ToggleFavoritoView.as_view(), name='api_toggle_favorito_v2'),
    path('api/favoritos/seleccionar/', FavoritosView.as_view(), name='api_select_favorites'),
    path('api/favoritos/<int:fav_id>/', DeleteFavoritoView.as_view(), name='api_delete_favorito'),
    path('api/amigos/', AmigosView.as_view(), name='api_amigos'),
    path('api/amigos/solicitud/', EnviarSolicitudView.as_view(), name='api_enviar_solicitud'),
    path('api/amigos/aceptar/<int:solicitud_id>/', AceptarSolicitudView.as_view(), name='api_aceptar_solicitud'),
    path('api/amigos/rechazar/<int:solicitud_id>/', RechazarSolicitudView.as_view(), name='api_rechazar_solicitud'),
    path('api/amigos/eliminar/<int:user_id>/', EliminarAmigoView.as_view(), name='api_eliminar_amigo'),
    path('api/amigos/<int:user_id>/plantillas/', PlantillasAmigoView.as_view(), name='api_plantillas_amigo'),
    path('api/mi-plantilla/', MiPlantillaView.as_view(), name='api_mi_plantilla'),
    path('api/mi-plantilla/jugadores/', MiPlantillaJugadoresView.as_view(), name='api_mi_plantilla_jugadores'),
    path('api/plantillas/usuario/', PlantillasUsuarioView.as_view(), name='api_plantillas_usuario'),
    path('api/plantillas/usuario/<int:plantilla_id>/', PlantillaItemView.as_view(), name='api_plantilla_item'),
    path('api/plantillas/usuario/<int:plantilla_id>/renombrar/', PlantillaItemView.as_view(), name='api_plantilla_renombrar'),
    path('api/plantilla-notificaciones/<int:jornada_num>/', PlantillaNotificacionesView.as_view(), name='api_plantilla_notificaciones'),
    path('api/notificaciones/', NotificacionesView.as_view(), name='api_notificaciones'),
    path('api/notificaciones/leer-todas/', MarcarTodasLeidasView.as_view(), name='api_marcar_todas_leidas'),
    path('api/notificaciones/<int:notif_id>/leer/', MarcarNotificacionLeidaView.as_view(), name='api_marcar_notificacion_leida'),
    path('api/notificaciones/<int:notif_id>/borrar/', BorrarNotificacionView.as_view(), name='api_borrar_notificacion'),
    path('api/notificaciones/borrar-todas/', BorrarTodasNotificacionesView.as_view(), name='api_borrar_todas_notificaciones'),
    path('api/consejero/', ConsejeroView.as_view(), name='api_consejero'),
    path('api/plantilla/<int:plantilla_id>/privacidad/', TogglePrivacidadPlantillaView.as_view(), name='api_toggle_privacidad_plantilla'),
    path('api/plantilla/<int:plantilla_id>/predeterminada/', SetPlantillaPredeterminadaView.as_view(), name='api_set_plantilla_predeterminada'),
    path('api/plantillas/privacidad/', MisPlantillasPrivacidadView.as_view(), name='api_mis_plantillas_privacidad'),
    path('api/estadisticas/', EstadisticasView.as_view(), name='api_estadisticas'),
    path('api/estadisticas/comparacion/', ComparacionJugadoresView.as_view(), name='api_comparacion_jugadores'),
    path('api/v2/jugadores/', drf_views.JugadorListView.as_view(), name='v2_jugadores'),
    path('api/v2/jugadores/<int:jugador_id>/', drf_views.JugadorDetailView.as_view(), name='v2_jugador_detail'),
    path('api/v2/jugadores/<int:jugador_id>/predicciones/', drf_views.JugadorPrediccionesView.as_view(), name='v2_jugador_predicciones'),
    path('api/v2/equipos/', drf_views.EquipoListView.as_view(), name='v2_equipos'),
    path('api/v2/equipos/<str:equipo_nombre>/', drf_views.EquipoDetailView.as_view(), name='v2_equipo_detail'),
    path('api/v2/clasificacion/', drf_views.clasificacion_view, name='v2_clasificacion'),
    path('api/v2/jornadas/', drf_views.jornadas_view, name='v2_jornadas'),
    path('api/v2/predicciones/', drf_views.PrediccionCreateView.as_view(), name='v2_predicciones'),
]
