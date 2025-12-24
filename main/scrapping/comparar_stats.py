import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz

from commons import (
    normalizar_texto,
    normalizar_equipo,
    aplicar_alias_contextual,
    obtener_match_nombre,  # importado pero sobrescrito localmente
)

# ==== Sobrescritura local de obtener_match_nombre para usar alias contextual ====


def _obtener_match_nombre_local(nombre_raw, nombres_norm_equipo, equipo_norm=None, score_cutoff=75):
    """
    nombres_norm_equipo: lista de nombres YA normalizados (mismo orden que la lista cruda).
    Devuelve (nombre_match_norm, score, idx).
    """
    if not nombres_norm_equipo:
        return None, 0, -1

    if equipo_norm is not None:
        equipo_norm = normalizar_equipo(equipo_norm)

    nombre_norm = normalizar_texto(
        aplicar_alias_contextual(nombre_raw, equipo_norm)
    )
    tokens = nombre_norm.split()

    # 1) match directo si ya está en la lista
    if nombre_norm in nombres_norm_equipo:
        idx = nombres_norm_equipo.index(nombre_norm)
        return nombre_norm, 100, idx

    # 2) si es un único token tipo "pepelu"/"chimy", intenta por prefijo/sufijo
    if len(tokens) == 1:
        t = tokens[0]
        candidatos = [(i, n) for i, n in enumerate(nombres_norm_equipo)
                      if n.endswith(t) or n.startswith(t)]
        if len(candidatos) == 1:
            i, n = candidatos[0]
            return n, 95, i

    # 3) fuzzy estándar sobre las claves normalizadas
    match_norm, score, _ = process.extractOne(
        nombre_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if match_norm and score >= score_cutoff:
        idx = nombres_norm_equipo.index(match_norm)
        return match_norm, score, idx

    return None, 0, -1


TABLAS_FBREF = {
    "summary": ["_summary"],
    "passing": ["_passing"],
    "defense": ["_defense"],
    "possession": ["_possession"],
    "misc": ["_misc"],
    "keepers": ["keeper_stats_"],
}


def limpiar_numero(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if val is None:
        return 0.0
    s = str(val).split("\n")[0].replace("%", "").strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def fmt(val):
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(val)


def extraer_tablas_fbref(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    tablas = {}
    for tipo, sufijos in TABLAS_FBREF.items():
        dfs = []
        for tabla in soup.find_all("table"):
            tid = tabla.get("id") or ""
            if tipo == "keepers":
                if not any(suf in tid for suf in sufijos):
                    continue
            else:
                if not any(tid.endswith(suf) for suf in sufijos):
                    continue
            try:
                df = pd.read_html(str(tabla))[0]
            except Exception:
                df = None
            if df is None:
                continue
            try:
                cols = df.columns.get_level_values(-1)
            except Exception:
                cols = df.columns
            df.columns = [
                str(col).split(",")[-1].strip(" ()'").replace(" ", "")
                for col in cols
            ]
            dfs.append(df)
        if dfs:
            tablas[tipo] = pd.concat(dfs, ignore_index=True)
    return tablas


def construir_diccionario_jugadores(tablas):
    jugadores = {}
    for tipo, df in tablas.items():
        posibles_cols_squad = ["Squad", "Team", "Equipo", "Club"]
        col_squad = next((c for c in posibles_cols_squad if c in df.columns), None)

        for _, row in df.iterrows():
            nombre = str(row.get("Player", "")).strip()
            if nombre in ["nan", "Player", "Total", "Players"] or re.match(
                r"^\d+\s+Players$", nombre
            ):
                continue

            equipo = str(row.get(col_squad, "")).strip() if col_squad else None
            equipo_norm = normalizar_equipo(equipo) if equipo else None

            nombre_norm = normalizar_texto(
                aplicar_alias_contextual(nombre, equipo_norm)
            )

            if nombre_norm not in jugadores:
                jugadores[nombre_norm] = {}
            for col in row.index:
                key = f"{tipo}:{col}"
                if key not in jugadores[nombre_norm]:
                    val = row[col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    if isinstance(val, str):
                        val = val.split("\n")[0].strip()
                    jugadores[nombre_norm][key] = val
    return jugadores


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


def _posicion_csv_es_medio(fila_csv):
    pos = str(fila_csv.get("posicion", "")).upper()
    return any(p in pos for p in ["MC", "MD", "MI", "MCD", "MCO", "MF", "DM", "CM"])


def _posicion_csv_es_defensa(fila_csv):
    pos = str(fila_csv.get("posicion", "")).upper()
    return any(p in pos for p in ["DF", "DC", "LD", "LI", "CB", "LB", "RB"])


def _posicion_html(row_html):
    for key in ["summary:Pos", "summary:position", "Pos", "position"]:
        if key in row_html:
            return str(row_html[key]).upper()
    return ""


def _normalizar_para_html(nombre_raw, equipo_norm, jugadores_html):
    """
    Devuelve la clave adecuada para jugadores_html:
    - Usa alias contextual (pepelu) si existe en HTML.
    - Si no, usa el nombre normalizado sin alias (jose luis garcia vaya).
    - Si ninguno existe, devuelve el alias (para que siga funcionando fuzzy con apodos).
    """
    equipo_norm_n = normalizar_equipo(equipo_norm) if equipo_norm else None

    nombre_alias = normalizar_texto(
        aplicar_alias_contextual(nombre_raw, equipo_norm_n)
    )
    nombre_sin_alias = normalizar_texto(nombre_raw)

    if nombre_alias in jugadores_html:
        return nombre_alias
    if nombre_sin_alias in jugadores_html:
        return nombre_sin_alias
    return nombre_alias


def comparar_partido_stats(path_html, path_csv, jugador_objetivo):
    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)

    df_csv = pd.read_csv(path_csv)

    df_csv["equipo_norm"] = df_csv["Equipo_propio"].apply(normalizar_equipo)

    df_csv["player_norm"] = df_csv.apply(
        lambda row: normalizar_texto(
            aplicar_alias_contextual(row["player"], row["equipo_norm"])
        ),
        axis=1,
    )

    fila_jugador = None
    equipo_jugador = None

    # 1) exacto por equipo propio
    for eq in df_csv["equipo_norm"].unique().tolist():
        obj_norm_eq = normalizar_texto(
            aplicar_alias_contextual(jugador_objetivo, eq)
        )
        cand = df_csv[
            (df_csv["equipo_norm"] == eq) & (df_csv["player_norm"] == obj_norm_eq)
        ]
        if not cand.empty:
            fila_jugador = cand.iloc[0]
            equipo_jugador = eq
            break

    # 2) fuzzy CSV si no hubo match exacto
    if fila_jugador is None:
        nombres_csv_raw = df_csv["player"].tolist()
        equipo_norm_fuzzy = (
            df_csv["equipo_norm"].iloc[0] if not df_csv.empty else None
        )
        nombres_norm = [
            normalizar_texto(
                aplicar_alias_contextual(n, equipo_norm_fuzzy)
            )
            for n in nombres_csv_raw
        ]

        match_raw_norm, score, idx = _obtener_match_nombre_local(
            jugador_objetivo,
            nombres_norm,
            equipo_norm=equipo_norm_fuzzy,
        )
        if match_raw_norm is None or idx < 0:
            return None

        fila_jugador = df_csv.iloc[idx]
        equipo_jugador = fila_jugador["equipo_norm"]

    if fila_jugador is None:
        return None

    # clave objetivo para HTML (gestiona pepelu vs jose luis garcia vaya)
    jugador_norm = _normalizar_para_html(jugador_objetivo, equipo_jugador, jugadores_html)

    nombres_html = list(jugadores_html.keys())

    # 3) match HTML: exacto o fuzzy con filtro por posición
    if jugador_norm not in jugadores_html:
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


def analizar_jugador_interno(num_jornada, num_partido, nombre_jugador):
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")

    archivos_csv = [
        n
        for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        return {
            "ok": False,
            "motivo": f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}",
        }

    archivo_csv = archivos_csv[0]
    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    path_csv = os.path.join(carpeta_csv, archivo_csv)

    if not os.path.exists(path_html):
        return {
            "ok": False,
            "motivo": f"Falta HTML: {path_html}",
        }

    info = comparar_partido_stats(path_html, path_csv, nombre_jugador)
    if info is None:
        return {
            "ok": False,
            "motivo": f"No se pudo analizar al jugador '{nombre_jugador}' en j{num_jornada} partido {num_partido}.",
        }

    fila_csv = info["fila_csv"]
    get_summary = info["get_summary"]
    get_passing = info["get_passing"]
    get_misc = info["get_misc"]
    get_keepers = info["get_keepers"]
    get_defense = info["get_defense"]
    get_possession = info["get_possession"]
    es_portero = info["es_portero"]

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
                if get_summary("Sh") != "" and get_summary("SoT") != ""
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
                get_passing("Cmp%") if get_passing("Cmp%") != "" else get_summary("Cmp%"),
            ),
        ),
        ("Amarillas", lambda: (fila_csv.get("Amarillas", ""), get_misc("CrdY"))),
        ("Rojas", lambda: (fila_csv.get("Rojas", ""), get_misc("CrdR"))),
        (
            "Goles_en_contra",
            lambda: (
                fila_csv.get("Goles_en_contra", ""),
                limpiar_numero(get_keepers("GA")) if es_portero else 0,
            ),
        ),
        (
            "Porcentaje_paradas",
            lambda: (
                fila_csv.get("Porcentaje_paradas", ""),
                limpiar_numero(get_keepers("Save%")) if es_portero else 0,
            ),
        ),
        (
            "PSxG",
            lambda: (
                fila_csv.get("PSxG", ""),
                limpiar_numero(get_keepers("PSxG")) if es_portero else 0,
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
                limpiar_numero(get_misc("Won%")),
            ),
        ),
    ]

    campos_mal = []
    discrepancias = []
    for campo, getter in campos_a_comprobar:
        val_csv, val_html = getter()
        val_csv_n = limpiar_numero(val_csv)
        val_html_n = limpiar_numero(val_html)
        if val_csv_n != val_html_n:
            campos_mal.append(campo)
            discrepancias.append(
                {"campo": campo, "csv": fmt(val_csv_n), "html": fmt(val_html_n)}
            )

    return {
        "ok": True,
        "jugador_objetivo": nombre_jugador,
        "info": info,
        "campos_mal": campos_mal,
        "discrepancias": discrepancias,
    }


