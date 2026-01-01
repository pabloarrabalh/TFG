# comparar_puntos.py / comprobar_puntos.py
import os
import re
import pandas as pd

from commons import (
    normalizar_equipo,
    normalizar_puntos,
    obtener_match_nombre,
    añadir_equipo_y_player_norm,
    limpiar_minuto,
    normalizar_texto,
)
from alias import get_alias_jugadores_reverse  # usamos alias invertidos


# =====================================================
# RUTAS POR TEMPORADA
# =====================================================

def _build_rutas_temporada(codigo_temporada: str):
    """
    codigo_temporada: '24_25', '25_26', etc.

    HTML puntos: main/html/temporada_<codigo>/jX/puntos.html
    CSV       : data/temporada_<codigo>/jornada_X/*.csv
    """
    carpeta_html = os.path.join("main", "html", f"temporada_{codigo_temporada}")
    carpeta_csv = os.path.join("data", f"temporada_{codigo_temporada}")
    return carpeta_html, carpeta_csv


# =====================================================
# WRAPPER PARA LEER puntos.html USANDO fbref.py
# =====================================================

def scrapear_puntos_fantasy(path_html: str, codigo_temporada: str):
    """
    Lee puntos.html de una jornada y devuelve:
    {
      'betis-leganes': [(equipo_raw, nombre_html, puntos), ...],
      ...
    }
    reutilizando obtener_fantasy_jornada de fbref.py y
    forzando la temporada correcta.
    """
    m = re.search(r"[\\/](j(\d+))[\\/]puntos\.html$", path_html)
    if not m:
        return {}

    num_jornada = int(m.group(2))

    # importamos aquí para evitar dependencias circulares
    import fbref

    # Forzar temporada y rutas en fbref
    fbref.TEMPORADA_ACTUAL = codigo_temporada
    fbref.CARPETA_HTML, fbref.CARPETA_CSV = fbref._build_rutas_temporada(codigo_temporada)

    mapa_fantasy = fbref.obtener_fantasy_jornada(num_jornada)
    # mapa_fantasy: { 'betis-leganes': { clave_ff: info, ... }, ... }
    resultado = {}

    for clave_partido, mapa_puntos in (mapa_fantasy or {}).items():
        lista = []
        for _, info in mapa_puntos.items():
            equipo_raw = info.get("equipo")            # nombre original del equipo en Fantasy
            nombre_html = info.get("nombre_original")  # texto mostrado en puntos.html
            puntos = info.get("puntos", 0)
            lista.append((equipo_raw, nombre_html, puntos))
        resultado[clave_partido] = lista

    return resultado


# =====================================================
# REGISTRO DE ERRORES
# =====================================================

def registrar_error(errores,
                    partido,
                    equipo,
                    nombre_html,
                    puntos_html,
                    nombre_csv,
                    puntos_csv,
                    score):
    errores.append(
        {
            "partido": partido,
            "equipo": equipo,
            "nombre_html": nombre_html,
            "puntos_html": puntos_html,
            "nombre_csv": nombre_csv,
            "puntos_csv": puntos_csv,
            "score": score,
        }
    )


def mostrar_errores(errores):
    if not errores:
        print("Sin errores de puntos.")
        return

    print("\nErrores de puntos:")
    print("PARTIDO | EQUIPO | NOMBRE_HTML | NOMBRE_MATCH | PUNTOS_HTML | PUNTOS_CSV | SCORE")
    print("-" * 80)
    for err in errores:
        print(
            f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
            f"{err.get('nombre_csv', '')} | {err['puntos_html']} | "
            f"{err.get('puntos_csv', '')} | {err.get('score', 0)}"
        )


# =====================================================
# LOG LIGERO DE CLAVES POR PARTIDO (DESACTIVADO)
# =====================================================

def _log_claves_partido(clave_partido, puntos_html_por_partido, df_partido):
    # claves_html = list(puntos_html_por_partido.keys())
    # equipos_csv = sorted(df_partido["equipo_norm"].unique())
    # print(f"[PARTIDO] {clave_partido}")
    # print(f"  HTML keys        : {claves_html}")
    # print(f"  CSV equipos_norm : {equipos_csv}")
    pass


# =====================================================
# LOG ESPECIAL PARA HERRERA / ARNAU / YILDIRIM
# =====================================================

OBJ_ESPECIALES = {"herrera", "arnau", "yildirim"}


