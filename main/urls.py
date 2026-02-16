from django.urls import path
from . import views
from . import api_endpoints

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
    # API Endpoints
    path('api/radar/<int:jugador_id>/<str:temporada>/', api_endpoints.api_radar_jugador, name='api_radar_jugador'),
    path('api/buscar/', api_endpoints.api_buscar, name='api_buscar'),
    path('api/favoritos/toggle/', api_endpoints.api_toggle_favorito, name='api_toggle_favorito'),
]