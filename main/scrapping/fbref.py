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
    aplicar_alias_contextual,
    obtener_match_nombre,
)

CARPETA_HTML = os.path.join("main", "html")
CARPETA_CSV = os.path.join("data", "temporada_25_26")

os.makedirs(CARPETA_HTML, exist_ok=True)
os.makedirs(CARPETA_CSV, exist_ok=True)

COLUMNAS_MODELO = [
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular',
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido',
    'xAG',
    'Tiros', 'TiroFallado_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct',
    'Amarillas', 'Rojas', 'Goles_en_contra', 'Porcentaje_paradas', 'PSxG', 'puntosFantasy',
    'Entradas', 'Duelos', 'DuelosGanados', 'DuelosPerdidos',
    'Bloqueos', 'BloqueoTiros', 'BloqueoPase', 'Despejes',
    'Regates', 'RegatesCompletados', 'RegatesFallidos',
    'Conducciones', 'DistanciaConduccion', 'MetrosAvanzadosConduccion', 'ConduccionesProgresivas',
    'DuelosAereosGanados', 'DuelosAereosPerdidos', 'DuelosAereosGanadosPct'
]

JUGADORES_SIN_MATCH = []
UMBRAL_MATCH = 75.0

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

# ======================
# Helpers básicos
# ======================

def to_float(valor):
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if pd.isna(valor) or valor == "" or valor == "-":
        return np.nan
    texto = str(valor).split('\n')[0].replace('%', '').strip()
    try:
        return float(texto)
    except:
        return np.nan


def to_int(valor):
    v = to_float(valor)
    if pd.isna(v):
        return np.nan
    return int(round(v))


POSICION_MAP = {
    "GK": "PT",
    "DF": "DF",
    "RB": "DF",
    "LB": "DF",
    "CB": "DF",
    "FW": "DT",
    "RW": "DT",
    "LW": "DT",
}


def mapear_posicion(pos_raw):
    pos_raw = (pos_raw or "MC").upper()
    return POSICION_MAP.get(pos_raw, "MC")


def parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante):
    """
    Devuelve dict{nombre_norm_fbref: fila_df} de una tabla de FBref.
    """
    caption = tabla_html.find('caption')
    texto_caption = caption.get_text(strip=True) if caption else ""
    equipo_caption = None
    if texto_caption.endswith("Player Stats Table"):
        equipo_caption = texto_caption.replace(" Player Stats Table", "").strip()

    try:
        df_tabla = pd.read_html(StringIO(str(tabla_html)))[0]
    except Exception:
        return {}

    df_tabla.columns = [
        str(columna).split(',')[-1].strip(" ()'").replace(' ', '')
        for columna in df_tabla.columns.get_level_values(-1)
    ]

    id_tabla = tabla_html.get('id', '')
    jugadores = {}

    for indice, fila in df_tabla.iterrows():
        nombre_crudo = re.sub(r'\s\(.*\)', '', str(fila['Player'])).strip()
        if (
            nombre_crudo in ['nan', 'Player', 'Total', 'Players'] or
            re.match(r'^\d+\s+Players$', nombre_crudo)
        ):
            continue

        equipo_fila = str(fila.get('Squad', '')).strip() if 'Squad' in fila else ""

        if not equipo_fila:
            if equipo_caption:
                equipo_fila = equipo_caption
            elif "_home_" in id_tabla:
                equipo_fila = equipo_local
            elif "_away_" in id_tabla:
                equipo_fila = equipo_visitante

        equipo_norm = normalizar_equipo(equipo_fila) if equipo_fila else None
        nombre_norm = normalizar_texto(
            aplicar_alias_contextual(nombre_crudo, equipo_norm)
        )

        jugadores[nombre_norm] = fila

    return jugadores


