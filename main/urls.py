from django.urls import path
from . import views
from . import api_endpoints
from . import api_views  # legacy proxy – kept for backwards compat
from . import drf_views

# ── DRF API v1 views ────────────────────────────────────────────────────────
from .api.auth import MeView, LoginView, LogoutView, RegisterView
from .api.menu import MenuView, MenuTopJugadoresView
from .api.clasificacion import ClasificacionView
from .api.equipo import EquipoListView, EquipoDetailView
from .api.jugador import JugadorDetailView, TopJugadoresPorPosicionView
from .api.jugador_partidos import JugadorPartidosView
from .api.jugador_insight import JugadorInsightView
from .api.perfil import (
    PerfilView, UpdatePerfilView, UpdateStatusView,
    UploadPhotoView, UpdatePreferenciasNotificacionesView,
    CambiarJornadaView,
)
from .api.favoritos import FavoritosView, ToggleFavoritoView, DeleteFavoritoView
from .api.amigos import (
    AmigosView, EnviarSolicitudView, AceptarSolicitudView,
    RechazarSolicitudView, EliminarAmigoView, PlantillasAmigoView,
)
from .api.plantilla import (
    MiPlantillaView, MiPlantillaJugadoresView,
    TogglePrivacidadPlantillaView, SetPlantillaPredeterminadaView,
    MisPlantillasPrivacidadView,
)
from .api.plantilla_notificaciones import PlantillaNotificacionesView
from .api.notificaciones import (
    NotificacionesView, MarcarNotificacionLeidaView, MarcarTodasLeidasView,
    BorrarNotificacionView, BorrarTodasNotificacionesView,
)
from .api.estadisticas import EstadisticasView, ComparacionJugadoresView
from .api.consejero import ConsejeroView

urlpatterns = [
    path('', views.menu, name='menu'),
    path('equipos/', views.equipos, name='equipos'),
    path('favoritos/select/', views.select_favorite_teams, name='select_favorite_teams'),
    path('favoritos/toggle/', views.toggle_favorite_team, name='toggle_favorite_team'),
    path('mi-plantilla/', views.mi_plantilla, name='mi_plantilla'),
    path('clasificacion/', views.clasificacion, name='clasificacion'),
    path('equipo/<str:equipo_nombre>/', views.equipo, name='equipo'),
    path('equipo/<str:equipo_nombre>/<str:temporada>/', views.equipo, name='equipo_temporada'),
    path('jugador/', views.jugador, name='jugador'),
    path('jugador/<int:jugador_id>/', views.jugador, name='jugador_detail'),
    path('jugador/<int:jugador_id>/<str:temporada>/', views.jugador, name='jugador_temporada'),
    path('amigos/', views.amigos, name='amigos'),
    path('login/', views.login_register, name='login_register'),
    path('login/submit/', views.login_view, name='login'),
    path('register/submit/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_usuario, name='perfil'),
    path('perfil/upload-photo/', views.upload_profile_photo, name='upload_profile_photo'),
    path('perfil/update/', views.update_profile, name='update_profile'),
    path('perfil/update-status/', views.update_user_status, name='update_user_status'),
    path('perfil/delete-favorite/<int:fav_id>/', views.delete_favorite_team, name='delete_favorite_team'),
    path('mi-plantilla/guardar/', views.guardar_plantilla, name='guardar_plantilla'),
    path('mi-plantilla/listar/', views.listar_plantillas, name='listar_plantillas'),
    path('mi-plantilla/<int:plantilla_id>/', views.obtener_plantilla, name='obtener_plantilla'),
    path('mi-plantilla/<int:plantilla_id>/eliminar/', views.eliminar_plantilla, name='eliminar_plantilla'),
    path('mi-plantilla/<int:plantilla_id>/renombrar/', views.renombrar_plantilla, name='renombrar_plantilla'),
    path('terms-conditions/', views.terms_conditions, name='terms_conditions'),
    # API Endpoints (existing)
    path('api/radar/<int:jugador_id>/<str:temporada>/', api_endpoints.api_radar_jugador, name='api_radar_jugador'),
    path('api/buscar/', api_endpoints.api_buscar, name='api_buscar'),
    path('api/favoritos/toggle/', api_endpoints.api_toggle_favorito, name='api_toggle_favorito'),
    path('api/predecir-portero/', views.predecir_portero_api, name='predecir_portero_api'),
    path('api/predecir-jugador/', views.predecir_jugador_api, name='predecir_jugador_api'),
    path('api/explicar-prediccion/', views.explicar_prediccion_portero_api, name='explicar_prediccion_portero_api'),
    path('api/cambiar-jornada/', views.cambiar_jornada_api, name='cambiar_jornada_api'),

    # ── REST API v1 (DRF) ─────────────────────────────────────────────────────
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

    # ── REST API v2 (DRF) ────────────────────────────────────────────────────
    # Jugadores
    path('api/v2/jugadores/', drf_views.JugadorListView.as_view(), name='v2_jugadores'),
    path('api/v2/jugadores/<int:jugador_id>/', drf_views.JugadorDetailView.as_view(), name='v2_jugador_detail'),
    path('api/v2/jugadores/<int:jugador_id>/predicciones/', drf_views.JugadorPrediccionesView.as_view(), name='v2_jugador_predicciones'),
    # Equipos
    path('api/v2/equipos/', drf_views.EquipoListView.as_view(), name='v2_equipos'),
    path('api/v2/equipos/<str:equipo_nombre>/', drf_views.EquipoDetailView.as_view(), name='v2_equipo_detail'),
    # Otros recursos
    path('api/v2/clasificacion/', drf_views.clasificacion_view, name='v2_clasificacion'),
    path('api/v2/jornadas/', drf_views.jornadas_view, name='v2_jornadas'),
    # Predicciones (escritura autenticada)
    path('api/v2/predicciones/', drf_views.PrediccionCreateView.as_view(), name='v2_predicciones'),
]
