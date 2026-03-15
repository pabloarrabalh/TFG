from django.db import models
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


# ============================================================================
# CHOICES
# ============================================================================
class EstadoPartido(models.TextChoices):
    JUGADO = 'JUGADO', 'Jugado'
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APLAZADO = 'APLAZADO', 'Aplazado'


class Posicion(models.TextChoices):
    PORTERO = 'Portero', 'Portero'
    DEFENSA = 'Defensa', 'Defensa'
    CENTROCAMPISTA = 'Centrocampista', 'Centrocampista'
    DELANTERO = 'Delantero', 'Delantero'


# ============================================================================
# TABLA: TEMPORADAS
# ============================================================================
class Temporada(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Temporada'
        verbose_name_plural = 'Temporadas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# ============================================================================
# TABLA: EQUIPOS
# ============================================================================
class Equipo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    estadio = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = 'Equipo'
        verbose_name_plural = 'Equipos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# ============================================================================
# TABLA: EQUIPOS EN TEMPORADAS
# ============================================================================
class EquipoTemporada(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Equipo Temporada'
        verbose_name_plural = 'Equipos Temporada'
        unique_together = ('equipo', 'temporada')
        ordering = ['temporada', 'equipo']

    def __str__(self):
        return f"{self.equipo.nombre} - {self.temporada.nombre}"


# ============================================================================
# TABLA: JUGADORES
# ============================================================================
class Jugador(models.Model):
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150)
    nacionalidad = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Jugador'
        verbose_name_plural = 'Jugadores'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    def get_posicion_mas_frecuente(self):
        """
        Calcula la posición más frecuente del jugador en todos sus partidos.
        
        Returns:
            string: La posición más frecuente (Portero, Defensa, Centrocampista, Delantero)
                   o None si no tiene estadísticas
        """
        # Obtener conteo de posiciones en EstadisticasPartidoJugador
        posiciones = (
            self.estadisticas_partidos
            .filter(posicion__isnull=False)
            .values('posicion')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        
        if posiciones:
            return posiciones['posicion']
        return None


# ============================================================================
# TABLA: EQUIPO-JUGADOR-TEMPORADA (Plantilla jugada)
# ============================================================================
class EquipoJugadorTemporada(models.Model):
    """Almacena solo jugadores que jugaron al menos un partido en la temporada"""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='jugadores_temporada')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='equipos_temporada')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    dorsal = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(99)])
    edad = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(50)])
    partidos_jugados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Campos para almacenar percentiles precalculados (JSON)
    posicion = models.CharField(max_length=20, null=True, blank=True)  # Portero, Defensa, Centrocampista, Delantero
    percentiles = models.JSONField(default=dict, blank=True)  # { ataque: { goles: 50, ... }, ... }

    class Meta:
        verbose_name = 'Equipo Jugador Temporada'
        verbose_name_plural = 'Equipos Jugadores Temporadas'
        unique_together = ('equipo', 'jugador', 'temporada')
        ordering = ['temporada', 'equipo', 'jugador__apellido']

    def __str__(self):
        return f"{self.jugador} - {self.equipo.nombre} ({self.temporada.nombre})"


# ============================================================================
# TABLA: JORNADAS
# ============================================================================
class Jornada(models.Model):
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE, related_name='jornadas')
    numero_jornada = models.IntegerField(validators=[MinValueValidator(1)])
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Jornada'
        verbose_name_plural = 'Jornadas'
        unique_together = ('temporada', 'numero_jornada')
        ordering = ['temporada', 'numero_jornada']

    def __str__(self):
        return f"{self.temporada.nombre} - Jornada {self.numero_jornada}"


