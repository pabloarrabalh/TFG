import os
import re
from io import StringIO

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import cloudscraper

from commons import (
    normalizar_texto,
    normalizar_equipo,
    limpiar_minuto,
    extraer_nombre_jugador,
    to_int,
    to_float,
    mapear_posicion,
    nombre_a_mayus,
    coincide_inicial_apellido,
    obtener_match_nombre,
)
from alias import (
    MAPEO_STATS,
    COLUMNAS_MODELO,
    POSICION_MAP,
    APELLIDOS_CRITICOS,
    UMBRAL_MATCH,
    ALIAS_EQUIPOS,
    get_alias_jugadores,
)

# =====================================================
# CONFIG GLOBAL DEPENDIENTE DE TEMPORADA
# =====================================================

TEMPORADA_ACTUAL = "25_26"   # valor por defecto

def _build_rutas_temporada(temporada: str):
    """
    HTML: main/html/temporada_25_26/j1/p1.html, puntos.html
    CSV:  data/temporada_25_26/jornada_1/*.csv
    """
    carpeta_html = os.path.join("main", "html", f"temporada_{temporada}")
    carpeta_csv = os.path.join("data", f"temporada_{temporada}")
    os.makedirs(carpeta_html, exist_ok=True)
    os.makedirs(carpeta_csv, exist_ok=True)
    return carpeta_html, carpeta_csv

CARPETA_HTML, CARPETA_CSV = _build_rutas_temporada(TEMPORADA_ACTUAL)

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True,
    }
)

# =====================================================
# HELPERS ALIAS / NORMALIZACIÓN
# =====================================================

def normalizar_equipo_temporada(nombre: str) -> str:
    """
    Normaliza texto base + aplica ALIAS_EQUIPOS (global, sin temporada).
    """
    nombre_norm = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias_jugador_temporada(nombre: str, equipo_norm: str) -> str:
    """
    Aplica ALIAS_JUGADORES para la temporada actual.
    """
    alias_jug = get_alias_jugadores(TEMPORADA_ACTUAL)
    equipo_norm = equipo_norm or ""
    equipo_norm = normalizar_texto(equipo_norm)

    mapa_equipo = alias_jug.get(equipo_norm, {})
    nombre_norm = normalizar_texto(nombre)
    return mapa_equipo.get(nombre_norm, nombre)


# =====================================================
# LÓGICA FBREF + FANTASY
# =====================================================

def parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante):
    caption = tabla_html.find('caption')
    if caption:
        texto_caption = caption.get_text(strip=True)
    else:
        texto_caption = ""

    equipo_caption = None
    if texto_caption.endswith("Player Stats Table"):
        equipo_caption = texto_caption.replace(" Player Stats Table", "").strip()

    try:
        df_tabla = pd.read_html(StringIO(str(tabla_html)))[0]
    except Exception:
        return {}

    columnas = []
    for columna in df_tabla.columns.get_level_values(-1):
        texto_columna = str(columna)
        texto_columna = texto_columna.split(',')[-1]
        texto_columna = texto_columna.strip(" ()'")
        texto_columna = texto_columna.replace(' ', '')
        columnas.append(texto_columna)

    df_tabla.columns = columnas

    id_tabla = tabla_html.get('id', '')
    jugadores = {}

    for _, fila in df_tabla.iterrows():
        nombre = str(fila['Player'])
        nombre = re.sub(r'\s\(.*\)', '', nombre).strip()

        if nombre in ['nan', 'Player', 'Total', 'Players']:
            continue

        if re.match(r'^\d+\s+Players$', nombre):
            continue

        nombre = limpiar_minuto(nombre)

        if 'Squad' in fila:
            equipo_fila = str(fila.get('Squad', '')).strip()
        else:
            equipo_fila = ""

        if not equipo_fila:
            if equipo_caption:
                equipo_fila = equipo_caption
            elif "_home_" in id_tabla:
                equipo_fila = equipo_local
            elif "_away_" in id_tabla:
                equipo_fila = equipo_visitante

        if equipo_fila:
            equipo_norm = normalizar_equipo_temporada(equipo_fila)
        else:
            equipo_norm = None

        nombre_con_alias = aplicar_alias_jugador_temporada(nombre, equipo_norm)
        nombre_norm = normalizar_texto(nombre_con_alias)

        jugadores[nombre_norm] = fila

    return jugadores


def rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val):
    for tipo, cfg in MAPEO_STATS.items():
        mapa_tipo = tablas_por_tipo.get(tipo, {})
        fila_tipo = mapa_tipo.get(clave_fbref)

        if fila_tipo is None:
            continue

        for col_fb, col_dest in cfg["enteros"].items():
            valor_fb = fila_tipo.get(col_fb, 0)
            fila_salida[col_dest] = to_int(valor_fb)

        for col_fb, col_dest in cfg["decimales"].items():
            valor_fb = fila_tipo.get(col_fb, 0)
            fila_salida[col_dest] = to_float(valor_fb)

    resumen = tablas_por_tipo.get("summary", {})
    fila_summary = resumen.get(clave_fbref)

    if fila_summary is not None:
        tiros_tot = to_int(fila_summary.get("Sh", 0))
        tiros_puerta = to_int(fila_summary.get("SoT", 0))

        fila_salida["TiroFallado_partido"] = max(tiros_tot - tiros_puerta, 0)
        fila_salida["TiroPuerta_partido"] = tiros_puerta

    passing = tablas_por_tipo.get('passing', {})
    fila_pases = passing.get(clave_fbref)

    if fila_pases is not None and 'Cmp%' in fila_pases:
        fila_salida['Pases_Completados_Pct'] = to_float(fila_pases['Cmp%'])
    elif fila_summary is not None and 'Cmp%' in fila_summary:
        fila_salida['Pases_Completados_Pct'] = to_float(fila_summary['Cmp%'])

    if pos_val == 'PT':
        keepers = tablas_por_tipo.get('keepers', {})
        fila_portero = keepers.get(clave_fbref)

        if fila_portero is not None:
            goles_contra = to_int(fila_portero.get('GA', 0))

            pct_paradas = 0.0
            for col_sv in ['Save%', 'Sv%', 'SV%']:
                if col_sv in fila_portero:
                    pct_paradas = to_float(fila_portero[col_sv])
                    break

            if 'PSxG' in fila_portero:
                psxg = to_float(fila_portero.get('PSxG', 0))
            else:
                psxg = 0.0

            fila_salida['Goles_en_contra'] = goles_contra
            fila_salida['Porcentaje_paradas'] = pct_paradas
            fila_salida['PSxG'] = psxg


def postprocesar_df_partido(df):
    if df.empty:
        return df

    if 'Equipo_propio' in df.columns:
        df['Equipo_propio'] = df['Equipo_propio'].apply(normalizar_equipo_temporada)

    if 'Equipo_rival' in df.columns:
        df['Equipo_rival'] = df['Equipo_rival'].apply(normalizar_equipo_temporada)

    mask_no_portero = df['posicion'] != 'PT'
    df.loc[mask_no_portero, 'Goles_en_contra'] = 0.0
    df.loc[mask_no_portero, 'Porcentaje_paradas'] = 0.0

    if 'Amarillas' not in df.columns:
        df['Amarillas'] = 0

    if 'Rojas' not in df.columns:
        df['Rojas'] = 0

    df['Amarillas'] = df['Amarillas'].fillna(0).astype(int)
    df['Rojas'] = df['Rojas'].fillna(0).astype(int)

    df = df.fillna(0)

    return df


