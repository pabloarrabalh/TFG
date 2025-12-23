import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from commons import (
    normalizar_texto,
    normalizar_equipo,
    aplicar_alias,
    obtener_match_nombre,
)

CAMPOS_MAPEO = [
    ("Min_partido", ["Min", "minutes", "Min"]),
    ("Gol_partido", ["Gls", "Goals", "Gls"]),
    ("Asist_partido", ["Ast", "Assists", "Ast"]),
    ("xG_partido", ["xG", "xG", "xG"]),
    ("TiroFallado_partido", ["Sh", "Shots", "Sh"]),
    ("TiroPuerta_partido", ["SoT", "Shots on target", "SoT"]),
    ("Pases_Totales", ["Cmp", "Att", "Cmp"]),
    ("Pases_Completados_Pct", ["Cmp%", "Cmp%", "Cmp%"]),
    ("Amarillas", ["CrdY", "Yellow Cards", "CrdY"]),
    ("Rojas", ["CrdR", "Red Cards", "CrdR"]),
    ("Goles_en_contra", ["GA", "GA", "GA"]),
    ("Porcentaje_paradas", ["Save%", "Save%", "Save%"]),
    ("PSxG", ["PSxG", "PSxG", "PSxG"]),
    ("Entradas", ["Tkl", "Tackles", "Tkl"]),
    ("Duelos", ["Att", "Challenges", "Att"]),
    ("DuelosGanados", ["Won", "Challenges Won", "Won"]),
    ("DuelosPerdidos", ["Lost", "Challenges Lost", "Lost"]),
    ("Bloqueos", ["Blocks", "Blocks", "Blocks"]),
    ("BloqueoTiros", ["Sh", "Shots Blocked", "Sh"]),
    ("BloqueoPase", ["Pass", "Passes Blocked", "Pass"]),
    ("Despejes", ["Clr", "Clearances", "Clr"]),
    ("Regates", ["Att", "Dribbles", "Att"]),
    ("RegatesCompletados", ["Succ", "Dribbles Succ", "Succ"]),
    ("RegatesFallidos", ["Lost", "Dribbles Lost", "Lost"]),
    ("Conducciones", ["Carries", "Carries", "Carries"]),
    ("DistanciaConduccion", ["TotDist", "Total Distance", "TotDist"]),
    ("MetrosAvanzadosConduccion", ["PrgDist", "Progressive Distance", "PrgDist"]),
    ("ConduccionesProgresivas", ["PrgC", "Progressive Carries", "PrgC"]),
    ("DuelosAereosGanados", ["Won", "Aerials Won", "Won"]),
    ("DuelosAereosPerdidos", ["Lost", "Aerials Lost", "Lost"]),
    ("DuelosAereosGanadosPct", ["Won%", "Aerials Won%", "Won%"]),
    ("puntosFantasy", ["puntosFantasy"]),
]

TABLAS_FBREF = {
    "summary": ["_summary"],
    "passing": ["_passing"],
    "defense": ["_defense"],
    "possession": ["_possession"],
    "misc": ["_misc"],
    # Adaptado para tablas de portero tipo keeper_stats_XXXX
    "keepers": ["keeper_stats_"],
}


def limpiar_float(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return 0.0


def limpiar_numero(val):
    """
    Normaliza valores numéricos para comparación:
    - Quita % y saltos de línea.
    - Convierte a float.
    - Si es NaN o no convertible, devuelve 0.0.
    """
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if val is None:
        return 0.0
    s = str(val).split('\n')[0].replace('%', '').strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def extraer_tablas_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    tablas = {}
    for tipo, sufijos in TABLAS_FBREF.items():
        dfs = []
        for tabla in soup.find_all('table'):
            tid = tabla.get('id') or ''
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
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in cols
            ]
            dfs.append(df)
        if dfs:
            tablas[tipo] = pd.concat(dfs, ignore_index=True)
    return tablas