def analizar_jugador(num_jornada, num_partido, nombre_jugador):
    print(f"[LOG] Procesando jugador: {nombre_jugador}")
    resultado = analizar_jugador_interno(num_jornada, num_partido, nombre_jugador)
    mostrar_analisis_jugador(resultado)


def analizar_partido_completo(num_jornada, num_partido, errores_jornada):
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
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

    for _, fila in df_csv.iterrows():
        nombre_jugador = fila["player"]
        print(f"[LOG] Procesando jugador: {nombre_jugador}")
        resultado = analizar_jugador_interno(num_jornada, num_partido, nombre_jugador)

        if not resultado["ok"]:
            print(f"\n[ERROR] {nombre_jugador}")
            print(f"  - {resultado['motivo']}")
            errores_jornada.append(
                {
                    "jornada": num_jornada,
                    "partido": num_partido,
                    "jugador": nombre_jugador,
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
                    "tipo": "CAMPOS_ERRONEOS",
                    "detalle": ", ".join(resultado["campos_mal"]),
                }
            )


def analizar_jornada_completa(num_jornada):
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
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

    for archivo_csv in archivos_csv:
        m = re.match(r"p(\d+)_", archivo_csv)
        if not m:
            continue
        num_partido = int(m.group(1))
        print(f"\n[LOG] ===== Procesando partido {num_partido} de la jornada {num_jornada} =====")
        analizar_partido_completo(num_jornada, num_partido, errores_jornada)

    print("\n" + "=" * 80)
    print(f"RESUMEN JORNADA {num_jornada}")
    if not errores_jornada:
        print("Todos los jugadores han pasado las comprobaciones correctamente.")
    else:
        print("Jugadores con errores:")
        for err in errores_jornada:
            print(
                f" - j{err['jornada']} p{err['partido']} | {err['jugador']} | "
                f"{err['tipo']} | {err['detalle']}"
            )