# ============================================================================
# TABLA: PARTIDOS
# ============================================================================
class Partido(models.Model):
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name='partidos')
    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local')
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visitante')
    fecha_partido = models.DateTimeField(null=True, blank=True)
    goles_local = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    goles_visitante = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    estado = models.CharField(max_length=20, choices=EstadoPartido.choices, default=EstadoPartido.PENDIENTE)

    class Meta:
        verbose_name = 'Partido'
        verbose_name_plural = 'Partidos'
        ordering = ['-fecha_partido']

    def __str__(self):
        if self.goles_local is not None and self.goles_visitante is not None:
            return f"{self.equipo_local} {self.goles_local}-{self.goles_visitante} {self.equipo_visitante}"
        return f"{self.equipo_local} vs {self.equipo_visitante}"

    def clean(self):
        if self.equipo_local == self.equipo_visitante:
            raise ValidationError("El equipo local y visitante no pueden ser el mismo")


# ============================================================================
# TABLA: CLASIFICACIÓN POR JORNADA
# ============================================================================
class ClasificacionJornada(models.Model):
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE)
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    posicion = models.IntegerField(validators=[MinValueValidator(1)])
    puntos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    goles_favor = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    goles_contra = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    diferencia_goles = models.IntegerField(default=0)
    partidos_ganados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    partidos_empatados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    partidos_perdidos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    racha_reciente = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = 'Clasificación Jornada'
        verbose_name_plural = 'Clasificaciones Jornada'
        unique_together = ('temporada', 'jornada', 'equipo')
        ordering = ['temporada', 'jornada', 'posicion']

    def __str__(self):
        return f"{self.equipo.nombre} - {self.posicion}º ({self.temporada.nombre})"


# ============================================================================
# TABLA: ESTADÍSTICAS DE PARTIDO POR JUGADOR
# ============================================================================
class EstadisticasPartidoJugador(models.Model):
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='estadisticas_jugadores')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='estadisticas_partidos')
    
    # Minutos y estado
    min_partido = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(120)])
    titular = models.BooleanField(default=False)
    
    # Goles y asistencias
    gol_partido = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    asist_partido = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Expected stats (xG, xAG)
    xg_partido = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    xag = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    
    # Tiros
    tiros = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    tiro_fallado_partido = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    tiro_puerta_partido = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Pases
    pases_totales = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    pases_completados_pct = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Tarjetas
    amarillas = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(2)])
    rojas = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    
    # Estadísticas de portero
    goles_en_contra = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    porcentaje_paradas = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    psxg = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    
    # Fantasy
    puntos_fantasy = models.IntegerField(default=0)
    
    # Entradas y duelos
    entradas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_ganados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_perdidos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Bloqueos
    bloqueos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    bloqueo_tiros = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    bloqueo_pase = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Despejes y regates
    despejes = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    regates = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    regates_completados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    regates_fallidos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Conducciones
    conducciones = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    distancia_conduccion = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    metros_avanzados_conduccion = models.FloatField(default=0.0, validators=[MinValueValidator(0)])
    conducciones_progresivas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Duelos aéreos
    duelos_aereos_ganados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_aereos_perdidos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_aereos_ganados_pct = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Balones parados y pases clave
    lanzadores_penalties = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    lanzadores_corners = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    pases_clave = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Faltas
    faltas_cometidas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    faltas_recibidas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Roles destacados (JSON array of role objects)
    roles = models.JSONField(default=list, blank=True)
    
    # Posición del jugador en el partido
    posicion = models.CharField(max_length=30, choices=Posicion.choices, null=True, blank=True)
    
    # Nacionalidad y edad del jugador en el partido
    nacionalidad = models.CharField(max_length=100, blank=True, default='')
    edad = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(50)])

    class Meta:
        verbose_name = 'Estadísticas Partido Jugador'
        verbose_name_plural = 'Estadísticas Partidos Jugadores'
        unique_together = ('partido', 'jugador')
        ordering = ['-partido__fecha_partido']

    def __str__(self):
        return f"{self.jugador} - {self.partido}"


