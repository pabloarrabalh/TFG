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
    "atletico madrid": "atletico madrid"
    }

ALIAS_JUGADORES = {
    "tsygankov": "viktor tsyhankov",
    "s cardona": "sergi cardona",
    "p gueye": "pape gueye",
    "elabdellaoui": "el abdellaoui",
    "sorloth": "alexander sorloth",
    "caletacar": "caleta car",
    "isaac palazon camacho": "isi palazon",
    "jose luis garcia vaya": "pepelu",
    "ezequiel avila": "chimy avila",
    "cunat campos": "pablo cunat",
    "alhassane": "rahim bonkano",
    "a f carreras": "alvaro carreras",
    "alexanderarnold": "trent alexander arnold",
}

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto) #tildes
        if unicodedata.category(c) != 'Mn'
    )
    # IMPORTANTE: El primer codigo sustituye puntos por espacios
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-–—]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def normalizar_equipo(nombre_equipo):
    nombre_normalizado = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_normalizado, nombre_normalizado)

def aplicar_alias(nombre_jugador):
    nombre_normalizado = normalizar_texto(nombre_jugador)
    return ALIAS_JUGADORES.get(nombre_normalizado, nombre_normalizado)

def registrar_error(errores, partido, equipo, nombre_html, puntos_html, nombre_csv=None, puntos_csv=None, score=0):
    errores.append({
        "partido": partido,
        "equipo": equipo,
        "nombre_html": nombre_html,
        "nombre_csv": nombre_csv,
        "puntos_html": puntos_html,
        "puntos_csv": puntos_csv,
        "score": score,
    })

def scrapping(path_html):
    if not os.path.exists(path_html):
        return {}

    with open(path_html, "r", encoding="utf-8") as f:
        contenido_html = f.read()

    s = BeautifulSoup(contenido_html, "lxml")
    puntos_por_partido = {}
    partidos = s.find_all("section", class_="over fichapartido")
    
    for partido in partidos:
        encabezado = partido.find("header", class_="encabezado-partido")
        if not encabezado:
            continue
        
        nombre_l_tag = encabezado.select_one(".equipo.local .nombre")
        nombre_v_tag = encabezado.select_one(".equipo.visitante .nombre")

        if not nombre_l_tag or not nombre_v_tag:
            continue

        equipo_local_norm = normalizar_equipo(nombre_l_tag.get_text(strip=True))
        equipo_visitante_norm = normalizar_equipo(nombre_v_tag.get_text(strip=True))
        clave_partido = f"{equipo_local_norm}-{equipo_visitante_norm}"

        lista_jugadores_html = []
        tablas_estadisticas = partido.find_all("table", class_="tablestats")

        for indice_tabla, tabla_estadisticas in enumerate(tablas_estadisticas):
            #local y visitante
            contenedor_equipo = tabla_estadisticas.find_parent("div", class_=["box-estadisticas", "equipo-stats"])

            if contenedor_equipo:
                clases_contenedor = contenedor_equipo.get("class", [])
                if any("local" in clase for clase in clases_contenedor):
                    equipo_actual_norm = equipo_local_norm
                else:
                    equipo_actual_norm = equipo_visitante_norm
            else:
                # Primero local 
                equipo_actual_norm = equipo_local_norm if indice_tabla == 0 else equipo_visitante_norm

            jugadores = tabla_estadisticas.select("tbody tr.plegado")
            for jugador in jugadores:
                td_name = jugador.find("td", class_="name")
                span_puntos = jugador.select_one("span.laliga-fantasy")
                
                if not td_name or not span_puntos:
                    continue

                texto_puntos = span_puntos.get_text(strip=True) 
                if texto_puntos in ["-", "–", ""]:          #Los que no juegan
                    continue
                
                # CORRECCIÓN: Extraer nombre completo del title o data-fullname como en el Codigo 1
                nombre_raw = td_name.get_text(" ", strip=True) 
                nombre_raw = re.sub(r"\s\d+'?$", "", nombre_raw).strip() # Quitar mins Raúl García
                
                nombre_completo = nombre_raw
                if td_name.has_attr('title'):
                    nombre_completo = td_name['title'].strip()
                elif td_name.has_attr('data-fullname'):
                    nombre_completo = td_name['data-fullname'].strip()

                try:
                    puntos_int = int(float(texto_puntos))
                except ValueError:
                    continue

                lista_jugadores_html.append((equipo_actual_norm, nombre_completo, puntos_int))

        puntos_por_partido[clave_partido] = lista_jugadores_html

    return puntos_por_partido

