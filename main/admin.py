from django.contrib import admin
from .models import SolicitudAmistad, Amistad, Notificacion, PrediccionJugador

@admin.register(SolicitudAmistad)
class SolicitudAmistadAdmin(admin.ModelAdmin):
    list_display = ('emisor', 'receptor', 'estado', 'fecha_creada')
    list_filter = ('estado',)

@admin.register(Amistad)
class AmistadAdmin(admin.ModelAdmin):
    list_display = ('usuario1', 'usuario2', 'fecha_creada')

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'titulo', 'leida', 'fecha_creada')
    list_filter = ('tipo', 'leida')

@admin.register(PrediccionJugador)
class PrediccionJugadorAdmin(admin.ModelAdmin):
    list_display = ('jugador', 'jornada', 'modelo', 'prediccion', 'creada_en')
    list_filter = ('modelo', 'jornada__temporada')
    search_fields = ('jugador__nombre', 'jugador__apellido')
    ordering = ('-jornada__temporada__nombre', 'jornada__numero_jornada')
