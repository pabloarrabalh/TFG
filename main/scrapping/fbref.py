#############################################################################################################
#   scrapper_fbref.py  (versión con LOGS extra + equipo desde caption tabla FBref)
#############################################################################################################

import os
import re
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup
import cloudscraper
import numpy as np

from commons import (
    ALIAS_EQUIPOS,
    ALIAS_JUGADORES,
    normalizar_texto,
    normalizar_equipo,
    aplicar_alias,
    aplicar_alias_contextual,
)

from rapidfuzz import process, fuzz

pd.set_option('display.max_columns', None)

BASE_FOLDER_HTML = os.path.join("main", "html")
BASE_FOLDER_CSV = os.path.join("data", "temporada_25_26")

os.makedirs(BASE_FOLDER_HTML, exist_ok=True)
os.makedirs(BASE_FOLDER_CSV, exist_ok=True)

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

UMBRAL_MATCH = 80.0

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

DEBUG_NOMBRES = (
    "isi", "isi palazon", "isaac palazon camacho",
    "pepelu", "jose luis garcia vaya",
    "chimy", "ezequiel avila",
    "nico williams", "iñaki williams"
)


def es_debug_nombre(nombre):
    return normalizar_texto(nombre) in DEBUG_NOMBRES


def get_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }


def limpiar_float(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return np.nan
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return np.nan


def limpiar_int(val):
    f = limpiar_float(val)
    if pd.isna(f):
        return np.nan
    return int(round(f))


def obtener_calendario_local_o_remoto():
    path_local = "calendario.html"
    if os.path.exists(path_local):
        with open(path_local, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        url_cal = "https://fbref.com/en/comps/12/schedule/La-Liga-Scores-and-Fixtures"
        try:
            resp = scraper.get(url_cal, headers=get_headers())
            html = resp.text
        except:
            return {}

    soup = BeautifulSoup(html, 'lxml')
    calendario = {}
    tabla = soup.find('table', {'id': re.compile('sched')})
    if not tabla:
        return {}

    for row in tabla.find_all('tr'):
        wk = row.find('th', {'data-stat': 'gameweek'})
        match_report = row.find('td', {'data-stat': 'match_report'})
        if wk and match_report and match_report.find('a'):
            j_num = wk.get_text().strip()
            href = match_report.find('a')['href']
            link = "https://fbref.com" + href if not href.startswith('http') else href
            calendario.setdefault(j_num, []).append(link)
    return calendario


def extraer_puntos_fantasy_jornada(jornada):
    path_puntos = os.path.join(BASE_FOLDER_HTML, f"j{jornada}", "puntos.html")
    if not os.path.exists(path_puntos):
        print(f"     ⚠️ No se encuentra puntos.html en j{jornada}")
        return {}

    with open(path_puntos, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    res = {}

    secciones = soup.find_all("section", class_="over fichapartido")

    for seccion in secciones:
        encabezado = seccion.find("header", class_="encabezado-partido")
        if not encabezado:
            continue

        nombre_local = encabezado.select_one(".equipo.local .nombre")
        nombre_visit = encabezado.select_one(".equipo.visitante .nombre")
        if not nombre_local or not nombre_visit:
            continue

        n_l = nombre_local.get_text(strip=True)
        n_v = nombre_visit.get_text(strip=True)
        n_l_norm = normalizar_equipo(n_l)
        n_v_norm = normalizar_equipo(n_v)
        clave_partido = f"{n_l_norm}-{n_v_norm}"

        puntos_map = {}

        tablas = seccion.select("table.tablestats")
        for i, tabla in enumerate(tablas):
            filas = tabla.select("tbody tr.plegado")
            equipo_tabla_norm = n_l_norm if i == 0 else n_v_norm

            for fila in filas:
                td_name = fila.find("td", class_="name")
                if not td_name:
                    continue

                nombre_real = td_name.get_text(" ", strip=True)
                nombre_real = nombre_real.replace("+", "").replace("-", "").strip()
                nombre_real = re.sub(r"\s\d+'?$", "", nombre_real).strip()

                puntos = 0
                span_puntos = fila.select_one("span.laliga-fantasy")
                if span_puntos:
                    txt = span_puntos.get_text(strip=True)
                    try:
                        puntos = int(float(txt))
                    except:
                        puntos = 0

                equipo_norm = equipo_tabla_norm
                clave_ff = f"{equipo_norm}|{nombre_real}"

                nombre_norm = normalizar_texto(
                    aplicar_alias_contextual(nombre_real, equipo_tabla_norm)
                )

                info_jugador = {
                    "nombre_original": nombre_real,
                    "nombre_norm": nombre_norm,
                    "puntos": puntos,
                    "equipo": equipo_tabla_norm,
                    "equipo_norm": equipo_norm,
                }

                if es_debug_nombre(nombre_real):
                    print(f"[FF_DEBUG] puntos.html -> partido={clave_partido} "
                          f"equipo={equipo_tabla_norm} orig='{nombre_real}' "
                          f"nombre_norm='{nombre_norm}' puntos={puntos} "
                          f"clave_ff='{clave_ff}'")

                if clave_ff in puntos_map:
                    if abs(puntos) > abs(puntos_map[clave_ff]["puntos"]):
                        puntos_map[clave_ff] = info_jugador
                else:
                    puntos_map[clave_ff] = info_jugador

        res[clave_partido] = puntos_map

    return res


def obtener_nombres_partido_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"
    return n_l, n_v


def procesar_partido(html_content, puntos_fantasy_dict, idx_partido):
    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"

    n_l_norm = normalizar_equipo(n_l)
    n_v_norm = normalizar_equipo(n_v)

    puntos_fantasy_match = puntos_fantasy_dict

    if any(es_debug_nombre(info["nombre_original"]) for info in puntos_fantasy_match.values()):
        print(f"[DBG_PARTIDO] idx={idx_partido} n_l='{n_l}' n_v='{n_v}' "
              f"clave_ff_partido='{n_l_norm}-{n_v_norm}'")
        for k_ff, info in puntos_fantasy_match.items():
            if es_debug_nombre(info["nombre_original"]):
                print(f"[DBG_PARTIDO_FF] idx={idx_partido} clave_ff='{k_ff}' "
                      f"orig='{info['nombre_original']}' nom_norm='{info['nombre_norm']}' "
                      f"puntos={info['puntos']} equipo_norm='{info['equipo_norm']}'")

    lineup_divs = soup.find_all('div', class_='lineup')
    titulares_nombres = []
    if lineup_divs:
        for div in lineup_divs:
            titulares_partido = [a.get_text().strip() for a in div.find_all('a')][:11]
            titulares_nombres.extend(titulares_partido)

    equipo_local_nombres = [a.get_text().strip() for a in lineup_divs[0].find_all('a')] if lineup_divs else []

    tablas_por_tipo = {}
    for tipo in ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']:
        dic = {}
        if tipo == 'keepers':
            table_objs = soup.find_all('table', id=re.compile(r'^keeper_stats_.*'))
        else:
            table_objs = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))

        for table_obj in table_objs:
            caption = table_obj.find('caption')
            caption_text = caption.get_text(strip=True) if caption else ""
            equipo_tabla_from_caption = None
            if caption_text.endswith("Player Stats Table"):
                nombre_equipo_caption = caption_text.replace(" Player Stats Table", "").strip()
                equipo_tabla_from_caption = nombre_equipo_caption

            try:
                df_raw = pd.read_html(StringIO(str(table_obj)))[0]
            except Exception:
                continue

            df_raw.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_raw.columns.get_level_values(-1)
            ]

            table_id = table_obj.get('id', '')

            for _, row in df_raw.iterrows():
                nombre_raw = re.sub(r'\s\(.*\)', '', str(row['Player'])).strip()
                if (
                    nombre_raw in ['nan', 'Player', 'Total', 'Players'] or
                    re.match(r'^\d+\s+Players$', nombre_raw)
                ):
                    continue

                equipo = str(row.get('Squad', '')).strip() if 'Squad' in row else ""

                if not equipo:
                    if equipo_tabla_from_caption:
                        equipo = equipo_tabla_from_caption
                    elif "_home_" in table_id:
                        equipo = n_l
                    elif "_away_" in table_id:
                        equipo = n_v

                equipo_norm = normalizar_equipo(equipo) if equipo else None

                fb_norm = normalizar_texto(
                    aplicar_alias_contextual(nombre_raw, equipo_norm)
                )

                if equipo_norm in ("valencia", "betis"):
                    print(f"[FBREF_VALBET] tipo={tipo} partido_idx={idx_partido} "
                          f"table_id='{table_id}' equipo='{equipo}' equipo_norm='{equipo_norm}' "
                          f"player_raw='{nombre_raw}' fb_norm='{fb_norm}'")

                if es_debug_nombre(nombre_raw) or es_debug_nombre(fb_norm):
                    print(f"[FBREF_DEBUG] tipo={tipo} partido_idx={idx_partido} "
                          f"table_id='{table_id}' equipo='{equipo}' equipo_norm='{equipo_norm}' "
                          f"player_raw='{nombre_raw}' fb_norm='{fb_norm}'")

                dic[fb_norm] = row

        tablas_por_tipo[tipo] = dic

    propuestas_match = []

    for fb_norm, row_sum in tablas_por_tipo.get('summary', {}).items():
        p_fb = str(row_sum.get('Player', '')).strip()

        es_local = p_fb in equipo_local_nombres
        equipo_fb = n_l_norm if es_local else n_v_norm

        partes_fb_norm = fb_norm.split()
        primer_nombre = partes_fb_norm[0] if partes_fb_norm else fb_norm
        ultimo_apellido = partes_fb_norm[-1] if len(partes_fb_norm) >= 2 else ""

        if len(partes_fb_norm) >= 2:
            nombre_apellido = f"{primer_nombre} {ultimo_apellido}"
        else:
            nombre_apellido = fb_norm

        min_fb = limpiar_int(row_sum.get('Min', 0))
        pos_raw = str(row_sum.get('Pos', 'MC')).split(',')[0].strip().upper()
        if pos_raw == 'GK':
            pos_val = 'PT'
        elif pos_raw in ['DF', 'RB', 'LB', 'CB']:
            pos_val = 'DF'
        elif pos_raw in ['FW', 'RW', 'LW']:
            pos_val = 'DT'
        else:
            pos_val = 'MC'

        candidatos_equipo = {
            k: info for k, info in puntos_fantasy_match.items()
            if info.get("equipo_norm") == equipo_fb
        }
        nombres_ff_norm = [info["nombre_norm"] for info in candidatos_equipo.values()]

        best_name_norm = None
        best_score = 0.0

        def intentar_match(cadena, current_best_name, current_best_score):
            if not nombres_ff_norm:
                return current_best_name, current_best_score, []
            matches = process.extract(
                cadena,
                nombres_ff_norm,
                scorer=fuzz.WRatio,
                limit=5
            )
            if not matches:
                return current_best_name, current_best_score, []
            posibles = [n for n in nombres_ff_norm if n == cadena]
            if len(posibles) > 1:
                cand, score, _ = matches[0]
                if cand == cadena and score == 100:
                    return cand, score, matches
                else:
                    return current_best_name, current_best_score, matches
            elif len(posibles) == 1:
                cand, score, _ = matches[0]
                if cand == cadena and score > current_best_score:
                    return cand, score, matches
                else:
                    return current_best_name, current_best_score, matches
            if re.match(r"^[a-z]\.[ ]?[a-z]+$", cadena):
                cand, score, _ = matches[0]
                if cand == cadena and score == 100:
                    return cand, score, matches
                else:
                    return current_best_name, current_best_score, matches
            cand, score, _ = matches[0]
            if score > current_best_score:
                return cand, score, matches
            return current_best_name, current_best_score, matches

        matches_usados = []

        best_name_norm, best_score, matches_usados = intentar_match(
            fb_norm, best_name_norm, best_score
        )
        if best_score < UMBRAL_MATCH and nombre_apellido:
            best_name_norm, best_score, matches_usados = intentar_match(
                nombre_apellido, best_name_norm, best_score
            )
        if best_score < UMBRAL_MATCH and ultimo_apellido:
            best_name_norm, best_score, matches_usados = intentar_match(
                ultimo_apellido, best_name_norm, best_score
            )

        if best_score < UMBRAL_MATCH:
            best_name_norm = None
            best_score = 0.0

        best_name_original = None
        if best_name_norm is not None:
            for info in candidatos_equipo.values():
                if info["nombre_norm"] == best_name_norm:
                    best_name_original = info["nombre_original"]
                    break

        propuestas_match.append({
            "clave_fb": fb_norm,
            "p_fb": p_fb,
            "fb_norm": fb_norm,
            "equipo_fb": equipo_fb,
            "min_fb": min_fb,
            "pos_val": pos_val,
            "best_name_norm": best_name_norm,
            "best_name_original": best_name_original,
            "best_score": best_score,
            "row_sum": row_sum,
        })

        if equipo_fb in ("valencia", "betis"):
            print(f"[MATCH_VALBET] partido_idx={idx_partido} equipo_fb={equipo_fb} "
                  f"p_fb='{p_fb}' fb_norm='{fb_norm}' "
                  f"candidatos={nombres_ff_norm} "
                  f"best_norm='{best_name_norm}' best_orig='{best_name_original}' "
                  f"score={best_score} matches={matches_usados}")

        if es_debug_nombre(p_fb) or es_debug_nombre(fb_norm):
            print(f"[MATCH_DEBUG] partido_idx={idx_partido} equipo_fb={equipo_fb} "
                  f"p_fb='{p_fb}' fb_norm='{fb_norm}' "
                  f"candidatos={nombres_ff_norm} "
                  f"best_norm='{best_name_norm}' best_orig='{best_name_original}' "
                  f"score={best_score} matches={matches_usados}")

    fantasy_por_nombre_norm = {}
    for k_ff, info in puntos_fantasy_match.items():
        nombre_norm = info["nombre_norm"]
        fantasy_por_nombre_norm.setdefault(nombre_norm, []).append({
            "clave_ff": k_ff,
            "puntos": info["puntos"],
            "info": info,
        })

    for nombre_norm, lista in fantasy_por_nombre_norm.items():
        if nombre_norm in ("isi palazon", "pepelu", "chimy"):
            print(f"[DBG_FF_GROUP] partido_idx={idx_partido} nombre_norm='{nombre_norm}' "
                  f"candidatos_ff={[ (x['clave_ff'], x['puntos']) for x in lista ]}")

    asignacion_fb_a_ff = {}

    propuestas_por_nombre_norm = {}
    for prop in propuestas_match:
        nombre_norm = prop["best_name_norm"]
        score = prop["best_score"]
        if not nombre_norm or score < UMBRAL_MATCH:
            continue
        propuestas_por_nombre_norm.setdefault(nombre_norm, []).append(prop)

    for nombre_norm, props in propuestas_por_nombre_norm.items():
        candidatos_ff = fantasy_por_nombre_norm.get(nombre_norm, [])
        if not candidatos_ff:
            if nombre_norm in ("isi palazon", "pepelu", "chimy"):
                print(f"[DBG_ASIG] sin candidatos_ff para nombre_norm='{nombre_norm}'")
            continue

        props_ordenadas = sorted(props, key=lambda p: p["min_fb"], reverse=True)
        cands_ordenados = sorted(candidatos_ff, key=lambda x: x["puntos"], reverse=True)

        for prop, cand in zip(props_ordenadas, cands_ordenados):
            asignacion_fb_a_ff[prop["clave_fb"]] = cand["clave_ff"]
            if nombre_norm in ("isi palazon", "pepelu", "chimy"):
                print(f"[DBG_ASIG] nombre_norm='{nombre_norm}' "
                      f"clave_fb='{prop['clave_fb']}' -> clave_ff='{cand['clave_ff']}' "
                      f"puntos={cand['puntos']}")

    db = {}

    for prop in propuestas_match:
        clave_fb = prop["clave_fb"]
        p_fb = prop["p_fb"]
        fb_norm = prop["fb_norm"]
        equipo_fb = prop["equipo_fb"]
        min_fb = prop["min_fb"]
        pos_val = prop["pos_val"]
        row_sum = prop["row_sum"]

        equipo_rival = n_v_norm if equipo_fb == n_l_norm else n_l_norm

        clave_db = f"{fb_norm}|{equipo_fb}|{min_fb}|{pos_val}"

        nombre_csv = p_fb

        if clave_db not in db:
            db[clave_db] = {c: np.nan for c in COLUMNAS_MODELO}
            db[clave_db].update({
                'player': nombre_csv,
                'Equipo_propio': equipo_fb,
                'Equipo_rival': equipo_rival,
                'Titular': 1 if p_fb in titulares_nombres else 0,
                'Goles_en_contra': np.nan,
                'Porcentaje_paradas': np.nan,
                'PSxG': np.nan,
                'posicion': pos_val,
            })

        db[clave_db]['Min_partido'] = limpiar_int(row_sum.get('Min', 0))
        db[clave_db]['Gol_partido'] = limpiar_int(row_sum.get('Gls', 0))
        db[clave_db]['Asist_partido'] = limpiar_int(row_sum.get('Ast', 0))
        db[clave_db]['xG_partido'] = limpiar_float(row_sum.get('xG', 0))
        db[clave_db]['xAG'] = limpiar_float(row_sum.get('xAG', 0))
        db[clave_db]['Tiros'] = limpiar_int(row_sum.get('Sh', 0))
        sh_total = limpiar_int(row_sum.get('Sh', 0))
        sot = limpiar_int(row_sum.get('SoT', 0))
        db[clave_db]['TiroFallado_partido'] = max(sh_total - sot, 0)
        db[clave_db]['TiroPuerta_partido'] = sot
        db[clave_db]['Pases_Totales'] = limpiar_int(row_sum.get('Att', 0))

        row_pas = tablas_por_tipo.get('passing', {}).get(clave_fb)
        cmp_pct = 0.0
        if row_pas is not None and 'Cmp%' in row_pas:
            cmp_pct = limpiar_float(row_pas['Cmp%'])
        elif 'Cmp%' in row_sum:
            cmp_pct = limpiar_float(row_sum['Cmp%'])
        db[clave_db]['Pases_Completados_Pct'] = cmp_pct

        row_def = tablas_por_tipo.get('defense', {}).get(clave_fb)
        if row_def is not None:
            db[clave_db]['Entradas'] = limpiar_int(row_def.get('Tkl', 0))
            db[clave_db]['Duelos'] = limpiar_int(row_def.get('Att', 0))
            db[clave_db]['DuelosGanados'] = limpiar_int(row_def.get('Won', 0))
            db[clave_db]['DuelosPerdidos'] = limpiar_int(row_def.get('Lost', 0))
            db[clave_db]['Bloqueos'] = limpiar_int(row_def.get('Blocks', 0))
            db[clave_db]['BloqueoTiros'] = limpiar_int(row_def.get('Sh', 0))
            db[clave_db]['BloqueoPase'] = limpiar_int(row_def.get('Pass', 0))
            db[clave_db]['Despejes'] = limpiar_int(row_def.get('Clr', 0))

        row_poss = tablas_por_tipo.get('possession', {}).get(clave_fb)
        if row_poss is not None:
            db[clave_db]['Regates'] = limpiar_int(row_poss.get('Att', 0))
            db[clave_db]['RegatesCompletados'] = limpiar_int(row_poss.get('Succ', 0))
            db[clave_db]['RegatesFallidos'] = limpiar_int(row_poss.get('Tkld', 0))
            db[clave_db]['Conducciones'] = limpiar_int(row_poss.get('Carries', 0))
            db[clave_db]['DistanciaConduccion'] = limpiar_float(row_poss.get('TotDist', 0))
            db[clave_db]['MetrosAvanzadosConduccion'] = limpiar_float(row_poss.get('PrgDist', 0))
            db[clave_db]['ConduccionesProgresivas'] = limpiar_int(row_poss.get('PrgC', 0))

        row_misc = tablas_por_tipo.get('misc', {}).get(clave_fb)
        if row_misc is not None:
            db[clave_db]['Amarillas'] = limpiar_int(row_misc.get('CrdY', 0))
            db[clave_db]['Rojas'] = limpiar_int(row_misc.get('CrdR', 0))
            db[clave_db]['DuelosAereosGanados'] = limpiar_int(row_misc.get('Won', 0))
            db[clave_db]['DuelosAereosPerdidos'] = limpiar_int(row_misc.get('Lost', 0))
            db[clave_db]['DuelosAereosGanadosPct'] = limpiar_float(row_misc.get('Won%', 0))

        if pos_val == 'PT':
            keepers_dict = tablas_por_tipo.get('keepers', {})
            row_keep = keepers_dict.get(clave_fb)
            if row_keep is not None:
                ga_val = limpiar_int(row_keep.get('GA', 0))
                sv_val = 0.0
                for col_sv in ['Save%', 'Sv%', 'SV%']:
                    if col_sv in row_keep:
                        sv_val = limpiar_float(row_keep[col_sv])
                        break
                psxg_val = limpiar_float(row_keep.get('PSxG', 0)) if 'PSxG' in row_keep else 0.0
                db[clave_db]['Goles_en_contra'] = ga_val
                db[clave_db]['Porcentaje_paradas'] = sv_val
                db[clave_db]['PSxG'] = psxg_val

        clave_ff_asignada = asignacion_fb_a_ff.get(clave_fb)
        puntos_asignados = 0
        if clave_ff_asignada is not None:
            puntos_asignados = puntos_fantasy_match[clave_ff_asignada]['puntos']
        db[clave_db]['puntosFantasy'] = puntos_asignados

        if equipo_fb in ("valencia", "betis"):
            print(f"[ASIG_VALBET] partido_idx={idx_partido} equipo_fb={equipo_fb} "
                  f"p_fb='{p_fb}' fb_norm='{fb_norm}' clave_db='{clave_db}' "
                  f"clave_ff_asignada={clave_ff_asignada} puntosFantasy={puntos_asignados}")

        if es_debug_nombre(p_fb) or es_debug_nombre(fb_norm):
            print(f"[ASIG_DEBUG] partido_idx={idx_partido} equipo_fb={equipo_fb} "
                  f"p_fb='{p_fb}' fb_norm='{fb_norm}' clave_db='{clave_db}' "
                  f"clave_ff_asignada={clave_ff_asignada} puntosFantasy={puntos_asignados}")

        if clave_ff_asignada is None and idx_partido in (1, 2, 3):
            JUGADORES_SIN_MATCH.append({
                "partido_idx": idx_partido,
                "equipo_local": n_l,
                "equipo_visitante": n_v,
                "nombre_fbref": p_fb,
                "fb_norm": fb_norm,
            })

    df_final = pd.DataFrame.from_dict(db, orient='index')
    if not df_final.empty:
        if 'Equipo_propio' in df_final.columns:
            df_final['Equipo_propio'] = df_final['Equipo_propio'].apply(normalizar_equipo)
        if 'Equipo_rival' in df_final.columns:
            df_final['Equipo_rival'] = df_final['Equipo_rival'].apply(normalizar_equipo)

        mask_no_gk = df_final['posicion'] != 'PT'
        df_final.loc[mask_no_gk, 'Goles_en_contra'] = 0.0
        df_final.loc[mask_no_gk, 'Porcentaje_paradas'] = 0.0
        df_final.fillna(0, inplace=True)

        mask_doble_amarilla = df_final['Amarillas'] >= 2
        df_final.loc[mask_doble_amarilla, 'Rojas'] = 1.0

        debug_rows = df_final[df_final['player'].apply(es_debug_nombre)]
        if not debug_rows.empty:
            print(f"[DF_DEBUG] idx={idx_partido} filas debug antes de to_csv:")
            print(debug_rows[['player', 'Equipo_propio', 'puntosFantasy', 'Min_partido']])

    return df_final, n_l, n_v