def obtener_calendario():
    ruta_local = "calendario.html"

    if os.path.exists(ruta_local):
        with open(ruta_local, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        url = "https://fbref.com/en/comps/12/schedule/La-Liga-Scores-and-Fixtures"
        try:
            resp = scraper.get(url)
            html = resp.text
        except Exception:
            return {}

    soup = BeautifulSoup(html, 'lxml')
    calendario = {}

    tabla_calendario = soup.find('table', {'id': re.compile('sched')})
    if not tabla_calendario:
        return {}

    filas_calendario = tabla_calendario.find_all('tr')
    for tr_fila in filas_calendario:
        th_jornada = tr_fila.find('th', {'data-stat': 'gameweek'})
        td_report = tr_fila.find('td', {'data-stat': 'match_report'})

        if not th_jornada:
            continue

        if td_report:
            a_enlace = td_report.find('a')
        else:
            a_enlace = None

        if a_enlace is None:
            continue

        jornada = th_jornada.get_text().strip()
        href = a_enlace.get('href', '').strip()

        if not href:
            continue

        if href.startswith('http'):
            url_partido = href
        else:
            url_partido = "https://fbref.com" + href

        if jornada not in calendario:
            calendario[jornada] = []

        calendario[jornada].append(url_partido)

    return calendario


def obtener_fantasy_jornada(jornada):
    # main/html/temporada_25_26/j1/puntos.html
    ruta_puntos = os.path.join(CARPETA_HTML, f"j{jornada}", "puntos.html")

    if not os.path.exists(ruta_puntos):
        print(f"     ⚠️ No se encuentra puntos.html en j{jornada}")
        return {}

    with open(ruta_puntos, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    resultado = {}

    secciones_partido = soup.find_all("section", class_="over fichapartido")

    for section_partido in secciones_partido:
        header_partido = section_partido.find("header", class_="encabezado-partido")
        if not header_partido:
            continue

        div_local = header_partido.select_one(".equipo.local .nombre")
        div_visit = header_partido.select_one(".equipo.visitante .nombre")

        if not div_local:
            continue
        if not div_visit:
            continue

        nombre_local = div_local.get_text(strip=True)
        nombre_visit = div_visit.get_text(strip=True)

        local_norm = normalizar_equipo_temporada(nombre_local)
        visit_norm = normalizar_equipo_temporada(nombre_visit)

        clave_partido = f"{local_norm}-{visit_norm}"

        mapa_puntos = {}

        tablas_stats = section_partido.select("table.tablestats")
        for indice_tabla, tabla_stats in enumerate(tablas_stats):
            filas_jugadores = tabla_stats.select("tbody tr.plegado")

            if indice_tabla == 0:
                equipo_tabla_norm = local_norm
            else:
                equipo_tabla_norm = visit_norm

            for tr_jugador in filas_jugadores:
                td_nombre = tr_jugador.find("td", class_="name")
                if not td_nombre:
                    continue

                nombre_sin_min = extraer_nombre_jugador(td_nombre)
                nombre_sin_min = limpiar_minuto(nombre_sin_min)

                pos_fantasy_raw = td_nombre.get("data-posicion-laliga-fantasy", "")
                if not pos_fantasy_raw:
                    pos_fantasy_raw = ""
                pos_fantasy_raw = pos_fantasy_raw.strip()

                pos_map_fantasy = {
                    "Portero": "PT",
                    "Defensa": "DF",
                    "Mediocampista": "MC",
                    "Centrocampista": "MC",
                    "Delantero": "DT",
                }

                if pos_fantasy_raw in pos_map_fantasy:
                    pos_fantasy = pos_map_fantasy[pos_fantasy_raw]
                else:
                    pos_fantasy = "MC"

                puntos = 0
                span_pts = tr_jugador.select_one("span.laliga-fantasy")
                if not span_pts:
                    span_pts = tr_jugador.select_one("span.fantasy-points")
                if not span_pts:
                    span_pts = tr_jugador.select_one("span.puntos")
                if not span_pts:
                    span_pts = tr_jugador.select_one("span.points")

                if span_pts:
                    txt = span_pts.get_text(strip=True)
                    try:
                        puntos = int(float(txt.replace(',', '.')))
                    except Exception:
                        puntos = 0

                td_events = tr_jugador.find("td", class_="events")
                amarillas = 0
                rojas = 0

                if td_events:
                    imagenes_evento = td_events.find_all("img")
                    for img_evento in imagenes_evento:
                        tooltip = img_evento.get("data-tooltip") or ""
                        tooltip = tooltip.strip().lower()

                        alt = img_evento.get("alt") or ""
                        alt = alt.strip().lower()

                        texto = tooltip if tooltip else alt

                        if "amarilla" in texto:
                            amarillas += 1
                        elif "roja" in texto:
                            rojas += 1

                equipo_norm = equipo_tabla_norm

                clave_ff = f"{equipo_norm}|{nombre_sin_min}"

                nombre_con_alias = aplicar_alias_jugador_temporada(nombre_sin_min, equipo_tabla_norm)
                nombre_norm = normalizar_texto(nombre_con_alias)

                info = {
                    "nombre_original": nombre_sin_min,
                    "nombre_norm": nombre_norm,
                    "puntos": puntos,
                    "equipo": equipo_tabla_norm,
                    "equipo_norm": equipo_norm,
                    "amarillas": amarillas,
                    "rojas": rojas,
                    "posicion": pos_fantasy,
                }

                if clave_ff in mapa_puntos:
                    puntos_previos = mapa_puntos[clave_ff]["puntos"]
                    if abs(puntos) > abs(puntos_previos):
                        mapa_puntos[clave_ff] = info
                else:
                    mapa_puntos[clave_ff] = info

        resultado[clave_partido] = mapa_puntos

    return resultado


def obtener_nombres_partido(html_partido):
    soup = BeautifulSoup(html_partido, 'lxml')
    tag_title = soup.find('title')

    if tag_title:
        title = tag_title.get_text()
    else:
        title = "Match"

    try:
        equipo_local = title.split(' vs. ')[0]
        equipo_visitante = title.split(' vs. ')[1].split(' Match')[0]
    except Exception:
        equipo_local = "Local"
        equipo_visitante = "Visitante"

    return equipo_local, equipo_visitante


def procesar_partido(html_partido, mapa_fantasy_partido, idx_partido):
    soup = BeautifulSoup(html_partido, 'lxml')
    tag_title = soup.find('title')

    if tag_title:
        title = tag_title.get_text()
    else:
        title = "Match"

    try:
        equipo_local = title.split(' vs. ')[0]
        equipo_visitante = title.split(' vs. ')[1].split(' Match')[0]
    except Exception:
        equipo_local = "Local"
        equipo_visitante = "Visitante"

    local_norm = normalizar_equipo_temporada(equipo_local)
    visit_norm = normalizar_equipo_temporada(equipo_visitante)

    fantasy_partido = mapa_fantasy_partido

    divs_alineacion = soup.find_all('div', class_='lineup')
    titulares = []

    if divs_alineacion:
        for div_lineup in divs_alineacion:
            anclas = div_lineup.find_all('a')
            nombres_equipo = []

            for a_jugador in anclas:
                texto_jugador = a_jugador.get_text().strip()
                texto_jugador = limpiar_minuto(texto_jugador)
                nombres_equipo.append(texto_jugador)

            nombres_equipo = nombres_equipo[:11]
            for nombre_j in nombres_equipo:
                titulares.append(nombre_j)

    if divs_alineacion:
        anclas_local = divs_alineacion[0].find_all('a')
        nombres_local = []
        for a_local in anclas_local:
            txt = a_local.get_text().strip()
            txt = limpiar_minuto(txt)
            nombres_local.append(txt)
    else:
        nombres_local = []

    tablas_por_tipo = {}
    tipos = ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']

    for tipo in tipos:
        jugadores_tipo = {}

        if tipo == 'keepers':
            tablas = soup.find_all('table', id=re.compile(r'^keeper_stats_.*'))
        else:
            tablas = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))

        for tabla_html in tablas:
            jugadores_tabla = parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante)
            for k, v in jugadores_tabla.items():
                jugadores_tipo[k] = v

        tablas_por_tipo[tipo] = jugadores_tipo

    propuestas = []

    resumen_summary = tablas_por_tipo.get('summary', {})
    for nombre_fb_norm, fila_sum in resumen_summary.items():
        nombre_fb_raw = str(fila_sum.get('Player', '')).strip()
        nombre_fb = limpiar_minuto(nombre_fb_raw)

        es_local = False
        for n_loc in nombres_local:
            if n_loc == nombre_fb:
                es_local = True
                break

        if es_local:
            equipo_fb_norm = local_norm
        else:
            equipo_fb_norm = visit_norm

        minutos = to_int(fila_sum.get('Min', 0))

        pos_raw = str(fila_sum.get('Pos', 'MC'))
        pos_raw = pos_raw.split(',')[0]
        pos_raw = pos_raw.strip()
        pos_val = mapear_posicion(pos_raw)

        candidatos_equipo = {}
        for clave, info in fantasy_partido.items():
            if info.get("equipo_norm") == equipo_fb_norm:
                candidatos_equipo[clave] = info

        nombres_fantasy_norm = []
        for info in candidatos_equipo.values():
            nombres_fantasy_norm.append(info["nombre_norm"])

        # === clave: alias temporada + normalizar ANTES de matchear ===
        nombre_fb_aliased = aplicar_alias_jugador_temporada(nombre_fb, equipo_fb_norm)
        nombre_html_norm = normalizar_texto(nombre_fb_aliased)

        mejor_norm, mejor_score = obtener_match_nombre(
            nombre_html_norm,
            nombres_fantasy_norm,
            equipo_norm=equipo_fb_norm,
            score_cutoff=UMBRAL_MATCH,
        )

        if mejor_norm is None or mejor_score < UMBRAL_MATCH:
            from rapidfuzz import process as rf_process, fuzz as rf_fuzz

            mejor_basico = rf_process.extractOne(
                nombre_html_norm,
                nombres_fantasy_norm,
                scorer=rf_fuzz.WRatio,
            )

            if mejor_basico is not None:
                candidato_norm = mejor_basico[0]
                score_basico = mejor_basico[1]

                if score_basico >= UMBRAL_MATCH:
                    mejor_norm = candidato_norm
                    mejor_score = score_basico

        mejor_original = None
        if mejor_norm is not None:
            for info in candidatos_equipo.values():
                if info["nombre_norm"] == mejor_norm:
                    mejor_original = info["nombre_original"]
                    break

        propuesta = {
            "clave_fbref": nombre_fb_norm,
            "nombre_fb": nombre_fb,
            "nombre_fb_norm": nombre_fb_norm,
            "equipo_fb_norm": equipo_fb_norm,
            "minutos": minutos,
            "posicion": pos_val,
            "mejor_norm": mejor_norm,
            "mejor_original": mejor_original,
            "score": mejor_score,
        }
        propuestas.append(propuesta)

    fantasy_por_norm = {}
    for clave_ff, info in fantasy_partido.items():
        nombre_norm = info["nombre_norm"]

        if nombre_norm not in fantasy_por_norm:
            fantasy_por_norm[nombre_norm] = []

        entrada = {
            "clave_ff": clave_ff,
            "puntos": info["puntos"],
            "info": info,
        }
        fantasy_por_norm[nombre_norm].append(entrada)

    asignacion_fbref_a_fantasy = {}

    propuestas_por_norm = {}
    for propuesta in propuestas:
        nombre_norm = propuesta["mejor_norm"]
        score = propuesta["score"]

        if not nombre_norm:
            continue
        if score < UMBRAL_MATCH:
            continue

        if nombre_norm not in propuestas_por_norm:
            propuestas_por_norm[nombre_norm] = []

        propuestas_por_norm[nombre_norm].append(propuesta)

    for nombre_norm, lista_props in propuestas_por_norm.items():
        candidatos_ff = fantasy_por_norm.get(nombre_norm, [])

        if not candidatos_ff:
            continue

        lista_props_ordenada = sorted(
            lista_props,
            key=lambda p: p["minutos"],
            reverse=True
        )

        candidatos_ff_ordenados = sorted(
            candidatos_ff,
            key=lambda x: abs(x["puntos"]),
            reverse=True
        )

        for propuesta, candidato in zip(lista_props_ordenada, candidatos_ff_ordenados):
            clave_fbref = propuesta["clave_fbref"]
            clave_ff = candidato["clave_ff"]
            asignacion_fbref_a_fantasy[clave_fbref] = clave_ff

    bd_partido = {}

    for propuesta in propuestas:
        clave_fbref = propuesta["clave_fbref"]
        nombre_fb = propuesta["nombre_fb"]
        nombre_fb_norm = propuesta["nombre_fb_norm"]
        equipo_fb_norm = propuesta["equipo_fb_norm"]
        minutos = propuesta["minutos"]
        pos_val = propuesta["posicion"]

        if equipo_fb_norm == local_norm:
            equipo_rival_norm = visit_norm
        else:
            equipo_rival_norm = local_norm

        clave_registro = f"{nombre_fb_norm}|{equipo_fb_norm}|{minutos}|{pos_val}"

        if clave_registro not in bd_partido:
            fila_nueva = {}
            for columna in COLUMNAS_MODELO:
                fila_nueva[columna] = np.nan

            fila_nueva['player'] = nombre_fb
            fila_nueva['Equipo_propio'] = equipo_fb_norm
            fila_nueva['Equipo_rival'] = equipo_rival_norm

            if nombre_fb in titulares:
                fila_nueva['Titular'] = 1
            else:
                fila_nueva['Titular'] = 0

            fila_nueva['Goles_en_contra'] = np.nan
            fila_nueva['Porcentaje_paradas'] = np.nan
            fila_nueva['PSxG'] = np.nan
            fila_nueva['posicion'] = pos_val

            bd_partido[clave_registro] = fila_nueva

        fila_salida = bd_partido[clave_registro]
        rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val)

        clave_ff = asignacion_fbref_a_fantasy.get(clave_fbref)
        puntos = 0

        if clave_ff is not None:
            puntos = fantasy_partido[clave_ff]['puntos']

        fila_salida['puntosFantasy'] = puntos

    usadas_ff = set(asignacion_fbref_a_fantasy.values())

    claves_canonicas_presentes = set()
    nombres_canonicos_presentes = {}

    for clave_registro, fila in bd_partido.items():
        nombre_fb = fila['player']
        equipo_fb_norm = fila['Equipo_propio']
        pos_fb = fila['posicion']

        nombre_canonico_fb = normalizar_texto(
            aplicar_alias_jugador_temporada(nombre_fb, equipo_fb_norm)
        )

        claves_canonicas_presentes.add((nombre_canonico_fb, equipo_fb_norm, pos_fb))

        clave_ep = (equipo_fb_norm, pos_fb)
        if clave_ep not in nombres_canonicos_presentes:
            nombres_canonicos_presentes[clave_ep] = set()
        nombres_canonicos_presentes[clave_ep].add(nombre_canonico_fb)

    for clave_ff, info in fantasy_partido.items():
        nombre_original = info["nombre_original"]
        equipo_norm = info["equipo_norm"]
        pos_val = info.get("posicion", "MC")

        nombre_canonico_ff = normalizar_texto(
            aplicar_alias_jugador_temporada(nombre_original, equipo_norm)
        )

        if (nombre_canonico_ff, equipo_norm, pos_val) in claves_canonicas_presentes:
            continue

        clave_ep = (equipo_norm, pos_val)
        nombres_presentes = nombres_canonicos_presentes.get(clave_ep, set())

        coincidencia = None
        for n in nombres_presentes:
            if coincide_inicial_apellido(nombre_canonico_ff, n):
                coincidencia = n
                break

        if coincidencia:
            for clave_registro, fila in bd_partido.items():
                nombre_canonico_fila = normalizar_texto(
                    aplicar_alias_jugador_temporada(fila['player'], fila['Equipo_propio'])
                )
                if (
                    nombre_canonico_fila == coincidencia
                    and fila['Equipo_propio'] == equipo_norm
                    and fila['posicion'] == pos_val
                ):
                    fila['puntosFantasy'] = info['puntos']
                    break

            continue

        if clave_ff in usadas_ff:
            continue

        puntos = info["puntos"]
        amarillas_banquillo = info.get("amarillas", 0)
        rojas_banquillo = info.get("rojas", 0)

        if amarillas_banquillo == 0 and rojas_banquillo == 0:
            continue

        if equipo_norm == local_norm:
            equipo_rival_norm = visit_norm
        else:
            equipo_rival_norm = local_norm

        nombre_norm = info["nombre_norm"]
        clave_registro = f"{nombre_norm}|{equipo_norm}|0|{pos_val}|fantasy_only"

        if clave_registro in bd_partido:
            continue

        fila = {}
        for columna in COLUMNAS_MODELO:
            fila[columna] = 0

        fila['player'] = nombre_a_mayus(nombre_canonico_ff)
        fila['posicion'] = pos_val
        fila['Equipo_propio'] = equipo_norm
        fila['Equipo_rival'] = equipo_rival_norm
        fila['Titular'] = 0
        fila['Min_partido'] = 0
        fila['puntosFantasy'] = puntos
        fila['Amarillas'] = amarillas_banquillo
        fila['Rojas'] = rojas_banquillo

        bd_partido[clave_registro] = fila

    df_partido = pd.DataFrame.from_dict(bd_partido, orient='index')
    df_partido = postprocesar_df_partido(df_partido)

    return df_partido, equipo_local, equipo_visitante


