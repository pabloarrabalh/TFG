# ================== REFUERZO CLAVES MATCHING JUGADORES ==================
def generar_claves_jugador(nombre):
    nombre = normalizar_clave_match(nombre)
    partes = nombre.split()
    claves = set()
    if len(partes) == 1:
        claves.add(partes[0])
    elif len(partes) == 2:
        claves.add(nombre)
        claves.add(partes[0])  # solo nombre
        claves.add(partes[1])  # solo apellido
        claves.add(f"{partes[0][0]}. {partes[1]}")  # inicial. apellido
        claves.add(f"{partes[0][0]} {partes[1]}")    # inicial apellido
    elif len(partes) > 2:
        claves.add(nombre)
        claves.add(' '.join(partes[:2]))  # nombre compuesto
        claves.add(' '.join(partes[-2:])) # apellido compuesto
        claves.add(partes[0])  # solo primer nombre
        claves.add(partes[-1]) # solo último apellido
        claves.add(f"{partes[0][0]}. {partes[-1]}")  # inicial. apellido
        claves.add(f"{partes[0][0]} {partes[-1]}")    # inicial apellido
        # Añadir todos los nombres y apellidos por separado
        for p in partes:
            claves.add(p)
    return list(claves)
import pandas as pd
import os, re, time, random
import unicodedata
from io import StringIO
from bs4 import BeautifulSoup
import cloudscraper

# --- CONFIGURACIÓN ---
pd.set_option('display.max_columns', None)
BASE_FOLDER_HTML = os.path.join("main", "html")
BASE_FOLDER_CSV = os.path.join("data", "temporada_25_26")

os.makedirs(BASE_FOLDER_HTML, exist_ok=True)
os.makedirs(BASE_FOLDER_CSV, exist_ok=True)

COLUMNAS_MODELO = [
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular',
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido', 'xA_partido',
    'TiroFallado_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct',
    'Amarillas', 'Rojas', 'Goles_en_contra', 'Porcentaje_paradas', 'PSxG', 'puntosFantasy',
    'Entradas', 'Duelos', 'DuelosGanados', 'DuelosPerdidos',
    'Bloqueos', 'BloqueoTiros', 'BloqueoPase', 'Despejes',
    'Regates', 'RegatesCompletados', 'RegatesFallidos',
    'Conducciones', 'DistanciaConduccion', 'MetrosAvanzadosConduccion', 'ConduccionesProgresivas',
    'DuelosAereosGanados', 'DuelosAereosPerdidos', 'DuelosAereosGanadosPct'
]

JUGADORES_SIN_MATCH = []

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

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

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def normalizar_clave_match(s):
    s = normalizar_texto(s)
    s = s.replace('.', ' ')
    s = re.sub(r'[-–—]', '', s)  # Elimina guiones
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace(' ', '')  # Elimina espacios para matching total

# Alias imprescindibles para equipos
ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "villarreal cf": "villarreal",
    "real oviedo": "oviedo",
    "celta vigo": "celta",
    "alaves": "alaves",
    "alavés": "alaves",
    "athletic club": "athletic",
    "elche cf": "elche",
    "sevilla fc": "sevilla",
    "real betis": "betis",
    "atlético": "atletico madrid",
    "atletico": "atletico madrid",
}

def normalizar_equipo(nombre):
    base = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(base, base)

