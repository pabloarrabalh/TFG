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
    'TiroF_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct',
    'Amarillas', 'Rojas', 'Goles_en_contra', 'puntosFantasy',
    'Tkl_challenge', 'Att_challenge', 'Tkl_pct_challenge', 'Lost_challenge',
    'Blocks_total', 'Blocks_sh', 'Blocks_pass', 'Clearances',
    'TakeOn_att', 'TakeOn_succ', 'TakeOn_tkld',
    'Carries_total', 'Carries_TotDist', 'Carries_PrgDist', 'Carries_PrgC',
    'Aerial_won', 'Aerial_lost', 'Aerial_won_pct'
]

# lista global para ver jugadores sin match (por ejemplo en P1 y P2)
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
    """
    Normalización robusta para comparar claves de FBRef y Fantasy:
    - minúsculas, sin tildes
    - puntos eliminados
    - espacios compactados
    """
    s = normalizar_texto(s)
    s = s.replace('.', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "rayo": "rayo",
    "villarreal cf": "villarreal",
    "real oviedo": "oviedo",
}

def normalizar_equipo(nombre):
    base = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(base, base)

def limpiar_valor(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return 0.0

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

# ============ SCRAPPING DE puntos.html Y SEPARACIÓN POR PARTIDOS ============

def extraer_puntos_fantasy_jornada(jornada):
    """
    Lee main/html/j{jornada}/puntos.html y devuelve:
      { 'girona-rayo': {...}, 'valencia-las palmas': {...}, ... }
    Cada dict interno: { clave_normalizada: {nombre_original, puntos} }.
    """
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
        clave_partido = f"{normalizar_equipo(n_l)}-{normalizar_equipo(n_v)}"

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

                span_puntos = fila.select_one("span.laliga-fantasy")
                puntos = 0
                if span_puntos:
                    txt = span_puntos.get_text(strip=True)
                    puntos = int(txt) if txt.lstrip("-").isdigit() else 0

                # clave normalizada para el match
                clave_norm = normalizar_clave_match(nombre_real)

                # si hay duplicados de clave (por escrituras distintas), nos quedamos con el valor
                # de mayor módulo para no machacar puntuaciones altas con 0 o -1
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

        res[clave_partido] = puntos_map

    return res

# ====================== AUXILIAR: OBTENER NOMBRES DESDE FBREF ======================

def obtener_nombres_partido_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"
    return n_l, n_v

# ================================ PROCESAR PARTIDO FBREF ================================

def procesar_partido(html_content, puntos_fantasy_dict, idx_partido):
    soup = BeautifulSoup(html_content, 'lxml')
    scores = soup.find_all('div', class_='score')
    g_l, g_v = (int(scores[0].get_text()), int(scores[1].get_text())) if len(scores) >= 2 else (0, 0)
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"

    n_l_norm = normalizar_equipo(n_l)
    n_v_norm = normalizar_equipo(n_v)

    # puntos_fantasy_dict YA viene con claves normalizadas (normalizar_clave_match)
    puntos_fantasy_match = puntos_fantasy_dict

    # Debug solo para P2
    es_debug = (idx_partido == 2)

    if es_debug:
        print("######## DEBUG PARTIDO P2 ########")
        print(f"Título FBRef: '{title}'")
        print(f"Equipos detectados: local='{n_l}' visitante='{n_v}'")
        print("--------- MAPA FANTASY DEL PARTIDO ---------")
        for k, v in puntos_fantasy_match.items():
            print(f"  {k} -> ({v['nombre_original']}, {v['puntos']})")
        print("--------------------------------------------")

    lineup_divs = soup.find_all('div', class_='lineup')
    titulares_nombres = []
    if lineup_divs:
        for div in lineup_divs:
            titulares_partido = [a.get_text().strip() for a in div.find_all('a')][:11]
            titulares_nombres.extend(titulares_partido)

    equipo_local_nombres = [a.get_text().strip() for a in lineup_divs[0].find_all('a')] if lineup_divs else []

    db = {}
    tipos = ['summary', 'passing', 'defense', 'possession', 'misc', 'keepers']

    for tipo in tipos:
        html_t = soup.find_all('table', id=re.compile(f"stats_.*_{tipo}"))
        for table_obj in html_t:
            df_raw = pd.read_html(StringIO(str(table_obj)))[0]
            df_raw.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_raw.columns.get_level_values(-1)
            ]

            for _, row in df_raw.iterrows():
                p_fb = re.sub(r'\s\(.*\)', '', str(row['Player'])).strip()

                if (
                    p_fb in ['nan', 'Player', 'Total', 'Players'] or
                    re.match(r'^\d+\s+Players$', p_fb)
                ):
                    continue

                fb_norm = normalizar_texto(p_fb)
                partes = fb_norm.split()
                fb_short = partes[-1] if partes else fb_norm

                # Alias manuales
                ALIAS_JUGADORES = {
                    'isaac palazon camacho': 'isi',
                    'viktor tsyhankov': 'tsygankov',
                    'jorge de frutos': 'de frutos',
                    'luiz lucio reis junior': 'luiz junior',
                    'rahim bonkano': 'alhassane',
                }
                if fb_norm in ALIAS_JUGADORES:
                    fb_norm = ALIAS_JUGADORES[fb_norm]
                    partes = fb_norm.split()
                    fb_short = partes[-1]

                # --- Construir candidatos en crudo ---
                candidatos = set()
                if fb_norm:
                    candidatos.add(fb_norm)
                if fb_short:
                    candidatos.add(fb_short)
                # penúltimo + último
                if len(partes) >= 2:
                    candidatos.add(" ".join(partes[-2:]))
                # inicial + apellido
                if len(partes) >= 2:
                    inicial = partes[0][0]
                    candidatos.add(f"{inicial} {fb_short}")
                    candidatos.add(f"{inicial}. {fb_short}")
                # quitar primer nombre si hay 3+
                if len(partes) >= 3:
                    candidatos.add(" ".join(partes[1:]))

                # Normalizar candidatos para compararlos: misma función que en Fantasy
                candidatos_normm = {normalizar_clave_match(c) for c in candidatos if c}

                n_final, pts_f = p_fb, 0
                mejor_clave = None

                # 1) match exacto con claves normalizadas
                for cand_nm in candidatos_normm:
                    if cand_nm in puntos_fantasy_match:
                        info = puntos_fantasy_match[cand_nm]
                        n_final, pts_f = info['nombre_original'], info['puntos']
                        mejor_clave = cand_nm
                        break

                # 2) fallback prefijo/sufijo
                if mejor_clave is None:
                    for ff_nm, info in puntos_fantasy_match.items():
                        for cand_nm in candidatos_normm:
                            if cand_nm and (cand_nm.startswith(ff_nm) or ff_nm.startswith(cand_nm)):
                                n_final, pts_f = info['nombre_original'], info['puntos']
                                mejor_clave = ff_nm
                                break
                        if mejor_clave is not None:
                            break

                if es_debug:
                    print(
                        f"DEBUG_MAPEO_JUGADOR: FBREF='{p_fb}' "
                        f"(norm='{fb_norm}', short='{fb_short}') "
                        f"candidatos={list(candidatos)} "
                        f"candidatos_normm={list(candidatos_normm)} "
                        f"-> FANTASY='{n_final}' puntos={pts_f} clave_match='{mejor_clave}'"
                    )

                # Crear entrada si no existe
                if n_final not in db:
                    es_local = p_fb in equipo_local_nombres
                    db[n_final] = {c: 0 for c in COLUMNAS_MODELO}
                    db[n_final].update({
                        'player': n_final,
                        'Equipo_propio': n_l if es_local else n_v,
                        'Equipo_rival': n_v if es_local else n_l,
                        'Titular': 1 if p_fb in titulares_nombres else 0,
                        'Goles_en_contra': g_v if es_local else g_l
                    })

                    pos_raw = str(row.get('Pos', 'MC')).split(',')[0].strip().upper()
                    if pos_raw in ['GK']:
                        pos_val = 'PT'
                    elif pos_raw in ['DF', 'RB', 'LB', 'CB']:
                        pos_val = 'DF'
                    elif pos_raw in ['FW', 'RW', 'LW']:
                        pos_val = 'DT'
                    else:
                        pos_val = 'MC'
                    db[n_final]['posicion'] = pos_val

                # Asignar puntos Fantasy
                if mejor_clave is not None:
                    db[n_final]['puntosFantasy'] = pts_f

                # Guardar sin match (solo los que realmente no encuentran clave)
                if mejor_clave is None and idx_partido in (1, 2):
                    JUGADORES_SIN_MATCH.append({
                        "partido_idx": idx_partido,
                        "equipo_local": n_l,
                        "equipo_visitante": n_v,
                        "nombre_fbref": p_fb,
                        "fb_norm": fb_norm,
                        "fb_short": fb_short
                    })

                # Estadísticas específicas
                if tipo == 'keepers' and 'GA' in row:
                    db[n_final]['Goles_en_contra'] = limpiar_valor(row['GA'])

                if 'Cmp%' in row:
                    val_c = limpiar_valor(row['Cmp%'])
                    if tipo == 'passing' or db[n_final]['Pases_Completados_Pct'] == 0:
                        db[n_final]['Pases_Completados_Pct'] = val_c

                # Mapeos desde todas las tablas (incluida misc)
                mappings = [
                    ('Min', 'Min_partido'),
                    ('Gls', 'Gol_partido'),
                    ('Ast', 'Asist_partido'),
                    ('xG', 'xG_partido'),
                    ('xAG', 'xA_partido'),
                    ('Sh', 'TiroF_partido'),
                    ('SoT', 'TiroPuerta_partido'),
                    ('Att', 'Pases_Totales'),
                    ('CrdY', 'Amarillas'),
                    ('CrdR', 'Rojas'),
                    ('Tkl', 'Tkl_challenge'),
                    ('Blocks', 'Blocks_total'),
                    ('Clr', 'Clearances'),
                    ('Succ', 'TakeOn_succ'),
                    ('Won', 'Aerial_won'),
                    ('Lost', 'Aerial_lost'),
                    ('Won%', 'Aerial_won_pct'),
                    ('Carries', 'Carries_total'),
                    ('TotDist', 'Carries_TotDist'),
                    ('PrgDist', 'Carries_PrgDist'),
                    ('PrgC', 'Carries_PrgC')
                ]
                for fin, fout in mappings:
                    if fin in row:
                        val = limpiar_valor(row[fin])
                        if val > float(db[n_final][fout]):
                            db[n_final][fout] = val

    df_final = pd.DataFrame.from_dict(db, orient='index')
    if not df_final.empty:
        df_final.loc[~df_final['posicion'].isin(['PT', 'DF']), 'Goles_en_contra'] = 0
        df_final.fillna(0, inplace=True)

        # --- ROJA POR DOBLE AMARILLA ---
        mask_doble_amarilla = df_final['Amarillas'] >= 2
        df_final.loc[mask_doble_amarilla, 'Rojas'] = 1.0

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

        for idx in range(1, 10 + 1):
            path_html = os.path.join(j_html_dir, f"p{idx}.html")
            html_content = ""

            if os.path.exists(path_html):
                print(f"     📂 [P{idx}] Usando local: {path_html}")
                with open(path_html, "r", encoding="utf-8") as f:
                    html_content = f.read()
            else:
                if num_j in calendario and len(calendario[num_j]) >= idx:
                    url = calendario[num_j][idx-1]
                    print(f"     🌐 [P{idx}] Descargando de FBRef...")
                    time.sleep(random.uniform(20, 35))
                    try:
                        resp = scraper.get(url, headers=get_headers())
                        if "bot" in resp.text.lower() or "captcha" in resp.text.lower():
                            print(f"     🛑 BLOQUEO en P{idx}. Descárgalo a mano.")
                            continue
                        html_content = resp.text
                        with open(path_html, "w", encoding="utf-8") as f:
                            f.write(html_content)
                    except:
                        continue
                else:
                    continue

            n_l, n_v = obtener_nombres_partido_fbref(html_content)
            clave_ff = f"{normalizar_equipo(n_l)}-{normalizar_equipo(n_v)}"
            dict_ff = puntos_por_partido.get(clave_ff, {})

            df, loc, vis = procesar_partido(html_content, dict_ff, idx)
            if df is not None and not df.empty:
                fname = f"p{idx}_{normalizar_texto(loc)}-{normalizar_texto(vis)}.csv"
                df.to_csv(os.path.join(j_csv_dir, fname), index=False, encoding='utf-8-sig')
                print(f"     ✅ CSV generado.")

    # Mostrar jugadores sin match de P1 y P2
    if JUGADORES_SIN_MATCH:
        print("\n===== JUGADORES SIN MATCH (P1 y P2) =====")
        for j in JUGADORES_SIN_MATCH:
            print(
                f"[P{j['partido_idx']}] {j['equipo_local']} vs {j['equipo_visitante']} "
                f"-> FBREF='{j['nombre_fbref']}' (norm='{j['fb_norm']}', short='{j['fb_short']}')"
            )

if __name__ == "__main__":
    ejecutar_rango(inicio=1, fin=1)
