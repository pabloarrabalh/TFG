import os
import pandas as pd
from bs4 import BeautifulSoup
import unicodedata
import re

ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "rayo": "rayo",
    "villarreal cf": "villarreal",
    "villarreal": "villarreal",
    "real oviedo": "oviedo",
    "oviedo": "oviedo",
    "celta vigo": "celta",
    "celta": "celta",
    "getafe cf": "getafe",
    "getafe": "getafe",
    "alaves": "alavés",
    "alavés": "alavés",
    "athletic club": "athletic",
    "athletic": "athletic",
    "elche cf": "elche",
    "elche": "elche",
    "sevilla fc": "sevilla",
    "sevilla": "sevilla",
    "real betis": "betis",
    "betis": "betis",
    "levante ud": "levante",
    "levante": "levante",
    "osasuna": "osasuna",
    "espanyol": "espanyol",
    "esanyol": "espanyol",
    "atletico": "atletico madrid",
    "atlético": "atletico madrid",
    "atletico madrid": "atletico madrid",
    "atlético madrid": "atletico madrid",
    "barcelona": "barcelona",
    "mallorca": "mallorca",
    "real sociedad": "real sociedad",
    "valencia": "valencia",
    "real madrid": "real madrid",
}

def normalizar_equipo(nombre):
    base = normalizar_texto(nombre)
    # Aplica alias sobre el texto normalizado y también sobre el texto original
    return ALIAS_EQUIPOS.get(base, ALIAS_EQUIPOS.get(nombre.lower().strip(), base))

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
    # Aplica alias a cada equipo si es un partido
    if '-' in s:
        partes = s.split('-')
        partes = [normalizar_equipo(p) for p in partes]
        s = '-'.join(partes)
    else:
        s = normalizar_equipo(s)
    return s

def extraer_puntos_html(path_html):
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "lxml")
    puntos_por_partido = {}
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
        clave_partido = f"{normalizar_clave_match(n_l)}-{normalizar_clave_match(n_v)}"
        puntos = {}
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
                clave_norm = normalizar_clave_match(nombre_real)
                # Extrae el valor de la columna de puntos de laliga-fantasy (la primera span con class 'laliga-fantasy')
                puntos_val = None
                span_laliga = fila.select_one("span.racha-box.laliga-fantasy")
                if span_laliga:
                    txt = span_laliga.get_text(strip=True)
                    try:
                        puntos_val = int(float(txt))
                    except:
                        puntos_val = 0
                else:
                    puntos_val = 0
                puntos[clave_norm] = puntos_val
        puntos_por_partido[clave_partido] = puntos
    return puntos_por_partido

def extraer_puntos_csv(path_csv):
    df = pd.read_csv(path_csv)
    puntos = {}
    for _, row in df.iterrows():
        nombre = normalizar_clave_match(row['player'])
        puntos_val = int(float(row['puntosFantasy'])) if not pd.isna(row['puntosFantasy']) else 0
        puntos[nombre] = puntos_val
    return puntos

def comparar_puntos(puntos_html, puntos_csv):
    resultados = {}
    for nombre, puntos in puntos_html.items():
        if nombre in puntos_csv:
            if puntos == puntos_csv[nombre]:
                resultados[nombre] = f'HTML: {puntos} ---- CSV: {puntos_csv[nombre]} 🟩'
            else:
                resultados[nombre] = f'HTML: {puntos} ---- CSV: {puntos_csv[nombre]}'
        else:
            resultados[nombre] = f'HTML: {puntos} ---- CSV: -'
    for nombre, puntos in puntos_csv.items():
        if nombre not in puntos_html:
            resultados[nombre] = f'HTML: - ---- CSV: {puntos}'
    return resultados

if __name__ == "__main__":
    # Configura los paths de los partidos a comparar
    path_html = os.path.join('main', 'html', 'j1', 'puntos.html')
    # Busca todos los CSVs de la jornada 1 automáticamente
    csv_dir = os.path.join('data', 'temporada_25_26', 'jornada_1')
    path_csvs = [os.path.join(csv_dir, f) for f in os.listdir(csv_dir) if f.endswith('.csv')]

    puntos_html_por_partido = extraer_puntos_html(path_html)
    print("\nClaves de partido extraídas de puntos.html:")
    for k in puntos_html_por_partido.keys():
        print(f"  - {k}")

    for path_csv in path_csvs:
        nombre_csv = os.path.basename(path_csv)
        # Detecta el partido por el nombre del archivo CSV y normaliza
        partido_csv_raw = nombre_csv.replace('.csv', '').replace('p', '').replace('_', '-').replace('--', '-')
        partes = partido_csv_raw.split('-')
        if len(partes) >= 2:
            eq1 = normalizar_clave_match(partes[1])
            eq2 = normalizar_clave_match(partes[2]) if len(partes) > 2 else ''
            clave_csv = f"{eq1}-{eq2}"
        else:
            clave_csv = normalizar_clave_match(partido_csv_raw)

        print(f'\n=== Comparando partido: {clave_csv} ===')
        puntos_csv = extraer_puntos_csv(path_csv)

        # Busca el partido correspondiente en puntos_html_por_partido
        puntos_html = puntos_html_por_partido.get(clave_csv)
        clave_usada = clave_csv
        if puntos_html is None:
            # Busca por substring en ambas direcciones
            for k in puntos_html_por_partido.keys():
                if clave_csv in k or k in clave_csv:
                    puntos_html = puntos_html_por_partido[k]
                    clave_usada = k
                    print(f"Usando clave de partido por substring: {k}")
                    break

        if puntos_html is None:
            print('No se encontró el partido en puntos.html para este CSV.')
            continue

        resultados = comparar_puntos(puntos_html, puntos_csv)

        # Si el CSV tiene columna 'posicion', ordena por posición
        try:
            df = pd.read_csv(path_csv)
            orden_pos = ['PT', 'DF', 'MC', 'DT']
            df['nombre_norm'] = df['player'].apply(normalizar_clave_match)
            df['posicion'] = df['posicion'].fillna('')
            df['posicion'] = df['posicion'].str.upper()
            df = df[df['nombre_norm'].isin(resultados.keys())]
            df['estado'] = df['nombre_norm'].map(resultados)
            df = df.sort_values(by=['posicion'], key=lambda x: x.map({v: i for i, v in enumerate(orden_pos)}).fillna(99))
            for _, row in df.iterrows():
                print(f"{row['nombre_norm']} ({row['posicion']}): {row['estado']}")
        except Exception as e:
            for nombre, estado in resultados.items():
                print(f'{nombre}: {estado}')

        # Mostrar discrepancias al final del partido
        discrepancias = []
        for nombre, estado in resultados.items():
            if '🟩' not in estado:
                discrepancias.append(f"{nombre}: {estado}")
        print(f"Discrepancias: {len(discrepancias)} 🟥")
        if discrepancias:
            for d in discrepancias:
                print(d)