def limpiar_float(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return 0.0

def limpiar_int(val):
    return int(round(limpiar_float(val)))

def obtener_calendario_local_o_remoto():
    path_local = "calendario.html"
    if os.path.exists(path_local):
        print("     📂 Cargando calendario desde archivo LOCAL")
        with open(path_local, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        print("     🌐 Intentando descarga de calendario desde FBRef...")
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

# ============ SCRAPPING DE puntos.html ============

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

                # Construir clave de FF: inicial-apellido si hay nombre+apellido
                nombre_clave = nombre_real
                partes = nombre_real.split()
                if len(partes) == 2 and len(partes[0]) == 2 and partes[0][1] == '.':
                    # Ya es 'N. Apellido'
                    pass
                elif len(partes) >= 2:
                    inicial = partes[0][0].lower()
                    apellido = partes[-1].lower()
                    nombre_clave = f"{inicial}-{apellido}"
                else:
                    nombre_clave = normalizar_clave_match(nombre_real)

                puntos = 0
                span_puntos = fila.select_one("span.laliga-fantasy")
                if span_puntos:
                    txt = span_puntos.get_text(strip=True)
                    try:
                        puntos = int(float(txt))
                    except:
                        puntos = 0


                claves_jugador = generar_claves_jugador(nombre_real)
                equipo_norm = equipo_tabla_norm
                for nombre_norm in claves_jugador:
                    clave_ff = f"{equipo_norm}|{nombre_norm}"
                    info_jugador = {
                        "nombre_original": nombre_real,
                        "puntos": puntos,
                        "equipo": equipo_tabla_norm,
                        "nombre_norm": nombre_norm,
                        "equipo_norm": equipo_norm,
                    }
                    if clave_ff in puntos_map:
                        if abs(puntos) > abs(puntos_map[clave_ff]["puntos"]):
                            puntos_map[clave_ff] = info_jugador
                    else:
                        puntos_map[clave_ff] = info_jugador

        res[clave_partido] = puntos_map

    return res

# ====================== AUXILIAR: OBTENER NOMBRES ======================

def obtener_nombres_partido_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"
    return n_l, n_v

# ================================ PROCESAR PARTIDO ================================

def procesar_partido(html_content, puntos_fantasy_dict, idx_partido):
    # LOG especial para los hermanos Williams
    log_williams = []

    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"

    n_l_norm = normalizar_equipo(n_l)
    n_v_norm = normalizar_equipo(n_v)

    puntos_fantasy_match = puntos_fantasy_dict  # ya es dict clave_ff -> info

    lineup_divs = soup.find_all('div', class_='lineup')
    titulares_nombres = []
    if lineup_divs:
        for div in lineup_divs:
            titulares_partido = [a.get_text().strip() for a in div.find_all('a')][:11]
            titulares_nombres.extend(titulares_partido)

    equipo_local_nombres = [a.get_text().strip() for a in lineup_divs[0].find_all('a')] if lineup_divs else []

    # Leer todas las tablas de FBRef una vez e indexar por clave_fb (nombre FBRef puro)
    tablas_por_tipo = {}
    for tipo in ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']:
        dic = {}
        if tipo == 'keepers':
            table_objs = soup.find_all('table', id=re.compile(r'^keeper_stats_.*'))
        else:
            table_objs = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))

        for table_obj in table_objs:
            try:
                df_raw = pd.read_html(StringIO(str(table_obj)))[0]
            except Exception:
                continue

            df_raw.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_raw.columns.get_level_values(-1)
            ]

            for _, row in df_raw.iterrows():
                nombre_raw = re.sub(r'\s\(.*\)', '', str(row['Player'])).strip()
                if (
                    nombre_raw in ['nan', 'Player', 'Total', 'Players'] or
                    re.match(r'^\d+\s+Players$', nombre_raw)
                ):
                    continue
                clave_fb = normalizar_texto(nombre_raw)
                dic[clave_fb] = row

        tablas_por_tipo[tipo] = dic

    db = {}

    # Alias especiales de jugadores problemáticos (solo para match FF)
    ALIAS_JUGADORES = {
        'isaac palazon camacho': 'isi',
        'isi palazon': 'isi',
        'isi': 'isi',
        'viktor tsyhankov': 'tsygankov',
        'luiz lucio reis junior': 'luiz junior',
        'luiz reis junior': 'luiz junior',
        'luiz junior': 'luiz junior',
        'paulo gazzaniga': 'gazzaniga',
        'gazzaniga': 'gazzaniga',
        'rahim bonkano': 'alhassane',
        'ezequiel avila': 'chimy',
        'ezequiel chimy avila': 'chimy',
        'chimy avila': 'chimy',
        'avila': 'chimy',
        'chimy': 'chimy',
        # Alias para Alexander-Arnold cuando FF lo pone sin "Trent"
        'alexander arnold': 'trent alexander-arnold',
    }

    # Recorremos jugadores según summary (clave_fb es la clave del diccionario)
    for clave_fb, row_sum in tablas_por_tipo.get('summary', {}).items():
        # Log para los Williams
        if 'williams' in clave_fb:
            log_williams.append({
                'clave_fb': clave_fb,
                'row_sum_player': str(row_sum.get('Player', '')).strip(),
                'row_sum': dict(row_sum),
            })

        p_fb = str(row_sum.get('Player', '')).strip()
        fb_norm = normalizar_texto(p_fb)
        partes = fb_norm.split()
        fb_short = partes[-1] if partes else fb_norm

        # Aplicar alias solo para construir candidatos de FF
        fb_match = fb_norm
        for alias_key, alias_val in ALIAS_JUGADORES.items():
            if fb_match == alias_key or fb_match.endswith(alias_key) or fb_match.startswith(alias_key):
                fb_match = alias_val
                partes = fb_match.split()
                fb_short = partes[-1]
                break

        # caso especial Chimy Ávila
        if 'avila' in fb_match and ('chimy' in p_fb.lower() or 'chimy' in fb_match):
            fb_match = 'chimy'
            partes = ['chimy']
            fb_short = 'chimy'

        # equipo del jugador según FBRef
        es_local = p_fb in equipo_local_nombres
        equipo_fb = n_l_norm if es_local else n_v_norm

        # Candidatos de nombre para el match con FutbolFantasy
        candidatos = set()
        if fb_match:
            candidatos.add(fb_match)
        if fb_short:
            candidatos.add(fb_short)

        if len(partes) >= 2:
            candidatos.add(" ".join(partes[-2:]))
            inicial = partes[0][0]
            apellido = partes[-1]
            # Añadir variantes con y sin punto
            candidatos.add(f"{inicial} {apellido}")
            candidatos.add(f"{inicial}. {apellido}")
            # Añadir variantes con nombre completo abreviado
            candidatos.add(f"{inicial} {fb_short}")
            candidatos.add(f"{inicial}. {fb_short}")
            candidatos.add(f"{inicial} {partes[-2]} {partes[-1]}")
            candidatos.add(f"{inicial}. {partes[-2]} {partes[-1]}")
            # Añadir variante con inicial y apellido sin tildes ni punto
            apellido_norm = normalizar_texto(apellido)
            candidatos.add(f"{inicial} {apellido_norm}")
            candidatos.add(f"{inicial}. {apellido_norm}")

        if len(partes) >= 3:
            candidatos.add(" ".join(partes[1:]))

        if len(partes) >= 2 and partes[-2] == 'de':
            candidatos.add(partes[-2] + ' ' + partes[-1])
            candidatos.add(partes[-1])

        # Alias especiales para Chimy Ávila (refuerzo)
        if 'chimy' in fb_match or 'avila' in fb_match:
            candidatos.add('chimy')
            candidatos.add('chimy avila')
            candidatos.add('avila')

        # Normalizar todas las variantes (quita tildes, minúsculas, quita puntos extra)
        candidatos_norm = {normalizar_clave_match(c.replace('.', '')) for c in candidatos if c}

        n_final, pts_f = p_fb, 0
        mejor_clave_ff = None

        # Prioridad: inicial+apellido (N. Williams / I. Williams)
        match_prioridad = []
        if len(partes) >= 2:
            inicial = partes[0][0].upper()
            apellido = partes[-1].capitalize()
            match_prioridad.append(f"{inicial}. {apellido}")
            match_prioridad.append(f"{inicial} {apellido}")
        match_prioridad.extend(list(candidatos))

        equipo_ff = equipo_fb  # ya normalizado

        # 1) Match exacto equipo+nombre con prioridad
        for cand_nm in match_prioridad:
            clave_ff = f"{equipo_ff}|{normalizar_clave_match(cand_nm)}"
            if clave_ff in puntos_fantasy_match:
                info = puntos_fantasy_match[clave_ff]
                n_final, pts_f = info['nombre_original'], info['puntos']
                mejor_clave_ff = clave_ff
                break

        # 2) Match flexible dentro del mismo equipo usando nombre_norm/equipo_norm
        if mejor_clave_ff is None and puntos_fantasy_match:
            for ff_key, info in puntos_fantasy_match.items():
                equipo_ff_norm = info.get("equipo_norm", "")
                if equipo_ff_norm != equipo_ff:
                    continue
                nombre_ff_norm = info.get("nombre_norm", "")
                if not nombre_ff_norm:
                    continue

                for cand_nm in candidatos_norm:
                    if cand_nm == nombre_ff_norm:
                        n_final, pts_f = info['nombre_original'], info['puntos']
                        mejor_clave_ff = ff_key
                        break
                    if cand_nm.endswith(nombre_ff_norm) or nombre_ff_norm.endswith(cand_nm):
                        n_final, pts_f = info['nombre_original'], info['puntos']
                        mejor_clave_ff = ff_key
                        break
                if mejor_clave_ff is not None:
                    break

        # Clave de DB: nombre FBRef normalizado + equipo (para no mezclar hermanos)
        clave_db = f"{normalizar_clave_match(p_fb)}|{equipo_fb}"

        # Nombre a mostrar en CSV: SIEMPRE el alias normalizado (igual que clave de comparación)
        # Para Williams, mantener inicial+apellido; para alias como Chimy, usar el alias
        nombre_csv = n_final
        # Si el alias es 'chimy', mostrar 'chimy' siempre
        if normalizar_clave_match(fb_match) == 'chimy':
            nombre_csv = 'chimy'
        # Si es Williams, mantener inicial+apellido
        elif normalizar_clave_match(p_fb).endswith('williams'):
            partes_nombre = p_fb.strip().split()
            if len(partes_nombre) >= 2:
                inicial = partes_nombre[0][0].upper()
                apellido = partes_nombre[-1].capitalize()
                nombre_csv = f"{inicial}. {apellido}"
        # Si el alias es otro (por ejemplo, 'isi'), mostrar el alias
        elif fb_match != fb_norm:
            nombre_csv = fb_match

        # Inicializar estructura del jugador si no existe
        if clave_db not in db:
            db[clave_db] = {c: 0 for c in COLUMNAS_MODELO}
            db[clave_db].update({
                'player': nombre_csv,
                'Equipo_propio': n_l_norm if es_local else n_v_norm,
                'Equipo_rival': n_v_norm if es_local else n_l_norm,
                'Titular': 1 if p_fb in titulares_nombres else 0,
                'Goles_en_contra': 0.0,
                'Porcentaje_paradas': 0.0,
                'PSxG': 0.0
            })
            pos_raw = str(row_sum.get('Pos', 'MC')).split(',')[0].strip().upper()
            if pos_raw == 'GK':
                pos_val = 'PT'
            elif pos_raw in ['DF', 'RB', 'LB', 'CB']:
                pos_val = 'DF'
            elif pos_raw in ['FW', 'RW', 'LW']:
                pos_val = 'DT'
            else:
                pos_val = 'MC'
            db[clave_db]['posicion'] = pos_val

        # Asegurar que siempre haya posición
        if 'posicion' not in db[clave_db]:
            pos_raw = str(row_sum.get('Pos', 'MC')).split(',')[0].strip().upper()
            if pos_raw == 'GK':
                pos_val = 'PT'
            elif pos_raw in ['DF', 'RB', 'LB', 'CB']:
                pos_val = 'DF'
            elif pos_raw in ['FW', 'RW', 'LW']:
                pos_val = 'DT'
            else:
                pos_val = 'MC'
            db[clave_db]['posicion'] = pos_val

        # LOG SOLO PARA JUGADORES DEL REAL MADRID
        if (n_l_norm == 'real madrid' or n_v_norm == 'real madrid') and db[clave_db]['Equipo_propio'] == 'real madrid':
            print(f"[REALMADRID-LOG] Jugador: '{p_fb}' | player_csv: '{nombre_csv}' | puntos: {db[clave_db].get('puntosFantasy', 0)} | clave_db: '{clave_db}' | mapeo antes de CSV: {db[clave_db]}")
        # Guardar el nombre formateado (siempre)
        db[clave_db]['player'] = nombre_csv

        # SUMMARY (stats desde FBRef usando clave_fb)
        db[clave_db]['Min_partido'] = limpiar_int(row_sum.get('Min', 0))
        db[clave_db]['Gol_partido'] = limpiar_float(row_sum.get('Gls', 0))
        db[clave_db]['Asist_partido'] = limpiar_float(row_sum.get('Ast', 0))
        db[clave_db]['xG_partido'] = limpiar_float(row_sum.get('xG', 0))
        db[clave_db]['xA_partido'] = limpiar_float(row_sum.get('xAG', 0))

        sh_total = limpiar_float(row_sum.get('Sh', 0))
        sot = limpiar_float(row_sum.get('SoT', 0))
        tiros_fallados = max(sh_total - sot, 0)
        db[clave_db]['TiroFallado_partido'] = tiros_fallados
        db[clave_db]['TiroPuerta_partido'] = sot

        # PASSING
        row_pas = tablas_por_tipo.get('passing', {}).get(clave_fb)
        cmp_pct = 0.0
        if row_pas is not None:
            db[clave_db]['Pases_Totales'] = limpiar_int(row_pas.get('Att', 0))
            if 'Cmp%' in row_pas:
                cmp_pct = limpiar_float(row_pas['Cmp%'])
        if cmp_pct == 0.0 and 'Cmp%' in row_sum:
            cmp_pct = limpiar_float(row_sum['Cmp%'])
        db[clave_db]['Pases_Completados_Pct'] = cmp_pct

        # DEFENSE
        row_def = tablas_por_tipo.get('defense', {}).get(clave_fb)
        if row_def is not None:
            db[clave_db]['Entradas'] = limpiar_float(row_def.get('Tkl', 0))
            db[clave_db]['Duelos'] = limpiar_float(row_def.get('Att', 0))
            db[clave_db]['DuelosGanados'] = limpiar_float(row_def.get('Tkl%', 0))
            db[clave_db]['DuelosPerdidos'] = limpiar_float(row_def.get('Lost', 0))
            db[clave_db]['Bloqueos'] = limpiar_float(row_def.get('Blocks', 0))
            db[clave_db]['BloqueoTiros'] = limpiar_float(row_def.get('Sh', 0))
            db[clave_db]['BloqueoPase'] = limpiar_float(row_def.get('Pass', 0))
            db[clave_db]['Despejes'] = limpiar_float(row_def.get('Clr', 0))

        # POSSESSION
        row_poss = tablas_por_tipo.get('possession', {}).get(clave_fb)
        if row_poss is not None:
            db[clave_db]['Regates'] = limpiar_float(row_poss.get('Att', 0))
            db[clave_db]['RegatesCompletados'] = limpiar_float(row_poss.get('Succ', 0))
            db[clave_db]['RegatesFallidos'] = limpiar_float(row_poss.get('Tkld', 0))
            db[clave_db]['Conducciones'] = limpiar_float(row_poss.get('Carries', 0))
            db[clave_db]['DistanciaConduccion'] = limpiar_float(row_poss.get('TotDist', 0))
            db[clave_db]['MetrosAvanzadosConduccion'] = limpiar_float(row_poss.get('PrgDist', 0))
            db[clave_db]['ConduccionesProgresivas'] = limpiar_float(row_poss.get('PrgC', 0))

        # MISC
        row_misc = tablas_por_tipo.get('misc', {}).get(clave_fb)
        if row_misc is not None:
            db[clave_db]['Amarillas'] = limpiar_float(row_misc.get('CrdY', 0))
            db[clave_db]['Rojas'] = limpiar_float(row_misc.get('CrdR', 0))
            db[clave_db]['DuelosAereosGanados'] = limpiar_float(row_misc.get('Won', 0))
            db[clave_db]['DuelosAereosPerdidos'] = limpiar_float(row_misc.get('Lost', 0))
            db[clave_db]['DuelosAereosGanadosPct'] = limpiar_float(row_misc.get('Won%', 0))

        # PORTEROS
        if db[clave_db]['posicion'] == 'PT':
            keepers_dict = tablas_por_tipo.get('keepers', {})
            row_keep = keepers_dict.get(clave_fb)
            if row_keep is not None:
                ga_val = limpiar_float(row_keep.get('GA', 0))
                sv_val = 0.0
                for col_sv in ['Save%', 'Sv%', 'SV%']:
                    if col_sv in row_keep:
                        sv_val = limpiar_float(row_keep[col_sv])
                        break
                psxg_val = limpiar_float(row_keep.get('PSxG', 0)) if 'PSxG' in row_keep else 0.0
                db[clave_db]['Goles_en_contra'] = ga_val
                db[clave_db]['Porcentaje_paradas'] = sv_val
                db[clave_db]['PSxG'] = psxg_val
            else:
                db[clave_db]['Goles_en_contra'] = 0.0
                db[clave_db]['Porcentaje_paradas'] = 0.0
                db[clave_db]['PSxG'] = 0.0
        else:
            db[clave_db]['Goles_en_contra'] = 0.0
            db[clave_db]['Porcentaje_paradas'] = 0.0
            db[clave_db]['PSxG'] = 0.0

        # Puntos fantasy si hubo match
        if mejor_clave_ff is not None:
            db[clave_db]['puntosFantasy'] = pts_f

        # (Eliminado log general de asignación)

        # Solo guardamos jugadores sin match en los primeros partidos (debug)
        if mejor_clave_ff is None and idx_partido in (1, 2, 3):
            JUGADORES_SIN_MATCH.append({
                "partido_idx": idx_partido,
                "equipo_local": n_l,
                "equipo_visitante": n_v,
                "nombre_fbref": p_fb,
                "fb_norm": fb_norm,
                "fb_short": partes[-1] if partes else fb_norm
            })

    df_final = pd.DataFrame.from_dict(db, orient='index')
    if not df_final.empty:
        # Normalizar siempre los nombres de equipo
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

    return df_final, n_l, n_v

