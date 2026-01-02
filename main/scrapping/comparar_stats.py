import os
import re
import pandas as pd
from rapidfuzz import process, fuzz
from io import StringIO

from commons import (
    normalizar_texto,
    normalizar_equipo,
    añadir_equipo_y_player_norm,
    limpiar_numero_generico,
    fmt_generico,
    limpiar_minuto,
    extraer_nombre_jugador,
    _posicion_csv_es_medio,
    _posicion_csv_es_defensa,
    _posicion_html,
)
from fbref import (
    normalizar_equipo_temporada,
)
from bs4 import BeautifulSoup


# =====================================================
# HELPERS DE RUTAS POR TEMPORADA
# =====================================================


def _carpeta_html_partidos(codigo_temporada: str, num_jornada: int) -> str:
    return os.path.join("main", "html", f"temporada_{codigo_temporada}", f"j{num_jornada}")


def _carpeta_csv_jornada(codigo_temporada: str, num_jornada: int) -> str:
    return os.path.join("data", f"temporada_{codigo_temporada}", f"jornada_{num_jornada}")


# =====================================================
# EXTRAER TABLAS FBREF Y DICCIONARIO JUGADORES
# =====================================================


def extraer_tablas_fbref(html_content: str):
    soup = BeautifulSoup(html_content, "lxml")
    tablas = []

    # summary, passing, defense, possession, misc, keepers
    tipos = ["summary", "passing", "defense", "possession", "misc", "keepers"]
    for tipo in tipos:
        if tipo == "keepers":
            tablas_tipo = list(soup.find_all("table", id=re.compile(r"stats_.*_keepers")))
            for tabla in soup.find_all("table"):
                tid = tabla.get("id") or ""
                if "keeper_stats_" in tid and tabla not in tablas_tipo:
                    tablas_tipo.append(tabla)
        else:
            tablas_tipo = soup.find_all("table", id=re.compile(f"stats_.*_{tipo}"))

        for tabla in tablas_tipo:
            tablas.append((tipo, tabla))

    return tablas


def construir_diccionario_jugadores(tablas):
    """
    Construye un diccionario:
    {
      nombre_norm: {
         "summary:Min": ...,
         "summary:Gls": ...,
         ...
      },
      ...
    }
    usando las tablas de FBRef.
    """
    jugadores_html = {}

    for tipo, tabla_html in tablas:
        caption = tabla_html.find("caption")
        if caption:
            texto_caption = caption.get_text(strip=True)
        else:
            texto_caption = ""

        equipo_local = ""
        equipo_visitante = ""

        try:
            df_tabla = pd.read_html(StringIO(str(tabla_html)))[0]
        except Exception:
            continue

        columnas = []
        for columna in df_tabla.columns.get_level_values(-1):
            texto_columna = str(columna)
            columnas.append(texto_columna)
        df_tabla.columns = columnas

        for _, fila in df_tabla.iterrows():
            nombre = str(fila.get("Player", "")).strip()
            nombre = re.sub(r"\s\(.*\)\s*", "", nombre).strip()
            if nombre in ["nan", "Player", "Total", "Players"]:
                continue
            if re.match(r"^\d+\s+Players$", nombre):
                continue

            nombre = limpiar_minuto(nombre)
            nombre_norm = normalizar_texto(nombre)

            if nombre_norm not in jugadores_html:
                jugadores_html[nombre_norm] = {}

            for col in df_tabla.columns:
                val = fila.get(col, "")
                clave = f"{tipo}:{col}"
                jugadores_html[nombre_norm][clave] = val

    return jugadores_html


# =====================================================
# LÓGICA PRINCIPAL
# =====================================================


def mostrar_analisis_jugador(resultado):
    if not resultado["ok"]:
        print(resultado["motivo"])
        return

    campos_mal = resultado["campos_mal"]
    discrepancias = resultado["discrepancias"]

    if not campos_mal:
        return

    nombre = resultado["jugador_objetivo"]
    print(f"\n[ERROR] {nombre}")
    for d in discrepancias:
        campo = d["campo"]
        csv_val = d["csv"]
        html_val = d["html"]
        print(f"  - {campo}: CSV={csv_val} | HTML={html_val}")


