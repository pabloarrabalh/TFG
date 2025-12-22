import os
import pandas as pd
from bs4 import BeautifulSoup
import unicodedata
import re
from rapidfuzz import process, fuzz


ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "villarreal cf": "villarreal",
    "real oviedo": "oviedo",
    "celta vigo": "celta",
    "getafe cf": "getafe",
    "alaves": "alaves",
    "alavés": "alaves",
    "athletic club": "athletic",
    "elche cf": "elche",
    "sevilla fc": "sevilla",
    "real betis": "betis",
    "levante ud": "levante",
    "atletico": "atletico madrid",
    "atlético": "atletico madrid",
    "atletico madrid": "atletico madrid",
}

ALIAS_JUGADORES = {
    # =========================
    # Desambiguaciones específicas (scrapper original)
    # =========================

    # Osasuna: Raúl García y Rubén García
    "raul garcia": "raul garcia",
    "r. garcia": "raul garcia",
    "rubén garcia": "ruben garcia",
    "ruben garcia": "ruben garcia",
    "rubén": "ruben garcia",
    "ruben": "ruben garcia",

    # Mallorca: Antonio Raíllo y Antonio Sánchez
    "antonio raillo": "antonio raillo",
    "a. raillo": "antonio raillo",
    "raillo": "antonio raillo",
    "antonio sanchez": "antonio sanchez",
    "a. sanchez": "antonio sanchez",
    "sanchez": "antonio sanchez",

    # Elche: Álvaro Rodríguez y Álvaro Núñez
    "alvaro rodriguez": "alvaro rodriguez",
    "a. rodriguez": "alvaro rodriguez",
    "alvaro nunez": "alvaro nunez",
    "a. nunez": "alvaro nunez",
    "alvaro r.": "alvaro rodriguez",
    "alvaro r": "alvaro rodriguez",

    # Barcelona / otros García genéricos
    "eric garcia": "eric garcia",
    "sergi garcia": "sergi garcia",
    "garcia": "eric garcia",  # por defecto

    # Levante: Pablo Martínez
    "pablo martinez": "pablo martinez",
    "pablo": "pablo martinez",

    # Hermanos Williams (Athletic)
    "n. williams": "nico williams",
    "nico williams": "nico williams",
    "i. williams": "inaki williams",
    "iñaki williams": "inaki williams",
    "inaki williams": "inaki williams",
    "williams": "nico williams",

    # Apodos varios
    "isaac palazon camacho": "isi palazon",
    "isaac palazon": "isi palazon",
    "isi palazon": "isi palazon",
    "cristian portugues manzanera": "portu",
    "cristian portugues": "portu",
    "jose luis garcia vaya": "pepelu",
    "jose luis garcia": "pepelu",
    "ezequiel avila": "chimy avila",
    "chimy avila": "chimy avila",

    # =========================
    # Casos específicos jornada 1 (HTML -> CSV)
    # =========================

    # Real Madrid
    "a f carreras": "alvaro carreras",
    "a. f. carreras": "alvaro carreras",
    "alexanderarnold": "trent alexander arnold",
    "alexander arnold": "trent alexander arnold",

    # Girona
    "tsygankov": "viktor tsyhankov",

    # Villarreal
    "s cardona": "sergi cardona",
    "s. cardona": "sergi cardona",
    "p gueye": "pape gueye",
    "p. gueye": "pape gueye",

    # Oviedo (Alhassane, tal y como viene en CSV)
    "alhassane": "alhassane",

    # Levante (portero y otros)
    "cunat campos": "pablo cunat",
    "cuñat campos": "pablo cunat",

    # Real Sociedad
    "caletacar": "caleta car",
    "caleta car": "caleta car",

    # Celta
    "elabdellaoui": "el abdellaoui",
    "el abdellaoui": "el abdellaoui",

    # Atlético
    "sorloth": "alexander sorloth",
    "sörloth": "alexander sorloth",

    # Mallorca (Antonio genérico del HTML => Antonio Sánchez)
    "antonio": "antonio sanchez",
    "alhassane": "rahim bonkano",
}