# ============================================================================
# TABLA: CALENDARIO
# ============================================================================
class Calendario(models.Model):
    """Almacena los datos del calendario de la temporada para consultas rápidas"""
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name='calendario_matches')
    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='calendario_local')
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='calendario_visitante')
    fecha = models.DateField()
    hora = models.TimeField(null=True, blank=True)
    match_str = models.CharField(max_length=100, blank=True, default='')  # e.g., "girona vs rayo"

    class Meta:
        verbose_name = 'Calendario'
        verbose_name_plural = 'Calendarios'
        unique_together = ('jornada', 'equipo_local', 'equipo_visitante')
        ordering = ['jornada', 'fecha']

    def __str__(self):
        hora_str = self.hora.strftime('%H:%M') if self.hora else 'TBD'
        return f"{self.match_str} - {self.fecha} {hora_str}"


# ============================================================================
# TABLA: RENDIMIENTO HISTÓRICO DE JUGADORES
# ============================================================================
class RendimientoHistoricoJugador(models.Model):
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='rendimiento_historico')
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    partidos_jugados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    partidos_como_titular = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    minutos_totales = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    goles_temporada = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    asistencias_temporada = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    tarjetas_amarillas_total = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    tarjetas_rojas_total = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    pases_completados_total = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendimiento Histórico Jugador'
        verbose_name_plural = 'Rendimientos Históricos Jugadores'
        unique_together = ('jugador', 'temporada', 'equipo')
        ordering = ['-temporada', '-goles_temporada']

    def __str__(self):
        return f"{self.jugador} - {self.temporada.nombre} ({self.equipo.nombre})"

# ============================================================================
# TABLA: PERFIL DE USUARIO
# ============================================================================
class UserProfile(models.Model):
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('away', 'Ausente'),
        ('dnd', 'No molestar'),
    ]
    NOTIF_CHOICES = [
        ('all', 'Todas'),
        ('friends', 'Solo solicitudes de amistad'),
        ('events', 'Solo eventos de jugadores'),
        ('none', 'Ninguna'),
    ]
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField(max_length=100, blank=True, default='')
    foto = models.FileField(upload_to='profile_pics/', null=True, blank=True)
    estado = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    plantilla_guardada = models.TextField(blank=True, default='{}')  # JSON con la alineación guardada
    preferencias_notificaciones = models.CharField(
        max_length=10, choices=NOTIF_CHOICES, default='all'
    )
    jornada_pref = models.IntegerField(null=True, blank=True)  # Jornada preferida del usuario (None = usar actual)

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'

    def __str__(self):
        return f"{self.user.username} - {self.nickname}"


# ============================================================================
# TABLA: EQUIPOS FAVORITOS DEL USUARIO
# ============================================================================
class EquipoFavorito(models.Model):
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='equipos_favoritos')
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Equipo Favorito'
        verbose_name_plural = 'Equipos Favoritos'
        unique_together = ('usuario', 'equipo')
        ordering = ['equipo__nombre']

    def __str__(self):
        return f"{self.usuario.username} - {self.equipo.nombre}"


# ============================================================================
# TABLA: PLANTILLAS DEL USUARIO
# ============================================================================
class Plantilla(models.Model):
    PRIVACIDAD_CHOICES = [
        ('publica', 'Pública'),
        ('privada', 'Privada'),
    ]
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='plantillas')
    nombre = models.CharField(max_length=100)
    formacion = models.CharField(max_length=10, default='4-3-3')  # e.g., "4-3-3", "4-4-2"
    alineacion = models.JSONField(default=dict)  # Almacena posiciones y jugadores
    fecha_creada = models.DateTimeField(auto_now_add=True)
    fecha_modificada = models.DateTimeField(auto_now=True)
    privacidad = models.CharField(max_length=10, choices=PRIVACIDAD_CHOICES, default='publica')
    predeterminada = models.BooleanField(default=False)  # Solo una por usuario para notificaciones

    class Meta:
        verbose_name = 'Plantilla'
        verbose_name_plural = 'Plantillas'
        unique_together = ('usuario', 'nombre')
        ordering = ['-fecha_modificada']

    def __str__(self):
        return f"{self.usuario.username} - {self.nombre}"


