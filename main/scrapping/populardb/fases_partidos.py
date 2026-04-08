import glob
import logging
import os

import pandas as pd
import requests
from django.conf import settings

from main.models import Equipo, EstadisticasPartidoJugador, Jornada, Partido
from main.scrapping.alias import MAPEO_POSICIONES_INVERSO
from main.scrapping.commons import normalizar_equipo_bd, parsear_fecha
from main.scrapping.transfermarkt import (
    extraer_hrefs_equipos_desde_clasificacion,
    mapear_equipo_tm_a_bd,
    obtener_plantilla_equipo,
    procesar_plantilla_equipo,
)

from .helpers import (
    _puntos_fantasy_sin_outlier,
    obtener_o_crear_equipo,
    obtener_o_crear_equipo_jugador_temporada,
    obtener_o_crear_equipo_temporada,
    obtener_o_crear_jornada,
    obtener_o_crear_jugador,
    obtener_o_crear_partido,
    obtener_o_crear_temporada,
)


def procesar_csv_partido(ruta_csv, temporada):
    """Procesa un CSV de partido y carga los datos con bulk_create para perf."""
    _log = logging.getLogger(__name__)
    try:
        df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    except Exception as e:
        return False

    if df.empty:
        return False

    stats_to_create = []
    try:
        primera_fila = df.iloc[0]
        jornada_num = int(primera_fila["jornada"])
        fecha_partido = parsear_fecha(primera_fila["fecha_partido"])
        equipo_local_nombre = normalizar_equipo_bd(
            primera_fila["equipo_propio"]
            if bool(primera_fila["local"])
            else primera_fila["equipo_rival"]
        )
        equipo_visitante_nombre = normalizar_equipo_bd(
            primera_fila["equipo_rival"]
            if bool(primera_fila["local"])
            else primera_fila["equipo_propio"]
        )

        jornada = obtener_o_crear_jornada(temporada, jornada_num)
        equipo_local = obtener_o_crear_equipo(equipo_local_nombre)
        equipo_visitante = obtener_o_crear_equipo(equipo_visitante_nombre)
        obtener_o_crear_equipo_temporada(equipo_local, temporada)
        obtener_o_crear_equipo_temporada(equipo_visitante, temporada)

        partido = obtener_o_crear_partido(jornada, equipo_local, equipo_visitante, fecha_partido)

        for _, row in df.iterrows():
            try:
                nombre_jugador = row["player"]
                posicion = row["posicion"]
                nacionalidad = row.get("nacionalidad", "")
                equipo_nombre = row["equipo_propio"]
                dorsal = row["dorsal"]

                equipo = obtener_o_crear_equipo(equipo_nombre)
                obtener_o_crear_equipo_temporada(equipo, temporada)
                jugador = obtener_o_crear_jugador(nombre_jugador, posicion, nacionalidad)
                obtener_o_crear_equipo_jugador_temporada(jugador, equipo, temporada, dorsal)

                posicion_codigo = row.get("posicion") if pd.notna(row.get("posicion")) else None
                posicion_norm = MAPEO_POSICIONES_INVERSO.get(posicion_codigo) if posicion_codigo else None
                edad = None
                if pd.notna(row.get("edad")):
                    try:
                        edad = int(row["edad"])
                    except (TypeError, ValueError):
                        edad = None

                stat_obj = EstadisticasPartidoJugador(
                    partido=partido,
                    jugador=jugador,
                    nacionalidad=nacionalidad,
                    edad=edad,
                    min_partido=int(row["min_partido"]) if pd.notna(row["min_partido"]) else 0,
                    titular=bool(row["titular"]) if pd.notna(row["titular"]) else False,
                    gol_partido=int(row["gol_partido"]) if pd.notna(row["gol_partido"]) else 0,
                    asist_partido=int(row["asist_partido"]) if pd.notna(row["asist_partido"]) else 0,
                    xg_partido=float(row["xg_partido"]) if pd.notna(row["xg_partido"]) else 0.0,
                    xag=float(row["xag"]) if pd.notna(row["xag"]) else 0.0,
                    tiros=int(row["tiros"]) if pd.notna(row["tiros"]) else 0,
                    tiro_fallado_partido=int(row["tiro_fallado_partido"])
                    if pd.notna(row["tiro_fallado_partido"])
                    else 0,
                    tiro_puerta_partido=int(row["tiro_puerta_partido"])
                    if pd.notna(row["tiro_puerta_partido"])
                    else 0,
                    pases_totales=int(row["pases_totales"]) if pd.notna(row["pases_totales"]) else 0,
                    pases_completados_pct=float(row["pases_completados_pct"])
                    if pd.notna(row["pases_completados_pct"])
                    else 0.0,
                    amarillas=int(row["amarillas"]) if pd.notna(row["amarillas"]) else 0,
                    rojas=int(row["rojas"]) if pd.notna(row["rojas"]) else 0,
                    goles_en_contra=int(row["goles_en_contra"]) if pd.notna(row["goles_en_contra"]) else 0,
                    porcentaje_paradas=float(row["porcentaje_paradas"])
                    if pd.notna(row["porcentaje_paradas"])
                    else 0.0,
                    psxg=float(row["psxg"]) if pd.notna(row["psxg"]) else 0.0,
                    puntos_fantasy=_puntos_fantasy_sin_outlier(row, jugador),
                    entradas=int(row["entradas"]) if pd.notna(row["entradas"]) else 0,
                    duelos=int(row["duelos"]) if pd.notna(row["duelos"]) else 0,
                    duelos_ganados=int(row["duelos_ganados"]) if pd.notna(row["duelos_ganados"]) else 0,
                    duelos_perdidos=int(row["duelos_perdidos"]) if pd.notna(row["duelos_perdidos"]) else 0,
                    bloqueos=int(row["bloqueos"]) if pd.notna(row["bloqueos"]) else 0,
                    bloqueo_tiros=int(row["bloqueo_tiros"]) if pd.notna(row["bloqueo_tiros"]) else 0,
                    bloqueo_pase=int(row["bloqueo_pase"]) if pd.notna(row["bloqueo_pase"]) else 0,
                    despejes=int(row["despejes"]) if pd.notna(row["despejes"]) else 0,
                    regates=int(row["regates"]) if pd.notna(row["regates"]) else 0,
                    regates_completados=int(row["regates_completados"])
                    if pd.notna(row["regates_completados"])
                    else 0,
                    regates_fallidos=int(row["regates_fallidos"]) if pd.notna(row["regates_fallidos"]) else 0,
                    conducciones=int(row["conducciones"]) if pd.notna(row["conducciones"]) else 0,
                    distancia_conduccion=float(row["distancia_conduccion"])
                    if pd.notna(row["distancia_conduccion"])
                    else 0.0,
                    metros_avanzados_conduccion=float(row["metros_avanzados_conduccion"])
                    if pd.notna(row["metros_avanzados_conduccion"])
                    else 0.0,
                    conducciones_progresivas=int(row["conducciones_progresivas"])
                    if pd.notna(row["conducciones_progresivas"])
                    else 0,
                    duelos_aereos_ganados=int(row["duelos_aereos_ganados"])
                    if pd.notna(row["duelos_aereos_ganados"])
                    else 0,
                    duelos_aereos_perdidos=int(row["duelos_aereos_perdidos"])
                    if pd.notna(row["duelos_aereos_perdidos"])
                    else 0,
                    duelos_aereos_ganados_pct=float(row["duelos_aereos_ganados_pct"])
                    if pd.notna(row["duelos_aereos_ganados_pct"])
                    else 0.0,
                    posicion=posicion_norm,
                    roles=[],
                )
                stats_to_create.append(stat_obj)
            except Exception:
                continue

        if stats_to_create:
            EstadisticasPartidoJugador.objects.bulk_create(
                stats_to_create,
                batch_size=5000,
                ignore_conflicts=True,
            )

        return True
    except Exception as e:
        return False


