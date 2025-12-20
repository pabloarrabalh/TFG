import cloudscraper
import pandas as pd
import os, re, time, random
from io import StringIO
from bs4 import BeautifulSoup

# CONFIGURACIÓN
pd.set_option('display.max_columns', None)

COLUMNAS_MODELO = [
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular', 
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido', 'xA_partido', 
    'TiroF_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct', 
    'Amarillas', 'Rojas', 'Tackles_ganados', 'Intercepciones', 'Bloqueos', 
    'Saves', 'SoTA', 'Save_Pct', 'PSxG_partido', 'Goles_en_contra'
]

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Accept-Language": "es-ES,es;q=0.9"
}

TEMPORADA_FOLDER = "data/temporada_25_26"

def obtener_calendario_jornadas(url_calendario):
    """Escanea el calendario y devuelve un diccionario { 'X': [urls] }"""
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

def extraer_desde_fbref(url):
    """Extrae datos de un partido individual con lógica de GA para defensas"""
    try:
        resp = scraper.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, 'lxml')
        tablas_raw = pd.read_html(StringIO(resp.text))

        goles_en_contra_por_equipo = {}
        for t in tablas_raw:
            t.columns = t.columns.get_level_values(t.columns.nlevels - 1)
            if 'GA' in t.columns and 'Player' in t.columns:
                for _, row in t.iterrows():
                    if pd.notna(row['GA']) and str(row['Player']) != 'Player':
                        p_name = re.sub(r'\s\(.*\)', '', str(row['Player'])).strip()
                        goles_en_contra_por_equipo[p_name] = int(row['GA'])

        suplentes = [a.get_text().strip() for div in soup.find_all('div', class_='lineup') 
                     for r in div.find_all('tr') if r.find('th') and 'Bench' in r.find('th').get_text() 
                     for a in r.find_all('a')]

        db = {}
        for t in tablas_raw:
            t.columns = t.columns.get_level_values(t.columns.nlevels - 1)
            if 'Player' not in t.columns or 'Min' not in t.columns: continue
            for _, row in t.iterrows():
                p_name = str(row['Player'])
                if p_name in ['nan', 'Player'] or "Players" in p_name: continue
                p_name = re.sub(r'\s\(.*\)', '', p_name).strip()
                try:
                    if int(row['Min']) <= 0: continue
                except: continue

                if p_name not in db:
                    db[p_name] = {c: 0 for c in COLUMNAS_MODELO}
                    db[p_name].update({'player': p_name, 'Titular': 0 if p_name in suplentes else 1})
                
                if 'Pos' in t.columns:
                    raw_pos = str(row['Pos']).split(',')[0].strip()
                    pos_map = {'GK': 'PT', 'DF': 'DF', 'MF': 'MC', 'FW': 'DT', 'FB': 'DF', 'CB': 'DF', 'LB': 'DF', 'RB': 'DF'}
                    db[p_name]['posicion'] = pos_map.get(raw_pos, 'MC')
                
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
                            if val > float(db[p_name][fout]): db[p_name][fout] = val
                        except: continue

        df_final = pd.DataFrame.from_dict(db, orient='index')
        title_tag = soup.find('title').get_text()
        n_l, n_v = title_tag.split(' vs. ')[0], title_tag.split(' vs. ')[1].split(' Match')[0]
        df_final['Equipo_propio'], df_final['Equipo_rival'] = n_v, n_l
        if len(tablas_raw) > 3:
            lista_local = list(tablas_raw[3].iloc[:, 0]) 
            df_final.loc[df_final['player'].isin(lista_local), ['Equipo_propio', 'Equipo_rival']] = [n_l, n_v]
        
        # Sincronización GA
        ga_map = {}
        for p, ga in goles_en_contra_por_equipo.items():
            if p in df_final.index: ga_map[df_final.at[p, 'Equipo_propio']] = ga

        for idx, row in df_final.iterrows():
            df_final.at[idx, 'Goles_en_contra'] = ga_map.get(row['Equipo_propio'], 0) if row['posicion'] in ['DF', 'PT'] else 0
            if row['posicion'] != 'PT':
                df_final.loc[idx, ['Saves', 'SoTA', 'Save_Pct', 'PSxG_partido']] = 0

        return df_final
    except Exception as e:
        print(f"❌ Error en partido {url}: {e}")
        return None

def ejecutar_scraper_rango(inicio, fin):
    """Recorre las jornadas de a a b guardando con formato px_eq1_eq2.csv"""
    url_base = "https://fbref.com/en/comps/12/schedule/La-Liga-Scores-and-Fixtures"
    calendario = obtener_calendario_jornadas(url_base)
    
    for j in range(inicio, fin + 1):
        num_j = str(j)
        if num_j not in calendario: continue
            
        print(f"\n=== PROCESANDO JORNADA {num_j} ===")
        partidos = calendario[num_j]
        jornada_folder = os.path.join(TEMPORADA_FOLDER, f"jornada_{num_j}")
        if not os.path.exists(jornada_folder): os.makedirs(jornada_folder)
        
        for idx, url in enumerate(partidos, 1):
            # Obtener nombres de equipos desde la URL para el chequeo de archivo
            # Formato URL: .../Sevilla-Barcelona-October-5-2025-La-Liga
            slug = url.split('/')[-1]
            partes_slug = slug.split('-')
            eq1_slug = partes_slug[0].lower()
            eq2_slug = partes_slug[1].lower()
            
            nombre_archivo = f"p{idx}_{eq1_slug}_{eq2_slug}.csv"
            path_save = os.path.join(jornada_folder, nombre_archivo)
            
            # Verificación de existencia antes de llamar a fbref
            if os.path.exists(path_save):
                print(f"⏩ Saltando (ya existe): {nombre_archivo}")
                continue

            print(f"🔍 Scraping {num_j} - {idx}/10: {eq1_slug} vs {eq2_slug}")
            df_partido = extraer_desde_fbref(url)
            
            if df_partido is not None:
                df_partido.to_csv(path_save, index=False, encoding='utf-8-sig')
                print(f"✅ Guardado: {nombre_archivo}")
                # Pausa para evitar ban de IP
                time.sleep(random.uniform(5, 9))

if __name__ == "__main__":
    # Ejemplo: De la jornada 1 a la 38
    ejecutar_scraper_rango(inicio=1, fin=3)