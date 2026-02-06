from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('mi-plantilla/', views.mi_plantilla, name='mi_plantilla'),
    path('clasificacion/', views.clasificacion, name='clasificacion'),
    path('equipo/<str:equipo_nombre>/', views.equipo, name='equipo'),
    path('jugador/', views.jugador, name='jugador'),
    path('amigos/', views.amigos, name='amigos'),
    path('login/', views.login_register, name='login_register'),
]