def comparar_jugador_completo(num_jornada, num_partido, nombre_jugador):
    """
    Muestra por consola una comparativa CSV vs HTML de todas las stats
    para un jugador concreto en un partido concreto.
    """
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")

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

    info = comparar_partido_stats(path_html, path_csv, nombre_jugador)
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

    print(f"\n=== COMPARATIVA J{num_jornada} P{num_partido} | {nombre_jugador} ===")

    # Lista de campos a comparar (los mismos que en analizar_jugador_interno)
    campos_a_comprobar = [
        ("Min_partido",        "CSV: Min_partido",            lambda: (fila_csv.get("Min_partido", ""), get_summary("Min"))),
        ("Gol_partido",        "Goles",                       lambda: (fila_csv.get("Gol_partido", ""), get_summary("Gls"))),
        ("Asist_partido",      "Asistencias",                 lambda: (fila_csv.get("Asist_partido", ""), get_summary("Ast"))),
        ("xG_partido",         "xG",                          lambda: (fila_csv.get("xG_partido", ""), get_summary("xG"))),
        ("Tiros",              "Tiros totales",               lambda: (fila_csv.get("Tiros", ""), get_summary("Sh"))),
        ("TiroFallado_partido","Tiros fallados",             lambda: (
            fila_csv.get("TiroFallado_partido", ""),
            (float(get_summary("Sh")) - float(get_summary("SoT")))
            if get_summary("Sh") != "" and get_summary("SoT") != "" else 0.0,
        )),
        ("TiroPuerta_partido", "Tiros a puerta",              lambda: (fila_csv.get("TiroPuerta_partido", ""), get_summary("SoT"))),
        ("Pases_Totales",      "Pases totales",               lambda: (fila_csv.get("Pases_Totales", ""), get_summary("Att"))),
        ("Pases_Completados_Pct","% pases completados",       lambda: (
            fila_csv.get("Pases_Completados_Pct", ""),
            get_passing("Cmp%") if get_passing("Cmp%") != "" else get_summary("Cmp%"),
        )),
        ("Amarillas",          "Amarillas",                   lambda: (fila_csv.get("Amarillas", ""), get_misc("CrdY"))),
        ("Rojas",              "Rojas",                       lambda: (fila_csv.get("Rojas", ""), get_misc("CrdR"))),
        ("Goles_en_contra",    "Goles en contra",             lambda: (
            fila_csv.get("Goles_en_contra", ""),
            limpiar_numero(get_keepers("GA")) if es_portero else 0,
        )),
        ("Porcentaje_paradas", "% paradas",                   lambda: (
            fila_csv.get("Porcentaje_paradas", ""),
            limpiar_numero(get_keepers("Save%")) if es_portero else 0,
        )),
        ("PSxG",               "PSxG",                        lambda: (
            fila_csv.get("PSxG", ""),
            limpiar_numero(get_keepers("PSxG")) if es_portero else 0,
        )),
        ("Entradas",           "Entradas",                    lambda: (fila_csv.get("Entradas", ""), get_defense("Tkl"))),
        ("Duelos",             "Duelos",                      lambda: (fila_csv.get("Duelos", ""), get_defense("Att"))),
        ("DuelosGanados",      "Duelos ganados",              lambda: (fila_csv.get("DuelosGanados", ""), get_defense("Won"))),
        ("DuelosPerdidos",     "Duelos perdidos",             lambda: (fila_csv.get("DuelosPerdidos", ""), get_defense("Lost"))),
        ("Bloqueos",           "Bloqueos",                    lambda: (fila_csv.get("Bloqueos", ""), get_defense("Blocks"))),
        ("BloqueoTiros",       "Bloqueo tiros",               lambda: (fila_csv.get("BloqueoTiros", ""), get_defense("Sh"))),
        ("BloqueoPase",        "Bloqueo pases",               lambda: (fila_csv.get("BloqueoPase", ""), get_defense("Pass"))),
        ("Despejes",           "Despejes",                    lambda: (fila_csv.get("Despejes", ""), get_defense("Clr"))),
        ("Regates",            "Regates intentados",          lambda: (fila_csv.get("Regates", ""), get_possession("Att"))),
        ("RegatesCompletados", "Regates completados",         lambda: (fila_csv.get("RegatesCompletados", ""), get_possession("Succ"))),
        ("RegatesFallidos",    "Regates fallidos",            lambda: (fila_csv.get("RegatesFallidos", ""), get_possession("Tkld"))),
        ("Conducciones",       "Conducciones",                lambda: (fila_csv.get("Conducciones", ""), get_possession("Carries"))),
        ("DistanciaConduccion","Distancia conducciones",      lambda: (fila_csv.get("DistanciaConduccion", ""), get_possession("TotDist"))),
        ("MetrosAvanzadosConduccion","Metros avanzados conduccion", lambda: (fila_csv.get("MetrosAvanzadosConduccion", ""), get_possession("PrgDist"))),
        ("ConduccionesProgresivas","Conducciones progresivas",lambda: (fila_csv.get("ConduccionesProgresivas", ""), get_possession("PrgC"))),
        ("DuelosAereosGanados","Duelos aéreos ganados",       lambda: (fila_csv.get("DuelosAereosGanados", ""), get_misc("Won"))),
        ("DuelosAereosPerdidos","Duelos aéreos perdidos",     lambda: (fila_csv.get("DuelosAereosPerdidos", ""), get_misc("Lost"))),
        ("DuelosAereosGanadosPct","% duelos aéreos ganados",  lambda: (
            fila_csv.get("DuelosAereosGanadosPct", ""),
            limpiar_numero(get_misc("Won%")),
        )),
    ]

    # Encabezado de tabla
    print(f"{'Campo':35s} | {'CSV':>10s} | {'HTML':>10s} | {'OK?':>3s}")
    print("-" * 70)

    for campo, etiqueta, getter in campos_a_comprobar:
        val_csv, val_html = getter()
        val_csv_n = limpiar_numero(val_csv)
        val_html_n = limpiar_numero(val_html)
        ok = "✓" if val_csv_n == val_html_n else "X"
        print(f"{etiqueta:35s} | {fmt(val_csv_n):>10s} | {fmt(val_html_n):>10s} | {ok:>3s}")


if __name__ == "__main__":
    analizar_jornada_completa(1)
    #comparar_jugador_completo(1,5,"Jose Luis Garcia Vaya")