def comparar_partido_stats_precalculado(jugadores_html, df_csv, jugador_objetivo):
    """
    Igualar jugador en CSV y en HTML, y preparar getters de columnas FBRef.
    Se evita fuzzy-match HTML para jugadores sin minutos (suplentes puros).
    """
    fila_jugador = None
    equipo_jugador = None

    # 1) match exacto en CSV por equipo propio
    for eq in df_csv["equipo_norm"].unique().tolist():
        obj_norm_eq = normalizar_texto(jugador_objetivo)
        cand = df_csv[
            (df_csv["equipo_norm"] == eq) & (df_csv["player_norm"] == obj_norm_eq)
        ]
        if not cand.empty:
            fila_jugador = cand.iloc[0]
            equipo_jugador = eq
            break

    # 2) fuzzy en CSV si no hubo match exacto
    if fila_jugador is None:
        nombres_csv_norm = df_csv["player_norm"].tolist()
        match_norm, score, idx = process.extractOne(
            normalizar_texto(jugador_objetivo),
            nombres_csv_norm,
            scorer=fuzz.WRatio,
        )
        if not match_norm or idx is None:
            return None

        fila_jugador = df_csv.iloc[idx]
        equipo_jugador = fila_jugador["equipo_norm"]

    if fila_jugador is None:
        return None

    # minutos en CSV, para decidir si tiene sentido buscarlo en HTML
    try:
        min_csv = float(fila_jugador.get("Min_partido", 0) or 0)
    except Exception:
        min_csv = 0.0

    # 3) localizar jugador en diccionario HTML
    jugador_norm = normalizar_texto(jugador_objetivo)
    nombres_html = list(jugadores_html.keys())

    # --- CASO 3A: si no está en HTML y no jugó minutos, no comparar ---
    if jugador_norm not in jugadores_html and min_csv == 0:
        # suplente sin minutos, stats FBRef no existen -> no se analiza
        return None

    # --- CASO 3B: exacto en HTML ---
    if jugador_norm in jugadores_html:
        row_html = jugadores_html[jugador_norm]
    else:
        # --- CASO 3C: fuzzy en HTML sólo si tiene minutos ---
        if not nombres_html:
            return None

        candidatos = process.extract(
            jugador_norm,
            nombres_html,
            scorer=fuzz.WRatio,
            limit=None,
        )
        candidatos = [(name, score) for name, score, _ in candidatos if score >= 75]
        if not candidatos:
            return None

        pos_medio_csv = _posicion_csv_es_medio(fila_jugador)
        pos_def_csv = _posicion_csv_es_defensa(fila_jugador)

        candidatos_filtrados = candidatos
        if pos_medio_csv or pos_def_csv:
            candidatos_pos = []
            for name, score in candidatos:
                row_html_cand = jugadores_html.get(name, {})
                pos_html = _posicion_html(row_html_cand)
                es_def = any(p in pos_html for p in ["DF", "DC", "LD", "LI", "CB", "LB", "RB"])
                es_med = any(p in pos_html for p in ["MF", "DM", "CM", "LM", "RM", "AM"])
                if pos_medio_csv and es_med:
                    candidatos_pos.append((name, score))
                elif pos_def_csv and es_def:
                    candidatos_pos.append((name, score))
            if candidatos_pos:
                candidatos_filtrados = candidatos_pos

        candidatos_filtrados.sort(key=lambda x: x[1], reverse=True)
        match_norm_html, score_html = candidatos_filtrados[0]
        jugador_norm = match_norm_html
        row_html = jugadores_html[jugador_norm]

    def get_summary(col):
        return row_html.get(f"summary:{col}", "")

    def get_passing(col):
        return row_html.get(f"passing:{col}", "")

    def get_misc(col):
        return row_html.get(f"misc:{col}", "")

    def get_keepers(col):
        return row_html.get(f"keepers:{col}", "")

    def get_defense(col):
        return row_html.get(f"defense:{col}", "")

    def get_possession(col):
        return row_html.get(f"possession:{col}", "")

    es_portero = str(fila_jugador.get("posicion", "")).strip().upper() == "PT"

    return {
        "jugador_objetivo": jugador_objetivo,
        "fila_csv": fila_jugador,
        "row_html": row_html,
        "get_summary": get_summary,
        "get_passing": get_passing,
        "get_misc": get_misc,
        "get_keepers": get_keepers,
        "get_defense": get_defense,
        "get_possession": get_possession,
        "es_portero": es_portero,
    }