MAPEO_STATS = {
    "summary": {
        "enteros": {
            "Min": "Min_partido",
            "Gls": "Gol_partido",
            "Ast": "Asist_partido",
            "Sh": "Tiros",
            "Att": "Pases_Totales",
        },
        "decimales": {
            "xG": "xG_partido",
            "xAG": "xAG",
        },
    },
    "defense": {
        "enteros": {
            "Tkl": "Entradas",
            "Att": "Duelos",
            "Won": "DuelosGanados",
            "Lost": "DuelosPerdidos",
            "Blocks": "Bloqueos",
            "Sh": "BloqueoTiros",
            "Pass": "BloqueoPase",
            "Clr": "Despejes",
        },
        "decimales": {},
    },
    "possession": {
        "enteros": {
            "Att": "Regates",
            "Succ": "RegatesCompletados",
            "Tkld": "RegatesFallidos",
            "Carries": "Conducciones",
            "PrgC": "ConduccionesProgresivas",
        },
        "decimales": {
            "TotDist": "DistanciaConduccion",
            "PrgDist": "MetrosAvanzadosConduccion",
        },
    },
    "misc": {
        "enteros": {
            "CrdY": "Amarillas",
            "CrdR": "Rojas",
            "Won": "DuelosAereosGanados",
            "Lost": "DuelosAereosPerdidos",
        },
        "decimales": {
            "Won%": "DuelosAereosGanadosPct",
        },
    },
}


def rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val):
    for tipo, cfg in MAPEO_STATS.items():
        fila_tipo = tablas_por_tipo.get(tipo, {}).get(clave_fbref)
        if fila_tipo is None:
            continue

        for col_fb, col_dest in cfg["enteros"].items():
            fila_salida[col_dest] = to_int(fila_tipo.get(col_fb, 0))

        for col_fb, col_dest in cfg["decimales"].items():
            fila_salida[col_dest] = to_float(fila_tipo.get(col_fb, 0))

    fila_summary = tablas_por_tipo.get("summary", {}).get(clave_fbref)
    if fila_summary is not None:
        tiros_tot = to_int(fila_summary.get("Sh", 0))
        tiros_puerta = to_int(fila_summary.get("SoT", 0))
        fila_salida["TiroFallado_partido"] = max(tiros_tot - tiros_puerta, 0)
        fila_salida["TiroPuerta_partido"] = tiros_puerta

    fila_pases = tablas_por_tipo.get('passing', {}).get(clave_fbref)
    if fila_pases is not None and 'Cmp%' in fila_pases:
        fila_salida['Pases_Completados_Pct'] = to_float(fila_pases['Cmp%'])
    elif fila_summary is not None and 'Cmp%' in fila_summary:
        fila_salida['Pases_Completados_Pct'] = to_float(fila_summary['Cmp%'])

    if pos_val == 'PT':
        tablas_portero = tablas_por_tipo.get('keepers', {})
        fila_portero = tablas_por_tipo.get('keepers', {}).get(clave_fbref)
        if fila_portero is not None:
            goles_contra = to_int(fila_portero.get('GA', 0))
            pct_paradas = 0.0
            for col_sv in ['Save%', 'Sv%', 'SV%']:
                if col_sv in fila_portero:
                    pct_paradas = to_float(fila_portero[col_sv])
                    break
            psxg = to_float(fila_portero.get('PSxG', 0)) if 'PSxG' in fila_portero else 0.0
            fila_salida['Goles_en_contra'] = goles_contra
            fila_salida['Porcentaje_paradas'] = pct_paradas
            fila_salida['PSxG'] = psxg


def postprocesar_df_partido(df):
    if df.empty:
        return df
    if 'Equipo_propio' in df.columns:
        df['Equipo_propio'] = df['Equipo_propio'].apply(normalizar_equipo)
    if 'Equipo_rival' in df.columns:
        df['Equipo_rival'] = df['Equipo_rival'].apply(normalizar_equipo)

    mask_no_portero = df['posicion'] != 'PT'
    df.loc[mask_no_portero, 'Goles_en_contra'] = 0.0
    df.loc[mask_no_portero, 'Porcentaje_paradas'] = 0.0
    df.fillna(0, inplace=True)

    mask_doble_amarilla = df['Amarillas'] >= 2
    df.loc[mask_doble_amarilla, 'Rojas'] = 1.0
    return df


# ======================
# Scraping
# ======================

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
        except:
            return {}

    soup = BeautifulSoup(html, 'lxml')
    calendario = {}
    tabla = soup.find('table', {'id': re.compile('sched')})
    if not tabla:
        return {}

    for fila in tabla.find_all('tr'):
        th_jornada = fila.find('th', {'data-stat': 'gameweek'})
        td_report = fila.find('td', {'data-stat': 'match_report'})
        enlace = td_report.find('a') if td_report else None
        if th_jornada and enlace:
            j = th_jornada.get_text().strip()
            href = enlace['href']
            url_partido = "https://fbref.com" + href if not href.startswith('http') else href
            calendario.setdefault(j, []).append(url_partido)
    return calendario


