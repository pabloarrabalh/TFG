import os
import pandas as pd
from bs4 import BeautifulSoup
import unicodedata
import re

ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo", "villarreal cf": "villarreal", "real oviedo": "oviedo",
    "celta vigo": "celta", "getafe cf": "getafe", "alaves": "alavés",
    "athletic club": "athletic", "elche cf": "elche", "sevilla fc": "sevilla",
    "real betis": "betis", "levante ud": "levante", "atletico": "atletico madrid",
    "atlético": "atletico madrid", "atletico madrid": "atletico madrid",
}

ALIAS_JUGADORES = {
    # Alias problemáticos y variantes con iniciales
    "a f carreras": "alvaro carreras",
    "a. f. carreras": "alvaro carreras",
    "alvaro f carreras": "alvaro carreras",
    "trent alexander arnold": "alexander arnold",
    "alexanderarnold": "alexander arnold",
    "f de jong": "frenkie de jong",
    "f. de jong": "frenkie de jong",
    "p gueye": "gueye",
    "s cardona": "cardona",
    "javi guerra": "javier guerra",
    "javier guerra": "javier guerra",
    "n williams": "nico williams",
    "n. williams": "nico williams",
    "i williams": "iñaki williams",
    "i. williams": "iñaki williams",
    "leo roman": "leo roman",
    "joan garcia": "joan garcia",
    "eric garcia": "eric garcia",
    "toni martinez": "toni martinez",
    "carlos vicente": "carlos vicente",
    "moi gomez": "moi gomez",
    "unai simon": "unai simon",
    "stanis idumbo": "stanis idumbo m.",
    # Añadir más alias según se detecten errores
}

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-–—]', '', texto)  # Elimina guiones
    return re.sub(r'\s+', ' ', texto).strip()

def normalizar_equipo(nombre):
    base = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(base, base)


# --- UNIFICACIÓN DE CLAVE DE JUGADOR (idéntica a fbref.py) ---
def clave_jugador(nombre):
    norm = normalizar_texto(nombre)
    # Alias primero
    if norm in ALIAS_JUGADORES:
        norm = ALIAS_JUGADORES[norm]
    partes = norm.split()
    claves = set()
    if len(partes) == 2:
        inicial = partes[0][0]
        apellido = partes[1]
        claves.add(f"{inicial}-{apellido}")
        claves.add(f"{inicial}{apellido}")
        claves.add(f"{partes[0]}{partes[1]}")
        claves.add(f"{partes[0]} {partes[1]}")
        claves.add(norm.replace(' ', ''))
        claves.add(norm)
        claves.add(partes[0])  # solo nombre
        claves.add(partes[1])  # solo apellido
    elif len(partes) == 3:
        inicial1 = partes[0][0]
        inicial2 = partes[1][0]
        apellido = partes[2]
        claves.add(f"{inicial1}-{inicial2}-{apellido}")
        claves.add(f"{inicial1}{inicial2}{apellido}")
        claves.add(f"{partes[0]}{partes[1]}{partes[2]}")
        claves.add(f"{partes[0]} {partes[1]} {partes[2]}")
        claves.add(norm.replace(' ', ''))
        claves.add(norm)
        claves.add(partes[0])  # solo nombre
        claves.add(partes[1])  # segundo nombre
        claves.add(partes[2])  # solo apellido
    else:
        claves.add(norm)
        claves.add(norm.replace(' ', ''))
    return list(claves)