def _comparar_campos_stats(
    fila_csv,
    es_portero,
    get_summary,
    get_passing,
    get_misc,
    get_keepers,
    get_defense,
    get_possession,
):
    campos_a_comprobar = [
        ("Min_partido", lambda: (fila_csv.get("Min_partido", ""), get_summary("Min"))),
        ("Gol_partido", lambda: (fila_csv.get("Gol_partido", ""), get_summary("Gls"))),
        ("Asist_partido", lambda: (fila_csv.get("Asist_partido", ""), get_summary("Ast"))),
        ("xG_partido", lambda: (fila_csv.get("xG_partido", ""), get_summary("xG"))),
        ("Tiros", lambda: (fila_csv.get("Tiros", ""), get_summary("Sh"))),
        (
            "TiroFallado_partido",
            lambda: (
                fila_csv.get("TiroFallado_partido", ""),
                (float(get_summary("Sh")) - float(get_summary("SoT")))
                if get_summary("Sh") not in ("", None)
                and get_summary("SoT") not in ("", None)
                else 0.0,
            ),
        ),
        (
            "TiroPuerta_partido",
            lambda: (fila_csv.get("TiroPuerta_partido", ""), get_summary("SoT")),
        ),
        ("Pases_Totales", lambda: (fila_csv.get("Pases_Totales", ""), get_summary("Att"))),
        (
            "Pases_Completados_Pct",
            lambda: (
                fila_csv.get("Pases_Completados_Pct", ""),
                (
                    limpiar_numero_generico(get_passing("Cmp%"))
                    if str(get_passing("Cmp%")).strip() not in ("", "-", "nan", "NaN")
                    else limpiar_numero_generico(get_summary("Cmp%"))
                ),
            ),
        ),
        ("Amarillas", lambda: (fila_csv.get("Amarillas", ""), get_misc("CrdY"))),
        ("Rojas",     lambda: (fila_csv.get("Rojas", ""),     get_misc("CrdR"))),
        (
            "Goles_en_contra",
            lambda: (
                fila_csv.get("Goles_en_contra", ""),
                limpiar_numero_generico(get_keepers("GA")) if es_portero else 0,
            ),
        ),
        (
            "Porcentaje_paradas",
            lambda: (
                fila_csv.get("Porcentaje_paradas", ""),
                limpiar_numero_generico(get_keepers("Save%")) if es_portero else 0,
            ),
        ),
        (
            "PSxG",
            lambda: (
                fila_csv.get("PSxG", ""),
                limpiar_numero_generico(get_keepers("PSxG")) if es_portero else 0,
            ),
        ),
        ("Entradas", lambda: (fila_csv.get("Entradas", ""), get_defense("Tkl"))),
        ("Duelos", lambda: (fila_csv.get("Duelos", ""), get_defense("Att"))),
        ("DuelosGanados", lambda: (fila_csv.get("DuelosGanados", ""), get_defense("Won"))),
        ("DuelosPerdidos", lambda: (fila_csv.get("DuelosPerdidos", ""), get_defense("Lost"))),
        ("Bloqueos", lambda: (fila_csv.get("Bloqueos", ""), get_defense("Blocks"))),
        ("BloqueoTiros", lambda: (fila_csv.get("BloqueoTiros", ""), get_defense("Sh"))),
        ("BloqueoPase", lambda: (fila_csv.get("BloqueoPase", ""), get_defense("Pass"))),
        ("Despejes", lambda: (fila_csv.get("Despejes", ""), get_defense("Clr"))),
        ("Regates", lambda: (fila_csv.get("Regates", ""), get_possession("Att"))),
        (
            "RegatesCompletados",
            lambda: (fila_csv.get("RegatesCompletados", ""), get_possession("Succ")),
        ),
        (
            "RegatesFallidos",
            lambda: (fila_csv.get("RegatesFallidos", ""), get_possession("Tkld")),
        ),
        ("Conducciones", lambda: (fila_csv.get("Conducciones", ""), get_possession("Carries"))),
        (
            "DistanciaConduccion",
            lambda: (fila_csv.get("DistanciaConduccion", ""), get_possession("TotDist")),
        ),
        (
            "MetrosAvanzadosConduccion",
            lambda: (fila_csv.get("MetrosAvanzadosConduccion", ""), get_possession("PrgDist")),
        ),
        (
            "ConduccionesProgresivas",
            lambda: (fila_csv.get("ConduccionesProgresivas", ""), get_possession("PrgC")),
        ),
        ("DuelosAereosGanados", lambda: (fila_csv.get("DuelosAereosGanados", ""), get_misc("Won"))),
        (
            "DuelosAereosPerdidos",
            lambda: (fila_csv.get("DuelosAereosPerdidos", ""), get_misc("Lost")),
        ),
        (
            "DuelosAereosGanadosPct",
            lambda: (
                fila_csv.get("DuelosAereosGanadosPct", ""),
                limpiar_numero_generico(get_misc("Won%")),
            ),
        ),
    ]

    campos_mal = []
    discrepancias = []
    for campo, getter in campos_a_comprobar:
        val_csv, val_html = getter()
        val_csv_n = limpiar_numero_generico(val_csv)
        val_html_n = limpiar_numero_generico(val_html)
        if val_csv_n != val_html_n:
            campos_mal.append(campo)
            discrepancias.append(
                {"campo": campo, "csv": fmt_generico(val_csv_n), "html": fmt_generico(val_html_n)}
            )

    return campos_mal, discrepancias