def construir_diccionario_jugadores(tablas):
    jugadores = {}
    for tipo, df in tablas.items():
        for _, row in df.iterrows():
            nombre = str(row.get('Player', '')).strip()
            if nombre in ['nan', 'Player', 'Total', 'Players'] or re.match(r'^\d+\s+Players$', nombre):
                continue
            equipo = str(row.get('Squad', '')).strip() if 'Squad' in row else None
            equipo_norm = normalizar_equipo(equipo) if equipo else None
            nombre_norm = normalizar_texto(aplicar_alias(nombre, equipo_norm))
            if nombre_norm not in jugadores:
                jugadores[nombre_norm] = {}
            for col in row.index:
                key = f"{tipo}:{col}"
                if key not in jugadores[nombre_norm]:
                    val = row[col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    if isinstance(val, str):
                        val = val.split('\n')[0].strip()
                    jugadores[nombre_norm][key] = val
    return jugadores


def buscar_valor(jugador_dict, posibles_campos, preferencia_tipo=None):
    if preferencia_tipo is None:
        preferencia_tipo = list(TABLAS_FBREF.keys())
    for campo in posibles_campos:
        for tipo in preferencia_tipo:
            key = f"{tipo}:{campo}"
            if key in jugador_dict:
                return jugador_dict[key]
    return None


def fmt(val):
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except:
        return str(val)


def mostrar_analisis_jugador(resultado):
    """
    Imprime solo los campos con error, no toda la comparativa.
    """
    if not resultado["ok"]:
        print(resultado["motivo"])
        return

    nombre = resultado["jugador_objetivo"]
    campos_mal = resultado["campos_mal"]
    discrepancias = resultado["discrepancias"]

    if not campos_mal:
        return

    print(f"\n[ERROR] {nombre}")
    for d in discrepancias:
        campo = d["campo"]
        csv_val = d["csv"]
        html_val = d["html"]
        print(f"  - {campo}: CSV={csv_val} | HTML={html_val}")


def comparar_partido_stats(path_html, path_csv, jugador_objetivo="kylian mbappe"):
    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)
    df_csv = pd.read_csv(path_csv)
    df_csv["player_norm"] = df_csv.apply(
        lambda row: normalizar_texto(aplicar_alias(row["player"], row["Equipo_propio"])), axis=1
    )

    # Buscar fila del CSV
    fila_jugador = df_csv[df_csv["player_norm"].str.lower() == normalizar_texto(aplicar_alias(jugador_objetivo)).lower()]
    if fila_jugador.empty:
        return None

    fila_csv = fila_jugador.iloc[0]
    equipo_jugador = fila_csv["Equipo_propio"]

    # Nombre normalizado directo
    jugador_norm = normalizar_texto(aplicar_alias(jugador_objetivo, equipo_jugador))

    if jugador_norm not in jugadores_html:
        # Intentar match inteligente usando obtener_match_nombre
        nombres_norm_equipo = list(jugadores_html.keys())
        match_norm, score = obtener_match_nombre(jugador_objetivo, nombres_norm_equipo)
        if match_norm is None:
            return None
        jugador_norm = match_norm

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

    es_portero = str(fila_csv.get('posicion', '')).strip().upper() == 'PT'

    return {
        "jugador_objetivo": jugador_objetivo,
        "fila_csv": fila_csv,
        "row_html": row_html,
        "get_summary": get_summary,
        "get_passing": get_passing,
        "get_misc": get_misc,
        "get_keepers": get_keepers,
        "get_defense": get_defense,
        "get_possession": get_possession,
        "es_portero": es_portero,
    }


# ========= ANALISIS JUGADOR / PARTIDO =========