def extraer_puntos_html(path_html):
    if not os.path.exists(path_html): return {}
    with open(path_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    
    puntos_por_partido = {}
    secciones = soup.find_all("section", class_="over fichapartido")
    
    for seccion in secciones:
        encabezado = seccion.find("header", class_="encabezado-partido")
        if not encabezado: continue
        
        n_l = normalizar_equipo(encabezado.select_one(".equipo.local .nombre").get_text())
        n_v = normalizar_equipo(encabezado.select_one(".equipo.visitante .nombre").get_text())
        clave_partido = f"{n_l}-{n_v}"
        
        puntos_partido = {}
        # Buscamos las tablas de puntos. Suele haber 2 por sección (local y visitante)
        tablas = seccion.find_all("table", class_="tablestats")
        
        for i, tabla in enumerate(tablas):
            # En la mayoría de estructuras, la primera tabla es local y la segunda visitante
            # O intentamos buscar un ancestro que nos diga el equipo
            parent_box = tabla.find_parent("div", class_=["box-estadisticas", "equipo-stats"])
            if parent_box:
                equipo_actual = n_l if "local" in parent_box.get("class", []) else n_v
            else:
                equipo_actual = n_l if i == 0 else n_v

            for fila in tabla.select("tbody tr.plegado"):
                td_name = fila.find("td", class_="name")
                span_pts = fila.select_one("span.laliga-fantasy")
                if not td_name or not span_pts: continue
                
                txt_pts = span_pts.get_text(strip=True)
                # FILTRO CLAVE: Si es '-' o '–', ignoramos al jugador completamente
                if txt_pts in ["-", "–", ""]: continue
                


                nombre_raw = re.sub(r"\s\d+'?$", "", td_name.get_text(" ", strip=True).replace("+", "").replace("-", "")).strip()
                claves_generadas = list(clave_jugador(nombre_raw))
                print(f"[DEBUG-HTML] {equipo_actual}|{nombre_raw} -> {claves_generadas}")
                for clave_j in claves_generadas:
                    clave = f"{equipo_actual}|{clave_j}"
                    puntos_partido[clave] = int(float(txt_pts))
                        
        puntos_por_partido[clave_partido] = puntos_partido
    return puntos_por_partido

def extraer_puntos_csv(path_csv):
    df = pd.read_csv(path_csv)
    res = {}
    for _, r in df.iterrows():
        if pd.isna(r['puntosFantasy']):
            continue
        equipo = normalizar_equipo(r['Equipo_propio'])
        claves_generadas = list(clave_jugador(r['player']))
        print(f"[DEBUG-CSV] {equipo}|{r['player']} -> {claves_generadas}")
        for clave_j in claves_generadas:
            clave = f"{equipo}|{clave_j}"
            res[clave] = int(float(r['puntosFantasy']))
    return res

if __name__ == "__main__":
    path_html = os.path.join('main', 'html', 'j1', 'puntos.html')
    csv_dir = os.path.join('data', 'temporada_25_26', 'jornada_1')
    
    puntos_html_todo = extraer_puntos_html(path_html)
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]

    for f_name in csv_files:
        match = re.search(r'p\d+_(.+)-(.+)\.csv', f_name)
        if not match: continue
        
        eq1, eq2 = normalizar_equipo(match.group(1)), normalizar_equipo(match.group(2))
        clave_partido = f"{eq1}-{eq2}"
        
        print(f'\n=== PARTIDO: {clave_partido} ===')
        puntos_csv = extraer_puntos_csv(os.path.join(csv_dir, f_name))
        puntos_html = puntos_html_todo.get(clave_partido) or puntos_html_todo.get(f"{eq2}-{eq1}")

        if not puntos_html:
            print(f"❌ No se encontró el partido en el HTML.")
            continue

        errores = 0
        # Normalizar claves para comparación (sin guiones ni espacios)
        def norm_clave(c):
            return c.replace('-', '').replace(' ', '').lower()
        claves_html_norm = {norm_clave(k): v for k, v in puntos_html.items()}
        for clave, val_csv in puntos_csv.items():
            n_clave = norm_clave(clave)
            val_html = claves_html_norm.get(n_clave)
            if val_html is None:
                print(f"❓ {clave}: No está en HTML (pero sí en CSV)")
                errores += 1
            elif val_html != val_csv:
                print(f"🟥 {clave}: HTML({val_html}) != CSV({val_csv})")
                errores += 1
        print(f"Total errores: {errores}")