def analizar_jugador_interno_precalculado(jugadores_html, df_csv, nombre_jugador):
    info = comparar_partido_stats_precalculado(jugadores_html, df_csv, nombre_jugador)
    if info is None:
        return {
            "ok": False,
            "motivo": f"No se pudo analizar al jugador '{nombre_jugador}' en este partido.",
        }

    fila_csv = info["fila_csv"]
    get_summary = info["get_summary"]
    get_passing = info["get_passing"]
    get_misc = info["get_misc"]
    get_keepers = info["get_keepers"]
    get_defense = info["get_defense"]
    get_possession = info["get_possession"]
    es_portero = info["es_portero"]

    campos_mal, discrepancias = _comparar_campos_stats(
        fila_csv, es_portero, get_summary, get_passing,
        get_misc, get_keepers, get_defense, get_possession
    )

    return {
        "ok": True,
        "jugador_objetivo": nombre_jugador,
        "info": info,
        "campos_mal": campos_mal,
        "discrepancias": discrepancias,
    }


# =====================================================
# CLASIFICAR NO_ANALIZADOS SEGÚN TARJETA DESDE BANQUILLO
# =====================================================


def clasificar_no_analizados_tarjetas(codigo_temporada: str, no_analizados_globales):
    con_tarjeta_banquillo = []
    otros = []

    cache_partidos = {}

    for err in no_analizados_globales:
        j = err["jornada"]
        p = err["partido"]
        jugador = err["jugador"]

        clave_partido = (j, p)
        if clave_partido not in cache_partidos:
            carpeta_csv = _carpeta_csv_jornada(codigo_temporada, j)
            archivos_csv = [
                n for n in os.listdir(carpeta_csv)
                if n.startswith(f"p{p}_") and n.endswith(".csv")
            ]
            if not archivos_csv:
                cache_partidos[clave_partido] = None
            else:
                path_csv = os.path.join(carpeta_csv, archivos_csv[0])
                df = pd.read_csv(path_csv)
                cache_partidos[clave_partido] = df

        df_partido = cache_partidos.get(clave_partido)
        if df_partido is None:
            otros.append(err)
            continue

        fila_jug = df_partido[df_partido["player"] == jugador]
        if fila_jug.empty:
            otros.append(err)
            continue

        fila = fila_jug.iloc[0]
        try:
            min_partido = float(fila.get("Min_partido", 0) or 0)
        except Exception:
            min_partido = 0.0

        try:
            amar = float(fila.get("Amarillas", 0) or 0)
        except Exception:
            amar = 0.0

        try:
            roj = float(fila.get("Rojas", 0) or 0)
        except Exception:
            roj = 0.0

        if min_partido == 0 and (amar + roj) > 0:
            err2 = dict(err)
            err2["tarjeta_banquillo"] = True
            con_tarjeta_banquillo.append(err2)
        else:
            otros.append(err)

    return con_tarjeta_banquillo, otros


