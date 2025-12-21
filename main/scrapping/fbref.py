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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
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
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# Alias mínimos imprescindibles para match correcto
ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "villarreal cf": "villarreal",
    "real oviedo": "oviedo",
    "celta vigo": "celta",
    "alaves": "alavés",
    "athletic club": "athletic",
    "elche cf": "elche",
    "sevilla fc": "sevilla",
    "real betis": "betis",
    # Alias mínimos para normalización estricta
    "atlético": "atlético madrid",
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
        print(f"     📂 Cargando calendario desde archivo LOCAL")
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
        print(f"[LOG puntos.html] Partido: '{n_l}' vs '{n_v}' | n_l_norm='{n_l_norm}' n_v_norm='{n_v_norm}' | clave_partido='{clave_partido}'")

        puntos_map = {}

        tablas = seccion.select("table.tablestats")
        for tabla in tablas:
            filas = tabla.select("tbody tr.plegado")
            for fila in filas:
                td_name = fila.find("td", class_="name")
                if not td_name:
                    continue

                nombre_real = td_name.get_text(" ", strip=True)
                nombre_real = nombre_real.replace("+", "").replace("-", "").strip()
                nombre_real = re.sub(r"\s\d+'?$", "", nombre_real).strip()

                # --- CORRECCIÓN GUEYE Y ALHASSANE ---
                puntos = 0
                # Si el jugador es Gueye, busca el span con clase 'futmondo-mixto' (15 puntos)
                if 'gueye' in normalizar_texto(nombre_real):
                    span_gueye = fila.select_one("span.futmondo-mixto")
                    if span_gueye:
                        txt = span_gueye.get_text(strip=True)
                        try:
                            puntos = int(float(txt))
                        except:
                            puntos = 0
                # Si el jugador es Alhassane, busca el nombre exacto y usa laliga-fantasy (0 puntos)
                elif 'alhassane' in normalizar_texto(nombre_real):
                    span_alhassane = fila.select_one("span.laliga-fantasy")
                    if span_alhassane:
                        txt = span_alhassane.get_text(strip=True)
                        try:
                            puntos = int(float(txt))
                        except:
                            puntos = 0
                else:
                    span_puntos = fila.select_one("span.laliga-fantasy")
                    if span_puntos:
                        txt = span_puntos.get_text(strip=True)
                        puntos = int(txt) if txt.lstrip("-").isdigit() else 0

                clave_norm = normalizar_clave_match(nombre_real)

                if clave_norm in puntos_map:
                    if abs(puntos) > abs(puntos_map[clave_norm]["puntos"]):
                        puntos_map[clave_norm] = {
                            "nombre_original": nombre_real,
                            "puntos": puntos
                        }
                else:
                    puntos_map[clave_norm] = {
                        "nombre_original": nombre_real,
                        "puntos": puntos
                    }

        print(f"[LOG puntos.html]   -> jugadores: {[k for k in puntos_map.keys()]}")
        res[clave_partido] = puntos_map

    print(f"[LOG puntos.html] Claves partidos extraídos: {list(res.keys())}")
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
    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"

    puntos_fantasy_match = puntos_fantasy_dict
    es_debug = False  # Desactivar logs detallados

    lineup_divs = soup.find_all('div', class_='lineup')
    titulares_nombres = []
    if lineup_divs:
        for div in lineup_divs:
            titulares_partido = [a.get_text().strip() for a in div.find_all('a')][:11]
            titulares_nombres.extend(titulares_partido)

    equipo_local_nombres = [a.get_text().strip() for a in lineup_divs[0].find_all('a')] if lineup_divs else []

    # Leer todas las tablas una vez, con la misma clave normalizada (sin tildes, minúsculas)
    tablas_por_tipo = {}
    html_luiz_junior = None
    for tipo in ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']:
        dic = {}
        if tipo == 'keepers':
            table_objs = soup.find_all('table', id=re.compile(r'^keeper_stats_.*'))
        else:
            table_objs = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))
        # print(f"[LOG] Tablas encontradas para tipo '{tipo}': {len(table_objs)}")
        for table_obj in table_objs:
            # Solo para porteros, buscamos la fila de Luiz Junior y guardamos el HTML bruto
            if tipo == 'keepers':
                tbody = table_obj.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        td_player = tr.find('td', {'data-stat': 'player'})
                        if td_player:
                            nombre_portero = td_player.get_text()
                            norm_portero = normalizar_texto(nombre_portero)
                            # print(f"[LOG] Fila portero detectada: '{nombre_portero}' (normalizado: '{norm_portero}')")
                            # Captura HTML de Luiz Junior por coincidencia flexible
                            if 'luiz' in norm_portero and 'junior' in norm_portero:
                                html_luiz_junior = str(tr)
                                # print(f"[LOG] HTML bruto de Luiz Junior capturado.")
            try:
                df_raw = pd.read_html(StringIO(str(table_obj)))[0]
            except Exception as e:
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
                clave_norm = normalizar_texto(nombre_raw)
                dic[clave_norm] = row
        tablas_por_tipo[tipo] = dic

    db = {}

    # Recorremos jugadores según summary
    for clave_norm, row_sum in tablas_por_tipo.get('summary', {}).items():
        p_fb = str(row_sum.get('Player', '')).strip()  # nombre original tal cual
        fb_norm = clave_norm
        partes = fb_norm.split()
        fb_short = partes[-1] if partes else fb_norm

        ALIAS_JUGADORES = {
            'isaac palazon camacho': 'isi',
            'viktor tsyhankov': 'tsygankov',
            'luiz lucio reis junior': 'luiz junior',
            'luiz reis junior': 'luiz junior',
            'luiz junior': 'luiz junior',
            'paulo gazzaniga': 'gazzaniga',
            'gazzaniga': 'gazzaniga',
            'rahim bonkano': 'alhassane',
        }
        # Aplica alias si el nombre normalizado coincide exactamente o parcialmente
        for alias_key, alias_val in ALIAS_JUGADORES.items():
            if fb_norm == alias_key or fb_norm.endswith(alias_key) or fb_norm.startswith(alias_key):
                fb_norm = alias_val
                partes = fb_norm.split()
                fb_short = partes[-1]
                break


        # --- MATCH FANTASY ---
        candidatos = set()
        if fb_norm:
            candidatos.add(fb_norm)
        if fb_short:
            candidatos.add(fb_short)
        if len(partes) >= 2:
            candidatos.add(" ".join(partes[-2:]))
            inicial = partes[0][0]
            candidatos.add(f"{inicial} {fb_short}")
            candidatos.add(f"{inicial}. {fb_short}")
            # Always add initial plus surname (e.g., 'f de jong')
            candidatos.add(f"{inicial} {partes[-2]} {partes[-1]}")
            candidatos.add(f"{inicial}. {partes[-2]} {partes[-1]}")
        if len(partes) >= 3:
            candidatos.add(" ".join(partes[1:]))

        # Lógica especial para apellidos que empiezan por 'de' (ej: 'de frutos', 'de jong')
        if len(partes) >= 2 and partes[-2] == 'de':
            candidatos.add(partes[-2] + ' ' + partes[-1])  # 'de frutos', 'de jong'
            candidatos.add(partes[-1])  # 'frutos', 'jong'        

        candidatos_normm = {normalizar_clave_match(c) for c in candidatos if c}

        n_final, pts_f = p_fb, 0
        mejor_clave = None

        for cand_nm in candidatos_normm:
            if cand_nm in puntos_fantasy_match:
                info = puntos_fantasy_match[cand_nm]
                n_final, pts_f = info['nombre_original'], info['puntos']
                mejor_clave = cand_nm
                break

        if mejor_clave is None:
            for ff_nm, info in puntos_fantasy_match.items():
                for cand_nm in candidatos_normm:
                    if cand_nm and (cand_nm.startswith(ff_nm) or ff_nm.startswith(cand_nm)):
                        n_final, pts_f = info['nombre_original'], info['puntos']
                        mejor_clave = ff_nm
                        break
                if mejor_clave is not None:
                    break

        # if es_debug:
        #     print(
        #         f"DEBUG MAP: FBREF='{p_fb}' norm='{fb_norm}' short='{fb_short}' "
        #         f"-> FANTASY='{n_final}' pts={pts_f} clave='{mejor_clave}'"
        #     )

        # Crear jugador en db si no existe
        if n_final not in db:
            es_local = p_fb in equipo_local_nombres
            db[n_final] = {c: 0 for c in COLUMNAS_MODELO}
            db[n_final].update({
                'player': n_final,
                'Equipo_propio': n_l if es_local else n_v,
                'Equipo_rival': n_v if es_local else n_l,
                'Titular': 1 if p_fb in titulares_nombres else 0,
                'Goles_en_contra': 0.0,
                'Porcentaje_paradas': 0.0
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
            db[n_final]['posicion'] = pos_val

        # SUMMARY
        db[n_final]['Min_partido'] = limpiar_int(row_sum.get('Min', 0))
        db[n_final]['Gol_partido'] = limpiar_float(row_sum.get('Gls', 0))
        db[n_final]['Asist_partido'] = limpiar_float(row_sum.get('Ast', 0))
        db[n_final]['xG_partido'] = limpiar_float(row_sum.get('xG', 0))
        db[n_final]['xA_partido'] = limpiar_float(row_sum.get('xAG', 0))

        sh_total = limpiar_float(row_sum.get('Sh', 0))
        sot = limpiar_float(row_sum.get('SoT', 0))
        tiros_fallados = max(sh_total - sot, 0)

        db[n_final]['TiroFallado_partido'] = tiros_fallados
        db[n_final]['TiroPuerta_partido'] = sot

        # PASSING
        row_pas = tablas_por_tipo.get('passing', {}).get(fb_norm)
        cmp_pct = 0.0
        if row_pas is not None:
            db[n_final]['Pases_Totales'] = limpiar_int(row_pas.get('Att', 0))
            if 'Cmp%' in row_pas:
                cmp_pct = limpiar_float(row_pas['Cmp%'])
        if cmp_pct == 0.0 and 'Cmp%' in row_sum:
            cmp_pct = limpiar_float(row_sum['Cmp%'])
        db[n_final]['Pases_Completados_Pct'] = cmp_pct

        # DEFENSE
        row_def = tablas_por_tipo.get('defense', {}).get(fb_norm)
        if row_def is not None:
            db[n_final]['Entradas'] = limpiar_float(row_def.get('Tkl', 0))
            db[n_final]['Duelos'] = limpiar_float(row_def.get('Att', 0))
            db[n_final]['DuelosGanados'] = limpiar_float(row_def.get('Tkl%', 0))
            db[n_final]['DuelosPerdidos'] = limpiar_float(row_def.get('Lost', 0))
            db[n_final]['Bloqueos'] = limpiar_float(row_def.get('Blocks', 0))
            db[n_final]['BloqueoTiros'] = limpiar_float(row_def.get('Sh', 0))
            db[n_final]['BloqueoPase'] = limpiar_float(row_def.get('Pass', 0))
            db[n_final]['Despejes'] = limpiar_float(row_def.get('Clr', 0))

        # POSSESSION
        row_poss = tablas_por_tipo.get('possession', {}).get(fb_norm)
        if row_poss is not None:
            db[n_final]['Regates'] = limpiar_float(row_poss.get('Att', 0))
            db[n_final]['RegatesCompletados'] = limpiar_float(row_poss.get('Succ', 0))
            db[n_final]['RegatesFallidos'] = limpiar_float(row_poss.get('Tkld', 0))
            db[n_final]['Conducciones'] = limpiar_float(row_poss.get('Carries', 0))
            db[n_final]['DistanciaConduccion'] = limpiar_float(row_poss.get('TotDist', 0))
            db[n_final]['MetrosAvanzadosConduccion'] = limpiar_float(row_poss.get('PrgDist', 0))
            db[n_final]['ConduccionesProgresivas'] = limpiar_float(row_poss.get('PrgC', 0))

        # MISC
        row_misc = tablas_por_tipo.get('misc', {}).get(fb_norm)
        if row_misc is not None:
            db[n_final]['Amarillas'] = limpiar_float(row_misc.get('CrdY', 0))
            db[n_final]['Rojas'] = limpiar_float(row_misc.get('CrdR', 0))
            db[n_final]['DuelosAereosGanados'] = limpiar_float(row_misc.get('Won', 0))
            db[n_final]['DuelosAereosPerdidos'] = limpiar_float(row_misc.get('Lost', 0))
            db[n_final]['DuelosAereosGanadosPct'] = limpiar_float(row_misc.get('Won%', 0))

        # PORTEROS -> GA, Save%, PSxG solo para posicion PT, usando keeper_stats_*
        if db[n_final]['posicion'] == 'PT':
            # Coincidencia flexible para porteros: busca por inclusión/similitud
            keepers_dict = tablas_por_tipo.get('keepers', {})
            row_keep = None
            for k_norm, k_row in keepers_dict.items():
                # Si el nombre del jugador está incluido en la clave del portero, o viceversa
                if fb_norm in k_norm or k_norm in fb_norm:
                    row_keep = k_row
                    break
                # También compara por apellidos si hay más de una palabra
                partes_fb = fb_norm.split()
                partes_k = k_norm.split()
                if len(partes_fb) > 1 and len(partes_k) > 1:
                    if partes_fb[-1] == partes_k[-1]:
                        row_keep = k_row
                        break
            if row_keep is not None:
                ga_val = limpiar_float(row_keep.get('GA', 0))
                sv_val = 0.0
                for col_sv in ['Save%', 'Sv%', 'SV%']:
                    if col_sv in row_keep:
                        sv_val = limpiar_float(row_keep[col_sv])
                        break
                psxg_val = limpiar_float(row_keep.get('PSxG', 0)) if 'PSxG' in row_keep else 0.0
                db[n_final]['Goles_en_contra'] = ga_val
                db[n_final]['Porcentaje_paradas'] = sv_val
                db[n_final]['PSxG'] = psxg_val
            else:
                db[n_final]['Goles_en_contra'] = 0.0
                db[n_final]['Porcentaje_paradas'] = 0.0
                db[n_final]['PSxG'] = 0.0
        else:
            db[n_final]['Goles_en_contra'] = 0.0
            db[n_final]['Porcentaje_paradas'] = 0.0
            db[n_final]['PSxG'] = 0.0

        if mejor_clave is not None:
            db[n_final]['puntosFantasy'] = pts_f

        if mejor_clave is None and idx_partido in (1, 2):
            JUGADORES_SIN_MATCH.append({
                "partido_idx": idx_partido,
                "equipo_local": n_l,
                "equipo_visitante": n_v,
                "nombre_fbref": p_fb,
                "fb_norm": fb_norm,
                "fb_short": fb_short
            })

    df_final = pd.DataFrame.from_dict(db, orient='index')
    if not df_final.empty:
        # Goles en contra y % paradas solo para porteros
        mask_no_gk = df_final['posicion'] != 'PT'
        df_final.loc[mask_no_gk, 'Goles_en_contra'] = 0.0
        df_final.loc[mask_no_gk, 'Porcentaje_paradas'] = 0.0
        df_final.fillna(0, inplace=True)

        # ROJA POR DOBLE AMARILLA
        mask_doble_amarilla = df_final['Amarillas'] >= 2
        df_final.loc[mask_doble_amarilla, 'Rojas'] = 1.0

    # Eliminado log de HTML bruto de Luiz Junior

    return df_final, n_l, n_v

# ================================== MAIN ==================================

def ejecutar_rango(inicio, fin):
    print("🚀 INICIANDO SISTEMA...")
    calendario = obtener_calendario_local_o_remoto()

    for j_val in range(inicio, fin + 1):
        num_j = str(j_val)
        print(f"\n--- JORNADA {num_j} ---")

        puntos_por_partido = extraer_puntos_fantasy_jornada(num_j)

        j_html_dir = os.path.join(BASE_FOLDER_HTML, f"j{num_j}")
        j_csv_dir = os.path.join(BASE_FOLDER_CSV, f"jornada_{num_j}")
        os.makedirs(j_html_dir, exist_ok=True)
        os.makedirs(j_csv_dir, exist_ok=True)

        # Limpiar lista de sin match para la jornada
        jugadores_sin_match_jornada = []

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
            clave_ff = f"{n_l_norm}-{n_v_norm}"
            print(f"     [LOG] P{idx}: n_l='{n_l}' n_v='{n_v}' | n_l_norm='{n_l_norm}' n_v_norm='{n_v_norm}' | clave_ff='{clave_ff}'")
            dict_ff = puntos_por_partido.get(clave_ff, {})

            # Limpiar JUGADORES_SIN_MATCH antes de cada partido
            global JUGADORES_SIN_MATCH
            JUGADORES_SIN_MATCH = []
            df, loc, vis = procesar_partido(html_content, dict_ff, idx)
            if df is not None and not df.empty:
                fname = f"p{idx}_{normalizar_texto(loc)}-{normalizar_texto(vis)}.csv"
                df.to_csv(os.path.join(j_csv_dir, fname), index=False, encoding='utf-8-sig')
                print(f"     ✅ CSV generado.")

                # Mostrar jugadores con 0 puntosFantasy
                jugadores_cero = df[df['puntosFantasy'] == 0]['player'].tolist()
                if jugadores_cero:
                    print(f"     Jugadores con 0 puntos en P{idx} ({loc} vs {vis}):")
                    for nombre in jugadores_cero:
                        print(f"        - {nombre}")
                else:
                    print(f"     Todos los jugadores tienen puntos en P{idx} ({loc} vs {vis})")

            # Añadir sin match de este partido a la lista de la jornada
            if JUGADORES_SIN_MATCH:
                for j in JUGADORES_SIN_MATCH:
                    jugadores_sin_match_jornada.append({
                        "partido_idx": j["partido_idx"],
                        "equipo_local": j["equipo_local"],
                        "equipo_visitante": j["equipo_visitante"],
                        "nombre_fbref": j["nombre_fbref"],
                        "fb_norm": j["fb_norm"],
                        "fb_short": j["fb_short"]
                    })

        # Log de jugadores sin match tras todos los partidos de la jornada
        if jugadores_sin_match_jornada:
            print(f"\n===== JUGADORES SIN MATCH EN JORNADA {num_j} =====")
            for j in jugadores_sin_match_jornada:
                print(
                    f"[P{j['partido_idx']}] {j['equipo_local']} vs {j['equipo_visitante']} "
                    f"-> FBREF='{j['nombre_fbref']}' (norm='{j['fb_norm']}', short='{j['fb_short']}')"
                )
        else:
            print(f"\nTodos los jugadores han hecho match en la jornada {num_j}.")

    

if __name__ == "__main__":
    ejecutar_rango(inicio=1, fin=1)
