# comparar_puntos.py / comprobar_puntos.py
import os
import re
import pandas as pd
from rapidfuzz import fuzz

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
# CONFIG DEBUG / LOG
# =====================================================

DEBUG_DETALLE = True  # ponlo a True solo cuando quieras ver trazas detalladas


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
    Devuelve:
    { 'betis-leganes': [(equipo_raw, nombre_html, puntos, pos_fantasy), ...], ... }
    """
    m = re.search(r"[\\/](j(\d+))[\\/]puntos\.html$", path_html)
    if not m:
        return {}

    num_jornada = int(m.group(2))

    import fbref

    fbref.TEMPORADA_ACTUAL = codigo_temporada
    fbref.CARPETA_HTML, fbref.CARPETA_CSV = fbref._build_rutas_temporada(codigo_temporada)

    mapa_fantasy = fbref.obtener_fantasy_jornada(num_jornada)
    resultado = {}

    for clave_partido, mapa_puntos in (mapa_fantasy or {}).items():
        lista = []
        for _, info in mapa_puntos.items():
            equipo_raw = info.get("equipo")
            nombre_html = info.get("nombre_original")
            puntos = info.get("puntos", 0)
            pos_fantasy = info.get("posicion")
            lista.append((equipo_raw, nombre_html, puntos, pos_fantasy))
        resultado[clave_partido] = lista

    return resultado


# =====================================================
# REGISTRO DE ERRORES
# =====================================================


def registrar_error(
    errores,
    partido,
    equipo,
    nombre_html,
    puntos_html,
    nombre_csv,
    puntos_csv,
    score,
):
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
# LOG LIGERO (DESACTIVADO)
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


def log_debug_match_especial(
    clave_partido,
    equipo_html_norm,
    nombre_html,
    nombre_html_norm_original,
    nombre_html_norm_aliased,
    nombre_match_norm,
    nombre_csv,
    puntos_html,
    puntos_csv,
    score_match,
    fila_match=None,
):
    if not DEBUG_DETALLE:
        return

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
# LOG PARA AMBIGÜEDAD
# =====================================================


def log_match_ambiguo(
    clave_partido,
    equipo_html_norm,
    nombre_html,
    nombre_match_norm,
    score_match,
    coincidentes_df,
):
    if not DEBUG_DETALLE:
        return

    print("\n[MATCH_AMBIGUO]")
    print(f"  PARTIDO          : {clave_partido}")
    print(f"  EQUIPO_HTML_NORM : {equipo_html_norm}")
    print(f"  NOMBRE_HTML      : {nombre_html}")
    print(f"  MATCH_NORM       : {nombre_match_norm}")
    print(f"  SCORE            : {score_match}")
    print("  CANDIDATOS CSV:")
    # for _, fila in coincidentes_df.iterrows():
    #     print(
    #         f"    - player={fila['player']} | player_norm={fila['player_norm']} | "
    #         f"pos={fila.get('posicion', '')} | puntosFantasy={fila.get('puntosFantasy', '')}"
    #     )


# =====================================================
# FUNCIONES AUXILIARES DE MATCH
# =====================================================


def _resolver_coincidente(
    df_candidatos_equipo: pd.DataFrame,
    nombre_html_norm: str,
    apellido_html: str,
    pos_fantasy: str,
    puntos_html_normalizado: int,
    nombre_match_norm: str,
    clave_partido: str,
    equipo_html_norm: str,
    nombre_html: str,
    score_match: float,
):
    """
    Devuelve (fila_match, coincidentes_orden) filtrando por:
    equipo -> (match_norm duro solo si el HTML tiene varias palabras) ->
    posición opcional -> apellido -> diferencia de puntos.
    Siempre devuelve una fila del CSV (no crea filas nuevas).
    """
    coincidentes = df_candidatos_equipo.copy()

    # 1) Usar match_norm "duro" solo si el nombre HTML tiene al menos 2 palabras.
    usar_match_duro = bool(nombre_match_norm and " " in (nombre_html_norm or ""))

    if usar_match_duro and nombre_match_norm:
        coinc_nm = coincidentes[coincidentes["player_norm"] == nombre_match_norm].copy()
        if not coinc_nm.empty:
            coincidentes = coinc_nm

    # 2) Si seguimos teniendo más de uno, usar posición solo cuando el score no es muy alto
    if (
        len(coincidentes) > 1
        and "posicion" in coincidentes.columns
        and pos_fantasy
        and score_match < 90
    ):
        coinc_pos = coincidentes[coincidentes["posicion"] == pos_fantasy].copy()
        if not coinc_pos.empty:
            coincidentes = coinc_pos

    # 3) si aún hay varios y el HTML tiene apellido, filtrar por apellido
    if len(coincidentes) > 1 and apellido_html and " " in (nombre_html_norm or ""):
        coinc_ap = coincidentes[
            coincidentes["player_norm"].str.split().str[-1] == apellido_html
        ].copy()
        if not coinc_ap.empty:
            coincidentes = coinc_ap

    # 4) si solo queda uno, perfecto
    if len(coincidentes) == 1:
        coincidentes_orden = coincidentes.copy()
        fila_match = coincidentes_orden.iloc[0]
        return fila_match, coincidentes_orden

    # 5) si hay varios aún, usar diferencia de puntos como desempate final
    coincidentes = coincidentes.copy()
    coincidentes["__diff_puntos__"] = (
        coincidentes["puntosFantasy"].apply(normalizar_puntos)
        - puntos_html_normalizado
    ).abs()

    # Si el nombre HTML tiene apellido y el score es alto,
    # solo desempatar entre el mismo player_norm que dio el fuzzy.
    tiene_apellido = " " in (nombre_html_norm or "")
    if tiene_apellido and score_match >= 80 and nombre_match_norm:
        mismos_nombre = coincidentes[
            coincidentes["player_norm"] == nombre_match_norm
        ].copy()
        if not mismos_nombre.empty:
            coincidentes = mismos_nombre

    coincidentes_orden = coincidentes.sort_values("__diff_puntos__")

    if len(coincidentes_orden) > 1:
        log_match_ambiguo(
            clave_partido,
            equipo_html_norm,
            nombre_html,
            nombre_match_norm,
            score_match,
            coincidentes_orden,
        )

    fila_match = coincidentes_orden.iloc[0]
    return fila_match, coincidentes_orden


# =====================================================
# LÓGICA DE COMPROBACIÓN (RANGO / JORNADA)
# =====================================================


def comprobar_jornada_paths(path_html, csv_dir, codigo_temporada: str, score_cutoff=70):
    puntos_html_por_partido = scrapear_puntos_fantasy(path_html, codigo_temporada)
    archivos_csv = [n for n in os.listdir(csv_dir) if n.endswith(".csv")]

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
        df_partido = añadir_equipo_y_player_norm(df_partido)

        _log_claves_partido(clave_partido, puntos_html_por_partido, df_partido)

        jugadores_html_partido = (
            puntos_html_por_partido.get(clave_partido)
            or puntos_html_por_partido.get(f"{equipo_2_norm}-{equipo_1_norm}")
        )
        if not jugadores_html_partido:
            continue

        partido_ok = True

        for equipo_html_raw, nombre_html, puntos_html, pos_fantasy in jugadores_html_partido:
            puntos_html_normalizado = normalizar_puntos(puntos_html)
            if puntos_html_normalizado == 0:
                continue

            equipo_html_norm = normalizar_equipo(equipo_html_raw)
            df_candidatos_equipo = df_partido[
                df_partido["equipo_norm"] == equipo_html_norm
            ].copy()
            if df_candidatos_equipo.empty:
                continue

            nombre_html_limpio = limpiar_minuto(nombre_html)
            nombre_html_norm_original = normalizar_texto(nombre_html_limpio)

            alias_equipo = alias_temp.get(equipo_html_norm, {})
            nombre_html_norm = alias_equipo.get(
                nombre_html_norm_original,
                nombre_html_norm_original,
            )

            nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

            nombre_match_norm, score_match = obtener_match_nombre(
                nombre_html_norm,
                nombres_norm_equipo,
                equipo_norm=equipo_html_norm,
                score_cutoff=score_cutoff,
            )

            if not nombre_match_norm or score_match < score_cutoff:
                # solo log de fallo global, sin detalle por jugador
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

            apellido_html = nombre_html_norm.split()[-1] if nombre_html_norm else ""

            fila_match, coincidentes_orden = _resolver_coincidente(
                df_candidatos_equipo=df_candidatos_equipo,
                nombre_html_norm=nombre_html_norm,
                apellido_html=apellido_html,
                pos_fantasy=pos_fantasy,
                puntos_html_normalizado=puntos_html_normalizado,
                nombre_match_norm=nombre_match_norm,
                clave_partido=clave_partido,
                equipo_html_norm=equipo_html_norm,
                nombre_html=nombre_html,
                score_match=score_match,
            )

            nombre_csv = fila_match["player"]
            puntos_csv = normalizar_puntos(fila_match["puntosFantasy"])

            # Salvaguarda contra emparejamientos sin sentido (Allende, etc.)
            diff_puntos = abs(puntos_csv - puntos_html_normalizado)
            if diff_puntos >= 5 and score_match < 80:
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

        # LOG PRINCIPAL POR PARTIDO:
        print(f"{clave_partido} {'✔' if partido_ok else '✖'}")

    mostrar_errores(errores)
    return errores


# =====================================================
# API PÚBLICA
# =====================================================


def comprobar_jornada(codigo_temporada: str, num_jornada: int, score_cutoff=70):
    carpeta_html, carpeta_csv = _build_rutas_temporada(codigo_temporada)
    etiqueta_jornada = f"j{num_jornada}"

    path_html = os.path.join(carpeta_html, etiqueta_jornada, "puntos.html")
    path_csv_dir = os.path.join(carpeta_csv, f"jornada_{num_jornada}")

    return comprobar_jornada_paths(
        path_html,
        path_csv_dir,
        codigo_temporada,
        score_cutoff=score_cutoff,
    )


def comprobar_rango_jornadas(
    codigo_temporada: str,
    jornada_inicio: int,
    jornada_fin: int,
    score_cutoff=70,
):
    carpeta_html, carpeta_csv = _build_rutas_temporada(codigo_temporada)
    errores_globales = []

    # ========= WARNING ESPECÍFICO POR TEMPORADA =========
    def mostrar_warnings_temporada(cod_temp: str, j_ini: int, j_fin: int):
        msg = []

        if cod_temp == "24_25":
            if j_ini <= 10 <= j_fin:
                msg.append(
                    "24/25 J10 -> Villarreal: Pau Navarro no tiene entrada en futbolfantasy.com"
                )
            if j_ini <= 15 <= j_fin:
                msg.append(
                    "24/25 J15 -> Villarreal: Pau Cabanes no tiene entrada en futbolfantasy.com"
                )
            if j_ini <= 34 <= j_fin:
                msg.append(
                    "24/25 J34 -> Real Sociedad: Olasagasti no aparece en fbref.com"
                )

        if msg:
            print("\nWARNINGS (incidencias ajenas al scraping):")
            for linea in msg:
                print(f"  - {linea}")
    # ====================================================

    for j in range(jornada_inicio, jornada_fin + 1):
        print("\n" + "=" * 80)
        print(f"Comprobando temporada {codigo_temporada} | jornada {j}")

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
        print(
            "PARTIDO | EQUIIPO | NOMBRE_HTML | NOMBRE_MATCH | "
            "PUNTOS_HTML | PUNTOS_CSV | SCORE"
        )
        print("-" * 80)
        for err in errores_globales:
            print(
                f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
                f"{err.get('nombre_csv', '')} | {err['puntos_html']} | "
                f"{err.get('puntos_csv', '')} | {err.get('score', 0)}"
            )

    # warnings “fuera de tu control” también en el resumen global,
    # justo encima de la Nota:
    mostrar_warnings_temporada(codigo_temporada, jornada_inicio, jornada_fin)

    if errores_globales:
        print(
            "\nNota: es posible que alguno de los jugadores listados con 0 minutos "
            "haya recibido tarjeta desde el banquillo; en esos casos este "
            "comportamiento es esperado y no indica un fallo de scraping."
        )


# =====================================================
# COMPARAR UN PARTIDO
# =====================================================


def comparar_partido(
    codigo_temporada: str,
    num_jornada: int,
    num_partido: int,
    score_cutoff=70,
):
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
        f"| PARTIDO p{num_partido} ({eq1}-{eq2}) ---"
    )
    print(f"{'JUGADOR':<25} | {'EQUIPO':<15} | {'HTML':<5} | {'CSV':<5} | {'ESTADO'}")
    print("-" * 80)

    for equipo_html_raw, nombre_html, puntos_html, pos_fantasy in jugadores_html:
        puntos_html_normalizado = normalizar_puntos(puntos_html)

        equipo_html_norm = normalizar_equipo(equipo_html_raw)
        df_candidatos_equipo = df_partido[
            df_partido["equipo_norm"] == equipo_html_norm
        ].copy()
        if df_candidatos_equipo.empty:
            continue

        nombre_html_limpio = limpiar_minuto(nombre_html)
        nombre_html_norm_original = normalizar_texto(nombre_html_limpio)
        alias_equipo = alias_temp.get(equipo_html_norm, {})
        nombre_html_norm = alias_equipo.get(
            nombre_html_norm_original,
            nombre_html_norm_original,
        )

        nombres_norm_equipo = df_candidatos_equipo["player_norm"].tolist()

        match_norm, score = obtener_match_nombre(
            nombre_html_norm,
            nombres_norm_equipo,
            equipo_norm=equipo_html_norm,
            score_cutoff=score_cutoff,
        )

        puntos_csv = "-"
        estado = "❓ No existe"
        nombre_csv = ""

        if match_norm and score >= score_cutoff:
            apellido_html = nombre_html_norm.split()[-1] if nombre_html_norm else ""

            fila, coincidentes_orden = _resolver_coincidente(
                df_candidatos_equipo=df_candidatos_equipo,
                nombre_html_norm=nombre_html_norm,
                apellido_html=apellido_html,
                pos_fantasy=pos_fantasy,
                puntos_html_normalizado=puntos_html_normalizado,
                nombre_match_norm=match_norm,
                clave_partido=f"{eq1}-{eq2}",
                equipo_html_norm=equipo_html_norm,
                nombre_html=nombre_html,
                score_match=score,
            )

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

        print(
            f"{nombre_html[:25]:<25} | {equipo_html_raw[:15]:<15} | "
            f"{puntos_html:<5} | {puntos_csv:<5} | {estado}"
        )


if __name__ == "__main__":
    # ejemplo: rango completo
    comprobar_rango_jornadas("23_24", 1, 2)
    # o solo un partido:
    # comparar_partido("24_25", 15, 2)
