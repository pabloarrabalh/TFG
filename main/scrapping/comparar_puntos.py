# comprobar_puntos.py
import os
import re
import pandas as pd
from bs4 import BeautifulSoup

from commons import (
    normalizar_texto,
    normalizar_equipo,
    normalizar_puntos,
    obtener_match_nombre,
    aplicar_alias_contextual,
    añadir_equipo_y_player_norm,
)


def registrar_error(errores, partido, equipo, nombre_html, puntos_html,
                    nombre_csv=None, puntos_csv=None, score=0):
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
        print(f"[SCRAPPING] No existe {path_html}")
        return {}

    with open(path_html, "r", encoding="utf-8") as f:
        contenido_html = f.read()

    soup = BeautifulSoup(contenido_html, "lxml")
    puntos_por_partido = {}
    partidos = soup.find_all("section", class_="over fichapartido")

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

        for indice_tabla, tabla in enumerate(tablas_estadisticas):
            contenedor_equipo = tabla.find_parent(
                "div", class_=["box-estadisticas", "equipo-stats"]
            )

            if contenedor_equipo:
                clases = contenedor_equipo.get("class", [])
                if any("local" in c for c in clases):
                    equipo_actual_norm = equipo_local_norm
                else:
                    equipo_actual_norm = equipo_visitante_norm
            else:
                equipo_actual_norm = (
                    equipo_local_norm if indice_tabla == 0 else equipo_visitante_norm
                )

            jugadores = tabla.select("tbody tr.plegado")
            for fila in jugadores:
                td_name = fila.find("td", class_="name")
                span_puntos = fila.select_one("span.laliga-fantasy")
                if not td_name or not span_puntos:
                    continue

                texto_puntos = span_puntos.get_text(strip=True)
                if texto_puntos in ["-", "–", ""]:
                    continue

                nombre_raw = td_name.get_text(" ", strip=True)
                nombre_raw = re.sub(r"\s\d+'?$", "", nombre_raw).strip()

                nombre_completo = nombre_raw
                if td_name.has_attr("title"):
                    nombre_completo = td_name["title"].strip()
                elif td_name.has_attr("data-fullname"):
                    nombre_completo = td_name["data-fullname"].strip()

                try:
                    puntos_int = int(float(texto_puntos))
                except ValueError:
                    continue

                lista_jugadores_html.append(
                    (equipo_actual_norm, nombre_completo, puntos_int)
                )

        puntos_por_partido[clave_partido] = lista_jugadores_html

    return puntos_por_partido


def comprobar_jornada_paths(path_html, csv_dir, score_cutoff=70):
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

        df_partido = añadir_equipo_y_player_norm(df_partido)

        jugadores_html_partido = (
            puntos_html_por_partido.get(clave_partido)
            or puntos_html_por_partido.get(f"{equipo_2_norm}-{equipo_1_norm}")
        )
        if not jugadores_html_partido:
            continue

        partido_ok = True
        for equipo_html_raw, nombre_html, puntos_html in jugadores_html_partido:
            equipo_html_norm = normalizar_equipo(equipo_html_raw)
            df_candidatos_equipo = df_partido[df_partido["equipo_norm"] == equipo_html_norm].copy()
            if df_candidatos_equipo.empty:
                registrar_error(errores, clave_partido, equipo_html_norm,
                                nombre_html, puntos_html, None, None, 0)
                partido_ok = False
                continue

            nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

            debug_prefix = f"{clave_partido} | eq={equipo_html_norm} | HTML='{nombre_html}'"
            nombre_match_norm, score_match = obtener_match_nombre(
                nombre_html,
                nombres_norm_equipo,
                equipo_norm=equipo_html_norm,
                score_cutoff=score_cutoff,
            )

            if not nombre_match_norm or score_match < score_cutoff:
                print(f"[MATCH_FAIL] {debug_prefix} score={score_match}")
                registrar_error(errores, clave_partido, equipo_html_norm,
                                nombre_html, puntos_html, None, None, score_match)
                partido_ok = False
                continue

            
            fila_match = df_candidatos_equipo[
                df_candidatos_equipo["player_norm"] == nombre_match_norm
            ].iloc[0]

            nombre_csv = fila_match["player"]
            puntos_csv = normalizar_puntos(fila_match["puntosFantasy"])
            puntos_html_normalizado = normalizar_puntos(puntos_html)

            if puntos_csv != puntos_html_normalizado:
                registrar_error(
                    errores, clave_partido, equipo_html_norm,
                    nombre_html, puntos_html, nombre_csv, puntos_csv, score_match
                )
                partido_ok = False

        print(f"{clave_partido} {'✔' if partido_ok else '✖'}")

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