def _es_especial(nombre_html: str, nombre_match: str) -> bool:
    n1 = normalizar_texto(limpiar_minuto(nombre_html or ""))
    n2 = normalizar_texto(nombre_match or "")
    return n1 in OBJ_ESPECIALES or n2 in OBJ_ESPECIALES


def log_debug_match_especial(clave_partido,
                             equipo_html_norm,
                             nombre_html,
                             nombre_html_norm_original,
                             nombre_html_norm_aliased,
                             nombre_match_norm,
                             nombre_csv,
                             puntos_html,
                             puntos_csv,
                             score_match,
                             fila_match=None):
    if not _es_especial(nombre_html, nombre_csv or ""):
        return

    print("\n[DEBUG MATCH ESPECIAL]")
    print(f"  PARTIDO            : {clave_partido}")
    print(f"  EQUIPO_HTML_NORM   : {equipo_html_norm}")
    print(f"  NOMBRE_HTML_RAW    : {nombre_html}")
    print(f"  NOMBRE_HTML_NORM   : {nombre_html_norm_original}")
    print(f"  NOMBRE_HTML_ALIAS  : {nombre_html_norm_aliased}")
    print(f"  NOMBRE_MATCH_NORM  : {nombre_match_norm}")
    print(f"  NOMBRE_CSV         : {nombre_csv}")
    print(f"  PUNTOS_HTML        : {puntos_html}")
    print(f"  PUNTOS_CSV         : {puntos_csv}")
    print(f"  SCORE              : {score_match}")

    if fila_match is not None:
        print("  --- Fila CSV completa ---")
        for k, v in fila_match.items():
            print(f"    {k}: {v}")


# =====================================================
# LÓGICA DE COMPROBACIÓN
# =====================================================

def comprobar_jornada_paths(path_html, csv_dir, codigo_temporada: str, score_cutoff=70):
    """
    path_html: ruta a puntos.html de la jornada
    csv_dir  : carpeta con los CSV de esa jornada
    codigo_temporada: '24_25', '25_26', etc. (para cargar alias de jugadores)
    """
    puntos_html_por_partido = scrapear_puntos_fantasy(path_html, codigo_temporada)
    archivos_csv = [n for n in os.listdir(csv_dir) if n.endswith(".csv")]

    # mapa equipo_norm -> {alias_corto_norm (HTML) -> nombre_largo_norm (CSV)}
    alias_temp = get_alias_jugadores_reverse(codigo_temporada)

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

        # añade equipo_norm y player_norm a partir del CSV
        df_partido = añadir_equipo_y_player_norm(df_partido)

        _log_claves_partido(clave_partido, puntos_html_por_partido, df_partido)

        jugadores_html_partido = (
            puntos_html_por_partido.get(clave_partido)
            or puntos_html_por_partido.get(f"{equipo_2_norm}-{equipo_1_norm}")
        )
        if not jugadores_html_partido:
            continue

        partido_ok = True

        for equipo_html_raw, nombre_html, puntos_html in jugadores_html_partido:
            # Normalizar puntos del HTML y filtrar suplentes/no jugados
            puntos_html_normalizado = normalizar_puntos(puntos_html)
            if puntos_html_normalizado == 0:
                # Jugadores con 0 puntos Fantasy: normalmente suplentes/no jugados → los ignoramos
                continue

            equipo_html_norm = normalizar_equipo(equipo_html_raw)
            df_candidatos_equipo = df_partido[df_partido["equipo_norm"] == equipo_html_norm].copy()

            if df_candidatos_equipo.empty:
                # Plantilla del CSV vacía para ese equipo en este partido → nada que comparar
                continue

            # 1) limpiar minuto en nombre HTML
            nombre_html_limpio = limpiar_minuto(nombre_html)
            # 2) normalizar HTML
            nombre_html_norm_original = normalizar_texto(nombre_html_limpio)

            # 3) aplicar alias invertido (Pepelu -> jose luis garcia vaya, etc.)
            alias_equipo = alias_temp.get(equipo_html_norm, {})
            nombre_html_norm = alias_equipo.get(
                nombre_html_norm_original,
                nombre_html_norm_original,
            )

            nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

            debug_prefix = f"{clave_partido} | eq={equipo_html_norm} | HTML='{nombre_html}'"
            nombre_match_norm, score_match = obtener_match_nombre(
                nombre_html_norm,
                nombres_norm_equipo,
                equipo_norm=equipo_html_norm,
                score_cutoff=score_cutoff,
            )

            if not nombre_match_norm or score_match < score_cutoff:
                # Si a pesar de tener puntos no encontramos match decente, esto sí interesa verlo
                print(f"[MATCH_FAIL] {debug_prefix} score={score_match}")
                registrar_error(
                    errores,
                    clave_partido,
                    equipo_html_norm,
                    nombre_html,
                    puntos_html,
                    None,
                    None,
                    score_match,
                )
                partido_ok = False
                continue

            fila_match = df_candidatos_equipo[
                df_candidatos_equipo["player_norm"] == nombre_match_norm
            ].iloc[0]

            nombre_csv = fila_match["player"]
            puntos_csv = normalizar_puntos(fila_match["puntosFantasy"])

            # LOG ESPECIAL para Herrera / Arnau / Yildirim
            if puntos_csv != puntos_html_normalizado:
                log_debug_match_especial(
                    clave_partido=clave_partido,
                    equipo_html_norm=equipo_html_norm,
                    nombre_html=nombre_html,
                    nombre_html_norm_original=nombre_html_norm_original,
                    nombre_html_norm_aliased=nombre_html_norm,
                    nombre_match_norm=nombre_match_norm,
                    nombre_csv=nombre_csv,
                    puntos_html=puntos_html_normalizado,
                    puntos_csv=puntos_csv,
                    score_match=score_match,
                    fila_match=fila_match.to_dict(),
                )

            if puntos_csv != puntos_html_normalizado:
                registrar_error(
                    errores,
                    clave_partido,
                    equipo_html_norm,
                    nombre_html,
                    puntos_html,
                    nombre_csv,
                    puntos_csv,
                    score_match,
                )
                partido_ok = False

        print(f"{clave_partido} {'✔' if partido_ok else '✖'}")

    mostrar_errores(errores)
    return errores