# =====================================================
# FUNCIONES PÚBLICAS CON MULTI‑TEMPORADA
# =====================================================


def analizar_jugador(codigo_temporada: str, num_jornada: int, num_partido: int, nombre_jugador: str):
    carpeta_html = _carpeta_html_partidos(codigo_temporada, num_jornada)
    carpeta_csv = _carpeta_csv_jornada(codigo_temporada, num_jornada)

    archivos_csv = [
        n
        for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        print(f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}")
        return

    archivo_csv = archivos_csv[0]
    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    path_csv = os.path.join(carpeta_csv, archivo_csv)

    if not os.path.exists(path_html):
        print(f"Falta HTML: {path_html}")
        return

    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)

    df_csv = pd.read_csv(path_csv)
    df_csv = añadir_equipo_y_player_norm(df_csv)

    resultado = analizar_jugador_interno_precalculado(jugadores_html, df_csv, nombre_jugador)
    mostrar_analisis_jugador(resultado)


def analizar_partido_completo(codigo_temporada: str, num_jornada: int, num_partido: int,
                              errores_jornada, no_analizados_jornada):
    carpeta_html = _carpeta_html_partidos(codigo_temporada, num_jornada)
    carpeta_csv = _carpeta_csv_jornada(codigo_temporada, num_jornada)

    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    if not os.path.exists(path_html):
        print(f"Falta HTML: {path_html}")
        return

    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)

    archivos_csv = [
        n
        for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        print(f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}")
        return

    archivo_csv = archivos_csv[0]
    path_csv = os.path.join(carpeta_csv, archivo_csv)
    df_csv = pd.read_csv(path_csv)
    df_csv = añadir_equipo_y_player_norm(df_csv)

    for _, fila in df_csv.iterrows():
        nombre_jugador = fila["player"]
        resultado = analizar_jugador_interno_precalculado(jugadores_html, df_csv, nombre_jugador)

        if not resultado["ok"]:
            print(f"\n[ERROR] {nombre_jugador}")
            print(f"  - {resultado['motivo']}")
            no_analizados_jornada.append(
                {
                    "jornada": num_jornada,
                    "partido": num_partido,
                    "jugador": nombre_jugador,
                    "equipo": fila["equipo_norm"],
                    "tipo": "NO_ANALIZADO",
                    "detalle": resultado["motivo"],
                }
            )
        elif resultado["campos_mal"]:
            mostrar_analisis_jugador(resultado)
            errores_jornada.append(
                {
                    "jornada": num_jornada,
                    "partido": num_partido,
                    "jugador": resultado["jugador_objetivo"],
                    "equipo": fila["equipo_norm"],
                    "tipo": "CAMPOS_ERRONEOS",
                    "detalle": ", ".join(resultado["campos_mal"]),
                }
            )


def analizar_jornada_completa(codigo_temporada: str, num_jornada: int):
    carpeta_csv = _carpeta_csv_jornada(codigo_temporada, num_jornada)
    if not os.path.exists(carpeta_csv):
        print(f"No existe la carpeta de la jornada {num_jornada}")
        return

    archivos_csv = sorted(
        n for n in os.listdir(carpeta_csv) if n.startswith("p") and n.endswith(".csv")
    )

    if not archivos_csv:
        print(f"No se encontraron CSVs en jornada {num_jornada}")
        return

    errores_jornada = []
    no_analizados_jornada = []

    for archivo_csv in archivos_csv:
        m = re.match(r"p(\d+)_", archivo_csv)
        if not m:
            continue
        num_partido = int(m.group(1))
        print(f"\n[LOG] ===== Procesando partido {num_partido} de la jornada {num_jornada} =====")
        analizar_partido_completo(codigo_temporada, num_jornada, num_partido,
                                  errores_jornada, no_analizados_jornada)

    print("\n" + "=" * 80)
    print(f"RESUMEN JORNADA {num_jornada}")
    if not errores_jornada and not no_analizados_jornada:
        print("Todos los jugadores han pasado las comprobaciones correctamente.")
    else:
        if no_analizados_jornada:
            print("Jugadores NO analizados en esta jornada (posibles tarjetas desde banquillo):")
            for err in no_analizados_jornada:
                print(f" - {err['jugador']} (j{err['jornada']} p{err['partido']})")
        if errores_jornada:
            print("Jugadores con errores en stats en esta jornada:")
            for err in errores_jornada:
                print(
                    f" - j{err['jornada']} p{err['partido']} | {err['jugador']} | "
                    f"{err['tipo']} | {err['detalle']}"
                )


def imprimir_resumen_global(errores_globales, no_analizados_globales, codigo_temporada: str):
    print("\n" + "=" * 80)
    print("RESUMEN GLOBAL")

    con_tarjeta_banquillo, otros_no_analizados = clasificar_no_analizados_tarjetas(
        codigo_temporada, no_analizados_globales
    )

    if con_tarjeta_banquillo or otros_no_analizados:
        print("Jugadores NO analizados (comprobación tarjetas desde banquillo):")
        for err in con_tarjeta_banquillo:
            print(f" - {err['jugador']} (j{err['jornada']} p{err['partido']})  -> TARJETA BANQUILLO")
        for err in otros_no_analizados:
            print(f" - {err['jugador']} (j{err['jornada']} p{err['partido']})  -> SIN TARJETA/NO ENCONTRADO")
        print()
    else:
        print("No hay jugadores marcados como NO_ANALIZADO.\n")

    if not errores_globales:
        print("No hay discrepancias de ninguna stat.")
        return

    cabecera = f"{'Jornada':7s} | {'Partido':7s} | {'Equipo':15s} | {'Jugador':25s} | {'Tipo':15s} | Detalle"
    print("Jugadores con errores de stats:")
    print(cabecera)
    print("-" * len(cabecera))

    for err in errores_globales:
        jornada = f"j{err['jornada']}"
        partido = f"p{err['partido']}"
        equipo = str(err.get("equipo", "-"))[:15]
        jugador = str(err['jugador'])[:25]
        tipo = str(err['tipo'])[:15]
        detalle = err['detalle']
        print(f"{jornada:7s} | {partido:7s} | {equipo:15s} | {jugador:25s} | {tipo:15s} | {detalle}")


def analizar_rango_jornadas(codigo_temporada: str, jornada_inicio: int, jornada_fin: int):
    errores_globales = []
    no_analizados_globales = []

    for j in range(jornada_inicio, jornada_fin + 1):
        carpeta_csv = _carpeta_csv_jornada(codigo_temporada, j)
        if not os.path.exists(carpeta_csv):
            print(f"No existe la carpeta de la jornada {j}")
            continue

        archivos_csv = sorted(
            n for n in os.listdir(carpeta_csv) if n.startswith("p") and n.endswith(".csv")
        )
        if not archivos_csv:
            print(f"No se encontraron CSVs en jornada {j}")
            continue

        print("\n" + "=" * 80)
        print(f"[LOG] ===== Analizando temporada {codigo_temporada} | jornada {j} =====")

        errores_jornada = []
        no_analizados_jornada = []

        for archivo_csv in archivos_csv:
            m = re.match(r"p(\d+)_", archivo_csv)
            if not m:
                continue
            num_partido = int(m.group(1))
            print(f"\n[LOG] ===== Procesando partido {num_partido} de la jornada {j} =====")
            analizar_partido_completo(codigo_temporada, j, num_partido,
                                      errores_jornada, no_analizados_jornada)

        print("\n" + "-" * 80)
        print(f"RESUMEN JORNADA {j}")
        if not errores_jornada and not no_analizados_jornada:
            print("Todos los jugadores han pasado las comprobaciones correctamente.")
        else:
            if no_analizados_jornada:
                print("Jugadores NO analizados en esta jornada (posibles tarjetas desde banquillo):")
                for err in no_analizados_jornada:
                    print(f" - {err['jugador']} (j{err['jornada']} p{err['partido']})")
            if errores_jornada:
                print("Jugadores con errores en stats en esta jornada:")
                for err in errores_jornada:
                    print(
                        f" - j{err['jornada']} p{err['partido']} | {err['jugador']} | "
                        f"{err['tipo']} | {err['detalle']}"
                    )

        errores_globales.extend(errores_jornada)
        no_analizados_globales.extend(no_analizados_jornada)

    imprimir_resumen_global(errores_globales, no_analizados_globales, codigo_temporada)


def comparar_jugador_completo(codigo_temporada: str, num_jornada: int,
                              num_partido: int, nombre_jugador: str):
    carpeta_html = _carpeta_html_partidos(codigo_temporada, num_jornada)
    carpeta_csv = _carpeta_csv_jornada(codigo_temporada, num_jornada)

    archivos_csv = [
        n
        for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        print(f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}")
        return

    archivo_csv = archivos_csv[0]
    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    path_csv = os.path.join(carpeta_csv, archivo_csv)

    if not os.path.exists(path_html):
        print(f"Falta HTML: {path_html}")
        return

    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)

    df_csv = pd.read_csv(path_csv)
    df_csv = añadir_equipo_y_player_norm(df_csv)

    info = comparar_partido_stats_precalculado(jugadores_html, df_csv, nombre_jugador)
    if info is None:
        print(f"No se pudo localizar a '{nombre_jugador}' en j{num_jornada} partido {num_partido}.")
        return

    fila_csv = info["fila_csv"]
    get_summary = info["get_summary"]
    get_passing = info["get_passing"]
    get_misc = info["get_misc"]
    get_keepers = info["get_keepers"]
    get_defense = info["get_defense"]
    get_possession = info["get_possession"]
    es_portero = info["es_portero"]

    print(f"\n=== COMPARATIVA {codigo_temporada} | J{num_jornada} P{num_partido} | {nombre_jugador} ===")

    campos_mal, discrepancias = _comparar_campos_stats(
        fila_csv, es_portero, get_summary, get_passing,
        get_misc, get_keepers, get_defense, get_possession
    )

    print(f"{'Campo':35s} | {'CSV':>10s} | {'HTML':>10s} | {'OK?':>3s}")
    print("-" * 70)

    discrep_map = {d["campo"]: d for d in discrepancias}

    for campo, _ in [
        ("Min_partido", None), ("Gol_partido", None), ("Asist_partido", None),
        ("xG_partido", None), ("Tiros", None), ("TiroFallado_partido", None),
        ("TiroPuerta_partido", None), ("Pases_Totales", None),
        ("Pases_Completados_Pct", None), ("Amarillas", None), ("Rojas", None),
        ("Goles_en_contra", None), ("Porcentaje_paradas", None), ("PSxG", None),
        ("Entradas", None), ("Duelos", None), ("DuelosGanados", None),
        ("DuelosPerdidos", None), ("Bloqueos", None), ("BloqueoTiros", None),
        ("BloqueoPase", None), ("Despejes", None), ("Regates", None),
        ("RegatesCompletados", None), ("RegatesFallidos", None),
        ("Conducciones", None), ("DistanciaConduccion", None),
        ("MetrosAvanzadosConduccion", None), ("ConduccionesProgresivas", None),
        ("DuelosAereosGanados", None), ("DuelosAereosPerdidos", None),
        ("DuelosAereosGanadosPct", None),
    ]:
        d = discrep_map.get(campo)
        if d:
            csv_v = d["csv"]
            html_v = d["html"]
            ok = "X"
        else:
            csv_v = "-"
            html_v = "-"
            ok = "✓"
        print(f"{campo:35s} | {csv_v:>10s} | {html_v:>10s} | {ok:>3s}")


if __name__ == "__main__":
    analizar_rango_jornadas("25_26", 1, 17)