def comprobar_rango_jornadas(jornada_inicio, jornada_fin, score_cutoff=70):
    """
    Recorre de jornada_inicio a jornada_fin (incluidas),
    llama a comprobar_jornada y acumula todos los errores.
    """
    errores_globales = []

    for j in range(jornada_inicio, jornada_fin + 1):
        print("\n" + "=" * 80)
        print(f"[LOG] ===== Comprobando jornada {j} =====")

        etiqueta_jornada = f"j{j}"
        path_html = os.path.join("main", "html", etiqueta_jornada, "puntos.html")
        path_csv_dir = os.path.join("data", "temporada_25_26", f"jornada_{j}")

        if not os.path.exists(path_html):
            print(f"No existe el HTML de puntos para la jornada {j}: {path_html}")
            continue
        if not os.path.exists(path_csv_dir):
            print(f"No existe la carpeta CSV de la jornada {j}: {path_csv_dir}")
            continue

        errores_jornada = comprobar_jornada_paths(path_html, path_csv_dir, score_cutoff=score_cutoff)
        if errores_jornada:
            errores_globales.extend(errores_jornada)

    print("\n" + "=" * 80)
    print(f"RESUMEN GLOBAL JORNADAS {jornada_inicio}-{jornada_fin}")
    if not errores_globales:
        print("Todos los jugadores tienen los puntos bien asignados en todo el rango.")
    else:
        print("Errores encontrados en el rango:")
        print("PARTIDO | EQUIPO | NOMBRE_HTML | NOMBRE_MATCH | PUNTOS_HTML | PUNTOS_CSV | SCORE")
        print("-" * 80)
        for err in errores_globales:
            print(
                f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
                f"{err['nombre_csv']} | {err['puntos_html']} | {err['puntos_csv']} | "
                f"{err['score']}"
            )


def comparar_partido(num_jornada, num_partido):
    id_partido = f"p{num_partido}"
    etiqueta_jornada = f"j{num_jornada}"
    path_html = os.path.join("main", "html", etiqueta_jornada, "puntos.html")
    csv_dir = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")

    try:
        archivos = os.listdir(csv_dir)
        archivo_csv = next((f for f in archivos if f.startswith(f"{id_partido}_")), None)
    except FileNotFoundError:
        print(f"No se encuentra la carpeta: {csv_dir}")
        return

    if not archivo_csv:
        print(f"No se encontró el archivo CSV para el partido {id_partido}")
        return

    m = re.search(r"p\d+_(.+)-(.+)\.csv", archivo_csv)
    eq1 = normalizar_equipo(m.group(1))
    eq2 = normalizar_equipo(m.group(2))

    df_partido = pd.read_csv(os.path.join(csv_dir, archivo_csv))
    df_partido = añadir_equipo_y_player_norm(df_partido)

    puntos_html_todo = scrapping(path_html)
    jugadores_html = (
        puntos_html_todo.get(f"{eq1}-{eq2}")
        or puntos_html_todo.get(f"{eq2}-{eq1}")
    )

    if not jugadores_html:
        print(f"No hay datos en el HTML para el enfrentamiento: {eq1} vs {eq2}")
        return

    print(f"\n--- COMPARATIVA JORNADA {num_jornada} | PARTIDO {id_partido} ({eq1}-{eq2}) ---")
    print(f"{'JUGADOR':<25} | {'EQUIPO':<15} | {'HTML':<5} | {'CSV':<5} | {'ESTADO'}")
    print("-" * 80)

    for equipo_html_raw, nombre_html, puntos_html in jugadores_html:
        equipo_html_norm = normalizar_equipo(equipo_html_raw)
        df_candidatos_equipo = df_partido[df_partido["equipo_norm"] == equipo_html_norm].copy()
        nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

        debug_prefix = f"{eq1}-{eq2} | eq={equipo_html_norm} | HTML='{nombre_html}'"
        match_norm, score = obtener_match_nombre(
            nombre_html,
            nombres_norm_equipo,
            equipo_norm=equipo_html_norm,
            score_cutoff=70,
        )

        puntos_csv = "-"
        estado = "❓ No existe"

        if match_norm and score >= 70:
            fila = df_candidatos_equipo[df_candidatos_equipo["player_norm"] == match_norm].iloc[0]
            puntos_csv = normalizar_puntos(fila["puntosFantasy"])
            estado = "✅ OK" if puntos_csv == puntos_html else "❌ ERROR"

        if not match_norm:
            print(f"[MATCH_FAIL] {debug_prefix} score={score}")
        elif score < 87:
            print(f"[MATCH<87] {debug_prefix} -> '{match_norm}' score={score}")

        print(f"{nombre_html[:25]:<25} | {equipo_html_raw[:15]:<15} | {puntos_html:<5} | {puntos_csv:<5} | {estado}")


if __name__ == "__main__":
    # una jornada
    # comprobar_jornada(2)

    # rango de jornadas (por ejemplo, de la 1 a la 10)
    comprobar_rango_jornadas(1, 17)
    # comparar_partido(1, 1)
