import pandas as pd
from django.db.models import Count

from main.models import (
    Equipo,
    EquipoJugadorTemporada,
    EquipoTemporada,
    EstadisticasPartidoJugador,
    Jornada,
    Jugador,
    Partido,
    Temporada,
)
from main.scrapping.commons import normalizar_equipo_bd


def obtener_o_crear_temporada(codigo):
    """Obtiene o crea una Temporada."""
    temporada, _ = Temporada.objects.get_or_create(nombre=codigo)
    return temporada


def obtener_o_crear_equipo(nombre_csv):
    """Obtiene o crea un Equipo."""
    nombre_normalizado = normalizar_equipo_bd(nombre_csv)
    equipo, _ = Equipo.objects.get_or_create(
        nombre=nombre_normalizado,
        defaults={"estadio": ""},
    )
    return equipo


def obtener_o_crear_equipo_temporada(equipo, temporada):
    """Obtiene o crea EquipoTemporada."""
    eq_temp, _ = EquipoTemporada.objects.get_or_create(
        equipo=equipo,
        temporada=temporada,
    )
    return eq_temp


def obtener_o_crear_jornada(temporada, numero_jornada):
    """Obtiene o crea una Jornada."""
    jornada, _ = Jornada.objects.get_or_create(
        temporada=temporada,
        numero_jornada=numero_jornada,
        defaults={"fecha_inicio": None, "fecha_fin": None},
    )
    return jornada


def obtener_o_crear_jugador(nombre_completo, posicion_csv, nacionalidad=""):
    """Obtiene o crea un Jugador con nacionalidad."""
    _ = posicion_csv  # Conservamos la firma para compatibilidad.

    partes = nombre_completo.strip().split()
    if len(partes) >= 2:
        nombre = " ".join(partes[:-1])
        apellido = partes[-1]
    else:
        nombre = nombre_completo
        apellido = ""

    jugador, created = Jugador.objects.get_or_create(
        nombre=nombre,
        apellido=apellido,
        defaults={"nacionalidad": nacionalidad},
    )

    if not created and nacionalidad and jugador.nacionalidad != nacionalidad:
        jugador.nacionalidad = nacionalidad
        jugador.save(update_fields=["nacionalidad"])

    return jugador


def obtener_o_crear_equipo_jugador_temporada(jugador, equipo, temporada, dorsal):
    """Obtiene o crea EquipoJugadorTemporada y actualiza el dorsal."""
    dorsal_limpio = 0
    if pd.notna(dorsal):
        try:
            dorsal_int = int(dorsal)
            if 0 <= dorsal_int <= 99:
                dorsal_limpio = dorsal_int
        except (TypeError, ValueError):
            pass

    ejt, created = EquipoJugadorTemporada.objects.get_or_create(
        jugador=jugador,
        equipo=equipo,
        temporada=temporada,
        defaults={"dorsal": dorsal_limpio},
    )

    if not created and ejt.dorsal != dorsal_limpio:
        ejt.dorsal = dorsal_limpio
        ejt.save(update_fields=["dorsal"])

    return ejt


def obtener_o_crear_partido(jornada, equipo_local, equipo_visitante, fecha_partido):
    """Obtiene o crea un Partido."""
    partido, _ = Partido.objects.get_or_create(
        jornada=jornada,
        equipo_local=equipo_local,
        equipo_visitante=equipo_visitante,
        defaults={"fecha_partido": fecha_partido, "estado": "JUGADO"},
    )
    return partido


def _puntos_fantasy_sin_outlier(row, jugador, umbral=40, fallback=6):
    """
    Devuelve el valor de puntos_fantasy a guardar.
    Si el valor del CSV supera el umbral (outlier), usa la moda histórica
    del jugador en la BD (excluyendo outliers). Si no hay historial, devuelve fallback.
    """
    raw = int(row["puntos_fantasy"]) if pd.notna(row.get("puntos_fantasy")) else 0
    if raw <= umbral:
        return raw

    moda = (
        EstadisticasPartidoJugador.objects.filter(jugador=jugador, puntos_fantasy__lte=umbral)
        .values("puntos_fantasy")
        .annotate(cnt=Count("id"))
        .order_by("-cnt", "puntos_fantasy")
        .first()
    )
    return moda["puntos_fantasy"] if moda else fallback