def fase_0a_crear_todas_las_jornadas():
    """
    FASE 0a: Crea TODAS las jornadas (1-38) para cada temporada.
    Se ejecuta PRIMERO para que existan las jornadas aunque no haya partidos jugados aún.
    """
    _log = logging.getLogger(__name__)
    _log.info("[FASE 0a] Creando jornadas...")

    for temp_codigo in ("23_24", "24_25", "25_26"):
        temporada = obtener_o_crear_temporada(temp_codigo)
        _log.info("[FASE 0a] Creando temporada: %s", temporada.nombre)
        
        for num_jornada in range(1, 39):
            Jornada.objects.get_or_create(
                temporada=temporada,
                numero_jornada=num_jornada,
                defaults={"fecha_inicio": None, "fecha_fin": None},
            )
        _log.info("[FASE 0a] Temporada %s: 38 jornadas creadas OK", temporada.nombre)

    _log.info("[FASE 0a] Jornadas OK: %d en BD", Jornada.objects.count())


def fase_0_scrapear_plantillas_y_estadios():
    """
    FASE 0: Scrapea plantillas desde Transfermarkt para MÚLTIPLES TEMPORADAS
    y actualiza estadios en BD para cada una.
    """
    _log = logging.getLogger(__name__)
    _log.info("[FASE 0] Scrapando plantillas Transfermarkt...")

    temporadas_to_scrap = [
        (2023, "23_24"),
        (2024, "24_25"),
        (2025, "25_26"),
    ]

    estadios_actualizados = 0

    try:
        base_url = "https://www.transfermarkt.es/laliga/spieltagtabelle/wettbewerb/ES1"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for saison_id, temp_nombre in temporadas_to_scrap:
            _log.info("[FASE 0] Scrapeando temporada: %s", temp_nombre)
            
            try:
                resp = requests.get(f"{base_url}?saison_id={saison_id}", headers=headers, timeout=15)
                if resp.status_code != 200:
                    _log.warning("[FASE 0] No se pudo acceder a la temporada %s", temp_nombre)
                    continue
            except Exception as e:
                _log.warning("[FASE 0] Error scrapeando %s: %s", temp_nombre, e)
                continue

            equipos_href = extraer_hrefs_equipos_desde_clasificacion(resp.text)
            if not equipos_href:
                _log.warning("[FASE 0] No se encontraron equipos en %s", temp_nombre)
                continue

            equipos_revisados = 0
            estadios_actualizados_temp = 0
            for equipo_norm, href in equipos_href.items():
                try:
                    equipos_revisados += 1
                    _log.info("[FASE 0] Procesando equipo: %s", equipo_norm)
                    html = obtener_plantilla_equipo(href, saison_id=saison_id, delay_min=1, delay_max=2)
                    if not html:
                        continue

                    _, estadio = procesar_plantilla_equipo(html, equipo_norm)
                    if not estadio:
                        continue

                    equipo_bd_nombre = mapear_equipo_tm_a_bd(equipo_norm)
                    equipo_obj = Equipo.objects.filter(nombre=equipo_bd_nombre).first()
                    if equipo_obj and equipo_obj.estadio != estadio:
                        equipo_obj.estadio = estadio
                        equipo_obj.save(update_fields=["estadio"])
                        estadios_actualizados += 1
                        estadios_actualizados_temp += 1
                        _log.info("[FASE 0] Equipo %s: estadio actualizado a '%s'", equipo_bd_nombre, estadio)
                except Exception as e:
                    _log.debug("[FASE 0] Error procesando %s: %s", equipo_norm, e)
                    pass

            _log.info(
                "[FASE 0] Temporada %s completada: %d equipos revisados, %d estadios actualizados",
                temp_nombre,
                equipos_revisados,
                estadios_actualizados_temp,
            )

        equipos_con_estadio = Equipo.objects.exclude(estadio__exact="").count()
        equipos_total = Equipo.objects.count()
        _log.info(
            "[FASE 0] Estadios: %d/%d equipos (%d actualizados en scrape)",
            equipos_con_estadio,
            equipos_total,
            estadios_actualizados,
        )
        return True

    except Exception as e:
        _log.warning("[FASE 0] Falló - continuando: %s", e)
        return False


