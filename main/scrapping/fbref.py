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

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'windows','desktop': True})

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def limpiar_valor(val):
    if isinstance(val, pd.Series): val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-": return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try: return float(s_val)
    except: return 0.0

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
    if not tabla: return {}
    
    for row in tabla.find_all('tr'):
        wk = row.find('th', {'data-stat': 'gameweek'})
        match_report = row.find('td', {'data-stat': 'match_report'})
        if wk and match_report and match_report.find('a'):
            j_num = wk.get_text().strip()
            href = match_report.find('a')['href']
            link = "https://fbref.com" + href if not href.startswith('http') else href
            calendario.setdefault(j_num, []).append(link)
    return calendario

def extraer_puntos_fantasy(jornada):
    url = f"https://www.futbolfantasy.com/laliga/puntos/2026/{jornada}/laliga-fantasy"
    try:
        resp = scraper.get(url, headers=get_headers())
        soup = BeautifulSoup(resp.text, 'lxml')
        puntos_map = {} 
        filas = soup.find_all('tr', class_=re.compile(r'plegado'))
        for fila in filas:
            td_name = fila.find('td', class_='name')
            if not td_name: continue
            nombre_real = re.sub(r'\s\d+\'?$', '', td_name.get_text(" ", strip=True).replace('+', '').replace('-', '').strip())
            span_puntos = fila.select_one('span.laliga-fantasy')
            puntos = int(span_puntos.get_text(strip=True)) if span_puntos and span_puntos.get_text(strip=True) not in ['-', ''] else 0
            puntos_map[normalizar_texto(nombre_real)] = {'nombre_original': nombre_real, 'puntos': puntos}
        return puntos_map
    except: return {}

def procesar_partido(html_content, puntos_fantasy_dict):
    soup = BeautifulSoup(html_content, 'lxml')
    scores = soup.find_all('div', class_='score')
    g_l, g_v = (int(scores[0].get_text()), int(scores[1].get_text())) if len(scores) >= 2 else (0,0)
    title = soup.find('title').get_text() if soup.find('title') else "Match"
    try:
        n_l, n_v = title.split(' vs. ')[0], title.split(' vs. ')[1].split(' Match')[0]
    except:
        n_l, n_v = "Local", "Visitante"

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
            df_raw.columns = [str(col).split(',')[-1].strip(" ()'").replace(' ', '') for col in df_raw.columns.get_level_values(-1)]
            
            for _, row in df_raw.iterrows():
                p_fb = re.sub(r'\s\(.*\)', '', str(row['Player'])).strip()
                if p_fb in ['nan', 'Player', 'Total', 'Players']: continue

                fb_norm = normalizar_texto(p_fb)
                n_final, pts_f = p_fb, 0
                for ff_norm, info in puntos_fantasy_dict.items():
                    if ff_norm in fb_norm or fb_norm in ff_norm:
                        n_final, pts_f = info['nombre_original'], info['puntos']; break

                if n_final not in db:
                    es_local = p_fb in equipo_local_nombres
                    db[n_final] = {c: 0 for c in COLUMNAS_MODELO}
                    db[n_final].update({
                        'player': n_final, 'puntosFantasy': pts_f,
                        'Equipo_propio': n_l if es_local else n_v, 'Equipo_rival': n_v if es_local else n_l,
                        'Titular': 1 if p_fb in titulares_nombres else 0,
                        'Goles_en_contra': g_v if es_local else g_l
                    })
                    pos_raw = str(row.get('Pos', 'MC')).split(',')[0].strip().upper()
                    if pos_raw in ['GK']: pos_val = 'PT'
                    elif pos_raw in ['DF', 'RB', 'LB', 'CB']: pos_val = 'DF'
                    elif pos_raw in ['FW', 'RW', 'LW']: pos_val = 'DT'
                    else: pos_val = 'MC'
                    db[n_final]['posicion'] = pos_val

                if tipo == 'keepers' and 'GA' in row:
                    db[n_final]['Goles_en_contra'] = limpiar_valor(row['GA'])
                
                if 'Cmp%' in row:
                    val_c = limpiar_valor(row['Cmp%'])
                    if tipo == 'passing' or db[n_final]['Pases_Completados_Pct'] == 0:
                        db[n_final]['Pases_Completados_Pct'] = val_c

                mappings = [
                    ('Min','Min_partido'), ('Gls','Gol_partido'), ('Ast','Asist_partido'), 
                    ('xG','xG_partido'), ('xAG','xA_partido'), ('Att','Pases_Totales'),
                    ('CrdY','Amarillas'), ('CrdR','Rojas'), 
                    ('Tkl','Tkl_challenge'), ('Blocks','Blocks_total'), ('Clr','Clearances'), 
                    ('Succ','TakeOn_succ'), ('Won','Aerial_won'),
                    ('Carries','Carries_total'), ('TotDist','Carries_TotDist'), 
                    ('PrgDist','Carries_PrgDist'), ('PrgC','Carries_PrgC')
                ]
                for fin, fout in mappings:
                    if fin in row:
                        val = limpiar_valor(row[fin])
                        if val > float(db[n_final][fout]): db[n_final][fout] = val

    df_final = pd.DataFrame.from_dict(db, orient='index')
    if not df_final.empty:
        df_final.loc[~df_final['posicion'].isin(['PT', 'DF']), 'Goles_en_contra'] = 0
        df_final.fillna(0, inplace=True)
    return df_final, n_l, n_v

def ejecutar_rango(inicio, fin):
    print("🚀 INICIANDO SISTEMA...")
    calendario = obtener_calendario_local_o_remoto()

    for j_val in range(inicio, fin + 1):
        num_j = str(j_val)
        print(f"\n--- JORNADA {num_j} ---")
        dict_ff = extraer_puntos_fantasy(num_j)
        
        j_html_dir = os.path.join(BASE_FOLDER_HTML, f"j{num_j}")
        j_csv_dir = os.path.join(BASE_FOLDER_CSV, f"jornada_{num_j}")
        os.makedirs(j_html_dir, exist_ok=True)
        os.makedirs(j_csv_dir, exist_ok=True)

        # Ahora el bucle de partidos es fijo (1 a 10) para permitir carga local sin calendario
        for idx in range(1, 11):
            path_html = os.path.join(j_html_dir, f"p{idx}.html")
            html_content = ""

            if os.path.exists(path_html):
                print(f"     📂 [P{idx}] Usando local: {path_html}")
                with open(path_html, "r", encoding="utf-8") as f:
                    html_content = f.read()
            else:
                # Si no hay archivo local, intentamos usar el link del calendario
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
                        with open(path_html, "w", encoding="utf-8") as f: f.write(html_content)
                    except: continue
                else:
                    # Si no hay archivo local Y no hay calendario, saltamos
                    continue

            df, loc, vis = procesar_partido(html_content, dict_ff)
            if df is not None:
                fname = f"p{idx}_{normalizar_texto(loc)}-{normalizar_texto(vis)}.csv"
                df.to_csv(os.path.join(j_csv_dir, fname), index=False, encoding='utf-8-sig')
                print(f"     ✅ CSV generado.")

if __name__ == "__main__":
    ejecutar_rango(inicio=1, fin=2)