APELLIDOS_AMBIGUOS = {"garcia", "williams", "alvaro"}

def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return valor

def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (
        len(tokens) == 1
        and tokens[0] in APELLIDOS_AMBIGUOS
        and sum(n.startswith(tokens[0]) for n in nombres_norm_equipo) > 1
    )

def obtener_match_nombre(nombre_html_norm, nombres_norm_equipo):
    # Usamos score 85 como el codigo que funciona
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    return nombre_match_norm, score_match

def comprobar_jornada_paths(path_html, csv_dir):
    puntos_html_por_partido = scrapping(path_html)
    archivos_csv = [n for n in os.listdir(csv_dir) if n.endswith(".csv")]

    errores = []

    for nombre_archivo_csv in archivos_csv:
        coincidencia_nombre = re.search(r"p\d+_(.+)-(.+)\.csv", nombre_archivo_csv)
        if not coincidencia_nombre:
            continue

        equipo_1_norm = normalizar_equipo(coincidencia_nombre.group(1))
        equipo_2_norm = normalizar_equipo(coincidencia_nombre.group(2))
        clave_partido = f"{equipo_1_norm}-{equipo_2_norm}"

        ruta_csv = os.path.join(csv_dir, nombre_archivo_csv)
        df_partido = pd.read_csv(ruta_csv)

        # Añadimos columnas normalizadas para poder comparar cómodamente
        df_partido["equipo_norm"] = df_partido["Equipo_propio"].apply(normalizar_equipo)
        df_partido["player_norm"] = df_partido["player"].apply(
            lambda nombre: normalizar_texto(aplicar_alias(nombre))
        )

        # Recuperamos los jugadores/puntos HTML de este partido
        jugadores_html_partido = (
            puntos_html_por_partido.get(clave_partido)
            or puntos_html_por_partido.get(f"{equipo_2_norm}-{equipo_1_norm}")
        )
        if not jugadores_html_partido:
            continue

        partido_ok = True
        for equipo_html_raw, nombre_html, puntos_html in jugadores_html_partido:
            equipo_html_norm = normalizar_equipo(equipo_html_raw)
            nombre_html_norm = normalizar_texto(aplicar_alias(nombre_html))

            # Filtrar en el CSV solo las filas de ese equipo
            df_candidatos_equipo = df_partido[df_partido["equipo_norm"] == equipo_html_norm].copy()
            if df_candidatos_equipo.empty:
                registrar_error(errores, clave_partido, equipo_html_norm, nombre_html, puntos_html, None, None, 0)
                partido_ok = False
                continue

            nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

            # Chequeo de ambigüedad simple
            if es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
                registrar_error(errores, clave_partido, equipo_html_norm, nombre_html, puntos_html, None, None, 0)
                partido_ok = False
                continue

            nombre_match_norm, score_match = obtener_match_nombre(nombre_html_norm, nombres_norm_equipo)

            if nombre_match_norm is None or score_match < 85:
                registrar_error(errores, clave_partido, equipo_html_norm, nombre_html, puntos_html, None, None, score_match)
                partido_ok = False
                continue

            fila_match = df_candidatos_equipo[df_candidatos_equipo["player_norm"] == nombre_match_norm].iloc[0]

            nombre_csv = fila_match["player"]
            puntos_csv = normalizar_puntos(fila_match["puntosFantasy"])
            puntos_html_normalizado = normalizar_puntos(puntos_html)

            if puntos_csv != puntos_html_normalizado:
                registrar_error(errores, clave_partido, equipo_html_norm, nombre_html, puntos_html, nombre_csv, puntos_csv, score_match)
                partido_ok = False

        # El indicador visual del primer script
        if partido_ok:
            print(f"{clave_partido} ✔")
        else:
            print(f"{clave_partido}  ✖")

    mostrar_errores(errores)
    return errores

def mostrar_errores(errores):
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
    else:
        print("\nTodos los jugadores tienen los puntos bien asignados.")


def comprobar_jornada(num_jornada):
    etiqueta_jornada = f"j{num_jornada}"
    path_html = os.path.join("main", "html", etiqueta_jornada, "puntos.html")
    path_csv_dir = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    return comprobar_jornada_paths(path_html, path_csv_dir)

if __name__ == "__main__":
    comprobar_jornada(1)