# ============================================================================
# TABLA: SOLICITUDES DE AMISTAD
# ============================================================================
class SolicitudAmistad(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]
    emisor = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='solicitudes_enviadas')
    receptor = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='solicitudes_recibidas')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='pendiente')
    fecha_creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Solicitud de Amistad'
        verbose_name_plural = 'Solicitudes de Amistad'
        unique_together = ('emisor', 'receptor')
        ordering = ['-fecha_creada']

    def __str__(self):
        return f"{self.emisor.username} → {self.receptor.username} ({self.estado})"


# ============================================================================
# TABLA: AMISTADES
# ============================================================================
class Amistad(models.Model):
    usuario1 = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='amistades_como_usuario1')
    usuario2 = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='amistades_como_usuario2')
    fecha_creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Amistad'
        verbose_name_plural = 'Amistades'
        unique_together = ('usuario1', 'usuario2')
        ordering = ['-fecha_creada']

    def __str__(self):
        return f"{self.usuario1.username} ↔ {self.usuario2.username}"


# ============================================================================
# TABLA: NOTIFICACIONES
# ============================================================================
class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('solicitud_amistad', 'Solicitud de amistad'),
        ('evento_jugador', 'Evento de jugador'),
    ]
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True, default='')
    leida = models.BooleanField(default=False)
    fecha_creada = models.DateTimeField(auto_now_add=True)
    # Datos extra en JSON (e.g., solicitud_id, jugador_id, etc.)
    datos = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_creada']

    def __str__(self):
        return f"[{self.tipo}] {self.usuario.username}: {self.titulo}"


# ============================================================================
# TABLA: PREDICCIONES DE JUGADORES
# ============================================================================
class PrediccionJugador(models.Model):
    """Almacena predicciones de puntos fantasy por jugador y jornada.
    Permite comparar prediccion vs resultado real en la vista de jugador.
    Se recomienda DB sobre Redis porque las predicciones son datos históricos valiosos
    (comparación pred vs real, auditoría de modelos, gráficas temporales).
    """
    MODELOS = [
        ('xgb', 'XGBoost'),
        ('rf', 'Random Forest'),
        ('lgbm', 'LightGBM'),
        ('ridge', 'Ridge Regression'),
        ('baseline', 'Baseline (Media)'),
    ]

    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='predicciones')
    jornada = models.ForeignKey('Jornada', on_delete=models.CASCADE, related_name='predicciones_jugadores')
    prediccion = models.FloatField(help_text='Puntos fantasy predichos')
    modelo = models.CharField(max_length=10, choices=MODELOS, default='rf')
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Predicción Jugador'
        verbose_name_plural = 'Predicciones Jugadores'
        unique_together = [['jugador', 'jornada', 'modelo']]
        ordering = ['-jornada__temporada__nombre', 'jornada__numero_jornada']

    def __str__(self):
        return f"{self.jugador} | J{self.jornada.numero_jornada} | {self.modelo}: {self.prediccion:.1f}"


# ============================================================================
# TABLA: PREDICCIONES PENDIENTES (para generación en background/on-demand)
# ============================================================================
class PedidoPrediccion(models.Model):
    """Trackea predicciones pendientes de generar.
    - PENDING: Falta generar (background queue)
    - GENERATED: Ya existe predicción
    - FAILED: Error en generación
    """
    ESTADO_CHOICES = [
        ('pending', 'Pendiente'),
        ('generated', 'Generada'),
        ('failed', 'Error'),
    ]

    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='pedidos_prediccion')
    jornada = models.ForeignKey('Jornada', on_delete=models.CASCADE, related_name='pedidos_prediccion')
    temporada = models.ForeignKey('Temporada', on_delete=models.CASCADE, related_name='pedidos_prediccion')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='pending')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    intentos = models.IntegerField(default=0)
    motivo_error = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Pedido Predicción'
        verbose_name_plural = 'Pedidos Predicción'
        unique_together = [['jugador', 'jornada', 'temporada']]
        indexes = [
            models.Index(fields=['estado', 'temporada'], name='pred_estado_temp_idx'),
            models.Index(fields=['jugador', 'estado'], name='pred_jugador_estado_idx'),
        ]
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.jugador} | J{self.jornada.numero_jornada} | {self.estado}"