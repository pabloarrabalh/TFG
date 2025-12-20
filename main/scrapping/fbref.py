import cloudscraper
import pandas as pd
import os, re, time, random
import unicodedata
from io import StringIO
from bs4 import BeautifulSoup

# CONFIGURACIÓN
pd.set_option('display.max_columns', None)

COLUMNAS_MODELO = [
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular', 
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido', 'xA_partido', 
    'TiroF_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct', 
    'Amarillas', 'Rojas', 'Tackles_ganados', 'Intercepciones', 'Bloqueos', 
    'Saves', 'SoTA', 'Save_Pct', 'PSxG_partido', 'Goles_en_contra', 'puntosFantasy'
]

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Accept-Language": "es-ES,es;q=0.9"
}

TEMPORADA_FOLDER = "data/temporada_25_26"

def normalizar_texto(texto):
    """Elimina acentos, tildes y pone en minúsculas para comparar nombres."""
    if not texto: return ""
    texto = str(texto).lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')
    return texto

def extraer_puntos_fantasy(jornada):
    """Extrae los nombres y puntos de FutbolFantasy para toda la jornada."""
    url = f"https://www.futbolfantasy.com/laliga/puntos/2026/{jornada}/laliga-fantasy"
    print(f"--- SCRAPING PUNTOS FANTASY JORNADA {jornada} ---")
    try:
        resp = scraper.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, 'lxml')
        puntos_map = {} 

        filas = soup.find_all('tr', class_=re.compile(r'plegado'))
        for fila in filas:
            td_name = fila.find('td', class_='name')
            if not td_name: continue
            
            nombre_sucio = td_name.get_text(" ", strip=True)
            nombre_real = nombre_sucio.replace('+', '').replace('-', '').strip()
            nombre_real = re.sub(r'\s\d+\'?$', '', nombre_real).strip()
            
            span_puntos = fila.select_one('span.laliga-fantasy')
            puntos = 0
            if span_puntos:
                txt = span_puntos.get_text(strip=True)
                puntos = int(txt) if txt not in ['-', ''] else 0
            
            puntos_map[normalizar_texto(nombre_real)] = {
                'nombre_original': nombre_real, 
                'puntos': puntos
            }
        return puntos_map
    except Exception as e:
        print(f"❌ Error en FutbolFantasy: {e}")
        return {}

def obtener_calendario_jornadas(url_calendario):
    print(f">>> OBTENIENDO CALENDARIO DESDE: {url_calendario}")
    resp = scraper.get(url_calendario, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'lxml')
    calendario = {}
    tabla = soup.find('table', {'id': re.compile('sched')})
    if not tabla: return calendario
    for row in tabla.find_all('tr'):
        wk = row.find('th', {'data-stat': 'gameweek'})
        match_report = row.find('td', {'data-stat': 'match_report'})
        if wk and match_report and match_report.find('a'):
            num_jornada = wk.get_text().strip()
            link = "https://fbref.com" + match_report.find('a')['href']
            calendario.setdefault(num_jornada, []).append(link)
    return calendario