def obtener_fantasy_jornada(jornada):
    ruta_puntos = os.path.join(CARPETA_HTML, f"j{jornada}", "puntos.html")
    if not os.path.exists(ruta_puntos):
        print(f"     ⚠️ No se encuentra puntos.html en j{jornada}")
        return {}

    with open(ruta_puntos, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    resultado = {}

    secciones = soup.find_all("section", class_="over fichapartido")

    for seccion in secciones:
        cabecera = seccion.find("header", class_="encabezado-partido")
        if not cabecera:
            continue

        nodo_local = cabecera.select_one(".equipo.local .nombre")
        nodo_visit = cabecera.select_one(".equipo.visitante .nombre")
        if not nodo_local or not nodo_visit:
            continue

        nombre_local = nodo_local.get_text(strip=True)
        nombre_visit = nodo_visit.get_text(strip=True)
        local_norm = normalizar_equipo(nombre_local)
        visit_norm = normalizar_equipo(nombre_visit)
        clave_partido = f"{local_norm}-{visit_norm}"

        mapa_puntos = {}

        tablas = seccion.select("table.tablestats")
        for indice_tabla, tabla_x in enumerate(tablas):
            filas = tabla_x.select("tbody tr.plegado")
            equipo_tabla_norm = local_norm if indice_tabla == 0 else visit_norm

            for fila in filas:
                td_nombre = fila.find("td", class_="name")
                if not td_nombre:
                    continue

                nombre_raw = td_nombre.get_text(" ", strip=True)
                nombre_raw = nombre_raw.replace("+", "").replace("-", "").strip()
                nombre_raw = re.sub(r"\s\d+'?$", "", nombre_raw).strip()

                puntos = 0
                span_pts = fila.select_one("span.laliga-fantasy")
                if span_pts:
                    txt = span_pts.get_text(strip=True)
                    try:
                        puntos = int(float(txt))
                    except:
                        puntos = 0

                equipo_norm = equipo_tabla_norm
                clave_ff = f"{equipo_norm}|{nombre_raw}"

                nombre_norm = normalizar_texto(
                    aplicar_alias_contextual(nombre_raw, equipo_tabla_norm)
                )

                info = {
                    "nombre_original": nombre_raw,
                    "nombre_norm": nombre_norm,
                    "puntos": puntos,
                    "equipo": equipo_tabla_norm,
                    "equipo_norm": equipo_norm,
                }

                if clave_ff in mapa_puntos:
                    if abs(puntos) > abs(mapa_puntos[clave_ff]["puntos"]):
                        mapa_puntos[clave_ff] = info
                else:
                    mapa_puntos[clave_ff] = info

        resultado[clave_partido] = mapa_puntos

    return resultado


def obtener_nombres_partido(html_partido):
    soup = BeautifulSoup(html_partido, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        local, visitante = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        local, visitante = "Local", "Visitante"
    return local, visitante


def procesar_partido(html_partido, mapa_fantasy_partido, idx_partido):
    soup = BeautifulSoup(html_partido, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        equipo_local, equipo_visitante = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        equipo_local, equipo_visitante = "Local", "Visitante"

    local_norm = normalizar_equipo(equipo_local)
    visit_norm = normalizar_equipo(equipo_visitante)

    fantasy_partido = mapa_fantasy_partido

    divs_alineacion = soup.find_all('div', class_='lineup')
    titulares = []
    if divs_alineacion:
        for div_lineup in divs_alineacion:
            nombres_equipo = [a.get_text().strip() for a in div_lineup.find_all('a')][:11]
            titulares.extend(nombres_equipo)

    nombres_local = (
        [a.get_text().strip() for a in divs_alineacion[0].find_all('a')]
        if divs_alineacion else []
    )

    tablas_por_tipo = {}
    for tipo in ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']:
        jugadores_tipo = {}
        if tipo == 'keepers':
            tablas = soup.find_all('table', id=re.compile(r'^keeper_stats_.*'))
        else:
            tablas = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))

        for tabla_html in tablas:
            jugadores_tabla = parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante)
            jugadores_tipo.update(jugadores_tabla)

        tablas_por_tipo[tipo] = jugadores_tipo

    propuestas = []

    for nombre_fb_norm, fila_sum in tablas_por_tipo.get('summary', {}).items():
        nombre_fb = str(fila_sum.get('Player', '')).strip()

        es_local = nombre_fb in nombres_local
        equipo_fb_norm = local_norm if es_local else visit_norm

        minutos = to_int(fila_sum.get('Min', 0))
        pos_raw = str(fila_sum.get('Pos', 'MC')).split(',')[0].strip()
        pos_val = mapear_posicion(pos_raw)

        candidatos_equipo = {
            clave: info for clave, info in fantasy_partido.items()
            if info.get("equipo_norm") == equipo_fb_norm
        }
        nombres_fantasy_norm = [info["nombre_norm"] for info in candidatos_equipo.values()]

        nombre_fb_norm_local = normalizar_texto(nombre_fb)

        mejor_norm, mejor_score = obtener_match_nombre(
            nombre_fb_norm_local,
            nombres_fantasy_norm,
            equipo_norm=equipo_fb_norm,
            score_cutoff=UMBRAL_MATCH,
        )

        # Fallback si el matching avanzado falla: RapidFuzz directo [web:35][web:99]
        if mejor_norm is None or mejor_score < UMBRAL_MATCH:
            from rapidfuzz import process, fuzz
            mejor_basico = process.extractOne(
                nombre_fb_norm_local,
                nombres_fantasy_norm,
                scorer=fuzz.WRatio,
            )
            if mejor_basico is not None:
                candidato_norm, score_basico, _ = mejor_basico
                if score_basico >= UMBRAL_MATCH:
                    mejor_norm = candidato_norm
                    mejor_score = score_basico

        mejor_original = None
        if mejor_norm is not None:
            for info in candidatos_equipo.values():
                if info["nombre_norm"] == mejor_norm:
                    mejor_original = info["nombre_original"]
                    break

        propuestas.append({
            "clave_fbref": nombre_fb_norm,
            "nombre_fb": nombre_fb,
            "nombre_fb_norm": nombre_fb_norm,
            "equipo_fb_norm": equipo_fb_norm,
            "minutos": minutos,
            "posicion": pos_val,
            "mejor_norm": mejor_norm,
            "mejor_original": mejor_original,
            "score": mejor_score,
        })

    fantasy_por_norm = {}
    for clave_ff, info in fantasy_partido.items():
        nombre_norm = info["nombre_norm"]
        fantasy_por_norm.setdefault(nombre_norm, []).append({
            "clave_ff": clave_ff,
            "puntos": info["puntos"],
            "info": info,
        })

    asignacion_fbref_a_fantasy = {}

    propuestas_por_norm = {}
    for propuesta in propuestas:
        nombre_norm = propuesta["mejor_norm"]
        score = propuesta["score"]
        if not nombre_norm or score < UMBRAL_MATCH:
            continue
        propuestas_por_norm.setdefault(nombre_norm, []).append(propuesta)

    for nombre_norm, lista_props in propuestas_por_norm.items():
        candidatos_ff = fantasy_por_norm.get(nombre_norm, [])
        if not candidatos_ff:
            continue

        lista_props_ordenada = sorted(lista_props, key=lambda p: p["minutos"], reverse=True)
        candidatos_ff_ordenados = sorted(candidatos_ff, key=lambda x: x["puntos"], reverse=True)

        for propuesta, candidato in zip(lista_props_ordenada, candidatos_ff_ordenados):
            asignacion_fbref_a_fantasy[propuesta["clave_fbref"]] = candidato["clave_ff"]

    bd_partido = {}

    for propuesta in propuestas:
        clave_fbref = propuesta["clave_fbref"]
        nombre_fb = propuesta["nombre_fb"]
        nombre_fb_norm = propuesta["nombre_fb_norm"]
        equipo_fb_norm = propuesta["equipo_fb_norm"]
        minutos = propuesta["minutos"]
        pos_val = propuesta["posicion"]

        equipo_rival_norm = visit_norm if equipo_fb_norm == local_norm else local_norm

        clave_registro = f"{nombre_fb_norm}|{equipo_fb_norm}|{minutos}|{pos_val}"

        if clave_registro not in bd_partido:
            bd_partido[clave_registro] = {columna: np.nan for columna in COLUMNAS_MODELO}
            bd_partido[clave_registro].update({
                'player': nombre_fb,
                'Equipo_propio': equipo_fb_norm,
                'Equipo_rival': equipo_rival_norm,
                'Titular': 1 if nombre_fb in titulares else 0,
                'Goles_en_contra': np.nan,
                'Porcentaje_paradas': np.nan,
                'PSxG': np.nan,
                'posicion': pos_val,
            })

        fila_salida = bd_partido[clave_registro]
        rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val)

        clave_ff = asignacion_fbref_a_fantasy.get(clave_fbref)
        puntos = 0
        if clave_ff is not None:
            puntos = fantasy_partido[clave_ff]['puntos']
        fila_salida['puntosFantasy'] = puntos

        if clave_ff is None and idx_partido in (1, 2, 3):
            JUGADORES_SIN_MATCH.append({
                "partido_idx": idx_partido,
                "equipo_local": equipo_local,
                "equipo_visitante": equipo_visitante,
                "nombre_fbref": nombre_fb,
                "fb_norm": nombre_fb_norm,
            })

    df_partido = pd.DataFrame.from_dict(bd_partido, orient='index')
    df_partido = postprocesar_df_partido(df_partido)
    return df_partido, equipo_local, equipo_visitante