def procesar_jornada(jornada: int):
    sj = str(jornada)
    print(f"\n=== JORNADA {sj} (temp {TEMPORADA_ACTUAL}) ===")

    fantasy_por_partido = obtener_fantasy_jornada(sj)

    carpeta_html_j = os.path.join(CARPETA_HTML, f"j{jornada}")
    carpeta_csv_j = os.path.join(CARPETA_CSV, f"jornada_{sj}")

    os.makedirs(carpeta_html_j, exist_ok=True)
    os.makedirs(carpeta_csv_j, exist_ok=True)

    for idx_partido in range(1, 10 + 1):
        ruta_html = os.path.join(carpeta_html_j, f"p{idx_partido}.html")

        if not os.path.exists(ruta_html):
            continue

        print(f"    📂 [P{idx_partido}] {ruta_html}")

        with open(ruta_html, "r", encoding="utf-8") as f:
            html_partido = f.read()

        equipo_local, equipo_visitante = obtener_nombres_partido(html_partido)

        local_norm = normalizar_equipo_temporada(equipo_local)
        visit_norm = normalizar_equipo_temporada(equipo_visitante)

        clave_partido = f"{local_norm}-{visit_norm}"

        fantasy_partido = fantasy_por_partido.get(clave_partido, {})

        df_partido, eq_loc_csv, eq_vis_csv = procesar_partido(
            html_partido,
            fantasy_partido,
            idx_partido,
        )

        if df_partido is not None and not df_partido.empty:
            eq_loc_norm = normalizar_texto(eq_loc_csv)
            eq_vis_norm = normalizar_texto(eq_vis_csv)

            nombre_csv = f"p{idx_partido}_{eq_loc_norm}-{eq_vis_norm}.csv"

            ruta_salida = os.path.join(carpeta_csv_j, nombre_csv)
            df_partido.to_csv(
                ruta_salida,
                index=False,
                encoding='utf-8-sig'
            )

            print("✅ CSV generado.")


def procesar_rango_jornadas(jornada_inicio: int, jornada_fin: int):
    for j in range(jornada_inicio, jornada_fin + 1):
        procesar_jornada(j)


# =====================================================
# NUEVO: analizar_temporada(x)
# =====================================================

def analizar_temporada(codigo_temporada: str, j_ini: int = 1, j_fin: int = 38):
    """
    codigo_temporada: '25_26', '24_25', etc.
    Usa alias de jugadores de esa temporada y rutas:
    - main/html/temporada_<temporada>/jX/puntos.html, p1.html...
    - data/temporada_<temporada>/jornada_X/*.csv
    """
    global TEMPORADA_ACTUAL, CARPETA_HTML, CARPETA_CSV

    TEMPORADA_ACTUAL = codigo_temporada
    CARPETA_HTML, CARPETA_CSV = _build_rutas_temporada(codigo_temporada)

    print(f"\n=== ANALIZANDO TEMPORADA {codigo_temporada} ===")
    procesar_rango_jornadas(j_ini, j_fin)


if __name__ == "__main__":
    analizar_temporada("24_24", 1, 10)