def normalizar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-–—]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def normalizar_equipo(nombre):
    base = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(base, base)


def aplicar_alias_jugador(nombre):
    norm = normalizar_texto(nombre)
    return ALIAS_JUGADORES.get(norm, norm)


def extraer_puntos_html(path_html):
    if not os.path.exists(path_html):
        return {}

    with open(path_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    puntos_por_partido = {}
    secciones = soup.find_all("section", class_="over fichapartido")

    for seccion in secciones:
        encabezado = seccion.find("header", class_="encabezado-partido")
        if not encabezado:
            continue

        nombre_l = encabezado.select_one(".equipo.local .nombre")
        nombre_v = encabezado.select_one(".equipo.visitante .nombre")
        if not nombre_l or not nombre_v:
            continue

        n_l = normalizar_equipo(nombre_l.get_text(strip=True))
        n_v = normalizar_equipo(nombre_v.get_text(strip=True))
        clave_partido = f"{n_l}-{n_v}"

        nombres_html = []
        tablas = seccion.find_all("table", class_="tablestats")

        for i, tabla in enumerate(tablas):
            parent_box = tabla.find_parent("div", class_=["box-estadisticas", "equipo-stats"])
            if parent_box:
                clases = parent_box.get("class", [])
                if any("local" in c for c in clases):
                    equipo_actual = n_l
                else:
                    equipo_actual = n_v
            else:
                equipo_actual = n_l if i == 0 else n_v

            for fila in tabla.select("tbody tr.plegado"):
                td_name = fila.find("td", class_="name")
                span_pts = fila.select_one("span.laliga-fantasy")
                if not td_name or not span_pts:
                    continue

                txt_pts = span_pts.get_text(strip=True)
                if txt_pts in ["-", "–", ""]:
                    continue

                nombre_raw = td_name.get_text(" ", strip=True)
                nombre_raw = nombre_raw.replace("+", "").replace("-", "")
                nombre_raw = re.sub(r"\s\d+'?$", "", nombre_raw).strip()

                nombre_completo = nombre_raw
                if td_name.has_attr('title'):
                    nombre_completo = td_name['title'].strip()
                elif td_name.has_attr('data-fullname'):
                    nombre_completo = td_name['data-fullname'].strip()

                try:
                    puntos_int = int(float(txt_pts))
                except ValueError:
                    continue

                nombres_html.append((equipo_actual, nombre_completo, puntos_int))

        puntos_por_partido[clave_partido] = nombres_html

    return puntos_por_partido


if __name__ == "__main__":
    path_html = os.path.join('main', 'html', 'j1', 'puntos.html')
    csv_dir = os.path.join('data', 'temporada_25_26', 'jornada_1')

    puntos_html_todo = extraer_puntos_html(path_html)
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]

    errores = []

    jugadores_debug = {
        ("real madrid", "Mastantuono"),
        ("real madrid", "Gonzalo"),
        ("osasuna", "Raúl García"),
        ("rayo", "Pelayo"),
        ("mallorca", "Antonio"),
        ("barcelona", "Eric García"),
        ("barcelona", "Joan García"),
        ("athletic", "I. Williams"),
        ("elche", "Alvaro R."),
    }

    for f_name in csv_files:
        m = re.search(r'p\d+_(.+)-(.+)\.csv', f_name)
        if not m:
            continue

        eq1 = normalizar_equipo(m.group(1))
        eq2 = normalizar_equipo(m.group(2))
        clave_partido = f"{eq1}-{eq2}"

        path_csv = os.path.join(csv_dir, f_name)
        df_csv = pd.read_csv(path_csv)
        df_csv['equipo_norm'] = df_csv['Equipo_propio'].apply(normalizar_equipo)
        df_csv['player_norm'] = df_csv['player'].apply(
            lambda x: normalizar_texto(aplicar_alias_jugador(x))
        )

        puntos_html = (
            puntos_html_todo.get(clave_partido)
            or puntos_html_todo.get(f"{eq2}-{eq1}")
        )
        if not puntos_html:
            continue

        partido_ok = True

        for equipo_actual_raw, nombre_html, puntos_html_val in puntos_html:
            equipo_actual = normalizar_equipo(equipo_actual_raw)
            nombre_html_norm = normalizar_texto(aplicar_alias_jugador(nombre_html))

            debug_this = (equipo_actual, nombre_html) in jugadores_debug
            if debug_this:
                print("\n[DEBUG] ---")
                print(f"PARTIDO: {clave_partido}")
                print(f"EQUIPO: {equipo_actual}")
                print(f"NOMBRE_HTML: {nombre_html}")

            candidatos = df_csv[df_csv['equipo_norm'] == equipo_actual].copy()
            if candidatos.empty:
                if debug_this:
                    print("[DEBUG] Sin candidatos en CSV para ese equipo")
                errores.append({
                    "partido": clave_partido,
                    "equipo": equipo_actual,
                    "nombre_html": nombre_html,
                    "nombre_csv": None,
                    "puntos_html": puntos_html_val,
                    "puntos_csv": None,
                    "score": 0,
                })
                partido_ok = False
                continue

            # Ambigüedad: solo un token MUY genérico y repetido
            nombres_norm_equipo = candidatos['player_norm'].tolist()
            base_tokens = nombre_html_norm.split()
            ambiguos_base = {"garcia", "williams", "alvaro"}  # 'antonio' resuelto por alias
            es_ambiguo_simple = (
                len(base_tokens) == 1
                and base_tokens[0] in ambiguos_base
                and sum(t.startswith(base_tokens[0]) for t in nombres_norm_equipo) > 1
            )

            if es_ambiguo_simple:
                if debug_this:
                    print(f"[DEBUG] Nombre ambiguo sin desambiguar en CSV: {nombre_html_norm}")
                errores.append({
                    "partido": clave_partido,
                    "equipo": equipo_actual,
                    "nombre_html": nombre_html,
                    "nombre_csv": None,
                    "puntos_html": puntos_html_val,
                    "puntos_csv": None,
                    "score": 0,
                })
                partido_ok = False
                continue

            lista_norm = candidatos['player_norm'].tolist()
            match_norm, score, _ = process.extractOne(
                nombre_html_norm,
                lista_norm,
                scorer=fuzz.WRatio
            )

            if debug_this:
                print(f"[DEBUG] Nombre_html_norm: {nombre_html_norm}")
                print(f"[DEBUG] Candidatos_norm: {lista_norm}")
                print(f"[DEBUG] Mejor match_norm: {match_norm} (score={score})")

            if match_norm is None or score < 85:
                errores.append({
                    "partido": clave_partido,
                    "equipo": equipo_actual,
                    "nombre_html": nombre_html,
                    "nombre_csv": None,
                    "puntos_html": puntos_html_val,
                    "puntos_csv": None,
                    "score": score,
                })
                partido_ok = False
                continue

            fila_match = candidatos[candidatos['player_norm'] == match_norm].iloc[0]
            nombre_csv = fila_match['player']
            puntos_csv_val = int(float(fila_match['puntosFantasy']))

            if debug_this:
                print(f"[DEBUG] Fila CSV match: {nombre_csv}, puntos_csv={puntos_csv_val}")

            if puntos_csv_val != puntos_html_val:
                errores.append({
                    "partido": clave_partido,
                    "equipo": equipo_actual,
                    "nombre_html": nombre_html,
                    "nombre_csv": nombre_csv,
                    "puntos_html": puntos_html_val,
                    "puntos_csv": puntos_csv_val,
                    "score": score,
                })
                partido_ok = False

        if partido_ok:
            print(f"{clave_partido}  \u001b[34m\u001b[1m✔\u001b[0m")
        else:
            print(f"{clave_partido}  \u001b[31m\u001b[1m✖\u001b[0m")

    if errores:
        print("\nErrores encontrados:")
        print("PARTIDO | EQUIPO | NOMBRE_HTML | NOMBRE_MATCH | PUNTOS_HTML | PUNTOS_CSV | SCORE")
        print("-" * 80)
        for err in errores:
            print(
                f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
                f"{err['nombre_csv']} | {err['puntos_html']} | {err['puntos_csv']} | "
                f"{err['score']}"
            )
