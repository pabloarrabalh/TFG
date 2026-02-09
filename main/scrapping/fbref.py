"""
Módulo para scraping y análisis de datos de FBref.

Este módulo procesa datos de partidos de FBref y los combina con información
de Fantasy para generar datasets de entrenamiento.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import re
from io import StringIO
import logging
from datetime import datetime
import time
import json

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from main.scrapping.commons import *
from main.scrapping.alias import *
from main.scrapping.roles import ROLES_DESTACADOS
from main.scrapping.matching import generar_propuestas, resolver_matching


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TEMPORADA_ACTUAL = "25_26"
CARPETA_HTML, CARPETA_CSV = construir_rutas_temporada(TEMPORADA_ACTUAL)

MAPEO_POSICIONES_FANTASY = {
    "Portero": "PT",
    "Defensa": "DF",
    "Mediocampista": "MC",
    "Centrocampista": "MC",
    "Delantero": "DT",
}


def buscar_estadisticas_portero(estadisticas_porteros, resumen_stats, clave_jugador):
    """
    Busca las estadísticas de un portero en los datos de porteros o resumen.
    
    Args:
        estadisticas_porteros: Diccionario con estadísticas de porteros
        resumen_stats: Diccionario con estadísticas resumidas
        clave_jugador: Clave del jugador a buscar
    
    Returns:
        Fila de estadísticas del portero o None
    """
    fila_portero = estadisticas_porteros.get(clave_jugador)
    if fila_portero is not None:
        return fila_portero

    fila_resumen = resumen_stats.get(clave_jugador)
    if fila_resumen is not None:
        nombre_raw = limpiar_minuto(str(fila_resumen.get("Player", "")).strip())
        apellido_base = nombre_raw
    else:
        apellido_base = clave_jugador

    # Búsqueda por apellido cuando no hay match exacto
    apellido = normalizar_texto(apellido_base).split()[-1]
    for clave_portero, fila_portero in estadisticas_porteros.items():
        if not clave_portero:
            continue
        apellido_portero = normalizar_texto(clave_portero).split()[-1]
        if apellido_portero == apellido:
            return fila_portero

    return None


def parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante, tipo_tabla=None):
    """
    Parsea una tabla HTML de FBref y extrae información de jugadores.
    
    Args:
        tabla_html: Elemento BeautifulSoup con la tabla
        equipo_local: Nombre del equipo local
        equipo_visitante: Nombre del equipo visitante
        tipo_tabla: Tipo de tabla (summary, keepers, etc)
    
    Returns:
        Dict {nombre_normalizado: fila_stats}
    """
    caption = tabla_html.find("caption")
    texto_caption = caption.get_text(strip=True) if caption else ""

    nombre_equipo = None
    if texto_caption.endswith("Player Stats Table"):
        nombre_equipo = texto_caption.replace(" Player Stats Table", "").strip()

    try:
        df = pd.read_html(StringIO(str(tabla_html)))[0]
    except Exception:
        return {}

    # Normalizar nombres de columnas
    nombres_columnas = []
    for col in df.columns.get_level_values(-1):
        nombre_col = str(col).split(",")[-1].strip(" ()'").replace(" ", "")
        nombres_columnas.append(nombre_col)
    df.columns = nombres_columnas

    id_tabla = tabla_html.get("id", "")
    jugadores = {}

    # Procesar filas del dataframe
    for _, fila in df.iterrows():
        nombre_jugador = str(fila["Player"]).strip()
        
        # Saltar fila de resumen "11 Players" al final de los jugadores
        if re.match(r"^\d+\s+Players$", nombre_jugador):
            continue

        if nombre_equipo:
            equipo = nombre_equipo
        elif "_home_" in id_tabla:
            equipo = equipo_local
        elif "_away_" in id_tabla:
            equipo = equipo_visitante
        else:
            equipo = ""

        equipo_norm = normalizar_equipo_temporada(equipo)
        jugador_con_alias = aplicar_alias_jugador_temporada(nombre_jugador, equipo_norm, TEMPORADA_ACTUAL)
        nombre_norm = normalizar_texto(jugador_con_alias)
        nombre_base_norm = normalizar_texto(nombre_jugador)

        fila_copia = fila.copy()
        fila_copia["__nombre_norm"] = nombre_norm
        fila_copia["__equipo_norm"] = equipo_norm
        
        # Extraer nacionalidad de la columna "Nation" (ej: "co COL")
        nacionalidad = ""
        if "Nation" in fila.index:
            val = fila["Nation"]
            if pd.notna(val):
                texto = str(val).strip()
                partes = texto.split()
                nacionalidad = partes[-1] if partes else ""
        fila_copia["__nacionalidad"] = nacionalidad
        
        # Extraer edad de la columna "Age" (ej: "21-269" -> 21)
        edad = None
        if "Age" in fila.index:
            val = fila["Age"]
            if pd.notna(val):
                texto = str(val).strip()
                edad_str = texto.split("-")[0]  # Tomar solo el primer número
                try:
                    edad = int(edad_str)
                except (ValueError, TypeError):
                    edad = None
        fila_copia["__edad"] = edad

        jugadores[nombre_norm] = fila_copia

        if tipo_tabla == "keepers" and nombre_base_norm not in jugadores:
            jugadores[nombre_base_norm] = fila_copia

    return jugadores


def rellenar_estadisticas_jugador(fila_jugador, estadisticas_por_tipo, clave_jugador, posicion):
    """
    Rellena las estadísticas de un jugador en su fila de datos.
    
    Args:
        fila_jugador: Diccionario con los datos del jugador
        estadisticas_por_tipo: Estadísticas organizadas por tipo
        clave_jugador: Clave del jugador en las estadísticas
        posicion: Posición del jugador (PT, DF, MC, DT)
    """
    for tipo_stat, configuracion in MAPEO_STATS.items():
        stats_tipo = estadisticas_por_tipo.get(tipo_stat, {})
        stats_jugador = stats_tipo.get(clave_jugador)

        if stats_jugador is None:
            continue

        # Procesar valores enteros
        for columna_fb, columna_dest in configuracion["enteros"].items():
            valor = stats_jugador.get(columna_fb, 0)
            fila_jugador[columna_dest] = to_int(valor)

        # Procesar valores decimales
        for columna_fb, columna_dest in configuracion["decimales"].items():
            valor = stats_jugador.get(columna_fb, 0)
            fila_jugador[columna_dest] = to_float(valor)

    # Procesar resumen y tiros
    resumen = estadisticas_por_tipo.get("summary", {})
    fila_resumen = resumen.get(clave_jugador)

    if fila_resumen is not None:
        total_tiros = to_int(fila_resumen.get("Sh", 0))
        tiros_puerta = to_int(fila_resumen.get("SoT", 0))

        fila_jugador["tiro_fallado_partido"] = max(total_tiros - tiros_puerta, 0)
        fila_jugador["tiro_puerta_partido"] = tiros_puerta
        fila_jugador["pases_completados_pct"] = to_float(fila_resumen.get("Cmp%", 0))

    # Procesar estadísticas de portero
    if posicion == "PT":
        stats_porteros = estadisticas_por_tipo.get("keepers", {})
        fila_portero = buscar_estadisticas_portero(stats_porteros, resumen, clave_jugador)

        if fila_portero is not None:
            goles_contra = to_int(fila_portero.get("GA", 0))
            porcentaje_paradas = 0.0

            if "Save%" in fila_portero:
                porcentaje_paradas = to_float(fila_portero["Save%"])

            psxg = to_float(fila_portero.get("PSxG", 0)) if "PSxG" in fila_portero else 0.0

            fila_jugador["goles_en_contra"] = goles_contra
            fila_jugador["porcentaje_paradas"] = porcentaje_paradas
            fila_jugador["psxg"] = psxg


def obtener_calendario(codigo_temporada: str) -> dict:
    # Convertir el código de temporada de '23_24' a '2023-2024'
    anio_inicio, anio_fin = codigo_temporada.split('_')
    codigo_temporada_formateado = f"20{anio_inicio}-20{anio_fin}"

    ruta_html = os.path.join("main", "html", "html", f"temporada_{codigo_temporada}", "calendario.html")
    with open(ruta_html, "r", encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "lxml")
    tabla_id = f"sched_{codigo_temporada_formateado}_12_1"
    tabla = soup.find("table", id=tabla_id)

    if not tabla:
        raise ValueError(f"No se encontró tabla calendario para {codigo_temporada}")

    matches_by_round = {}

    for row in tabla.find_all("tr"):
        if "spacer" in row.get("class", []):
            continue

        cells = row.find_all(["th", "td"])
        if len(cells) < 9:
            continue

        try:
            round_cell = row.find(attrs={"data-stat": "gameweek"})
            home_cell = row.find(attrs={"data-stat": "home_team"})
            away_cell = row.find(attrs={"data-stat": "away_team"})
            score_cell = row.find(attrs={"data-stat": "score"})
            
            # Extraer fecha y hora
            date_cell = row.find(attrs={"data-stat": "date"})

            if not (round_cell and home_cell and away_cell):
                continue

            round_num = int(round_cell.get_text(strip=True))
            home_name = home_cell.get_text(strip=True)
            away_name = away_cell.get_text(strip=True)
            
            # Extraer fecha del atributo csk en formato YYYYMMDD
            fecha_str = ""
            hora_str = ""
            if date_cell:
                fecha_csk = date_cell.get("csk", "")
                if fecha_csk:
                    try:
                        # Convertir YYYYMMDD a dd/mm/yyyy
                        fecha_obj = datetime.strptime(fecha_csk, "%Y%m%d")
                        fecha_str = fecha_obj.strftime("%d/%m/%Y")
                    except:
                        fecha_str = ""
            
            # Extraer hora del span venuetime
            time_span = row.find("span", class_="venuetime")
            if time_span:
                hora_text = time_span.get("data-venue-time", "")
                if hora_text and hora_text.lower() not in ['', 'nan', 'tbd']:
                    hora_str = hora_text

            # Extraer resultado si el partido ya se jugó
            resultado = None
            if score_cell:
                score_text = score_cell.get_text(strip=True)
                # Si tiene formato "X–Y" o "X-Y", es que se jugó
                if score_text and '–' in score_text:
                    partes = score_text.split('–')
                    if len(partes) == 2:
                        try:
                            goles_local = int(partes[0].strip())
                            goles_visitante = int(partes[1].strip())
                            resultado = f"{goles_local}-{goles_visitante}"
                        except:
                            pass
                elif score_text and '-' in score_text and score_text != '–':
                    # Alternativa con guion normal
                    partes = score_text.split('-')
                    if len(partes) == 2:
                        try:
                            goles_local = int(partes[0].strip())
                            goles_visitante = int(partes[1].strip())
                            resultado = f"{goles_local}-{goles_visitante}"
                        except:
                            pass

            home_norm = normalizar_equipo_temporada(home_name)
            away_norm = normalizar_equipo_temporada(away_name)

            if round_num not in matches_by_round:
                matches_by_round[round_num] = []

            # Crear diccionario con fecha, hora y resultado
            match_info = {
                "match": f"{home_norm} vs {away_norm}",
                "fecha": fecha_str,
                "hora": hora_str
            }
            
            # Agregar resultado si el partido ya se jugó
            if resultado:
                match_info["resultado"] = resultado
            
            matches_by_round[round_num].append(match_info)

        except Exception as e:
            logger.warning(f"Error procesando fila de calendario: {e}")
            continue

    calendar_ordered = dict(sorted(matches_by_round.items()))

    output_dir = os.path.join("csv", "csvGenerados")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"calendario_{codigo_temporada}.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(calendar_ordered, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Calendario guardado en {output_file}")
    return calendar_ordered


def obtener_fantasy_jornada(jornada):
    puntos_path = os.path.join(CARPETA_HTML, f"j{jornada}", "puntos.html")

    if not os.path.exists(puntos_path):
        logger.warning(f"No se encuentra puntos.html en j{jornada}")
        return {}

    html = leer_html(puntos_path)
    if not html:
        return {}

    soup = BeautifulSoup(html, "lxml")
    resultado = {}

    matches = soup.find_all("section", class_="over fichapartido")

    for match in matches:
        header = match.find("header", class_="encabezado-partido")

        home_div = header.select_one(".equipo.local .nombre")
        away_div = header.select_one(".equipo.visitante .nombre")
        home_norm = normalizar_equipo_temporada(home_div.get_text(strip=True))
        away_norm = normalizar_equipo_temporada(away_div.get_text(strip=True))

        match_key = f"{home_norm}-{away_norm}"
        players_points = {}

        team_tables = match.select("table.tablestats")
        for table_idx, table in enumerate(team_tables):
            team_norm = home_norm if table_idx == 0 else away_norm
            player_rows = table.select("tbody tr.plegado")

            for player_row in player_rows:
                name_cell = player_row.find("td", class_="name")
                if not name_cell:
                    continue

                player_name = limpiar_minuto(extraer_nombre_jugador(name_cell))
                pos_raw = name_cell.get("data-posicion-laliga-fantasy", "").strip()
                posicion = POSICION_MAP.get(pos_raw, "MC")


                puntos = 6767
                puntos_span = player_row.select_one("span.laliga-fantasy")
                if puntos_span:
                    try:
                        puntos = int(puntos_span.get_text(strip=True))
                    except ValueError:
                        puntos = 6767

                amarillas = 0
                rojas = 0
                events_cell = player_row.find("td", class_="events")

                if events_cell:
                    for img in events_cell.find_all("img"):
                        tooltip = (img.get("data-tooltip") or "").strip().lower()
                        alt = (img.get("alt") or "").strip().lower()
                        event_text = tooltip if tooltip else alt

                        if "amarilla" in event_text:
                            amarillas += 1
                        elif "roja" in event_text:
                            rojas += 1

                player_key = f"{team_norm}|{player_name}"
                player_with_alias = aplicar_alias_jugador_temporada(
                    player_name, team_norm, TEMPORADA_ACTUAL
                )
                player_norm = normalizar_texto(player_with_alias)

                players_points[player_key] = {
                    "nombre_original": player_name,
                    "nombre_norm": player_norm,
                    "puntos": puntos,
                    "equipo": team_norm,
                    "equipo_norm": team_norm,
                    "amarillas": amarillas,
                    "rojas": rojas,
                    "posicion": posicion,
                }

        resultado[match_key] = players_points

    return resultado


def obtener_nombres_equipos(html_partido) -> tuple:
    soup = BeautifulSoup(html_partido, "lxml")
    title_text = soup.find("title").get_text()

    try:
        home = title_text.split(" vs. ")[0]
        away = title_text.split(" vs. ")[1].split(" Match")[0]
    except Exception:
        logger.error("No se pudieron extraer nombres de equipos")
        home = "Local"
        away = "Visitante"

    return home, away


def obtener_fecha_partido(html_partido):
    """Extrae solo la fecha del HTML del partido (sin hora)."""
    soup = BeautifulSoup(html_partido, "lxml")
    scorebox = soup.find("div", class_="scorebox_meta")

    if not scorebox:
        return None

    time_span = scorebox.find("span", class_="venuetime")
    if not time_span:
        return None

    fecha_raw = time_span.get("data-venue-date")
    
    if not fecha_raw:
        return None

    try:
        dt = datetime.strptime(fecha_raw, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return None


def extraer_titulares(sopa):
    alineaciones = sopa.find_all("div", class_="lineup")
    titulares = []
    jugadores_local = []

    if alineaciones:
        for alineacion in alineaciones:
            jugadores_alineacion = alineacion.find_all("a")
            equipo_jugadores = []
            for jugador in jugadores_alineacion:
                texto_jugador = limpiar_minuto(jugador.get_text().strip())
                equipo_jugadores.append(texto_jugador)
            equipo_jugadores = equipo_jugadores[:11]
            titulares.extend(equipo_jugadores)

        # Equipo local sale primero
        enlaces_local = alineaciones[0].find_all("a")
        for jugador in enlaces_local:
            texto_jugador = limpiar_minuto(jugador.get_text().strip())
            jugadores_local.append(texto_jugador)

    return titulares, jugadores_local


def parsear_tablas_partido(soup, equipo_local, equipo_visitante):
   
    estadisticas_por_tipo = {}
    tipos_tabla = ["summary", "passing", "defense", "possession", "misc", "keepers"]

    for tipo_tabla in tipos_tabla:
        jugadores_tipo = {}

        if tipo_tabla == "keepers":
            tablas = soup.find_all("table", id=re.compile(r"stats_.*_keepers"))
            for tabla in soup.find_all("table"):
                id_tabla = tabla.get("id") or ""
                if "keeper_stats_" in id_tabla and tabla not in tablas:
                    tablas.append(tabla)
        else:
            tablas = soup.find_all("table", id=re.compile(f"stats_.*_{tipo_tabla}"))

        for tabla_html in tablas:
            jugadores_tabla = parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante, tipo_tabla)
            for clave_jugador, stats_jugador in jugadores_tabla.items():
                jugadores_tipo[clave_jugador] = stats_jugador

        estadisticas_por_tipo[tipo_tabla] = jugadores_tipo

    return estadisticas_por_tipo


def construir_dataframe_partido(propuestas, estadisticas_por_tipo, mapeo_fbref_fantasy, datos_fantasy, titulares, local_norm, away_norm, jornada_num, fecha_partido, nacionalidades_map=None, edades_map=None):
    """
    Construye el DataFrame de un partido con datos de FBref y Fantasy.
    
    Args:
        propuestas: Lista de propuestas de matching
        estadisticas_por_tipo: Estadísticas por tipo
        mapeo_fbref_fantasy: Mapeo FBref -> Fantasy
        datos_fantasy: Datos de Fantasy
        titulares: Lista de titulares
        local_norm: Equipo local normalizado
        away_norm: Equipo visitante normalizado
        jornada_num: Número de jornada
        fecha_partido: Fecha del partido
        nacionalidades_map: Dict con nacionalidades por clave_fbref
        edades_map: Dict con edades por clave_fbref
    
    Returns:
        Dict con filas de datos
    """
    if nacionalidades_map is None:
        nacionalidades_map = {}
    if edades_map is None:
        edades_map = {}
    
    datos_partido = {}

    for propuesta in propuestas:
        clave_fbref = propuesta["clave_fbref"]
        nombre_jugador = propuesta["nombre_fb"]
        nombre_norm = propuesta["nombre_fb_norm"]
        equipo_norm = propuesta["equipo_fb_norm"]
        minutos = propuesta["minutos"]
        posicion = propuesta["posicion"]
        nacionalidad = nacionalidades_map.get(clave_fbref, "")
        edad = edades_map.get(clave_fbref)

        equipo_rival_norm = away_norm if equipo_norm == local_norm else local_norm
        clave_fantasy = mapeo_fbref_fantasy.get(clave_fbref)

        if clave_fantasy is not None:
            clave_registro = f"{clave_fantasy}|{equipo_norm}|{posicion}"
        else:
            clave_registro = f"{nombre_norm}|{equipo_norm}|{minutos}|{posicion}"

        if clave_registro not in datos_partido:
            fila_nueva = {col: np.nan for col in COLUMNAS_MODELO}

            fila_nueva["temporada"] = TEMPORADA_ACTUAL
            fila_nueva["jornada"] = jornada_num
            fila_nueva["fecha_partido"] = fecha_partido
            fila_nueva["player"] = nombre_jugador
            fila_nueva["nacionalidad"] = nacionalidad
            fila_nueva["edad"] = edad
            fila_nueva["posicion"] = posicion
            fila_nueva["equipo_propio"] = equipo_norm
            fila_nueva["equipo_rival"] = equipo_rival_norm
            fila_nueva["local"] = 1 if equipo_norm == local_norm else 0
            fila_nueva["titular"] = 1 if nombre_jugador in titulares else 0
            fila_nueva["min_partido"] = minutos
            fila_nueva["goles_en_contra"] = np.nan
            fila_nueva["porcentaje_paradas"] = np.nan
            fila_nueva["roles"] = []

            datos_partido[clave_registro] = fila_nueva

        fila = datos_partido[clave_registro]
        rellenar_estadisticas_jugador(fila, estadisticas_por_tipo, clave_fbref, posicion)

        # Asignar puntos de Fantasy
        puntos = None
        if clave_fantasy is not None:
            puntos = datos_fantasy.get(clave_fantasy, {}).get("puntos")

        if puntos is not None:
            fila["puntos_fantasy"] = puntos

    return datos_partido


def procesar_partido(html_partido, datos_fantasy, jornada_num):
    """
    Procesa un partido completo extrayendo y combinando datos de FBref y Fantasy.
    
    Args:
        html_partido: Contenido HTML del partido
        datos_fantasy: Datos de Fantasy del partido
        jornada_num: Número de la jornada
    
    Returns:
        Tupla (DataFrame, nombre_equipo_local, nombre_equipo_visitante)
    """
    sopa = BeautifulSoup(html_partido, "lxml")
    fecha_partido = obtener_fecha_partido(html_partido)
    equipo_local, equipo_visitante = obtener_nombres_equipos(html_partido)
    
    local_norm = normalizar_equipo_temporada(equipo_local)
    away_norm = normalizar_equipo_temporada(equipo_visitante)
    titulares, jugadores_local = extraer_titulares(sopa)

    estadisticas_por_tipo = parsear_tablas_partido(sopa, equipo_local, equipo_visitante)
    resumen = estadisticas_por_tipo.get("summary", {})

    propuestas = generar_propuestas(resumen, datos_fantasy, local_norm, away_norm, jugadores_local)
    jugadores_apellido, fantasy_norm = construir_fantasy_por_norm(datos_fantasy)
    mapeo_fbref_fantasy, _ = resolver_matching(propuestas, jugadores_apellido, fantasy_norm)

    # Extraer nacionalidades y edades del resumen
    nacionalidades_map = {}
    edades_map = {}
    for nombre_fb_norm, fila_resumen in resumen.items():
        nacionalidad = fila_resumen.get("__nacionalidad", "")
        nacionalidades_map[nombre_fb_norm] = nacionalidad
        edad = fila_resumen.get("__edad")
        edades_map[nombre_fb_norm] = edad

    datos_partido = construir_dataframe_partido(
        propuestas, estadisticas_por_tipo, mapeo_fbref_fantasy,
        datos_fantasy, titulares, local_norm, away_norm, jornada_num, fecha_partido,
        nacionalidades_map, edades_map
    )

    claves_fantasy_usadas = set(mapeo_fbref_fantasy.values())
    datos_partido = completar_fantasy_sin_match(
        datos_partido, datos_fantasy, claves_fantasy_usadas,
        local_norm, away_norm, fecha_partido, jornada_num, TEMPORADA_ACTUAL,
    )

    df = pd.DataFrame.from_dict(datos_partido, orient="index")
    df = postprocesar_df_partido(df)
    df = asignar_roles_df(df, ROLES_DESTACADOS)

    return df, equipo_local, equipo_visitante


def procesar_y_guardar_partido(jornada: int, idx_partido: int, datos_fantasy_por_partido):
    """
    Procesa y guarda un partido en CSV.
    
    Args:
        jornada: Número de la jornada
        idx_partido: Índice del partido dentro de la jornada
        datos_fantasy_por_partido: Datos de Fantasy organizados por partido
    
    Returns:
        Tupla (DataFrame, equipo_local, equipo_visitante) o (None, None, None)
    """
    carpeta_html_j, carpeta_csv_j = obtener_rutas_jornada(CARPETA_HTML, CARPETA_CSV, jornada)
    ruta_html = os.path.join(carpeta_html_j, f"p{idx_partido}.html")
    contenido_html = leer_html(ruta_html, logger=logger)

    if not contenido_html:
        logger.warning(f"No se pudo leer {ruta_html}")
        return None, None, None

    equipo_local, equipo_visitante = obtener_nombres_equipos(contenido_html)
    local_norm = normalizar_equipo_temporada(equipo_local)
    away_norm = normalizar_equipo_temporada(equipo_visitante)
    clave_partido = f"{local_norm}-{away_norm}"
    datos_fantasy = datos_fantasy_por_partido.get(clave_partido, {})

    df, equipo_local_csv, equipo_visitante_csv = procesar_partido(contenido_html, datos_fantasy, jornada)

    if df is None or df.empty:
        logger.warning(f"DataFrame vacío para J{jornada} P{idx_partido}")
        return None, None, None

    local_norm_txt = normalizar_texto(equipo_local_csv)
    away_norm_txt = normalizar_texto(equipo_visitante_csv)
    nombre_csv = f"p{idx_partido}_{local_norm_txt}-{away_norm_txt}.csv"
    ruta_csv = os.path.join(carpeta_csv_j, nombre_csv)

    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    logger.info(f"✅ CSV generado: J{jornada} P{idx_partido} {local_norm_txt}-{away_norm_txt}")

    return df, equipo_local_csv, equipo_visitante_csv


def procesar_jornada(jornada: int):
    logger.info(f"\n=== JORNADA {jornada} (temp {TEMPORADA_ACTUAL}) ===")

    datos_fantasy_por_partido = obtener_fantasy_jornada(jornada)
    tarjetas_banquillo = []

    for idx_partido in range(1, 11):
        df, equipo_local, equipo_visitante = procesar_y_guardar_partido(jornada, idx_partido, datos_fantasy_por_partido)

        if df is not None and not df.empty:
            jugadores_banquillo = contar_tarjetas_banquillo(df)
            if not jugadores_banquillo.empty:
                tarjetas_banquillo.extend(jugadores_banquillo.to_dict("records"))

    if tarjetas_banquillo:
        logger.info("\n📋 Jugadores con tarjetas en banquillo:")
        for jugador in tarjetas_banquillo:
            logger.info(
                f"- {jugador.get('player', '')} ({jugador.get('Equipo_propio', '')}) | "
                f"Amarillas: {jugador.get('Amarillas', 0)}, Rojas: {jugador.get('Rojas', 0)}"
            )


def procesar_rango_jornadas(jornada_inicio: int, jornada_fin: int):
    for jornada in range(jornada_inicio, jornada_fin + 1):
        procesar_jornada(jornada)


def analizar_temporada(codigo_temporada: str, j_ini: int = 1, j_fin: int = 38):
    global TEMPORADA_ACTUAL, CARPETA_HTML, CARPETA_CSV

    TEMPORADA_ACTUAL = codigo_temporada
    CARPETA_HTML, CARPETA_CSV = build_rutas_temporada(codigo_temporada)

    logger.info(f"\n=== ANALIZANDO TEMPORADA {codigo_temporada} ===")
    procesar_rango_jornadas(jornada_inicio=1, jornada_fin=38)


def scrappear_calendario_para_bd():
    """Función para scrappear calendarios con resultados (usada por popularDB)."""
    logger.info("\n" + "=" * 70)
    logger.info("FBREF: SCRAPPEAR CALENDARIO CON RESULTADOS")
    logger.info("=" * 70)
    
    for temporada in ["23_24", "24_25", "25_26"]:
        try:
            logger.info(f"\n[{temporada}] Extrayendo calendario y resultados...")
            obtener_calendario(temporada)
        except Exception as e:
            logger.error(f"❌ Error en la temporada {temporada}: {e}")
            continue


if __name__ == "__main__":
    inicio = time.perf_counter()

    #analizar_temporada("23_24", 1, 38)
    #analizar_temporada("24_25", 1, 38)
    #analizar_temporada("25_26", 1, 20)
    obtener_calendario("23_24")
    obtener_calendario("24_25")
    obtener_calendario("25_26")

    fin = time.perf_counter()
    duracion = fin - inicio
    logger.info(f"\n⏱️ Tiempo total: {duracion:.2f}s")