def analizar_jugador_interno(num_jornada, num_partido, nombre_jugador):
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")

    archivos_csv = [
        n for n in os.listdir(carpeta_csv)
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

    # Primer intento normal
    info = comparar_partido_stats(path_html, path_csv, nombre_jugador)
    if info is None:
        # Intento extra: emparejar nombre con claves del HTML
        with open(path_html, "r", encoding="utf-8") as f:
            html_content = f.read()
        tablas = extraer_tablas_fbref(html_content)
        jugadores_html = construir_diccionario_jugadores(tablas)
        nombres_norm_equipo = list(jugadores_html.keys())
        match_norm, score = obtener_match_nombre(nombre_jugador, nombres_norm_equipo)
        if match_norm is None:
            return {
                "ok": False,
                "motivo": f"No se pudo analizar al jugador '{nombre_jugador}' en j{num_jornada} partido {num_partido}.",
            }
        info = comparar_partido_stats(path_html, path_csv, match_norm)
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
        ("Min_partido", lambda: (fila_csv.get('Min_partido',''), get_summary('Min'))),
        ("Gol_partido", lambda: (fila_csv.get('Gol_partido',''), get_summary('Gls'))),
        ("Asist_partido", lambda: (fila_csv.get('Asist_partido',''), get_summary('Ast'))),
        ("xG_partido", lambda: (fila_csv.get('xG_partido',''), get_summary('xG'))),
        ("Tiros", lambda: (fila_csv.get('Tiros',''), get_summary('Sh'))),
        ("TiroFallado_partido", lambda: (
            fila_csv.get('TiroFallado_partido',''),
            (float(get_summary('Sh')) - float(get_summary('SoT'))) if get_summary('Sh') != "" and get_summary('SoT') != "" else 0.0
        )),
        ("TiroPuerta_partido", lambda: (fila_csv.get('TiroPuerta_partido',''), get_summary('SoT'))),
        ("Pases_Totales", lambda: (fila_csv.get('Pases_Totales',''), get_summary('Att'))),
        ("Pases_Completados_Pct", lambda: (
            fila_csv.get('Pases_Completados_Pct',''),
            get_passing('Cmp%') if get_passing('Cmp%') != "" else get_summary('Cmp%')
        )),
        ("Amarillas", lambda: (fila_csv.get('Amarillas',''), get_misc('CrdY'))),
        ("Rojas", lambda: (fila_csv.get('Rojas',''), get_misc('CrdR'))),
        ("Goles_en_contra", lambda: (
            fila_csv.get('Goles_en_contra',''),
            limpiar_numero(get_keepers('GA')) if es_portero else 0
        )),
        ("Porcentaje_paradas", lambda: (
            fila_csv.get('Porcentaje_paradas',''),
            limpiar_numero(get_keepers('Save%')) if es_portero else 0
        )),
        ("PSxG", lambda: (
            fila_csv.get('PSxG',''),
            limpiar_numero(get_keepers('PSxG')) if es_portero else 0
        )),
        ("Entradas", lambda: (fila_csv.get('Entradas',''), get_defense('Tkl'))),
        ("Duelos", lambda: (fila_csv.get('Duelos',''), get_defense('Att'))),
        ("DuelosGanados", lambda: (fila_csv.get('DuelosGanados',''), get_defense('Won'))),
        ("DuelosPerdidos", lambda: (fila_csv.get('DuelosPerdidos',''), get_defense('Lost'))),
        ("Bloqueos", lambda: (fila_csv.get('Bloqueos',''), get_defense('Blocks'))),
        ("BloqueoTiros", lambda: (fila_csv.get('BloqueoTiros',''), get_defense('Sh'))),
        ("BloqueoPase", lambda: (fila_csv.get('BloqueoPase',''), get_defense('Pass'))),
        ("Despejes", lambda: (fila_csv.get('Despejes',''), get_defense('Clr'))),
        ("Regates", lambda: (fila_csv.get('Regates',''), get_possession('Att'))),
        ("RegatesCompletados", lambda: (fila_csv.get('RegatesCompletados',''), get_possession('Succ'))),
        ("RegatesFallidos", lambda: (fila_csv.get('RegatesFallidos',''), get_possession('Tkld'))),
        ("Conducciones", lambda: (fila_csv.get('Conducciones',''), get_possession('Carries'))),
        ("DistanciaConduccion", lambda: (fila_csv.get('DistanciaConduccion',''), get_possession('TotDist'))),
        ("MetrosAvanzadosConduccion", lambda: (fila_csv.get('MetrosAvanzadosConduccion',''), get_possession('PrgDist'))),
        ("ConduccionesProgresivas", lambda: (fila_csv.get('ConduccionesProgresivas',''), get_possession('PrgC'))),
        ("DuelosAereosGanados", lambda: (fila_csv.get('DuelosAereosGanados',''), get_misc('Won'))),
        ("DuelosAereosPerdidos", lambda: (fila_csv.get('DuelosAereosPerdidos',''), get_misc('Lost'))),
        ("DuelosAereosGanadosPct", lambda: (fila_csv.get('DuelosAereosGanadosPct',''), limpiar_numero(get_misc('Won%')))),
    ]

    campos_mal = []
    discrepancias = []
    for campo, getter in campos_a_comprobar:
        val_csv, val_html = getter()
        val_csv_n = limpiar_numero(val_csv)
        val_html_n = limpiar_numero(val_html)
        if val_csv_n != val_html_n:
            campos_mal.append(campo)
            discrepancias.append({
                "campo": campo,
                "csv": fmt(val_csv_n),
                "html": fmt(val_html_n),
            })

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
    """
    Analiza un partido completo y acumula los jugadores con errores
    en la lista 'errores_jornada' (lista de dicts).
    """
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    archivos_csv = [
        n for n in os.listdir(carpeta_csv)
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
            errores_jornada.append({
                "jornada": num_jornada,
                "partido": num_partido,
                "jugador": nombre_jugador,
                "tipo": "NO_ANALIZADO",
                "detalle": resultado["motivo"],
            })
        elif resultado["campos_mal"]:
            mostrar_analisis_jugador(resultado)
            errores_jornada.append({
                "jornada": num_jornada,
                "partido": num_partido,
                "jugador": resultado["jugador_objetivo"],
                "tipo": "CAMPOS_ERRONEOS",
                "detalle": ", ".join(resultado["campos_mal"]),
            })


def analizar_jornada_completa(num_jornada):
    """
    Recorre todos los partidos de la jornada (todos los pX_*.csv)
    y para cada partido recorre todos los jugadores, mostrando solo
    los que tienen errores y, al final, un resumen global de la jornada.
    """
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    if not os.path.exists(carpeta_csv):
        print(f"No existe la carpeta de la jornada {num_jornada}")
        return

    archivos_csv = sorted(
        n for n in os.listdir(carpeta_csv)
        if n.startswith("p") and n.endswith(".csv")
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

    # RESUMEN FINAL DE JORNADA
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


if __name__ == "__main__":
    analizar_jornada_completa(1)