# =====================================================
# API PÚBLICA: TEMPORADA + JORNADA(S)
# =====================================================

def comprobar_jornada(codigo_temporada: str, num_jornada: int, score_cutoff=70):
    carpeta_html, carpeta_csv = _build_rutas_temporada(codigo_temporada)
    etiqueta_jornada = f"j{num_jornada}"

    path_html = os.path.join(carpeta_html, etiqueta_jornada, "puntos.html")
    path_csv_dir = os.path.join(carpeta_csv, f"jornada_{num_jornada}")

    return comprobar_jornada_paths(path_html, path_csv_dir, codigo_temporada, score_cutoff=score_cutoff)


def comprobar_rango_jornadas(codigo_temporada: str,
                             jornada_inicio: int,
                             jornada_fin: int,
                             score_cutoff=70):
    carpeta_html, carpeta_csv = _build_rutas_temporada(codigo_temporada)
    errores_globales = []

    for j in range(jornada_inicio, jornada_fin + 1):
        print("\n" + "=" * 80)
        print(f"[LOG] ===== Comprobando temporada {codigo_temporada} | jornada {j} =====")

        etiqueta_jornada = f"j{j}"
        path_html = os.path.join(carpeta_html, etiqueta_jornada, "puntos.html")
        path_csv_dir = os.path.join(carpeta_csv, f"jornada_{j}")

        if not os.path.exists(path_html):
            print(f"No existe el HTML de puntos para la jornada {j}: {path_html}")
            continue
        if not os.path.exists(path_csv_dir):
            print(f"No existe la carpeta CSV de la jornada {j}: {path_csv_dir}")
            continue

        errores_jornada = comprobar_jornada_paths(
            path_html,
            path_csv_dir,
            codigo_temporada,
            score_cutoff=score_cutoff,
        )
        if errores_jornada:
            errores_globales.extend(errores_jornada)

    print("\n" + "=" * 80)
    print(f"RESUMEN GLOBAL {codigo_temporada} JORNADAS {jornada_inicio}-{jornada_fin}")
    if not errores_globales:
        print("Todos los jugadores tienen los puntos bien asignados en todo el rango.")
    else:
        print("Errores encontrados en el rango:")
        print("PARTIDO | EQUIIPO | NOMBRE_HTML | NOMBRE_MATCH | PUNTOS_HTML | PUNTOS_CSV | SCORE")
        print("-" * 80)
        for err in errores_globales:
            print(
                f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
                f"{err.get('nombre_csv', '')} | {err['puntos_html']} | {err.get('puntos_csv', '')} | "
                f"{err.get('score', 0)}"
            )
        print(
            "\nNota: es posible que alguno de los jugadores listados con 0 minutos "
            "haya recibido tarjeta desde el banquillo; en esos casos este "
            "comportamiento es esperado y no indica un fallo de scraping."
        )


