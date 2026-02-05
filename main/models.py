from django.db import models
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
    estadio = models.CharField(max_length=150)

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
    posicion = models.CharField(max_length=30, choices=Posicion.choices)
    nacionalidad = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Jugador'
        verbose_name_plural = 'Jugadores'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# ============================================================================
# TABLA: HISTORIAL DE EQUIPOS DE JUGADORES
# ============================================================================
class HistorialEquiposJugador(models.Model):
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='historial_equipos')
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    dorsal = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    edad = models.IntegerField(validators=[MinValueValidator(15), MaxValueValidator(50)])
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Historial Equipos Jugador'
        verbose_name_plural = 'Historiales Equipos Jugadores'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"{self.jugador} - {self.equipo} ({self.temporada})"


# ============================================================================
# TABLA: JORNADAS
# ============================================================================
class Jornada(models.Model):
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE, related_name='jornadas')
    numero_jornada = models.IntegerField(validators=[MinValueValidator(1)])
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)

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
        from django.core.exceptions import ValidationError
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
    minutos_jugados = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(120)])
    goles = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    asistencias = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    disparos = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    disparos_a_puerta = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    pases_completados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    pases_totales = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    regates = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    despejes = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    faltas_cometidas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    tarjetas_amarillas = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(2)])
    tarjetas_rojas = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    recuperaciones = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    intercepciones = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    entradas = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_ganados = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    duelos_totales = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    calificacion_decimal = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    en_alineacion = models.BooleanField(default=True)
    fue_suplente = models.BooleanField(default=False)
    minuto_salida = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(120)])
    minuto_entrada = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(120)])
    gol_en_propia_puerta = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Estadísticas Partido Jugador'
        verbose_name_plural = 'Estadísticas Partidos Jugadores'
        unique_together = ('partido', 'jugador')
        ordering = ['-partido__fecha_partido']

    def __str__(self):
        return f"{self.jugador} - {self.partido}"


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
    promedio_calificacion = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    pases_completados_total = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    goles_en_propia_puerta_total = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendimiento Histórico Jugador'
        verbose_name_plural = 'Rendimientos Históricos Jugadores'
        unique_together = ('jugador', 'temporada')
        ordering = ['-temporada', '-goles_temporada']

    def __str__(self):
        return f"{self.jugador} - {self.temporada.nombre} ({self.equipo.nombre})"