# ================================== MAIN ==================================

def ejecutar_rango(inicio, fin):
    print("🚀 INICIANDO SISTEMA...")
    calendario = obtener_calendario_local_o_remoto()

    # Procesar todos los partidos de la jornada (hasta 10 partidos por jornada)
    for j_val in range(inicio, fin + 1):
        num_j = str(j_val)
        print(f"\n--- JORNADA {num_j} ---")

        puntos_por_partido = extraer_puntos_fantasy_jornada(num_j)

        j_html_dir = os.path.join(BASE_FOLDER_HTML, f"j{num_j}")
        j_csv_dir = os.path.join(BASE_FOLDER_CSV, f"jornada_{num_j}")
        os.makedirs(j_html_dir, exist_ok=True)
        os.makedirs(j_csv_dir, exist_ok=True)

        jugadores_sin_match_jornada = []
        resumen_gueye = []
        resumen_alhassane = []
        resumen_iglesias = []  # seguir a TODOS los Iglesias, por equipo

        for idx in range(1, 11):
            path_html = os.path.join(j_html_dir, f"p{idx}.html")
            html_content = ""

            if os.path.exists(path_html):
                print(f"     📂 [P{idx}] Usando local: {path_html}")
                with open(path_html, "r", encoding="utf-8") as f:
                    html_content = f.read()
            else:
                continue

            n_l, n_v = obtener_nombres_partido_fbref(html_content)
            n_l_norm = normalizar_equipo(n_l)
            n_v_norm = normalizar_equipo(n_v)
            clave_ff_partido = f"{n_l_norm}-{n_v_norm}"
            print(f"     [LOG] P{idx}: n_l='{n_l}' n_v='{n_v}' | n_l_norm='{n_l_norm}' n_v_norm='{n_v_norm}' | clave_ff='{clave_ff_partido}'")
            dict_ff = puntos_por_partido.get(clave_ff_partido, {})

            # Log de Gueye, Alhassane e Iglesias
            for clave_map, info in dict_ff.items():
                nombre_norm = normalizar_texto(info['nombre_original'])
                equipo_info = info.get('equipo', '')
                if 'gueye' in nombre_norm:
                    resumen_gueye.append((idx, info['nombre_original'], equipo_info, info['puntos']))
                if 'alhassane' in nombre_norm:
                    resumen_alhassane.append((idx, info['nombre_original'], equipo_info, info['puntos']))
                if 'iglesias' in nombre_norm:
                    resumen_iglesias.append((idx, info['nombre_original'], equipo_info, info['puntos']))

            global JUGADORES_SIN_MATCH
            JUGADORES_SIN_MATCH = []
            df, loc, vis = procesar_partido(html_content, dict_ff, idx)

            if df is not None and not df.empty:
                fname = f"p{idx}_{normalizar_texto(loc)}-{normalizar_texto(vis)}.csv"
                df.to_csv(os.path.join(j_csv_dir, fname), index=False, encoding='utf-8-sig')
                print("     ✅ CSV generado.")

            if JUGADORES_SIN_MATCH:
                for j in JUGADORES_SIN_MATCH:
                    jugadores_sin_match_jornada.append(j)

        # print(f"\n===== RESUMEN GUEYE / ALHASSANE / IGLESIAS JORNADA {num_j} =====")
        # if resumen_gueye:
        #     for p_idx, nombre, equipo, pts in resumen_gueye:
        #         print(f"Gueye en P{p_idx} ({equipo}): '{nombre}' -> {pts} puntos")
        # else:
        #     print("No se ha encontrado a Gueye en esta jornada.")

        # if resumen_alhassane:
        #     for p_idx, nombre, equipo, pts in resumen_alhassane:
        #         print(f"Alhassane en P{p_idx} ({equipo}): '{nombre}' -> {pts} puntos")
        # else:
        #     print("No se ha encontrado a Alhassane en esta jornada.")

        # if resumen_iglesias:
        #     for p_idx, nombre, equipo, pts in resumen_iglesias:
        #         print(f"Iglesias en P{p_idx} ({equipo}): '{nombre}' -> {pts} puntos")
        # else:
        #     print("No se ha encontrado ningún Iglesias en esta jornada.")

if __name__ == "__main__":
    ejecutar_rango(inicio=1, fin=1)