def extraer_desde_fbref(url, puntos_fantasy_dict):
    try:
        resp = scraper.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # 1. Extraer Marcador Real del Partido
        scores = soup.find_all('div', class_='score')
        gol_local = int(scores[0].get_text()) if len(scores) > 0 else 0
        gol_visit = int(scores[1].get_text()) if len(scores) > 1 else 0

        title_text = soup.find('title').get_text()
        match_info = title_text.split(' vs. ')
        n_l = match_info[0].strip()
        n_v = match_info[1].split(' Match')[0].strip()

        tablas_raw = pd.read_html(StringIO(resp.text))
        
        # Identificar equipo local para asignar goles correctamente
        lista_local_fbref = [re.sub(r'\s\(.*\)', '', str(p)).strip() for p in tablas_raw[3].iloc[:, 0]]
        suplentes_fbref = [a.get_text().strip() for div in soup.find_all('div', class_='lineup') 
                          for r in div.find_all('tr') if r.find('th') and 'Bench' in r.find('th').get_text() 
                          for a in r.find_all('a')]

        db = {}
        for t in tablas_raw:
            t.columns = t.columns.get_level_values(t.columns.nlevels - 1)
            if 'Player' not in t.columns or 'Min' not in t.columns: continue
            
            for _, row in t.iterrows():
                p_name_fbref = str(row['Player'])
                if p_name_fbref in ['nan', 'Player'] or "Players" in p_name_fbref: continue
                p_name_fbref = re.sub(r'\s\(.*\)', '', p_name_fbref).strip()
                
                try:
                    if int(row['Min']) <= 0: continue
                except: continue

                # BUSCAR NOMBRE FÚTBOL FANTASY
                nombre_final = p_name_fbref
                pts_f = 0
                fb_norm = normalizar_texto(p_name_fbref)
                for ff_norm, info in puntos_fantasy_dict.items():
                    if ff_norm in fb_norm or fb_norm in ff_norm:
                        nombre_final = info['nombre_original']
                        pts_f = info['puntos']
                        break

                if nombre_final not in db:
                    # Identificar si el jugador es local o visitante
                    es_local = p_name_fbref in lista_local_fbref
                    
                    db[nombre_final] = {c: 0 for c in COLUMNAS_MODELO}
                    db[nombre_final].update({
                        'player': nombre_final, 
                        'Titular': 0 if p_name_fbref in suplentes_fbref else 1,
                        'puntosFantasy': pts_f,
                        'Equipo_propio': n_l if es_local else n_v,
                        'Equipo_rival': n_v if es_local else n_l,
                        'Goles_en_contra': gol_visit if es_local else gol_local # Goles que encajó su equipo
                    })
                
                if 'Pos' in t.columns:
                    raw_pos = str(row['Pos']).split(',')[0].strip()
                    pos_map = {'GK': 'PT', 'DF': 'DF', 'MF': 'MC', 'FW': 'DT', 'FB': 'DF', 'CB': 'DF'}
                    db[nombre_final]['posicion'] = pos_map.get(raw_pos, 'MC')
                
                # Mapeo de estadísticas generales
                map_cols = [('Min','Min_partido'), ('Gls','Gol_partido'), ('Ast','Asist_partido'), 
                            ('xG','xG_partido'), ('xA','xA_partido'), ('Att','Pases_Totales'), 
                            ('Cmp%','Pases_Completados_Pct'), ('PSxG','PSxG_partido'), 
                            ('Saves','Saves'), ('SoTA','SoTA'), ('Save%','Save_Pct'),
                            ('TklW','Tackles_ganados'), ('Int','Intercepciones'), ('Blocks','Bloqueos'),
                            ('Sh', 'TiroF_partido'), ('SoT', 'TiroPuerta_partido'), ('CrdY', 'Amarillas'), ('CrdR', 'Rojas')]
                
                for fin, fout in map_cols:
                    if fin in t.columns:
                        try:
                            val = float(row[fin])
                            if val > float(db[nombre_final][fout]): db[nombre_final][fout] = val
                        except: continue

        df_final = pd.DataFrame.from_dict(db, orient='index')
        
        # 2. Ajuste Final por posición
        for idx, row in df_final.iterrows():
            # Solo defensas y porteros mantienen los goles en contra
            if row['posicion'] not in ['DF', 'PT']:
                df_final.at[idx, 'Goles_en_contra'] = 0
            # Solo porteros mantienen datos de paradas
            if row['posicion'] != 'PT':
                df_final.loc[idx, ['Saves', 'SoTA', 'Save_Pct', 'PSxG_partido']] = 0

        return df_final, n_l, n_v
    except Exception as e:
        print(f"❌ Error en partido {url}: {e}")
        return None, None, None

def ejecutar_scraper_rango(inicio, fin):
    url_base = "https://fbref.com/en/comps/12/schedule/La-Liga-Scores-and-Fixtures"
    calendario = obtener_calendario_jornadas(url_base)
    
    for j in range(inicio, fin + 1):
        num_j = str(j)
        if num_j not in calendario: continue
        
        dict_fantasy = extraer_puntos_fantasy(num_j)
            
        print(f"\n=== PROCESANDO JORNADA {num_j} ===")
        partidos = calendario[num_j]
        jornada_folder = os.path.join(TEMPORADA_FOLDER, f"jornada_{num_j}")
        if not os.path.exists(jornada_folder): os.makedirs(jornada_folder)
        
        for idx, url in enumerate(partidos, 1):
            if any(f.startswith(f"p{idx}_") for f in os.listdir(jornada_folder)): continue

            print(f"🔍 Descargando {num_j} - Partido {idx}/10...")
            df_partido, local, visitante = extraer_desde_fbref(url, dict_fantasy)
            
            if df_partido is not None:
                loc_f = re.sub(r'\W+', '', local.replace(' ', '_'))
                vis_f = re.sub(r'\W+', '', visitante.replace(' ', '_'))
                nombre_archivo = f"p{idx}_{loc_f}-{vis_f}.csv"
                path_save = os.path.join(jornada_folder, nombre_archivo)
                df_partido.to_csv(path_save, index=False, encoding='utf-8-sig')
                print(f"✅ Guardado: {nombre_archivo} con nombres de FútbolFantasy y goles sincronizados")
                time.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    ejecutar_scraper_rango(inicio=1, fin=2)