def ejecutar_rango_jornadas(j_ini, j_fin):
    print("🚀 INICIANDO SISTEMA...")
    obtener_calendario()

    for j in range(j_ini, j_fin + 1):
        sj = str(j)
        print(f"\n--- JORNADA {sj} ---")

        fantasy_por_partido = obtener_fantasy_jornada(sj)

        carpeta_html_j = os.path.join(CARPETA_HTML, f"j{j}")
        carpeta_csv_j = os.path.join(CARPETA_CSV, f"jornada_{sj}")
        os.makedirs(carpeta_html_j, exist_ok=True)
        os.makedirs(carpeta_csv_j, exist_ok=True)

        for idx_partido in range(1, 11):
            ruta_html = os.path.join(carpeta_html_j, f"p{idx_partido}.html")
            if not os.path.exists(ruta_html):
                continue

            print(f"     📂 [P{idx_partido}] Usando local: {ruta_html}")
            with open(ruta_html, "r", encoding="utf-8") as f:
                html_partido = f.read()

            equipo_local, equipo_visitante = obtener_nombres_partido(html_partido)
            local_norm = normalizar_equipo(equipo_local)
            visit_norm = normalizar_equipo(equipo_visitante)
            clave_partido = f"{local_norm}-{visit_norm}"

            fantasy_partido = fantasy_por_partido.get(clave_partido, {})

            global JUGADORES_SIN_MATCH
            JUGADORES_SIN_MATCH = []
            df_partido, eq_loc_csv, eq_vis_csv = procesar_partido(
                html_partido, fantasy_partido, idx_partido
            )

            if df_partido is not None and not df_partido.empty:
                nombre_csv = f"p{idx_partido}_{normalizar_texto(eq_loc_csv)}-{normalizar_texto(eq_vis_csv)}.csv"
                df_partido.to_csv(os.path.join(carpeta_csv_j, nombre_csv), index=False, encoding='utf-8-sig')
                print("     ✅ CSV generado.")
            df_cero = df_partido[df_partido['puntosFantasy'] == 0]

            if not df_cero.empty:
                for indice_fila, fila in df_cero.iterrows():
                    print(f"         - {fila['player']}  -> 0 puntos")


if __name__ == "__main__":
    ejecutar_rango_jornadas(j_ini=1, j_fin=1)

    if JUGADORES_SIN_MATCH:
        print("\n[LOG] Jugadores que han quedado sin match en ninguna asignación de puntos:")
        print("PARTIDO_IDX | EQUIPO_LOCAL | EQUIPO_VISITANTE | NOMBRE_FBREF | FB_NORM")
        print("-" * 80)
        for jugador in JUGADORES_SIN_MATCH:
            print(
                f" {jugador['partido_idx']} | {jugador['equipo_local']} "
                f"| {jugador['equipo_visitante']} | {jugador['nombre_fbref']} "
                f"| {jugador['fb_norm']}"
            )
    else:
        print("\n[LOG] Todos los jugadores han sido asignados correctamente.")