def comparar_partido(codigo_temporada: str,
                     num_jornada: int,
                     num_partido: int,
                     score_cutoff=70):
    carpeta_html, carpeta_csv = _build_rutas_temporada(codigo_temporada)

    alias_temp = get_alias_jugadores_reverse(codigo_temporada)

    id_partido = f"p{num_partido}"
    etiqueta_jornada = f"j{num_jornada}"
    path_html = os.path.join(carpeta_html, etiqueta_jornada, "puntos.html")
    csv_dir = os.path.join(carpeta_csv, f"jornada_{num_jornada}")

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

    puntos_html_todo = scrapear_puntos_fantasy(path_html, codigo_temporada)
    jugadores_html = (
        puntos_html_todo.get(f"{eq1}-{eq2}")
        or puntos_html_todo.get(f"{eq2}-{eq1}")
    )

    if not jugadores_html:
        print(f"No hay datos en el HTML para el enfrentamiento: {eq1} vs {eq2}")
        return

    print(
        f"\n--- COMPARATIVA {codigo_temporada} | JORNADA {num_jornada} "
        f"| PARTIDO {id_partido} ({eq1}-{eq2}) ---"
    )
    print(f"{'JUGADOR':<25} | {'EQUIPO':<15} | {'HTML':<5} | {'CSV':<5} | {'ESTADO'}")
    print("-" * 80)

    for equipo_html_raw, nombre_html, puntos_html in jugadores_html:
        equipo_html_norm = normalizar_equipo(equipo_html_raw)
        df_candidatos_equipo = df_partido[df_partido["equipo_norm"] == equipo_html_norm].copy()
        nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

        nombre_html_limpio = limpiar_minuto(nombre_html)
        nombre_html_norm_original = normalizar_texto(nombre_html_limpio)
        alias_equipo = alias_temp.get(equipo_html_norm, {})
        nombre_html_norm = alias_equipo.get(
            nombre_html_norm_original,
            nombre_html_norm_original,
        )

        debug_prefix = f"{eq1}-{eq2} | eq={equipo_html_norm} | HTML='{nombre_html}'"
        match_norm, score = obtener_match_nombre(
            nombre_html_norm,
            nombres_norm_equipo,
            equipo_norm=equipo_html_norm,
            score_cutoff=score_cutoff,
        )

        puntos_csv = "-"
        estado = "❓ No existe"
        nombre_csv = ""

        puntos_html_normalizado = normalizar_puntos(puntos_html)

        if match_norm and score >= score_cutoff:
            fila = df_candidatos_equipo[
                df_candidatos_equipo["player_norm"] == match_norm
            ].iloc[0]
            puntos_csv = normalizar_puntos(fila["puntosFantasy"])
            estado = "✅ OK" if puntos_csv == puntos_html_normalizado else "❌ ERROR"
            nombre_csv = fila["player"]

            if puntos_csv != puntos_html_normalizado:
                log_debug_match_especial(
                    clave_partido=f"{eq1}-{eq2}",
                    equipo_html_norm=equipo_html_norm,
                    nombre_html=nombre_html,
                    nombre_html_norm_original=nombre_html_norm_original,
                    nombre_html_norm_aliased=nombre_html_norm,
                    nombre_match_norm=match_norm,
                    nombre_csv=nombre_csv,
                    puntos_html=puntos_html_normalizado,
                    puntos_csv=puntos_csv,
                    score_match=score,
                    fila_match=fila.to_dict(),
                )

        if not match_norm:
            print(f"[MATCH_FAIL] {debug_prefix} score={score}")
        elif score < 87:
            print(f"[MATCH<87] {debug_prefix} -> '{match_norm}' score={score}")

        print(
            f"{nombre_html[:25]:<25} | {equipo_html_raw[:15]:<15} | "
            f"{puntos_html:<5} | {puntos_csv:<5} | {estado}"
        )


if __name__ == "__main__":
    comprobar_rango_jornadas("24_25", 1, 20)