def ejecutar_rango(inicio, fin):
    print("🚀 INICIANDO SISTEMA...")
    calendario = obtener_calendario_local_o_remoto()

    for j_val in range(inicio, fin + 1):
        num_j = str(j_val)
        print(f"\n--- JORNADA {num_j} ---")

        puntos_por_partido = extraer_puntos_fantasy_jornada(num_j)

        j_html_dir = os.path.join(BASE_FOLDER_HTML, f"j{j_val}")
        j_csv_dir = os.path.join(BASE_FOLDER_CSV, f"jornada_{num_j}")
        os.makedirs(j_html_dir, exist_ok=True)
        os.makedirs(j_csv_dir, exist_ok=True)

        jugadores_sin_match_jornada = []

        for idx in range(1, 11):
            path_html = os.path.join(j_html_dir, f"p{idx}.html")
            if not os.path.exists(path_html):
                continue

            print(f"     📂 [P{idx}] Usando local: {path_html}")
            with open(path_html, "r", encoding="utf-8") as f:
                html_content = f.read()

            n_l, n_v = obtener_nombres_partido_fbref(html_content)
            n_l_norm = normalizar_equipo(n_l)
            n_v_norm = normalizar_equipo(n_v)
            clave_ff_partido = f"{n_l_norm}-{n_v_norm}"

            dict_ff = puntos_por_partido.get(clave_ff_partido, {})

            global JUGADORES_SIN_MATCH
            JUGADORES_SIN_MATCH = []
            df, loc, vis = procesar_partido(html_content, dict_ff, idx)

            if df is not None and not df.empty:
                fname = f"p{idx}_{normalizar_texto(loc)}-{normalizar_texto(vis)}.csv"
                df.to_csv(os.path.join(j_csv_dir, fname), index=False, encoding='utf-8-sig')
                print("     ✅ CSV generado.")
            df_cero = df[df['puntosFantasy'] == 0]

            if not df_cero.empty:
                for _, row in df_cero.iterrows():
                    print(f"         - {row['player']}  -> 0 puntos")

            if JUGADORES_SIN_MATCH:
                jugadores_sin_match_jornada.extend(JUGADORES_SIN_MATCH)


if __name__ == "__main__":
    ejecutar_rango(inicio=1, fin=1)

    if JUGADORES_SIN_MATCH:
        print("\n[LOG] Jugadores que han quedado sin match en ninguna asignación de puntos:")
        print("PARTIDO_IDX | EQUIPO_LOCAL | EQUIPO_VISITANTE | NOMBRE_FBREF | FB_NORM")
        print("-" * 80)
        for j in JUGADORES_SIN_MATCH:
            print(f" {j['partido_idx']} | {j['equipo_local']} | {j['equipo_visitante']} | {j['nombre_fbref']} | {j['fb_norm']}")
    else:
        print("\n[LOG] Todos los jugadores han sido asignados correctamente.")