def fase_1_cargar_partidos_y_estadisticas():
    """FASE 1: Carga partidos y estadísticas iniciales."""
    _log = logging.getLogger(__name__)
    _log.info("[FASE 1] Cargando partidos y estadísticas...")

    temp_23_24 = obtener_o_crear_temporada("23_24")
    temp_24_25 = obtener_o_crear_temporada("24_25")
    temp_25_26 = obtener_o_crear_temporada("25_26")

    data_dir = os.path.join(settings.BASE_DIR, "data")

    temporadas_obj_map = {
        "temporada_23_24": temp_23_24,
        "temporada_24_25": temp_24_25,
        "temporada_25_26": temp_25_26,
    }

    total_csvs = 0
    for temp_dir, temp_obj in temporadas_obj_map.items():
        pattern = os.path.join(data_dir, temp_dir, "jornada_*", "p*.csv")
        csvs = sorted(glob.glob(pattern))
        
        csvs_temp = 0
        for idx, csv_path in enumerate(csvs, start=1):
            archivo = os.path.basename(csv_path)
            _log.info("[FASE 1] CSV %d/%d -> %s", idx, len(csvs), archivo)
            if procesar_csv_partido(csv_path, temp_obj):
                csvs_temp += 1
                total_csvs += 1
        
        _log.info("[FASE 1] Temporada %s: %d/%d CSVs procesados", temp_obj.nombre, csvs_temp, len(csvs))

    _log.info(
        "[FASE 1] OK: %d CSVs - %d partidos, %d stats",
        total_csvs,
        Partido.objects.count(),
        EstadisticasPartidoJugador.objects.count(),
    )
    actualizar_fechas_jornadas()


def actualizar_fechas_jornadas():
    """Actualiza fecha_inicio y fecha_fin de cada jornada con datos de partidos cargados."""
    _log = logging.getLogger(__name__)

    jornadas_actualizadas = 0

    for jornada in Jornada.objects.all():
        partidos = Partido.objects.filter(jornada=jornada, fecha_partido__isnull=False).only("fecha_partido")
        fechas = [p.fecha_partido for p in partidos if p.fecha_partido]

        if not fechas:
            continue

        jornada.fecha_inicio = min(fechas)
        jornada.fecha_fin = max(fechas)
        jornada.save(update_fields=["fecha_inicio", "fecha_fin"])
        jornadas_actualizadas += 1

    _log.info("[FASE 1] Jornadas con fechas actualizadas: %d", jornadas_actualizadas)
